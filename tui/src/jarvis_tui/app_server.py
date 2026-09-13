"""Codex App Server transport for the policy-governed Jarvis broker.

The transport implements account, thread, turn, and exact server-request
response surfaces. Tool authority is selected explicitly per turn.
"""

from __future__ import annotations

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4


class AppServerError(RuntimeError):
    pass


class AppServerMethodDenied(AppServerError):
    pass


ALLOWED_REQUEST_METHODS = frozenset(
    {
        "config/read",
        "initialize",
        "account/read",
        "account/login/start",
        "account/login/cancel",
        "account/rateLimits/read",
        "thread/start",
        "thread/resume",
        "thread/inject_items",
        "turn/start",
        "turn/interrupt",
    }
)
ALLOWED_NOTIFICATION_METHODS = frozenset({"initialized"})
APP_SERVER_ENVIRONMENT_KEYS = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "SHELL",
        "TERM",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "NO_COLOR",
        "TMPDIR",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_RUNTIME_DIR",
        "XDG_STATE_HOME",
        "CODEX_HOME",
        "CODEX_API_KEY",
        "OPENAI_API_KEY",
        "OPENAI_BASE_URL",
        "OPENAI_ORGANIZATION",
        "OPENAI_PROJECT",
    }
)
MAX_PROTOCOL_LINE_BYTES = 128 * 1024
MAX_PROTOCOL_NESTING = 32
MAX_PROTOCOL_VALUES = 10_000
MAX_EVENT_QUEUE = 256


class AppServerClient(Protocol):
    """Protocol used by the session controller and its fixture client."""

    @property
    def running(self) -> bool: ...

    async def start(self) -> dict[str, Any]: ...

    async def stop(self) -> None: ...

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any: ...

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None: ...

    async def respond(self, request_id: str | int, result: dict[str, Any]) -> None: ...

    def events(self) -> AsyncIterator[dict[str, Any]]: ...


