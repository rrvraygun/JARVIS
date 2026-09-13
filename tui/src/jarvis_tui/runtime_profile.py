"""Validate the exact child profile before allowing an App Server agent turn."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any


def validate(config: dict[str, Any], bundle: Path) -> None:
    servers = config.get("mcp_servers", {})
    features = config.get("features", {})
    server = servers.get("jarvis_control", {})
    expected = str(bundle / "plugins/jarvis-system-admin/scripts/mcp_server.py")
    if (
        config.get("sandbox_mode") != "read-only"
        or config.get("approval_policy") != "never"
        or config.get("web_search") != "disabled"
        or features.get("plugins") is not False
        or features.get("hooks") is not False
        or set(servers) != {"jarvis_control"}
        or server.get("command") != "/usr/bin/python3"
        or server.get("args") != [expected]
        or server.get("required") is not True
        or set(server) - {"command", "args", "required", "env"}
        or server.get("env") != {"JARVIS_STORE": str(bundle / "runtime/control-store")}
        or set(config.get("apps", {})) != {"_default"}
        or config.get("apps", {}).get("_default", {}).get("enabled") is not False
    ):
        raise ValueError("runtime_profile_authority_mismatch")


def check(bundle: Path) -> None:
    path = bundle / "runtime/codex-home/config.toml"
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError("runtime_profile_unsafe")
    validate(tomllib.loads(path.read_text()), bundle)
    policy = json.loads((bundle / "plugins/jarvis-system-admin/policy/policy.json").read_text())
    if (
        policy.get("default") != "deny"
        or policy.get("attempt_limit") != 1
        or policy.get("automatic_retry") is not False
    ):
        raise ValueError("runtime_policy_invalid")


def render(bundle: Path) -> str:
    return "\n".join(
        [
            'sandbox_mode = "read-only"',
            'approval_policy = "never"',
            'web_search = "disabled"',
            "[features]",
            "plugins = false",
            "hooks = false",
            "[apps._default]",
            "enabled = false",
            "[mcp_servers.jarvis_control]",
            'command = "/usr/bin/python3"',
            "args = "
            + json.dumps([str(bundle / "plugins/jarvis-system-admin/scripts/mcp_server.py")]),
            "required = true",
            "[mcp_servers.jarvis_control.env]",
            "JARVIS_STORE = " + json.dumps(str(bundle / "runtime/control-store")),
            "",
            f'[projects."{bundle}"]',
            'trust_level = "trusted"',
            "",
        ]
    )


def validate_effective(value: dict[str, Any], bundle: Path, scope_id: str) -> None:
    config = value.get("config")
    if not isinstance(config, dict):
        raise ValueError("effective_config_unavailable")
    candidate = dict(config)
    servers = candidate.get("mcp_servers", {})
    server = servers.get("jarvis_control", {})
    expected = [
        str(bundle / "plugins/jarvis-system-admin/scripts/mcp_server.py"),
        "--scope-id",
        scope_id,
    ]
    if server.get("args") != expected:
        raise ValueError("effective_mcp_identity_mismatch")
    if server.get("enabled") is not True or server.get("environment_id") not in {None, "local"}:
        raise ValueError("effective_mcp_transport_mismatch")
    timeout = server.get("tool_timeout_sec")
    if timeout is not None and (not isinstance(timeout, (int, float)) or not 0 < timeout <= 120):
        raise ValueError("effective_mcp_timeout_invalid")
    normalized = {
        key: item
        for key, item in server.items()
        if key not in {"enabled", "environment_id", "tool_timeout_sec"}
    }
    candidate["mcp_servers"] = {**servers, "jarvis_control": {**normalized, "args": expected[:1]}}
    validate(candidate, bundle)
