"""Read-only Fedora network, security, and recovery evidence collectors."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tui/src"))
from jarvis_tui.observation_safety import bounded_process, timestamp  # noqa: E402


def _run(argv: tuple[str, ...], timeout: int = 5) -> dict[str, Any]:
    return bounded_process(argv, timeout=timeout)


def network_inventory() -> dict[str, Any]:
    """Inspect local interfaces, routes, DNS, and listening sockets."""
    commands = {
        "interfaces": ("ip", "-j", "address"),
        "routes": ("ip", "-j", "route"),
        "connections": ("nmcli", "-t", "-f", "NAME,UUID,TYPE,DEVICE", "connection", "show"),
        "network_manager": ("nmcli", "-t", "-f", "STATE,CONNECTIVITY", "general"),
        "dns": ("resolvectl", "status"),
        "listening": ("ss", "-H", "-lntup"),
    }
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.network_inventory",
        "sources": {name: _run(argv) for name, argv in commands.items()},
    }


def security_inventory() -> dict[str, Any]:
    """Inspect local security posture without changing policy or host state."""
    commands = {
        "selinux": ("getenforce",),
        "firewall": ("firewall-cmd", "--state"),
        "secure_boot": ("mokutil", "--sb-state"),
        "listening": ("ss", "-H", "-lntup"),
        "failed_services": ("systemctl", "--failed", "--no-legend", "--plain"),
    }
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.security_inventory",
        "sources": {name: _run(argv) for name, argv in commands.items()},
    }


def recovery_inventory() -> dict[str, Any]:
    """Inspect local recovery signals and available snapshot tooling."""
    commands = {
        "mounts": ("findmnt", "--json", "--output", "TARGET,SOURCE,FSTYPE,OPTIONS"),
        "btrfs_subvolumes": ("btrfs", "subvolume", "list", "/"),
        "snapper": ("snapper", "list"),
        "systemd_boots": ("journalctl", "--list-boots"),
    }
    return {
        "read_only": True,
        "observed_at": timestamp(),
        "collector": "jarvis.recovery_inventory",
        "sources": {name: _run(argv) for name, argv in commands.items()},
        "recovery_paths": [
            str(path) for path in (Path("/var/lib/snapper"), Path("/var/backups")) if path.exists()
        ],
    }
