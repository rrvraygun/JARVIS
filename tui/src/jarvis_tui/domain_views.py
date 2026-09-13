"""On-demand domain evidence and exact operation review, outside Conversation."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from .terminal_safety import sanitize_and_redact_terminal_text


def inspect_domain(bundle: Path, domain: str) -> dict[str, Any]:
    mapping = {
        "health": ("health_tools", "health_inventory"),
        "development": ("health_tools", "development_toolchains"),
        "network": ("extended_tools", "network_inventory"),
        "security": ("extended_tools", "security_inventory"),
        "recovery": ("extended_tools", "recovery_inventory"),
    }
    module, function = mapping[domain]
    spec = importlib.util.spec_from_file_location(
        "jarvis_domain_" + module, bundle / "plugins/jarvis-system-admin/scripts" / f"{module}.py"
    )
    if spec is None or spec.loader is None:
        raise ValueError("collector_unavailable")
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return getattr(loaded, function)()


class OperationReview(ModalScreen[str | None]):
    CSS = """
    OperationReview { align: center middle; }
    #operation-review { width: 92%; height: 90%; border: thick $warning; padding: 1 2; }
    #operation-decisions { height: 3; }
    """

    def __init__(self, proposal: dict[str, Any]):
        super().__init__()
        self.proposal = proposal

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="operation-review"):
            yield Label("Review exact operation")
            fields = (
                "domain",
                "operation",
                "execution_mode",
                "target",
                "desired",
                "pre_state",
                "destination",
                "cwd",
                "argv",
                "effective_command",
                "executable",
                "file_identities",
                "file_metadata",
                "source_operation",
                "privileged_request",
                "url",
                "checksum",
                "crates",
                "environment",
                "network",
                "privilege",
                "expected_effect",
                "rollback",
                "isolation",
                "resource_limits",
                "postconditions",
                "blockers",
                "digest",
                "expires_at",
            )
            review = {key: self.proposal[key] for key in fields if key in self.proposal}
            if self.proposal.get("pre_state", {}).get("ports"):
                review["firewall_ports"] = self.proposal["pre_state"]["ports"]
            if "source_tree" in self.proposal:
                tree = self.proposal["source_tree"]
                review["source_snapshot"] = {
                    "files": len(tree["files"]),
                    "bytes": tree["bytes"],
                    "digest": tree["digest"],
                    "omitted": tree["omitted"],
                }
            if "diff" in self.proposal:
                review["exact_diff"] = self.proposal["diff"]
            safe, truncated = sanitize_and_redact_terminal_text(
                json.dumps(review, indent=2, ensure_ascii=False), 64000
            )
            yield Static(safe, markup=False)
            if truncated:
                self.proposal["blockers"] = [
                    *self.proposal["blockers"],
                    "review_not_fully_displayed",
                ]
            with Horizontal(id="operation-decisions"):
                yield Button(
                    "Approve once",
                    id="operation-approve",
                    variant="warning",
                    disabled=bool(self.proposal["blockers"]),
                )
                yield Button("Decline", id="operation-decline")
        self.call_after_refresh(self.query_one, "#operation-decline", Button)

    def on_mount(self) -> None:
        self.query_one("#operation-decline", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "operation-approve" and not self.proposal["blockers"]:
            self.dismiss(self.proposal["digest"])
        elif event.button.id == "operation-decline":
            self.dismiss(None)
