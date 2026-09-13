#!/usr/bin/python3 -I
"""Exact root-reviewed operations. No review record means no execution."""

from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import math
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path("/var/lib/jarvis/privileged-control")
OWNER = 0
IDENTITY = re.compile(r"[0-9a-f]{32}")
HASH = re.compile(r"[0-9a-f]{64}")
KERNEL = re.compile(r"[0-9][A-Za-z0-9_.+-]{0,127}")
ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def directory(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe_directory")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for name in path.parts[1:]:
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if info.st_uid != OWNER or info.st_mode & 0o022:
                raise ValueError("directory_not_root_controlled")
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_file(path: Path, limit: int = 512 * 1024 * 1024) -> tuple[str, bytes]:
    parent = directory(path.parent)
    try:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != OWNER
                or before.st_mode & 0o022
                or before.st_nlink != 1
                or before.st_size > limit
            ):
                raise ValueError("unsafe_root_file")
            hasher = hashlib.sha256()
            data = bytearray()
            count = 0
            while True:
                chunk = os.read(fd, min(1048576, limit + 1 - count))
                if not chunk:
                    break
                count += len(chunk)
                if count > limit:
                    raise ValueError("file_limit")
                hasher.update(chunk)
                if limit <= 65536:
                    data.extend(chunk)
            after = os.fstat(fd)
            if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ValueError("root_file_drift")
            return hasher.hexdigest(), bytes(data)
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def write_once(path: Path, record: dict[str, Any]) -> None:
    data = json.dumps(record, sort_keys=True).encode()
    if len(data) > 65536:
        raise ValueError("record_limit")
    parent = directory(path.parent)
    try:
        fd = os.open(
            path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)
    finally:
        os.close(parent)


def run(argv: list[str], timeout: int = 120, limit: int = 2 * 1024 * 1024) -> tuple[int, bytes]:
    output = bytearray()
    deadline = time.monotonic() + timeout
    with subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=ENV,
        start_new_session=True,
        umask=0o077,
    ) as child:
        assert child.stdout is not None
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        raise ValueError("command_timeout")
                    for key, _ in selector.select(0.1):
                        chunk = os.read(key.fd, min(65536, limit + 1 - len(output)))
                        if not chunk:
                            selector.unregister(key.fileobj)
                        output.extend(chunk)
                        if len(output) > limit:
                            raise ValueError("command_output_limit")
            code = child.wait(timeout=max(0.001, deadline - time.monotonic()))
        except BaseException:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
            raise
    return code, bytes(output)


def validate(request: Any, kind: str) -> None:
    common = {"id", "pre_state_digest"}
    if (
        not isinstance(request, dict)
        or not IDENTITY.fullmatch(str(request.get("id", "")))
        or not HASH.fullmatch(str(request.get("pre_state_digest", "")))
    ):
        raise ValueError("request_identity_invalid")
    if kind == "boot":
        extra = {"source_operation"} if request.get("operation") == "install_initramfs" else set()
        if (
            set(request) != common | {"operation", "kernel", "entry"} | extra
            or request["operation"]
            not in {"select_kernel", "repair_initramfs", "install_initramfs"}
            or not KERNEL.fullmatch(str(request["kernel"]))
        ):
            raise ValueError("boot_request_invalid")
        if extra and not IDENTITY.fullmatch(str(request["source_operation"])):
            raise ValueError("staged_operation_invalid")
        if not re.fullmatch(r"[A-Za-z0-9_.+-]{1,200}", str(request["entry"])):
            raise ValueError("boot_entry_invalid")
    elif kind == "update":
        if (
            set(request) != common | {"transaction_id", "transaction_digest"}
            or not IDENTITY.fullmatch(str(request["transaction_id"]))
            or not HASH.fullmatch(str(request["transaction_digest"]))
        ):
            raise ValueError("update_request_invalid")
    else:
        raise ValueError("unsupported_helper")


