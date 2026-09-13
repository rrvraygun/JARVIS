"""Unprivileged service preview and hash-bound fixed-helper client."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

HELPER = Path("/usr/libexec/jarvis-service-control")


def module(bundle: Path) -> Any:
    path = bundle / "vm-lab/scripts/jarvis_service_control.py"
    spec = importlib.util.spec_from_file_location("jarvis_service_contract", path)
    if spec is None or spec.loader is None:
        raise ValueError("service_contract_unavailable")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


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
                (bundle / "vm-lab/scripts/jarvis_service_control.py").read_bytes()
            ).digest()
        )
    except OSError:
        return False


def prepare(bundle: Path, operation: str, unit: str) -> dict[str, Any]:
    api = module(bundle)
    api.valid_unit(unit)
    blockers = []
    try:
        state = api.observe(unit)
    except (OSError, ValueError, subprocess.SubprocessError):
        state = {}
        blockers.append("fresh_service_state_unavailable")
    try:
        policy = api.policy_for(unit)
    except (OSError, ValueError):
        policy = {}
        blockers.append("reviewed_unit_and_recovery_not_enrolled")
    if not helper_matches(bundle):
        blockers.append("reviewed_service_helper_not_installed")
    if operation not in policy.get("operations", []):
        blockers.append("service_operation_not_enrolled")
    return {
        "pre_state": state,
        "service_policy": policy,
        "pre_state_digest": api.binding(state),
        "service_policy_digest": api.binding(policy),
        "blockers": blockers,
    }


def apply(bundle: Path, plan: dict[str, Any]) -> dict[str, Any]:
    if not helper_matches(bundle):
        raise ValueError("service_helper_drift")
    current = prepare(bundle, plan["operation"], plan["target"])
    if (
        current["blockers"]
        or current["pre_state_digest"] != plan["pre_state_digest"]
        or current["service_policy_digest"] != plan["service_policy_digest"]
    ):
        raise ValueError("service_preview_drift")
    request = {
        "id": plan["id"],
        "operation": plan["operation"],
        "unit": plan["target"],
        "pre_state_digest": plan["pre_state_digest"],
        "policy_digest": plan["service_policy_digest"],
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
        raise ValueError("service_outcome_indeterminate")
    value = json.loads(result.stdout)
    if not isinstance(value, dict) or value.get("id") != plan["id"]:
        raise ValueError("service_result_binding_invalid")
    return value