def app_server_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Pass only explicitly required process settings to Codex.

    Authentication values may be present in this mapping, but are never logged
    or persisted.  Unrelated host environment values are not an App Server
    capability and therefore must not cross this process boundary.
    """
    values = source if source is not None else os.environ
    return {
        key: value
        for key, value in values.items()
        if key in APP_SERVER_ENVIRONMENT_KEYS and isinstance(value, str)
    }


def _within_protocol_limits(value: object) -> bool:
    """Reject oversized or pathologically nested protocol values before use."""
    pending: list[tuple[object, int]] = [(value, 0)]
    seen = 0
    while pending:
        current, depth = pending.pop()
        seen += 1
        if seen > MAX_PROTOCOL_VALUES or depth > MAX_PROTOCOL_NESTING:
            return False
        if isinstance(current, dict):
            if len(current) > MAX_PROTOCOL_VALUES:
                return False
            pending.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            if len(current) > MAX_PROTOCOL_VALUES:
                return False
            pending.extend((item, depth + 1) for item in current)
        elif (
            isinstance(current, str)
            and len(current.encode("utf-8", "replace")) > MAX_PROTOCOL_LINE_BYTES
        ):
            return False
    return True


# Compatibility alias for callers from the former subscription-only transport.
subscription_environment = app_server_environment


def subscription_account_status(result: dict[str, Any]) -> dict[str, Any]:
    """Classify supported ChatGPT and API-key App Server authentication."""
    account = result.get("account")
    if account is None:
        return {"state": "login_required", "auth_mode": None, "plan_type": None}
    auth_mode = account.get("type")
    if auth_mode not in {"chatgpt", "apiKey", "apikey"}:
        return {
            "state": "unsupported_auth_mode",
            "auth_mode": auth_mode,
            "plan_type": account.get("planType"),
        }
    return {
        "state": "ready",
        "auth_mode": "apiKey" if auth_mode in {"apiKey", "apikey"} else "chatgpt",
        "plan_type": account.get("planType"),
    }


def _check_method(method: str, allowed: frozenset[str]) -> None:
    if method not in allowed:
        raise AppServerMethodDenied(f"App Server method is outside the Phase 1 allowlist: {method}")


class StdioAppServerClient:
    """Timeout-bounded JSON-RPC client for a broker-owned App Server child."""

    def __init__(
        self,
        codex_bin: str = "codex",
        request_timeout: float = 60.0,
        codex_home: Path | None = None,
    ) -> None:
        self.scope_id = uuid4().hex
        self.codex_home = codex_home
        self.codex_bin = codex_bin
        self.request_timeout = request_timeout
        self.process: asyncio.subprocess.Process | None = None
        self._next_id = 1
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._events: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=MAX_EVENT_QUEUE)
        self._reader_task: asyncio.Task[None] | None = None
        self._stderr_task: asyncio.Task[None] | None = None
        self._request_lock = asyncio.Lock()

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.returncode is None

    async def start(self) -> dict[str, Any]:
        if self.running:
            raise AppServerError("App Server is already running")
        environment = app_server_environment()
        if self.codex_home is not None:
            environment["CODEX_HOME"] = str(self.codex_home)
        overrides: list[str] = []
        if self.codex_home is not None:
            from .runtime_profile import check

            bundle = self.codex_home.parent.parent
            check(bundle)
            server = bundle / "plugins/jarvis-system-admin/scripts/mcp_server.py"
            overrides = [
                "-c",
                'sandbox_mode="read-only"',
                "-c",
                'approval_policy="never"',
                "-c",
                'mcp_servers.jarvis_control.command="/usr/bin/python3"',
                "-c",
                "mcp_servers.jarvis_control.args="
                + json.dumps([str(server), "--scope-id", self.scope_id]),
            ]
        if self.codex_home is not None:
            overrides.extend(
                [
                    "-c",
                    "features.plugins=false",
                    "-c",
                    "features.hooks=false",
                    "-c",
                    "apps._default.enabled=false",
                    "-c",
                    'web_search="disabled"',
                ]
            )
        self.process = await asyncio.create_subprocess_exec(
            self.codex_bin,
            "app-server",
            *overrides,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=environment,
            cwd=str(self.codex_home.parent.parent) if self.codex_home is not None else None,
            limit=MAX_PROTOCOL_LINE_BYTES,
        )
        self._reader_task = asyncio.create_task(self._read_loop())
        self._stderr_task = asyncio.create_task(self._stderr_loop())
        try:
            result = await self.request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "jarvis_tui",
                        "title": "Jarvis Terminal Interface",
                        "version": "0.7.0-dev",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            await self.notify("initialized", {})
            if self.codex_home is not None:
                from .runtime_profile import validate_effective

                effective = await self.request("config/read", {"includeLayers": False})
                validate_effective(effective, self.codex_home.parent.parent, self.scope_id)
            if not isinstance(result, dict):
                raise AppServerError("App Server initialize result is invalid")
            return result
        except Exception:
            await self.stop()
            raise

    async def stop(self) -> None:
        process = self.process
        if process is None:
            return
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except TimeoutError:
                process.kill()
                await process.wait()
        for task in (self._reader_task, self._stderr_task):
            if task and not task.done():
                task.cancel()
            if task:
                with suppress(asyncio.CancelledError):
                    await task
        self.process = None
        self._reader_task = None
        self._stderr_task = None

    async def _read_loop(self) -> None:
        assert self.process and self.process.stdout
        while True:
            try:
                line = await self.process.stdout.readline()
            except ValueError:
                await self._events.put(
                    {
                        "method": "jarvis/protocolError",
                        "params": {"reason": "line_too_large"},
                    }
                )
                break
            if not line:
                break
            if len(line) > MAX_PROTOCOL_LINE_BYTES:
                await self._events.put(
                    {
                        "method": "jarvis/protocolError",
                        "params": {"reason": "line_too_large"},
                    }
                )
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                await self._events.put(
                    {
                        "method": "jarvis/protocolError",
                        "params": {"reason": "invalid_json"},
                    }
                )
                continue
            if not isinstance(message, dict) or not _within_protocol_limits(message):
                await self._events.put(
                    {
                        "method": "jarvis/protocolError",
                        "params": {"reason": "message_limits_exceeded"},
                    }
                )
                continue
            if "method" in message:
                await self._events.put(message)
                continue
            identifier = message.get("id")
            if not isinstance(identifier, int):
                await self._events.put(
                    {
                        "method": "jarvis/protocolError",
                        "params": {"reason": "unknown_response_id"},
                    }
                )
                continue
            future = self._pending.pop(identifier, None)
            if future is None:
                await self._events.put(
                    {
                        "method": "jarvis/protocolError",
                        "params": {"reason": "unknown_response_id"},
                    }
                )
            elif "error" in message:
                if not future.done():
                    future.set_exception(AppServerError(str(message["error"])))
            else:
                if not future.done():
                    future.set_result(message.get("result", {}))
        failure = AppServerError("App Server stream closed")
        for future in self._pending.values():
            if not future.done():
                future.set_exception(failure)
        self._pending.clear()
        await self._events.put({"method": "jarvis/disconnected", "params": {}})

    async def _stderr_loop(self) -> None:
        assert self.process and self.process.stderr
        while line := await self.process.stderr.readline():
            # Stderr is diagnostic display data only. The reducer sanitizes it
            # and the event journal records only its digest and length.
            message = line.decode(errors="replace").rstrip()[:4096]
            if message:
                await self._events.put(
                    {"method": "jarvis/appServerStderr", "params": {"message": message}}
                )

    async def _write(self, message: dict[str, Any]) -> None:
        if not self.process or not self.process.stdin or not self.running:
            raise AppServerError("App Server is not running")
        self.process.stdin.write(json.dumps(message, separators=(",", ":")).encode() + b"\n")
        await self.process.stdin.drain()

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        _check_method(method, ALLOWED_REQUEST_METHODS)
        # Codex serializes some lifecycle operations internally. Serializing
        # client requests prevents a timed-out stale lifecycle call from
        # queueing a second thread operation behind it.
        async with self._request_lock:
            identifier = self._next_id
            self._next_id += 1
            future = asyncio.get_running_loop().create_future()
            self._pending[identifier] = future
            try:
                await self._write({"method": method, "id": identifier, "params": params or {}})
                timeout = (
                    min(self.request_timeout, 20.0)
                    if method in {"thread/start", "thread/resume"}
                    else self.request_timeout
                )
                return await asyncio.wait_for(future, timeout=timeout)
            except TimeoutError as exc:
                self._pending.pop(identifier, None)
                raise AppServerError(f"App Server request timed out: {method}") from exc
            except Exception:
                self._pending.pop(identifier, None)
                raise

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        _check_method(method, ALLOWED_NOTIFICATION_METHODS)
        await self._write({"method": method, "params": params or {}})

    async def respond(self, request_id: str | int, result: dict[str, Any]) -> None:
        """Answer one App Server-originated JSON-RPC request."""
        if not isinstance(request_id, (str, int)) or request_id == "":
            raise ValueError("server request id is required")
        if not isinstance(result, dict):
            raise TypeError("server response result must be an object")
        await self._write({"id": request_id, "result": result})

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while self.running or not self._events.empty():
            event = await self._events.get()
            yield event
            if event.get("method") == "jarvis/disconnected":
                return

    async def account(self) -> dict[str, Any]:
        result = await self.request("account/read", {"refreshToken": False})
        if not isinstance(result, dict):
            raise AppServerError("App Server account result is invalid")
        return result

    async def start_chatgpt_login(self) -> dict[str, Any]:
        result = await self.request(
            "account/login/start",
            {
                "type": "chatgpt",
                "useHostedLoginSuccessPage": True,
                "appBrand": "chatgpt",
            },
        )
        if not isinstance(result, dict):
            raise AppServerError("App Server login result is invalid")
        return result

    async def rate_limits(self) -> dict[str, Any]:
        result = await self.request("account/rateLimits/read", {})
        if not isinstance(result, dict):
            raise AppServerError("App Server rate-limit result is invalid")
        return result


def turn_start_request(
    thread_id: str,
    text: str,
    cwd: Path,
    *,
    sandbox_policy: dict[str, Any],
    approval_policy: str | dict[str, Any],
    request_id: int = 1,
    output_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a turn with caller-selected, visible authority."""
    params: dict[str, Any] = {
        "threadId": thread_id,
        "input": [{"type": "text", "text": text}],
        "cwd": str(cwd.resolve()),
        "approvalPolicy": approval_policy,
        "sandboxPolicy": sandbox_policy,
    }
    if output_schema is not None:
        params["outputSchema"] = output_schema
    return {
        "method": "turn/start",
        "id": request_id,
        "params": params,
    }
