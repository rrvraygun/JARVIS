"""TUI client for the root-owned, allowlisted Jarvis power helper."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

HELPER_PATH = Path("/usr/libexec/jarvis-power-control")
PKEXEC_PATH = Path("/usr/bin/pkexec")
MAX_OUTPUT = 65_536
POWER_CONTROL_OPTIONS = {
    "power.profile": ("power-saver", "balanced", "performance"),
    "cpu.epp": ("power", "balance_power", "balance_performance", "performance"),
    "cpu.turbo": ("enabled", "disabled"),
    "intel_gpu.runtime_pm": ("auto", "on"),
    "nvidia_gpu.runtime_pm": ("auto", "on"),
}


class PowerControlClientError(ValueError):
    pass


def default_journal_path() -> Path:
    return Path.home() / ".local/state/jarvis/power-last-change.json"


def helper_available(path: Path = HELPER_PATH, *, require_root_owned: bool = True) -> bool:
    try:
        info = path.lstat()
    except OSError:
        return False
    if not stat.S_ISREG(info.st_mode) or not os.access(path, os.X_OK):
        return False
    if require_root_owned and (info.st_uid != 0 or info.st_mode & 0o022):
        return False
    return True


def _invoke(
    argv: list[str],
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    try:
        result = runner(argv, check=True, capture_output=True, text=True, timeout=60, shell=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise PowerControlClientError("authorized power operation failed or was cancelled") from exc
    if len(result.stdout.encode()) > MAX_OUTPUT:
        raise PowerControlClientError("power helper response exceeded limit")
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise PowerControlClientError("power helper response is invalid") from exc
    if not isinstance(value, dict) or value.get("status") != "passed":
        raise PowerControlClientError("power helper did not verify the operation")
    return value


def _write_journal(path: Path, value: dict[str, Any]) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise PowerControlClientError("power undo journal path is unsafe")
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(parent, 0o700)
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    if len(payload) > MAX_OUTPUT:
        raise PowerControlClientError("power undo journal exceeded limit")
    temporary = parent / f".{path.name}.{os.getpid()}.tmp"
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def load_undo(path: Path | None = None) -> dict[str, Any] | None:
    target = path or default_journal_path()
    try:
        if target.is_symlink() or target.stat().st_size > MAX_OUTPUT:
            raise PowerControlClientError("power undo journal is unsafe")
        value = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise PowerControlClientError("power undo journal is unreadable") from exc
    required = {"control", "post_value", "pre_state"}
    if (
        not isinstance(value, dict)
        or set(value) != required
        or not isinstance(value["pre_state"], dict)
    ):
        raise PowerControlClientError("power undo journal is invalid")
    return value


def apply_change(
    control: str,
    value: str,
    expected: str,
    *,
    helper: Path = HELPER_PATH,
    journal: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    require_root_owned: bool = True,
) -> dict[str, Any]:
    if not helper_available(helper, require_root_owned=require_root_owned):
        raise PowerControlClientError("root-owned power helper is not deployed")
    result = _invoke(
        [
            str(PKEXEC_PATH),
            str(helper),
            "apply",
            "--control",
            control,
            "--value",
            value,
            "--expected",
            expected,
        ],
        runner,
    )
    record = {key: result[key] for key in ("control", "post_value", "pre_state")}
    try:
        _write_journal(journal or default_journal_path(), record)
        result["user_hint_written"] = True
    except PowerControlClientError:
        # The root helper committed the authoritative record before mutation.
        # A user hint failure must not hide or misreport the verified change.
        result["user_hint_written"] = False
    return result


def apply_profile_transaction(
    changes: dict[str, str],
    expected: dict[str, str],
    *,
    helper: Path = HELPER_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    require_root_owned: bool = True,
) -> dict[str, Any]:
    """Apply one exact multi-control profile through the root helper."""
    if not changes or set(changes) != set(expected) or len(changes) > 16:
        raise PowerControlClientError("power profile control set is invalid")
    if not helper_available(helper, require_root_owned=require_root_owned):
        raise PowerControlClientError("root-owned power helper is not deployed")
    result = _invoke(
        [
            str(PKEXEC_PATH),
            str(helper),
            "apply-profile",
            "--changes-json",
            json.dumps(changes, sort_keys=True, separators=(",", ":")),
            "--expected-json",
            json.dumps(expected, sort_keys=True, separators=(",", ":")),
        ],
        runner,
    )
    if result.get("operation") != "profile" or not isinstance(result.get("controls"), dict):
        raise PowerControlClientError("power profile helper response is invalid")
    return result


def authoritative_undo_status(
    *,
    helper: Path = HELPER_PATH,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    require_root_owned: bool = True,
) -> dict[str, Any]:
    if not helper_available(helper, require_root_owned=require_root_owned):
        raise PowerControlClientError("root-owned power helper is not deployed")
    result = _invoke([str(PKEXEC_PATH), str(helper), "status"], runner)
    if (
        result.get("operation") not in {"status", "recovery-status"}
        or not isinstance(result.get("control"), str)
        or not isinstance(result.get("post_value"), str)
        or not isinstance(result.get("record_digest"), str)
        or len(result["record_digest"]) != 64
    ):
        raise PowerControlClientError("authoritative undo status is invalid")
    return result


def undo_last(
    record_digest: str,
    *,
    helper: Path = HELPER_PATH,
    journal: Path | None = None,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    require_root_owned: bool = True,
) -> dict[str, Any]:
    target = journal or default_journal_path()
    if not helper_available(helper, require_root_owned=require_root_owned):
        raise PowerControlClientError("root-owned power helper is not deployed")
    if len(record_digest) != 64 or any(char not in "0123456789abcdef" for char in record_digest):
        raise PowerControlClientError("authoritative undo digest is invalid")
    result = _invoke(
        [str(PKEXEC_PATH), str(helper), "undo", "--record-digest", record_digest],
        runner,
    )
    target.unlink(missing_ok=True)
    return result
