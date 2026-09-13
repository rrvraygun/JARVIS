#!/usr/bin/env python3
"""Perform the exact, one-use H1 Tier-0 activation transaction.

This is the only reviewed promotion helper. It installs a user service,
promotes the four approved read-only adapters, records one expiring durable
authorization, and performs one bounded observation through the private socket.
It has no shell, sudo, network, arbitrary command, or retry path.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import socket
import stat
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import activation_authority as authority
import h1_activation_contract as contract


class ActivationError(RuntimeError):
    pass


EXPECTED_CONTROLLER_SHA256 = contract.TRUSTED_CONTROLLER_POLICY_SHA256
EXPECTED_BROKER_SHA256 = contract.TRUSTED_BROKER_POLICY_SHA256
EXPECTED_REGISTRY_SHA256 = "b39caa670af7b3c59fdb2005cf39a1c99e04bb8fc58287008ca6115d765659b8"
EXPECTED_UNIT_SHA256 = contract.TRUSTED_UNIT_SHA256
MAX_FRAME_BYTES = 65536
SOCKET_TIMEOUT = 5.0
SYSTEMCTL = "/usr/bin/systemctl"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ActivationError(f"invalid activation artifact: {path}") from exc
    if not isinstance(value, dict):
        raise ActivationError(f"activation artifact is not an object: {path}")
    return value


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    encoded = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode(
        "utf-8"
    )
    _atomic_bytes(path, encoded)


def _atomic_bytes(path: Path, encoded: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _install_noreplace(path: Path, encoded: bytes) -> None:
    """Atomically create a new file, failing if the destination exists."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temporary, 0o600)
    try:
        os.link(temporary, path, follow_symlinks=False)
    except OSError as exc:
        raise ActivationError(
            "user unit destination appeared or cannot be installed atomically"
        ) from exc
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
    directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(directory_fd)
    except OSError:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise
    finally:
        os.close(directory_fd)


def _systemctl(*arguments: str) -> None:
    command = [SYSTEMCTL, "--user", *arguments]
    try:
        completed = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ActivationError("systemd-user command failed to execute") from exc
    if completed.returncode != 0:
        raise ActivationError(f"systemd-user command failed: {arguments[0]}")


