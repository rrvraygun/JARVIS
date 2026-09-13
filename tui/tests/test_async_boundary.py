from __future__ import annotations

import asyncio
import threading
import unittest
from pathlib import Path
import sys

TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.async_boundary import (  # noqa: E402
    BlockingOperationOutcomePending,
    run_blocking_once,
)


class BlockingBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_settle_cancellation_waits_for_the_started_operation(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def operation() -> str:
            started.set()
            release.wait(timeout=1)
            return "verified"

        task = asyncio.create_task(run_blocking_once(operation, cancellation="settle"))
        while not started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        asyncio.get_running_loop().call_later(0.01, release.set)
        self.assertEqual(await task, "verified")

    async def test_default_cancellation_does_not_claim_to_stop_the_worker(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def operation() -> None:
            started.set()
            release.wait(timeout=1)

        task = asyncio.create_task(run_blocking_once(operation))
        while not started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        release.set()

    async def test_settle_timeout_reports_an_indeterminate_outcome(self) -> None:
        started = threading.Event()
        release = threading.Event()

        def operation() -> None:
            started.set()
            release.wait(timeout=1)

        task = asyncio.create_task(
            run_blocking_once(operation, cancellation="settle", settle_timeout_seconds=0.01)
        )
        while not started.is_set():
            await asyncio.sleep(0.001)
        task.cancel()
        with self.assertRaises(BlockingOperationOutcomePending):
            await task
        release.set()


if __name__ == "__main__":
    unittest.main()
