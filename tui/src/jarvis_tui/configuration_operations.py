"""Typed previews and fixed-helper client for narrow configuration operations."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

HELPER = Path("/usr/libexec/jarvis-configuration-control")


def module(bundle: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "jarvis_configuration_contract", bundle / "vm-lab/scripts/jarvis_configuration_control.py"
    )
    if spec is None or spec.loader is None:
        raise ValueError("configuration_contract_unavailable")
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def helper_matches(bundle: Path) -> bool:
    try:
        info = HELPER.lstat()
        return (
            stat.S_ISREG(info.st_mode)
            and info.st_uid == 0
            and not info.st_mode & 0o022
            and info.st_size <= 65536
            and os.access(HELPER, os.X_OK)
            and hashlib.sha256(HELPER.read_bytes()).digest()
            == hashlib.sha256(
                (bundle / "vm-lab/scripts/jarvis_configuration_control.py").read_bytes()
            ).digest()
        )
    except OSError:
        return False


def prepare(bundle: Path, adapter: str, target: str, desired: Any) -> dict[str, Any]:
    api = module(bundle)
    api.validate(adapter, target, desired)
    blockers = []
    try:
        state = api.observe(adapter, target, desired)
    except (OSError, ValueError, subprocess.SubprocessError):
        state = {}
        blockers.append("fresh_configuration_state_unavailable")
    try:
        policy = api.enrollment(adapter, target)
    except (OSError, ValueError):
        policy = {}
        blockers.append("target_and_recovery_not_enrolled")
    if not helper_matches(bundle):
        blockers.append("reviewed_configuration_helper_not_installed")
    if desired not in policy.get("allowed_values", []):
        blockers.append("exact_configuration_value_not_enrolled")
    return {
        "pre_state": state,
        "configuration_policy": policy,
        "pre_state_digest": api.digest(state),
        "configuration_policy_digest": api.digest(policy),
        "blockers": blockers,
        "adapter": adapter,
        "desired": desired,
        "effective_command": api.command(adapter, target, desired),
    }


def apply(bundle: Path, plan: dict[str, Any]) -> dict[str, Any]:
    if not helper_matches(bundle):
        raise ValueError("configuration_helper_drift")
    preview = prepare(bundle, plan["adapter"], plan["target"], plan["desired"])
    if (
        preview["blockers"]
        or preview["pre_state_digest"] != plan["pre_state_digest"]
        or preview["configuration_policy_digest"] != plan["configuration_policy_digest"]
    ):
        raise ValueError("configuration_preview_drift")
    request = {
        "id": plan["id"],
        "adapter": plan["adapter"],
        "target": plan["target"],
        "desired": plan["desired"],
        "pre_state_digest": plan["pre_state_digest"],
        "policy_digest": plan["configuration_policy_digest"],
    }
    result = subprocess.run(
        ["/usr/bin/pkexec", str(HELPER)],
        input=json.dumps(request),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=45,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
    if result.returncode != 0 or len(result.stdout) > 8192:
        raise ValueError("configuration_outcome_indeterminate")
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or any(
        value.get(key) != request[key] for key in ("id", "adapter", "target", "desired")
    ):
        raise ValueError("configuration_result_binding_invalid")
    return value
