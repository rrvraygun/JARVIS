"""Hash-matched root-helper bridge; root review is required separately."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import stat
import subprocess
from pathlib import Path
from typing import Any

FILES = {
    "boot": ("jarvis_boot_control.py", "/usr/libexec/jarvis-boot-control"),
    "update": ("jarvis_update_control.py", "/usr/libexec/jarvis-update-control"),
}


def contract(bundle: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "jarvis_privileged_contract", bundle / "vm-lab/scripts/jarvis_privileged_control.py"
    )
    if spec is None or spec.loader is None:
        raise ValueError("privileged_contract_unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def matches(bundle: Path, kind: str) -> bool:
    names = [
        FILES[kind],
        ("jarvis_privileged_control.py", "/usr/libexec/jarvis_privileged_control.py"),
    ]
    try:
        for source, installed in names:
            path = Path(installed)
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != 0
                or info.st_mode & 0o022
                or info.st_nlink != 1
                or info.st_size > 1048576
                or hashlib.sha256(path.read_bytes()).digest()
                != hashlib.sha256((bundle / "vm-lab/scripts" / source).read_bytes()).digest()
            ):
                return False
        policy_name = "org.jarvis." + kind + "-control.policy"
        policy = Path("/usr/share/polkit-1/actions") / policy_name
        info = policy.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != 0
            or info.st_mode & 0o022
            or info.st_nlink != 1
            or info.st_size > 65536
            or policy.read_bytes() != (bundle / "deployment/host" / policy_name).read_bytes()
        ):
            return False
        return os.access(FILES[kind][1], os.X_OK)
    except OSError:
        return False


def prepare(bundle: Path, operation: str, target: str, request: dict[str, Any]) -> dict[str, Any]:
    kind = "boot" if operation == "boot" else "update"
    api = contract(bundle)
    api.validate(request, kind)
    if (kind == "boot" and request["kernel"] != target) or (
        kind == "update" and target != "system"
    ):
        raise ValueError("privileged_target_mismatch")
    return {
        "privileged_kind": kind,
        "privileged_request": request,
        "argv": ["/usr/bin/pkexec", "--disable-internal-agent", FILES[kind][1]],
        "request_digest": api.digest(request),
        "blockers": [] if matches(bundle, kind) else ["reviewed_privileged_helper_not_installed"],
    }


def apply(bundle: Path, plan: dict[str, Any]) -> dict[str, Any]:
    kind = plan["privileged_kind"]
    api = contract(bundle)
    request = plan["privileged_request"]
    api.validate(request, kind)
    if not matches(bundle, kind) or api.digest(request) != plan["request_digest"]:
        raise ValueError("privileged_helper_or_request_drift")
    # Only the root-owned helper handles stdin. Authentication belongs to Polkit;
    # no credential is requested or captured here. Output is a bounded root receipt.
    result = subprocess.run(
        ["/usr/bin/pkexec", "--disable-internal-agent", FILES[kind][1]],
        input=json.dumps(request),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        timeout=700,
        check=False,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
    )
    if result.returncode != 0 or len(result.stdout) > 65536:
        raise ValueError("privileged_outcome_requires_reconciliation")
    receipt = json.loads(result.stdout)
    if (
        not isinstance(receipt, dict)
        or receipt.get("id") != request["id"]
        or receipt.get("request_digest") != plan["request_digest"]
        or receipt.get("kind") != kind
    ):
        raise ValueError("privileged_receipt_mismatch")
    return {"status": "root_command_requires_verification", "root_receipt": receipt}
