"""Durable, digest-bound records for verified Power profile applications."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RESULT_VERSION = 1
RESULT_STATUSES = ("applied", "failed", "indeterminate")


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PowerProfileApplicationRecord:
    profile_id: str
    profile_name: str
    goal: str
    selected_variant: str
    profile_digest: str
    transaction_timestamp: str
    pre_activation: dict[str, Any]
    requested: dict[str, str]
    resulting: dict[str, Any]
    changed: dict[str, dict[str, Any]]
    unchanged: tuple[dict[str, Any], ...] = ()
    skipped: tuple[dict[str, Any], ...] = ()
    status: str = "indeterminate"
    recovery: dict[str, Any] | None = None
    schema_version: int = RESULT_VERSION
    record_digest: str = ""

    def binding_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "profile_name": self.profile_name,
            "goal": self.goal,
            "selected_variant": self.selected_variant,
            "profile_digest": self.profile_digest,
            "transaction_timestamp": self.transaction_timestamp,
            "pre_activation": self.pre_activation,
            "requested": self.requested,
            "resulting": self.resulting,
            "changed": self.changed,
            "unchanged": self.unchanged,
            "skipped": self.skipped,
            "status": self.status,
            "recovery": self.recovery,
        }

    def __post_init__(self) -> None:
        if (
            self.schema_version != RESULT_VERSION
            or not self.profile_id
            or self.selected_variant not in {"ac", "battery"}
            or self.status not in RESULT_STATUSES
            or not self.profile_digest
            or not isinstance(self.pre_activation, dict)
            or not isinstance(self.requested, dict)
            or not isinstance(self.resulting, dict)
        ):
            raise ValueError("invalid power profile application record")
        expected = _digest(self.binding_payload())
        if not self.record_digest:
            object.__setattr__(self, "record_digest", expected)
        elif self.record_digest != expected:
            raise ValueError("power profile application record digest mismatch")

    @classmethod
    def from_transaction(
        cls,
        *,
        profile: Any,
        variant: str,
        pre_activation: dict[str, Any],
        requested: dict[str, str],
        result: dict[str, Any] | None,
        skipped: tuple[dict[str, Any], ...] = (),
        status: str = "applied",
        recovery: dict[str, Any] | None = None,
    ) -> "PowerProfileApplicationRecord":
        resulting = dict((result or {}).get("post_state", {})) if result else {}
        changed: dict[str, dict[str, Any]] = {}
        unchanged: list[dict[str, Any]] = []
        for control, target in requested.items():
            before = pre_activation.get(control)
            after = resulting.get(control)
            item = {"control": control, "before": before, "requested": target, "after": after}
            if before == after:
                unchanged.append(item)
            else:
                changed[control] = item
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return cls(
            profile_id=profile.profile_id,
            profile_name=profile.name,
            goal=profile.goal,
            selected_variant=variant,
            profile_digest=profile.profile_digest,
            transaction_timestamp=timestamp,
            pre_activation=dict(pre_activation),
            requested=dict(requested),
            resulting=resulting,
            changed=changed,
            unchanged=tuple(unchanged),
            skipped=tuple(skipped),
            status=status,
            recovery=recovery,
        )

    def to_dict(self) -> dict[str, Any]:
        return {**self.binding_payload(), "record_digest": self.record_digest}


class PowerProfileApplicationStore:
    """Atomic owner-only storage for the latest valid result per profile."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path.home() / ".local/state/jarvis/power-profiles"

    def save(self, record: PowerProfileApplicationRecord) -> Path:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.root, 0o700)
        target = self.root / f"{record.profile_id}.application.json"
        fd, name = tempfile.mkstemp(prefix=".application.", suffix=".tmp", dir=self.root)
        temporary = Path(name)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                fd = -1
                json.dump(record.to_dict(), stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            os.chmod(target, 0o600)
        finally:
            if fd >= 0:
                os.close(fd)
            temporary.unlink(missing_ok=True)
        return target

    def _load_path(self, path: Path) -> PowerProfileApplicationRecord | None:
        try:
            if path.is_symlink() or path.stat().st_size > 256_000:
                return None
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                return None
            record = PowerProfileApplicationRecord(
                profile_id=str(value["profile_id"]),
                profile_name=str(value["profile_name"]),
                goal=str(value["goal"]),
                selected_variant=str(value["selected_variant"]),
                profile_digest=str(value["profile_digest"]),
                transaction_timestamp=str(value["transaction_timestamp"]),
                pre_activation=dict(value["pre_activation"]),
                requested={str(k): str(v) for k, v in value["requested"].items()},
                resulting=dict(value["resulting"]),
                changed={str(k): dict(v) for k, v in value["changed"].items()},
                unchanged=tuple(dict(v) for v in value.get("unchanged", ())),
                skipped=tuple(dict(v) for v in value.get("skipped", ())),
                status=str(value["status"]),
                recovery=dict(value["recovery"])
                if isinstance(value.get("recovery"), dict)
                else None,
                schema_version=int(value.get("schema_version", 0)),
                record_digest=str(value.get("record_digest", "")),
            )
            # If the corresponding profile still exists, bind restoration to
            # its current digest as well as to the record's own digest.
            profile_path = self.root / f"{record.profile_id}.json"
            if profile_path.is_file():
                profile = json.loads(profile_path.read_text(encoding="utf-8"))
                binding = {
                    key: profile[key]
                    for key in (
                        "schema_version",
                        "profile_id",
                        "name",
                        "goal",
                        "variants",
                        "version",
                    )
                }
                if _digest(binding) != record.profile_digest:
                    return None
            return record
        except (OSError, TypeError, ValueError, KeyError, json.JSONDecodeError):
            return None

    def load(self, profile_id: str) -> PowerProfileApplicationRecord | None:
        return self._load_path(self.root / f"{profile_id}.application.json")

    def load_latest(self) -> PowerProfileApplicationRecord | None:
        try:
            paths = self.root.glob("*.application.json")
        except OSError:
            return None
        records = [record for path in paths if (record := self._load_path(path)) is not None]
        return max(records, key=lambda record: record.transaction_timestamp, default=None)

    def load_latest_applied(self) -> PowerProfileApplicationRecord | None:
        records = []
        try:
            paths = self.root.glob("*.application.json")
        except OSError:
            return None
        for path in paths:
            record = self._load_path(path)
            if record is not None and record.status == "applied":
                records.append(record)
        return max(records, key=lambda record: record.transaction_timestamp, default=None)
