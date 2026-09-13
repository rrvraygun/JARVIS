#!/usr/bin/python3
"""Fixed configuration adapters; root-owned enrollment and exact Polkit use required."""

from __future__ import annotations

import hashlib
import ipaddress
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
import uuid
from pathlib import Path
from typing import Any

POLICY = Path("/etc/jarvis/configuration-policy.json")
JOURNAL = Path("/var/lib/jarvis-configuration-control")
TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


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


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate(adapter: str, target: str, desired: Any) -> None:
    if adapter == "network.ipv4_dns":
        if str(uuid.UUID(target)) != target or not isinstance(desired, list) or len(desired) > 3:
            raise ValueError("exact_dns_target_required")
        for address in desired:
            parsed = ipaddress.IPv4Address(address)
            if str(parsed) != address or parsed.is_multicast or parsed.is_unspecified:
                raise ValueError("dns_address_invalid")
    elif adapter == "security.firewall_service":
        parts = target.split("/")
        if (
            len(parts) != 2
            or not all(TOKEN.fullmatch(item) for item in parts)
            or desired not in {"present", "absent"}
        ):
            raise ValueError("exact_firewall_target_required")
    elif adapter == "security.restore_labels":
        path = Path(target)
        if (
            desired != "default"
            or not path.is_absolute()
            or ".." in path.parts
            or path.parts[1] not in {"etc", "usr"}
        ):
            raise ValueError("exact_selinux_file_required")
    else:
        raise ValueError("configuration_adapter_not_registered")


def read_command(
    argv: list[str], runner: Any = None, *, negative_ok: bool = False
) -> tuple[int, str]:
    result = (runner or bounded_read_process)(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=5,
        check=False,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )
    if result.returncode not in ({0, 1} if negative_ok else {0}) or len(result.stdout) > 8192:
        raise ValueError("configuration_observation_unavailable")
    return result.returncode, result.stdout.decode().strip()


def file_identity(target: str) -> dict[str, Any]:
    path = Path(target)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError("selinux_parent_unsafe")
        child = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        try:
            info = os.fstat(child)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != 0
                or info.st_mode & 0o022
                or info.st_nlink != 1
            ):
                raise ValueError("selinux_target_unsafe")
            label = os.getxattr(child, "security.selinux").decode().rstrip("\x00")
            return {
                "device": info.st_dev,
                "inode": info.st_ino,
                "links": info.st_nlink,
                "label": label,
            }
        finally:
            os.close(child)
    finally:
        os.close(fd)


def observe(adapter: str, target: str, desired: Any, runner: Any = None) -> dict[str, Any]:
    validate(adapter, target, desired)
    if adapter == "network.ipv4_dns":
        _, output = read_command(
            ["/usr/bin/nmcli", "-g", "ipv4.dns", "connection", "show", "uuid", target], runner
        )
        values = [str(ipaddress.IPv4Address(item)) for item in re.split(r"[,\s]+", output) if item]
        return {"value": values, "target": target}
    if adapter == "security.firewall_service":
        zone, service = target.split("/")
        code, _ = read_command(
            ["/usr/bin/firewall-cmd", "--zone=" + zone, "--query-service=" + service],
            runner,
            negative_ok=True,
        )
        _, definition = read_command(["/usr/bin/firewall-cmd", "--info-service=" + service], runner)
        ports = []
        for line in definition.splitlines()[1:]:
            if ":" not in line:
                if line.strip():
                    raise ValueError("firewall_definition_not_supported")
                continue
            key, value = line.strip().split(":", 1)
            if key == "ports":
                for port in value.split():
                    match = re.fullmatch(r"(\d{1,5})(?:-(\d{1,5}))?/(tcp|udp)", port)
                    if not match:
                        raise ValueError("firewall_port_not_supported")
                    low = int(match[1])
                    high = int(match[2] or match[1])
                    if not 1 <= low <= high <= 65535 or high - low > 16:
                        raise ValueError("firewall_port_range_too_broad")
                    ports.append(port)
            elif value.strip():
                raise ValueError("firewall_expanded_service_not_supported")
        if not ports or len(ports) > 16:
            raise ValueError("firewall_explicit_ports_required")
        return {
            "ports": ports,
            "value": "present" if code == 0 else "absent",
            "target": target,
            "definition_digest": digest(definition),
        }
    state = file_identity(target)
    _, expected = read_command(["/usr/sbin/matchpathcon", "-n", target], runner)
    if not re.fullmatch(r"[A-Za-z0-9_:.,-]{1,256}", expected):
        raise ValueError("selinux_expected_label_invalid")
    return {**state, "expected": expected, "value": state["label"], "target": target}


