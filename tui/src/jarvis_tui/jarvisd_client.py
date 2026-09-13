"""Read-only client for the bounded Jarvis H1 user service."""

from __future__ import annotations

import json
import os
import socket
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MAX_FRAME_BYTES = 65_536
DEFAULT_TIMEOUT = 2.0


class JarvisdClientError(RuntimeError):
    """Raised when the private Jarvis status transport is unavailable/invalid."""


@dataclass(frozen=True)
class JarvisdStatus:
    state: str
    service: str
    controller_observation: bool
    broker_observation: bool
    live_observation_performed: bool
    service_uid: int | None

    @property
    def host_authority(self) -> str:
        if self.controller_observation and self.broker_observation:
            return "H1 Tier-0 read-only enabled"
        return "disabled"

    def to_display(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "service": self.service,
            "controller_observation": self.controller_observation,
            "broker_observation": self.broker_observation,
            "live_observation_performed": self.live_observation_performed,
            "service_uid": self.service_uid,
            "host_authority": self.host_authority,
        }


class JarvisdStatusClient:
    """Only calls health.read and activation.status; it cannot observe or mutate."""

    ALLOWED_METHODS = frozenset({"health.read", "activation.status"})

    def __init__(
        self, socket_path: Path | None = None, *, timeout: float = DEFAULT_TIMEOUT
    ) -> None:
        runtime = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        self.socket_path = (socket_path or Path(runtime) / "jarvis" / "jarvisd.sock").resolve()
        self.timeout = max(0.1, min(float(timeout), 5.0))

    def read_status(self) -> JarvisdStatus:
        self._check_socket()
        health = self._request("health.read", "tui-health")
        if health.get("status") != "ok" or health.get("service") != "jarvisd-user-service-v1":
            raise JarvisdClientError("jarvisd health response is invalid")
        activation = self._request("activation.status", "tui-activation-status")
        if activation.get("status") != "ok":
            raise JarvisdClientError("jarvisd activation response is invalid")
        value = activation.get("activation")
        if not isinstance(value, dict):
            raise JarvisdClientError("jarvisd activation projection is invalid")
        booleans = (
            "controller_host_observation_enabled",
            "broker_host_observation_enabled",
            "live_observation_performed",
        )
        if any(type(value.get(key)) is not bool for key in booleans):
            raise JarvisdClientError("jarvisd activation flags are invalid")
        uid = value.get("service_uid")
        if type(uid) is not int or uid != os.getuid():
            raise JarvisdClientError("jarvisd service identity is invalid")
        return JarvisdStatus(
            state="available",
            service=str(health["service"]),
            controller_observation=value[booleans[0]],
            broker_observation=value[booleans[1]],
            live_observation_performed=value[booleans[2]],
            service_uid=uid,
        )

    def _check_socket(self) -> None:
        try:
            parent = self.socket_path.parent.lstat()
            target = self.socket_path.lstat()
        except OSError as exc:
            raise JarvisdClientError("jarvisd socket is unavailable") from exc
        if (
            not stat.S_ISDIR(parent.st_mode)
            or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) & 0o077
            or not stat.S_ISSOCK(target.st_mode)
            or target.st_uid != os.getuid()
            or stat.S_IMODE(target.st_mode) != 0o600
        ):
            raise JarvisdClientError("jarvisd socket is not owner-only")

    def _request(self, method: str, request_id: str) -> dict[str, Any]:
        if method not in self.ALLOWED_METHODS:
            raise JarvisdClientError("jarvisd method is not allowed")
        request = (
            json.dumps({"method": method, "request_id": request_id}, separators=(",", ":")) + "\n"
        ).encode()
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect(str(self.socket_path))
            sock.sendall(request)
            response = bytearray()
            while len(response) <= MAX_FRAME_BYTES:
                block = sock.recv(65_536)
                if not block:
                    break
                response.extend(block)
                if b"\n" in response:
                    line = bytes(response).split(b"\n", 1)[0]
                    if len(line) > MAX_FRAME_BYTES:
                        raise JarvisdClientError("jarvisd response exceeds bound")
                    value = json.loads(line.decode("utf-8"))
                    if not isinstance(value, dict) or value.get("request_id") != request_id:
                        raise JarvisdClientError("jarvisd response identity is invalid")
                    return value
            raise JarvisdClientError("jarvisd response is incomplete")
        except JarvisdClientError:
            raise
        except (TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JarvisdClientError("jarvisd status transport failed") from exc
        finally:
            sock.close()
