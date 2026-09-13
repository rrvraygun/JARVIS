#!/usr/bin/env python3
"""Root-owned, allowlisted Jarvis power mutation helper.

This helper has no arbitrary path, command, or value input.  It performs one
exact change, verifies it, and returns the captured pre-state for a separately
confirmed undo operation.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

PROFILE_VALUES = {"power-saver", "balanced", "performance"}
EPP_VALUES = {"power", "balance_power", "balance_performance", "performance"}
TURBO_VALUES = {"enabled", "disabled"}
RUNTIME_PM_VALUES = {"auto", "on"}
CONTROL_VALUES = {
    "power.profile": PROFILE_VALUES,
    "cpu.epp": EPP_VALUES,
    "cpu.turbo": TURBO_VALUES,
    "intel_gpu.runtime_pm": RUNTIME_PM_VALUES,
    "nvidia_gpu.runtime_pm": RUNTIME_PM_VALUES,
}
BUSCTL = "/usr/bin/busctl"
BUS_NAME = "org.freedesktop.UPower.PowerProfiles"
OBJECT_PATH = "/org/freedesktop/UPower/PowerProfiles"
INTERFACE = "org.freedesktop.UPower.PowerProfiles"
JOURNAL_COMPONENTS = ("var", "lib", "jarvis", "power-control")
THERMAL_LIMIT_MILLICELSIUS = 90_000


class PowerControlError(ValueError):
    pass


def _actor_uid() -> int:
    raw = os.environ.get("PKEXEC_UID", "")
    if not raw.isascii() or not raw.isdigit() or int(raw) <= 0:
        raise PowerControlError("authenticated desktop caller identity is unavailable")
    return int(raw)


def _journal_name(actor_uid: int) -> str:
    return f"{actor_uid}.json"


def _pending_name(actor_uid: int) -> str:
    return f"{actor_uid}.pending.json"


def _open_secure_directory(
    root: Path,
    components: tuple[str, ...],
    *,
    expected_uid: int,
    create_from: int,
) -> int:
    """Open the fixed journal directory without following any component."""
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, component in enumerate(components):
            allow_create = index >= create_from
            try:
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                if not allow_create:
                    raise PowerControlError("authoritative journal ancestor is missing")
                os.mkdir(component, 0o700, dir_fd=descriptor)
                os.fsync(descriptor)
                child = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=descriptor,
                )
            info = os.fstat(child)
            if info.st_uid != expected_uid or info.st_mode & 0o022:
                os.close(child)
                raise PowerControlError(
                    "authoritative journal directory ownership or mode is unsafe"
                )
            os.close(descriptor)
            descriptor = child
        return descriptor
    except (OSError, PowerControlError) as exc:
        os.close(descriptor)
        if isinstance(exc, PowerControlError):
            raise
        raise PowerControlError("authoritative journal directory is unsafe") from exc


def _open_authoritative_directory() -> int:
    return _open_secure_directory(Path("/"), JOURNAL_COMPONENTS, expected_uid=0, create_from=2)


def _journal_exists(name: str) -> bool:
    directory_fd = _open_authoritative_directory()
    try:
        try:
            os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False
    finally:
        os.close(directory_fd)


def _write_authoritative_journal(name: str, record: dict[str, Any]) -> None:
    payload = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    if len(payload) > 65_536:
        raise PowerControlError("authoritative undo record exceeded limit")
    directory_fd = _open_authoritative_directory()
    temporary = f".{name}.{os.getpid()}.tmp"
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.chmod(name, 0o600, dir_fd=directory_fd, follow_symlinks=False)
        os.fsync(directory_fd)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass
        os.close(directory_fd)


def _load_authoritative_journal(name: str) -> dict[str, Any]:
    directory_fd = _open_authoritative_directory()
    descriptor: int | None = None
    try:
        descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise PowerControlError("authoritative undo record is unsafe")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            payload = stream.read(65_537)
        if len(payload) > 65_536:
            raise PowerControlError("authoritative undo record exceeded limit")
        record = json.loads(payload)
    except FileNotFoundError as exc:
        raise PowerControlError("there is no power change to undo") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PowerControlError("authoritative undo record is unreadable") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory_fd)
    if not isinstance(record, dict):
        raise PowerControlError("authoritative undo record is invalid")
    if record.get("operation") == "profile":
        if set(record) != {"operation", "controls", "pre_state", "post_state", "status"}:
            raise PowerControlError("authoritative profile record is invalid")
        if not isinstance(record["controls"], dict) or not isinstance(record["post_state"], dict):
            raise PowerControlError("authoritative profile record is invalid")
    elif set(record) != {"control", "post_value", "pre_state", "status"}:
        raise PowerControlError("authoritative undo record is invalid")
    if record["status"] != "prepared" or not isinstance(record["pre_state"], dict):
        raise PowerControlError("authoritative power record has an unexpected state")
    return record


def _replace_journal(source: str, destination: str) -> None:
    directory_fd = _open_authoritative_directory()
    try:
        os.replace(source, destination, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
        os.fsync(directory_fd)
    except OSError as exc:
        raise PowerControlError("authoritative journal commit failed") from exc
    finally:
        os.close(directory_fd)


def _remove_journal(name: str) -> None:
    directory_fd = _open_authoritative_directory()
    try:
        os.unlink(name, dir_fd=directory_fd)
        os.fsync(directory_fd)
    except OSError as exc:
        raise PowerControlError("authoritative journal consumption failed") from exc
    finally:
        os.close(directory_fd)


@contextmanager
def _actor_transaction_lock(actor_uid: int):
    """Serialize every status/apply/undo transaction for one desktop UID."""
    directory_fd = _open_authoritative_directory()
    name = f"{actor_uid}.lock"
    lock_fd: int | None = None
    try:
        lock_fd = os.open(
            name,
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory_fd,
        )
        info = os.fstat(lock_fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise PowerControlError("power transaction lock is unsafe")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield
    except OSError as exc:
        raise PowerControlError("power transaction lock failed") from exc
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)
        os.close(directory_fd)


def _record_digest(record: dict[str, Any]) -> str:
    payload = json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _expected_digest(value: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise PowerControlError("authoritative record digest is invalid")
    return value


def _verify_record_digest(record: dict[str, Any], expected: str) -> None:
    if _record_digest(record) != _expected_digest(expected):
        raise PowerControlError("authoritative undo record changed after review")


def _run(argv: list[str]) -> str:
    try:
        result = subprocess.run(
            argv, check=True, capture_output=True, text=True, timeout=15, shell=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PowerControlError("fixed provider operation failed") from exc
    if len(result.stdout.encode()) > 16_384:
        raise PowerControlError("provider response exceeded limit")
    return result.stdout.strip()


def _profile_read(run: Callable[[list[str]], str]) -> str:
    raw = run([BUSCTL, "get-property", BUS_NAME, OBJECT_PATH, INTERFACE, "ActiveProfile"])
    try:
        value = raw.split(maxsplit=1)[1].strip().strip('"')
    except IndexError as exc:
        raise PowerControlError("profile response is invalid") from exc
    if value not in PROFILE_VALUES:
        raise PowerControlError("active profile is unsupported")
    return value


def _profile_write(value: str, run: Callable[[list[str]], str]) -> None:
    run(
        [
            BUSCTL,
            "set-property",
            BUS_NAME,
            OBJECT_PATH,
            INTERFACE,
            "ActiveProfile",
            "s",
            value,
        ]
    )


def _require_thermal_safe(root: Path) -> None:
    readings: list[int] = []
    for path in sorted(root.glob("sys/class/thermal/thermal_zone[0-9]*/temp")):
        try:
            raw = path.read_text(encoding="ascii").strip()
            if raw.isascii() and raw.isdigit():
                readings.append(int(raw))
        except OSError:
            continue
    if not readings:
        raise PowerControlError("thermal state is unavailable; profile/turbo mutation is blocked")
    if max(readings) >= THERMAL_LIMIT_MILLICELSIUS:
        raise PowerControlError("thermal degradation detected; profile/turbo mutation is blocked")


def _targets(root: Path, control: str) -> dict[str, Path]:
    if control == "cpu.epp":
        paths = sorted(
            root.glob("sys/devices/system/cpu/cpu[0-9]*/cpufreq/energy_performance_preference")
        )
        return {path.parents[1].name: path for path in paths}
    if control == "cpu.turbo":
        path = root / "sys/devices/system/cpu/intel_pstate/no_turbo"
        return {"intel_pstate": path} if path.is_file() else {}
    vendor = "0x8086" if control == "intel_gpu.runtime_pm" else "0x10de"
    result: dict[str, Path] = {}
    for card in sorted(root.glob("sys/class/drm/card[0-9]")):
        try:
            if (card / "device/vendor").read_text(encoding="utf-8").strip().casefold() == vendor:
                result[card.name] = card / "device/power/control"
        except OSError:
            continue
    return result


def _decode_value(control: str, value: str) -> str:
    if value not in CONTROL_VALUES.get(control, set()):
        raise PowerControlError("requested value is not allowlisted")
    if control == "cpu.turbo":
        return "0" if value == "enabled" else "1"
    return value


def _encode_value(control: str, value: str) -> str:
    if control == "cpu.turbo":
        if value not in {"0", "1"}:
            raise PowerControlError("turbo state is invalid")
        return "enabled" if value == "0" else "disabled"
    return value


def _read_targets(root: Path, control: str) -> tuple[dict[str, Path], dict[str, str]]:
    paths = _targets(root, control)
    if not paths:
        raise PowerControlError("control has no live target")
    values: dict[str, str] = {}
    for key, path in paths.items():
        try:
            values[key] = _encode_value(control, path.read_text(encoding="utf-8").strip())
        except OSError as exc:
            raise PowerControlError("control pre-state is unreadable") from exc
    return paths, values


def _write_targets(paths: dict[str, Path], control: str, requested: dict[str, str]) -> None:
    if set(paths) != set(requested):
        raise PowerControlError("restore target set drifted")
    for key, path in paths.items():
        raw = _decode_value(control, requested[key])
        _write_target(path, raw)


def _write_target(path: Path, raw: str) -> None:
    """Write one kernel control only after a no-follow identity check."""
    try:
        before = path.lstat()
        if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
            raise PowerControlError("control target is unsafe")
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_TRUNC | os.O_CLOEXEC | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise PowerControlError("control target changed before write")
            os.write(descriptor, raw.encode("utf-8"))
        finally:
            os.close(descriptor)
    except PowerControlError:
        raise
    except OSError as exc:
        raise PowerControlError("control write failed; outcome may be partial") from exc


def apply(
    control: str,
    value: str,
    expected: str,
    *,
    root: Path = Path("/"),
    run: Callable[[list[str]], str] = _run,
    precommit: Callable[[dict[str, Any]], None] | None = None,
    thermal_guard: Callable[[], None] | None = None,
) -> dict[str, Any]:
    _decode_value(control, value)
    if control in {"power.profile", "cpu.turbo"}:
        (thermal_guard or (lambda: _require_thermal_safe(root)))()
    if control == "power.profile":
        before = _profile_read(run)
        if before != expected or before == value:
            raise PowerControlError("profile pre-state is stale or transition is a no-op")
        pre_state = {"profile": before}
        if precommit is not None:
            precommit(
                {
                    "control": control,
                    "post_value": value,
                    "pre_state": pre_state,
                    "status": "prepared",
                }
            )
        _profile_write(value, run)
        after = _profile_read(run)
        if after != value:
            raise PowerControlError("profile postcondition failed")
    else:
        paths, before_values = _read_targets(root, control)
        if set(before_values.values()) != {expected} or expected == value:
            raise PowerControlError("control pre-state is stale, divergent, or a no-op")
        pre_state = {"targets": before_values}
        if precommit is not None:
            precommit(
                {
                    "control": control,
                    "post_value": value,
                    "pre_state": pre_state,
                    "status": "prepared",
                }
            )
        _write_targets(paths, control, {key: value for key in paths})
        _, after_values = _read_targets(root, control)
        if set(after_values.values()) != {value}:
            raise PowerControlError("control postcondition failed")
    return {
        "status": "passed",
        "control": control,
        "pre_state": pre_state,
        "post_value": value,
    }


def undo(
    control: str,
    expected: str,
    pre_state: dict[str, Any],
    *,
    root: Path = Path("/"),
    run: Callable[[list[str]], str] = _run,
    thermal_guard: Callable[[], None] | None = None,
) -> dict[str, Any]:
    _decode_value(control, expected)
    if control in {"power.profile", "cpu.turbo"}:
        (thermal_guard or (lambda: _require_thermal_safe(root)))()
    if control == "power.profile":
        prior = pre_state.get("profile")
        if prior not in PROFILE_VALUES or _profile_read(run) != expected:
            raise PowerControlError("undo pre-state is invalid or stale")
        _profile_write(prior, run)
        if _profile_read(run) != prior:
            raise PowerControlError("undo postcondition failed")
        restored: Any = prior
    else:
        prior = pre_state.get("targets")
        if not isinstance(prior, dict) or not prior:
            raise PowerControlError("undo pre-state is invalid")
        paths, current = _read_targets(root, control)
        if set(current.values()) != {expected} or set(prior) != set(paths):
            raise PowerControlError("undo target state drifted")
        if any(value not in CONTROL_VALUES[control] for value in prior.values()):
            raise PowerControlError("undo value is not allowlisted")
        _write_targets(paths, control, prior)
        _, restored_values = _read_targets(root, control)
        if restored_values != prior:
            raise PowerControlError("undo postcondition failed")
        restored = prior
    return {
        "status": "passed",
        "control": control,
        "restored": restored,
        "undone_value": expected,
    }


def recover_prepared(
    control: str,
    expected: str,
    pre_state: dict[str, Any],
    *,
    root: Path = Path("/"),
    run: Callable[[list[str]], str] = _run,
    thermal_guard: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Restore a fsynced pre-state after an interrupted or partial apply."""
    _decode_value(control, expected)
    if control in {"power.profile", "cpu.turbo"}:
        (thermal_guard or (lambda: _require_thermal_safe(root)))()
    if control == "power.profile":
        prior = pre_state.get("profile")
        current = _profile_read(run)
        if prior not in PROFILE_VALUES or current not in {prior, expected}:
            raise PowerControlError("prepared profile recovery state is invalid")
        _profile_write(prior, run)
        if _profile_read(run) != prior:
            raise PowerControlError("prepared profile recovery postcondition failed")
        restored: Any = prior
    else:
        prior = pre_state.get("targets")
        if not isinstance(prior, dict) or not prior:
            raise PowerControlError("prepared recovery pre-state is invalid")
        paths, current = _read_targets(root, control)
        if set(prior) != set(paths):
            raise PowerControlError("prepared recovery target set drifted")
        if any(value not in CONTROL_VALUES[control] for value in prior.values()):
            raise PowerControlError("prepared recovery value is not allowlisted")
        if any(current[key] not in {prior[key], expected} for key in paths):
            raise PowerControlError("prepared recovery current state drifted")
        _write_targets(paths, control, prior)
        _, restored_values = _read_targets(root, control)
        if restored_values != prior:
            raise PowerControlError("prepared recovery postcondition failed")
        restored = prior
    return {
        "status": "passed",
        "operation": "recovery",
        "control": control,
        "restored": restored,
        "attempted_value": expected,
    }