def review(request: dict[str, Any], kind: str, uid: int) -> dict[str, Any]:
    _, data = read_file(ROOT / "approvals" / str(uid) / (request["id"] + ".json"), 65536)
    value = json.loads(data)
    if not isinstance(value, dict) or not isinstance(value.get("recovery"), dict):
        raise ValueError("root_review_invalid")
    now = time.time()
    expiry = value.get("expires_at")
    recovery = value.get("recovery", {})
    verified_at = recovery.get("verified_at")
    if (
        value.get("kind") != kind
        or value.get("request_digest") != digest(request)
        or not isinstance(expiry, (int, float))
        or not math.isfinite(expiry)
        or not now < expiry <= now + 600
        or recovery.get("level") != "R2"
        or not HASH.fullmatch(str(recovery.get("digest", "")))
        or not isinstance(verified_at, (int, float))
        or not math.isfinite(verified_at)
        or not 0 <= now - verified_at <= 1800
        or recovery.get("target_pre_state_digest") != request["pre_state_digest"]
        or value.get("known_good_boot_verified") is not True
    ):
        raise ValueError("fresh_independent_root_review_required")
    # This is an administrator-owned, exact expiring attestation, never two
    # equal values supplied by the model. Installation does not create it.
    return value


def boot_state(request: dict[str, Any]) -> dict[str, str]:
    kernel = request["kernel"]
    paths = [
        Path("/boot") / ("vmlinuz-" + kernel),
        Path("/boot") / ("initramfs-" + kernel + ".img"),
        Path("/boot/loader/entries") / (request["entry"] + ".conf"),
        Path("/boot/grub2/grubenv"),
    ]
    state = {str(path): read_file(path)[0] for path in paths}
    _, entry = read_file(paths[2], 65536)
    lines = entry.decode().splitlines()
    linux = [line.split(maxsplit=1)[1] for line in lines if line.startswith("linux ")]
    initrd = [line.split(maxsplit=1)[1] for line in lines if line.startswith("initrd ")]
    if (
        ("version " + kernel) not in lines
        or linux != ["/vmlinuz-" + kernel]
        or initrd != ["/initramfs-" + kernel + ".img"]
    ):
        raise ValueError("boot_entry_kernel_mismatch")
    return state


def rpm_state() -> str:
    return digest(sorted(rpm_packages()))


def normalize_nevra(value: str) -> str:
    if not isinstance(value, str) or len(value) > 256:
        raise ValueError("nevra_invalid")
    parts = value.rsplit("-", 2)
    if len(parts) != 3 or "." not in parts[2]:
        raise ValueError("nevra_invalid")
    name, version, release_arch = parts
    epoch, version = version.split(":", 1) if ":" in version else ("0", version)
    release, arch = release_arch.rsplit(".", 1)
    if (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.+-]*", name)
        or not re.fullmatch(r"[0-9]+", epoch)
        or not all(re.fullmatch(r"[A-Za-z0-9_.+~^]+", token) for token in (version, release, arch))
    ):
        raise ValueError("nevra_invalid")
    return f"{name}-{int(epoch)}:{version}-{release}.{arch}"


def rpm_packages() -> set[str]:
    code, output = run(
        ["/usr/bin/rpm", "-qa", "--qf", "%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}\\n"]
    )
    if code:
        raise ValueError("rpm_state_unavailable")
    rows = [normalize_nevra(row) for row in output.decode().splitlines()]
    if not rows or len(set(rows)) != len(rows):
        raise ValueError("rpm_state_invalid_or_duplicate")
    return set(rows)


