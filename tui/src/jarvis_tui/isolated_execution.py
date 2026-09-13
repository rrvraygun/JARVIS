"""Read-only settlement proof from the trusted pre-sandbox launcher."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import private_records


def settled(
    root: Path, plan: dict[str, Any], *, cgroup_root: Path = Path("/sys/fs/cgroup")
) -> bool:
    if plan.get("settlement_version") != 1:
        return False
    try:
        private_records.read(root / "launches", plan["id"] + ".json")
    except FileNotFoundError:
        # An outcome without any launch request proves a pre-launch refusal.
        try:
            result = private_records.read(root / "results", plan["id"] + ".json")
            return bool(result.get("id") == plan["id"] and result.get("digest") == plan["digest"])
        except (OSError, ValueError):
            return False
    try:
        receipt = private_records.read(root / "starts", plan["id"] + ".json")
        name = receipt["cgroup"]
        if (
            receipt["id"] != plan["id"]
            or receipt["digest"] != plan["digest"]
            or not isinstance(name, str)
            or not name.startswith("/")
            or ".." in Path(name).parts
            or not name.endswith("/" + plan["unit"] + ".service")
        ):
            return False
        if receipt["boot_id"] != Path("/proc/sys/kernel/random/boot_id").read_text().strip():
            return True
        group = cgroup_root / name.lstrip("/")
        try:
            info = group.stat()
        except FileNotFoundError:
            return True
        if [info.st_dev, info.st_ino] != receipt["identity"]:
            return False
        fields = dict(line.split() for line in (group / "cgroup.events").read_text().splitlines())
        return fields.get("populated") == "0"
    except (OSError, ValueError, KeyError, TypeError):
        return False