def _control_pre_state(
    control: str,
    *,
    root: Path,
    run: Callable[[list[str]], str],
) -> tuple[str, dict[str, Any]]:
    """Capture one control's canonical expected value and exact restore state."""
    if control == "power.profile":
        value = _profile_read(run)
        return value, {"profile": value}
    _, values = _read_targets(root, control)
    if not values or len(set(values.values())) != 1:
        raise PowerControlError("profile control pre-state is divergent or unavailable")
    value = next(iter(values.values()))
    return value, {"targets": values}


def apply_profile(
    changes: dict[str, str],
    expected: dict[str, str],
    *,
    root: Path = Path("/"),
    run: Callable[[list[str]], str] = _run,
    precommit: Callable[[dict[str, Any]], None] | None = None,
    thermal_guard: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Apply one exact multi-control profile and retain one recoverable record."""
    if not 1 <= len(changes) <= 16 or set(changes) != set(expected):
        raise PowerControlError("profile control set is invalid")
    pre_state: dict[str, dict[str, Any]] = {}
    for control, value in sorted(changes.items()):
        if control not in CONTROL_VALUES:
            raise PowerControlError("profile control is not allowlisted")
        _decode_value(control, value)
        observed, state = _control_pre_state(control, root=root, run=run)
        if expected[control] != observed or observed == value:
            raise PowerControlError("profile pre-state is stale, divergent, or contains a no-op")
        pre_state[control] = state
    if precommit is not None:
        precommit(
            {
                "operation": "profile",
                "controls": changes,
                "pre_state": pre_state,
                "post_state": changes,
                "status": "prepared",
            }
        )
    for control, value in sorted(changes.items()):
        apply(
            control,
            value,
            expected[control],
            root=root,
            run=run,
            thermal_guard=thermal_guard,
        )
    return {
        "status": "passed",
        "operation": "profile",
        "controls": changes,
        "pre_state": pre_state,
        "post_state": changes,
    }


def undo_profile(
    controls: dict[str, str],
    pre_state: dict[str, dict[str, Any]],
    *,
    root: Path = Path("/"),
    run: Callable[[list[str]], str] = _run,
    thermal_guard: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Restore every control in one profile record, preserving partial recovery."""
    if set(controls) != set(pre_state):
        raise PowerControlError("profile rollback control set drifted")
    restored: dict[str, Any] = {}
    for control, value in sorted(controls.items()):
        result = undo(
            control,
            value,
            pre_state[control],
            root=root,
            run=run,
            thermal_guard=thermal_guard,
        )
        restored[control] = result["restored"]
    return {
        "status": "passed",
        "operation": "profile-rollback",
        "controls": controls,
        "restored": restored,
    }


def recover_profile(
    controls: dict[str, str],
    pre_state: dict[str, dict[str, Any]],
    *,
    root: Path = Path("/"),
    run: Callable[[list[str]], str] = _run,
) -> dict[str, Any]:
    """Recover a prepared profile after interruption when current state is bound."""
    if set(controls) != set(pre_state):
        raise PowerControlError("prepared profile control set drifted")
    restored: dict[str, Any] = {}
    for control, value in sorted(controls.items()):
        prior = pre_state[control]
        if control == "power.profile":
            current = _profile_read(run)
            prior_value = prior.get("profile")
            if current not in {prior_value, value}:
                raise PowerControlError("prepared profile current state drifted")
            if current != prior_value:
                _profile_write(str(prior_value), run)
                if _profile_read(run) != prior_value:
                    raise PowerControlError("prepared profile recovery postcondition failed")
            restored[control] = prior_value
        else:
            paths, current = _read_targets(root, control)
            targets = prior.get("targets")
            if not isinstance(targets, dict) or set(targets) != set(paths):
                raise PowerControlError("prepared profile target set drifted")
            if any(current[key] not in {targets[key], value} for key in paths):
                raise PowerControlError("prepared profile current state drifted")
            if current != targets:
                _write_targets(paths, control, targets)
                _, restored_values = _read_targets(root, control)
                if restored_values != targets:
                    raise PowerControlError("prepared profile recovery postcondition failed")
            restored[control] = targets
    return {
        "status": "passed",
        "operation": "profile-recovery",
        "controls": controls,
        "restored": restored,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="operation", required=True)
    apply_parser = sub.add_parser("apply")
    apply_parser.add_argument("--control", required=True, choices=sorted(CONTROL_VALUES))
    apply_parser.add_argument("--value", required=True)
    apply_parser.add_argument("--expected", required=True)
    profile_parser = sub.add_parser("apply-profile")
    profile_parser.add_argument("--changes-json", required=True)
    profile_parser.add_argument("--expected-json", required=True)
    undo_parser = sub.add_parser("undo")
    undo_parser.add_argument("--record-digest", required=True)
    sub.add_parser("status")
    return parser


def main() -> int:
    try:
        if os.geteuid() != 0:
            raise PowerControlError("power-control helper requires root")
        args = _parser().parse_args()
        actor_uid = _actor_uid()
        journal = _journal_name(actor_uid)
        pending = _pending_name(actor_uid)
        with _actor_transaction_lock(actor_uid):
            if args.operation == "apply":
                if _journal_exists(pending):
                    raise PowerControlError(
                        "a prior power operation has an unresolved prepared state"
                    )
                result = apply(
                    args.control,
                    args.value,
                    args.expected,
                    precommit=lambda record: _write_authoritative_journal(pending, record),
                )
                # The exact prepared record remains recoverable through every
                # interruption point. Its directory entry becomes the verified
                # last-change record only after postcondition verification.
                _replace_journal(pending, journal)
            elif args.operation == "apply-profile":
                if _journal_exists(pending):
                    raise PowerControlError(
                        "a prior power operation has an unresolved prepared state"
                    )
                try:
                    changes = json.loads(args.changes_json)
                    expected = json.loads(args.expected_json)
                except json.JSONDecodeError as exc:
                    raise PowerControlError("profile JSON is invalid") from exc
                if not isinstance(changes, dict) or not isinstance(expected, dict):
                    raise PowerControlError("profile JSON must contain objects")
                result = apply_profile(
                    {str(key): str(value) for key, value in changes.items()},
                    {str(key): str(value) for key, value in expected.items()},
                    precommit=lambda record: _write_authoritative_journal(pending, record),
                )
                _replace_journal(pending, journal)
            elif args.operation == "undo":
                recovery = _journal_exists(pending)
                record_path = pending if recovery else journal
                record = _load_authoritative_journal(record_path)
                _verify_record_digest(record, args.record_digest)
                if record.get("operation") == "profile":
                    result = (
                        recover_profile(record["post_state"], record["pre_state"])
                        if recovery
                        else undo_profile(record["post_state"], record["pre_state"])
                    )
                elif recovery:
                    result = recover_prepared(
                        record["control"], record["post_value"], record["pre_state"]
                    )
                else:
                    result = undo(record["control"], record["post_value"], record["pre_state"])
                _remove_journal(record_path)
            else:
                recovery = _journal_exists(pending)
                record = _load_authoritative_journal(pending if recovery else journal)
                result = {
                    "status": "passed",
                    "operation": "recovery-status" if recovery else "status",
                    "control": record.get("control", "profile"),
                    "post_value": record.get("post_value", "profile"),
                    "controls": record.get("controls", record.get("post_state", {})),
                    "record_digest": _record_digest(record),
                }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except PowerControlError as exc:
        print(
            json.dumps({"status": "error", "error": str(exc)}, sort_keys=True),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