def _request(socket_path: Path, request: dict[str, Any]) -> dict[str, Any]:
    raw = (
        json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n"
    ).encode("utf-8")
    if len(raw) > MAX_FRAME_BYTES:
        raise ActivationError("activation request exceeds frame bound")
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(SOCKET_TIMEOUT)
    try:
        client.connect(str(socket_path))
        client.sendall(raw)
        response = bytearray()
        while len(response) <= MAX_FRAME_BYTES:
            block = client.recv(65536)
            if not block:
                break
            response.extend(block)
            if b"\n" in response:
                line = bytes(response).split(b"\n", 1)[0]
                if len(line) > MAX_FRAME_BYTES:
                    raise ActivationError("activation response exceeds frame bound")
                value = json.loads(line.decode("utf-8"))
                if not isinstance(value, dict):
                    raise ActivationError("activation response is not an object")
                return value
        raise ActivationError("activation response was incomplete or oversized")
    except (TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ActivationError("private activation transport failed") from exc
    finally:
        client.close()


def _verify_socket(socket_path: Path) -> None:
    deadline = time.monotonic() + SOCKET_TIMEOUT
    while True:
        try:
            value = socket_path.lstat()
        except FileNotFoundError:
            if time.monotonic() < deadline:
                time.sleep(0.05)
                continue
            raise ActivationError("Jarvis socket was not created")
        except OSError as exc:
            raise ActivationError("Jarvis socket could not be inspected") from exc
        if (
            not stat.S_ISSOCK(value.st_mode)
            or value.st_uid != os.getuid()
            or stat.S_IMODE(value.st_mode) != 0o600
        ):
            raise ActivationError("Jarvis socket is not owner-only")
        return


def _enabled_controller(current: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(current))
    value.update(
        {
            "implementation_status": "h1_tier0_enabled",
            "transport": "unix-user-private",
            "service_process_exists": True,
            "operational_authority": True,
            "host_observation_enabled": True,
        }
    )
    value["current_capabilities"] = ["bounded_tier0_read_only_observation"]
    value["activation_gate"].update(
        {
            "current_activation_authorized": True,
            "new_security_review_required": False,
            "new_user_decision_required": False,
        }
    )
    return value


def _enabled_broker(current: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(current))
    value.update(
        {
            "implementation_status": "tier0_live_read_enabled",
            "host_observation_enabled": True,
        }
    )
    value["current_capabilities"] = [
        "validate_registered_adapters",
        "collect_bounded_tier0_host_facts",
        "emit_ephemeral_candidate_facts",
    ]
    value["activation_gate"].update(
        {
            "live_collector_implemented": True,
            "host_read_authority_granted": True,
            "new_security_review_required": False,
            "new_user_decision_required": False,
        }
    )
    return value


def _enabled_registry(current: dict[str, Any]) -> dict[str, Any]:
    value = json.loads(json.dumps(current))
    value["implementation_status"] = "tier0_live_read_enabled"
    value["host_observation_enabled"] = True
    return value


def _authorization(
    decision: dict[str, Any],
    scope: dict[str, Any],
    authorization_id: str,
    request_id: str,
    expires_at: str,
) -> authority.UserAuthorization:
    facts = tuple(sorted({fact_id for entry in scope["entries"] for fact_id in entry["fact_ids"]}))
    result = authority.UserAuthorization(
        authorization_id=authorization_id,
        request_id=request_id,
        proposal_digest=decision["decision_scope"]["proposal_digest"],
        source_catalog_digest=decision["decision_scope"]["source_catalog_digest"],
        scope_digest=decision["decision_scope"]["scope_digest"],
        attestation_digest=decision["decision_scope"]["attestation_digest"],
        approved_group_ids=tuple(sorted(decision["decision_scope"]["approved_groups"])),
        approved_fact_ids=facts,
        decision_digest=decision["decision_digest"],
        idempotency_key=f"h1-tier0-{authorization_id}",
        expires_at=expires_at,
    )
    authority.validate_authorization(result)
    return result


def activate(
    root: Path, *, authorization_id: str, request_id: str, ttl_seconds: int
) -> dict[str, Any]:
    if root.resolve() != Path(contract.TRUSTED_PROJECT_ROOT):
        raise ActivationError("activation root is not the trusted checkout")
    vm_root = root / "vm-lab"
    contract.validate_prepared_promotion(vm_root)
    controller_path = vm_root / "controller" / "policy.json"
    broker_path = vm_root / "observation" / "broker-policy.json"
    registry_path = vm_root / "observation" / "adapter-registry.json"
    unit_source = vm_root / "controller" / "jarvisd.service.template"
    if (
        _digest(controller_path) != EXPECTED_CONTROLLER_SHA256
        or _digest(broker_path) != EXPECTED_BROKER_SHA256
    ):
        raise ActivationError("current disabled policy digests do not match the reviewed packet")
    if (
        _digest(registry_path) != EXPECTED_REGISTRY_SHA256
        or _digest(unit_source) != EXPECTED_UNIT_SHA256
    ):
        raise ActivationError("registry or unit artifact drifted")
    original_controller_bytes = controller_path.read_bytes()
    original_broker_bytes = broker_path.read_bytes()
    original_registry_bytes = registry_path.read_bytes()
    current_controller = json.loads(original_controller_bytes)
    current_broker = json.loads(original_broker_bytes)
    current_registry = json.loads(original_registry_bytes)
    decision = _read_json(root / "runtime" / "reports" / "2026-08-07-h1-user-decision-packet.json")
    scope = _read_json(vm_root / "enrollment" / "tier0-approved-fact-scope.json")
    expires_at = (
        (dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=ttl_seconds))
        .isoformat()
        .replace("+00:00", "Z")
    )
    user_authorization = _authorization(decision, scope, authorization_id, request_id, expires_at)
    unit_destination = Path.home() / ".config" / "systemd" / "user" / "jarvisd.service"
    ledger_path = Path.home() / ".local" / "state" / "jarvis" / "activation.sqlite3"
    socket_path = (
        Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
        / "jarvis"
        / "jarvisd.sock"
    )
    unit_destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if unit_destination.exists():
        raise ActivationError("jarvisd user unit already exists")
    if socket_path.exists():
        raise ActivationError("Jarvis socket path is already occupied")
    promotion_started = False
    consumed = False
    ledger_recorded = False
    try:
        _install_noreplace(unit_destination, unit_source.read_bytes())
        _systemctl("daemon-reload")
        _systemctl("start", "jarvisd.service")
        _verify_socket(socket_path)
        health = _request(
            socket_path, {"method": "health.read", "request_id": "h1-health-pre-enable"}
        )
        if health.get("status") != "ok":
            raise ActivationError("jarvisd health check failed")
        promotion_started = True
        _atomic_json(controller_path, _enabled_controller(current_controller))
        _atomic_json(broker_path, _enabled_broker(current_broker))
        _atomic_json(registry_path, _enabled_registry(current_registry))
        ledger_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(ledger_path.parent, 0o700)
        ledger = authority.ActivationAuthorityLedger(ledger_path)
        try:
            ledger.record(user_authorization)
            ledger_recorded = True
        finally:
            ledger.close()
        result = _request(
            socket_path,
            {
                "method": "observation.prepare",
                "request_id": request_id,
                "authorization_id": authorization_id,
                "authorization": user_authorization.document(),
            },
        )
        consumed = result.get("authorization_ledger_mutated") is True
        if (
            result.get("status") != "host_observed_tier0"
            or result.get("fact_persistence_performed") is not False
        ):
            raise ActivationError("Tier-0 observation did not return the exact success boundary")
        return {
            "status": "h1_tier0_activated",
            "authorization_id": authorization_id,
            "request_id": request_id,
            "fact_count": len(result.get("facts", [])),
            "service": health.get("service"),
            "policy_changed": True,
            "authorization_consumed": True,
        }
    except Exception as exc:
        rollback_errors: list[str] = []
        if ledger_recorded and not consumed:
            try:
                rollback_ledger = authority.ActivationAuthorityLedger(ledger_path)
                try:
                    consumed = rollback_ledger.is_consumed(
                        authorization_id, expected=user_authorization
                    )
                    if not consumed:
                        rollback_ledger.revoke_unconsumed(
                            authorization_id, expected=user_authorization
                        )
                finally:
                    rollback_ledger.close()
            except authority.AuthorizationError as rollback_exc:
                rollback_errors.append(f"revoke authorization: {rollback_exc}")
        if promotion_started:
            for path, original in (
                (controller_path, original_controller_bytes),
                (broker_path, original_broker_bytes),
                (registry_path, original_registry_bytes),
            ):
                try:
                    _atomic_bytes(path, original)
                except OSError as rollback_exc:
                    rollback_errors.append(f"restore {path.name}: {rollback_exc}")
        try:
            _systemctl("stop", "jarvisd.service")
        except ActivationError as rollback_exc:
            rollback_errors.append(f"stop service: {rollback_exc}")
        try:
            if unit_destination.exists():
                unit_destination.unlink()
            _systemctl("daemon-reload")
        except (OSError, ActivationError) as rollback_exc:
            rollback_errors.append(f"remove unit: {rollback_exc}")
        if rollback_errors:
            raise ActivationError(
                "activation failed and rollback was incomplete: " + "; ".join(rollback_errors)
            ) from exc
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--request-id", required=True)
    parser.add_argument("--ttl-seconds", type=int, default=300)
    args = parser.parse_args()
    if args.ttl_seconds < 60 or args.ttl_seconds > 900:
        raise SystemExit("ttl-seconds must be between 60 and 900")
    print(
        json.dumps(
            activate(
                args.root.resolve(),
                authorization_id=args.authorization_id,
                request_id=args.request_id,
                ttl_seconds=args.ttl_seconds,
            ),
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
