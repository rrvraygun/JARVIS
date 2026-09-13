"""Deterministic planning and bounded execution for exact local filesystem reads."""

from __future__ import annotations

import asyncio
import fnmatch
import hashlib
import os
import pwd
import re
import stat
import threading
import time
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .async_boundary import run_blocking_once
from .models import LocalFilesystemReadPlan, LocalReadOperation, LocalSearchMode
from .terminal_safety import sanitize_and_redact_terminal_text

LIST_LIMIT = 500
LIST_DIRECTORY_ENTRY_LIMIT = 5_000
READ_LIMIT = 64 * 1024
DISPLAY_LIMIT = 16_000
SEARCH_DEPTH_LIMIT = 8
SEARCH_FILE_LIMIT = 2_000
SEARCH_FILE_BYTE_LIMIT = 1024 * 1024
SEARCH_MATCH_LIMIT = 200
SEARCH_DIRECTORY_ENTRY_LIMIT = 20_000
SEARCH_DEADLINE_SECONDS = 2.0


def _current_user_home() -> Path:
    return Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()


_SHELL_SYNTAX = re.compile(r"[\n\r;&|<>`]|\$\(")
_HIDDEN = re.compile(
    r"\b(?:including hidden(?: files| entries)?|include hidden(?: files| entries)?|"
    r"including dotfiles|include dotfiles|incluyendo archivos ocultos|"
    r"incluir archivos ocultos|con archivos ocultos)\b",
    re.IGNORECASE,
)
_RECURSIVE = re.compile(
    r"\b(?:recursively|recursive|including subdirectories|include subdirectories|"
    r"recursivamente|recursivo|incluyendo subdirectorios|incluir subdirectorios)\b",
    re.IGNORECASE,
)
_NON_RECURSIVE = re.compile(
    r"\b(?:non[- ]recursively|only this directory|this directory only|"
    r"sin recursi[oó]n|solo este directorio|solamente este directorio)\b",
    re.IGNORECASE,
)

_FILENAME_SEARCH = (
    re.compile(
        r"^(?:please\s+)?(?:find|search\s+for)\s+(?:the\s+)?files?\s+named\s+"
        r"(?P<query>\"[^\"]+\"|'[^']+'|\S+)\s+(?:in|under|inside)\s+(?P<target>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:por\s+favor\s+)?(?:busca|buscar|encuentra|encontrar)\s+"
        r"(?:los\s+)?(?:archivos|ficheros)\s+(?:llamados?|con\s+nombre)\s+"
        r"(?P<query>\"[^\"]+\"|'[^']+'|\S+)\s+(?:en|dentro\s+de)\s+(?P<target>.+)$",
        re.IGNORECASE,
    ),
)
_CONTENT_SEARCH = (
    re.compile(
        r"^(?:please\s+)?(?:search|look)\s+(?:the\s+)?(?:contents?|text)\s+for\s+"
        r"(?P<query>\"[^\"]+\"|'[^']+'|\S+)\s+(?:in|under|inside)\s+(?P<target>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?search\s+for\s+(?P<query>\"[^\"]+\"|'[^']+'|\S+)\s+"
        r"(?:in|under|inside)\s+(?P<target>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:por\s+favor\s+)?(?:busca|buscar)\s+(?:el\s+)?(?:contenido|texto)\s+"
        r"(?P<query>\"[^\"]+\"|'[^']+'|\S+)\s+(?:en|dentro\s+de)\s+(?P<target>.+)$",
        re.IGNORECASE,
    ),
)
_AMBIGUOUS_SEARCH = (
    re.compile(
        r"^(?:please\s+)?(?:search|find)\s+(?P<query>\"[^\"]+\"|'[^']+'|\S+)\s+"
        r"(?:in|under|inside)\s+(?P<target>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:por\s+favor\s+)?(?:busca|buscar|encuentra|encontrar)\s+"
        r"(?P<query>\"[^\"]+\"|'[^']+'|\S+)\s+(?:en|dentro\s+de)\s+(?P<target>.+)$",
        re.IGNORECASE,
    ),
)
_READ = (
    re.compile(
        r"^(?:please\s+)?(?:read|open)\s+(?:the\s+)?(?:file\s+)?(?P<target>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:por\s+favor\s+)?(?:lee|leer|abre|abrir)\s+(?:el\s+)?(?:archivo\s+)?(?P<target>.+)$",
        re.IGNORECASE,
    ),
)
_LIST = (
    re.compile(
        r"^(?:please\s+)?(?:list|show)\s+(?:me\s+)?(?:the\s+)?"
        r"(?:files|entries)(?:\s+(?:inside|in|under|of))?\s*(?P<target>.*)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:por\s+favor\s+)?(?:lista|listar|muestra|mostrar)\s+(?:los\s+|las\s+)?"
        r"(?:archivos|ficheros|entradas)(?:\s+(?:dentro\s+de|en|de))?\s*(?P<target>.*)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:please\s+)?(?:list|show)\s+(?!(?:the\s+)?contents?\b)(?P<target>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:por\s+favor\s+)?(?:lista|listar|muestra|mostrar)\s+"
        r"(?!(?:el\s+)?contenido\b)(?P<target>.+)$",
        re.IGNORECASE,
    ),
)
_CONTENTS = (
    re.compile(
        r"^(?:please\s+)?(?:show|list)\s+(?:me\s+)?(?:the\s+)?contents?\s+"
        r"(?:of|in|inside)\s+(?P<target>.+)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:por\s+favor\s+)?(?:muestra|mostrar|lista|listar)\s+(?:el\s+)?contenido\s+"
        r"(?:de|en)\s+(?P<target>.+)$",
        re.IGNORECASE,
    ),
)

