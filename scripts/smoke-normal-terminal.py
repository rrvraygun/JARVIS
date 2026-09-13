#!/usr/bin/env python3
"""Visible TUI smoke: fixtures plus exactly one harmless printf, no model/root."""
# ruff: noqa: E402

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tui/src"))

from jarvis_tui.actions import ActionRegistry
from jarvis_tui.app import JarvisTui
from jarvis_tui.broker import JarvisBroker
from jarvis_tui.event_store import EventJournal
from jarvis_tui.normal_terminal import NormalTerminalWorkflow, available
from jarvis_tui.operation_workflow import OperationWorkflow
from jarvis_tui.session import AppServerSessionController
from jarvis_tui.testing import FakeAppServerClient
from textual.widgets import Input, TabbedContent


class FixtureControl:
    def capabilities(self):
        return ()

    def knowledge_status(self):
        return {"available": False, "read_only": True}

    def query_knowledge(self, *args, **kwargs):
        return ()


async def smoke(output: Path) -> None:
    if not available():
        raise RuntimeError("Run this smoke from a real terminal or PTY.")
    with tempfile.TemporaryDirectory(prefix="jarvis-visible-smoke-") as tmp:
        fixture = Path(tmp)
        project = fixture / "project"
        project.mkdir(mode=0o700)
        (project / "Cargo.toml").write_text('[package]\nname="smoke"\nversion="0.1.0"\n')
        registry = ActionRegistry.load(ROOT / "plugins/jarvis-system-admin/registry/actions.json")
        broker = JarvisBroker(
            registry, EventJournal(fixture / "events.jsonl"), local_control=FixtureControl()
        )
        client = FakeAppServerClient()
        session = AppServerSessionController(client, broker, ROOT, live_turns_enabled=False)
        app = JarvisTui(
            ROOT, broker=broker, session=session, conversation_storage=fixture / "conversations"
        )
        app.operation_workflow = OperationWorkflow(fixture)
        app.normal_terminal_workflow = NormalTerminalWorkflow(fixture)
        proposal = app.operation_workflow.propose(
            "development",
            "command",
            str(project),
            {"argv": ["/usr/bin/printf", "JARVIS_NORMAL_TERMINAL_OK\\n"]},
        )
        async with app.run_test(headless=False, size=(110, 35)) as pilot:
            app.query_one(TabbedContent).active = "development-pane"
            app.query_one("#domain-operation-development", Input).value = proposal["id"]
            await pilot.pause()
            await pilot.click("#domain-terminal-development")
            await pilot.pause()
            normal = app.screen.proposal
            assert normal["execution_mode"] == "normal-terminal"
            assert normal["digest"] != proposal["digest"]
            app.save_screenshot("terminal-review.svg", str(output))
            await pilot.click("#operation-approve")
            await app.workers.wait_for_complete()
            await pilot.pause()
            result_path = app.normal_terminal_workflow.root / "results" / (normal["id"] + ".json")
            result = json.loads(result_path.read_text())
            assert result["exit_code"] == 0 and result["attempts"] == 1
            assert result["execution_mode"] == "normal-terminal"
            assert not client.requests
            app.save_screenshot("terminal-result.svg", str(output))
            (output / "terminal-result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("JARVIS_VISIBLE_SMOKE_PASSED " + str(output))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--approve-printf-smoke",
        action="store_true",
        help="Approve only the fixed harmless printf in this fixture session.",
    )
    args = parser.parse_args()
    if not args.approve_printf_smoke:
        parser.error("This test requires explicit --approve-printf-smoke.")
    evidence_root = ROOT / "runtime" / "validation"
    evidence_root.mkdir(parents=True, exist_ok=True)
    target = Path(tempfile.mkdtemp(prefix="visible-", dir=evidence_root))
    asyncio.run(smoke(target))
