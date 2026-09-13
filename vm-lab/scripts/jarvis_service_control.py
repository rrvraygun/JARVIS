#!/usr/bin/python3
"""Standalone fixed service helper. No imports from a writable project.

Installation and the root-owned per-unit policy are separately reviewed actions.
No operation is enabled by shipping this file.
"""

from __future__ import annotations

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
from pathlib import Path
from typing import Any

POLICY = Path("/etc/jarvis/service-policy.json")
JOURNAL = Path("/var/lib/jarvis-service-control")
UNIT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.service$")
PROTECTED = {
    "auditd.service",
    "firewalld.service",
    "sshd.service",
    "NetworkManager.service",
    "dbus.service",
    "dbus-broker.service",
    "polkit.service",
    "gdm.service",
    "sddm.service",
    "systemd-logind.service",
    "systemd-journald.service",
}
PROPERTIES = "Id,LoadState,ActiveState,SubState,UnitFileState,NeedDaemonReload,FragmentPath,DropInPaths,Requires,Wants,Requisite,BindsTo,PartOf,ConsistsOf,TriggeredBy,Triggers"


def bounded_read_process(argv: list[str], **unused: Any) -> subprocess.CompletedProcess[bytes]:
    deadline = time.monotonic() + 5
    output = bytearray()
    with subprocess.Popen(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    ) as process:
        assert process.stdout is not None
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise ValueError("observation_timeout")
                    for key, _ in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fd, min(4096, 8193 - len(output)))
                        if not chunk:
                            selector.unregister(key.fileobj)
                        else:
                            output.extend(chunk)
                            if len(output) > 8192:
                                raise ValueError("observation_output_limit")
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
        assert process.returncode is not None
        return subprocess.CompletedProcess(argv, process.returncode, bytes(output))


def binding(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def valid_unit(unit: str) -> None:
    if not UNIT.fullmatch(unit) or unit in PROTECTED or unit.startswith("systemd-"):
        raise ValueError("service_not_supported")


def install_links(data: bytes, unit: str) -> list[str]:
    section = ""
    links = []
    for line in data.decode().splitlines():
        text = line.strip()
        if text.startswith("[") and text.endswith("]"):
            section = text[1:-1]
        elif section == "Install" and text and not text.startswith(("#", ";")):
            if "=" not in text or text.endswith("\\"):
                raise ValueError("service_install_syntax_not_supported")
            key, value = text.split("=", 1)
            if key.strip() not in {"WantedBy", "RequiredBy"}:
                raise ValueError("service_install_directive_not_supported")
            for target in value.split():
                if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,100}\.target", target):
                    raise ValueError("service_install_target_not_supported")
                suffix = "wants" if key.strip() == "WantedBy" else "requires"
                links.append("/etc/systemd/system/" + target + "." + suffix + "/" + unit)
    return sorted(set(links))


def current_links(fragment: Path) -> list[str]:
    links = []
    count = 0
    root = Path("/etc/systemd/system")
    for folder, directories, files in os.walk(root, followlinks=False):
        parent = Path(folder)
        if len(parent.relative_to(root).parts) > 3:
            raise ValueError("service_link_depth_limit")
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("service_link_directory_unsafe")
        for name in directories + files:
            count += 1
            if count > 2000:
                raise ValueError("service_link_inventory_limit")
            path = parent / name
            if path.is_symlink():
                if name in directories:
                    raise ValueError("service_link_directory_alias_not_supported")
                if path.resolve() == fragment:
                    links.append(str(path))
    return sorted(links)


def observe(unit: str, runner: Any = None) -> dict[str, str]:
    valid_unit(unit)
    result = (runner or bounded_read_process)(
        ["/usr/bin/systemctl", "show", unit, "--no-pager", "--property=" + PROPERTIES],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=5,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    if result.returncode != 0 or len(result.stdout) > 8192:
        raise ValueError("service_observation_unavailable")
    fields = dict(line.split("=", 1) for line in result.stdout.decode().splitlines() if "=" in line)
    if (
        fields.get("Id") != unit
        or fields.get("LoadState") != "loaded"
        or fields.get("NeedDaemonReload") != "no"
    ):
        raise ValueError("service_not_canonical_or_reloaded")
    if any(
        fields.get(key)
        for key in (
            "DropInPaths",
            "Requires",
            "Wants",
            "Requisite",
            "BindsTo",
            "PartOf",
            "ConsistsOf",
            "TriggeredBy",
            "Triggers",
        )
    ):
        raise ValueError("service_complex_effects_not_registered")
    path = Path(fields.pop("FragmentPath", ""))
    if not path.is_absolute() or not str(path).startswith(
        ("/etc/systemd/system/", "/usr/lib/systemd/system/")
    ):
        raise ValueError("service_fragment_outside_registered_roots")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & 0o022
            or info.st_size > 65536
        ):
            raise ValueError("service_fragment_unsafe")
        data = os.read(fd, 65537)
        if len(data) > 65536:
            raise ValueError("service_fragment_oversized")
        if re.search(rb"(?m)^\s*(?:Also|Alias)\s*=|^\s*\.include\b", data):
            raise ValueError("service_install_expansion_not_registered")
        fields["expected_enabled_links"] = json.dumps(install_links(data, unit))
        fields["current_links"] = json.dumps(current_links(path))
        fields["fragment_sha256"] = hashlib.sha256(data).hexdigest()
    finally:
        os.close(fd)
    return fields