_PROTECTED_PARTS = frozenset(
    {
        ".ssh",
        ".gnupg",
        ".aws",
        ".azure",
        ".kube",
        ".docker",
        ".password-store",
        "password-store",
        "keyrings",
        "keyring",
        ".credentials",
        "credentials",
        ".secrets",
        "secrets",
        "google-chrome",
        "chromium",
        "chrome",
        ".mozilla",
        "firefox",
        "brave-browser",
        "vivaldi",
        "opera",
        "keepass",
        "1password",
        "gcloud",
    }
)
_SENSITIVE_NAME = re.compile(
    r"(?i)^(?:\.env(?:\..*)?|credentials?(?:\..*)?|secrets?(?:\..*)?|"
    r"id_(?:rsa|dsa|ecdsa|ed25519)(?:\..*)?|shadow|gshadow|passwd|"
    r"\.netrc|\.npmrc|\.pypirc|\.git-credentials|krb5\.keytab|.*\.keytab|"
    r"login data|cookies?(?:\.sqlite)?|key[34]\.db|signons\.sqlite|"
    r"auth(?:entication)?(?:\.db)?|tokens?(?:\.json|\.db)?|.*\.(?:key|pem|p12|pfx))$"
)
_SENSITIVE_LABEL = re.compile(
    r"(?:^|[._+\-\s])(?:password|passwd|passphrase|credentials?|secrets?|tokens?|"
    r"api[._+\-\s]?keys?|private[._+\-\s]?keys?|contrasenas?|credenciales?|"
    r"secretos?|claves?[._+\-\s]?privadas?|llaves?[._+\-\s]?privadas?)"
    r"(?:$|[._+\-\s])"
)


def _is_sensitive_filename(name: str) -> bool:
    normalized = unicodedata.normalize("NFKC", name).casefold()
    folded = "".join(
        character
        for character in unicodedata.normalize("NFKD", normalized)
        if not unicodedata.combining(character)
    )
    if _SENSITIVE_NAME.fullmatch(normalized) or _SENSITIVE_LABEL.search(folded):
        return True
    # Locale-compatible names are sometimes concatenated with a purpose label
    # (for example, "contraseñaDrivers..."). Treat that prefix conservatively.
    return folded.startswith(("contrasena", "credencial", "claveprivada", "llaveprivada"))


class LocalFilesystemError(RuntimeError):
    def __init__(self, code: str, user_message: str) -> None:
        super().__init__(code)
        self.code = code
        self.user_message = user_message


@dataclass(frozen=True)
class LocalReadClarification:
    code: str
    question: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class LocalReadPlanningResult:
    matched: bool
    plan: LocalFilesystemReadPlan | None = None
    clarification: LocalReadClarification | None = None
    denial_code: str | None = None
    denial_message: str | None = None


@dataclass(frozen=True)
class LocalFilesystemReadResult:
    operation: LocalReadOperation
    status: str
    display_text: str
    plan_digest: str
    target_digest: str
    target_category: str
    result_count: int
    files_examined: int
    bytes_examined: int
    skipped_hidden: int
    skipped_sensitive: int
    skipped_unreadable: int
    truncated: bool
    deadline_reached: bool
    sanitized_or_redacted: bool
    duration_ms: int
    applied_caps: tuple[str, ...]
    error_code: str | None = None

    def audit_metadata(self) -> dict[str, object]:
        return {
            "operation": self.operation.value,
            "status": self.status,
            "plan_digest": self.plan_digest,
            "target_digest": self.target_digest,
            "target_category": self.target_category,
            "result_count": self.result_count,
            "files_examined": self.files_examined,
            "bytes_examined": self.bytes_examined,
            "skipped_hidden": self.skipped_hidden,
            "skipped_sensitive": self.skipped_sensitive,
            "skipped_unreadable": self.skipped_unreadable,
            "truncated": self.truncated,
            "deadline_reached": self.deadline_reached,
            "sanitized_or_redacted": self.sanitized_or_redacted,
            "duration_ms": self.duration_ms,
            "applied_caps": list(self.applied_caps),
            "error_code": self.error_code,
        }


@dataclass(frozen=True)
class _ParsedRequest:
    operation: LocalReadOperation
    target: str
    search_mode: LocalSearchMode | None
    query: str | None
    recursive: bool
    include_hidden: bool
    auto_contents: bool = False


@dataclass(frozen=True)
class _TargetResolution:
    path: Path | None = None
    clarification: LocalReadClarification | None = None


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def _clean_target(value: str, workspace: Path) -> str:
    raw = value.strip()
    quoted_literal = len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}
    target = _unquote(raw)
    if not quoted_literal:
        target = re.sub(
            r"^(?:the\s+)?(?:folder|directory|carpeta|directorio)\s+",
            "",
            target,
            flags=re.IGNORECASE,
        )
    if target.endswith(".") and not (workspace / target).exists() and not Path(target).exists():
        target = target[:-1].rstrip()
    return target


def _first_match(patterns: Iterable[re.Pattern[str]], text: str) -> re.Match[str] | None:
    for pattern in patterns:
        if match := pattern.fullmatch(text):
            return match
    return None


