"""Fixture-only App Server implementation for broker tests."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from typing import Any

from .app_server import AppServerError


class FakeAppServerClient:
    def __init__(self, responses: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self._running = False
        self._responses: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for method, values in (responses or {}).items():
            self._responses[method].extend(values)
        self._events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
        self.requests: list[tuple[str, dict[str, Any]]] = []
        self.notifications: list[tuple[str, dict[str, Any]]] = []
        self.responses: list[tuple[str | int, dict[str, Any]]] = []

    @property
    def running(self) -> bool:
        return self._running

    async def start(self) -> dict[str, Any]:
        if self._running:
            raise AppServerError("fake server already running")
        self._running = True
        return {"serverInfo": {"name": "fixture", "version": "0"}}

    async def stop(self) -> None:
        if self._running:
            self._running = False
            await self._events.put(None)

    async def request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self.requests.append((method, dict(params or {})))
        if not self._responses[method]:
            raise AppServerError(f"no fixture response for {method}")
        return self._responses[method].pop(0)

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self.notifications.append((method, dict(params or {})))

    async def respond(self, request_id: str | int, result: dict[str, Any]) -> None:
        self.responses.append((request_id, dict(result)))

    async def emit(self, message: dict[str, Any]) -> None:
        await self._events.put(message)

    async def events(self) -> AsyncIterator[dict[str, Any]]:
        while self._running or not self._events.empty():
            message = await self._events.get()
            if message is None:
                return
            yield message
