"""Approval-gated, Python-only current-user filesystem mutations.

The planner intentionally recognizes a very small English/Spanish grammar.
Anything else falls through to typed model preflight.  Plans contain exact
filesystem identity bindings and are reviewed again immediately before the TUI
may ask the user for one-use approval.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from .async_boundary import run_blocking_once
from .local_filesystem import (
    LocalFilesystemPlanner,
    _has_hidden_component,
    _is_relative_to,
    _is_sensitive_filename,
    _open_descriptor_path,
    _parse_xdg_file,
    _symlink_in_parents,
    _target_category,
)
from .models import (
    LocalFilesystemMutationPlan,
    LocalMutationOperation,
    MutationReview,
    OneUseApproval,
)
from .terminal_safety import sanitize_and_redact_terminal_text

MAX_TEXT_BYTES = 64 * 1024
DISPLAY_LIMIT = 12_000
_SHELL = re.compile(r"(?:[;&|`<>]|\$\(|\n|\r)")
_PROTECTED_ROOTS = tuple(
    Path(value)
    for value in (
        "/boot",
        "/dev",
        "/proc",
        "/sys",
        "/run/credentials",
        "/run/secrets",
        "/etc/ssh",
        "/etc/ssl/private",
        "/etc/sudoers.d",
        "/etc/polkit-1",
        "/etc/NetworkManager/system-connections",
        "/var/lib/AccountsService",
        "/var/lib/NetworkManager",
        "/var/lib/sss",
    )
)
_PROTECTED_PARTS = {
    ".ssh",
    ".gnupg",
    ".pki",
    "keyrings",
    "keyring",
    "credentials",
    "secrets",
    "password-store",
    "mozilla",
    "chromium",
    "google-chrome",
}


class LocalMutationError(RuntimeError):
    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class LocalMutationClarification:
    code: str
    question: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class LocalMutationPlanningResult:
    matched: bool
    plan: LocalFilesystemMutationPlan | None = None
    clarification: LocalMutationClarification | None = None
    denial_code: str | None = None
    denial_message: str | None = None


@dataclass(frozen=True)
class LocalFilesystemMutationResult:
    operation: LocalMutationOperation
    status: str
    display_text: str
    plan_digest: str
    target_digest: str
    target_category: str
    duration_ms: int
    sanitized_or_redacted: bool
    rollback_available: bool
    error_code: str | None = None

    def audit_metadata(self) -> dict[str, object]:
        return {
            "operation": self.operation.value,
            "status": self.status,
            "plan_digest": self.plan_digest,
            "target_digest": self.target_digest,
            "target_category": self.target_category,
            "duration_ms": self.duration_ms,
            "sanitized_or_redacted": self.sanitized_or_redacted,
            "rollback_available": self.rollback_available,
            "error_code": self.error_code,
        }


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    return value


def _protected(path: Path, home: Path) -> str | None:
    absolute = path.absolute()
    if absolute == Path("/"):
        return "local_mutation.root_denied"
    if any(absolute == root or _is_relative_to(absolute, root) for root in _PROTECTED_ROOTS):
        return "local_mutation.protected_target"
    if any(part.casefold() in _PROTECTED_PARTS for part in absolute.parts):
        return "local_mutation.sensitive_store"
    if any(_is_sensitive_filename(part) for part in absolute.parts):
        return "local_mutation.sensitive_filename"
    if _has_hidden_component(absolute, home):
        return "local_mutation.hidden_target_denied"
    return None


def _valid_leaf(name: str) -> bool:
    return (
        bool(name)
        and name not in {".", ".."}
        and "/" not in name
        and "\x00" not in name
        and not any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in name)
        and not name.startswith(".")
        and len(os.fsencode(name)) <= 255
        and not _is_sensitive_filename(name)
    )


class LocalFilesystemMutationPlanner:
    """Build exact plans for simple create and move-to-trash requests."""

    _CREATE_DIRECTORY = tuple(
        re.compile(value, re.IGNORECASE)
        for value in (
            r"create\s+(?:a\s+)?(?:new\s+)?(?:directory|folder)\s+(?:in|inside|under)\s+(?P<parent>.+?)\s+(?:named|called)\s+(?P<name>.+)",
            r"create\s+(?:a\s+)?(?:new\s+)?(?:directory|folder)\s+(?P<name>[^/]+?)\s+(?:in|inside|under)\s+(?P<parent>.+)",
            r"crea(?:r)?\s+(?:un\s+|una\s+)?(?:nuevo\s+|nueva\s+)?(?:directorio|carpeta)\s+(?:en|dentro\s+de)\s+(?P<parent>.+?)\s+(?:llamad[oa]|con\s+nombre)\s+(?P<name>.+)",
            r"crea(?:r)?\s+(?:un\s+|una\s+)?(?:directorio|carpeta)\s+(?P<name>[^/]+?)\s+(?:en|dentro\s+de)\s+(?P<parent>.+)",
        )
    )
    _CREATE_FILE = tuple(
        re.compile(value, re.IGNORECASE)
        for value in (
            r"create\s+(?:a\s+)?(?:new\s+)?(?:empty\s+)?(?:text\s+)?file\s+(?:in|inside|under)\s+(?P<parent>.+?)\s+(?:named|called)\s+(?P<name>.+)",
            r"crea(?:r)?\s+(?:un\s+)?(?:nuevo\s+)?archivo(?:\s+de\s+texto)?\s+(?:en|dentro\s+de)\s+(?P<parent>.+?)\s+(?:llamado|con\s+nombre)\s+(?P<name>.+)",
        )
    )
    _CREATE_DIRECTORY_PATH = re.compile(
        r"create\s+(?:a\s+)?(?:new\s+)?(?:directory|folder)\s+(?P<path>(?:/|~/|workspace/|project/|desktop/|escritorio/).+)",
        re.IGNORECASE,
    )
    _CREATE_DIRECTORY_PATH_ES = re.compile(
        r"crea(?:r)?\s+(?:un\s+|una\s+)?(?:nuevo\s+|nueva\s+)?(?:directorio|carpeta)\s+(?P<path>(?:/|~/|workspace/|project/|desktop/|escritorio/).+)",
        re.IGNORECASE,
    )
    _TRASH = tuple(
        re.compile(value, re.IGNORECASE)
        for value in (
            r"(?:delete|remove)\s+(?:the\s+)?(?:file|directory|folder)\s+(?P<target>.+)",
            r"(?:trash|move\s+to\s+trash)\s+(?:the\s+)?(?:(?:file|directory|folder)\s+)?(?P<target>.+)",
            r"(?:elimina(?:r)?|borra(?:r)?)\s+(?:el\s+|la\s+)?(?:archivo|directorio|carpeta)\s+(?P<target>.+)",
            r"mueve\s+a\s+la\s+papelera\s+(?:el\s+|la\s+)?(?:(?:archivo|directorio|carpeta)\s+)?(?P<target>.+)",
        )
    )

    def __init__(
        self,
        filesystem_planner: LocalFilesystemPlanner,
        *,
        identifier=lambda prefix: f"{prefix}_{os.urandom(16).hex()}",
    ) -> None:
        self.paths = filesystem_planner
        self.workspace = filesystem_planner.workspace
        self.home = filesystem_planner.home
        self.identifier = identifier

    def plan(self, text: str) -> LocalMutationPlanningResult:
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > 4_000
            or _SHELL.search(text)
        ):
            return LocalMutationPlanningResult(matched=False)
        value = text.strip().rstrip(".")
        folded = value.casefold()
        if folded in {
            "create a directory",
            "create directory",
            "create a folder",
            "create folder",
            "crear directorio",
            "crear carpeta",
            "delete a file",
            "delete file",
            "remove a directory",
            "borrar archivo",
            "eliminar carpeta",
        }:
            return LocalMutationPlanningResult(
                matched=True,
                clarification=LocalMutationClarification(
                    "local_mutation.missing_target",
                    "Which exact path should I change?",
                    (
                        "Desktop/Escritorio",
                        "Current workspace",
                        "Specify another exact path",
                    ),
                ),
            )
        for pattern in self._CREATE_DIRECTORY:
            if match := pattern.fullmatch(value):
                return self._plan_create(
                    LocalMutationOperation.CREATE_DIRECTORY,
                    _unquote(match.group("parent")),
                    _unquote(match.group("name")),
                    content=None,
                )
        for pattern in (self._CREATE_DIRECTORY_PATH, self._CREATE_DIRECTORY_PATH_ES):
            if match := pattern.fullmatch(value):
                requested = _unquote(match.group("path"))
                parent, separator, name = requested.rpartition("/")
                if not separator:
                    return self._deny(
                        "local_mutation.invalid_target",
                        "The exact destination path is invalid.",
                    )
                return self._plan_create(
                    LocalMutationOperation.CREATE_DIRECTORY,
                    parent or "/",
                    name,
                    content=None,
                )
        for pattern in self._CREATE_FILE:
            if match := pattern.fullmatch(value):
                return self._plan_create(
                    LocalMutationOperation.CREATE_TEXT_FILE,
                    _unquote(match.group("parent")),
                    _unquote(match.group("name")),
                    content="",
                )
        for pattern in self._TRASH:
            if match := pattern.fullmatch(value):
                return self._plan_trash(_unquote(match.group("target")))
        return LocalMutationPlanningResult(matched=False)

    def _resolve(self, token: str) -> tuple[Path | None, LocalMutationPlanningResult | None]:
        resolution = self.paths._resolve_target(token)
        if resolution.clarification is not None:
            item = resolution.clarification
            return None, LocalMutationPlanningResult(
                matched=True,
                clarification=LocalMutationClarification(item.code, item.question, item.options),
            )
        return resolution.path, None

    def _plan_create(
        self,
        operation: LocalMutationOperation,
        parent_token: str,
        name: str,
        *,
        content: str | None,
    ) -> LocalMutationPlanningResult:
        if not _valid_leaf(name):
            return self._deny(
                "local_mutation.invalid_name",
                "The requested name is unsafe or ambiguous.",
            )
        parent, issue = self._resolve(parent_token)
        if issue is not None:
            return issue
        assert parent is not None
        if _symlink_in_parents(parent.absolute()):
            return self._deny(
                "local_mutation.symlink_parent_denied",
                "A parent directory is a symlink.",
            )
        try:
            canonical_parent = parent.resolve(strict=True)
            parent_info = canonical_parent.stat()
        except (OSError, RuntimeError):
            return self._deny(
                "local_mutation.parent_unavailable",
                "The destination directory is unavailable.",
            )
        if not stat.S_ISDIR(parent_info.st_mode):
            return self._deny(
                "local_mutation.parent_not_directory",
                "The destination is not a directory.",
            )
        target = canonical_parent / name
        protected = _protected(target, self.home)
        if protected:
            return self._deny(protected, "That target is protected by the mutation privacy policy.")
        if target.exists() or target.is_symlink():
            return self._deny(
                "local_mutation.target_exists",
                "The target already exists; it will not be overwritten.",
            )
        if not os.access(canonical_parent, os.W_OK | os.X_OK, effective_ids=True):
            return self._deny(
                "local_mutation.permission_denied",
                "The current user cannot write to that directory.",
            )
        aliases = _parse_xdg_file(self.paths.xdg_config, self.home)
        encoded = content.encode("utf-8") if content is not None else b""
        plan = LocalFilesystemMutationPlan(
            plan_id=self.identifier("mutation_plan"),
            operation=operation,
            original_target=f"{parent_token}/{name}",
            target_path=str(target),
            parent_path=str(canonical_parent),
            target_category=_target_category(target, self.home, self.workspace, aliases),
            target_digest=hashlib.sha256(str(target).encode()).hexdigest(),
            parent_device=int(parent_info.st_dev),
            parent_inode=int(parent_info.st_ino),
            parent_mode=int(parent_info.st_mode),
            existing_device=None,
            existing_inode=None,
            existing_mode=None,
            content=content,
            content_digest=hashlib.sha256(encoded).hexdigest() if content is not None else None,
            content_bytes=len(encoded),
            rollback="Move the created target to Trash with a separate fresh approval.",
            risk=1,
            plan_digest="",
        )
        return LocalMutationPlanningResult(matched=True, plan=plan)

    def _plan_trash(self, token: str) -> LocalMutationPlanningResult:
        target, issue = self._resolve(token)
        if issue is not None:
            return issue
        assert target is not None
        requested = target.absolute()
        if _symlink_in_parents(requested):
            return self._deny(
                "local_mutation.symlink_parent_denied",
                "A parent directory is a symlink.",
            )
        try:
            requested_info = requested.lstat()
            canonical = requested.resolve(strict=True)
            info = canonical.stat()
            parent = canonical.parent.resolve(strict=True)
            parent_info = parent.stat()
        except (OSError, RuntimeError):
            return self._deny(
                "local_mutation.target_unavailable",
                "The requested target is unavailable.",
            )
        if stat.S_ISLNK(requested_info.st_mode) or str(requested) != str(canonical):
            return self._deny(
                "local_mutation.symlink_target_denied",
                "Symlink deletion is outside this bounded workflow.",
            )
        protected = _protected(canonical, self.home)
        if protected:
            return self._deny(protected, "That target is protected by the mutation privacy policy.")
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
            return self._deny(
                "local_mutation.special_file_denied",
                "Only regular files and directories can be moved to Trash.",
            )
        if info.st_uid != os.geteuid() or not os.access(
            parent, os.W_OK | os.X_OK, effective_ids=True
        ):
            return self._deny(
                "local_mutation.permission_denied",
                "Only a current-user-owned writable target can be moved to Trash.",
            )
        trash_files = self.home / ".local/share/Trash/files"
        trash_info = self.home / ".local/share/Trash/info"
        try:
            files_info = trash_files.stat()
            info_info = trash_info.stat()
        except OSError:
            return self._deny(
                "local_mutation.trash_unavailable",
                "The current user's Trash directories are unavailable.",
            )
        if (
            not stat.S_ISDIR(files_info.st_mode)
            or not stat.S_ISDIR(info_info.st_mode)
            or files_info.st_uid != os.geteuid()
            or info_info.st_uid != os.geteuid()
            or files_info.st_dev != info.st_dev
        ):
            return self._deny(
                "local_mutation.trash_unsafe",
                "The current user's Trash boundary is unsafe or on another filesystem.",
            )
        aliases = _parse_xdg_file(self.paths.xdg_config, self.home)
        plan = LocalFilesystemMutationPlan(
            plan_id=self.identifier("mutation_plan"),
            operation=LocalMutationOperation.TRASH,
            original_target=token,
            target_path=str(canonical),
            parent_path=str(parent),
            target_category=_target_category(canonical, self.home, self.workspace, aliases),
            target_digest=hashlib.sha256(str(canonical).encode()).hexdigest(),
            parent_device=int(parent_info.st_dev),
            parent_inode=int(parent_info.st_ino),
            parent_mode=int(parent_info.st_mode),
            existing_device=int(info.st_dev),
            existing_inode=int(info.st_ino),
            existing_mode=int(info.st_mode),
            content=None,
            content_digest=None,
            content_bytes=0,
            rollback="Restore the item from the current user's Trash with a separate fresh approval.",
            risk=2,
            plan_digest="",
        )
        return LocalMutationPlanningResult(matched=True, plan=plan)

    @staticmethod
    def _deny(code: str, message: str) -> LocalMutationPlanningResult:
        return LocalMutationPlanningResult(matched=True, denial_code=code, denial_message=message)


class LocalMutationReviewer:
    """Independent deterministic policy pass over a completed immutable plan."""

    def __init__(self, *, home: Path | None = None) -> None:
        self.home = (home or Path.home()).resolve()

    def review(self, plan: LocalFilesystemMutationPlan) -> MutationReview:
        target = Path(plan.target_path)
        parent = Path(plan.parent_path)
        code: str | None = None
        if plan.plan_digest != plan.expected_digest():
            code = "mutation_review.digest_mismatch"
        elif (
            not target.is_absolute()
            or target.parent != parent
            or not _valid_leaf(target.name)
            or _protected(target, self.home) is not None
            or _symlink_in_parents(parent)
        ):
            code = "mutation_review.policy_mismatch"
        else:
            try:
                parent_info = parent.stat()
                if (
                    not stat.S_ISDIR(parent_info.st_mode)
                    or parent_info.st_dev != plan.parent_device
                    or parent_info.st_ino != plan.parent_inode
                    or stat.S_IFMT(parent_info.st_mode) != stat.S_IFMT(plan.parent_mode)
                    or not os.access(parent, os.W_OK | os.X_OK, effective_ids=True)
                ):
                    code = "mutation_review.parent_mismatch"
                elif plan.operation == LocalMutationOperation.TRASH:
                    target_info = target.lstat()
                    if (
                        stat.S_ISLNK(target_info.st_mode)
                        or not (
                            stat.S_ISREG(target_info.st_mode) or stat.S_ISDIR(target_info.st_mode)
                        )
                        or target_info.st_uid != os.geteuid()
                        or target_info.st_dev != plan.existing_device
                        or target_info.st_ino != plan.existing_inode
                        or stat.S_IFMT(target_info.st_mode) != stat.S_IFMT(plan.existing_mode or 0)
                    ):
                        code = "mutation_review.target_mismatch"
                elif target.exists() or target.is_symlink():
                    code = "mutation_review.overwrite_denied"
            except OSError:
                code = "mutation_review.state_unavailable"
        if code is not None:
            return MutationReview(
                plan.plan_digest,
                "deny",
                code,
                "The proposal failed independent current-state policy review.",
                plan.rollback,
            )
        return MutationReview(
            plan.plan_digest,
            "allow_for_user_review",
            "mutation_review.ready",
            (
                f"{plan.operation.value.replace('_', ' ')}: {plan.target_path}\n"
                f"Scope: {plan.target_category}; risk={plan.risk}\n"
                f"Rollback: {plan.rollback}\n"
                "Approval is valid for this exact plan once only."
            ),
            plan.rollback,
        )


class BoundedLocalFilesystemMutationExecutor:
    """Consume one approval and execute one descriptor-bound mutation."""

    def __init__(self, *, home: Path) -> None:
        self.home = home.resolve()
        self._consumed: set[str] = set()
        self._lock = threading.Lock()

    async def execute(
        self,
        plan: LocalFilesystemMutationPlan,
        review: MutationReview,
        approval: OneUseApproval,
    ) -> LocalFilesystemMutationResult:
        return await run_blocking_once(
            self._execute_once,
            plan,
            review,
            approval,
            thread_name=f"jarvis-local-mutation-{plan.plan_id[:20]}",
            cancellation="settle",
        )

    def _execute_once(
        self,
        plan: LocalFilesystemMutationPlan,
        review: MutationReview,
        approval: OneUseApproval,
    ) -> LocalFilesystemMutationResult:
        started = time.monotonic()
        mutation_started = False
        try:
            if (
                plan.plan_digest != plan.expected_digest()
                or review.decision != "allow_for_user_review"
                or review.plan_digest != plan.plan_digest
                or approval.plan_digest != plan.plan_digest
                or approval.review_digest != review.review_digest
            ):
                raise LocalMutationError(
                    "local_mutation.binding_mismatch",
                    "The approved mutation binding is invalid.",
                )
            target = Path(plan.target_path)
            if (
                target.parent != Path(plan.parent_path)
                or not _valid_leaf(target.name)
                or _protected(target, self.home) is not None
            ):
                raise LocalMutationError(
                    "local_mutation.policy_recheck_failed",
                    "The target no longer satisfies the bounded mutation policy.",
                )
            with self._lock:
                if approval.approval_id in self._consumed:
                    raise LocalMutationError(
                        "local_mutation.approval_replayed",
                        "This one-use approval was already consumed.",
                    )
                self._consumed.add(approval.approval_id)
            parent_fd = _open_descriptor_path(Path(plan.parent_path), directory=True)
            try:
                parent_info = os.fstat(parent_fd)
                if (
                    int(parent_info.st_dev) != plan.parent_device
                    or int(parent_info.st_ino) != plan.parent_inode
                    or stat.S_IFMT(parent_info.st_mode) != stat.S_IFMT(plan.parent_mode)
                ):
                    raise LocalMutationError(
                        "local_mutation.parent_changed",
                        "The destination directory changed after approval.",
                    )
                name = target.name
                if plan.operation == LocalMutationOperation.CREATE_DIRECTORY:
                    os.mkdir(name, 0o700, dir_fd=parent_fd)
                    mutation_started = True
                    created = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                    if not stat.S_ISDIR(created.st_mode):
                        raise LocalMutationError(
                            "local_mutation.postcondition_failed",
                            "The new directory could not be verified.",
                        )
                    message = f"Created directory: {plan.target_path}"
                    rollback_available = True
                elif plan.operation == LocalMutationOperation.CREATE_TEXT_FILE:
                    descriptor = os.open(
                        name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                        0o600,
                        dir_fd=parent_fd,
                    )
                    mutation_started = True
                    try:
                        data = (plan.content or "").encode("utf-8")
                        if hashlib.sha256(data).hexdigest() != plan.content_digest:
                            raise LocalMutationError(
                                "local_mutation.content_changed",
                                "The text-file content binding changed.",
                            )
                        view = memoryview(data)
                        while view:
                            written = os.write(descriptor, view)
                            if written <= 0:
                                raise OSError("short text-file write")
                            view = view[written:]
                        os.fsync(descriptor)
                        created = os.fstat(descriptor)
                        if not stat.S_ISREG(created.st_mode) or created.st_size != len(data):
                            raise LocalMutationError(
                                "local_mutation.postcondition_failed",
                                "The new text file could not be verified.",
                            )
                    finally:
                        os.close(descriptor)
                    message = f"Created text file: {plan.target_path}"
                    rollback_available = True
                else:
                    current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                    if (
                        int(current.st_dev) != plan.existing_device
                        or int(current.st_ino) != plan.existing_inode
                        or stat.S_IFMT(current.st_mode) != stat.S_IFMT(plan.existing_mode or 0)
                    ):
                        raise LocalMutationError(
                            "local_mutation.target_changed",
                            "The target changed after approval.",
                        )
                    destination = self._trash(parent_fd, name, Path(plan.target_path), plan)
                    mutation_started = True
                    message = f"Moved to Trash: {plan.target_path}\nTrash name: {destination}"
                    rollback_available = True
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
            safe, changed = sanitize_and_redact_terminal_text(message, DISPLAY_LIMIT)
            return LocalFilesystemMutationResult(
                plan.operation,
                "completed",
                safe,
                plan.plan_digest,
                plan.target_digest,
                plan.target_category,
                max(0, int((time.monotonic() - started) * 1000)),
                changed,
                rollback_available,
            )
        except (LocalMutationError, OSError, UnicodeError) as exc:
            code = (
                exc.code
                if isinstance(exc, LocalMutationError)
                else (
                    "local_mutation.permission_denied"
                    if isinstance(exc, PermissionError)
                    else "local_mutation.io_failure"
                )
            )
            message = (
                exc.user_message
                if isinstance(exc, LocalMutationError)
                else ("The approved filesystem mutation failed safely; it was not retried.")
            )
            if mutation_started and code != "local_mutation.outcome_indeterminate":
                code = "local_mutation.outcome_indeterminate"
                message = (
                    "The filesystem operation started but final verification failed. "
                    "Its outcome is indeterminate; inspect the exact target before making a new plan."
                )
            safe, changed = sanitize_and_redact_terminal_text(message, DISPLAY_LIMIT)
            return LocalFilesystemMutationResult(
                plan.operation,
                "failed",
                safe,
                plan.plan_digest,
                plan.target_digest,
                plan.target_category,
                max(0, int((time.monotonic() - started) * 1000)),
                changed,
                mutation_started or code == "local_mutation.outcome_indeterminate",
                code,
            )

    def _trash(
        self,
        parent_fd: int,
        name: str,
        source: Path,
        plan: LocalFilesystemMutationPlan,
    ) -> str:
        trash_files = self.home / ".local/share/Trash/files"
        trash_info = self.home / ".local/share/Trash/info"
        suffix = os.urandom(16).hex()
        destination_name = f"{source.name}.{suffix}"
        info_name = f"{destination_name}.trashinfo"
        info_directory_fd = _open_descriptor_path(trash_info, directory=True)
        info_created = False
        try:
            info_directory = os.fstat(info_directory_fd)
            if not stat.S_ISDIR(info_directory.st_mode) or info_directory.st_uid != os.geteuid():
                raise LocalMutationError(
                    "local_mutation.trash_changed",
                    "The Trash metadata directory changed after approval.",
                )
            info_fd = os.open(
                info_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                0o600,
                dir_fd=info_directory_fd,
            )
            info_created = True
            try:
                payload = (
                    "[Trash Info]\n"
                    f"Path={quote(str(source))}\n"
                    f"DeletionDate={datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S')}\n"
                ).encode()
                view = memoryview(payload)
                while view:
                    written = os.write(info_fd, view)
                    if written <= 0:
                        raise OSError("short trash metadata write")
                    view = view[written:]
                os.fsync(info_fd)
            finally:
                os.close(info_fd)
            os.fsync(info_directory_fd)
            files_fd = _open_descriptor_path(trash_files, directory=True)
            renamed = False
            try:
                files_directory = os.fstat(files_fd)
                # This is the last pathname lookup before the atomic rename.
                # Bind it again to the inode/type reviewed and approved by the
                # user so a concurrent replacement cannot consume that grant.
                source_info = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if (
                    not stat.S_ISDIR(files_directory.st_mode)
                    or files_directory.st_uid != os.geteuid()
                    or files_directory.st_dev != source_info.st_dev
                    or int(source_info.st_dev) != plan.existing_device
                    or int(source_info.st_ino) != plan.existing_inode
                    or stat.S_IFMT(source_info.st_mode) != stat.S_IFMT(plan.existing_mode or 0)
                ):
                    raise LocalMutationError(
                        "local_mutation.trash_changed",
                        "The source or Trash destination changed after approval.",
                    )
                os.rename(name, destination_name, src_dir_fd=parent_fd, dst_dir_fd=files_fd)
                renamed = True
                try:
                    os.fsync(files_fd)
                except OSError as exc:
                    raise LocalMutationError(
                        "local_mutation.outcome_indeterminate",
                        "The item was moved to Trash, but durability verification failed; no retry was attempted.",
                    ) from exc
            except BaseException:
                if info_created and not renamed:
                    try:
                        os.unlink(info_name, dir_fd=info_directory_fd)
                        os.fsync(info_directory_fd)
                    except OSError:
                        pass
                raise
            finally:
                os.close(files_fd)
        finally:
            os.close(info_directory_fd)
        return destination_name