def load_transaction(path: Path) -> dict[str, Any]:
    """Bind a root-prepared DNF5 --store tree, including every local package."""
    files = {}
    headers = {}
    count = 0
    total = 0
    pending = [path]
    while pending:
        current = pending.pop()
        fd = directory(current)
        try:
            with os.scandir(fd) as entries:
                for entry in entries:
                    count += 1
                    if count > 2000:
                        raise ValueError("stored_transaction_limit")
                    child = current / entry.name
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(info.st_mode):
                        if len(child.relative_to(path).parts) > 8:
                            raise ValueError("stored_transaction_depth")
                        pending.append(child)
                    else:
                        total += info.st_size
                        if total > 2 * 1024 * 1024 * 1024:
                            raise ValueError("stored_transaction_byte_limit")
                        files[str(child.relative_to(path))] = read_file(child)[0]
                        if child.suffix == ".rpm":
                            code, signature = run(["/usr/bin/rpmkeys", "--checksig", str(child)])
                            if code or b"signatures OK" not in signature:
                                raise ValueError("rpm_signature_unverified")
                            code, header = run(
                                [
                                    "/usr/bin/rpm",
                                    "-qp",
                                    "--qf",
                                    "%{NAME}-%{EPOCHNUM}:%{VERSION}-%{RELEASE}.%{ARCH}",
                                    str(child),
                                ]
                            )
                            if code:
                                raise ValueError("rpm_header_unavailable")
                            headers[str(child.relative_to(path))] = normalize_nevra(
                                header.decode().strip()
                            )
        finally:
            os.close(fd)
    if "transaction.json" not in files:
        raise ValueError("stored_transaction_missing")
    _, body = read_file(path / "transaction.json", 65536)
    if hashlib.sha256(body).hexdigest() != files["transaction.json"]:
        raise ValueError("stored_transaction_changed_during_read")
    spec = json.loads(body)
    actions = validate_transaction(spec, files, headers)
    return {"digest": digest(files), "actions": actions}


def validate_transaction(
    spec: Any, files: dict[str, str], headers: dict[str, str]
) -> list[dict[str, str]]:
    if (
        not isinstance(spec, dict)
        or spec.get("version") != "1.0"
        or set(spec) - {"version", "rpms", "groups", "environments"}
        or spec.get("groups")
        or spec.get("environments")
    ):
        raise ValueError("stored_transaction_schema_not_supported")
    rpms = spec.get("rpms")
    if not isinstance(rpms, list) or not 1 <= len(rpms) <= 400:
        raise ValueError("stored_transaction_actions_invalid")
    actions = []
    seen = set()
    incoming = {"Install", "Upgrade", "Downgrade", "Reinstall"}
    for rpm in rpms:
        if (
            not isinstance(rpm, dict)
            or set(rpm) - {"nevra", "action", "reason", "repo_id", "package_path"}
            or not all(isinstance(v, str) for v in rpm.values())
            or rpm.get("action") not in incoming | {"Remove", "Replaced"}
        ):
            raise ValueError("stored_rpm_action_invalid")
        nevra = normalize_nevra(rpm.get("nevra", ""))
        pair = (rpm["action"], nevra)
        if pair in seen:
            raise ValueError("stored_rpm_action_duplicate")
        seen.add(pair)
        location = rpm.get("package_path", "")
        if location or rpm["action"] in incoming:
            relative = PurePosixPath(location)
            if (
                not location
                or relative.is_absolute()
                or ".." in relative.parts
                or str(relative) != location
                or ":" in location
                or "\\" in location
                or location not in files
                or headers.get(location) != nevra
            ):
                raise ValueError("stored_rpm_outside_verified_tree")
        actions.append({"action": rpm["action"], "nevra": nevra})
    return actions


def expected_packages(actions: list[dict[str, str]], before: set[str]) -> set[str]:
    removed = {item["nevra"] for item in actions if item["action"] in {"Remove", "Replaced"}}
    if not removed <= before:
        raise ValueError("stored_transaction_installed_state_mismatch")
    added = {
        item["nevra"]
        for item in actions
        if item["action"] in {"Install", "Upgrade", "Downgrade", "Reinstall"}
    }
    return (before - removed) | added


def exchange(parent: int, first: str, second: str) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    call = libc.renameat2
    call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    call.restype = ctypes.c_int
    if call(parent, first.encode(), parent, second.encode(), 2):
        raise OSError(ctypes.get_errno(), "initramfs_exchange_failed")