def command(adapter: str, target: str, desired: Any) -> list[str]:
    validate(adapter, target, desired)
    if adapter == "network.ipv4_dns":
        return [
            "/usr/bin/nmcli",
            "connection",
            "modify",
            "uuid",
            target,
            "ipv4.dns",
            ",".join(desired),
        ]
    if adapter == "security.firewall_service":
        zone, service = target.split("/")
        return [
            "/usr/bin/firewall-cmd",
            "--zone=" + zone,
            ("--add-service=" if desired == "present" else "--remove-service=") + service,
        ]
    return ["/usr/sbin/restorecon", "--", target]


def enrollment(adapter: str, target: str) -> dict[str, Any]:
    fd = os.open(POLICY, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & 0o022
            or info.st_size > 16384
        ):
            raise ValueError("configuration_policy_unsafe")
        policy = json.loads(os.read(fd, 16385))
    finally:
        os.close(fd)
    entry = policy.get("targets", {}).get(adapter + ":" + target, {})
    if (
        policy.get("activation_enabled") is not True
        or entry.get("reviewed") is not True
        or entry.get("recovery_level") != "R1"
        or not isinstance(entry.get("expires_at"), (int, float))
        or not math.isfinite(entry["expires_at"])
        or not time.time() < entry["expires_at"] <= time.time() + 1800
        or not re.fullmatch("[0-9a-f]{64}", entry.get("recovery_evidence_digest", ""))
    ):
        raise ValueError("configuration_target_not_enrolled")
    return dict(entry)


def apply(
    request: dict[str, Any],
    state: dict[str, Any],
    policy: dict[str, Any],
    reserve: Any,
    runner: Any = subprocess.run,
) -> dict[str, Any]:
    if set(request) != {
        "id",
        "adapter",
        "target",
        "desired",
        "pre_state_digest",
        "policy_digest",
    } or not re.fullmatch("[0-9a-f]{32}", request["id"]):
        raise ValueError("configuration_request_invalid")
    adapter, target, desired = request["adapter"], request["target"], request["desired"]
    argv = command(adapter, target, desired)
    if (
        digest(state) != request["pre_state_digest"]
        or digest(policy) != request["policy_digest"]
        or desired not in policy.get("allowed_values", [])
    ):
        raise ValueError("configuration_state_policy_or_value_drift")
    reserve(
        {
            "request": request,
            "before": state,
            "recovery_evidence_digest": policy["recovery_evidence_digest"],
        }
    )
    result = runner(
        argv,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=30,
        check=False,
        env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
    )
    return {
        "id": request["id"],
        "adapter": adapter,
        "target": target,
        "desired": desired,
        "status": "applied_unverified" if result.returncode == 0 else "indeterminate",
        "exit_code": result.returncode,
        "attempts": 1,
    }


def main() -> int:
    if (
        os.geteuid() != 0
        or not os.environ.get("PKEXEC_UID", "").isdigit()
        or int(os.environ["PKEXEC_UID"]) == 0
    ):
        raise ValueError("desktop_authorization_required")
    raw = sys.stdin.buffer.read(16385)
    if len(raw) > 16384:
        raise ValueError("configuration_request_oversized")
    request = json.loads(raw)
    state = observe(request["adapter"], request["target"], request["desired"])
    policy = enrollment(request["adapter"], request["target"])
    parent = os.open(JOURNAL, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        info = os.fstat(parent)
        if info.st_uid != 0 or info.st_mode & 0o077:
            raise ValueError("configuration_journal_unsafe")

        def reserve(record: dict[str, Any]) -> None:
            name = os.environ["PKEXEC_UID"] + "-" + request["id"] + ".json"
            if not re.fullmatch(r"[0-9]+-[0-9a-f]{32}\.json", name):
                raise ValueError("configuration_record_invalid")
            fd = os.open(
                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
            )
            with os.fdopen(fd, "w") as stream:
                json.dump(record, stream, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(parent)

        print(json.dumps(apply(request, state, policy, reserve), sort_keys=True))
    finally:
        os.close(parent)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print(json.dumps({"status": "indeterminate", "error": "configuration_attempt_stopped"}))
        raise SystemExit(1)