def _parse_xdg_file(path: Path, home: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    try:
        lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    except (OSError, UnicodeError):
        return result
    rule = re.compile(r'^XDG_(DESKTOP|DOCUMENTS|DOWNLOAD)_DIR\s*=\s*"((?:\\.|[^"\\])*)"\s*$')
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = rule.fullmatch(stripped)
        if not match:
            continue
        key, encoded = match.groups()
        if "`" in encoded or "$(" in encoded:
            continue
        value = encoded.replace(r"\"", '"').replace(r"\\", "\\")
        if value == "$HOME":
            candidate = home
        elif value.startswith("$HOME/"):
            candidate = home / value[len("$HOME/") :]
        elif value.startswith("${HOME}/"):
            candidate = home / value[len("${HOME}/") :]
        elif value.startswith("/") and "$" not in value:
            candidate = Path(value)
        else:
            continue
        result[key.casefold()] = candidate
    return result


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _has_hidden_component(path: Path, root: Path | None = None) -> bool:
    try:
        parts = path.relative_to(root).parts if root is not None else path.parts
    except ValueError:
        parts = path.parts
    return any(part.startswith(".") and part not in {".", ".."} for part in parts)


def _sensitive_path(
    path: Path, *, operation: LocalReadOperation, recursive: bool, home: Path
) -> str | None:
    canonical = path.absolute()
    protected_roots = (Path("/dev"), Path("/proc"), Path("/sys"))
    if any(canonical == root or _is_relative_to(canonical, root) for root in protected_roots):
        return "local_read.protected_special_tree"
    lowered = tuple(part.casefold() for part in canonical.parts)
    if any(part in _PROTECTED_PARTS for part in lowered):
        return "local_read.sensitive_store"
    if any(_is_sensitive_filename(part) for part in canonical.parts):
        return "local_read.sensitive_filename"
    protected_system_stores = (
        Path("/etc/ssh"),
        Path("/etc/ssl/private"),
        Path("/etc/sudoers.d"),
        Path("/etc/polkit-1"),
        Path("/etc/NetworkManager/system-connections"),
        Path("/etc/openvpn"),
        Path("/etc/wireguard"),
        Path("/run/credentials"),
        Path("/run/secrets"),
        Path("/var/lib/AccountsService"),
        Path("/var/lib/NetworkManager"),
        Path("/var/lib/bluetooth"),
        Path("/var/lib/sss"),
    )
    if any(
        canonical == root or _is_relative_to(canonical, root) for root in protected_system_stores
    ):
        return "local_read.sensitive_system_store"
    broad_system_roots = {
        Path("/"),
        Path("/boot"),
        Path("/etc"),
        Path("/run"),
        Path("/usr"),
        Path("/var"),
    }
    if operation == LocalReadOperation.SEARCH and canonical in broad_system_roots:
        return "local_read.broad_system_search"
    config_root = home / ".config"
    if (
        operation in {LocalReadOperation.LIST, LocalReadOperation.SEARCH}
        and canonical == config_root
    ):
        return "local_read.broad_configuration_store"
    if recursive and canonical == home:
        return "local_read.broad_home_traversal"
    return None


def _target_category(path: Path, home: Path, workspace: Path, aliases: dict[str, Path]) -> str:
    if path == workspace or _is_relative_to(path, workspace):
        return "workspace"
    for key, value in aliases.items():
        try:
            canonical = value.resolve(strict=False)
        except OSError:
            continue
        if path == canonical or _is_relative_to(path, canonical):
            return {
                "desktop": "desktop",
                "documents": "documents",
                "download": "downloads",
            }.get(key, "user_directory")
    for category, names in (
        ("desktop", ("Desktop", "Escritorio")),
        ("documents", ("Documents", "Documentos")),
        ("downloads", ("Downloads", "Descargas")),
    ):
        if any(path == home / name or _is_relative_to(path, home / name) for name in names):
            return category
    if path == home:
        return "home"
    if _is_relative_to(path, home):
        return "user_path"
    if _is_relative_to(path, Path("/tmp")):
        return "temporary"
    return "system_or_external_path"


def _symlink_in_parents(path: Path) -> bool:
    current = Path(path.anchor)
    parts = path.parts[1:] if path.is_absolute() else path.parts
    for part in parts[:-1]:
        current /= part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                return True
        except OSError:
            return False
    return False


class LocalFilesystemPlanner:
    """Recognize only conservative English/Spanish local-read requests."""

    def __init__(
        self,
        workspace: Path,
        *,
        home: Path | None = None,
        xdg_config: Path | None = None,
        identifier=lambda prefix: f"{prefix}_{os.urandom(16).hex()}",
    ) -> None:
        self.workspace = workspace.resolve()
        self.home = (home or _current_user_home()).resolve()
        self.xdg_config = xdg_config or self.home / ".config/user-dirs.dirs"
        self.identifier = identifier

    def plan(self, text: str) -> LocalReadPlanningResult:
        if not isinstance(text, str) or not text.strip() or len(text) > 4_000:
            return LocalReadPlanningResult(matched=False)
        if _SHELL_SYNTAX.search(text):
            return LocalReadPlanningResult(matched=False)
        parsed = self._parse(text.strip())
        if isinstance(parsed, LocalReadClarification):
            return LocalReadPlanningResult(matched=True, clarification=parsed)
        if parsed is None:
            return LocalReadPlanningResult(matched=False)
        if parsed.query is not None and len(parsed.query) > 1_000:
            return LocalReadPlanningResult(
                matched=True,
                clarification=LocalReadClarification(
                    "local_read.query_too_long",
                    "The search text is too long for a bounded local search. What should I do?",
                    ("Provide a shorter exact query", "Cancel the search"),
                ),
            )
        if not parsed.target:
            return LocalReadPlanningResult(
                matched=True,
                clarification=LocalReadClarification(
                    "local_read.missing_target",
                    "Which exact location should I use?",
                    (
                        "Desktop/Escritorio",
                        "Current workspace",
                        "Specify another exact path",
                    ),
                ),
            )
        resolution = self._resolve_target(parsed.target)
        if resolution.clarification:
            return LocalReadPlanningResult(matched=True, clarification=resolution.clarification)
        assert resolution.path is not None
        requested = resolution.path.absolute()
        if _symlink_in_parents(requested):
            return self._deny(
                "local_read.directory_symlink_denied",
                "A directory symlink is outside the bounded local-read policy.",
            )
        try:
            requested_stat = requested.lstat()
            canonical = requested.resolve(strict=True)
            target_stat = canonical.stat()
        except FileNotFoundError:
            return LocalReadPlanningResult(
                matched=True,
                clarification=LocalReadClarification(
                    "local_read.target_missing",
                    "That target does not exist. Which exact target should I use?",
                    (
                        "Desktop/Escritorio",
                        "Current workspace",
                        "Specify another exact path",
                    ),
                ),
            )
        except (OSError, RuntimeError):
            return self._deny(
                "local_read.target_unresolvable",
                "The target could not be resolved safely.",
            )
        if stat.S_ISLNK(requested_stat.st_mode) and stat.S_ISDIR(target_stat.st_mode):
            return self._deny(
                "local_read.directory_symlink_denied",
                "Directory symlinks are not followed by the local reader.",
            )
        if not os.access(canonical, os.R_OK, effective_ids=True):
            return self._deny(
                "local_read.permission_denied",
                "The current user cannot read that target.",
            )
        operation = parsed.operation
        if parsed.auto_contents:
            operation = (
                LocalReadOperation.LIST
                if stat.S_ISDIR(target_stat.st_mode)
                else LocalReadOperation.READ
            )
        if operation == LocalReadOperation.READ and parsed.recursive:
            return LocalReadPlanningResult(
                matched=True,
                clarification=LocalReadClarification(
                    "local_read.recursion_not_applicable",
                    "A direct file read is not recursive. What should I do?",
                    ("Read one exact file", "Search a directory instead"),
                ),
            )
        if not (stat.S_ISDIR(target_stat.st_mode) or stat.S_ISREG(target_stat.st_mode)):
            return self._deny(
                "local_read.special_file_denied",
                "Only directories and regular text files are supported.",
            )
        if operation == LocalReadOperation.LIST and not stat.S_ISDIR(target_stat.st_mode):
            return LocalReadPlanningResult(
                matched=True,
                clarification=LocalReadClarification(
                    "local_read.expected_directory",
                    "That target is a file. What should I do?",
                    ("Read the file", "Choose a directory"),
                ),
            )
        if operation == LocalReadOperation.READ and not stat.S_ISREG(target_stat.st_mode):
            return LocalReadPlanningResult(
                matched=True,
                clarification=LocalReadClarification(
                    "local_read.expected_file",
                    "That target is not a regular file. What should I do?",
                    ("Choose a regular text file", "List a directory instead"),
                ),
            )
        if operation == LocalReadOperation.SEARCH and not stat.S_ISDIR(target_stat.st_mode):
            return LocalReadPlanningResult(
                matched=True,
                clarification=LocalReadClarification(
                    "local_read.search_root_not_directory",
                    "Search needs an exact directory. Which scope should I use?",
                    ("Use the containing directory", "Specify another directory"),
                ),
            )
        if operation not in {
            LocalReadOperation.LIST,
            LocalReadOperation.READ,
            LocalReadOperation.SEARCH,
        }:
            return LocalReadPlanningResult(matched=False)
        sensitive = _sensitive_path(
            canonical, operation=operation, recursive=parsed.recursive, home=self.home
        )
        if sensitive:
            return self._deny(
                sensitive, "That target is protected by the local-read privacy policy."
            )
        aliases = _parse_xdg_file(self.xdg_config, self.home)
        category = _target_category(canonical, self.home, self.workspace, aliases)
        target_digest = hashlib.sha256(str(canonical).encode()).hexdigest()
        query_digest = hashlib.sha256(parsed.query.encode()).hexdigest() if parsed.query else None
        plan = LocalFilesystemReadPlan(
            plan_id=self.identifier("local_plan"),
            operation=operation,
            original_target=parsed.target,
            requested_path=str(requested),
            canonical_path=str(canonical),
            target_category=category,
            target_digest=target_digest,
            target_device=int(target_stat.st_dev),
            target_inode=int(target_stat.st_ino),
            target_mode=int(target_stat.st_mode),
            search_mode=parsed.search_mode,
            query=parsed.query,
            query_digest=query_digest,
            recursive=parsed.recursive,
            max_depth=SEARCH_DEPTH_LIMIT if parsed.recursive else 0,
            item_limit=LIST_LIMIT,
            file_limit=SEARCH_FILE_LIMIT,
            byte_limit=READ_LIMIT,
            per_file_byte_limit=SEARCH_FILE_BYTE_LIMIT,
            match_limit=SEARCH_MATCH_LIMIT,
            deadline_seconds=SEARCH_DEADLINE_SECONDS,
            include_hidden=parsed.include_hidden,
            plan_digest="",
        )
        return LocalReadPlanningResult(matched=True, plan=plan)

    def _deny(self, code: str, message: str) -> LocalReadPlanningResult:
        return LocalReadPlanningResult(matched=True, denial_code=code, denial_message=message)

    def _parse(self, text: str) -> _ParsedRequest | LocalReadClarification | None:
        bare = text.strip().rstrip(".").casefold()
        bare = re.sub(r"^(?:please|por favor)\s+", "", bare)
        if bare in {
            "list",
            "show",
            "list files",
            "show files",
            "listar",
            "lista",
            "mostrar",
            "muestra",
            "listar archivos",
            "lista archivos",
        }:
            return LocalReadClarification(
                "local_read.missing_target",
                "Which exact location should I list?",
                (
                    "Desktop/Escritorio",
                    "Current workspace",
                    "Specify another exact path",
                ),
            )
        if bare in {
            "read",
            "open",
            "read file",
            "open file",
            "leer",
            "lee",
            "abrir",
            "abre",
            "leer archivo",
            "lee el archivo",
        }:
            return LocalReadClarification(
                "local_read.missing_target",
                "Which exact text file should I read?",
                (
                    "Specify a workspace-relative file",
                    "Specify an absolute file path",
                    "Cancel",
                ),
            )
        if bare in {
            "search",
            "find",
            "search files",
            "buscar",
            "busca",
            "encontrar",
            "encuentra",
        }:
            return LocalReadClarification(
                "local_read.unclear_search_mode",
                "What should I search for, and in which exact directory?",
                (
                    "Provide a filename pattern and directory",
                    "Provide text and directory",
                    "Cancel",
                ),
            )
        include_hidden = bool(_HIDDEN.search(text))
        recursive = bool(_RECURSIVE.search(text))
        non_recursive = bool(_NON_RECURSIVE.search(text))
        if recursive and non_recursive:
            return LocalReadClarification(
                "local_read.conflicting_recursion",
                "Should this read include subdirectories?",
                ("Only this directory", "Include subdirectories (depth 8)"),
            )
        normalized = _HIDDEN.sub(" ", text)
        normalized = _RECURSIVE.sub(" ", normalized)
        normalized = _NON_RECURSIVE.sub(" ", normalized)
        normalized = " ".join(normalized.split())
        for mode, patterns in (
            (LocalSearchMode.FILENAME, _FILENAME_SEARCH),
            (LocalSearchMode.CONTENT, _CONTENT_SEARCH),
        ):
            if match := _first_match(patterns, normalized):
                if not recursive and not non_recursive:
                    return LocalReadClarification(
                        "local_read.unclear_recursion",
                        "Should the search include subdirectories?",
                        ("Only this directory", "Include subdirectories (depth 8)"),
                    )
                return _ParsedRequest(
                    LocalReadOperation.SEARCH,
                    _clean_target(match.group("target"), self.workspace),
                    mode,
                    _unquote(match.group("query")),
                    recursive,
                    include_hidden,
                )
        if match := _first_match(_AMBIGUOUS_SEARCH, normalized):
            return LocalReadClarification(
                "local_read.unclear_search_mode",
                "Should I search file names or text inside files?",
                ("Search file names", "Search text inside files"),
            )
        if match := _first_match(_READ, normalized):
            if recursive or non_recursive:
                return LocalReadClarification(
                    "local_read.recursion_not_applicable",
                    "A direct file read is not recursive. What should I do?",
                    ("Read one exact file", "Search a directory instead"),
                )
            return _ParsedRequest(
                LocalReadOperation.READ,
                _clean_target(match.group("target"), self.workspace),
                None,
                None,
                False,
                include_hidden,
            )
        if match := _first_match(_LIST, normalized):
            return _ParsedRequest(
                LocalReadOperation.LIST,
                _clean_target(match.group("target"), self.workspace),
                None,
                None,
                recursive,
                include_hidden,
            )
        if match := _first_match(_CONTENTS, normalized):
            return _ParsedRequest(
                LocalReadOperation.READ,
                _clean_target(match.group("target"), self.workspace),
                None,
                None,
                recursive,
                include_hidden,
                auto_contents=True,
            )
        return None

    def _resolve_target(self, target: str) -> _TargetResolution:
        raw = target.strip()
        raw = re.sub(r"^(?:my|mi)\s+", "", raw, flags=re.IGNORECASE)
        raw = re.sub(r"\s+(?:folder|directory|carpeta|directorio)$", "", raw, flags=re.IGNORECASE)
        alias = raw.casefold().strip()
        workspace_aliases = {
            "workspace",
            "project",
            "current project",
            "current workspace",
            "proyecto",
            "espacio de trabajo",
            "repositorio",
            "repository",
            "repo",
        }
        home_aliases = {"home", "home directory", "inicio", "hogar", "~"}
        if alias in workspace_aliases:
            return _TargetResolution(path=self.workspace)
        if alias in home_aliases:
            return _TargetResolution(path=self.home)
        for prefix in sorted(workspace_aliases, key=len, reverse=True):
            if alias.startswith(prefix + "/"):
                return _TargetResolution(path=self.workspace / raw[len(prefix) + 1 :])
        for prefix in sorted(home_aliases, key=len, reverse=True):
            if alias.startswith(prefix + "/"):
                return _TargetResolution(path=self.home / raw[len(prefix) + 1 :])
        groups = {
            "desktop": ({"desktop", "escritorio"}, ("Desktop", "Escritorio")),
            "documents": ({"documents", "documentos"}, ("Documents", "Documentos")),
            "download": (
                {"downloads", "download", "descargas", "descarga"},
                ("Downloads", "Descargas"),
            ),
        }
        configured = _parse_xdg_file(self.xdg_config, self.home)
        for key, (names, fallbacks) in groups.items():
            selected_alias = next(
                (
                    name
                    for name in sorted(names, key=len, reverse=True)
                    if alias == name or alias.startswith(name + "/")
                ),
                None,
            )
            if selected_alias is None:
                continue
            suffix = (
                raw[len(selected_alias) + 1 :] if alias.startswith(selected_alias + "/") else ""
            )
            candidate = configured.get(key)
            if candidate is not None and candidate.is_dir():
                return _TargetResolution(path=candidate / suffix)
            existing = tuple(self.home / name for name in fallbacks if (self.home / name).is_dir())
            if len(existing) == 1:
                return _TargetResolution(path=existing[0] / suffix)
            if len(existing) > 1:
                return _TargetResolution(
                    clarification=LocalReadClarification(
                        "local_read.ambiguous_xdg_fallback",
                        f"Which existing {key} directory should I use?",
                        tuple(path.name for path in existing[:3]),
                    )
                )
            return _TargetResolution(
                clarification=LocalReadClarification(
                    "local_read.missing_xdg_directory",
                    f"No configured {key} directory exists. Which target should I use?",
                    (
                        "Current workspace",
                        "Home directory",
                        "Specify another exact path",
                    ),
                )
            )
        expanded = raw
        if expanded == "~":
            return _TargetResolution(path=self.home)
        if expanded.startswith("~/"):
            return _TargetResolution(path=self.home / expanded[2:])
        path = Path(expanded)
        if path.is_absolute():
            return _TargetResolution(path=path)
        return _TargetResolution(path=self.workspace / path)


def _open_descriptor_path(path: Path, *, directory: bool) -> int:
    """Open an absolute canonical path without following any path-component symlink."""

    if not path.is_absolute():
        raise LocalFilesystemError(
            "local_read.invalid_canonical_path", "The admitted target is not absolute."
        )
    directory_flags = os.O_RDONLY | os.O_CLOEXEC | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", directory_flags)
    parts = path.parts[1:]
    if not parts:
        if directory:
            return fd
        os.close(fd)
        raise LocalFilesystemError(
            "local_read.special_file_denied",
            "The filesystem root is not a regular file.",
        )
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, directory_flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        final_flags = directory_flags if directory else os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        result = os.open(parts[-1], final_flags, dir_fd=fd)
    except BaseException:
        os.close(fd)
        raise
    os.close(fd)
    return result


def _matches_identity(info: os.stat_result, plan: LocalFilesystemReadPlan) -> bool:
    return (
        int(info.st_dev) == plan.target_device
        and int(info.st_ino) == plan.target_inode
        and stat.S_IFMT(info.st_mode) == stat.S_IFMT(plan.target_mode)
    )


def _same_object(left: os.stat_result, right: os.stat_result) -> bool:
    return (
        int(left.st_dev) == int(right.st_dev)
        and int(left.st_ino) == int(right.st_ino)
        and stat.S_IFMT(left.st_mode) == stat.S_IFMT(right.st_mode)
    )


def _same_bound_directory(info: os.stat_result, device: int, inode: int, mode: int) -> bool:
    return (
        int(info.st_dev) == device
        and int(info.st_ino) == inode
        and stat.S_IFMT(info.st_mode) == stat.S_IFMT(mode)
        and stat.S_ISDIR(info.st_mode)
    )


class BoundedLocalFilesystemExecutor:
    """Execute one admitted plan with Python filesystem APIs in a worker thread."""

    def __init__(self, *, home: Path | None = None) -> None:
        self.home = (home or _current_user_home()).resolve()

    async def execute(self, plan: LocalFilesystemReadPlan) -> LocalFilesystemReadResult:
        cancellation = threading.Event()
        try:
            return await run_blocking_once(
                self._execute_once,
                plan,
                cancellation,
                thread_name=f"jarvis-local-read-{plan.plan_id[:24]}",
            )
        except asyncio.CancelledError:
            cancellation.set()
            raise

    def _execute_once(
        self, plan: LocalFilesystemReadPlan, cancellation: threading.Event
    ) -> LocalFilesystemReadResult:
        started = time.monotonic()
        try:
            self._verify_plan(plan)
            if plan.operation == LocalReadOperation.LIST:
                value = self._list(plan, started, cancellation)
            elif plan.operation == LocalReadOperation.READ:
                value = self._read(plan, started, cancellation)
            else:
                value = self._search(plan, started, cancellation)
            return value
        except LocalFilesystemError as exc:
            duration = max(0, int((time.monotonic() - started) * 1000))
            safe, changed = sanitize_and_redact_terminal_text(exc.user_message, DISPLAY_LIMIT)
            return LocalFilesystemReadResult(
                operation=plan.operation,
                status="failed",
                display_text=safe,
                plan_digest=plan.plan_digest,
                target_digest=plan.target_digest,
                target_category=plan.target_category,
                result_count=0,
                files_examined=0,
                bytes_examined=0,
                skipped_hidden=0,
                skipped_sensitive=0,
                skipped_unreadable=0,
                truncated=False,
                deadline_reached=False,
                sanitized_or_redacted=changed,
                duration_ms=duration,
                applied_caps=self._caps(plan),
                error_code=exc.code,
            )
        except (OSError, UnicodeError) as exc:
            duration = max(0, int((time.monotonic() - started) * 1000))
            code = (
                "local_read.permission_denied"
                if isinstance(exc, PermissionError)
                else "local_read.io_failure"
            )
            return LocalFilesystemReadResult(
                operation=plan.operation,
                status="failed",
                display_text="The bounded local read failed safely; no retry was attempted.",
                plan_digest=plan.plan_digest,
                target_digest=plan.target_digest,
                target_category=plan.target_category,
                result_count=0,
                files_examined=0,
                bytes_examined=0,
                skipped_hidden=0,
                skipped_sensitive=0,
                skipped_unreadable=1,
                truncated=False,
                deadline_reached=False,
                sanitized_or_redacted=False,
                duration_ms=duration,
                applied_caps=self._caps(plan),
                error_code=code,
            )

    def _verify_plan(self, plan: LocalFilesystemReadPlan) -> None:
        if plan.plan_digest != plan.expected_digest():
            raise LocalFilesystemError(
                "local_read.plan_digest_mismatch",
                "The admitted local-read plan no longer matches its binding.",
            )
        requested = Path(plan.requested_path)
        if _symlink_in_parents(requested):
            raise LocalFilesystemError(
                "local_read.symlink_changed",
                "A directory component became a symlink after admission.",
            )
        try:
            requested_stat = requested.lstat()
            canonical = requested.resolve(strict=True)
            target_stat = canonical.stat()
        except FileNotFoundError as exc:
            raise LocalFilesystemError(
                "local_read.target_changed", "The target disappeared after admission."
            ) from exc
        if str(canonical) != plan.canonical_path:
            raise LocalFilesystemError(
                "local_read.symlink_changed",
                "The target resolves differently from the admitted path.",
            )
        if stat.S_ISLNK(requested_stat.st_mode) and stat.S_ISDIR(target_stat.st_mode):
            raise LocalFilesystemError(
                "local_read.directory_symlink_denied",
                "Directory symlinks are not followed.",
            )
        sensitive = _sensitive_path(
            canonical,
            operation=plan.operation,
            recursive=plan.recursive,
            home=self.home,
        )
        if sensitive:
            raise LocalFilesystemError(
                sensitive,
                "The target is now protected by the local-read privacy policy.",
            )
        if not _matches_identity(target_stat, plan):
            raise LocalFilesystemError(
                "local_read.target_changed",
                "The target identity changed after admission.",
            )
        if hashlib.sha256(str(canonical).encode()).hexdigest() != plan.target_digest:
            raise LocalFilesystemError(
                "local_read.target_digest_mismatch",
                "The target binding changed after admission.",
            )
        if not os.access(canonical, os.R_OK, effective_ids=True):
            raise LocalFilesystemError(
                "local_read.permission_denied",
                "The current user can no longer read the target.",
            )

    def _caps(self, plan: LocalFilesystemReadPlan) -> tuple[str, ...]:
        if plan.operation == LocalReadOperation.LIST:
            return (
                f"entries={plan.item_limit}",
                f"directory_entries_examined={LIST_DIRECTORY_ENTRY_LIMIT}",
                f"depth={plan.max_depth}",
                f"hidden={'included' if plan.include_hidden else 'excluded'}",
            )
        if plan.operation == LocalReadOperation.READ:
            return (
                f"read_bytes={plan.byte_limit}",
                f"display_characters={DISPLAY_LIMIT}",
            )
        return (
            f"depth={plan.max_depth}",
            f"files={plan.file_limit}",
            f"bytes_per_file={plan.per_file_byte_limit}",
            f"matches={plan.match_limit}",
            f"directory_entries_examined={SEARCH_DIRECTORY_ENTRY_LIMIT}",
            f"deadline_seconds={plan.deadline_seconds:g}",
            f"hidden={'included' if plan.include_hidden else 'excluded'}",
        )

    def _list(
        self,
        plan: LocalFilesystemReadPlan,
        started: float,
        cancellation: threading.Event,
    ) -> LocalFilesystemReadResult:
        root = Path(plan.canonical_path)
        entries: list[str] = []
        hidden = sensitive = unreadable = 0
        directory_entries_examined = 0
        truncated = False
        stack: list[tuple[Path, int, int, int, int]] = [
            (Path(), 0, plan.target_device, plan.target_inode, plan.target_mode)
        ]
        while (
            stack
            and len(entries) < plan.item_limit
            and directory_entries_examined < LIST_DIRECTORY_ENTRY_LIMIT
        ):
            if cancellation.is_set():
                raise LocalFilesystemError(
                    "local_read.cancelled", "The bounded local read was cancelled."
                )
            relative, depth, device, inode, mode = stack.pop()
            fd = _open_descriptor_path(root / relative, directory=True)
            try:
                if not _same_bound_directory(os.fstat(fd), device, inode, mode):
                    raise LocalFilesystemError(
                        "local_read.target_changed",
                        "A directory changed before it could be listed.",
                    )
                with os.scandir(fd) as scanned:
                    for entry in scanned:
                        directory_entries_examined += 1
                        if directory_entries_examined > LIST_DIRECTORY_ENTRY_LIMIT:
                            truncated = True
                            break
                        if cancellation.is_set():
                            raise LocalFilesystemError(
                                "local_read.cancelled",
                                "The bounded local read was cancelled.",
                            )
                        if entry.name.startswith(".") and not plan.include_hidden:
                            hidden += 1
                            continue
                        child_relative = relative / entry.name
                        child_path = root / child_relative
                        if _sensitive_path(
                            child_path,
                            operation=plan.operation,
                            recursive=False,
                            home=self.home,
                        ):
                            sensitive += 1
                            continue
                        try:
                            entry_info = entry.stat(follow_symlinks=False)
                            is_link = stat.S_ISLNK(entry_info.st_mode)
                            is_dir = stat.S_ISDIR(entry_info.st_mode)
                            is_file = stat.S_ISREG(entry_info.st_mode)
                        except OSError:
                            unreadable += 1
                            continue
                        if not (is_dir or is_file or is_link):
                            sensitive += 1
                            continue
                        suffix = "/" if is_dir else "@" if is_link else ""
                        entries.append(f"{child_relative.as_posix()}{suffix}")
                        if len(entries) >= plan.item_limit:
                            truncated = True
                            break
                        if plan.recursive and is_dir and depth < plan.max_depth:
                            stack.append(
                                (
                                    child_relative,
                                    depth + 1,
                                    int(entry_info.st_dev),
                                    int(entry_info.st_ino),
                                    int(entry_info.st_mode),
                                )
                            )
            finally:
                os.close(fd)
        header = (
            f"Directory ({plan.target_category}): {root}\n"
            f"Limits: entries={plan.item_limit}, "
            f"directory_entries_examined={LIST_DIRECTORY_ENTRY_LIMIT}, depth={plan.max_depth}, "
            f"hidden={'included' if plan.include_hidden else 'excluded'}\n"
        )
        entries.sort(key=str.casefold)
        body = "\n".join(entries) if entries else "[no visible entries]"
        if truncated:
            body += "\n[list stopped at an applied cap]"
        safe, changed = sanitize_and_redact_terminal_text(header + body, DISPLAY_LIMIT)
        duration = max(0, int((time.monotonic() - started) * 1000))
        return LocalFilesystemReadResult(
            plan.operation,
            "completed",
            safe,
            plan.plan_digest,
            plan.target_digest,
            plan.target_category,
            len(entries),
            0,
            0,
            hidden,
            sensitive,
            unreadable,
            truncated,
            False,
            changed,
            duration,
            self._caps(plan),
            None,
        )

    def _read(
        self,
        plan: LocalFilesystemReadPlan,
        started: float,
        cancellation: threading.Event,
    ) -> LocalFilesystemReadResult:
        if cancellation.is_set():
            raise LocalFilesystemError(
                "local_read.cancelled", "The bounded local read was cancelled."
            )
        path = Path(plan.canonical_path)
        fd = _open_descriptor_path(path, directory=False)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not _matches_identity(info, plan):
                raise LocalFilesystemError(
                    "local_read.target_changed",
                    "The file identity changed before it could be read.",
                )
            data = os.read(fd, plan.byte_limit + 1)
        finally:
            os.close(fd)
        truncated = len(data) > plan.byte_limit
        data = data[: plan.byte_limit]
        if b"\x00" in data:
            raise LocalFilesystemError(
                "local_read.binary_file_denied",
                "The selected file appears to be binary and was not displayed.",
            )
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LocalFilesystemError(
                "local_read.binary_file_denied",
                "The selected file is not valid UTF-8 text and was not displayed.",
            ) from exc
        header = (
            f"File ({plan.target_category}): {path}\n"
            f"Limits: read_bytes={plan.byte_limit}, display_characters={DISPLAY_LIMIT}\n"
        )
        if truncated:
            header += f"[source read truncated at {plan.byte_limit} bytes]\n"
        marker = ""
        safe, changed = sanitize_and_redact_terminal_text(header + text + marker, DISPLAY_LIMIT)
        display_truncated = len(header + text + marker) > DISPLAY_LIMIT
        duration = max(0, int((time.monotonic() - started) * 1000))
        return LocalFilesystemReadResult(
            plan.operation,
            "completed",
            safe,
            plan.plan_digest,
            plan.target_digest,
            plan.target_category,
            1,
            1,
            len(data),
            0,
            0,
            0,
            truncated or display_truncated,
            False,
            changed or display_truncated,
            duration,
            self._caps(plan),
            None,
        )

    def _search(
        self,
        plan: LocalFilesystemReadPlan,
        started: float,
        cancellation: threading.Event,
    ) -> LocalFilesystemReadResult:
        assert plan.search_mode is not None and plan.query is not None
        root = Path(plan.canonical_path)
        matches: list[str] = []
        files = bytes_examined = hidden = sensitive = unreadable = 0
        directory_entries_examined = 0
        truncated = deadline_reached = False
        stack: list[tuple[Path, int, int, int, int]] = [
            (Path(), 0, plan.target_device, plan.target_inode, plan.target_mode)
        ]
        while (
            stack
            and files < plan.file_limit
            and len(matches) < plan.match_limit
            and directory_entries_examined < SEARCH_DIRECTORY_ENTRY_LIMIT
        ):
            if cancellation.is_set():
                raise LocalFilesystemError(
                    "local_read.cancelled", "The bounded local read was cancelled."
                )
            if time.monotonic() - started >= plan.deadline_seconds:
                deadline_reached = truncated = True
                break
            relative, depth, device, inode, mode = stack.pop()
            fd = _open_descriptor_path(root / relative, directory=True)
            try:
                if not _same_bound_directory(os.fstat(fd), device, inode, mode):
                    raise LocalFilesystemError(
                        "local_read.target_changed",
                        "A search directory changed before it could be read.",
                    )
                with os.scandir(fd) as scanned:
                    for entry in scanned:
                        directory_entries_examined += 1
                        if directory_entries_examined > SEARCH_DIRECTORY_ENTRY_LIMIT:
                            truncated = True
                            break
                        if cancellation.is_set():
                            raise LocalFilesystemError(
                                "local_read.cancelled",
                                "The bounded local read was cancelled.",
                            )
                        if time.monotonic() - started >= plan.deadline_seconds:
                            deadline_reached = truncated = True
                            break
                        if entry.name.startswith(".") and not plan.include_hidden:
                            hidden += 1
                            continue
                        child_relative = relative / entry.name
                        child_path = root / child_relative
                        if _sensitive_path(
                            child_path,
                            operation=plan.operation,
                            recursive=False,
                            home=self.home,
                        ):
                            sensitive += 1
                            continue
                        try:
                            entry_info = entry.stat(follow_symlinks=False)
                            if stat.S_ISLNK(entry_info.st_mode):
                                sensitive += 1
                                continue
                            if stat.S_ISDIR(entry_info.st_mode):
                                if plan.recursive and depth < plan.max_depth:
                                    stack.append(
                                        (
                                            child_relative,
                                            depth + 1,
                                            int(entry_info.st_dev),
                                            int(entry_info.st_ino),
                                            int(entry_info.st_mode),
                                        )
                                    )
                                continue
                            if not stat.S_ISREG(entry_info.st_mode):
                                sensitive += 1
                                continue
                        except OSError:
                            unreadable += 1
                            continue
                        files += 1
                        if plan.search_mode == LocalSearchMode.FILENAME:
                            if fnmatch.fnmatchcase(entry.name.casefold(), plan.query.casefold()):
                                matches.append(child_relative.as_posix())
                        else:
                            try:
                                child_fd = os.open(
                                    entry.name,
                                    os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                                    dir_fd=fd,
                                )
                                try:
                                    info = os.fstat(child_fd)
                                    if not stat.S_ISREG(info.st_mode) or not _same_object(
                                        entry_info, info
                                    ):
                                        continue
                                    data = os.read(child_fd, plan.per_file_byte_limit + 1)
                                finally:
                                    os.close(child_fd)
                                capped = len(data) > plan.per_file_byte_limit
                                data = data[: plan.per_file_byte_limit]
                                bytes_examined += len(data)
                                if b"\x00" in data:
                                    continue
                                decoded = data.decode("utf-8")
                                for line_number, line in enumerate(decoded.splitlines(), 1):
                                    if plan.query.casefold() in line.casefold():
                                        matches.append(
                                            f"{child_relative.as_posix()}:{line_number}: {line[:240]}"
                                        )
                                        if len(matches) >= plan.match_limit:
                                            truncated = True
                                            break
                                if capped:
                                    truncated = True
                            except (OSError, UnicodeDecodeError):
                                unreadable += 1
                        if files >= plan.file_limit or len(matches) >= plan.match_limit:
                            truncated = True
                            break
            finally:
                os.close(fd)
        header = (
            f"Search ({plan.search_mode.value}, {plan.target_category}): {root}\n"
            f"Query: {plan.query}\n"
            f"Limits: depth={plan.max_depth}, files={plan.file_limit}, "
            f"bytes_per_file={plan.per_file_byte_limit}, matches={plan.match_limit}, "
            f"directory_entries_examined={SEARCH_DIRECTORY_ENTRY_LIMIT}, "
            f"deadline_seconds={plan.deadline_seconds:g}, "
            f"hidden={'included' if plan.include_hidden else 'excluded'}\n"
        )
        matches.sort(key=str.casefold)
        body = "\n".join(matches) if matches else "[no matches]"
        if truncated:
            body += "\n[search stopped at an applied cap or deadline]"
        safe, changed = sanitize_and_redact_terminal_text(header + body, DISPLAY_LIMIT)
        display_truncated = len(header + body) > DISPLAY_LIMIT
        duration = max(0, int((time.monotonic() - started) * 1000))
        return LocalFilesystemReadResult(
            plan.operation,
            "completed",
            safe,
            plan.plan_digest,
            plan.target_digest,
            plan.target_category,
            len(matches),
            files,
            bytes_examined,
            hidden,
            sensitive,
            unreadable,
            truncated or display_truncated,
            deadline_reached,
            changed or display_truncated,
            duration,
            self._caps(plan),
            None,
        )