def _perform(request: dict[str, Any], kind: str, uid: int) -> dict[str, Any]:
    validate(request, kind)
    approval = review(request, kind, uid)
    identity = request["id"]
    if kind == "boot":
        state: Any = boot_state(request)
        active_boot_state = dict(state)
        executable = (
            "/usr/bin/grub2-reboot"
            if request["operation"] == "select_kernel"
            else "/usr/bin/dracut"
        )
        read_file(Path(executable), 64 * 1024 * 1024)
        if request["operation"] == "install_initramfs":
            _, raw = read_file(ROOT / "results" / (request["source_operation"] + ".json"), 65536)
            source = json.loads(raw)
            staged = Path("/boot") / (".jarvis-initramfs-" + request["source_operation"] + ".img")
            if (
                source.get("kernel") != request["kernel"]
                or source.get("staged_image") != str(staged)
                or source.get("image_parse_exit") != 0
                or source.get("status") != "command_completed_requires_independent_verification"
            ):
                raise ValueError("staged_initramfs_not_verified")
            staged_hash, _ = read_file(staged)
            if (
                staged_hash != source.get("staged_sha256")
                or approval.get("independent_image_sha256") != staged_hash
            ):
                raise ValueError("independent_initramfs_review_required")
            state[str(staged)] = staged_hash
    else:
        state = rpm_state()
        transaction = ROOT / "transactions" / request["transaction_id"]
        prepared = load_transaction(transaction)
        if prepared["digest"] != request["transaction_digest"]:
            raise ValueError("stored_transaction_drift")
        before = rpm_packages()
        if digest(sorted(before)) != state:
            raise ValueError("rpm_prestate_drift")
        expected_post_state_digest = digest(sorted(expected_packages(prepared["actions"], before)))
        prefix = ["/usr/bin/dnf", "--cacheonly", "--disable-repo=*", "--setopt=installonly_limit=0"]
        if rpm_state() != state:
            raise ValueError("rpm_prestate_drift")
    current_digest = digest(state) if kind == "boot" else state
    if current_digest != request["pre_state_digest"]:
        raise ValueError("pre_state_drift")
    if review(request, kind, uid) != approval:
        raise ValueError("root_review_changed")
    # All exact roots must be provisioned by an independently reviewed install.
    # Reservation and immutable result are distinct files. Never overwrite either.
    write_once(
        ROOT / "reservations" / (identity + ".json"),
        {
            "kind": kind,
            "uid": uid,
            "request": request,
            "pre_state": state,
            "approval_digest": digest(approval),
        },
    )
    result: dict[str, Any] = {
        "id": identity,
        "kind": kind,
        "kernel": request.get("kernel"),
        "request_digest": digest(request),
        "status": "indeterminate",
        "attempts": 1,
        "bootability_verified": False,
    }
    try:
        if review(request, kind, uid) != approval:
            raise ValueError("root_review_changed")
        if kind == "boot" and boot_state(request) != active_boot_state:
            raise ValueError("boot_prestate_drift")
        if kind == "update":
            # DNF5 replay rejects changed installed versions and extra solver
            # actions. Never use ignore-installed/ignore-extras/skip flags.
            if rpm_state() != state:
                raise ValueError("rpm_prestate_drift")
            if load_transaction(transaction)["digest"] != request["transaction_digest"]:
                raise ValueError("stored_transaction_drift")
            code, _ = run([*prefix, "-y", "replay", str(transaction)], timeout=600)
            result.update(
                exit_code=code,
                post_state_digest=rpm_state(),
                expected_post_state_digest=expected_post_state_digest,
            )
            if result["post_state_digest"] != expected_post_state_digest:
                raise ValueError("unexpected_rpm_transaction_result")
        elif request["operation"] == "select_kernel":
            code, _ = run([executable, request["entry"]])
            read_code, contents = run(["/usr/bin/grub2-editenv", "/boot/grub2/grubenv", "list"])
            next_entry = b"next_entry=" + request["entry"].encode()
            result.update(
                exit_code=code,
                post_state=boot_state(request),
                next_entry_verified=read_code == 0 and next_entry in contents.splitlines(),
            )
            if not result["next_entry_verified"]:
                result["exit_code"] = 1
        elif request["operation"] == "install_initramfs":
            active = Path("/boot") / ("initramfs-" + request["kernel"] + ".img")
            backup = ROOT / "backups" / (identity + ".img")
            parent = directory(backup.parent)
            try:
                output = os.open(
                    backup.name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                    dir_fd=parent,
                )
                with active.open("rb") as original, os.fdopen(output, "wb") as saved:
                    copied = 0
                    while chunk := original.read(1048576):
                        copied += len(chunk)
                        if copied > 512 * 1024 * 1024:
                            raise ValueError("initramfs_backup_limit")
                        saved.write(chunk)
                    saved.flush()
                    os.fsync(saved.fileno())
                os.fsync(parent)
            finally:
                os.close(parent)
            if read_file(backup)[0] != state[str(active)] or boot_state(request) != {
                k: v for k, v in state.items() if k != str(staged)
            }:
                raise ValueError("initramfs_backup_or_prestate_drift")
            parent = directory(Path("/boot"))
            try:
                if read_file(staged)[0] != staged_hash or review(request, kind, uid) != approval:
                    raise ValueError("staged_image_or_review_drift")
                exchange(parent, staged.name, active.name)
                result["retained_original"] = str(staged)
                os.fsync(parent)
            finally:
                os.close(parent)
            if read_file(staged)[0] != state[str(active)] or read_file(active)[0] != staged_hash:
                raise ValueError("concurrent_initramfs_change_retained")
            result.update(
                exit_code=0,
                backup=str(backup),
                backup_sha256=state[str(active)],
                post_state=boot_state(request),
                active_image_replaced=True,
            )
        else:
            # Generation into a new file is its own operation. Replacing the
            # active image requires a separate reviewed publication operation.
            destination = Path("/boot") / (".jarvis-initramfs-" + identity + ".img")
            if os.path.lexists(destination):
                raise ValueError("initramfs_destination_exists")
            code, _ = run([executable, str(destination), request["kernel"]], timeout=600)
            if code == 0:
                image_digest, _ = read_file(destination)
                parsed, _ = run(["/usr/bin/lsinitrd", str(destination)])
                result.update(
                    staged_image=str(destination),
                    staged_sha256=image_digest,
                    image_parse_exit=parsed,
                )
                if parsed:
                    code = parsed
            result.update(exit_code=code, active_image_replaced=False)
        if result.get("exit_code") == 0:
            result["status"] = "command_completed_requires_independent_verification"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result["error"] = type(exc).__name__
    write_once(ROOT / "results" / (identity + ".json"), result)
    return result


