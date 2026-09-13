"""Bounded Fedora workstation health collectors for specialist tool calls."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tui/src"))
from jarvis_tui.observation_safety import (  # noqa: E402
    bounded_process,
    bounded_read,
    open_project,
    read_project_file,
    timestamp,
)
from jarvis_tui.terminal_safety import sanitize_and_redact_terminal_text  # noqa: E402

MAX_OUTPUT = 8_000
SERVICE_NAME = re.compile(r"^[A-Za-z0-9@_.:][A-Za-z0-9@_.:-]{0,127}$")


def _run(argv: tuple[str, ...], timeout: int = 5) -> dict[str, Any]:
    return bounded_process(argv, timeout=timeout, limit=MAX_OUTPUT)


def _read(path: Path, limit: int = MAX_OUTPUT) -> str:
    return bounded_read(path, limit)


def health_inventory() -> dict[str, Any]:
    """Collect bounded performance, service, storage, and network evidence."""
    commands = {
        "cpu": ("lscpu", "--json"),
        "memory": ("free", "--bytes"),
        "processes": ("ps", "-eo", "pid,comm,%cpu,%mem", "--sort=-%cpu"),
        "services": ("systemctl", "--failed", "--no-legend", "--plain"),
        "storage": ("df", "-P", "-x", "tmpfs", "-x", "devtmpfs"),
        "network": ("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"),
    }
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.health_inventory",
        "sources": {name: _run(argv) for name, argv in commands.items()},
        "loadavg": _read(Path("/proc/loadavg"), 256),
        "thermal_zones": sorted(
            path.name for path in Path("/sys/class/thermal").glob("thermal_zone*") if path.is_dir()
        )[:64],
    }


def health_telemetry() -> dict[str, Any]:
    """Read passive current load, memory pressure, and thermal telemetry."""
    meminfo = _read(Path("/proc/meminfo"), 4_000)
    pressure = {
        name: _read(Path("/proc/pressure") / name, 1_000)
        for name in ("cpu", "memory", "io")
        if (Path("/proc/pressure") / name).exists()
    }
    temperatures: dict[str, str] = {}
    for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp"))[:64]:
        value = _read(zone, 64).strip()
        if value:
            temperatures[str(zone)] = value
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.health_telemetry",
        "loadavg": _read(Path("/proc/loadavg"), 256),
        "memory": meminfo,
        "pressure": pressure,
        "temperatures": temperatures,
    }


def development_toolchains() -> dict[str, Any]:
    """Detect common compiler/runtime versions without changing the host."""
    commands = {
        "rustc": ("rustc", "--version"),
        "cargo": ("cargo", "--version"),
        "python": ("python3", "--version"),
        "node": ("node", "--version"),
        "go": ("go", "version"),
        "gcc": ("gcc", "--version"),
        "java": ("java", "-version"),
    }
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.development_toolchains",
        "toolchains": {name: _run(argv) for name, argv in commands.items()},
    }


def development_project_inspect(project_root: str) -> dict[str, Any]:
    """Read bounded project manifests and identify available build systems."""
    if not isinstance(project_root, str) or not project_root or len(project_root) > 512:
        raise ValueError("project root is invalid")
    root = Path(project_root).expanduser()
    files = (
        "Cargo.toml",
        "Cargo.lock",
        "pyproject.toml",
        "package.json",
        "go.mod",
        "pom.xml",
        "Makefile",
    )
    manifests: dict[str, str] = {}
    omitted: dict[str, str] = {}
    fd = open_project(root)
    try:
        for name in files:
            try:
                data = read_project_file(fd, name)
                manifests[name] = sanitize_and_redact_terminal_text(
                    data.decode("utf-8", errors="replace")
                )[0]
            except FileNotFoundError:
                continue
            except (OSError, ValueError):
                omitted[name] = "unsafe_oversized_or_changed"
    finally:
        os.close(fd)
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.development_project_inspect",
        "project_root": str(root),
        "manifests": manifests,
        "omitted": omitted,
        "languages": [
            language
            for language, marker in (
                ("rust", "Cargo.toml"),
                ("python", "pyproject.toml"),
                ("node", "package.json"),
                ("go", "go.mod"),
                ("java", "pom.xml"),
            )
            if marker in manifests
        ],
    }


def health_processes() -> dict[str, Any]:
    """Return bounded CPU and memory process evidence."""
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.health_processes",
        "processes": _run(("ps", "-eo", "pid,ppid,comm,%cpu,%mem,etime", "--sort=-%cpu")),
    }


def health_services() -> dict[str, Any]:
    """Return failed and active systemd service evidence."""
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.health_services",
        "failed": _run(("systemctl", "--failed", "--no-legend", "--plain")),
        "active": _run(
            (
                "systemctl",
                "list-units",
                "--type=service",
                "--state=running",
                "--no-legend",
                "--plain",
            )
        ),
    }


def health_storage() -> dict[str, Any]:
    """Return bounded mount, filesystem, and block-device evidence."""
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.health_storage",
        "filesystems": _run(("df", "-P", "-x", "tmpfs", "-x", "devtmpfs")),
        "mounts": _run(("findmnt", "--json", "--output", "TARGET,SOURCE,FSTYPE,OPTIONS")),
        "devices": _run(("lsblk", "--json", "--output", "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS")),
    }


def health_logs(service: str) -> dict[str, Any]:
    """Read a bounded journal excerpt for one exact systemd service."""
    if not isinstance(service, str) or not SERVICE_NAME.fullmatch(service):
        raise ValueError("service name is invalid")
    result = _run(("journalctl", "--no-pager", "--output=short-iso", "-u", service, "-n", "100"))
    output = result.get("output", "")
    output = re.sub(
        r"(?i)(password|token|secret|api[_-]?key|authorization|cookie)\s*[:=]\s*[^\s]+",
        r"\1=[redacted]",
        output,
    )
    result["output"] = output[:MAX_OUTPUT]
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.health_logs",
        "service": service,
        "journal": result,
    }
