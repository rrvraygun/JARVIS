"""Small one-attempt boundary for blocking work outside the asyncio loop."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Literal, TypeVar

T = TypeVar("T")


class BlockingOperationOutcomePending(RuntimeError):
    """An irreversible worker outlived bounded cancellation settlement."""


async def run_blocking_once(
    function: Callable[..., T],
    *args: object,
    thread_name: str = "jarvis-blocking-operation",
    call_kwargs: dict[str, object] | None = None,
    cancellation: Literal["detach", "settle"] = "detach",
    settle_timeout_seconds: float = 30.0,
) -> T:
    """Run one callable in a daemon thread and settle on the owning loop.

    This is an `asyncio.to_thread()` equivalent that does not install or shut
    down the loop's shared default executor. Cancellation never retries or
    starts a replacement operation. Use ``settle`` for irreversible work:
    cancellation then waits for the authoritative outcome rather than
    abandoning a still-running mutation. Settlement is bounded: if a worker
    outlives it, callers must report an indeterminate/outcome-pending state.
    """

    completed = threading.Event()
    outcome: list[tuple[bool, object]] = []

    def run() -> None:
        try:
            result = function(*args, **(call_kwargs or {}))
        except BaseException as exc:
            outcome.append((False, exc))
        else:
            outcome.append((True, result))
        finally:
            completed.set()

    threading.Thread(target=run, name=thread_name, daemon=True).start()
    try:
        while not completed.is_set():
            await asyncio.sleep(0.005)
    except asyncio.CancelledError:
        if cancellation == "detach":
            raise
        deadline = asyncio.get_running_loop().time() + settle_timeout_seconds
        while not completed.is_set():
            if asyncio.get_running_loop().time() >= deadline:
                raise BlockingOperationOutcomePending("blocking operation outcome is pending")
            try:
                await asyncio.sleep(
                    min(0.005, max(0.0, deadline - asyncio.get_running_loop().time()))
                )
            except asyncio.CancelledError:
                continue
    succeeded, value = outcome[0]
    if not succeeded:
        raise value  # type: ignore[misc]
    return value  # type: ignore[return-value]
