#!/usr/bin/env python3
"""Root-owned, exact-set Jarvis package transaction helper.

The helper accepts only package names and an approval-bound preflight digest.
It never accepts a shell command, repository URL, arbitrary DNF option, or
transaction-wide approval. Rollback is a separate invocation and approval.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path
from typing import Any

NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.:-]{0,199}$")
ROOT = Path("/var/lib/jarvis/package-control")
ROOT_COMPONENTS = ("var", "lib", "jarvis", "package-control")
MAX_RECORD = 65_536
MAX_TRANSACTION_PACKAGES = 200
RPM_ARCH = re.compile(r"^(?:aarch64|i[3-6]86|noarch|ppc64le|s390x|src|x86_64)$", re.IGNORECASE)


def _row_package_name(token: str) -> str | None:
    token = token.lstrip("|+-*> ")
    match = re.match(
        r"^([A-Za-z0-9][A-Za-z0-9+_.:]*?)-[0-9].*\.(?:aarch64|i[3-6]86|noarch|ppc64le|s390x|src|x86_64)$",
        token,
        re.IGNORECASE,
    )
    if match:
        return match.group(1)
    direct = (
        token.rsplit(".", 1)[0]
        if re.search(
            r"\.(?:aarch64|i[3-6]86|noarch|ppc64le|s390x|src|x86_64)$", token, re.IGNORECASE
        )
        else token
    )
    return direct if NAME.fullmatch(direct) and not direct.isdigit() else None


def _matching_preview_lines(output: str, names: tuple[str, ...]) -> str:
    lines = []
    needles = tuple(name.casefold() for name in names)
    for raw in output.splitlines():
        line = " ".join(raw.split())
        if len(line) <= 300 and any(needle in line.casefold() for needle in needles):
            lines.append(line)
    return " | ".join(lines[:8])


PROTECTED_REMOVAL_PACKAGES = frozenset(
    {
        "audit",
        "bash",
        "coreutils",
        "dnf",
        "dnf5",
        "filesystem",
        "glibc",
        "kernel",
        "networkmanager",
        "polkit",
        "rpm",
        "selinux-policy",
        "setup",
        "shadow-utils",
        "sudo",
        "systemd",
    }
)


class PackageControlError(ValueError):
    pass


def _uid() -> int:
    raw = os.environ.get("PKEXEC_UID", "")
    if not raw.isascii() or not raw.isdigit() or int(raw) <= 0:
        raise PackageControlError("authenticated desktop caller identity is unavailable")
    return int(raw)


def _secure_root_fd() -> int:
    """Open the fixed journal path without following any directory component."""
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, component in enumerate(ROOT_COMPONENTS):
            try:
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                if index < 2:
                    raise PackageControlError("package journal ancestor is missing")
                os.mkdir(component, 0o700, dir_fd=descriptor)
                os.fsync(descriptor)
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            info = os.fstat(child)
            final_component = index == len(ROOT_COMPONENTS) - 1
            unsafe_mode = info.st_mode & 0o022
            if info.st_uid != 0 or unsafe_mode or (final_component and info.st_mode & 0o077):
                os.close(child)
                raise PackageControlError("package journal ownership or mode is unsafe")
            os.close(descriptor)
            descriptor = child
        return descriptor
    except (OSError, PackageControlError) as exc:
        os.close(descriptor)
        if isinstance(exc, PackageControlError):
            raise
        raise PackageControlError("package journal path is unsafe") from exc


def _secure_root() -> None:
    descriptor = _secure_root_fd()
    os.close(descriptor)


def _record_path(uid: int) -> Path:
    return ROOT / f"{uid}.json"


def _lock(uid: int):
    _secure_root()
    descriptor = _secure_root_fd()
    try:
        lock_fd = os.open(
            f"{uid}.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
            dir_fd=descriptor,
        )
    finally:
        os.close(descriptor)
    handle = os.fdopen(lock_fd, "a+", encoding="ascii")
    os.chmod(handle.fileno(), 0o600)
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _run(argv: list[str], timeout: float = 120.0) -> str:
    result = subprocess.run(
        argv, check=True, capture_output=True, text=True, timeout=timeout, shell=False
    )
    output = result.stdout
    if len(output.encode()) > 2 * 1024 * 1024:
        raise PackageControlError("package transaction output exceeded the bound")
    return output


def _validate_names(values: list[str]) -> tuple[str, ...]:
    names = tuple(dict.fromkeys(values))
    if not names or len(names) > 20 or any(not NAME.fullmatch(value) for value in names):
        raise PackageControlError("package set is invalid")
    return names


def _installed(names: tuple[str, ...]) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for name in names:
        probe = subprocess.run(
            [
                "rpm",
                "-q",
                "--qf",
                "%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}.%{ARCH}",
                name,
            ],
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
        )
        state = probe.stdout.strip() if probe.returncode == 0 else None
        if state is not None and len(state) > 1_024:
            raise PackageControlError("package pre-state exceeded its bound")
        result[name] = state
    return result


def _digest(
    operation: str,
    names: tuple[str, ...],
    pre_state: dict[str, str | None],
    preview_digest: str,
) -> str:
    value = {
        "operation": operation,
        "names": list(names),
        "pre_state": pre_state,
        "preview_digest": preview_digest,
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _preview(operation: str, names: tuple[str, ...]) -> str:
    argv = ["dnf", "--cacheonly", "--assumeno", operation]
    # DNF5 accepts --no-autoremove only after its remove subcommand.
    if operation == "remove":
        argv.append("--no-autoremove")
    result = subprocess.run(
        [*argv, *names],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
        shell=False,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if len(output.encode()) > 2 * 1024 * 1024:
        raise PackageControlError("package transaction preview exceeded the bound")
    if result.returncode not in {0, 1} or not re.search(
        r"(?:transaction\s+summary|resumen\s+de\s+la\s+transacci[oó]n|installing:|instalando:|removing:|eliminando:|desinstalando:)",
        output,
        re.IGNORECASE,
    ):
        raise PackageControlError("package transaction can no longer be resolved")
    return _canonicalize_preview(output)


def _canonicalize_preview(output: str) -> str:
    """Drop non-semantic DNF cache/log diagnostics before digest binding."""
    rows: set[str] = set()
    name_pattern = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9+_.:-]{0,199}(?:\.(?:aarch64|i[3-6]86|noarch|ppc64le|s390x|src|x86_64))?$",
        re.IGNORECASE,
    )
    for raw in output.splitlines():
        line = " ".join(raw.strip().split())
        lowered = line.casefold()
        if (
            "cannot open log file" in lowered
            or lowered.startswith("last metadata expiration check:")
            or lowered.startswith("warning: cannot open")
        ):
            continue
        fields = line.split()
        if len(fields) >= 2 and name_pattern.fullmatch(fields[0]):
            rows.add(f"{fields[0]} {fields[1]}")
    return "\n".join(sorted(rows, key=str.casefold))


def _contains_protected_removal(output: str) -> bool:
    lowered = output.casefold()
    return any(
        re.search(rf"(?m)^\s*{re.escape(name)}(?:\.|\s)", lowered)
        for name in PROTECTED_REMOVAL_PACKAGES
    ) or bool(re.search(r"(?m)^\s*kernel-[A-Za-z0-9+_.:-]*(?:\.|\s)", lowered))


def _removed_packages(output: str) -> tuple[str, ...]:
    values: set[str] = set()
    active = False
    removal_heading = re.compile(
        r"^\s*(removing|removing\s+dependent\s+packages|eliminando|desinstalando)(?:\s*:.*)?$",
        re.IGNORECASE,
    )
    other_heading = re.compile(
        r"^\s*(installing|upgrading|downgrading|reinstalling|replacing|instalando|actualizando)(?:\s*:.*)?$",
        re.IGNORECASE,
    )
    summary_count = re.compile(
        r"^\s*(?:installing|upgrading|downgrading|reinstalling|replacing|removing|"
        r"instalando|actualizando|degradando|reinstalando|reemplazando|eliminando|"
        r"desinstalando)\s*:\s*\d+\s+(?:packages?|paquetes?)\b",
        re.IGNORECASE,
    )
    for line in output.splitlines():
        if summary_count.match(line):
            active = False
            continue
        if removal_heading.match(line):
            active = True
            continue
        if other_heading.match(line) or re.match(
            r"^\s*(transaction summary|resumen de la transacci[oó]n)",
            line,
            re.IGNORECASE,
        ):
            active = False
            continue
        if not active or not line.strip() or set(line.strip()) <= {"-", "="}:
            continue
        fields = line.strip().split()
        token = fields[0]
        name = _row_package_name(token)
        if name is None:
            continue
        looks_rpm = bool(
            re.search(
                r"\.(?:aarch64|i[3-6]86|noarch|ppc64le|s390x|src|x86_64)$", token, re.IGNORECASE
            )
        )
        looks_versioned = len(fields) > 1 and bool(re.match(r"^(?:\d|[0-9]+:)", fields[1]))
        looks_arch = len(fields) > 1 and bool(RPM_ARCH.fullmatch(fields[1]))
        if (looks_rpm or looks_versioned or looks_arch or "-" in token) and name.casefold() not in {
            "package",
            "paquete",
        }:
            values.add(name)
    if not re.search(
        r"(?im)^\s*(?:installing(?:\s+(?:packages?|dependencies|weak dependencies|groups))?|"
        r"upgrading|downgrading|reinstalling|replacing|instalando(?:\s+dependencias)?|"
        r"actualizando|degradando|reinstalando|reemplazando)\s*:",
        output,
    ):
        table_values = _table_package_names(output)
        if table_values:
            values = set(table_values)
    return tuple(sorted(values, key=str.casefold))


def _table_package_names(output: str) -> tuple[str, ...]:
    values: set[str] = set()
    table_active = False
    header = re.compile(
        r"^\s*(?:package|paquete)\s+(?:arch|architecture|arquitectura|arq)\b",
        re.IGNORECASE,
    )
    for line in output.splitlines():
        if re.match(
            r"^\s*(?:transaction summary|resumen de la transacci[oó]n)",
            line,
            re.IGNORECASE,
        ):
            break
        if header.match(line):
            table_active = True
            continue
        if not table_active:
            continue
        fields = line.strip().lstrip("|+-*> ").split()
        arch_index = next(
            (index for index, field in enumerate(fields[:5]) if RPM_ARCH.fullmatch(field)),
            None,
        )
        if arch_index is None or arch_index == 0:
            continue
        name = _row_package_name(fields[arch_index - 1])
        if name is None and arch_index >= 2:
            name = _row_package_name(fields[arch_index - 2])
        if name is not None:
            values.add(name)
    return tuple(sorted(values, key=str.casefold))


def _installed_packages(output: str) -> tuple[str, ...]:
    values: set[str] = set()
    active = False
    install_heading = re.compile(
        r"^\s*(installing(?:\s+(?:packages?|dependencies|weak dependencies|groups))?|"
        r"instalando(?:\s+(?:dependencias|dependencias d[eé]biles|grupos))?)(?:\s*:.*)?$",
        re.IGNORECASE,
    )
    other_heading = re.compile(
        r"^\s*(removing|upgrading|downgrading|reinstalling|replacing|eliminando|"
        r"desinstalando|actualizando)(?:\s*:.*)?$",
        re.IGNORECASE,
    )
    summary_count = re.compile(
        r"^\s*(?:installing|upgrading|downgrading|reinstalling|replacing|removing|"
        r"instalando|actualizando|degradando|reinstalando|reemplazando|eliminando|"
        r"desinstalando)\s*:\s*\d+\s+(?:packages?|paquetes?)\b",
        re.IGNORECASE,
    )
    for line in output.splitlines():
        if summary_count.match(line):
            active = False
            continue
        if install_heading.match(line):
            active = True
            remainder = line.split(":", 1)[1].strip() if ":" in line else ""
            fields = remainder.split()
            if fields:
                name = _row_package_name(fields[0])
                if name is not None:
                    values.add(name)
            continue
        if other_heading.match(line) or re.match(
            r"^\s*(transaction summary|resumen de la transacci[oó]n)",
            line,
            re.IGNORECASE,
        ):
            active = False
            continue
        if not active or not line.strip() or set(line.strip()) <= {"-", "="}:
            continue
        fields = line.strip().split()
        token = fields[0]
        name = _row_package_name(token)
        if name is None:
            continue
        looks_rpm = bool(
            re.search(
                r"\.(?:aarch64|i[3-6]86|noarch|ppc64le|s390x|src|x86_64)$", token, re.IGNORECASE
            )
        )
        looks_versioned = len(fields) > 1 and bool(re.match(r"^(?:\d|[0-9]+:)", fields[1]))
        looks_arch = len(fields) > 1 and bool(RPM_ARCH.fullmatch(fields[1]))
        if (looks_rpm or looks_versioned or looks_arch or "-" in token) and name.casefold() not in {
            "package",
            "paquete",
        }:
            values.add(name)
    # Some DNF5 builds print package rows outside their section heading.
    for line in output.splitlines():
        fields = line.strip().lstrip("|+-*> ").split()
        if len(fields) < 2 or not RPM_ARCH.fullmatch(fields[1]):
            continue
        name = _row_package_name(fields[0])
        if name is not None:
            values.add(name)
    # DNF5 may emit a stable Package/Arch transaction table in addition to,
    # or instead of, localized Installing headings. Union both bounded views;
    # mixed effects remain fail-closed.
    if not re.search(
        r"(?im)^\s*(?:removing|upgrading|downgrading|reinstalling|replacing|"
        r"eliminando|desinstalando|actualizando|degradando|reinstalando|reemplazando)\s*:",
        output,
    ):
        values.update(_table_package_names(output))
    return tuple(sorted(values, key=str.casefold))


def _has_non_additive_install_effect(output: str) -> bool:
    return bool(
        re.search(
            r"(?im)^\s*(?:upgrading|downgrading|reinstalling|replacing|"
            r"actualizando|degradando|reinstalando|reemplazando)\s*:",
            output,
        )
    )


def _bound_install_spec(value: str) -> str:
    """Convert one bound RPM state row to an exact DNF NEVRA argument."""
    fields = value.split("|")
    if len(fields) != 4 or "." not in fields[3]:
        raise PackageControlError("package rollback pre-state is not version-bound")
    name, epoch, version, release_arch = fields
    release, arch = release_arch.rsplit(".", 1)
    if (
        not NAME.fullmatch(name)
        or not epoch.isascii()
        or not epoch.isdigit()
        or not all(part and len(part) <= 200 for part in (version, release, arch))
        or any(character.isspace() for part in (version, release, arch) for character in part)
    ):
        raise PackageControlError("package rollback pre-state is invalid")
    epoch_prefix = "" if epoch == "0" else f"{epoch}:"
    return f"{name}-{epoch_prefix}{version}-{release}.{arch}"


def _write(uid: int, record: dict[str, Any]) -> None:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    if len(payload) > MAX_RECORD:
        raise PackageControlError("package transaction record exceeded the bound")
    target = _record_path(uid)
    temporary = ROOT / f".{uid}.{os.getpid()}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
        os.chmod(target, 0o600)
        fd = os.open(ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _load(uid: int) -> dict[str, Any]:
    target = _record_path(uid)
    try:
        descriptor = os.open(target, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError as exc:
        raise PackageControlError("no package transaction recovery record exists") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise PackageControlError("package transaction record is unsafe")
        value = json.loads(os.read(descriptor, MAX_RECORD + 1))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageControlError("package transaction record is unreadable") from exc
    finally:
        os.close(descriptor)
    if not isinstance(value, dict) or value.get("status") not in {
        "prepared",
        "applied",
    }:
        raise PackageControlError("package transaction record is invalid")
    return value


def _record_digest(record: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _delete_record(uid: int) -> None:
    descriptor = _secure_root_fd()
    try:
        os.unlink(f"{uid}.json", dir_fd=descriptor)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _archive_fd() -> int:
    root_fd = _secure_root_fd()
    try:
        try:
            os.mkdir("archive", 0o700, dir_fd=root_fd)
            os.fsync(root_fd)
        except FileExistsError:
            pass
        descriptor = os.open(
            "archive", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd
        )
    finally:
        os.close(root_fd)
    info = os.fstat(descriptor)
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
        os.close(descriptor)
        raise PackageControlError("package archive directory is unsafe")
    return descriptor


def _archive_record(uid: int, record: dict[str, Any], record_digest: str) -> None:
    descriptor = _archive_fd()
    filename = f"{uid}-{record_digest}.json"
    payload = json.dumps(
        {
            "schema_version": 1,
            "record_digest": record_digest,
            "archived_record": record,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    if len(payload) > MAX_RECORD:
        os.close(descriptor)
        raise PackageControlError("package archive record exceeded the bound")
    try:
        archive_fd = os.open(
            filename,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=descriptor,
        )
        try:
            view = memoryview(payload)
            while view:
                written = os.write(archive_fd, view)
                if written <= 0:
                    raise OSError("short package archive write")
                view = view[written:]
            os.fsync(archive_fd)
        finally:
            os.close(archive_fd)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def apply(names: list[str], preview_digest: str, approved_digest: str) -> dict[str, Any]:
    uid = _uid()
    values = _validate_names(names)
    if len(preview_digest) != 64 or len(approved_digest) != 64:
        raise PackageControlError("approval digest is invalid")
    lock = _lock(uid)
    try:
        observed_preview = _preview("install", values)
        if hashlib.sha256(observed_preview.encode()).hexdigest() != preview_digest:
            raise PackageControlError("package preview changed; re-approval required")
        removed = _removed_packages(observed_preview)
        non_additive = _has_non_additive_install_effect(observed_preview)
        if (
            removed
            or non_additive
            or re.search(
                r"(?:removing|eliminando|desinstalando):\s*[1-9]",
                observed_preview,
                re.IGNORECASE,
            )
        ):
            raise PackageControlError(
                "resolved installation is not strictly additive; "
                f"removed={','.join(removed[:24])}; upgrade_or_replace={str(non_additive).lower()}"
            )
        affected = _installed_packages(observed_preview)
        if (
            not affected
            or len(affected) > MAX_TRANSACTION_PACKAGES
            or not set(values).issubset(affected)
        ):
            shown = ",".join(affected[:24])
            evidence = _matching_preview_lines(observed_preview, values)
            raise PackageControlError(
                "resolved installation set is incomplete; "
                f"requested={','.join(values)}; resolved_count={len(affected)}; resolved={shown}"
                + (f"; matching_lines={evidence}" if evidence else "")
            )
        pre_state = _installed(affected)
        expected = _digest("install", values, pre_state, preview_digest)
        if expected != approved_digest:
            raise PackageControlError(
                "package state or preview digest changed; re-approval required"
            )
        if _record_path(uid).exists():
            raise PackageControlError("a package transaction is already awaiting rollback")
        prepared = {
            "operation": "install",
            "names": list(values),
            "affected_installs": list(affected),
            "pre_state": pre_state,
            "preview_digest": preview_digest,
            "status": "prepared",
        }
        # Durable pre-state is committed before the transaction starts.
        _write(uid, prepared)
        # The command is fixed; package names are validated and passed as data.
        _run(["dnf", "-y", "install", *values])
        post_state = _installed(affected)
        if any(post_state[name] is None for name in affected):
            raise PackageControlError("package postcondition failed")
        transaction = {
            "operation": "install",
            "names": list(values),
            "affected_installs": list(affected),
            "pre_state": pre_state,
            "post_state": post_state,
            "preview_digest": preview_digest,
            "status": "applied",
        }
        _write(uid, transaction)
        return {
            "status": "passed",
            "operation": "apply",
            "packages": list(values),
            "post_state": post_state,
            "record_digest": _record_digest(transaction),
        }
    finally:
        lock.close()


def remove(names: list[str], preview_digest: str, approved_digest: str) -> dict[str, Any]:
    uid = _uid()
    values = _validate_names(names)
    if any(
        name.casefold() in PROTECTED_REMOVAL_PACKAGES or name.casefold().startswith("kernel-")
        for name in values
    ):
        raise PackageControlError("protected or boot-critical package removal is denied")
    if len(preview_digest) != 64 or len(approved_digest) != 64:
        raise PackageControlError("approval digest is invalid")
    lock = _lock(uid)
    try:
        observed_preview = _preview("remove", values)
        if hashlib.sha256(observed_preview.encode()).hexdigest() != preview_digest:
            raise PackageControlError("package preview changed; re-approval required")
        if _contains_protected_removal(observed_preview):
            raise PackageControlError("resolved transaction includes a protected package")
        affected = _removed_packages(observed_preview)
        if (
            not affected
            or len(affected) > MAX_TRANSACTION_PACKAGES
            or not set(values).issubset(affected)
        ):
            raise PackageControlError("resolved removal set is incomplete")
        pre_state = _installed(affected)
        if any(pre_state[name] is None for name in affected):
            raise PackageControlError("resolved removal pre-state is incomplete")
        for state in pre_state.values():
            assert state is not None
            _bound_install_spec(state)
        expected = _digest("remove", values, pre_state, preview_digest)
        if expected != approved_digest:
            raise PackageControlError(
                "package state or preview digest changed; re-approval required"
            )
        if _record_path(uid).exists():
            raise PackageControlError("a package transaction is already awaiting rollback")
        prepared = {
            "operation": "remove",
            "names": list(values),
            "affected_removals": list(affected),
            "pre_state": pre_state,
            "preview_digest": preview_digest,
            "status": "prepared",
        }
        _write(uid, prepared)
        _run(["dnf", "-y", "remove", "--no-autoremove", *values])
        post_state = _installed(affected)
        if any(post_state[name] is not None for name in affected):
            raise PackageControlError("package removal postcondition failed")
        transaction = {
            "operation": "remove",
            "names": list(values),
            "affected_removals": list(affected),
            "pre_state": pre_state,
            "post_state": post_state,
            "preview_digest": preview_digest,
            "status": "applied",
        }
        _write(uid, transaction)
        return {
            "status": "passed",
            "operation": "remove",
            "packages": list(values),
            "post_state": post_state,
            "record_digest": _record_digest(transaction),
        }
    finally:
        lock.close()


def status() -> dict[str, Any]:
    uid = _uid()
    lock = _lock(uid)
    try:
        try:
            record = _load(uid)
        except PackageControlError as exc:
            if str(exc) != "no package transaction recovery record exists":
                raise
            return {
                "status": "passed",
                "operation": "status",
                "packages": [],
                "rollback_packages": [],
                "record_status": "none",
                "archive_allowed": False,
                "transaction_operation": None,
                "record_digest": "0" * 64,
            }
        return {
            "status": "passed",
            "operation": "status" if record["status"] == "applied" else "recovery-status",
            "packages": record["names"],
            "rollback_packages": sorted(record.get("pre_state", {}), key=str.casefold),
            "record_status": record["status"],
            "archive_allowed": record["status"] == "applied",
            "transaction_operation": record.get("operation", "install"),
            "record_digest": _record_digest(record),
        }
    finally:
        lock.close()


def archive(record_digest: str) -> dict[str, Any]:
    """Seal an applied record and retire its rollback capability; never run DNF."""
    uid = _uid()
    lock = _lock(uid)
    try:
        record = _load(uid)
        observed_digest = _record_digest(record)
        if record_digest != observed_digest:
            raise PackageControlError("authoritative package record changed; re-review required")
        if record["status"] != "applied":
            raise PackageControlError("only an applied package record may be archived")
        _archive_record(uid, record, observed_digest)
        _delete_record(uid)
        return {
            "status": "passed",
            "operation": "archive",
            "packages": list(record["names"]),
            "archived_record_digest": observed_digest,
        }
    finally:
        lock.close()


def undo(record_digest: str) -> dict[str, Any]:
    uid = _uid()
    lock = _lock(uid)
    try:
        record = _load(uid)
        if record_digest != _record_digest(record):
            raise PackageControlError("authoritative package record changed; re-review required")
        if record["status"] == "prepared":
            observed_state = _installed(tuple(record["pre_state"]))
            if observed_state != record["pre_state"]:
                raise PackageControlError(
                    "prepared package record may reflect a partial mutation; manual recovery inspection is required"
                )
            _delete_record(uid)
            return {
                "status": "passed",
                "operation": "reconcile",
                "packages": list(record["names"]),
                "reconciled": "prepared record cleared after exact pre-state verification",
            }
        operation = record.get("operation", "install")
        if operation == "install":
            targets = [name for name, before in record["pre_state"].items() if before is None]
            if not targets:
                raise PackageControlError("rollback has no package absent from the pre-state")
            rollback_preview = _preview("remove", tuple(targets))
            resolved = _removed_packages(rollback_preview)
            if _contains_protected_removal(rollback_preview) or set(resolved) != set(targets):
                raise PackageControlError(
                    "rollback removal would affect packages outside the recorded set"
                )
            _run(["dnf", "-y", "remove", "--no-autoremove", *targets])
            post_state = _installed(tuple(targets))
            if any(post_state[name] is not None for name in targets):
                raise PackageControlError("package rollback postcondition failed")
        elif operation == "remove":
            targets = [name for name, before in record["pre_state"].items() if before is not None]
            if not targets:
                raise PackageControlError("rollback has no package to restore")
            exact_targets = [_bound_install_spec(record["pre_state"][name]) for name in targets]
            rollback_preview = _preview("install", tuple(exact_targets))
            resolved = _installed_packages(rollback_preview)
            if (
                _removed_packages(rollback_preview)
                or _has_non_additive_install_effect(rollback_preview)
                or set(resolved) != set(targets)
            ):
                raise PackageControlError(
                    "package restore would affect packages outside the recorded set"
                )
            _run(["dnf", "-y", "install", *exact_targets])
            post_state = _installed(tuple(targets))
            if any(post_state[name] != record["pre_state"][name] for name in targets):
                raise PackageControlError("package restore postcondition failed")
        else:
            raise PackageControlError("package transaction operation is invalid")
        _delete_record(uid)
        return {
            "status": "passed",
            "operation": "undo",
            "packages": targets,
            "undid": operation,
        }
    finally:
        lock.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)
    action = sub.add_parser("apply")
    action.add_argument("--preview-digest", required=True)
    action.add_argument("--approved-digest", required=True)
    action.add_argument("packages", nargs="+")
    remove_parser = sub.add_parser("remove")
    remove_parser.add_argument("--preview-digest", required=True)
    remove_parser.add_argument("--approved-digest", required=True)
    remove_parser.add_argument("packages", nargs="+")
    undo_parser = sub.add_parser("undo")
    undo_parser.add_argument("--record-digest", required=True)
    archive_parser = sub.add_parser("archive")
    archive_parser.add_argument("--record-digest", required=True)
    sub.add_parser("status")
    args = parser.parse_args()
    try:
        if args.operation == "apply":
            value = apply(args.packages, args.preview_digest, args.approved_digest)
        elif args.operation == "remove":
            value = remove(args.packages, args.preview_digest, args.approved_digest)
        elif args.operation == "undo":
            value = undo(args.record_digest)
        elif args.operation == "archive":
            value = archive(args.record_digest)
        else:
            value = status()
        print(json.dumps(value, sort_keys=True))
        return 0
    except PackageControlError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