def perform(request: dict[str, Any], kind: str, uid: int) -> dict[str, Any]:
    validate(request, kind)
    review(request, kind, uid)
    parent = directory(ROOT)
    try:
        lock = os.open(
            "execution.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
    finally:
        os.close(parent)
    try:
        info = os.fstat(lock)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != OWNER
            or info.st_nlink != 1
            or info.st_mode & 0o077
        ):
            raise ValueError("unsafe_execution_lock")
        fcntl.flock(lock, fcntl.LOCK_EX)
        fd = directory(ROOT / "reservations")
        try:
            with os.scandir(fd) as entries:
                for count, entry in enumerate(entries):
                    if count >= 1000:
                        raise ValueError("root_history_review_required")
                    _, data = read_file(ROOT / "results" / entry.name, 65536)
                    if (
                        json.loads(data).get("status")
                        != "command_completed_requires_independent_verification"
                    ):
                        raise ValueError("previous_root_outcome_requires_reconciliation")
        finally:
            os.close(fd)
        return _perform(request, kind, uid)
    finally:
        os.close(lock)


def main(kind: str) -> int:
    try:
        if (
            os.geteuid() != 0
            or not os.environ.get("PKEXEC_UID", "").isdecimal()
            or int(os.environ["PKEXEC_UID"]) <= 0
        ):
            raise ValueError("polkit_user_required")
        data = sys.stdin.buffer.read(32769)
        if len(data) > 32768:
            raise ValueError("request_limit")
        result = perform(json.loads(data), kind, int(os.environ["PKEXEC_UID"]))
        print(json.dumps(result, sort_keys=True))
        return 0 if result["status"] == "command_completed_requires_independent_verification" else 1
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print(
            json.dumps(
                {
                    "status": "blocked_or_indeterminate",
                    "error": "exact_root_review_or_execution_unavailable",
                }
            )
        )
        return 1
