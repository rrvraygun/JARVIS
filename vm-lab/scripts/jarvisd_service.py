#!/usr/bin/env python3
"""Bounded user-scoped Jarvis H1 JSONL service.

The service exposes only the reviewed Unix-socket methods. It has no shell,
subprocess, network, privilege, device, or arbitrary-dispatch interface. The
observation method remains fail-closed while the repository policies are
disabled; enabling it requires a separate activation revision and review.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import struct
import time
from pathlib import Path
from typing import Any

import activation_authority as authority
import live_lighting_observation as live_lighting
import live_tier0_observation as live

MAX_FRAME_BYTES = 65536
METHODS = (
    "health.read",
    "activation.status",
    "observation.prepare",
    "observation.stop",
    "lighting.observe",
)


class JarvisdError(ValueError):
    pass


def _request_id(value: Any) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 128
        or any(ord(c) < 0x20 for c in value)
    ):
        raise JarvisdError("invalid request_id")
    return value


def _authorization(value: Any) -> authority.UserAuthorization:
    if not isinstance(value, dict) or set(value) != set(
        authority.UserAuthorization.__dataclass_fields__
    ):
        raise JarvisdError("authorization fields are invalid")
    try:
        result = authority.UserAuthorization(
            authorization_id=value["authorization_id"],
            request_id=value["request_id"],
            proposal_digest=value["proposal_digest"],
            source_catalog_digest=value["source_catalog_digest"],
            scope_digest=value["scope_digest"],
            attestation_digest=value["attestation_digest"],
            approved_group_ids=tuple(value["approved_group_ids"]),
            approved_fact_ids=tuple(value["approved_fact_ids"]),
            decision_digest=value["decision_digest"],
            idempotency_key=value["idempotency_key"],
            expires_at=value["expires_at"],
        )
        authority.validate_authorization(result)
        return result
    except (KeyError, TypeError, ValueError, authority.AuthorizationError) as exc:
        raise JarvisdError("authorization is invalid") from exc


def _policy_status(project_root: Path) -> dict[str, Any]:
    policy_path = project_root / "controller" / "policy.json"
    broker_path = project_root / "observation" / "broker-policy.json"
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        broker = json.loads(broker_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise JarvisdError("policy state unavailable") from exc
    return {
        "controller_host_observation_enabled": policy.get("host_observation_enabled") is True,
        "broker_host_observation_enabled": broker.get("host_observation_enabled") is True,
        "service_uid": os.getuid(),
        "live_observation_performed": False,
    }


def handle_request(
    request: Any,
    *,
    project_root: Path,
    ledger_path: Path,
    deadline: float | None = None,
) -> dict[str, Any]:
    if not isinstance(request, dict) or "method" not in request or "request_id" not in request:
        raise JarvisdError("request envelope is invalid")
    method = request["method"]
    request_id = _request_id(request["request_id"])
    if method not in METHODS:
        raise JarvisdError("method is not registered")
    if method in {"health.read", "activation.status", "observation.stop"} and set(request) != {
        "method",
        "request_id",
    }:
        raise JarvisdError("unexpected request fields")
    if method == "health.read":
        return {
            "schema_version": 1,
            "request_id": request_id,
            "status": "ok",
            "service": "jarvisd-user-service-v1",
        }
    if method == "activation.status":
        return {
            "schema_version": 1,
            "request_id": request_id,
            "status": "ok",
            "activation": _policy_status(project_root),
        }
    if method == "observation.stop":
        return {
            "schema_version": 1,
            "request_id": request_id,
            "status": "not_running",
            "live_observation_performed": False,
        }
    if method == "lighting.observe":
        if set(request) != {
            "method",
            "request_id",
            "authorization_id",
            "authorization",
            "include_graphics",
        }:
            raise JarvisdError("lighting.observe fields are invalid")
        authorization_id = request["authorization_id"]
        expected = _authorization(request["authorization"])
        if expected.authorization_id != authorization_id:
            raise JarvisdError("lighting authorization identity mismatch")
        if expected.request_id != request_id:
            raise JarvisdError("lighting authorization request identity mismatch")
        if type(request["include_graphics"]) is not bool:
            raise JarvisdError("include_graphics must be boolean")
        if deadline is not None and time.monotonic() >= deadline:
            raise JarvisdError("request deadline exceeded")
        try:
            ledger = authority.ActivationAuthorityLedger(ledger_path)
        except authority.AuthorizationError as exc:
            raise JarvisdError("lighting.observe failed closed") from exc
        try:
            result = live_lighting.collect_lighting(
                ledger,
                authorization_id,
                expected_authorization=expected,
                project_root=project_root,
                include_graphics=request["include_graphics"],
                deadline=deadline,
            )
        except (
            authority.AuthorizationError,
            live_lighting.LiveLightingObservationError,
        ) as exc:
            raise JarvisdError("lighting.observe failed closed") from exc
        finally:
            ledger.close()
        return {"schema_version": 1, "request_id": request_id, **result}
    if set(request) != {"method", "request_id", "authorization_id", "authorization"}:
        raise JarvisdError("observation.prepare fields are invalid")
    authorization_id = request["authorization_id"]
    expected = _authorization(request["authorization"])
    if expected.authorization_id != authorization_id:
        raise JarvisdError("authorization identity mismatch")
    if expected.request_id != request_id:
        raise JarvisdError("authorization request identity mismatch")
    if deadline is not None and time.monotonic() >= deadline:
        raise JarvisdError("request deadline exceeded")
    try:
        ledger = authority.ActivationAuthorityLedger(ledger_path)
    except authority.AuthorizationError as exc:
        raise JarvisdError("observation.prepare failed closed") from exc
    try:
        result = live.collect_tier0(
            ledger,
            authorization_id,
            expected_authorization=expected,
            project_root=project_root,
            deadline=deadline,
        )
    except (authority.AuthorizationError, live.LiveObservationError) as exc:
        raise JarvisdError("observation.prepare failed closed") from exc
    finally:
        ledger.close()
    return {"schema_version": 1, "request_id": request_id, **result}


def _serve_client(client: socket.socket, *, project_root: Path, ledger_path: Path) -> None:
    with client:
        try:
            peer = client.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
            _, peer_uid, _ = struct.unpack("3i", peer)
        except (AttributeError, OSError, struct.error):
            return
        if peer_uid != os.getuid():
            return
        deadline = time.monotonic() + 5.0
        buffer = b""
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            client.settimeout(remaining)
            try:
                block = client.recv(65536)
            except TimeoutError:
                return
            if not block:
                return
            buffer += block
            while b"\n" in buffer:
                if time.monotonic() >= deadline:
                    return
                raw, buffer = buffer.split(b"\n", 1)
                if not raw:
                    continue
                if len(raw) > MAX_FRAME_BYTES:
                    return
                try:
                    response = handle_request(
                        json.loads(raw.decode("utf-8")),
                        project_root=project_root,
                        ledger_path=ledger_path,
                        deadline=deadline,
                    )
                except (UnicodeDecodeError, json.JSONDecodeError, JarvisdError) as exc:
                    response = {
                        "schema_version": 1,
                        "status": "error",
                        "error": str(exc),
                    }
                encoded = (
                    json.dumps(
                        response,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                    ).encode()
                    + b"\n"
                )
                if len(encoded) > MAX_FRAME_BYTES:
                    return
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return
                client.settimeout(remaining)
                try:
                    client.sendall(encoded)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
            if len(buffer) > MAX_FRAME_BYTES:
                return


def serve(socket_path: Path, *, project_root: Path, ledger_path: Path) -> None:
    if not socket_path.is_absolute() or socket_path.exists():
        raise JarvisdError("socket path must be absolute and unused")
    parent = socket_path.parent
    parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent_stat = parent.stat()
    if parent_stat.st_uid != os.getuid() or stat.S_IMODE(parent_stat.st_mode) & 0o077:
        raise JarvisdError("socket parent is not owner-controlled")
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        server.bind(str(socket_path))
        os.chmod(socket_path, 0o600)
        server.listen(4)
        while True:
            client, _ = server.accept()
            _serve_client(client, project_root=project_root, ledger_path=ledger_path)
    finally:
        server.close()
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--socket", required=True, type=Path)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--ledger", required=True, type=Path)
    args = parser.parse_args()
    serve(args.socket, project_root=args.project_root, ledger_path=args.ledger)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