def policy_for(unit: str, path: Path = POLICY) -> dict[str, Any]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & 0o022
            or info.st_size > 16384
        ):
            raise ValueError("service_policy_unsafe")
        value = json.loads(os.read(fd, 16385))
    finally:
        os.close(fd)
    entry = value.get("units", {}).get(unit, {})
    if (
        value.get("activation_enabled") is not True
        or entry.get("reviewed") is not True
        or entry.get("recovery_level") != "R1"
        or not isinstance(entry.get("expires_at"), (int, float))
        or not math.isfinite(entry["expires_at"])
        or not time.time() < entry["expires_at"] <= time.time() + 1800
        or not re.fullmatch("[0-9a-f]{64}", entry.get("recovery_evidence_digest", ""))
    ):
        raise ValueError("service_not_enrolled_with_recovery")
    return dict(entry)


def execute(
    request: dict[str, Any],
    state: dict[str, str],
    policy: dict[str, Any],
    reserve: Any,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    if set(request) != {"id", "operation", "unit", "pre_state_digest", "policy_digest"}:
        raise ValueError("service_request_invalid")
    unit = request["unit"]
    valid_unit(unit)
    operation = request["operation"]
    if operation not in {"restart", "enable", "disable"} or not re.fullmatch(
        "[0-9a-f]{32}", request["id"]
    ):
        raise ValueError("service_operation_invalid")
    if binding(state) != request["pre_state_digest"] or binding(policy) != request["policy_digest"]:
        raise ValueError("service_prestate_or_policy_drift")
    if operation not in policy.get("operations", []) or state["UnitFileState"] not in {
        "enabled",
        "disabled",
    }:
        raise ValueError("service_effect_not_registered")
    reserve(
        {
            "request": request,
            "before": state,
            "recovery_evidence_digest": policy["recovery_evidence_digest"],
        }
    )
    result = runner(
        ["/usr/bin/systemctl", operation, unit],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
    )
    return {
        "id": request["id"],
        "status": "applied_unverified" if result.returncode == 0 else "indeterminate",
        "exit_code": result.returncode,
        "attempts": 1,
        "unit": unit,
        "operation": operation,
        "recovery": "Restart cannot restore process memory; enable/disable require a new exact inverse proposal.",
    }


def main() -> int:
    if os.geteuid() != 0 or not os.environ.get("PKEXEC_UID", "").isdigit():
        raise ValueError("desktop_authorization_required")
    uid = int(os.environ["PKEXEC_UID"])
    if uid == 0:
        raise ValueError("nonroot_requester_required")
    raw = sys.stdin.buffer.read(16385)
    if len(raw) > 16384:
        raise ValueError("service_request_oversized")
    request = json.loads(raw)
    state = observe(request["unit"])
    policy = policy_for(request["unit"])
    # The fixed parent must be installed root-owned; never create through symlinks.
    parent = os.open(JOURNAL, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(parent)
        if info.st_uid != 0 or info.st_mode & 0o077:
            raise ValueError("service_journal_unsafe")
        name = str(uid) + "-" + request["id"] + ".json"

        def reserve(record: dict[str, Any]) -> None:
            if not re.fullmatch(r"[0-9]+-[0-9a-f]{32}\.json", name):
                raise ValueError("service_record_invalid")
            fd = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
            )
            with os.fdopen(fd, "w") as stream:
                json.dump(record, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(parent)

        result = execute(request, state, policy, reserve)
        print(json.dumps(result, sort_keys=True))
    finally:
        os.close(parent)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print(json.dumps({"status": "indeterminate", "error": "service_attempt_stopped"}))
        raise SystemExit(1)
