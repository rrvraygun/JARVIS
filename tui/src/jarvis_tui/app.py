"""Textual interface for the policy-governed Jarvis broker."""

from __future__ import annotations

import asyncio
import copy
import difflib
import hashlib
import json
import re
import webbrowser
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    ContentSwitcher,
    DataTable,
    Footer,
    Header,
    Input,
    Label,
    RichLog,
    Select,
    Static,
    TabbedContent,
    TabPane,
    TextArea,
)

from .actions import ActionRegistry
from .agent_coordinator import AgentCoordinator
from .agent_registry import AgentRegistry
from .app_server import AppServerError, StdioAppServerClient
from .async_boundary import run_blocking_once
from .broker import JarvisBroker
from .checkpoint_recovery import recovery_binding
from .conversation_checkpoints import ConversationCheckpoint, ConversationCheckpointStore
from .conversation_manager import Conversation, ConversationManager, ConversationStorageError
from .domain_clean import fields as clean_domain_fields
from .domain_views import OperationReview, inspect_domain
from .event_reducer import NormalizedEvent
from .event_store import EventJournal
from .jarvisd_client import JarvisdStatusClient
from .lighting_controls import (
    COLORS,
    EFFECTS,
    LightingControlError,
    LightingSelection,
    apply_driver_selection,
    driver_available,
    preview_driver_argv,
)
from .lighting_widgets import LightingRangeControl
from .live_activity import LiveActivity
from .local_control import ReadOnlyLocalControl
from .models import (
    ActionDefinition,
    AdmissionRoute,
    AssessmentDecision,
    ExecutionRoute,
    IntentAssessment,
    IntentClass,
    TaskRecord,
    TaskState,
)
from .normal_terminal import NormalTerminalWorkflow
from .operation_workflow import OperationWorkflow
from .package_control_client import (
    PackageControlClientError,
    apply_transaction,
    archive_transaction,
    authoritative_status,
    remove_transaction,
    undo_transaction,
)
from .package_control_client import helper_available as package_helper_available
from .package_control_client import (
    helper_matches_bundle as package_helper_matches_bundle,
)
from .package_inventory import (
    PackagePreviewError,
    PackageRecord,
    RepositoryPackageRecord,
    advisories,
    dnf_history,
    enrich_package,
    package_documentation,
    package_view,
    page_records,
    recommend_cached_packages,
    relationship_queries,
    repository_origins,
    scan_available_cached,
    scan_rpm,
)
from .power_control_client import (
    POWER_CONTROL_OPTIONS,
    PowerControlClientError,
    apply_change,
    apply_profile_transaction,
    authoritative_undo_status,
    helper_available,
    undo_last,
)
from .power_inventory import (
    PowerInventory,
    PowerSetting,
    PowerTelemetry,
    scan_power_inventory,
    scan_power_telemetry,
)
from .power_profile_results import (
    PowerProfileApplicationRecord,
    PowerProfileApplicationStore,
)
from .power_profiles import (
    PROFILE_GOALS,
    PowerProfile,
    PowerProfilePlan,
    PowerProfileStore,
    plan_power_profile,
)
from .preflight import PreflightClassifierError
from .presentation import ConversationEntry, JarvisPresentation
from .session import (
    JARVIS_ALLOWED_CONTEXT,
    JARVIS_ALLOWED_MODELS,
    JARVIS_ALLOWED_REASONING,
    JARVIS_CONTEXT_OPTIONS,
    JARVIS_MODEL_OPTIONS,
    JARVIS_REASONING_OPTIONS,
    AppServerSessionController,
    ConnectionState,
    ConversationContextSyncError,
    execution_policy,
)
from .specialists import Specialist
from .terminal_safety import sanitize_terminal_text

VIEW_IDS = {
    "system": "system-pane",
    "overview": "overview-pane",
    "conversation": "conversation-pane",
    "agents": "agents-pane",
    "lighting": "lighting-pane",
    "power": "power-pane",
    "timeline": "timeline-pane",
    "operations": "operations-pane",
    "packages": "packages-pane",
}

_POWER_EXPERT_TERMS = (
    "power",
    "battery",
    "performance",
    "thermal",
    "quiet",
    "energy",
    "cpu",
    "turbo",
    "tuned",
    "power-profiles",
    "profile",
    "governor",
    "frequency",
    "suspend",
    "hibernate",
    "gpu",
)


def _is_power_expert_request(text: str | None) -> bool:
    """Route Power-domain requests to the selected expert without choosing intent."""
    lowered = (text or "").casefold()
    return any(term in lowered for term in _POWER_EXPERT_TERMS)


KNOWLEDGE_KINDS = ("facts", "sources", "attempts", "errors", "lessons", "decisions")


def _package_preview_diagnostic(exc: BaseException) -> tuple[str, str]:
    """Return a stable, content-free reason for a rejected DNF simulation."""
    if isinstance(exc, PackagePreviewError):
        return exc.code, exc.safe_message
    if isinstance(exc, PermissionError):
        return (
            "package_preview.protected_target",
            "The resolved transaction includes a protected or boot-critical package.",
        )
    if isinstance(exc, TimeoutError):
        return (
            "package_preview.timeout",
            "The cache-only transaction simulation exceeded its time limit.",
        )
    text = str(exc).casefold()
    if "strictly additive" in text or "removing or replacing" in text:
        return (
            "package_preview.non_additive_effect",
            "The install preview would also change existing package versions or remove packages.",
        )
    if "pre-state" in text or "restored exactly" in text:
        return (
            "package_preview.prestate_unbound",
            "The current RPM state cannot be bound for exact recovery.",
        )
    if "exceeded" in text:
        return (
            "package_preview.bound_exceeded",
            "The resolved transaction exceeded a safety limit.",
        )
    if "resolve" in text or "summary" in text:
        return (
            "package_preview.dnf_unresolved",
            "DNF could not resolve a bounded cache-only transaction from current metadata.",
        )
    if "local control adapter" in text or "preview is unavailable" in text:
        return (
            "package_preview.adapter_unavailable",
            "The local package-preview adapter is unavailable in this TUI process.",
        )
    if isinstance(exc, OSError):
        return (
            "package_preview.local_io_failure",
            "A local package-preview input could not be read safely.",
        )
    return (
        f"package_preview.{type(exc).__name__.casefold()}",
        "A local package-preview component stopped before any package was changed.",
    )


def _package_execution_diagnostic(exc: BaseException) -> tuple[bool, str, str]:
    """Classify known helper refusals without overstating mutation uncertainty."""
    text = str(exc).casefold()
    if "authenticated desktop caller identity is unavailable" in text:
        return (
            False,
            "package_helper.caller_identity_unavailable",
            "The package helper could not verify the authenticated desktop caller; no package operation ran.",
        )
    if "package preview changed" in text or "preview digest changed" in text:
        return (
            False,
            "package_helper.preview_digest_changed",
            "The helper's second DNF preview differed from the approved preview; no package was changed.",
        )
    if "resolved installation set is incomplete" in text:
        detail = str(exc).split("; ", 1)[1][:300] if "; " in str(exc) else ""
        return (
            False,
            "package_helper.install_set_incomplete",
            "The helper could not bind every package resolved by DNF; no package was changed."
            + (f" Helper evidence: {detail}." if detail else ""),
        )
    if "resolved removal set is incomplete" in text:
        return (
            False,
            "package_helper.remove_set_incomplete",
            "The helper could not bind every package resolved for removal; no package was changed.",
        )
    if "package transaction can no longer be resolved" in text:
        return (
            False,
            "package_helper.transaction_unresolved",
            "The helper could not resolve the bounded DNF transaction; no package was changed.",
        )
    if "package state or preview digest changed" in text:
        return (
            False,
            "package_helper.state_changed",
            "The package state changed after approval; no package was changed by this attempt.",
        )
    if "resolved installation is not strictly additive" in text:
        detail = str(exc).split("; ", 1)[1][:300] if "; " in str(exc) else ""
        return (
            False,
            "package_helper.non_additive_install",
            "The resolved installation would also replace or remove existing packages; no package was changed."
            + (f" Helper evidence: {detail}." if detail else ""),
        )
    if "already awaiting rollback" in text:
        return (
            False,
            "package_helper.recovery_record_pending",
            "No new package operation ran because an earlier package recovery record is pending. "
            "Use Packages → Undo last transaction or Archive rollback record to resolve it with a fresh approval.",
        )
    return (
        True,
        "package_helper.outcome_indeterminate",
        "The approved package transaction started but its final state could not be verified; "
        "the outcome is indeterminate. "
        "Inspect the authoritative package recovery status before approving another transaction.",
    )


def _package_rollback_diagnostic(exc: BaseException) -> tuple[bool, str, str]:
    """Distinguish a safe rollback precondition refusal from an unknown outcome."""
    text = str(exc).casefold()
    if (
        "rollback removal would affect packages outside the recorded set" in text
        or "package restore would affect packages outside the recorded set" in text
    ):
        return (
            False,
            "package_rollback.scope_changed",
            "No package rollback ran because the recorded transaction would now affect packages "
            "outside its original set. The recovery record remains available for review.",
        )
    if "prepared package record may reflect a partial mutation" in text:
        return (
            False,
            "package_rollback.partial_state_requires_manual_recovery",
            "No package rollback ran because the prepared record may reflect a partial mutation. "
            "Manual recovery inspection is required.",
        )
    return (
        True,
        "package_rollback.outcome_indeterminate",
        "Package rollback started but its final state is indeterminate; inspect authoritative recovery "
        "status before any further package mutation.",
    )


class ActionFormScreen(ModalScreen[dict[str, Any] | None]):
    """Schema-generated action form with no authority of its own."""

    CSS = """
    ActionFormScreen { align: center middle; }
    #action-form {
        width: 90%; max-width: 72; height: 90%; max-height: 36;
        border: thick $primary; padding: 1 2; background: $surface;
    }
    #action-fields { height: 1fr; }
    .field-label { margin-top: 1; }
    #form-buttons { height: auto; margin-top: 1; }
    #form-buttons Button { margin-right: 1; }
    """

    def __init__(self, action: ActionDefinition) -> None:
        super().__init__()
        self.action_definition = action
        self.fields: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        action = self.action_definition
        required = set(action.input_schema.get("required", []))
        properties = action.input_schema.get("properties", {})
        with Vertical(id="action-form"):
            yield Label(
                f"{action.title}\n{action.summary}\n"
                f"mode={action.mode.value} · risk floor={action.risk_floor} · "
                f"host mutation={str(action.mutates_host).lower()}"
            )
            with VerticalScroll(id="action-fields"):
                for index, (name, rule) in enumerate(properties.items()):
                    field_id = f"parameter-{index}"
                    self.fields[field_id] = name
                    marker = "required" if name in required else "optional"
                    choices = rule.get("enum")
                    hint = f" — one of: {', '.join(choices)}" if choices else ""
                    yield Label(f"{name} ({marker}){hint}", classes="field-label")
                    yield Input(value=str(rule.get("default", "")), id=field_id)
            with Horizontal(id="form-buttons"):
                yield Button("Submit request", id="submit-action", variant="primary")
                yield Button("Cancel", id="cancel-action")

    def _parse_value(self, rule: dict[str, Any], value: str) -> Any:
        expected = rule.get("type")
        if expected == "boolean":
            lowered = value.casefold()
            if lowered not in {"true", "false"}:
                raise ValueError("expected true or false")
            return lowered == "true"
        if expected == "integer":
            return int(value)
        if expected == "number":
            return float(value)
        return value

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "cancel-action":
            self.dismiss(None)
            return
        if event.button.id != "submit-action":
            return
        required = set(self.action_definition.input_schema.get("required", []))
        properties = self.action_definition.input_schema.get("properties", {})
        parameters: dict[str, Any] = {}
        try:
            for field_id, name in self.fields.items():
                value = self.query_one(f"#{field_id}", Input).value.strip()
                if not value and name not in required:
                    continue
                if not value:
                    raise ValueError(f"{name} is required")
                parameters[name] = self._parse_value(properties[name], value)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.dismiss(parameters)


class PowerChangeReviewScreen(ModalScreen[bool | None]):
    """Two-step review for one exact power mutation or undo."""

    CSS = """
    PowerChangeReviewScreen { align: center middle; }
    #power-change-review {
        width: 88%; max-width: 78; height: auto;
        border: thick $warning; padding: 1 2; background: $surface;
    }
    #power-change-title { text-style: bold; color: $warning; margin-bottom: 1; }
    #power-change-buttons { height: auto; margin-top: 1; }
    #power-change-buttons Button { margin-right: 1; }
    """

    def __init__(self, *, title: str, details: str, confirm_label: str) -> None:
        super().__init__()
        self.review_title = title
        self.details = details
        self.confirm_label = confirm_label

    def compose(self) -> ComposeResult:
        with Vertical(id="power-change-review"):
            yield Label(self.review_title, id="power-change-title")
            yield Static(self.details, markup=False)
            with Horizontal(id="power-change-buttons"):
                yield Button(self.confirm_label, id="confirm-power-change", variant="warning")
                yield Button("Cancel", id="cancel-power-change")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-power-change":
            self.dismiss(True)
        elif event.button.id == "cancel-power-change":
            self.dismiss(False)


class CodexApprovalReviewScreen(ModalScreen[str]):
    """One-command App Server approval; no session-wide grant is offered."""

    CSS = """
    CodexApprovalReviewScreen { align: center middle; }
    #codex-approval { width: 92%; max-width: 96; height: auto; border: thick $warning;
      padding: 1 2; background: $surface; }
    #codex-approval-buttons { height: auto; margin-top: 1; }
    #codex-approval-buttons Button { margin-right: 1; }
    """

    def __init__(self, details: str, *, allow_approve: bool = False) -> None:
        super().__init__()
        self.details = details
        self.allow_approve = allow_approve

    def compose(self) -> ComposeResult:
        with Vertical(id="codex-approval"):
            yield Label(
                "Review exact command or file change"
                if self.allow_approve
                else "Generic execution is blocked; use a registered operation proposal"
            )
            yield Static(self.details, markup=False)
            with Horizontal(id="codex-approval-buttons"):
                yield Button(
                    "Approve once",
                    id="codex-accept",
                    variant="warning",
                    disabled=not self.allow_approve,
                )
                yield Button("Decline", id="codex-decline")
                yield Button("Cancel turn", id="codex-cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        decisions = {
            "codex-accept": "accept",
            "codex-decline": "decline",
            "codex-cancel": "cancel",
        }
        if event.button.id in decisions:
            self.dismiss(decisions[event.button.id])


class McpElicitationReviewScreen(ModalScreen[str]):
    """Visible review for an MCP server input/permission request."""

    CSS = """
    McpElicitationReviewScreen { align: center middle; }
    #mcp-elicitation { width: 92%; max-width: 96; height: auto; border: thick $warning;
      padding: 1 2; background: $surface; }
    #mcp-elicitation-buttons { height: auto; margin-top: 1; }
    #mcp-elicitation-buttons Button { margin-right: 1; }
    """

    def __init__(self, details: str) -> None:
        super().__init__()
        self.details = details

    def compose(self) -> ComposeResult:
        with Vertical(id="mcp-elicitation"):
            yield Label("Review MCP server request")
            yield Static(self.details, markup=False)
            with Horizontal(id="mcp-elicitation-buttons"):
                yield Button("Allow once", id="mcp-accept", variant="warning")
                yield Button("Decline", id="mcp-decline")
                yield Button("Cancel turn", id="mcp-cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        actions = {"mcp-accept": "accept", "mcp-decline": "decline", "mcp-cancel": "cancel"}
        action = actions.get(event.button.id or "")
        if action:
            self.dismiss(action)


class ConversationMessage(Static):
    """One full-width visible message; checkpoint controls live beside it."""

    def __init__(
        self,
        entry: Any,
        checkpoint: ConversationCheckpoint | None = None,
        selector_open: bool = False,
    ) -> None:
        classes = ["user-message" if entry.role == "user" else "response-message"]
        super().__init__(classes=" ".join(classes))
        self.entry = entry
        self.checkpoint = checkpoint
        self.selector_open = selector_open

    def compose(self) -> ComposeResult:
        yield Static("", classes="conversation-message-top")
        yield Static(self.entry.text.strip(), classes="conversation-message-content", markup=False)
        yield Static("", classes="conversation-message-bottom")


class ConversationActivityCard(Static):
    """A bounded, inspectable live-operation card outside agent context."""

    def __init__(self, entry: Any) -> None:
        super().__init__(classes=f"activity-card activity-{entry.status}")
        self.entry = entry

    @property
    def _is_active(self) -> bool:
        return self.entry.status.replace("_", "").casefold() in {
            "inprogress",
            "running",
            "streaming",
            "pending",
            "waiting",
        }

    def compose(self) -> ComposeResult:
        title, _, detail = self.entry.text.partition("\n")
        operation = title.removeprefix("Tool · ").strip().casefold()
        if operation == "mcpToolCall".casefold():
            operation = "package search"
        if self._is_active:
            owner = getattr(self.app.presentation, "activity_owner", "Agent")
            yield Static(f"Working… {owner}", classes="activity-heading")
            yield Static(
                f"  └─ {operation} · {self.entry.status.replace('_', ' ')}",
                classes="activity-detail",
                markup=False,
            )
        else:
            yield Static(
                f"{self.entry.status.replace('_', ' ').capitalize()} · {operation}",
                classes="activity-heading",
            )
            yield Static(
                detail or "No further detail was supplied.", classes="activity-detail", markup=False
            )


class CheckpointButton(Button):
    """Button with a local handler so parent layout propagation cannot swallow clicks."""


class MultilineComposer(Input):
    """Keep every clipboard line while retaining Input's existing submit contract."""

    def _on_paste(self, event: Any) -> None:
        if event.text:
            start, end = self.selection
            self.replace(event.text, start, end)
        event.stop()


class CheckpointChoiceScreen(ModalScreen[str | None]):
    """Native checkpoint chooser, independent of the conversation layout."""

    CSS = """
    CheckpointChoiceScreen { align: center middle; }
    #checkpoint-choice { width: 60; height: auto; border: thick #1683d8; padding: 1 2; background: #1f2328; }
    #checkpoint-choice-buttons { width: 1fr; height: auto; margin-top: 1; }
    #checkpoint-choice-buttons Button { width: 14; min-width: 14; margin-right: 1; }
    #checkpoint-cancel { color: #ffffff; background: #c7375b; border: tall #c7375b; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="checkpoint-choice"):
            yield Label("Checkpoint restoration")
            yield Static(
                "Choose what to restore. A confirmation is required before any restoration."
            )
            with Horizontal(id="checkpoint-choice-buttons"):
                yield Button("Chat", id="checkpoint-context", variant="primary")
                yield Button("Full", id="checkpoint-full", variant="warning")
                yield Button("Cancel", id="checkpoint-cancel", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        choice = {"checkpoint-context": "context", "checkpoint-full": "full"}.get(
            event.button.id or ""
        )
        self.dismiss(choice)


class DomainInfoScreen(ModalScreen[None]):
    CSS = """
    DomainInfoScreen { align: center middle; }
    #domain-info { width: 56; height: auto; border: thick #1683d8; padding: 1 2; background: #1f2328; }
    """

    def __init__(self, label: str, explanation: str):
        super().__init__()
        self.label = label
        self.explanation = explanation

    def compose(self) -> ComposeResult:
        with Vertical(id="domain-info"):
            yield Label(self.label)
            yield Static(self.explanation, markup=False)
            yield Button("Close", id="domain-info-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)


class DomainInfoLabel(Label):
    """Directly rendered ASCII info control."""

    def __init__(self, label: str, info_id: str):
        super().__init__(f"{label}  [i]", classes="domain-field-label", markup=False)
        self.info_id = info_id

    def on_click(self, event: Any) -> None:
        detail = self.app._domain_help.get(self.info_id)
        if detail is not None:
            self.app.push_screen(DomainInfoScreen(*detail))
        event.stop()


class ConversationCheckpointControl(Static):
    """Checkpoint affordance outside the message box, aligned to its right."""

    def __init__(self, checkpoint: ConversationCheckpoint, selector_open: bool = False) -> None:
        super().__init__(classes="checkpoint-control")
        self.checkpoint = checkpoint
        self.selector_open = selector_open

    def compose(self) -> ComposeResult:
        yield CheckpointButton(
            "↶ Checkpoint",
            id=f"checkpoint-{self.checkpoint.checkpoint_id}",
            classes="checkpoint-button",
            action="open_checkpoint",
        )

    def action_open_checkpoint(self) -> None:
        self.app.push_screen(
            CheckpointChoiceScreen(),
            lambda mode: (
                self.app._request_checkpoint_restore(self.checkpoint, mode) if mode else None
            ),
        )


class ConversationPanel(VerticalScroll):
    """Mountable message blocks; unlike RichLog, each block can own controls."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._plain_blocks: list[str] = []

    @property
    def text(self) -> str:
        return "\n\n".join(self._plain_blocks)

    @property
    def soft_wrap(self) -> bool:
        return True

    async def replace_entries(
        self, entries: list[Any], checkpoints: dict[str, ConversationCheckpoint]
    ) -> None:
        await self.remove_children()
        visible = self._visible_entries(entries)
        self._plain_blocks = [entry.text.strip() for entry in visible]
        messages = [self._build_message(entry, checkpoints) for entry in visible]
        activity = getattr(self.app, "_live_activity", None)
        messages.append(
            Static(
                activity.text() if activity is not None else "○ Ready",
                id="live-activity",
                markup=False,
            )
        )
        await self.mount(*messages)
        self.scroll_end(animate=False)

    @staticmethod
    def _visible_entries(entries: list[Any]) -> list[Any]:
        """Render messages and their live activity cards in conversation order."""
        return [entry for entry in entries if entry.text.strip()]

    def _build_message(self, entry: Any, checkpoints: dict[str, ConversationCheckpoint]) -> Any:
        if entry.role == "activity":
            return ConversationActivityCard(entry)
        checkpoint = checkpoints.get(entry.key)
        selector_open = (
            checkpoint is not None and checkpoint.checkpoint_id == self.app._checkpoint_selector_id
        )
        if selector_open:
            self.app._checkpoint_selector_initializing.add(checkpoint.checkpoint_id)
        message = ConversationMessage(entry)
        if checkpoint is None:
            return message
        return Container(
            message,
            Horizontal(
                ConversationCheckpointControl(checkpoint, selector_open),
                classes="checkpoint-row",
            ),
            classes="conversation-entry-row",
        )

    async def clear_entries(self) -> None:
        await self.remove_children()
        self._plain_blocks = []

    def set_checkpoint_menu(self, checkpoint_id: str, open_menu: bool) -> None:
        for control in self.query(ConversationCheckpointControl):
            control.set_menu_open(open_menu and control.checkpoint.checkpoint_id == checkpoint_id)


class ConversationHistoryModal(ModalScreen[tuple[str, str] | None]):
    """Modal screen to browse, load, and delete conversation history.

    Returns tuple of (action, conversation_id) or None:
    - ("load", conv_id) - Resume this conversation
    - ("delete", conv_id) - Delete this conversation
    - None - Cancelled
    """

    CSS = """
    ConversationHistoryModal { align: center middle; }
    #history-dialog {
        width: 90%; max-width: 100; height: 90%; max-height: 30;
        border: thick $primary; padding: 1 2; background: $surface;
    }
    #history-title { text-style: bold; margin-bottom: 1; }
    #history-list { height: 1fr; border: round $secondary; margin-bottom: 1; }
    #history-buttons { height: auto; }
    #history-buttons Button { margin-right: 1; }
    """

    def __init__(self, conversations: list[dict]) -> None:
        super().__init__()
        self.conversations = conversations
        self.selected_index: int | None = None
        self.conv_id_by_index: dict[int, str] = {}  # Map row index to conversation ID

    def compose(self) -> ComposeResult:
        from textual.widgets import DataTable

        with Vertical(id="history-dialog"):
            yield Label(
                f"📚 Conversation History ({len(self.conversations)} saved)",
                id="history-title",
            )
            yield DataTable(id="history-list", cursor_type="row", zebra_stripes=True)
            with Horizontal(id="history-buttons"):
                yield Button("Resume Selected", id="history-resume", variant="primary")
                yield Button("Delete Selected", id="history-delete", variant="error")
                yield Button("Close", id="history-close")

    def on_mount(self) -> None:
        """Populate the table with conversation data."""
        table = self.query_one("#history-list", DataTable)

        # Add columns
        table.add_columns("#", "Title", "Messages", "Last Updated")

        # Add rows and store index mapping
        for i, conv in enumerate(self.conversations, 1):
            title = conv["title"]
            if len(title) > 50:
                title = title[:50] + "..."

            date = conv["updated_at"][:16].replace("T", " ")

            table.add_row(str(i), title, str(conv["message_count"]), date)

            # Store mapping: row index (0-based) to conversation ID
            self.conv_id_by_index[i - 1] = conv["id"]

        # Disable action buttons initially
        self.query_one("#history-resume", Button).disabled = True
        self.query_one("#history-delete", Button).disabled = True

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handle row selection."""
        self.selected_index = event.cursor_row
        # Enable action buttons when a row is selected
        self.query_one("#history-resume", Button).disabled = False
        self.query_one("#history-delete", Button).disabled = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("system-domain-"):
            self._select_system_domain(button_id.removeprefix("system-domain-"))
            return

        if button_id == "history-close":
            self.dismiss(None)
            return

        if button_id in ("history-resume", "history-delete"):
            if self.selected_index is None:
                self.notify("Please select a conversation first", severity="warning")
                return

            # Get conversation ID from our mapping
            conv_id = self.conv_id_by_index.get(self.selected_index)

            if not conv_id:
                self.notify(
                    f"Error: No conversation found at index {self.selected_index}",
                    severity="error",
                )
                return

            if button_id == "history-resume":
                self.dismiss(("load", conv_id))
            elif button_id == "history-delete":
                # Find conversation title for confirmation
                conv = next((c for c in self.conversations if c["id"] == conv_id), None)
                if conv:
                    title = conv["title"][:30] + ("..." if len(conv["title"]) > 30 else "")
                    self.notify(f"Deleted: {title}", severity="information")
                self.dismiss(("delete", conv_id))


class JarvisTui(App[None]):
    TITLE = "Jarvis"
    SUB_TITLE = "hybrid conversation and bounded host actions"

    CSS = """
    Screen { layout: vertical; }
    #workspace-tabs { height: 1fr; }
    TabPane { padding: 1; }
    .pane-title { text-style: bold; margin-bottom: 1; }
    .pane-help { color: $text-muted; margin-bottom: 1; }
    .pane-log { height: 1fr; border: round $secondary; }
    #conversation-pane { padding: 1 0; align: center top; }
    #conversation-pane > * { width: 92%; }
    #conversation-layout {
        height: 1fr;
        align: left top;
        offset-x: -1;
    }
    #conversation-sidebar { width: 30; min-width: 30; height: 1fr; margin: 0; }
    #conversation-action-rail {
        width: 12;
        min-width: 12;
        height: 1fr;
        margin: 1 0 0 0;
    }
    #conversation-gap { width: 6%; height: 1fr; }
    #conversation-controls {
        height: auto;
        align: left top;
    }
    #conversation-controls Button {
        width: 12;
        min-width: 12;
        height: 3;
        margin-bottom: 1;
        padding: 0 1;
    }
    #conversation-main { width: 1fr; height: 1fr; }
    #conversation-right-gap, #conversation-right-spacer { display: none; }
    #specialist-global-row {
        width: 30;
        min-width: 30;
        height: 5;
        margin: 0 0 1 0;
        align: left top;
    }
    #specialist-select { width: 30; min-width: 30; height: 5; }
    #conversation-pane .pane-help { margin-bottom: 1; }
    #conversation-log { margin: 0 2; padding: 1 0 1 2; border: round $secondary; overflow-x: hidden; }
    #live-activity { height: auto; min-height: 1; max-height: 6; margin: 0 2 1 2; color: #8ecbff; }
    .conversation-entry-row { width: 1fr; min-width: 0; height: auto; background: #111111; }
    ConversationMessage { width: 1fr; min-width: 0; height: auto; box-sizing: border-box; overflow-x: hidden; }
    ConversationMessage.user-message { background: #626b75; color: #ffffff; }
    ConversationMessage.response-message { background: #111111; color: #e5e7eb; }
    .conversation-message-top, .conversation-message-bottom { height: 1; width: 1fr; min-width: 0; padding: 0; }
    .conversation-message-content { height: auto; width: 1fr; min-width: 0; padding: 0 4 0 1; overflow-x: hidden; }
    .activity-card { width: 1fr; min-width: 0; height: 2; margin: 0; padding: 0 1; border: none; background: #111111; color: #d9e1e8; }
    .activity-heading { width: 1fr; height: 1; color: #8ecbff; text-style: bold; }
    .activity-detail { width: 1fr; height: 1; color: #d9e1e8; }
    .checkpoint-row { width: 1fr; height: 3; min-height: 3; margin: 1 1 1 0; align: right top; }
    .checkpoint-control { width: 20; min-width: 20; height: 3; min-height: 3; margin: 0; padding: 0; }
    .checkpoint-button { width: 20; min-width: 20; height: 3; min-height: 3; padding: 0; margin: 0; border: round #1683d8; content-align: center middle; background: #1f2328; color: #ffffff; }
    #package-toolbar, #package-tools {
        height: auto; margin-bottom: 1; align: left middle;
    }
    #system-layout { width: 1fr; height: 1fr; }
    #system-sidebar { width: 22; min-width: 22; height: 1fr; border: round $secondary; padding: 1; }
    #system-sidebar Button { width: 1fr; margin-bottom: 1; }
    #system-sidebar .system-domain-active { background: $accent; color: $text; }
    #system-main { width: 1fr; height: 1fr; padding-left: 1; }
    #system-overview, #system-domain-detail { width: 1fr; height: 1fr; }
    #system-toolbar { height: auto; margin-bottom: 1; align: left middle; }
    #system-toolbar Label { width: auto; margin-left: 1; }
    #system-view { width: 16; margin-left: 1; }
    #system-clean { height: 1fr; border: round $secondary; padding: 1 4 1 1; }
    #system-overview-card { width: 1fr; height: auto; min-height: 4; border: round $secondary; padding: 1 2; margin-bottom: 1; }
    .domain-field { width: 1fr; height: 3; min-height: 3; border-bottom: solid #30363d; align: left middle; }
    .domain-field-label { width: 44; min-width: 44; color: $text-muted; text-style: bold; padding-right: 2; }
    .domain-field-value { width: 1fr; min-width: 12; padding-left: 1; }
    #domain-clean-health, #domain-clean-development, #domain-clean-network, #domain-clean-security, #domain-clean-recovery { padding-right: 2; }
    #package-toolbar Button, #package-tools Button {
        width: auto; min-width: 9; margin-right: 1;
    }
    #package-toolbar Label { width: auto; margin: 0 1; }
    #package-view { width: 23; }
    #package-sort { width: 18; }
    #package-name { width: 1fr; min-width: 24; }
    #package-summary { height: auto; color: $text-muted; margin-bottom: 1; }
    #packages-table { height: 1fr; min-height: 10; border: round $secondary; }
    #package-details-heading { height: auto; text-style: bold; margin-top: 1; }
    #package-details-panel { height: 5; border: round $secondary; padding: 0 1; }
    #power-toolbar { height: auto; margin-bottom: 1; align: left middle; }
    #power-toolbar Button { width: auto; min-width: 12; margin-right: 1; }
    #power-toolbar Label { width: auto; margin: 0 1; }
    #power-section { width: 24; }
    #power-summary { height: auto; color: $text-muted; margin-bottom: 1; }
    #power-data-region { height: 1fr; min-height: 10; }
    #power-inventory-region, #power-settings-region { width: 1fr; height: 1fr; border: round $secondary; padding: 0 1; overflow-x: hidden; }
    #power-providers { height: 1fr; border: none; padding: 0; margin-bottom: 1; }
    #power-live-summary { height: auto; color: $text-muted; margin-bottom: 1; }
    #power-profile-row { height: auto; margin-bottom: 1; align: left middle; }
    #power-profile-row Label { width: auto; margin-right: 1; }
    #power-profile-name { width: 24; margin-right: 1; }
    #power-profile-goal { width: 18; margin-right: 1; }
    #power-profile-row Button { width: auto; min-width: 12; margin-right: 1; }
    #power-profile-status { height: 5; border: round $secondary; padding: 0 1; margin-bottom: 1; overflow-x: hidden; }
    #power-profile-application { height: 1fr; min-height: 4; max-height: 10; border: round $warning; padding: 0 1; margin-bottom: 1; overflow-x: hidden; }
    #power-package-handoff { height: auto; margin-bottom: 1; align: left middle; }
    #power-package-handoff-status { width: 1fr; color: $text-muted; }
    #power-package-handoff-select { width: auto; min-width: 28; }
    #power-settings-table { height: 1fr; min-height: 7; border: none; }
    #power-mutation-row { height: auto; margin-top: 1; align: left middle; }
    #power-mutation-row Label { width: auto; margin-right: 1; }
    #power-value { width: 24; margin-right: 1; }
    #power-mutation-row Button { width: auto; min-width: 15; margin-right: 1; }
    #power-mutation-status { height: auto; color: $text-muted; }
    #power-details { height: 4; border: round $secondary; padding: 0 1; }
    #overview-content { height: 1fr; border: round $secondary; padding: 1; }
    #session-controls { height: auto; margin-bottom: 1; }
    #session-controls Button { width: auto; margin-right: 1; }
    #agents-workspace { height: 1fr; }
    #agent-catalog { width: 34; height: 1fr; margin-right: 1; }
    #agents-table { height: 1fr; border: round $secondary; }
    #agent-editor { width: 1fr; height: 1fr; border: round $secondary; padding: 1 2; }
    #agent-editor-content { height: 1fr; }
    #agent-editor-heading { text-style: bold; margin-bottom: 1; }
    #agent-summary, #agent-tools-summary, #agent-knowledge-summary {
        height: auto; color: $text-muted; margin-bottom: 1;
    }
    #agent-editor-mode { width: 26; margin-bottom: 1; }
    #agent-structured, #agent-raw { height: auto; }
    .agent-field-label { color: $text-muted; margin-top: 1; }
    #agent-structured Input, #agent-structured Select {
        height: 3; margin-bottom: 1; border: round $secondary;
    }
    #agent-prompt { height: 8; border: round $secondary; margin-bottom: 1; }
    #agent-definition { height: 20; border: round $secondary; margin-bottom: 1; }
    #agent-editor-actions { height: auto; margin-top: 1; }
    #agent-editor-actions Button { margin-right: 1; }
    #global-model-row { width: 1fr; height: 4; min-height: 4; align: left middle; margin: 1 0 1 0; }
    #global-model-row .agent-field-label { width: 18; height: 3; margin: 0 1 0 0; content-align: left middle; }
    #global-model-select { width: 30; min-width: 30; height: 3; min-height: 3; }
    #global-model-status { width: 1fr; height: 3; margin-left: 2; content-align: left middle; }
    #global-reasoning-row { width: 1fr; height: 4; min-height: 4; align: left middle; margin: 0 0 1 0; }
    #global-reasoning-row .agent-field-label { width: 18; height: 3; margin: 0 1 0 0; content-align: left middle; }
    #global-reasoning-select { width: 30; min-width: 30; height: 3; min-height: 3; }
    #global-reasoning-status { width: 1fr; height: 3; margin-left: 2; content-align: left middle; }
    #global-context-row { width: 1fr; height: 4; min-height: 4; align: left middle; margin: 0 0 1 0; }
    #global-context-row .agent-field-label { width: 18; height: 3; margin: 0 1 0 0; content-align: left middle; }
    #global-context-select { width: 30; min-width: 30; height: 3; min-height: 3; }
    #global-context-status { width: 1fr; height: 3; margin-left: 2; content-align: left middle; }
    #agent-validation { height: 7; border: round $secondary; margin-top: 1; }
    .lighting-control-row { height: auto; margin: 1 0; align: left middle; }
    .lighting-control-row > Label { width: 18; }
    .lighting-control-row Select { width: 34; }
    .lighting-control-row LightingRangeControl { width: 1fr; height: 3; }
    .lighting-range-line { height: 1; width: 1fr; align: left middle; }
    .lighting-range-line Button { width: 4; min-width: 4; }
    .lighting-range-line ProgressBar { width: 1fr; }
    #lighting-buttons { height: auto; margin: 1 0; }
    #lighting-buttons Button { margin-right: 1; }
    #composer-row { dock: bottom; height: 3; padding: 0 1; }
    #composer { width: 1fr; }
    #send-request { width: 10; margin-left: 1; }
    #cancel-turn { width: 10; margin-left: 1; }
    #status { height: 1; background: $panel; color: $text-muted; padding: 0 1; }
    .plain #status { text-style: none; }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("escape", "focus_composer", "Composer"),
        ("ctrl+x", "cancel_turn", "Cancel turn"),
        ("ctrl+1", "show_overview", "Overview"),
        ("ctrl+2", "show_conversation", "Conversation"),
        ("ctrl+3", "show_agents", "Agents"),
        ("ctrl+4", "show_lighting", "Lighting"),
        ("ctrl+g", "show_power", "Power"),
        ("ctrl+5", "show_packages", "Packages"),
        ("ctrl+6", "show_timeline", "Timeline"),
        ("ctrl+7", "show_operations", "Operations"),
        ("ctrl+9", "show_operations", "Operations"),
        ("ctrl+0", "show_packages", "Packages"),
    ]

    def __init__(
        self,
        bundle_root: Path,
        *,
        connect_app_server: bool = False,
        enable_live_turns: bool = False,
        plain_mode: bool = False,
        broker: JarvisBroker | None = None,
        session: AppServerSessionController | None = None,
        connect_jarvisd: bool = False,
        jarvisd_socket: Path | None = None,
        conversation_storage: Path | None = None,
    ) -> None:
        super().__init__()
        self.bundle_root = bundle_root.resolve()
        try:
            sandbox_mode, approval_policy = execution_policy(self.bundle_root)
            self._danger_full_access = (
                sandbox_mode == "danger-full-access" and approval_policy == "on-request"
            )
        except (OSError, ValueError, KeyError, TypeError):
            self._danger_full_access = False
        self.connect_app_server = connect_app_server
        self.enable_live_turns = enable_live_turns
        self.plain_mode = plain_mode
        self.connect_jarvisd = connect_jarvisd
        self.jarvisd_client = JarvisdStatusClient(jarvisd_socket)
        if broker is None:
            registry = ActionRegistry.load(
                self.bundle_root / "plugins/jarvis-system-admin/registry/actions.json"
            )
            broker = JarvisBroker(
                registry,
                EventJournal(self.bundle_root / "runtime/tui/events.jsonl"),
                local_control=ReadOnlyLocalControl(self.bundle_root),
            )
        self.operation_workflow = OperationWorkflow(self.bundle_root)
        self.normal_terminal_workflow = NormalTerminalWorkflow(self.bundle_root)
        self._operation_busy = False
        self.broker = broker
        self.registry = broker.registry
        self.session = session or AppServerSessionController(
            StdioAppServerClient(codex_home=self.bundle_root / "runtime/codex-home"),
            self.broker,
            self.bundle_root,
            live_turns_enabled=enable_live_turns,
        )
        self._model_settings_path = self.bundle_root / "runtime/jarvis-model.json"
        settings = self._load_model_settings()
        self._selected_model = settings["model"]
        self._selected_reasoning = settings["reasoning_effort"]
        self._selected_context = settings["context_window"]
        self.session.model = self._selected_model
        self.session.reasoning_effort = self._selected_reasoning
        self.session.context_window = self._selected_context
        self.session.add_listener(self._on_codex_event)

        self._pending_clarification: TaskRecord | None = None
        self._submission_busy = False
        self._submission_task_id: str | None = None
        self._active_submission_worker: Any | None = None
        self._submission_cancel_requested = False

        self.presentation = JarvisPresentation()
        self.agent_registry = AgentRegistry(self.bundle_root)
        self.agent_coordinator = AgentCoordinator(self.agent_registry)
        self._specialists: tuple[Specialist, ...] = self.agent_registry.selectable()
        self._all_specialists: tuple[Specialist, ...] = self.agent_registry.all()
        self._active_specialist: Specialist | None = self.agent_coordinator.selected()
        try:
            if self._active_specialist is None and self._specialists:
                self._active_specialist = self._specialists[0]
        except (IndexError, RuntimeError):
            pass
        self._agent_table_ready = False
        self._agent_table_items: dict[str, str] = {}
        self._agent_editor_id: str | None = None
        self._agent_editor_draft: dict[str, Any] | None = None
        self._pending_agent_activation: dict[str, Any] | None = None
        self._pending_agent_rollback: str | None = None
        self.active_view = "overview"
        self._overview_capabilities = 0
        self._overview_enabled_actions = 0
        self._overview_unavailable_actions = 0
        self._overview_knowledge: dict[str, Any] = {
            "available": False,
            "reason": "not_loaded",
        }
        self._overview_recovered_tasks = 0
        self._overview_h1_scope = "not loaded"
        self._overview_recovery: dict[str, Any] = {}
        self._overview_audit_status: dict[str, Any] = {"audit_integrity": "unavailable"}
        self._jarvisd_status: dict[str, Any] | None = None
        installed_lighting_driver = Path("/opt/acer-predator-rgb/facer_rgb.py")
        self._lighting_driver = (
            installed_lighting_driver
            if driver_available(installed_lighting_driver)
            else self.bundle_root.parent / "acer-predator-rgb/facer_rgb.py"
        )
        self._package_records: tuple[PackageRecord, ...] = ()
        self._available_package_records: tuple[RepositoryPackageRecord, ...] = ()
        self._package_mode = "installed"
        self._package_sort = "alphabetical"
        self._package_page = 0
        self._package_filter = ""
        self._package_loaded = False
        self._package_loading = False
        self._package_table_ready = False
        self._package_table_items: dict[str, dict[str, Any]] = {}
        self._package_preview: dict[str, Any] | None = None
        self._package_preview_task: TaskRecord | None = None
        self._package_catalog_queries: dict[str, str] = {}
        self._package_review_open = False
        self._package_mutation_busy = False
        self._power_inventory: PowerInventory | None = None
        self._power_loading = False
        self._power_section = "All"
        self._power_table_ready = False
        self._power_table_items: dict[str, PowerSetting] = {}
        self._power_selected: PowerSetting | None = None
        self._power_telemetry = PowerTelemetry()
        self._power_telemetry_timer: Any | None = None
        self._power_profile_store = PowerProfileStore()
        self._power_profile_application_store = PowerProfileApplicationStore(
            self._power_profile_store.root
        )
        self._power_profile_application: PowerProfileApplicationRecord | None = (
            self._power_profile_application_store.load_latest_applied()
        )
        self._power_profile_plan: PowerProfilePlan | None = None
        self._pending_package_handoff: dict[str, Any] | None = None
        self._domain_evidence: dict[str, dict[str, Any]] = {}
        self._domain_help: dict[str, tuple[str, str]] = {}

        # Initialize conversation manager
        self.conversation_manager = ConversationManager(
            conversation_storage, auto_save_enabled=False
        )
        # Start with fresh conversation (no auto-load)
        self.conversation_manager.new_conversation()
        self._checkpoint_store = ConversationCheckpointStore(self.conversation_manager.storage_dir)
        self._conversation_checkpoints: tuple[ConversationCheckpoint, ...] = ()
        self._checkpoint_selector_id: str | None = None
        self._checkpoint_selector_initializing: set[str] = set()

        # Track original user input for conversation history (not the formatted prompt)
        self._last_user_input = ""

        # Incremental rendering tracking for conversation
        self._last_rendered_conversation_length = 0
        self._last_conversation_entries_hash: list[tuple[str, str, int, str]] = []
        self._synced_entry_state: dict[str, tuple[int, str]] = {}
        self._conversation_message_indices: dict[str, int] = {}
        self._conversation_persist_queue: dict[str, dict[str, Any]] = {}
        self._conversation_persist_worker: Any | None = None
        self._conversation_render_worker: Any | None = None
        self._conversation_render_pending = False

        # Track when agent is actively streaming
        self._agent_streaming = False
        self._last_agent_delta_time = 0.0
        self._streaming_end_time = 0.0
        self._agent_delta_count = 0
        self._live_activity = LiveActivity()
        configured_context = getattr(self, "_selected_context", "auto")
        if configured_context.isdigit():
            self._live_activity.context_window = int(configured_context)
        self._live_activity_text = ""
        self._render_pending = False
        self._last_render_time = 0.0
        self._pending_timer = None

    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial=VIEW_IDS["overview"], id="workspace-tabs"):
            with TabPane("Overview", id=VIEW_IDS["overview"]):
                yield Label("Operational overview", classes="pane-title")
                with Horizontal(id="session-controls"):
                    yield Button("Sign in with ChatGPT", id="session-login", variant="primary")
                    yield Button("Refresh session", id="session-refresh")
                yield Static(id="overview-content")
            with TabPane("Conversation", id=VIEW_IDS["conversation"]):
                with Horizontal(id="conversation-layout"):
                    with Vertical(id="conversation-sidebar"):
                        with Horizontal(id="specialist-global-row"):
                            yield Select(
                                [(item.display_name, item.id) for item in self._specialists]
                                or [("Unavailable", "unavailable")],
                                value=self._active_specialist.id
                                if self._active_specialist
                                else "unavailable",
                                allow_blank=False,
                                id="specialist-select",
                            )
                        with Vertical(id="conversation-action-rail"):
                            with Vertical(id="conversation-controls"):
                                yield Button("New", id="conv-new", variant="primary")
                                yield Button("History", id="conv-history")
                                yield Button("Copy", id="conv-copy")
                    yield Static(id="conversation-gap")
                    with Vertical(id="conversation-main"):
                        yield Label(
                            "Agent messages stream here; tool output and private reasoning are withheld. Select text with the mouse, then Ctrl+C to copy.",
                            classes="pane-help",
                        )
                        yield ConversationPanel(
                            id="conversation-log",
                            classes="pane-log",
                        )
                    yield Static(id="conversation-right-gap")
                    yield Static(id="conversation-right-spacer")
            with TabPane("Agents", id=VIEW_IDS["agents"]):
                yield Label("Specialist agents", classes="pane-title")
                yield Label(
                    "Choose one model for every specialist. This global setting applies to new turns.",
                    classes="pane-help",
                )
                with Horizontal(id="global-model-row"):
                    yield Label("Global model", classes="agent-field-label")
                    yield Select(
                        JARVIS_MODEL_OPTIONS,
                        value=self._selected_model,
                        allow_blank=False,
                        id="global-model-select",
                    )
                    yield Static(id="global-model-status", markup=False)
                with Horizontal(id="global-reasoning-row"):
                    yield Label("Reasoning effort", classes="agent-field-label")
                    yield Select(
                        JARVIS_REASONING_OPTIONS,
                        value=self._selected_reasoning,
                        allow_blank=False,
                        id="global-reasoning-select",
                    )
                    yield Static(id="global-reasoning-status", markup=False)
                with Horizontal(id="global-context-row"):
                    yield Label("Context window", classes="agent-field-label")
                    yield Select(
                        JARVIS_CONTEXT_OPTIONS,
                        value=self._selected_context,
                        allow_blank=False,
                        id="global-context-select",
                    )
                    yield Static(id="global-context-status", markup=False)
                with Horizontal(id="agents-workspace"):
                    with Vertical(id="agent-catalog"):
                        yield DataTable(id="agents-table", zebra_stripes=True, cursor_type="row")
                    with Vertical(id="agent-editor"):
                        with VerticalScroll(id="agent-editor-content"):
                            yield Label("Select an agent", id="agent-editor-heading")
                            yield Static(id="agent-summary", markup=False)
                            yield Static(id="agent-tools-summary", markup=False)
                            yield Static(id="agent-knowledge-summary", markup=False)
                            yield Select(
                                [
                                    ("Structured definition", "structured"),
                                    ("Raw JSON definition", "raw"),
                                ],
                                value="structured",
                                allow_blank=False,
                                id="agent-editor-mode",
                            )
                            with Vertical(id="agent-structured"):
                                yield Label(
                                    "Agent ID (reviewed plugin identity)",
                                    classes="agent-field-label",
                                )
                                yield Static(id="agent-id")
                                yield Label("Display name", classes="agent-field-label")
                                yield Input(id="agent-display-name")
                                yield Label("Version", classes="agent-field-label")
                                yield Input(id="agent-version")
                                yield Label("Purpose", classes="agent-field-label")
                                yield Input(id="agent-purpose")
                                yield Label(
                                    "Context limit (characters)", classes="agent-field-label"
                                )
                                yield Input(id="agent-context-limit")
                                yield Label("Network policy", classes="agent-field-label")
                                yield Select(
                                    [
                                        ("Offline", "offline"),
                                        ("Official allowlist", "official-allowlist"),
                                    ],
                                    value="offline",
                                    allow_blank=False,
                                    id="agent-network",
                                )
                                yield Label("Mutation policy", classes="agent-field-label")
                                yield Select(
                                    [
                                        ("Project branch only", "project-branch-only"),
                                        ("Registered actions only", "registered-actions-only"),
                                        (
                                            "Approval-gated current user + registered host",
                                            "approval-gated-current-user-and-registered-host",
                                        ),
                                    ],
                                    value="registered-actions-only",
                                    allow_blank=False,
                                    id="agent-mutations",
                                )
                                yield Label(
                                    "Available in Conversation selector",
                                    classes="agent-field-label",
                                )
                                yield Select(
                                    [("Yes", "true"), ("No", "false")],
                                    value="true",
                                    allow_blank=False,
                                    id="agent-selectable",
                                )
                                yield Label(
                                    "Registered tool references (comma-separated)",
                                    classes="agent-field-label",
                                )
                                yield Input(id="agent-tools")
                                yield Label(
                                    "Knowledge sources (comma-separated)",
                                    classes="agent-field-label",
                                )
                                yield Input(id="agent-knowledge-sources")
                                yield Label(
                                    "Capabilities (comma-separated)",
                                    classes="agent-field-label",
                                )
                                yield Input(id="agent-capabilities")
                                yield Label("Specialist instructions", classes="agent-field-label")
                                yield TextArea(id="agent-prompt", show_line_numbers=False)
                            with Vertical(id="agent-raw"):
                                yield Label(
                                    "Complete editable JSON definition",
                                    classes="agent-field-label",
                                )
                                yield TextArea(id="agent-definition", show_line_numbers=True)
                        with Horizontal(id="agent-editor-actions"):
                            yield Button("Validate draft", id="agent-validate", variant="primary")
                            yield Button(
                                "Activate definition", id="agent-activate", variant="warning"
                            )
                            yield Button("Rollback previous", id="agent-rollback")
                            yield Button("Reset draft", id="agent-reset")
                        yield RichLog(id="agent-validation", wrap=True, markup=False)
            with TabPane("Lighting", id=VIEW_IDS["lighting"]):
                yield Label("Keyboard lighting controls", classes="pane-title")
                yield Label(
                    "Typed controls for the locally installed Acer Predator RGB driver.",
                    classes="pane-help",
                )
                with Horizontal(classes="lighting-control-row"):
                    yield Label("Effect")
                    yield Select(
                        [
                            (f"{name}{' (color)' if uses_color else ''}", mode)
                            for mode, (name, uses_color) in EFFECTS.items()
                        ],
                        value=0,
                        id="lighting-mode",
                    )
                with Horizontal(classes="lighting-control-row"):
                    yield Label("Brightness")
                    yield LightingRangeControl(
                        control_id="lighting-brightness",
                        label="Brightness",
                        minimum=0,
                        maximum=100,
                        value=100,
                    )
                with Horizontal(classes="lighting-control-row"):
                    yield Label("Animation speed")
                    yield LightingRangeControl(
                        control_id="lighting-speed",
                        label="Animation speed",
                        minimum=0,
                        maximum=9,
                        value=4,
                    )
                with Horizontal(classes="lighting-control-row"):
                    yield Label("Direction")
                    yield Select(
                        [("Right to left", 1), ("Left to right", 2)],
                        value=1,
                        id="lighting-direction",
                    )
                with Horizontal(classes="lighting-control-row"):
                    yield Label("Color preset")
                    yield Select(
                        [(name.title(), name) for name in COLORS],
                        value="white",
                        id="lighting-color",
                    )
                with Horizontal(classes="lighting-control-row"):
                    yield Label("Zones")
                    yield Select(
                        [
                            ("All zones", "all"),
                            ("Zone 1", "1"),
                            ("Zone 2", "2"),
                            ("Zone 3", "3"),
                            ("Zone 4", "4"),
                        ],
                        value="all",
                        id="lighting-zones",
                    )
                with Horizontal(id="lighting-buttons"):
                    yield Button("Preview typed plan", id="lighting-preview", variant="primary")
                    yield Button(
                        "Apply selected",
                        id="lighting-apply",
                        variant="warning",
                        disabled=not driver_available(self._lighting_driver),
                    )
                yield RichLog(id="lighting-log", classes="pane-log", wrap=True, markup=False)
            with TabPane("Power", id=VIEW_IDS["power"]):
                yield Label("Power drivers and configuration", classes="pane-title")
                yield Label(
                    "Live read-only inventory of exposed power interfaces. Device-waking probes and mutations are disabled.",
                    classes="pane-help",
                )
                with Horizontal(id="power-toolbar"):
                    yield Button("Refresh power state", id="power-refresh", variant="primary")
                    yield Label("Section")
                    yield Select(
                        [
                            ("All settings", "All"),
                            ("Profiles", "Profiles"),
                            ("CPU", "CPU"),
                            ("Platform", "Platform"),
                            ("Intel GPU", "Intel GPU"),
                            ("NVIDIA GPU", "NVIDIA GPU"),
                            ("Other GPU", "Other GPU"),
                            ("Battery / AC", "Battery / AC"),
                        ],
                        value="All",
                        allow_blank=False,
                        id="power-section",
                    )
                yield Static(
                    "Power inventory loads automatically when this tab opens.", id="power-summary"
                )
                with Horizontal(id="power-data-region"):
                    with VerticalScroll(id="power-inventory-region"):
                        yield Static(
                            "Providers not loaded.", id="power-provider-content", markup=False
                        )
                    with VerticalScroll(id="power-settings-region"):
                        yield DataTable(
                            id="power-settings-table", zebra_stripes=True, cursor_type="row"
                        )
                yield Static("Live telemetry: not loaded.", id="power-live-summary")
                with Horizontal(id="power-profile-row"):
                    yield Label("Profile")
                    yield Input(placeholder="Profile name", id="power-profile-name")
                    yield Select(
                        [(goal.title(), goal) for goal in PROFILE_GOALS],
                        value="balanced",
                        allow_blank=False,
                        id="power-profile-goal",
                    )
                    yield Button("Draft profile", id="power-profile-draft")
                    yield Button("Save profile", id="power-profile-save")
                    yield Button("Preview profile", id="power-profile-preview")
                    yield Button("Activate profile", id="power-profile-apply", variant="warning")
                yield Static("No draft", id="power-profile-status", markup=False)
                yield Static(
                    "Preview variant: AC · No applied result available.",
                    id="power-profile-application",
                    markup=False,
                )
                with Horizontal(id="power-package-handoff"):
                    yield Static("No package handoff pending.", id="power-package-handoff-status")
                    yield Button(
                        "Select Installation Specialist", id="power-package-handoff-select"
                    )
                with Horizontal(id="power-mutation-row"):
                    yield Label("New value")
                    yield Select(
                        [("Select an editable setting", "unavailable")],
                        value="unavailable",
                        allow_blank=False,
                        id="power-value",
                        disabled=True,
                    )
                    yield Button(
                        "Apply selected",
                        id="power-apply",
                        variant="warning",
                        disabled=True,
                    )
                    yield Button("Undo last change", id="power-undo", disabled=True)
                yield Static(
                    "Live changes require review confirmation and desktop authorization.",
                    id="power-mutation-status",
                )
                with VerticalScroll(id="power-details"):
                    yield Static(
                        "Select a setting to see its source and supported values.",
                        id="power-details-content",
                        markup=False,
                    )
            with TabPane("Packages", id=VIEW_IDS["packages"]):
                yield Label("Fedora package inventory", classes="pane-title")
                yield Label(
                    "Installed, cached-available, combined, and update views. Repository refresh and package transactions remain approval-gated.",
                    classes="pane-help",
                )
                with Horizontal(id="package-toolbar"):
                    yield Button("Refresh RPM database", id="package-scan", variant="primary")
                    yield Label("View")
                    yield Select(
                        [
                            ("Installed", "installed"),
                            ("Available (cached)", "available"),
                            ("Combined", "combined"),
                            ("Updates (cached)", "updates"),
                        ],
                        value="installed",
                        allow_blank=False,
                        id="package-view",
                    )
                    yield Label("Sort")
                    yield Select(
                        [
                            ("A–Z", "alphabetical"),
                            ("Category", "category"),
                            ("Purpose", "purpose"),
                        ],
                        value="alphabetical",
                        allow_blank=False,
                        id="package-sort",
                    )
                    yield Button("Previous", id="package-page-prev")
                    yield Button("Next", id="package-page-next")
                with Horizontal(id="package-tools"):
                    yield Input(placeholder="Filter packages (Enter)…", id="package-name")
                    yield Button("Filter", id="package-filter", variant="primary")
                    yield Button("Recommend", id="package-recommend")
                    yield Button("Preview install", id="package-preview")
                    yield Button("Preview remove", id="package-preview-remove")
                    yield Button("Authorize preview", id="package-apply")
                    yield Button("Undo last transaction", id="package-undo")
                    yield Button("Archive rollback record", id="package-archive")
                    yield Button("Inspect", id="package-details")
                    yield Button("Docs", id="package-docs")
                    yield Button("Relations", id="package-relationships")
                    yield Button("Repos", id="package-origins")
                    yield Button("History", id="package-history")
                yield Static(
                    "Package inventory loads automatically when this tab opens.",
                    id="package-summary",
                )
                yield DataTable(id="packages-table", zebra_stripes=True, cursor_type="row")
                yield Label(
                    "Package details — click a row; Inspect and Relations add local evidence",
                    id="package-details-heading",
                )
                with VerticalScroll(id="package-details-panel"):
                    yield Static(
                        "Select a package row to see its details.",
                        id="package-details-content",
                        markup=False,
                    )
            with TabPane("System", id=VIEW_IDS["system"]):
                with Horizontal(id="system-layout"):
                    with Vertical(id="system-sidebar"):
                        yield Label("System domains", classes="pane-title")
                        for domain in ("overview", "health", "development", "network", "security", "recovery"):
                            yield Button(domain.title(), id=f"system-domain-{domain}", variant="primary" if domain == "overview" else "default")
                    with Vertical(id="system-main"):
                        with ContentSwitcher(initial="system-overview", id="system-switcher"):
                            with VerticalScroll(id="system-overview"):
                                yield Label("System overview", classes="pane-title")
                                yield Label("Evidence is collected only when requested. Select a domain to inspect it.", classes="pane-help")
                                yield Static(id="system-overview-cards", markup=False)
                            with Vertical(id="system-domain-detail"):
                                yield Label("Select a system domain", id="system-domain-title", classes="pane-title")
                                with Horizontal(id="system-toolbar"):
                                    yield Button("Refresh evidence", id="system-refresh", display=False)
                                    yield Label("View")
                                    yield Select([("Clean", "clean"), ("Raw", "raw")], value="clean", allow_blank=False, id="system-view")
                                    yield Button("Review proposal", id="system-review", display=False)
                                    yield Button("Run in normal terminal", id="system-terminal", display=False)
                                yield Input(placeholder="Operation ID supplied by the agent", id="system-operation")
                                with ContentSwitcher(initial="system-clean", id="system-detail-switcher"):
                                    yield VerticalScroll(id="system-clean")
                                    yield RichLog(id="system-log", wrap=True, markup=False)
            with TabPane("Timeline", id=VIEW_IDS["timeline"]):
                with Horizontal(classes="pane-controls"):
                    yield Label("Auditable timeline projection", classes="pane-title")
                    yield Button("Copy Timeline", id="copy-timeline", classes="control-button")
                yield RichLog(id="timeline-log", classes="pane-log", wrap=True, markup=False)
            with TabPane("Operations", id=VIEW_IDS["operations"]):
                yield Label("Phase 6 operational console", classes="pane-title")
                yield Label(
                    "Read-only projection of errors, lessons, recovery, settings, and audit state. "
                    "It cannot trigger observations, execute commands, persist facts, or mutate policies.",
                    classes="pane-help",
                )
                yield RichLog(id="operations-log", classes="pane-log", wrap=True, markup=False)
        with Horizontal(id="composer-row"):
            yield MultilineComposer(placeholder="Ask Jarvis or describe a symptom…", id="composer")
            yield Button("Send", id="send-request", variant="primary")
            yield Button("Cancel", id="cancel-turn", disabled=True)
        yield Static(id="status")
        yield Footer()

    async def on_mount(self) -> None:
        self.set_interval(0.1, self._render_live_activity)
        if self.plain_mode:
            self.add_class("plain")
        self.presentation.load_journal(self.broker.journal.read())
        self._load_local_overview()
        self._load_agent_editor(self._active_specialist.id if self._active_specialist else None)
        self._render_all()
        self._render_lighting_preview()
        if isinstance(self.broker.local_control, ReadOnlyLocalControl):
            self.run_worker(
                self._load_package_inventory(refresh=True),
                group="package-inventory",
                exclusive=True,
            )
        self.query_one("#composer", Input).focus()
        if self.connect_jarvisd:
            self.run_worker(self._refresh_jarvisd(), group="jarvisd-status", exclusive=True)
        if self.connect_app_server:
            self.session.set_catalog_specialist(self._active_specialist)
            self.run_worker(self._connect_app_server(), group="app-server-connect", exclusive=True)
        self._system_domain = "overview"

    async def on_unmount(self) -> None:
        await self._persist_conversations()
        if self.session.client.running:
            await self.session.disconnect()

    async def _connect_app_server(self) -> None:
        try:
            await self.session.connect()
            self._system_message("Connected to local Codex App Server; no turn was submitted.")
        except Exception as exc:
            self._system_message(f"App Server connection failed safely: {type(exc).__name__}")
        self._refresh_overview()
        self._render_all()

    def _load_local_overview(self) -> None:
        """Load local, potentially expensive status once per explicit refresh."""

        try:
            self._overview_capabilities = len(self.broker.capabilities())
        except Exception:
            self._overview_capabilities = 0
        try:
            self._overview_knowledge = self.broker.knowledge_status()
        except Exception as exc:
            self._overview_knowledge = {
                "available": False,
                "reason": type(exc).__name__,
            }
        actions = self.registry.all()
        self._overview_enabled_actions = sum(item.availability == "enabled" for item in actions)
        self._overview_unavailable_actions = sum(item.availability != "enabled" for item in actions)
        self._overview_recovered_tasks = len(self.broker.recover_tasks())
        try:
            valid, count, reason = self.broker.journal.verify()
            self._overview_audit_status = {
                "audit_integrity": "verified" if valid else "failed",
                "journal_events": count,
                "journal_reason": reason,
            }
        except Exception as exc:
            self._overview_audit_status = {
                "audit_integrity": "unavailable",
                "journal_reason": type(exc).__name__,
            }
        self._overview_h1_scope = self._load_h1_scope_summary()
        recovery_reader = getattr(self.broker.local_control, "recovery_status", None)
        if callable(recovery_reader):
            try:
                self._overview_recovery = recovery_reader()
            except Exception:
                self._overview_recovery = {
                    "r1": {"status": "unavailable"},
                    "r2": {"status": "unavailable"},
                }
        self._refresh_overview()

    def _load_h1_scope_summary(self) -> str:
        path = self.bundle_root / "vm-lab/enrollment/tier0-approved-fact-scope.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            entries = value["entries"]
            facts = {fact for entry in entries for fact in entry["fact_ids"]}
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
            return f"{len(entries)} adapters / {len(facts)} facts · scope {digest}"
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            return "unavailable"

    async def _refresh_jarvisd(self) -> None:
        try:
            status = await run_blocking_once(
                self.jarvisd_client.read_status, thread_name="jarvisd-status-read"
            )
            self._jarvisd_status = status.to_display()
            self._system_message("jarvisd status loaded read-only")
        except Exception as exc:
            self._jarvisd_status = {"host_authority": f"unavailable ({type(exc).__name__})"}
            self._system_message(f"jarvisd status unavailable: {type(exc).__name__}")
        self._refresh_overview()
        self._render_all()

    async def _begin_chatgpt_login(self) -> None:
        try:
            if not self.session.client.running:
                await self.session.connect()
            elif self.session.snapshot.connection in {
                ConnectionState.OFFLINE,
                ConnectionState.DISCONNECTED,
                ConnectionState.FAILED,
            }:
                await self.session.refresh_account()
            if self.session.snapshot.connection in {
                ConnectionState.READY,
                ConnectionState.CAPACITY_LIMITED,
            }:
                self._system_message(
                    "ChatGPT session is already authenticated. Use Refresh session to reload it."
                )
                self._refresh_overview()
                self._render_all()
                return
            result = await self.session.begin_chatgpt_login()
            auth_url = result.get("authUrl") if isinstance(result, dict) else None
            opened = isinstance(auth_url, str) and webbrowser.open(auth_url, new=2)
            self._system_message(
                "ChatGPT sign-in opened in the browser. Complete it, then select Refresh session."
                if opened
                else "ChatGPT sign-in was started. Complete the managed login flow, then select Refresh session."
            )
        except Exception as exc:
            self._system_message(f"ChatGPT sign-in could not start: {type(exc).__name__}")
        self._refresh_overview()
        self._render_all()

    async def _refresh_app_server_session(self) -> None:
        try:
            await self.session.refresh_account()
            if self.session.snapshot.connection == ConnectionState.READY:
                await self.session.refresh_rate_limits()
            self._system_message("App Server session refreshed.")
        except Exception as exc:
            self._system_message(f"App Server session refresh failed: {type(exc).__name__}")
        self._refresh_overview()
        self._render_all()

    def _format_message_whatsapp_style(self, entry) -> str:
        """Return visible message text without exposing its internal role."""
        return entry.text.strip()

    def _refresh_overview(self) -> None:
        """Refresh volatile session state without touching the local database."""

        operational_status = dict(self._jarvisd_status or {})
        operational_status.update(self._overview_audit_status)

        self.presentation.refresh_overview(
            self.session.snapshot,
            capabilities=self._overview_capabilities,
            enabled_actions=self._overview_enabled_actions,
            unavailable_actions=self._overview_unavailable_actions,
            knowledge_status=self._overview_knowledge,
            recovered_tasks=self._overview_recovered_tasks,
            jarvisd_status=operational_status,
            h1_scope=self._overview_h1_scope,
            recovery_status=self._overview_recovery,
            phase5_status=self._overview_recovery.get("phase5", {}),
        )
        self.presentation.refresh_operational_console(
            jarvisd_status=operational_status,
            recovery_status=self._overview_recovery,
            knowledge_status=self._overview_knowledge,
        )

    def _schedule_conversation_render(self) -> None:
        worker = self._conversation_render_worker
        if worker is not None and not worker.is_finished:
            self._conversation_render_pending = True
            return
        self._conversation_render_pending = False
        self._conversation_render_worker = self.run_worker(
            self._render_conversation_panel(),
            group="conversation-blocks",
            exclusive=False,
        )

    async def _render_conversation_panel(self) -> None:
        panel = self.query_one("#conversation-log", ConversationPanel)
        while True:
            self._conversation_render_pending = False
            await panel.replace_entries(
                list(self.presentation.conversation), self._checkpoints_by_message_key()
            )
            if not self._conversation_render_pending:
                return

    def _replace_log(self, selector: str, lines: tuple[str, ...] | list[str] | str) -> None:
        # Conversation rows are styled individually; rebuild the bounded view
        # from presentation state so alignment and status changes stay exact.
        if selector == "#conversation-log":
            try:
                self.query_one(selector, ConversationPanel)

                # Get current conversation entries
                current_entries = self.presentation.conversation
                current_length = len(current_entries)

                # Bind content and status as well as length. App Server commonly
                # repeats identical text from item/started at item/completed.
                current_hash = [
                    (
                        entry.key,
                        entry.status,
                        len(entry.text),
                        hashlib.sha256(entry.text.encode("utf-8")).hexdigest(),
                    )
                    for entry in current_entries
                ]

                # Determine if we need full re-render or incremental update
                need_full_rerender = False

                # Check if entries were removed or reordered
                if current_length < self._last_rendered_conversation_length:
                    need_full_rerender = True
                # Check if existing entries changed (e.g., streaming -> completed)
                elif current_length > 0 and len(self._last_conversation_entries_hash) > 0:
                    common_length = min(
                        len(self._last_conversation_entries_hash), len(current_hash)
                    )
                    if (
                        self._last_conversation_entries_hash[:common_length]
                        != current_hash[:common_length]
                    ):
                        need_full_rerender = True

                if need_full_rerender or self._last_rendered_conversation_length == 0:
                    self._schedule_conversation_render()
                    self._last_rendered_conversation_length = current_length
                    self._last_conversation_entries_hash = current_hash

                elif current_length > self._last_rendered_conversation_length:
                    self._schedule_conversation_render()
                    self._last_rendered_conversation_length = current_length
                    self._last_conversation_entries_hash = current_hash

                # If length is same but hash different, it means an entry was updated
                # This is already handled by need_full_rerender check above
                elif self._last_conversation_entries_hash != current_hash:
                    self._schedule_conversation_render()
                    self._last_conversation_entries_hash = current_hash

            except Exception:
                pass
            return

        # Other logs are still RichLog - optimize by writing all at once
        log = self.query_one(selector, RichLog)
        log.clear()
        if isinstance(lines, str):
            # Single string - write directly
            log.write(lines)
        else:
            # Multiple lines - join and write once instead of loop
            # This is MUCH faster than individual write() calls
            combined = "\n".join(lines) if lines else ""
            if combined:
                log.write(combined)

    def _set_package_details(self, lines: tuple[str, ...] | list[str] | str) -> None:
        if isinstance(lines, str):
            text = lines
        else:
            text = "\n".join(lines)
        self.query_one("#package-details-content", Static).update(text)

    def _lighting_selection(self) -> LightingSelection:
        mode = self.query_one("#lighting-mode", Select).value
        direction = self.query_one("#lighting-direction", Select).value
        color = self.query_one("#lighting-color", Select).value
        zones = self.query_one("#lighting-zones", Select).value
        if (
            not isinstance(mode, int)
            or not isinstance(direction, int)
            or not isinstance(color, str)
        ):
            raise LightingControlError("lighting controls are incomplete")
        if zones == "all":
            selected_zones = (1, 2, 3, 4)
        elif isinstance(zones, str) and zones in {"1", "2", "3", "4"}:
            selected_zones = (int(zones),)
        else:
            raise LightingControlError("lighting zone selection is invalid")
        red, green, blue = COLORS[color]
        return LightingSelection(
            mode=mode,
            brightness=self.query_one("#lighting-brightness", LightingRangeControl).value,
            speed=self.query_one("#lighting-speed", LightingRangeControl).value,
            direction=direction,
            red=red,
            green=green,
            blue=blue,
            zones=selected_zones,
        )

    def _render_lighting_preview(self) -> None:
        log = self.query_one("#lighting-log", RichLog)
        log.clear()
        try:
            selection = self._lighting_selection()
            commands = preview_driver_argv(self._lighting_driver, selection)
            log.write("Preview only. Apply requires a separate confirmation.")
            log.write(
                f"effect={EFFECTS[selection.mode][0]} brightness={selection.brightness}% "
                f"speed={selection.speed} direction={selection.direction} "
                f"color={selection.red},{selection.green},{selection.blue} zones={list(selection.zones)}"
            )
            for argv in commands:
                log.write("argv: " + " ".join(argv))
            log.write("Apply invokes the fixed local driver with this exact selection.")
        except Exception as exc:
            log.write(f"Lighting preview unavailable: {type(exc).__name__}")

    def _sync_conversation_to_manager(self) -> None:
        """Sync presentation conversation entries to conversation manager.

        This bridges the old presentation.conversation system with the
        new conversation_manager system for persistence.

        Tracks synced entries by key and content to handle streaming updates.
        """
        if not hasattr(self, "conversation_manager") or not self.conversation_manager:
            return

        # Get current conversation entries from presentation
        current_entries = self.presentation.conversation
        active_keys = {entry.key for entry in current_entries}
        for stale_key in tuple(self._synced_entry_state):
            if stale_key not in active_keys:
                self._synced_entry_state.pop(stale_key, None)
                self._conversation_message_indices.pop(stale_key, None)

        changed = False
        for entry in current_entries:
            # Extract role and text
            role = entry.role.lower()  # "user", "agent", "jarvis", etc.
            text = entry.text
            status = entry.status

            # Persist every entry visible in the Conversation view. Model-context
            # eligibility is enforced separately by PresentationState.context_snapshot.
            if role not in {"user", "agent", "jarvis", "action", "system"}:
                continue

            # Check if this entry is new or has been updated
            entry_key = entry.key
            current_state = (len(text), status)
            previous_state = self._synced_entry_state.get(entry_key)

            if previous_state is None:
                # New entry - add it
                # For user messages, use the original input instead of the formatted prompt
                if role == "user" and hasattr(self, "_last_user_input") and self._last_user_input:
                    # The presentation entry has already passed terminal-control and
                    # credential-shaped value redaction. Never persist the raw draft.
                    self.conversation_manager.add_message(
                        role,
                        text,
                        {
                            "key": entry_key,
                            "status": status,
                            "task_id": entry.task_id,
                            "turn_id": entry.turn_id,
                            "specialist_id": entry.specialist_id,
                            "specialist_version": entry.specialist_version,
                        },
                    )
                    self._last_user_input = ""  # Clear after use
                else:
                    self.conversation_manager.add_message(
                        role,
                        text,
                        {
                            "key": entry_key,
                            "status": status,
                            "task_id": entry.task_id,
                            "turn_id": entry.turn_id,
                            "specialist_id": entry.specialist_id,
                            "specialist_version": entry.specialist_version,
                        },
                    )
                current = self.conversation_manager.current_conversation
                if current is not None:
                    self._conversation_message_indices[entry_key] = len(current.messages) - 1
                self._synced_entry_state[entry_key] = current_state
                changed = True
            elif current_state != previous_state:
                # Entry has been updated (streaming or status change)
                # Only update if text has grown or status changed to completed
                prev_len, prev_status = previous_state
                curr_len, curr_status = current_state

                if curr_len > prev_len or curr_status != prev_status:
                    msg_index = self._conversation_message_indices.get(entry_key)

                    # Update the message if it exists
                    if (
                        self.conversation_manager.current_conversation
                        and msg_index is not None
                        and msg_index < len(self.conversation_manager.current_conversation.messages)
                    ):
                        self.conversation_manager.current_conversation.messages[msg_index][
                            "content"
                        ] = text
                        self.conversation_manager.current_conversation.messages[msg_index][
                            "timestamp"
                        ] = self._get_timestamp()
                        self.conversation_manager.current_conversation.messages[msg_index][
                            "status"
                        ] = curr_status
                        changed = True

                    self._synced_entry_state[entry_key] = current_state
        if changed:
            self._queue_conversation_persistence()

    def _queue_conversation_persistence(self, conversation: Any | None = None) -> None:
        """Persist completed conversation projections outside the render path."""
        candidate = conversation or self.conversation_manager.get_current_conversation()
        if candidate is None or not candidate.messages:
            return
        snapshot = copy.deepcopy(candidate.to_dict())
        self._conversation_persist_queue[candidate.id] = snapshot
        worker = self._conversation_persist_worker
        if worker is None or worker.is_finished:
            self._conversation_persist_worker = self.run_worker(
                self._persist_conversations(),
                group="conversation-persistence",
                exclusive=False,
            )

    async def _persist_conversations(self) -> None:
        while self._conversation_persist_queue:
            _, snapshot = self._conversation_persist_queue.popitem()
            try:
                await run_blocking_once(
                    self.conversation_manager.save_snapshot,
                    snapshot,
                    thread_name="jarvis-conversation-persistence",
                )
            except ConversationStorageError as exc:
                self._system_message(f"Conversation was not saved ({exc.code}).")
            except Exception:
                self._system_message("Conversation was not saved (conversation.write_failed).")

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime

        return datetime.now().isoformat()

    def _render_all(self) -> None:
        self.query_one("#overview-content", Static).update(self.presentation.render_overview())

        # Skip all log rendering during streaming to prevent UI freeze
        is_streaming = self._is_streaming()

        if not is_streaming:
            self._replace_log("#conversation-log", self.presentation.render_conversation())
            self._sync_conversation_to_manager()
            self._replace_log("#timeline-log", self.presentation.render_timeline())
            self._replace_log("#operations-log", self.presentation.render_operational_console())

        self._render_agents()
        self._render_packages()
        self._render_power()
        self._render_system_overview()
        snapshot = self.session.snapshot
        auth = snapshot.plan_type or snapshot.auth_mode or "not-connected"
        turns = "enabled" if self.enable_live_turns else "disabled"
        pending = len(snapshot.pending_requests)
        power_executor = "ready" if helper_available() else "unavailable"
        package_executor = "ready" if package_helper_available() else "unavailable"
        host_authority = (
            "+".join(
                authority
                for authority, ready in (
                    ("bounded-power", power_executor == "ready"),
                    ("bounded-packages", package_executor == "ready"),
                )
                if ready
            )
            or "none"
        )
        self.query_one("#status", Static).update(
            f"STATE={snapshot.connection.value} | AUTH={auth} | TURNS={turns} | "
            f"PENDING={pending} | CODEX_APPROVALS=exact-once | "
            f"HOST_AUTHORITY={host_authority} | POWER_EXECUTOR={power_executor} | "
            f"PACKAGE_EXECUTOR={package_executor}"
        )
        self.query_one("#send-request", Button).disabled = self._submission_busy
        self.query_one("#cancel-turn", Button).disabled = not (
            snapshot.active_turn_id is not None or self._submission_busy
        )

    def _render_submission_projection(self) -> None:
        """Paint latency-sensitive task state without rebuilding every TUI view."""
        self._replace_log("#conversation-log", self.presentation.render_conversation())
        self._replace_log("#timeline-log", self.presentation.render_timeline())
        self.query_one("#send-request", Button).disabled = self._submission_busy
        self.query_one("#cancel-turn", Button).disabled = not (
            self.session.snapshot.active_turn_id is not None or self._submission_busy
        )

    def _system_message(self, text: str) -> None:
        safe, _ = sanitize_terminal_text(text, limit=1_000)
        self.presentation.add_notice(safe)

    def _show_view(self, name: str) -> None:
        self.active_view = name
        self.query_one("#workspace-tabs", TabbedContent).active = VIEW_IDS[name]

    def action_show_overview(self) -> None:
        self._show_view("overview")

    def action_show_conversation(self) -> None:
        self._show_view("conversation")

    def action_show_agents(self) -> None:
        self._show_view("agents")

    def action_show_lighting(self) -> None:
        self._show_view("lighting")

    def action_show_power(self) -> None:
        self._show_view("power")

    def action_show_timeline(self) -> None:
        self._show_view("timeline")

    def action_show_operations(self) -> None:
        self._show_view("operations")

    def action_show_packages(self) -> None:
        self._show_view("packages")

    def _load_agent_editor(self, specialist_id: str | None) -> None:
        """Load one installed specialist into the editor without activating it."""
        if specialist_id is None or self.agent_registry.get(specialist_id) is None:
            self._agent_editor_id = None
            self._agent_editor_draft = None
            return
        try:
            draft = self.agent_registry.draft(specialist_id)
        except ValueError:
            self._agent_editor_id = None
            self._agent_editor_draft = None
            return
        self._agent_editor_id = specialist_id
        self._agent_editor_draft = draft
        try:
            self.query_one("#agent-editor-heading", Label).update(
                f"Edit {draft['display_name']} ({draft['id']})"
            )
            self._set_structured_agent_fields(draft)
            self.query_one("#agent-definition", TextArea).text = json.dumps(
                draft, ensure_ascii=False, indent=2, sort_keys=True
            )
            self._render_agent_editor_mode()
        except Exception:
            # The registry remains usable in plain/headless contexts before mount.
            pass

    def _installation_specialist(self) -> Specialist | None:
        return self.agent_registry.get("jarvis-installation-specialist")

    @staticmethod
    def _agent_csv(value: str) -> list[str]:
        """Normalize one editable comma-separated descriptor field."""
        return list(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))

    def _set_structured_agent_fields(self, draft: dict[str, Any]) -> None:
        self.query_one("#agent-id", Static).update(str(draft["id"]))
        self.query_one("#agent-display-name", Input).value = str(draft["display_name"])
        self.query_one("#agent-version", Input).value = str(draft["version"])
        self.query_one("#agent-purpose", Input).value = str(draft["purpose"])
        self.query_one("#agent-context-limit", Input).value = str(draft["context_limit"])
        self.query_one("#agent-network", Select).value = str(draft["network"])
        self.query_one("#agent-mutations", Select).value = str(draft["mutations"])
        self.query_one("#agent-selectable", Select).value = (
            "true" if draft.get("selectable", True) else "false"
        )
        self.query_one("#agent-tools", Input).value = ", ".join(draft["allowed_tools"])
        self.query_one("#agent-knowledge-sources", Input).value = ", ".join(
            draft["knowledge_sources"]
        )
        self.query_one("#agent-capabilities", Input).value = ", ".join(draft["capabilities"])
        self.query_one("#agent-prompt", TextArea).text = str(draft["prompt"])

    def _structured_agent_draft(self) -> dict[str, Any]:
        if self._agent_editor_id is None:
            raise ValueError("select an agent before editing")
        draft = dict(self.agent_registry.draft(self._agent_editor_id))
        draft["display_name"] = self.query_one("#agent-display-name", Input).value.strip()
        draft["version"] = self.query_one("#agent-version", Input).value.strip()
        draft["purpose"] = self.query_one("#agent-purpose", Input).value.strip()
        draft["context_limit"] = int(self.query_one("#agent-context-limit", Input).value.strip())
        draft["network"] = str(self.query_one("#agent-network", Select).value)
        draft["mutations"] = str(self.query_one("#agent-mutations", Select).value)
        draft["selectable"] = self.query_one("#agent-selectable", Select).value == "true"
        draft["allowed_tools"] = self._agent_csv(self.query_one("#agent-tools", Input).value)
        draft["knowledge_sources"] = self._agent_csv(
            self.query_one("#agent-knowledge-sources", Input).value
        )
        draft["capabilities"] = self._agent_csv(self.query_one("#agent-capabilities", Input).value)
        draft["prompt"] = self.query_one("#agent-prompt", TextArea).text.strip()
        return draft

    def _render_agent_editor_mode(self) -> None:
        try:
            mode = self.query_one("#agent-editor-mode", Select).value
            if mode == "raw" and self._agent_editor_id is not None:
                self.query_one("#agent-definition", TextArea).text = json.dumps(
                    self._structured_agent_draft(), ensure_ascii=False, indent=2, sort_keys=True
                )
            self.query_one("#agent-structured").display = mode == "structured"
            self.query_one("#agent-raw").display = mode == "raw"
        except (TypeError, ValueError):
            return

    def _draft_from_agent_editor(self) -> dict[str, Any] | None:
        if self._agent_editor_id is None:
            return None
        try:
            mode = self.query_one("#agent-editor-mode", Select).value
            if mode == "raw":
                value = json.loads(self.query_one("#agent-definition", TextArea).text)
                if not isinstance(value, dict):
                    raise ValueError("raw definition must be a JSON object")
                draft = value
            else:
                draft = self._structured_agent_draft()
            draft["id"] = self._agent_editor_id
            draft["schema_version"] = 2
            draft["status"] = "enabled"
            return draft
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            self._write_agent_validation((f"Invalid draft JSON: {exc}",), ())
            return None

    def _write_agent_validation(
        self, errors: tuple[str, ...] | list[str], warnings: tuple[str, ...] | list[str]
    ) -> None:
        try:
            log = self.query_one("#agent-validation", RichLog)
            log.clear()
            if not errors and not warnings:
                log.write("Validation passed. No schema, tool-reference, or policy errors.")
                return
            for error in errors:
                log.write(f"ERROR: {error}")
            for warning in warnings:
                log.write(f"WARNING: {warning}")
        except Exception:
            return

    def _validate_agent_draft(self) -> dict[str, Any] | None:
        draft = self._draft_from_agent_editor()
        if draft is None:
            return None
        result = self.agent_registry.validate(draft, expected_id=self._agent_editor_id)
        self._agent_editor_draft = draft
        self._write_agent_validation(result.errors, result.warnings)
        return draft if result.valid else None

    def _activate_agent_definition(self) -> None:
        draft = self._validate_agent_draft()
        if draft is None or self._agent_editor_id is None:
            return
        current = self.agent_registry.draft(self._agent_editor_id)
        diff = "".join(
            difflib.unified_diff(
                json.dumps(current, ensure_ascii=False, indent=2, sort_keys=True).splitlines(True),
                json.dumps(draft, ensure_ascii=False, indent=2, sort_keys=True).splitlines(True),
                fromfile="active-definition",
                tofile="proposed-definition",
            )
        )
        if not diff:
            self._system_message("Agent definition is unchanged; no activation was requested.")
            return
        details, _ = sanitize_terminal_text(
            f"Agent: {self._agent_editor_id}\n\n{diff}\n\n"
            "Activation replaces the active definition after validation. "
            "The previous version is retained for rollback. This approval applies once.",
            limit=12_000,
        )
        definition_digest = hashlib.sha256(
            json.dumps(draft, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self.broker.journal.append(
            "agent.definition.activation.requested",
            "tui",
            "awaiting_approval",
            {"agent_id": self._agent_editor_id, "definition_digest": definition_digest},
        )
        self._pending_agent_activation = draft
        self.push_screen(
            PowerChangeReviewScreen(
                title="Review specialist definition activation",
                details=details,
                confirm_label="Activate definition",
            ),
            lambda confirmed: self._finish_agent_activation(bool(confirmed)),
        )

    def _finish_agent_activation(self, confirmed: bool) -> None:
        draft = self._pending_agent_activation
        self._pending_agent_activation = None
        if not confirmed or draft is None:
            self.broker.journal.append(
                "agent.definition.activation.declined",
                "tui",
                "cancelled",
                {"agent_id": draft.get("id") if isinstance(draft, dict) else None},
            )
            self._system_message("Agent definition activation declined; active version unchanged.")
            return
        try:
            activated = self.agent_registry.activate(draft)
        except (OSError, TypeError, ValueError) as exc:
            self._system_message(
                f"Agent definition activation failed safely: {type(exc).__name__}."
            )
            return
        self._all_specialists = self.agent_registry.all()
        self._specialists = self.agent_registry.selectable()
        if self._active_specialist is not None and self._active_specialist.id == activated.id:
            self._active_specialist = activated
        try:
            selector = self.query_one("#specialist-select", Select)
            selector.set_options([(item.display_name, item.id) for item in self._specialists])
            if self._active_specialist is not None:
                selector.value = self._active_specialist.id
        except Exception:
            pass
        self._load_agent_editor(activated.id)
        self.broker.journal.append(
            "agent.definition.activation.completed",
            "tui",
            "completed",
            {"agent_id": activated.id, "version": activated.version},
        )
        self._system_message(f"Activated {activated.display_name} definition {activated.version}.")
        self._render_all()

    def _rollback_agent_definition(self) -> None:
        specialist_id = self._agent_editor_id
        if specialist_id is None or not self.agent_registry.has_rollback(specialist_id):
            self._system_message("No archived agent definition is available for rollback.")
            return
        self._pending_agent_rollback = specialist_id
        self.broker.journal.append(
            "agent.definition.rollback.requested",
            "tui",
            "awaiting_approval",
            {"agent_id": specialist_id},
        )
        self.push_screen(
            PowerChangeReviewScreen(
                title="Review specialist definition rollback",
                details=(
                    f"Agent: {specialist_id}\n\n"
                    "The newest archived definition will replace the active definition. "
                    "This approval applies once."
                ),
                confirm_label="Rollback definition",
            ),
            lambda confirmed: self._finish_agent_rollback(bool(confirmed)),
        )

    def _finish_agent_rollback(self, confirmed: bool) -> None:
        specialist_id = self._pending_agent_rollback
        self._pending_agent_rollback = None
        if not confirmed or specialist_id is None:
            self.broker.journal.append(
                "agent.definition.rollback.declined",
                "tui",
                "cancelled",
                {"agent_id": specialist_id},
            )
            self._system_message("Agent definition rollback declined; active version unchanged.")
            return
        try:
            restored = self.agent_registry.rollback(specialist_id)
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._system_message(f"Agent definition rollback failed safely: {type(exc).__name__}.")
            return
        self._all_specialists = self.agent_registry.all()
        self._specialists = self.agent_registry.selectable()
        if self._active_specialist is not None and self._active_specialist.id == restored.id:
            self._active_specialist = restored
        try:
            selector = self.query_one("#specialist-select", Select)
            selector.set_options([(item.display_name, item.id) for item in self._specialists])
            if self._active_specialist is not None:
                selector.value = self._active_specialist.id
        except Exception:
            pass
        self._load_agent_editor(restored.id)
        self.broker.journal.append(
            "agent.definition.rollback.completed",
            "tui",
            "completed",
            {"agent_id": restored.id, "version": restored.version},
        )
        self._system_message(f"Rolled back {restored.display_name} to {restored.version}.")
        self._render_all()

    def _load_model_settings(self) -> dict[str, str]:
        try:
            data = json.loads(self._model_settings_path.read_text())
            model = data.get("model")
            reasoning = data.get("reasoning_effort")
            return {
                "model": model if model in JARVIS_ALLOWED_MODELS else "gpt-5.6-terra",
                "reasoning_effort": reasoning
                if reasoning in JARVIS_ALLOWED_REASONING
                else "medium",
                "context_window": data.get("context_window")
                if data.get("context_window") in JARVIS_ALLOWED_CONTEXT
                else "auto",
            }
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            pass
        return {"model": "gpt-5.6-terra", "reasoning_effort": "medium", "context_window": "auto"}

    def _set_global_model(self, model: str) -> None:
        if model not in JARVIS_ALLOWED_MODELS:
            return
        self._selected_model = model
        self.session.model = model
        self._model_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._model_settings_path.write_text(
            json.dumps(
                {
                    "model": model,
                    "reasoning_effort": self._selected_reasoning,
                    "context_window": self._selected_context,
                },
                sort_keys=True,
            )
            + "\n"
        )
        self.query_one("#global-model-status", Static).update(
            f"Active for all new turns: {model}. Current turn unchanged."
        )

    def _set_global_reasoning(self, effort: str) -> None:
        if effort not in JARVIS_ALLOWED_REASONING:
            return
        self._selected_reasoning = effort
        self.session.reasoning_effort = effort
        self._model_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._model_settings_path.write_text(
            json.dumps(
                {
                    "model": self._selected_model,
                    "reasoning_effort": effort,
                    "context_window": self._selected_context,
                },
                sort_keys=True,
            )
            + "\n"
        )
        self.query_one("#global-reasoning-status", Static).update(
            f"Active for all new turns: {effort}. Current turn unchanged."
        )

    def _set_global_context(self, context: str) -> None:
        if context not in JARVIS_ALLOWED_CONTEXT:
            return
        self._selected_context = context
        self.session.context_window = context
        self._model_settings_path.parent.mkdir(parents=True, exist_ok=True)
        self._model_settings_path.write_text(
            json.dumps(
                {
                    "model": self._selected_model,
                    "reasoning_effort": self._selected_reasoning,
                    "context_window": context,
                },
                sort_keys=True,
            )
            + "\n"
        )
        self.query_one("#global-context-status", Static).update(
            f"Active for all new turns: {context}."
        )

    def _render_agents(self) -> None:
        try:
            table = self.query_one("#agents-table", DataTable)
        except Exception:
            return
        if not self._agent_table_ready:
            table.add_columns("Agent", "Version", "Status", "Selected")
            self._agent_table_ready = True
        table.clear(columns=False)
        self._agent_table_items.clear()
        selected_id = self._active_specialist.id if self._active_specialist else None
        for index, specialist in enumerate(self._all_specialists):
            key = f"agent-{index}"
            self._agent_table_items[key] = specialist.id
            table.add_row(
                specialist.display_name,
                specialist.version,
                "selectable" if specialist.selectable else "installed / not selectable",
                "yes" if specialist.id == selected_id else "",
                key=key,
            )
        if self._agent_editor_id is None and self._all_specialists:
            self._load_agent_editor(selected_id or self._all_specialists[0].id)
        editor_id = self._agent_editor_id or selected_id
        if editor_id is not None:
            for index, specialist in enumerate(self._all_specialists):
                if specialist.id == editor_id:
                    table.move_cursor(row=index, scroll=False)
                    break
        specialist = (
            self.agent_registry.get(self._agent_editor_id) if self._agent_editor_id else None
        )
        if specialist is None:
            return
        draft = self._agent_editor_draft or self.agent_registry.draft(specialist.id)
        self.query_one("#agent-summary", Static).update(
            f"Purpose: {draft['purpose']}\n"
            f"Source: {specialist.source or 'reviewed local plugin'}\n"
            f"Conversation selection: {'active' if specialist.id == selected_id else 'not active'}\n"
            f"Context: {draft.get('context_limit', 64_000)} characters; retention={draft.get('retention', 'bounded')}\n"
            f"Network: {draft.get('network', 'offline')} · Mutation: {draft.get('mutations', 'unknown')}"
        )
        self.query_one("#agent-tools-summary", Static).update(
            "Registered tools: "
            + (", ".join(draft.get("allowed_tools", ())) or "none")
            + "\nCapabilities: "
            + (", ".join(draft.get("capabilities", ())) or "none")
        )
        self.query_one("#agent-knowledge-summary", Static).update(
            "Knowledge kinds: "
            + (", ".join(draft.get("knowledge_kinds", ())) or "none")
            + "\nKnowledge sources: "
            + (", ".join(draft.get("knowledge_sources", ())) or "none")
        )
        self._render_agent_editor_mode()
        try:
            self.query_one(
                "#agent-rollback", Button
            ).disabled = not self.agent_registry.has_rollback(specialist.id)
        except Exception:
            pass

    def _render_power(self) -> None:
        table = self.query_one("#power-settings-table", DataTable)
        summary = self.query_one("#power-summary", Static)
        live = self.query_one("#power-live-summary", Static)
        if not self._power_table_ready:
            table.add_columns("Section", "Setting", "Current", "Available values", "Source")
            self._power_table_ready = True
        table.clear(columns=False)
        self._power_table_items.clear()
        if self._power_loading:
            summary.update("Reading power drivers and settings…")
            return
        if self._power_inventory is None:
            summary.update("Power inventory loads automatically when this tab opens.")
            live.update("Live telemetry: not loaded.")
            self._render_power_application()
            return
        deployed = helper_available()
        self.query_one("#power-undo", Button).disabled = not deployed
        self.query_one("#power-mutation-status", Static).update(
            "Live helper ready · every Apply and Undo requires confirmation + desktop authorization."
            if deployed
            else "Read-only: the reviewed root-owned power helper is not deployed."
        )
        providers = self._power_inventory.providers or ("No exposed power provider detected.",)
        provider_lines = ["Providers:", *(f"• {item}" for item in providers)]
        if self._power_inventory.hardware:
            provider_lines.extend(
                ("", "Hardware:", *(f"• {item}" for item in self._power_inventory.hardware))
            )
        if self._power_inventory.software:
            provider_lines.extend(
                ("", "Software stack:", *(f"• {item}" for item in self._power_inventory.software))
            )
        if self._power_inventory.conflicts:
            provider_lines.extend(
                ("", "Conflicts:", *(f"• {item}" for item in self._power_inventory.conflicts))
            )
        self.query_one("#power-provider-content", Static).update("\n".join(provider_lines))
        telemetry = self._power_telemetry
        live.update(
            "Live telemetry: "
            f"battery={telemetry.battery_capacity}% ({telemetry.battery_status}) · "
            f"AC={telemetry.ac_online} · profile={telemetry.active_profile} · "
            f"temperatures={len(telemetry.temperatures)} · "
            f"sample={telemetry.collected_at or 'unavailable'}"
        )
        handoff = self.query_one("#power-package-handoff-status", Static)
        handoff_button = self.query_one("#power-package-handoff-select", Button)
        if self._pending_package_handoff:
            handoff.update(
                "Power package recommendation is ready; select Installation Specialist "
                "to continue with exact package/group evaluation."
            )
            handoff_button.display = True
        else:
            handoff.update("No package handoff pending.")
            handoff_button.display = False
        values = [
            item
            for item in self._power_inventory.settings
            if self._power_section == "All" or item.section == self._power_section
        ]
        summary.update(
            f"{len(values)} settings · {len(self._power_inventory.providers)} providers · "
            f"section: {self._power_section} · "
            f"{'supervised changes ready' if deployed else 'read-only'}"
        )
        self._render_power_application()
        for index, item in enumerate(values):
            key = f"power-{index}"
            self._power_table_items[key] = item
            table.add_row(
                item.section,
                item.setting,
                item.current,
                item.choices,
                item.source,
                key=key,
            )

    def _render_power_application(self) -> None:
        record = self._power_profile_application
        widget = self.query_one("#power-profile-application", Static)
        if record is None:
            variant = (
                "Battery"
                if self._power_telemetry.battery_status.casefold() == "discharging"
                else "AC"
            )
            widget.update(f"Preview variant: {variant} · No applied result available.")
            return
        lines = [
            f"Applied variant: {record.selected_variant.title()} · {record.status.title()}",
            f"Latest profile: {record.profile_name} · goal={record.goal} · {record.transaction_timestamp}",
        ]
        if record.status == "applied":
            lines.append("Result: verified resulting settings match the requested values.")
        else:
            lines.append(
                "Result: not verified; the draft is preserved and recovery inspection is required."
            )
        if record.changed:
            lines.append(
                "Changed: "
                + "; ".join(
                    f"{key} {value['before']} → {value['after']}"
                    for key, value in record.changed.items()
                )
            )
        if record.unchanged:
            lines.append("Unchanged: " + ", ".join(value["control"] for value in record.unchanged))
        if record.skipped:
            lines.append(
                "Skipped: "
                + ", ".join(str(value.get("control", value)) for value in record.skipped)
            )
        widget.update("\n".join(lines))

    def _configure_power_selection(self, item: PowerSetting) -> None:
        self._power_selected = item
        selector = self.query_one("#power-value", Select)
        apply_button = self.query_one("#power-apply", Button)
        options = POWER_CONTROL_OPTIONS.get(item.control_id or "", ())
        editable = bool(item.writable_by_jarvis and options and item.current in options)
        if editable:
            selector.set_options([(value.replace("_", " ").title(), value) for value in options])
            selector.value = item.current
        else:
            selector.set_options([("Setting is read-only", "unavailable")])
            selector.value = "unavailable"
        selector.disabled = not editable
        apply_button.disabled = True

    async def _load_power_inventory(self) -> None:
        if self._power_loading:
            return
        self._power_loading = True
        self._render_power()
        try:
            self._power_inventory = await run_blocking_once(
                scan_power_inventory, thread_name="jarvis-power-inventory"
            )
            self._power_telemetry = self._power_inventory.telemetry
            self._system_message(
                f"Power inventory loaded: {len(self._power_inventory.settings)} exposed settings."
            )
        except Exception as exc:
            self._system_message(f"Power inventory unavailable: {type(exc).__name__}")
        finally:
            self._power_loading = False
            self._render_power()

    def _ensure_power_telemetry_timer(self) -> None:
        if self._power_telemetry_timer is None:
            self._power_telemetry_timer = self.set_interval(
                10.0, self._schedule_power_telemetry_refresh
            )

    def _schedule_power_telemetry_refresh(self) -> None:
        if self.active_view == "power" and not self._power_loading:
            self.run_worker(
                self._load_power_telemetry(),
                group="power-telemetry",
                exclusive=True,
            )

    async def _load_power_telemetry(self) -> None:
        try:
            self._power_telemetry = await run_blocking_once(
                scan_power_telemetry, thread_name="jarvis-power-telemetry"
            )
            self._render_power()
        except Exception:
            self._power_telemetry = PowerTelemetry()

    def _draft_power_profile(self) -> PowerProfilePlan | None:
        inventory = self._power_inventory
        if inventory is None:
            self._system_message("Load the Power inventory before drafting a profile.")
            return None
        name = self.query_one("#power-profile-name", Input).value.strip()
        goal = self.query_one("#power-profile-goal", Select).value
        if not name or not isinstance(goal, str):
            self._system_message("Enter a profile name and select a goal first.")
            return None
        try:
            plan = plan_power_profile(
                name=name,
                goal=goal,
                inventory=inventory,
                profile_id="profile_" + hashlib.sha256(name.encode()).hexdigest()[:16],
            )
        except ValueError as exc:
            self._system_message(f"Power profile draft rejected: {exc}")
            return None
        self._power_profile_plan = plan
        self._render_power_profile_plan()
        return plan

    def _render_power_profile_plan(self) -> None:
        plan = self._power_profile_plan
        if plan is None:
            self.query_one("#power-profile-status", Static).update("No draft")
            return
        profile = plan.profile
        applied = self._power_profile_application
        state = (
            "Applied and verified"
            if applied is not None
            and applied.status == "applied"
            and applied.profile_digest == profile.profile_digest
            else "Preview prepared — not applied"
        )
        lines = [
            f"{state} · {profile.name} · goal={profile.goal} · digest={profile.profile_digest[:16]}",
            "AC settings: "
            + (
                ", ".join(f"{key}={value}" for key, value in profile.variants["ac"].items())
                or "none"
            ),
            "Battery settings: "
            + (
                ", ".join(f"{key}={value}" for key, value in profile.variants["battery"].items())
                or "none"
            ),
        ]
        if plan.unsupported:
            lines.append("Unsupported controls omitted: " + "; ".join(plan.unsupported[:12]))
        if plan.omitted:
            lines.append("Unavailable values omitted: " + "; ".join(plan.omitted[:12]))
        if plan.conflicts:
            lines.append("Blocked provider conflicts: " + "; ".join(plan.conflicts))
        self.query_one("#power-profile-status", Static).update("\n".join(lines))

    def _save_power_profile(self) -> None:
        plan = self._power_profile_plan or self._draft_power_profile()
        if plan is None:
            return
        try:
            path = self._power_profile_store.save(plan.profile)
        except (OSError, ValueError) as exc:
            self._system_message(f"Power profile could not be saved: {type(exc).__name__}.")
            return
        self._system_message(f"Power profile saved for this user: {path.name}.")

    def _preview_power_profile(self) -> None:
        plan = self._power_profile_plan or self._draft_power_profile()
        if plan is None:
            return
        self._render_power_profile_plan()
        self._system_message(
            "Power profile preview prepared; no setting was changed. "
            "Activation requires one exact approval."
        )

    def _review_power_profile(self) -> None:
        plan = self._power_profile_plan or self._draft_power_profile()
        if plan is None:
            return
        if plan.conflicts or not plan.executable:
            self._system_message(
                "Power profile activation is blocked because no conflict-free executable controls are available."
            )
            return
        variant = (
            "battery" if self._power_telemetry.battery_status.casefold() == "discharging" else "ac"
        )
        changes = plan.profile.variants[variant]
        current = {
            item.control_id: item.current
            for item in (self._power_inventory.settings if self._power_inventory else ())
            if item.control_id in changes
        }
        if set(current) != set(changes):
            self._system_message(
                "Power profile activation is blocked by incomplete current-state evidence."
            )
            return
        details = (
            f"Profile: {plan.profile.name}\nGoal: {plan.profile.goal}\nVariant: {variant}\n\n"
            + "\n".join(f"{key}: {current[key]} → {value}" for key, value in changes.items())
            + "\n\nOne approval applies to this exact profile transaction. "
            "Verification polls the Power inventory after execution."
        )
        self.push_screen(
            PowerChangeReviewScreen(
                title="Review exact power profile activation",
                details=details,
                confirm_label="Approve profile",
            ),
            lambda confirmed: (
                self._execute_power_profile(plan, variant, changes, current) if confirmed else None
            ),
        )

    def _execute_power_profile(
        self,
        plan: PowerProfilePlan,
        variant: str,
        changes: dict[str, str],
        current: dict[str, str],
    ) -> None:
        self._system_message(
            f"Applying {plan.profile.name} ({variant}) through the approved power helper."
        )
        self.run_worker(
            self._run_power_profile(plan, changes, current),
            group="power-profile-mutation",
            exclusive=True,
        )

    async def _run_power_profile(
        self, plan: PowerProfilePlan, changes: dict[str, str], current: dict[str, str]
    ) -> None:
        self.broker.journal.append(
            "registered_mutation.execution.reserved",
            "control_plane",
            "reserved",
            {"workflow": "run_power_profile"},
        )
        try:
            result = await run_blocking_once(
                apply_profile_transaction,
                changes,
                current,
                thread_name="jarvis-power-profile-apply",
                cancellation="settle",
            )
            # The helper's verified post-state is the sole authority for an
            # applied result. A successful process exit or incomplete payload
            # must never be presented as activation.
            if (
                result.get("status") != "passed"
                or result.get("operation") != "profile"
                or result.get("controls") != changes
                or result.get("post_state") != changes
            ):
                raise PowerControlClientError("power profile result was not independently verified")
            record = PowerProfileApplicationRecord.from_transaction(
                profile=plan.profile,
                variant=self._power_telemetry_variant(),
                pre_activation=current,
                requested=changes,
                result=result,
                skipped=tuple(
                    {"control": item, "reason": "planner omitted this control"}
                    for item in (*plan.unsupported, *plan.omitted)
                ),
                status="applied",
                recovery={"available": True, "source": "authoritative power helper"},
            )
            self._power_profile_application_store.save(record)
            self._power_profile_application = record
            explanation = self._power_profile_impact(record)
            confirmation = self._power_profile_confirmation(record, explanation)
            self.presentation.add_agent_conversation(
                confirmation,
                specialist_id="jarvis-power-expert",
            )
            self._system_message("Draft successfully activated and verified.")
            self._power_profile_plan = plan
            self._render_power_profile_plan()
            self._render_all()
            await self._load_power_inventory()
        except Exception as exc:
            try:
                record = PowerProfileApplicationRecord.from_transaction(
                    profile=plan.profile,
                    variant=self._power_profile_variant_for_plan(plan),
                    pre_activation=current,
                    requested=changes,
                    result=None,
                    status="indeterminate",
                    recovery={
                        "available": True,
                        "action": "inspect authoritative power recovery record",
                    },
                )
                self._power_profile_application_store.save(record)
                self._power_profile_application = record
            except (OSError, ValueError):
                pass
            self._render_power_application()
            self._system_message(
                f"Power profile activation failed or is indeterminate: {type(exc).__name__}. "
                "Inspect the authoritative power recovery record before retrying."
            )

    def _power_profile_variant_for_plan(self, plan: PowerProfilePlan) -> str:
        return (
            "battery" if self._power_telemetry.battery_status.casefold() == "discharging" else "ac"
        )

    def _power_telemetry_variant(self) -> str:
        return (
            self._power_profile_variant_for_plan(self._power_profile_plan)
            if self._power_profile_plan
            else (
                "battery"
                if self._power_telemetry.battery_status.casefold() == "discharging"
                else "ac"
            )
        )

    @staticmethod
    def _power_profile_impact(record: PowerProfileApplicationRecord) -> str:
        if record.goal in {"performance"}:
            return "Expected impact: more responsiveness, with potentially higher power use and heat; observed values are the verified after-state."
        if record.goal in {"battery", "quiet", "thermal"}:
            return "Expected impact: lower energy use and thermal activity, with potentially lower peak responsiveness; observed values are the verified after-state."
        return "Expected impact: a balanced compromise between responsiveness, energy use, and thermal activity; observed values are the verified after-state."

    @staticmethod
    def _power_profile_confirmation(record: PowerProfileApplicationRecord, impact: str) -> str:
        lines = [
            "Draft successfully activated",
            f"Profile: {record.profile_name} · variant={record.selected_variant.title()} · status=applied and verified",
            "Previous settings: "
            + (", ".join(f"{k}={v}" for k, v in record.pre_activation.items()) or "none"),
            "Changed controls: "
            + (
                "; ".join(
                    f"{k}: {v['before']} → {v['after']} (requested {v['requested']})"
                    for k, v in record.changed.items()
                )
                or "none"
            ),
            "Resulting profile settings: "
            + (", ".join(f"{k}={v}" for k, v in record.resulting.items()) or "none"),
            "Skipped/unchanged: "
            + (", ".join(v["control"] for v in (*record.unchanged, *record.skipped)) or "none"),
            impact,
        ]
        return "\n".join(lines)

    async def _execute_power_change(self, item: PowerSetting, value: str) -> None:
        self.broker.journal.append(
            "registered_mutation.execution.reserved",
            "control_plane",
            "reserved",
            {"workflow": "execute_power_change"},
        )
        try:
            await run_blocking_once(
                apply_change,
                item.control_id or "",
                value,
                item.current,
                thread_name="jarvis-power-change",
                cancellation="settle",
            )
            self._system_message(
                f"Power change verified: {item.setting}: {item.current} → {value}."
            )
            self.notify("Power setting applied and verified.", severity="information")
        except PowerControlClientError as exc:
            self._system_message(f"Power change failed safely: {exc}")
            self.notify(str(exc), severity="error")
        finally:
            self._power_inventory = None
            await self._load_power_inventory()

    async def _execute_power_undo(self, record_digest: str) -> None:
        self.broker.journal.append(
            "registered_mutation.execution.reserved",
            "control_plane",
            "reserved",
            {"workflow": "execute_power_undo"},
        )
        try:
            result = await run_blocking_once(
                undo_last,
                record_digest,
                thread_name="jarvis-power-undo",
                cancellation="settle",
            )
            self._system_message(f"Power undo verified for {result.get('control', 'profile')}.")
            self.notify("Last power change restored and verified.", severity="information")
        except PowerControlClientError as exc:
            self._system_message(f"Power undo failed safely: {exc}")
            self.notify(str(exc), severity="error")
        finally:
            self._power_inventory = None
            await self._load_power_inventory()

    async def _execute_lighting_change(self, selection: LightingSelection) -> None:
        self.broker.journal.append(
            "registered_mutation.execution.reserved",
            "control_plane",
            "reserved",
            {"workflow": "execute_lighting_change"},
        )
        log = self.query_one("#lighting-log", RichLog)
        try:
            count = await run_blocking_once(
                apply_driver_selection,
                self._lighting_driver,
                selection,
                thread_name="jarvis-lighting-change",
                cancellation="settle",
            )
            log.write(f"Applied RGB selection through {count} fixed driver command(s).")
            self.notify("Keyboard lighting selection applied.", severity="information")
        except LightingControlError as exc:
            log.write(f"Keyboard lighting change failed: {exc}")
            self.notify(str(exc), severity="error")

    def _review_lighting_change(self) -> None:
        try:
            selection = self._lighting_selection()
        except LightingControlError as exc:
            self.notify(str(exc), severity="error")
            return
        self.push_screen(
            PowerChangeReviewScreen(
                title="Review keyboard lighting change",
                details=(
                    f"effect: {EFFECTS[selection.mode][0]}\nbrightness: {selection.brightness}%\n"
                    f"speed: {selection.speed}\ndirection: {selection.direction}\n"
                    f"RGB: {selection.red},{selection.green},{selection.blue}\nzones: {list(selection.zones)}\n\n"
                    "This applies the exact selection through the locally installed Acer RGB driver."
                ),
                confirm_label="Apply keyboard lighting",
            ),
            lambda confirmed: (
                self.run_worker(
                    self._execute_lighting_change(selection),
                    group="lighting-mutation",
                    exclusive=True,
                )
                if confirmed
                else None
            ),
        )

    def _review_power_change(self) -> None:
        item = self._power_selected
        value = self.query_one("#power-value", Select).value
        if (
            item is None
            or item.control_id is None
            or not isinstance(value, str)
            or value == item.current
        ):
            self.notify("Select an editable setting and a different value.", severity="warning")
            return
        self.push_screen(
            PowerChangeReviewScreen(
                title="Review one live power change",
                details=(
                    f"control: {item.control_id}\nsetting: {item.setting}\n"
                    f"before: {item.current}\nafter: {value}\n\n"
                    "The helper will reject stale state, apply only this allowlisted value, and verify the result.\n"
                    "A single-use undo record will replace any previous undo record."
                ),
                confirm_label="Authorize Apply",
            ),
            lambda confirmed: (
                self.run_worker(
                    self._execute_power_change(item, value),
                    group="power-mutation",
                    exclusive=True,
                )
                if confirmed
                else None
            ),
        )

    async def _prepare_power_undo(self) -> None:
        try:
            record = await run_blocking_once(
                authoritative_undo_status, thread_name="jarvis-power-undo-status"
            )
        except PowerControlClientError as exc:
            self.notify(str(exc), severity="error")
            return
        self.push_screen(
            PowerChangeReviewScreen(
                title=(
                    "Review recovery of an interrupted power change"
                    if record["operation"] == "recovery-status"
                    else "Review rollback of the last power change"
                ),
                details=(
                    f"control: {record['control']}\n"
                    f"{'attempted' if record['operation'] == 'recovery-status' else 'current expected'} value: "
                    f"{record['post_value']}\n\n"
                    f"authoritative record: {record['record_digest']}\n\n"
                    "Undo will stop if this record or the target set drifted. It restores only the captured, fsynced pre-state and verifies it."
                ),
                confirm_label=(
                    "Authorize Recovery"
                    if record["operation"] == "recovery-status"
                    else "Authorize Undo"
                ),
            ),
            lambda confirmed: (
                self.run_worker(
                    self._execute_power_undo(record["record_digest"]),
                    group="power-mutation",
                    exclusive=True,
                )
                if confirmed
                else None
            ),
        )

    def _render_packages(self) -> None:
        try:
            table = self.query_one("#packages-table", DataTable)
            summary = self.query_one("#package-summary", Static)
            if not self._package_table_ready:
                table.add_column("Category", width=10)
                table.add_column("Package / version", width=30)
                table.add_column("State", width=14)
                table.add_column("Origin", width=16)
                table.add_column("Purpose", width=28)
                table.add_column("Installed alternatives", width=24)
                self._package_table_ready = True
            table.clear(columns=False)
            self._package_table_items.clear()
            if self._package_loading:
                summary.update("Loading installed package inventory…")
                return
            if not self._package_loaded:
                summary.update("Package inventory loads automatically when this tab opens.")
                return
            values = list(
                package_view(
                    self._package_records,
                    self._available_package_records,
                    self._package_mode,
                )
            )
            if self._package_filter:
                needle = self._package_filter.casefold()
                values = [
                    item
                    for item in values
                    if needle
                    in " ".join(
                        str(item.get(field, ""))
                        for field in (
                            "name",
                            "nevra",
                            "summary",
                            "category",
                            "purpose",
                            "origin",
                            "state",
                        )
                    ).casefold()
                ]
            if self._package_sort == "alphabetical":
                values.sort(
                    key=lambda item: (
                        item["name"].casefold(),
                        item["arch"],
                        item["nevra"],
                    )
                )
            elif self._package_sort == "category":
                values.sort(
                    key=lambda item: (
                        item["category"],
                        item["name"].casefold(),
                        item["arch"],
                    )
                )
            else:
                values.sort(
                    key=lambda item: (
                        item["purpose"],
                        item["category"],
                        item["name"].casefold(),
                    )
                )
            pages = max(1, (len(values) + 99) // 100)
            self._package_page = min(self._package_page, pages - 1)
            visible = page_records(values, page=self._package_page, page_size=100)
            filter_status = f" · filter: {self._package_filter}" if self._package_filter else ""
            summary.update(
                f"{len(values)} packages · {self._package_mode} · {self._package_sort}"
                f"{filter_status} · page {self._package_page + 1}/{pages}"
            )
            for index, item in enumerate(visible):
                version = item["nevra"]
                if item.get("installed_nevra"):
                    version += f" (installed: {item['installed_nevra']})"
                row_key = f"package-{self._package_page}-{index}"
                self._package_table_items[row_key] = item
                table.add_row(
                    item["category"],
                    version,
                    item["state"],
                    item["origin"],
                    item["purpose"],
                    ", ".join(item.get("installed_alternatives", ())) or "-",
                    key=row_key,
                )
        except Exception as exc:
            self.query_one("#package-summary", Static).update(
                f"Package inventory unavailable: {type(exc).__name__}"
            )

    async def _load_package_inventory(self, *, refresh: bool = False) -> None:
        if self._package_loading or (self._package_loaded and not refresh):
            return
        self._package_loading = True
        self._render_packages()
        try:
            installed = await run_blocking_once(scan_rpm, thread_name="jarvis-package-inventory")
            available: tuple[RepositoryPackageRecord, ...] = ()
            if self._package_mode != "installed":
                available = await run_blocking_once(
                    scan_available_cached,
                    call_kwargs={"updates_only": self._package_mode == "updates"},
                    thread_name="jarvis-package-available-inventory",
                )
            self._package_records = installed
            self._available_package_records = available
            self._package_loaded = True
            self._package_page = 0
            self._system_message(
                f"Package inventory loaded automatically: {len(installed)} installed packages."
            )
        except Exception as exc:
            self._system_message(f"Package inventory unavailable: {type(exc).__name__}")
        finally:
            self._package_loading = False
            self._render_packages()

    async def _recommend_packages(self) -> None:
        goal = self.query_one("#package-name", Input).value.strip()
        if not goal:
            self.notify("Enter a package or capability request first.", severity="warning")
            return
        try:
            available = self._available_package_records
            if not available:
                available = await run_blocking_once(
                    scan_available_cached,
                    thread_name="jarvis-package-recommendation-inventory",
                )
                self._available_package_records = available
            result = recommend_cached_packages(goal, self._package_records, available)
            self._set_package_details(json.dumps(result, indent=2, sort_keys=True))
        except Exception as exc:
            self._system_message(f"Package recommendation unavailable: {type(exc).__name__}")

    async def _preview_package_install(self, operation: str = "install") -> None:
        if self._package_review_open or self._package_mutation_busy:
            self.notify(
                "A package authorization or transaction is already in flight.",
                severity="warning",
            )
            return
        raw = self.query_one("#package-name", Input).value.strip()
        names = tuple(dict.fromkeys(raw.split()))
        if not names:
            self.notify("Enter one or more exact package names first.", severity="warning")
            return
        try:
            task = self.broker.capture_text(
                f"{operation} package " + " ".join(names),
                constraints=self.agent_coordinator.constraints(self._installation_specialist()),
                agent_id=(
                    self._installation_specialist().id
                    if self._installation_specialist() is not None
                    else None
                ),
                agent_version=(
                    self._installation_specialist().version
                    if self._installation_specialist() is not None
                    else None
                ),
            )
            assessment = self.broker.assess_deterministic_task(task)
            if assessment is None and task.package_plan is not None:
                assessment = self.broker.assess_catalog_package_task(task)
            admission = self.broker.admit(task)
            if (
                assessment is None
                or admission.route != AdmissionRoute.REGISTERED_MUTATION
                or task.package_plan is None
                or task.package_plan.operation.value != operation
                or task.package_plan.packages != names
            ):
                self.broker.transition(
                    task, TaskState.FAILED, reason="catalog_package_binding_failed"
                )
                raise RuntimeError("catalog package request did not produce an exact bound plan")
            previewer = (
                self.broker.preview_package_install
                if operation == "install"
                else self.broker.preview_package_remove
            )
            preview = await run_blocking_once(
                previewer,
                names,
                thread_name="jarvis-package-preview",
            )
            previous_task = self._package_preview_task
            if previous_task is not None and previous_task.state not in {
                TaskState.COMPLETED,
                TaskState.CANCELLED,
                TaskState.FAILED,
            }:
                self.broker.transition(
                    previous_task,
                    TaskState.CANCELLED,
                    reason="package_preview_superseded",
                )
            self._package_preview = preview
            self._package_preview_task = task
            details, _ = sanitize_terminal_text(
                json.dumps(preview, indent=2, sort_keys=True), limit=12_000
            )
            self._set_package_details(details)
            self._system_message(f"Package {operation} preview prepared; no package was changed.")
        except Exception as exc:
            code, message = _package_preview_diagnostic(exc)
            self._system_message(f"Package transaction preview unavailable ({code}): {message}")

    def _review_package_apply(self) -> None:
        preview = self._package_preview
        task = self._package_preview_task
        if self._package_review_open or self._package_mutation_busy:
            self.notify(
                "A package authorization or transaction is already in flight.",
                severity="warning",
            )
            return
        if (
            not preview
            or task is None
            or task.state != TaskState.AWAITING_APPROVAL
            or not preview.get("packages")
            or not preview.get("approval_digest")
        ):
            self.notify(
                "Create a fresh package preview before authorizing the transaction.",
                severity="warning",
            )
            return
        if not package_helper_available() or not package_helper_matches_bundle(self.bundle_root):
            self.notify(
                "The deployed root-owned package helper does not match this checkout. Run the package-helper installer first.",
                severity="error",
            )
            return
        names = tuple(str(value) for value in preview["packages"])
        operation = str(preview.get("operation", "install"))
        preview_text, _ = sanitize_terminal_text(str(preview.get("preview", "")), limit=8_000)
        raw_details = (
            f"Exact operation: {operation}\n"
            "Packages: " + ", ".join(names) + "\n\n"
            "Installed state: " + json.dumps(preview.get("pre_state", {}), sort_keys=True) + "\n"
            "Resolved installs: " + ", ".join(preview.get("affected_installs", ())) + "\n"
            "Resolved removals: " + ", ".join(preview.get("affected_removals", ())) + "\n"
            "Conflict/critical-package check: DNF transaction simulation passed\n\n"
            "Bounded DNF preview:\n" + preview_text + "\n\n"
            f"Approve to {operation} this exact transaction. Undo requires separate approval."
        )
        safe_details, _ = sanitize_terminal_text(raw_details, limit=12_000)
        self._package_review_open = True
        self.push_screen(
            PowerChangeReviewScreen(
                title=f"Review package {operation}",
                details=safe_details,
                confirm_label=f"Authorize {operation}",
            ),
            lambda confirmed: self._finish_package_review(bool(confirmed)),
        )

    def _reserve_exact_package_transaction(self, task: TaskRecord, preview: dict[str, Any]) -> None:
        """Consume one approval and reserve exactly one already-bound package plan."""
        self.broker.approve_package_transaction(task, preview)
        self.broker.reserve_package_execution(task, preview)

    async def _execute_reserved_package_transaction(
        self,
        task: TaskRecord,
        packages: tuple[str, ...],
        preview: dict[str, Any],
        *,
        thread_name: str,
    ) -> tuple[dict[str, Any] | None, tuple[bool, str, str] | None]:
        """Run the one reserved helper operation for every package UI route."""
        operation = str(preview.get("operation", "install"))
        executor = apply_transaction if operation == "install" else remove_transaction
        try:
            result = await run_blocking_once(
                executor,
                packages,
                str(preview["preview_digest"]),
                str(preview["approval_digest"]),
                thread_name=thread_name,
                cancellation="settle",
            )
        except Exception as exc:
            outcome = _package_execution_diagnostic(exc)
            if outcome[0]:
                try:
                    recovery = await run_blocking_once(
                        authoritative_status,
                        thread_name="jarvis-package-failure-status",
                    )
                    if recovery.get("record_status") == "none":
                        outcome = (
                            True,
                            "package_helper.no_recovery_record",
                            "The outcome remains indeterminate: no durable recovery record is visible. Reconcile the original helper process before preparing another attempt.",
                        )
                    recorded = {
                        str(value)
                        for value in recovery.get("packages", ())
                        if isinstance(value, str)
                    }
                    if recorded and recorded != set(packages):
                        outcome = (
                            True,
                            "package_helper.recovery_record_mismatch",
                            "The package helper outcome is indeterminate and its authoritative "
                            "recovery record does not match the requested package set. "
                            "Inspect the Packages recovery record before approving another transaction.",
                        )
                except Exception:
                    # A failed status read cannot safely refine the original
                    # indeterminate outcome and must not trigger a retry.
                    pass
            self.broker.complete_package_execution(
                task,
                status="indeterminate" if outcome[0] else "failed",
                error_code=outcome[1],
            )
            return None, outcome
        self.broker.complete_package_execution(
            task, status="completed", record_digest=result.get("record_digest")
        )
        return result, None

    def _finish_package_review(self, confirmed: bool) -> None:
        self._package_review_open = False
        preview = self._package_preview
        task = self._package_preview_task
        if preview is None or task is None:
            return
        if not confirmed:
            self.broker.transition(
                task, TaskState.CANCELLED, reason="catalog_package_transaction_declined"
            )
            self._package_preview = None
            self._package_preview_task = None
            self._system_message("Package authorization declined; the preview was invalidated.")
            return
        try:
            self._reserve_exact_package_transaction(task, preview)
        except Exception as exc:
            if task.state not in {
                TaskState.COMPLETED,
                TaskState.CANCELLED,
                TaskState.FAILED,
            }:
                self.broker.transition(
                    task, TaskState.FAILED, reason="catalog_package_reservation_failed"
                )
            self._package_preview = None
            self._package_preview_task = None
            self._system_message(
                f"Package authorization could not be reserved: {type(exc).__name__}"
            )
            return
        names = tuple(str(value) for value in preview["packages"])
        self._package_preview = None
        self._package_preview_task = None
        self._package_mutation_busy = True
        self.run_worker(
            self._execute_package_apply(names, preview, task),
            group="package-mutation",
            exclusive=True,
        )

    async def _execute_package_apply(
        self, names: tuple[str, ...], preview: dict[str, Any], task: TaskRecord
    ) -> None:
        operation = str(preview.get("operation", "install"))
        self.presentation.add_local_conversation(
            f"Authorization accepted. {operation.title()} transaction for {', '.join(names)}; waiting for the system privilege prompt.",
            status="running",
        )
        self._render_all()
        try:
            result, outcome = await self._execute_reserved_package_transaction(
                task, names, preview, thread_name="jarvis-package-apply"
            )
            if outcome is not None:
                _, code, message = outcome
                message = f"{message} (diagnostic={code})."
                self.presentation.add_local_conversation(
                    message,
                    status="failed",
                )
                self._system_message(message)
            else:
                assert result is not None
                self.presentation.add_local_conversation(
                    f"Package {operation} completed and verified: {', '.join(names)}. Refreshing the package inventory.",
                    status="completed",
                )
                self._system_message(
                    f"Package {operation} applied and verified; inventory refresh started."
                )
                self._set_package_details(json.dumps(result, indent=2, sort_keys=True))
                try:
                    await self._load_package_inventory(refresh=True)
                except Exception as exc:
                    self._system_message(
                        f"The package transaction completed, but inventory refresh failed: {type(exc).__name__}"
                    )
        finally:
            self._package_mutation_busy = False
            self._refresh_overview()
            self._render_all()

    async def _prepare_package_undo(self, checkpoint: ConversationCheckpoint | None = None) -> None:
        if self._package_review_open or self._package_mutation_busy:
            self.notify(
                "A package authorization or transaction is already in flight.",
                severity="warning",
            )
            return
        if not package_helper_available() or not package_helper_matches_bundle(self.bundle_root):
            self._system_message(
                "Package recovery is unavailable because the deployed root helper does not match this checkout. Run the package-helper installer first."
            )
            return
        try:
            record = await run_blocking_once(
                authoritative_status, thread_name="jarvis-package-undo-status"
            )
        except PackageControlClientError as exc:
            self._system_message(f"Package undo unavailable: {exc}")
            return
        if record.get("record_status") == "none":
            self._system_message("No package recovery record is pending; no rollback is available.")
            return
        packages = tuple(
            str(value) for value in record.get("rollback_packages", record.get("packages", ()))
        )
        record_digest = str(record["record_digest"])
        if checkpoint is not None:
            try:
                if (
                    self._checkpoint_recovery_binding(checkpoint) != record_digest
                    or record.get("record_status") != "applied"
                ):
                    raise ValueError("checkpoint receipt mismatch")
            except ValueError:
                self._system_message(
                    "Checkpoint recovery does not match the current package record; conversation preserved."
                )
                return
        attempt_id = self.broker.new_package_undo_attempt()
        prepared = record.get("record_status") == "prepared"
        details, _ = sanitize_terminal_text(
            "Packages: " + ", ".join(packages) + "\n"
            "authoritative record: "
            + record_digest
            + "\n\n"
            + (
                "This is an incomplete transaction record. Reconciliation first verifies that every "
                "bound package state is unchanged; only then does it clear the record."
                if prepared
                else "Rollback is a separate destructive operation and requires fresh authorization."
            ),
            limit=4_000,
        )
        self._package_review_open = True
        self.push_screen(
            PowerChangeReviewScreen(
                title="Review incomplete package recovery"
                if prepared
                else "Review package rollback",
                details=details,
                confirm_label="Authorize reconciliation" if prepared else "Authorize rollback",
            ),
            lambda confirmed: self._finish_package_undo_review(
                bool(confirmed), record_digest, len(packages), attempt_id, checkpoint
            ),
        )

    def _finish_package_undo_review(
        self,
        confirmed: bool,
        record_digest: str,
        package_count: int,
        attempt_id: str,
        checkpoint: ConversationCheckpoint | None = None,
    ) -> None:
        self._package_review_open = False
        if not confirmed:
            self._system_message("Package rollback authorization declined; nothing was changed.")
            return
        try:
            if checkpoint is not None and (
                self._checkpoint_work_active()
                or self._checkpoint_recovery_binding(checkpoint) != record_digest
            ):
                raise ValueError("checkpoint state changed")
            self.broker.reserve_package_undo(record_digest, package_count, attempt_id)
        except Exception as exc:
            self._system_message(
                f"Package rollback authorization could not be reserved: {type(exc).__name__}"
            )
            return
        self._package_mutation_busy = True
        self.run_worker(
            self._execute_package_undo(record_digest, checkpoint),
            group="package-mutation",
            exclusive=True,
        )

    async def _execute_package_undo(
        self, record_digest: str, checkpoint: ConversationCheckpoint | None = None
    ) -> None:
        restored = False
        before = self._later_mutation_events(checkpoint) if checkpoint is not None else ()
        try:
            result = await run_blocking_once(
                undo_transaction,
                record_digest,
                thread_name="jarvis-package-undo",
                cancellation="settle",
            )
        except Exception as exc:
            indeterminate, code, message = _package_rollback_diagnostic(exc)
            self.broker.complete_package_undo(
                record_digest,
                status="indeterminate" if indeterminate else "failed",
                error_code=code,
            )
            self._system_message(message)
        else:
            restored = True
            self.broker.complete_package_undo(record_digest, status="completed")
            if result.get("operation") == "reconcile":
                self._system_message(
                    "Incomplete package recovery record cleared after pre-state verification."
                )
            else:
                self._system_message("Package rollback applied and verified.")
            self._set_package_details(json.dumps(result, indent=2, sort_keys=True))
        finally:
            self._package_mutation_busy = False
            if restored and checkpoint is not None:
                after = self._later_mutation_events(checkpoint)
                if (
                    after[:-1] == before
                    and after[-1].get("event_type") == "package.rollback.completed"
                    and not (
                        self._submission_busy
                        or self.session.snapshot.active_turn_id
                        or self._operation_busy
                    )
                ):
                    self._restore_checkpoint_context(checkpoint)
                    self._live_activity.reset_context()
                    current = self.conversation_manager.get_current_conversation()
                    if current is not None:
                        self._queue_conversation_persistence(current)
                else:
                    self._system_message(
                        "Package recovery succeeded, but other work changed; conversation preserved."
                    )
            self._render_all()

    async def _prepare_package_archive(self) -> None:
        if self._package_review_open or self._package_mutation_busy:
            self.notify(
                "A package authorization or transaction is already in flight.",
                severity="warning",
            )
            return
        if not package_helper_available() or not package_helper_matches_bundle(self.bundle_root):
            self._system_message(
                "Package archive is unavailable because the deployed root helper does not match this checkout. Run the package-helper installer first."
            )
            return
        try:
            record = await run_blocking_once(
                authoritative_status, thread_name="jarvis-package-archive-status"
            )
        except PackageControlClientError as exc:
            self._system_message(f"Package archive unavailable: {exc}")
            return
        if not record.get("archive_allowed"):
            self._system_message(
                "Only an applied rollback record may be archived; inspect incomplete recovery instead."
            )
            return
        record_digest = str(record["record_digest"])
        packages = tuple(
            str(value) for value in record.get("rollback_packages", record.get("packages", ()))
        )
        attempt_id = self.broker.new_package_archive_attempt()
        details, _ = sanitize_terminal_text(
            "Packages: " + ", ".join(packages) + "\n"
            "authoritative record: " + record_digest + "\n\n"
            "Archive permanently disables rollback for this older transaction. No DNF command will run. "
            "The root-owned archival copy is sealed before the active record is cleared.",
            limit=4_000,
        )
        self._package_review_open = True
        self.push_screen(
            PowerChangeReviewScreen(
                title="Archive old package rollback record",
                details=details,
                confirm_label="Archive record",
            ),
            lambda confirmed: self._finish_package_archive_review(
                bool(confirmed), record_digest, len(packages), attempt_id
            ),
        )

    def _finish_package_archive_review(
        self,
        confirmed: bool,
        record_digest: str,
        package_count: int,
        attempt_id: str,
    ) -> None:
        self._package_review_open = False
        if not confirmed:
            self._system_message("Package rollback record was not archived.")
            return
        try:
            self.broker.reserve_package_archive(record_digest, package_count, attempt_id)
        except Exception as exc:
            self._system_message(
                f"Package archive authorization could not be reserved: {type(exc).__name__}"
            )
            return
        self._package_mutation_busy = True
        self.run_worker(
            self._execute_package_archive(record_digest),
            group="package-mutation",
            exclusive=True,
        )

    async def _execute_package_archive(self, record_digest: str) -> None:
        try:
            result = await run_blocking_once(
                archive_transaction,
                record_digest,
                thread_name="jarvis-package-archive",
                cancellation="settle",
            )
        except Exception as exc:
            self.broker.complete_package_archive(
                record_digest, status="failed", error_code="package_archive_failed"
            )
            self._system_message(
                "Package rollback archive failed before any DNF operation "
                f"(package_archive.{type(exc).__name__.casefold()})."
            )
        else:
            self.broker.complete_package_archive(record_digest, status="completed")
            self._system_message(
                "Old package rollback record archived; new package transactions are unblocked."
            )
            self._set_package_details(json.dumps(result, indent=2, sort_keys=True))
        finally:
            self._package_mutation_busy = False
            self._render_all()

    def action_focus_composer(self) -> None:
        self.query_one("#composer", Input).focus()

    def action_cancel_turn(self) -> None:
        if self.session.snapshot.active_turn_id:
            self.run_worker(self._cancel_turn(), group="turn-cancel", exclusive=True)
        elif self._submission_busy:
            task = (
                self.broker.task(self._submission_task_id)
                if self._submission_task_id is not None
                else None
            )
            if task is not None and task.state in {
                TaskState.APPROVED,
                TaskState.EXECUTING,
            }:
                self._system_message(
                    "The approved one-attempt mutation is already reserved and cannot be cancelled or replayed."
                )
                self._render_submission_projection()
                return
            if isinstance(self.screen, PowerChangeReviewScreen):
                self.screen.dismiss(False)
                return
            self._submission_cancel_requested = True
            worker = self._active_submission_worker
            if worker is not None:
                worker.cancel()
            self._system_message("Submission cancellation requested; no task will be replayed.")
            self._render_submission_projection()

    async def _cancel_turn(self) -> None:
        try:
            await self.session.interrupt()
            self._system_message("Turn interruption requested.")
        except Exception as exc:
            self._system_message(f"Turn interruption failed safely: {type(exc).__name__}")
        self._render_all()

    def _render_live_activity(self) -> None:
        value = self._live_activity.text()
        if value != self._live_activity_text:
            self._live_activity_text = value
            try:
                self.query_one("#live-activity", Static).update(value)
            except Exception:
                pass

    def _on_codex_event(self, event: NormalizedEvent) -> None:
        """Handle incoming codex events with throttled rendering."""
        import time

        self._live_activity.update(event)
        if event.kind == "agent_streaming":
            return

        # Retain all deltas; only UI rendering is throttled.
        if event.kind == "agent_delta":
            if not hasattr(self, "_agent_delta_count"):
                self._agent_delta_count = 0
                self._agent_streaming = False
                self._last_agent_delta_time = 0.0
                self._streaming_end_time = 0.0

            self._agent_delta_count += 1

            # Track streaming state for the first delta
            if not self._agent_streaming:
                self._agent_streaming = True

            self._last_agent_delta_time = time.time()

            # Preserve every fragment; the render scheduler bounds UI refreshes.

        # Handle end of streaming
        if event.kind == "agent_message":
            # Final message received, streaming done
            if self._agent_streaming:
                # Set cooldown timestamp to prevent render flood after streaming
                self._streaming_end_time = time.time()
            self._agent_streaming = False
            self._agent_delta_count = 0
            if event.text:
                self._ingest_agent_power_draft(event.text)
                self._ingest_agent_github_plan(event.text)
                if self._agent_requested_power_activation(event.text):
                    self.run_worker(
                        self._review_agent_power_activation(),
                        group="power-agent-approval",
                        exclusive=True,
                    )
        elif event.kind in ("turn_completed", "turn_cancelled"):
            # Turn ended, definitely not streaming
            if self._agent_streaming:
                self._streaming_end_time = time.time()
            self._agent_streaming = False
            self._agent_delta_count = 0

        if self._active_specialist is not None:
            self.presentation.set_activity_owner(self._active_specialist.display_name)
        self.presentation.apply_event(event)
        if event.kind == "server_request" and event.request_id is not None:
            pending = self.session.snapshot.pending_requests.get(event.request_id)
            if pending and pending.request_type in {
                "item/commandExecution/requestApproval",
                "item/fileChange/requestApproval",
            }:
                task = self.broker.task(pending.task_id) if pending.task_id else None
                assessment = task.assessment if task else None
                details = "\n".join(
                    (
                        f"operation: {assessment.operation if assessment else 'unknown'}",
                        f"risk: {assessment.risk if assessment else 'unknown'}",
                        f"targets: {list(assessment.targets) if assessment else []}",
                        f"command: {pending.command or '(file change)'}",
                        f"cwd: {pending.cwd or self.bundle_root}",
                        f"reason: {pending.reason or 'not supplied'}",
                        "decision applies once; session-wide approval is unavailable",
                    )
                )
                self.push_screen(
                    CodexApprovalReviewScreen(details, allow_approve=self._danger_full_access),
                    lambda decision, request_id=event.request_id: self.run_worker(
                        self._answer_codex_approval(request_id, decision),
                        group="codex-approval",
                        exclusive=True,
                    ),
                )
            elif pending and pending.request_type == "mcpServer/elicitation/request":
                details = "\n".join(
                    value
                    for value in (
                        f"server: {event.metadata.get('server_name') or 'unknown'}",
                        f"mode: {event.metadata.get('mode') or 'unknown'}",
                        f"message: {event.metadata.get('message') or 'No message supplied.'}",
                        f"URL: {event.metadata.get('url')}" if event.metadata.get("url") else None,
                        "This is an MCP request only; it does not authorize host mutation.",
                    )
                    if value
                )
                self.push_screen(
                    McpElicitationReviewScreen(details),
                    lambda action, request_id=event.request_id: self.run_worker(
                        self._answer_mcp_elicitation(request_id, action),
                        group="mcp-elicitation",
                        exclusive=True,
                    ),
                )
        for task_id in tuple(self.presentation.admissions):
            task = self.broker.task(task_id)
            if task:
                self.presentation.update_task_status(task)

        self._refresh_overview()

        # A completed item can carry the same text length as item/started.
        # Paint terminal agent state immediately so a status-only transition
        # cannot be hidden behind the streaming cooldown/hash optimization.
        terminal_agent_message = event.kind == "agent_message" and event.status in {
            "completed",
            "done",
            "failed",
            "cancelled",
        }
        if terminal_agent_message or event.kind in {"turn_completed", "turn_cancelled"}:
            if self._pending_timer is not None:
                self._pending_timer.stop()
                self._pending_timer = None
            self._render_pending = False
            self._do_throttled_render()
            return

        # Throttle rendering to avoid UI freezing during event floods
        self._schedule_throttled_render()

    async def _answer_mcp_elicitation(self, request_id: str | int, action: str) -> None:
        try:
            await self.session.respond_to_mcp_elicitation(request_id, action)
            self._system_message(f"MCP request decision: {action}.")
        except Exception as exc:
            self._system_message(f"MCP request response failed safely: {type(exc).__name__}.")
        self._refresh_overview()
        self._render_all()

    def _ingest_agent_power_draft(self, text: str) -> None:
        """Accept only a validated, non-mutating draft emitted by Power Expert."""
        match = re.search(
            r"<jarvis_power_profile_draft>(.*?)</jarvis_power_profile_draft>",
            text,
            flags=re.DOTALL,
        )
        if match is None:
            return
        try:
            payload = json.loads(match.group(1))
            profile_value = payload["profile"] if isinstance(payload, dict) else payload
            profile = PowerProfile(
                str(profile_value["profile_id"]),
                str(profile_value["name"]),
                str(profile_value["goal"]),
                {str(key): dict(value) for key, value in profile_value["variants"].items()},
                int(profile_value.get("version", 1)),
                str(profile_value.get("profile_digest", "")),
            )
            self._power_profile_plan = PowerProfilePlan(profile)
            self._render_power_profile_plan()
            self._show_view("power")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            self._system_message(
                "Power Expert draft marker was rejected; no configuration was staged."
            )

    def _ingest_agent_github_plan(self, text: str) -> None:
        """Open one exact GitHub operation review emitted by GitHub Agent."""
        match = re.search(
            r"<jarvis_github_operation_plan>(.*?)</jarvis_github_operation_plan>",
            text,
            flags=re.DOTALL,
        )
        if match is None:
            return
        try:
            payload = json.loads(match.group(1))
            operation_id = payload.get("operation_id") or payload.get("id")
            if not isinstance(operation_id, str):
                raise ValueError("operation_id_missing")
            plan = self.operation_workflow.load(operation_id)
            if plan.get("domain") != "github":
                raise ValueError("operation_domain_mismatch")
            if (
                self._active_specialist is None
                or self._active_specialist.id != "jarvis-github-agent"
                or plan.get("target") != str(self.bundle_root.resolve())
            ):
                raise ValueError("operation_scope_mismatch")
            self.push_screen(
                OperationReview(plan),
                lambda decision, operation_id=operation_id: self._operation_decision(
                    operation_id, decision
                ),
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            self._system_message(
                "GitHub operation plan marker was rejected; no repository change was staged."
            )

    async def _review_agent_power_activation(self) -> None:
        """Turn an agent proposal into the existing exact user review modal."""
        if self._power_profile_plan is None:
            self._system_message(
                "Power Expert requested activation without a validated draft; nothing was changed."
            )
            return
        if self._power_inventory is None:
            await self._load_power_inventory()
        self._review_power_profile()

    def _agent_requested_power_activation(self, text: str) -> bool:
        match = re.search(
            r"<jarvis_power_profile_activation_request>(.*?)</jarvis_power_profile_activation_request>",
            text,
            flags=re.DOTALL,
        )
        if match is None or self._power_profile_plan is None:
            return False
        try:
            value = json.loads(match.group(1))
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        return (
            isinstance(value, dict)
            and value.get("profile_digest") == self._power_profile_plan.profile.profile_digest
        )

    async def _answer_codex_approval(self, request_id: str | int, decision: str | None) -> None:
        try:
            final_decision = decision or "cancel"
            await self.session.respond_to_approval(request_id, final_decision)
            self._system_message(f"Codex operation decision: {final_decision}.")
        except Exception as exc:
            self._system_message(f"Approval failed safely: {type(exc).__name__}.")
        self._refresh_overview()
        self._render_all()

    def _is_streaming(self) -> bool:
        """Check if agent is actively streaming a response."""
        import time

        # If we received an agent_delta in the last 2 seconds, consider it streaming
        # This handles the case where deltas stop briefly but turn isn't complete yet
        if self._agent_streaming:
            time_since_last_delta = time.time() - self._last_agent_delta_time
            if time_since_last_delta < 2.0:
                return True
            else:
                # Timeout - no delta for 2 seconds, assume streaming stopped
                self._agent_streaming = False
                return False

        return False

    def _schedule_throttled_render(self) -> None:
        """Schedule a render, with longer throttle during streaming to reduce UI load."""
        if not hasattr(self, "_render_pending"):
            self._render_pending = False
            self._last_render_time = 0.0
            self._streaming_end_time = 0.0
            self._pending_timer = None

        import time

        current_time = time.time()
        time_since_last_render = current_time - self._last_render_time
        time_since_streaming_end = current_time - self._streaming_end_time

        # Use longer throttle during streaming to reduce UI load
        # Also use longer throttle for 3 seconds after streaming ends to prevent render flood
        is_streaming = self._is_streaming()
        in_post_streaming_cooldown = time_since_streaming_end < 3.0

        if is_streaming:
            throttle_seconds = 0.5
        elif in_post_streaming_cooldown:
            throttle_seconds = 1.0  # Longer throttle to prevent post-streaming render spam
        else:
            throttle_seconds = 0.15

        # If we rendered recently, schedule a delayed render (but cancel any existing timer first)
        if time_since_last_render < throttle_seconds:
            if not self._render_pending:
                self._render_pending = True
                # Cancel any existing timer to avoid multiple scheduled renders
                if self._pending_timer is not None:
                    self._pending_timer.stop()
                # Schedule render after throttle period
                self._pending_timer = self.set_timer(
                    throttle_seconds - time_since_last_render, self._do_throttled_render
                )
            # Else: render already pending, don't schedule another
        elif time_since_last_render >= throttle_seconds:
            # Enough time has passed, render immediately
            # Cancel any pending timer first
            if self._pending_timer is not None:
                self._pending_timer.stop()
                self._pending_timer = None
            self._do_throttled_render()

    def _do_throttled_render(self) -> None:
        """Execute the actual render and update timing."""
        import time

        self._last_render_time = time.time()
        self._render_pending = False
        self._pending_timer = None
        self._render_all()

    async def _dispatch_task(self, task: TaskRecord) -> None:
        try:
            if self._operation_busy:
                raise RuntimeError("registered_operation_in_progress")
            await asyncio.sleep(0)
            if self._submission_cancel_requested:
                raise asyncio.CancelledError
            if task.state == TaskState.CAPTURED:
                self.broker.transition(
                    task,
                    TaskState.RESOLVING_INTENT,
                    reason="submission_intent_resolution_started",
                )
            if task.action is not None:
                assessment = self.broker.assess_registered_task(task)
            else:
                package_query = self._package_catalog_query(task)
                if package_query is not None:
                    assessment = IntentAssessment(
                        assessment_id=self.broker.identifier("assessment"),
                        decision=AssessmentDecision.EXECUTE,
                        intent_class=IntentClass.INSPECT,
                        operation="Installation Specialist package inspection",
                        targets=("package-catalog",),
                        risk=0,
                        route=ExecutionRoute.CONVERSATION,
                        reason="selected package-capable specialist owns package inspection and explanation through typed tools",
                    )
                elif task.agent_id == "jarvis-power-expert" and _is_power_expert_request(
                    task.intent.text
                ):
                    # Power Expert owns clarification, recommendation, and
                    # explanation. Python supplies typed tools; it must not
                    # decide the user's goal from keywords before the agent
                    # sees the request and current evidence.
                    assessment = IntentAssessment(
                        assessment_id=self.broker.identifier("assessment"),
                        decision=AssessmentDecision.EXECUTE,
                        intent_class=IntentClass.INSPECT,
                        operation="Power Expert agent workflow",
                        targets=("power-expert",),
                        risk=0,
                        route=ExecutionRoute.CONVERSATION,
                        reason="Power Expert owns Power decisions through typed tools",
                    )
                else:
                    assessment = self.broker.assess_deterministic_task(task)
                if assessment is None:
                    if not self.enable_live_turns:
                        raise RuntimeError("live_turns_disabled")
                    if self.session.snapshot.connection != ConnectionState.READY:
                        raise RuntimeError(f"app_server_{self.session.snapshot.connection.value}")
                    preflight_kwargs = (
                        {"record_assessment": False}
                        if getattr(self.session.preflight_task, "__func__", None)
                        is AppServerSessionController.preflight_task
                        else {}
                    )
                    assessment = await self.session.preflight_task(
                        task,
                        self.presentation.context_snapshot(exclude_task_id=task.task_id),
                        **preflight_kwargs,
                    )
            assessment = self.broker.bind_agent_package_assessment(task, assessment)
            if task.assessment is None:
                self.broker.record_assessment(task, assessment)
            self.presentation.apply_assessment(task)
            if assessment.decision == AssessmentDecision.CLARIFY:
                self._pending_clarification = task
                return
            admission = self.broker.admit(task)
            self.presentation.apply_admission(task, admission)
            if admission.route == AdmissionRoute.REGISTERED_MUTATION:
                self.presentation.add_agent_package_handoff(task)
            if admission.route == AdmissionRoute.BLOCKED:
                self.presentation.update_task_status(task)
                return
            if admission.route == AdmissionRoute.LOCAL_READ:
                await self._run_local_task(task)
                return
            if admission.route == AdmissionRoute.LOCAL_MUTATION:
                plan = task.local_mutation_plan
                review = task.mutation_review
                if plan is None or review is None:
                    raise RuntimeError("local mutation admission has no reviewed plan")
                review_text, _ = sanitize_terminal_text(review.summary, limit=4_000)
                confirmed = await self.push_screen_wait(
                    PowerChangeReviewScreen(
                        title="Review exact filesystem change",
                        details=review_text,
                        confirm_label="Approve once",
                    )
                )
                if not confirmed:
                    self.broker.transition(
                        task, TaskState.CANCELLED, reason="local_mutation_declined"
                    )
                    self.presentation.mark_local_mutation_declined(task)
                    return
                approval = self.broker.create_local_mutation_approval(task)
                self.presentation.mark_local_mutation_approved(task)
                result = await self.broker.execute_local_filesystem_mutation(task, approval)
                self.presentation.set_local_mutation_result(task, result)
                self._show_view("conversation")
                return
            if admission.route == AdmissionRoute.REGISTERED_MUTATION:
                await self._run_package_submission(task)
                return
            if self.session.snapshot.active_turn_id:
                raise RuntimeError("wait for the active turn before submitting another request")
            await self.session.prepare_conversation_context(
                self.presentation.context_snapshot(exclude_task_id=task.task_id)
            )
            turn_id = await self.session.start_turn(task)
            # turn/start returned a turn id, so the current user/action entry
            # is already model-visible. Record it before waiting for a final
            # status to prevent failed or interrupted turns being reinjected.
            self.session.acknowledge_model_context(self.presentation.context_snapshot())
            self._system_message(f"Started scoped turn {turn_id}.")
            status = await self.session.wait_for_turn(turn_id, task)
            self.presentation.update_task_status(task)
            self.presentation.mark_task_terminal(task, f"agent turn {status}")
            self.session.acknowledge_model_context(self.presentation.context_snapshot())
            try:
                await self.session.compact_if_needed()
            except AppServerError as exc:
                self._system_message(f"Context compaction unavailable: {type(exc).__name__}")
        except ConversationContextSyncError as exc:
            if task.state not in {
                TaskState.COMPLETED,
                TaskState.CANCELLED,
                TaskState.FAILED,
            }:
                self.broker.transition(task, TaskState.FAILED, reason=exc.code)
            self.presentation.mark_context_sync_failure(task, exc.code)
        except PreflightClassifierError as exc:
            if exc.code == "preflight.cancelled":
                self.presentation.mark_task_terminal(task, exc.code)
            else:
                self.presentation.mark_classifier_failure(task, exc.code, exc.category)
                self._system_message(
                    "Intent classification failed safely "
                    f"({exc.code}; category={exc.category}); this was not a policy denial."
                )
        except asyncio.CancelledError:
            if task.state not in {
                TaskState.COMPLETED,
                TaskState.CANCELLED,
                TaskState.FAILED,
            }:
                self.broker.transition(task, TaskState.CANCELLED, reason="submission_cancelled")
            self.presentation.mark_task_terminal(task, "submission cancelled; no replay")
            raise
        except Exception as exc:
            if task.state not in {
                TaskState.COMPLETED,
                TaskState.CANCELLED,
                TaskState.FAILED,
            }:
                self.broker.transition(task, TaskState.FAILED, reason="task_dispatch_failed")
            if "capacity" in str(exc).casefold() or self.session.snapshot.connection == ConnectionState.CAPACITY_LIMITED:
                self._system_message(
                    "Codex capacity is currently limited; no model turn was submitted. "
                    "Wait for the reset time shown in SESSION capacity."
                )
            else:
                self._system_message(
                    f"Task dispatch failed safely (task_dispatch.{type(exc).__name__.casefold()}); "
                    "no task was replayed."
                )
            self.presentation.mark_task_terminal(task, "task_dispatch_failed")
        finally:
            self.presentation.update_task_status(task)
            if self._submission_task_id == task.task_id:
                self._submission_busy = False
                self._submission_task_id = None
                self._active_submission_worker = None
                self._submission_cancel_requested = False
            self._refresh_overview()
            self._render_all()

    async def _run_local_task(self, task: TaskRecord) -> None:
        if task.power_profile_plan is not None:
            await self._run_power_profile_draft(task)
            return
        catalog_query = self._package_catalog_queries.pop(task.task_id, None)
        if catalog_query is not None:
            await self._run_installation_catalog_query(task, catalog_query)
            return
        if task.local_read_plan is not None:
            result = await self.broker.execute_local_filesystem_read(task)
            self.presentation.set_local_read_result(task, result)
            self._show_view("conversation")
            return
        if not task.action or task.action.id != "knowledge.search":
            self.broker.transition(task, TaskState.BLOCKED, reason="unknown_local_task_route")
            self.presentation.update_task_status(task)
            return
        kind = str(task.intent.parameters["kind"])
        query = str(task.intent.parameters["query"])
        try:
            results = self.broker.query_knowledge(kind, query, 20)
            self.presentation.set_knowledge_results(kind, query, results)
            self.broker.transition(task, TaskState.COMPLETED, reason="local_read_completed")
            self._show_view("knowledge")
        except Exception as exc:
            self.presentation.set_knowledge_error(kind, query, exc)
            self.broker.transition(task, TaskState.FAILED, reason="local_read_failed")
        self.presentation.update_task_status(task)

    async def _run_power_profile_draft(self, task: TaskRecord) -> None:
        draft = task.power_profile_plan
        if draft is None:
            return
        if self._power_inventory is None:
            try:
                self._power_inventory = await run_blocking_once(
                    scan_power_inventory, thread_name="jarvis-power-profile-inventory"
                )
                self._power_telemetry = self._power_inventory.telemetry
            except Exception as exc:
                self.broker.transition(
                    task, TaskState.FAILED, reason="power_profile_inventory_failed"
                )
                self.presentation.add_local_conversation(
                    f"Power profile planning could not inspect the current inventory ({type(exc).__name__}).",
                    "failed",
                    task_id=task.task_id,
                )
                self.presentation.update_task_status(task)
                return
        try:
            plan = plan_power_profile(
                name=draft.name,
                goal=draft.goal,
                inventory=self._power_inventory,
                profile_id=draft.plan_id,
                scope=draft.scope,
            )
            self._power_profile_plan = plan
            self.query_one("#power-profile-name", Input).value = draft.name
            self.query_one("#power-profile-goal", Select).value = draft.goal
            self._render_power_profile_plan()
            self.broker.transition(
                task, TaskState.COMPLETED, reason="power_profile_draft_completed"
            )
            self.presentation.add_local_conversation(
                f"Power profile draft ready: {draft.name} ({draft.scope}). "
                "No power setting was changed. Review it in the Power tab; activation requires one exact approval.",
                "completed",
                task_id=task.task_id,
            )
            self._show_view("power")
        except Exception as exc:
            self.broker.transition(task, TaskState.FAILED, reason="power_profile_draft_failed")
            self.presentation.add_local_conversation(
                f"Power profile draft could not be prepared ({type(exc).__name__}); no setting was changed.",
                "failed",
                task_id=task.task_id,
            )
        self.presentation.update_task_status(task)

    def _package_catalog_query(self, task: TaskRecord) -> str | None:
        """Recognize bounded package inspection for package-capable specialists."""
        if (
            task.agent_id
            not in {
                "jarvis-installation-specialist",
                "jarvis-power-expert",
            }
            or not task.intent.text
        ):
            return None
        text = task.intent.text.strip()
        lowered = text.casefold()
        if self.broker.package_mutation_planner.recognizes(text):
            return None
        if "package" not in lowered and "rpm" not in lowered and "paquete" not in lowered:
            return None
        inspection_signals = (
            "paquetes disponibles",
            "paquetes instalados",
            "buscar paquetes",
            "busca paquetes",
            "qué paquetes",
            "que paquetes",
            "hay paquetes",
            "available package",
            "available packages",
            "search package",
            "search packages",
            "find package",
            "find packages",
            "list package",
            "list packages",
            "check package",
            "check packages",
            "packages related",
            "package related",
        )
        if task.agent_id == "jarvis-power-expert" and any(
            phrase in lowered
            for phrase in ("power management", "battery", "energy management", "power package")
        ):
            return text
        return text if any(signal in lowered for signal in inspection_signals) else None

    async def _run_installation_catalog_query(self, task: TaskRecord, query: str) -> None:
        """Search only the cached/local Fedora catalog through the read-only control adapter."""
        inspector = getattr(self.broker.local_control, "inspect_packages", None)
        if not callable(inspector):
            self.broker.transition(
                task, TaskState.FAILED, reason="package_catalog_inspector_unavailable"
            )
            self.presentation.add_local_conversation(
                "The Installation Specialist's cached package-catalog inspector is unavailable in "
                "this session. No shell, network, or package operation was attempted.",
                "failed",
                task_id=task.task_id,
            )
            self.presentation.update_task_status(task)
            return
        try:
            result = await run_blocking_once(
                inspector,
                query,
                call_kwargs={"refresh": True},
                thread_name="jarvis-installation-catalog-search",
            )
        except Exception as exc:
            self.broker.transition(
                task, TaskState.FAILED, reason="package_catalog_inspection_failed"
            )
            self.presentation.add_local_conversation(
                "The cached Fedora package-catalog search could not be completed "
                f"({type(exc).__name__}); no package was changed.",
                "failed",
                task_id=task.task_id,
            )
            self.presentation.update_task_status(task)
            return
        if not isinstance(result, dict) or not result.get("available"):
            self.broker.transition(task, TaskState.FAILED, reason="package_catalog_unavailable")
            self.presentation.add_local_conversation(
                "The cached Fedora package catalog is unavailable. No shell, network, or package "
                "operation was attempted.",
                "failed",
                task_id=task.task_id,
            )
            self.presentation.update_task_status(task)
            return
        matches = [item for item in result.get("matches", ()) if isinstance(item, dict)]
        available = [item for item in matches if item.get("state") == "available"]
        visible = available or matches
        lines = [
            "Cached Fedora package catalog search (read-only).",
            f"Query: {query}",
            f"Catalog: {result.get('installed_count', 0)} installed / "
            f"{result.get('available_count', 0)} cached available packages.",
        ]
        if result.get("stale"):
            lines.append(
                "Freshness: prior cached catalog used because the read-only refresh was incomplete."
            )
        if not visible:
            lines.append("No matching package roots were found in the bounded cached catalog.")
        else:
            lines.append("Matches:")
            for item in visible[:24]:
                state = str(item.get("state", "unknown"))
                name = str(item.get("name", "unknown"))
                summary = str(item.get("summary", "no summary"))
                origin = str(item.get("origin", item.get("repository", "unknown")))
                lines.append(f"- {name} [{state}; {origin}] — {summary}")
        if task.agent_id == "jarvis-power-expert" and visible:
            self._pending_package_handoff = {"query": query, "matches": visible[:24]}
            lines.extend(
                (
                    "",
                    "Pending handoff: select Installation Specialist to evaluate exact package "
                    "or group roots. No package preview or mutation was started.",
                )
            )
        self.broker.transition(task, TaskState.COMPLETED, reason="package_catalog_search_completed")
        self.presentation.add_local_conversation(
            "\n".join(lines), "completed", task_id=task.task_id
        )
        self.presentation.update_task_status(task)

    async def _run_package_submission(self, task: TaskRecord) -> None:
        plan = task.package_plan
        if plan is None:
            raise RuntimeError("registered package route requires a typed plan")
        if not package_helper_available() or not package_helper_matches_bundle(self.bundle_root):
            self.broker.transition(task, TaskState.FAILED, reason="package_helper_unavailable")
            self.presentation.set_package_mutation_result(
                task,
                "The deployed root-owned package helper does not match this checkout; nothing was changed. Run the package-helper installer first.",
                "failed",
            )
            return
        try:
            previewer = (
                self.broker.preview_package_install
                if plan.operation.value == "install"
                else self.broker.preview_package_remove
            )
            preview = await run_blocking_once(
                previewer,
                plan.packages,
                thread_name="jarvis-package-natural-language-preview",
            )
        except Exception as exc:
            self.broker.transition(task, TaskState.FAILED, reason="package_preview_failed")
            code, message = _package_preview_diagnostic(exc)
            self.broker.record_package_preview_failure(task, code, type(exc).__name__, exc)
            self.presentation.mark_package_preview_failure(task, code)
            self.presentation.set_package_mutation_result(
                task,
                f"The package transaction could not be previewed safely ({code}): {message} Nothing was changed.",
                "failed",
            )
            return
        preview_text, _ = sanitize_terminal_text(str(preview.get("preview", "")), limit=8_000)
        details = (
            f"Exact DNF operation: {plan.operation.value}\n"
            f"Requested DNF roots: {', '.join(plan.packages)}\n"
            f"Resolved installs: {', '.join(preview.get('affected_installs', ())) or 'none'}\n"
            f"Resolved removals: {', '.join(preview.get('affected_removals', ())) or 'none'}\n"
            f"Rollback: {plan.rollback}\n\n"
            "Resolved transaction preview (bounded):\n"
            f"{preview_text}\n\nApproval applies once to this exact preview."
        )
        confirmed = await self.push_screen_wait(
            PowerChangeReviewScreen(
                title=f"Review package {plan.operation.value}",
                details=details,
                confirm_label="Approve once",
            )
        )
        if not confirmed:
            self.broker.transition(task, TaskState.CANCELLED, reason="package_transaction_declined")
            self.presentation.set_package_mutation_result(
                task,
                "The package transaction was not approved; nothing was changed.",
                "cancelled",
            )
            return
        try:
            self._reserve_exact_package_transaction(task, preview)
        except Exception as exc:
            self.broker.transition(task, TaskState.FAILED, reason="package_reservation_failed")
            self.presentation.set_package_mutation_result(
                task,
                f"Package approval could not be reserved (package_reservation.{type(exc).__name__.casefold()}).",
                "failed",
            )
            return
        self.presentation.mark_package_mutation_approved(task)
        result, outcome = await self._execute_reserved_package_transaction(
            task,
            plan.packages,
            preview,
            thread_name="jarvis-package-natural-language-execution",
        )
        if outcome is not None:
            self.presentation.set_package_mutation_result(
                task, f"{outcome[2]} (diagnostic={outcome[1]}).", "failed"
            )
            return
        assert result is not None
        self.presentation.set_package_mutation_result(
            task,
            f"Package {plan.operation.value} completed and verified for: {', '.join(plan.packages)}.",
            "completed",
        )
        self._set_package_details(json.dumps(result, indent=2, sort_keys=True))
        try:
            await self._load_package_inventory(refresh=True)
        except Exception as exc:
            self._system_message(
                f"The package transaction completed, but inventory refresh failed: {type(exc).__name__}"
            )

    def _submit_composer(self) -> None:
        if self._submission_busy:
            self._system_message(
                "A submission is already in flight; this draft was preserved and was not queued."
            )
            self._render_submission_projection()
            return
        composer = self.query_one("#composer", Input)
        text = composer.value.strip()
        # Clipboard/paste paths can duplicate a complete prompt back-to-back.
        # Collapse only an exact two-halves repetition; ordinary repeated words
        # or intentionally duplicated sections remain untouched.
        if len(text) >= 2 and len(text) % 2 == 0:
            midpoint = len(text) // 2
            if text[:midpoint] == text[midpoint:]:
                text = text[:midpoint].strip()
        if not text:
            self._system_message("Enter a request before sending it.")
            self._render_all()
            return
        display_text: str | None = None
        if self._pending_clarification is not None:
            pending = self._pending_clarification
            original = pending.intent.text or ""
            entered_text = text
            choice = text.strip().casefold()
            option_text = None
            if pending.assessment is not None and choice in {
                "1",
                "2",
                "3",
                "option 1",
                "option 2",
                "option 3",
                "opcion 1",
                "opcion 2",
                "opcion 3",
                "opción 1",
                "opción 2",
                "opción 3",
            }:
                index = int(choice[-1]) - 1
                options = pending.assessment.clarification_options
                if 0 <= index < len(options):
                    option_text = options[index]
            if self.broker.package_mutation_planner.recognizes(text):
                # A fresh mechanical package command must not be appended to
                # an unrelated question such as a greeting clarification.
                self.broker.transition(
                    pending,
                    TaskState.CANCELLED,
                    reason="clarification_superseded_by_package_request",
                )
                self.presentation.update_task_status(pending)
            elif (
                pending.assessment is not None
                and pending.assessment.operation == "clarify exact package transaction"
            ):
                replacement = self.broker.package_mutation_planner.continuation_text(original, text)
                # An option number is not a package name. Keep this request on
                # the deterministic route rather than feeding concatenated
                # prose to model preflight.
                text = replacement if replacement is not None else original
            else:
                text = f"{original}\n\nUser clarification: {option_text or entered_text}"
            # The original request is already visible as the pending task entry.
            # Keep only this answer in the new user-facing projection; the
            # combined continuation remains the agent's internal task text.
            display_text = f"User clarification: {option_text or entered_text}"
            self._pending_clarification = None
        try:
            constraints = self.agent_coordinator.constraints(self._active_specialist)
            task = self.broker.capture_text(
                text,
                constraints=constraints,
                agent_id=self._active_specialist.id if self._active_specialist else None,
                agent_version=self._active_specialist.version if self._active_specialist else None,
            )
        except ValueError as exc:
            self._system_message(f"Input rejected: {exc}")
            self._render_all()
            return
        self._last_user_input = display_text or text
        composer.value = ""
        self._start_task_submission(task, display_text=display_text)

    def _start_task_submission(self, task: TaskRecord, *, display_text: str | None = None) -> None:
        if self._submission_busy:
            self._system_message(
                "A submission is already in flight; the additional task was rejected."
            )
            self._render_submission_projection()
            return
        if self._active_specialist is not None and task.agent_id is not None:
            try:
                self.session.bind_specialist(task, self._active_specialist)
            except AppServerError:
                self.query_one("#composer", Input).value = getattr(
                    self, "_last_user_input", ""
                ) or (task.intent.text or "")
                self._system_message(
                    "The session or specialist changed before admission. Your request remains editable."
                )
                return
        self._submission_busy = True
        self._submission_task_id = task.task_id
        self._submission_cancel_requested = False
        self.presentation.capture_pending_task(task, display_text=display_text)
        self._create_user_checkpoint(task)
        self._show_view("conversation")
        self._render_submission_projection()
        self.call_after_refresh(self._queue_task, task)

    def _capture_selected_action(self, action_id: str, parameters: dict[str, Any] | None) -> None:
        # Modal teardown otherwise leaves focus on whichever catalog button
        # Textual selects next, which can consume global navigation chords.
        self.action_focus_composer()
        if parameters is None:
            self._system_message(f"Cancelled {action_id}; nothing was submitted.")
            self._render_all()
            return
        if self._submission_busy:
            self._system_message("A submission is already in flight; this action was not queued.")
            self._render_submission_projection()
            return
        try:
            task = self.broker.capture_action(
                action_id,
                parameters,
                constraints=self.agent_coordinator.constraints(self._active_specialist),
                agent_id=self._active_specialist.id if self._active_specialist else None,
                agent_version=self._active_specialist.version if self._active_specialist else None,
            )
        except ValueError as exc:
            self._system_message(f"Action rejected: {exc}")
            self._render_all()
            return
        self._start_task_submission(task)

    def _queue_task(self, task: TaskRecord) -> None:
        self._active_submission_worker = self.run_worker(
            self._dispatch_task(task), group="task-dispatch", exclusive=False
        )

    def _apply_package_filter(self) -> None:
        self._package_filter = self.query_one("#package-name", Input).value.strip()
        self._package_page = 0
        self._render_packages()
        if self._package_filter:
            self._set_package_details(
                f"Showing packages matching: {self._package_filter}\n"
                "The filter checks name, version, summary, category, purpose, origin, and state."
            )
        else:
            self._set_package_details("Package filter cleared. Select a row to see its details.")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "composer":
            self._submit_composer()
        elif event.input.id == "package-name":
            self._apply_package_filter()

    def on_select_changed(self, event: Select.Changed) -> None:
        checkpoint_prefix = "checkpoint-mode-"
        if (
            event.select.id
            and event.select.id.startswith(checkpoint_prefix)
            and isinstance(event.value, str)
        ):
            checkpoint_id = event.select.id.removeprefix(checkpoint_prefix)
            if checkpoint_id in self._checkpoint_selector_initializing:
                self._checkpoint_selector_initializing.discard(checkpoint_id)
                return
            checkpoint = self._checkpoint_for_id(checkpoint_id)
            if checkpoint is not None and event.value in {"context", "full"}:
                self._request_checkpoint_restore(checkpoint, event.value)
            return
        if event.select.id == "specialist-select" and isinstance(event.value, str):
            try:
                self._active_specialist = self.agent_coordinator.select(event.value)
                self._system_message(
                    f"Active specialist: {self._active_specialist.display_name}. "
                    "Requests will not switch agents automatically."
                )
            except ValueError:
                self._system_message("Specialist selection rejected: descriptor is unavailable.")
            self._render_all()
            return
        if event.select.id == "global-model-select" and isinstance(event.value, str):
            self._set_global_model(event.value)
            self._system_message(f"Global model set for new turns: {event.value}.")
            return
        if event.select.id == "global-reasoning-select" and isinstance(event.value, str):
            self._set_global_reasoning(event.value)
            self._system_message(f"Global reasoning effort set for new turns: {event.value}.")
            return
        if event.select.id == "global-context-select" and isinstance(event.value, str):
            self._set_global_context(event.value)
            self._system_message(f"Global context window set for new turns: {event.value}.")
            return
        if (
            event.select.id == "system-view"
            and isinstance(event.value, str)
        ):
            self._set_domain_view(getattr(self, "_system_domain", "overview"), event.value)
            return
        if event.select.id == "agent-editor-mode" and isinstance(event.value, str):
            self._render_agent_editor_mode()
            return
        if event.select.id == "package-sort" and isinstance(event.value, str):
            if event.value != self._package_sort:
                self._package_sort = event.value
                self._package_page = 0
                self._render_packages()
            return
        if event.select.id == "package-view" and isinstance(event.value, str):
            if event.value != self._package_mode:
                self._package_mode = event.value
                self._package_loaded = False
                self._package_page = 0
                self.run_worker(
                    self._load_package_inventory(refresh=True),
                    group="package-inventory",
                    exclusive=True,
                )
            return
        if event.select.id == "power-section" and isinstance(event.value, str):
            self._power_section = event.value
            self._render_power()
            return
        if event.select.id == "power-value" and isinstance(event.value, str):
            item = self._power_selected
            self.query_one("#power-apply", Button).disabled = not (
                helper_available()
                and item is not None
                and item.control_id in POWER_CONTROL_OPTIONS
                and event.value in POWER_CONTROL_OPTIONS[item.control_id]
                and event.value != item.current
            )
            return

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "agents-table":
            specialist_id = self._agent_table_items.get(str(event.row_key.value))
            if specialist_id is not None:
                self._load_agent_editor(specialist_id)
                self._render_agents()
            return
        if event.data_table.id == "power-settings-table":
            item = self._power_table_items.get(str(event.row_key.value))
            if item is not None:
                self._configure_power_selection(item)
                self.query_one("#power-details-content", Static).update(
                    f"{item.section} / {item.setting}\n"
                    f"current: {item.current}\n"
                    f"available values: {item.choices}\n"
                    f"source: {item.source}\n"
                    f"Jarvis control: {item.control_id or 'read-only'}"
                )
            return
        if event.data_table.id != "packages-table":
            return
        item = self._package_table_items.get(str(event.row_key.value))
        if item is None:
            return
        self.query_one("#package-name", Input).value = item["name"]
        self._set_package_details(
            (
                f"{item['nevra']}",
                f"state: {item['state']}",
                f"category: {item['category']}",
                f"origin: {item['origin']}",
                f"purpose: {item['purpose']}",
                "installed alternatives (inferred same-purpose category): "
                + (", ".join(item.get("installed_alternatives", ())) or "none"),
                f"summary: {item['summary']}",
                "Use Relations for authoritative RPM dependency/conflict evidence.",
            ),
        )

    def on_tabbed_content_tab_activated(self, event: TabbedContent.TabActivated) -> None:
        pane_id = event.pane.id if event.pane else None
        for name, expected in VIEW_IDS.items():
            if pane_id == expected:
                self.active_view = name
                if name == "packages" and not self._package_loaded and not self._package_loading:
                    self.run_worker(
                        self._load_package_inventory(),
                        group="package-inventory",
                        exclusive=True,
                    )
                if name == "power" and self._power_inventory is None and not self._power_loading:
                    self._ensure_power_telemetry_timer()
                    self.run_worker(
                        self._load_power_inventory(),
                        group="power-inventory",
                        exclusive=True,
                    )
                break

    async def _refresh_domain(self, domain: str) -> None:
        view = self.query_one("#system-log", RichLog)
        try:
            evidence = await run_blocking_once(inspect_domain, self.bundle_root, domain)
            self._domain_evidence[domain] = evidence
            view.clear()
            view.write(json.dumps(evidence, indent=2, ensure_ascii=False))
            await self._render_domain_clean(domain)
            self._render_system_overview()
        except (OSError, ValueError, RuntimeError):
            view.write("Evidence unavailable; no automatic retry.")

    async def _render_domain_clean(self, domain: str) -> None:
        panel = self.query_one("#system-clean", VerticalScroll)
        await panel.remove_children()
        evidence = self._domain_evidence.get(domain)
        if evidence is None:
            await panel.mount(Static("Select Refresh evidence to load this view.", markup=False))
            return
        rows = []
        for index, (label, value, explanation) in enumerate(clean_domain_fields(evidence)):
            identifier = f"domain-info-{domain}-{index}"
            self._domain_help[identifier] = (label, explanation)
            rows.append(
                Horizontal(
                    DomainInfoLabel(label, identifier),
                    Static(value, classes="domain-field-value", markup=False),
                    classes="domain-field",
                )
            )
        await panel.mount(*rows)

    def _set_domain_view(self, domain: str, mode: str) -> None:
        switcher = self.query_one("#system-detail-switcher", ContentSwitcher)
        switcher.current = "system-clean" if mode == "clean" else "system-log"

    def _render_system_overview(self) -> None:
        cards = self.query_one("#system-overview-cards", Static)
        lines = []
        for domain in ("health", "development", "network", "security", "recovery"):
            evidence = self._domain_evidence.get(domain)
            status = "Available" if evidence is not None else "Not loaded"
            summary = (
                f"{len(clean_domain_fields(evidence))} clean evidence fields loaded."
                if evidence is not None
                else "Select the domain to inspect and refresh evidence."
            )
            lines.append(f"{domain.title()} · {status}\n{summary}")
        cards.update("\n\n".join(lines))

    def _select_system_domain(self, domain: str) -> None:
        switcher = self.query_one("#system-switcher", ContentSwitcher)
        if domain == "overview":
            switcher.current = "system-overview"
            return
        self._system_domain = domain
        switcher.current = "system-domain-detail"
        self.query_one("#system-domain-title", Label).update(domain.title())
        self.query_one("#system-refresh", Button).display = True
        self.query_one("#system-review", Button).display = True
        self.query_one("#system-terminal", Button).display = domain == "development"
        self._render_domain_clean(domain)

    def _review_domain(self, domain: str) -> None:
        try:
            operation_id = self.query_one("#system-operation", Input).value.strip()
            plan = self.operation_workflow.load(operation_id)
            if plan["domain"] != domain or self._operation_busy or self._submission_busy:
                raise ValueError("operation_scope_or_busy")
            self.push_screen(
                OperationReview(plan),
                lambda decision: self._operation_decision(operation_id, decision),
            )
        except (OSError, ValueError):
            self.query_one("#system-log", RichLog).write(
                "Proposal unavailable or outside this view."
            )

    def _review_normal_terminal(self) -> None:
        try:
            operation_id = self.query_one("#system-operation", Input).value.strip()
            plan = self.operation_workflow.load(operation_id)
            if plan.get("domain") != "development" or plan.get("operation") != "command":
                raise ValueError("normal_terminal_requires_command")
            if self._checkpoint_work_active():
                raise ValueError("operation_busy")
            terminal_plan = self.normal_terminal_workflow.propose(
                plan["argv"], plan["target"], operation_id
            )
            self.push_screen(
                OperationReview(terminal_plan),
                lambda decision: self._normal_terminal_decision(terminal_plan["id"], decision),
            )
        except (OSError, ValueError):
            self.query_one("#system-log", RichLog).write(
                "Normal-terminal proposal unavailable or outside Development."
            )

    def _normal_terminal_decision(self, operation_id: str, decision: str | None) -> None:
        if decision is None:
            self.normal_terminal_workflow.discard(operation_id)
            return
        if self._operation_busy or self._submission_busy:
            self.normal_terminal_workflow.discard(operation_id)
            return
        try:
            approval = self.normal_terminal_workflow.approve(operation_id, decision)
        except (OSError, ValueError):
            self._system_message("Normal-terminal approval rejected; prepare a fresh proposal.")
            return
        self._operation_busy = True
        self.run_worker(
            self._execute_normal_terminal(approval),
            group="registered-operation",
            exclusive=False,
        )

    async def _execute_normal_terminal(self, approval: Any) -> None:
        try:
            self.broker.journal.append(
                "registered_mutation.execution.reserved",
                "control_plane",
                "reserved",
                {"workflow": "normal_terminal", "operation_id": approval.operation_id},
            )
            # Textual's driver is owned by the UI thread. Keep exceptions inside
            # suspend's yield so the driver always gets its normal resume path.
            failure: BaseException | None = None
            result: dict[str, Any] = {}
            with self.suspend():
                try:
                    result = await run_blocking_once(
                        self.normal_terminal_workflow.execute, approval, cancellation="settle"
                    )
                except BaseException as exc:
                    failure = exc
            if failure is not None:
                raise failure
            message = f"Normal terminal operation {approval.operation_id}: {result['status']}; exit={result.get('exit_code', 'unknown')}. Foreground exit only; objective not independently verified."
            self._system_message(message)
            self.query_one("#system-log", RichLog).write(message)
        except Exception:
            self._system_message("Normal terminal outcome unavailable; no retry was made.")
        finally:
            self._operation_busy = False
            self._render_all()

    def _operation_decision(self, operation_id: str, decision: str | None) -> None:
        if decision is None:
            return
        if self._operation_busy or self._submission_busy:
            self._system_message(
                "Another operation is active; prepare a fresh review after it finishes."
            )
            return
        try:
            approval = self.operation_workflow.approve(operation_id, decision)
        except (OSError, ValueError):
            self._system_message("Operation approval rejected; prepare a fresh proposal.")
            return
        self._operation_busy = True
        self.run_worker(
            self._execute_operation(approval), group="registered-operation", exclusive=False
        )

    async def _execute_operation(self, approval: Any) -> None:
        self.broker.journal.append(
            "registered_mutation.execution.reserved",
            "control_plane",
            "reserved",
            {"workflow": "execute_operation"},
        )
        try:
            result = await run_blocking_once(
                self.operation_workflow.execute, approval, cancellation="settle"
            )
            verdict = result.get("verification", {}).get("verdict", "unknown")
            self._system_message(
                f"Operation {approval.operation_id}: {result['status']}; independent verification: {verdict}."
                + (
                    " Process checks do not establish that the requested objective was achieved."
                    if result.get("goal_verified") is False
                    else ""
                )
            )
        except (OSError, ValueError, RuntimeError):
            self._system_message(
                "Operation outcome unavailable. Inspect its durable record before any new plan; no retry was made."
            )
        finally:
            self._operation_busy = False
            self._render_all()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("domain-info-"):
            detail = self._domain_help.get(button_id)
            if detail is not None:
                self.push_screen(DomainInfoScreen(*detail))
            return
        if button_id == "system-refresh":
            domain = getattr(self, "_system_domain", "overview")
            if domain != "overview":
                self.run_worker(self._refresh_domain(domain), group="domain-" + domain, exclusive=True)
            return
        if button_id == "system-review":
            domain = getattr(self, "_system_domain", "overview")
            if domain != "overview":
                self._review_domain(domain)
            return
        if button_id == "system-terminal":
            if getattr(self, "_system_domain", "") == "development":
                self._review_normal_terminal()
            return

        # Conversation controls
        if button_id == "conv-new":
            if self._submission_busy:
                self._system_message(
                    "Wait for or cancel the active submission before starting a new conversation."
                )
                return
            self._start_new_conversation()
            return
        if button_id == "conv-history":
            self._show_conversation_history()
            return
        if button_id == "conv-copy":
            self._copy_conversation_to_clipboard()
            return
        if button_id == "copy-timeline":
            self._copy_timeline_to_clipboard()
            return

        # Existing handlers
        if button_id == "send-request":
            self._submit_composer()
            return
        if button_id == "session-login":
            self.run_worker(self._begin_chatgpt_login(), group="app-server-login", exclusive=True)
            return
        if button_id == "session-refresh":
            self.run_worker(
                self._refresh_app_server_session(),
                group="app-server-refresh",
                exclusive=True,
            )
            return
        if button_id == "cancel-turn":
            self.action_cancel_turn()
            return
        if button_id == "agent-validate":
            self._validate_agent_draft()
            return
        if button_id == "agent-activate":
            self._activate_agent_definition()
            return
        if button_id == "agent-rollback":
            self._rollback_agent_definition()
            return
        if button_id == "agent-reset":
            self._load_agent_editor(self._agent_editor_id)
            self._write_agent_validation((), ())
            self._render_agents()
            return
        if button_id == "package-scan":
            self.run_worker(
                self._load_package_inventory(refresh=True),
                group="package-inventory",
                exclusive=True,
            )
            return
        if button_id == "power-refresh":
            self.run_worker(self._load_power_inventory(), group="power-inventory", exclusive=True)
            return
        if button_id == "power-apply":
            self._review_power_change()
            return
        if button_id == "power-profile-draft":
            self._draft_power_profile()
            return
        if button_id == "power-profile-save":
            self._save_power_profile()
            return
        if button_id == "power-profile-preview":
            self._preview_power_profile()
            return
        if button_id == "power-profile-apply":
            self._review_power_profile()
            return
        if button_id == "power-package-handoff-select":
            try:
                self._active_specialist = self.agent_coordinator.select(
                    "jarvis-installation-specialist"
                )
                self._pending_package_handoff = None
                self.query_one("#specialist-select", Select).value = self._active_specialist.id
                self._system_message(
                    "Installation Specialist selected for the pending package recommendation."
                )
            except ValueError:
                self._system_message("Installation Specialist is unavailable for this handoff.")
            self._render_all()
            return
        if button_id == "power-undo":
            self.run_worker(self._prepare_power_undo(), group="power-undo-status", exclusive=True)
            return
        if button_id == "package-filter":
            self._apply_package_filter()
            return
        if button_id == "package-recommend":
            self.run_worker(
                self._recommend_packages(),
                group="package-recommendation",
                exclusive=True,
            )
            return
        if button_id == "package-preview":
            self.run_worker(
                self._preview_package_install("install"),
                group="package-preview",
                exclusive=True,
            )
            return
        if button_id == "package-preview-remove":
            self.run_worker(
                self._preview_package_install("remove"),
                group="package-preview",
                exclusive=True,
            )
            return
        if button_id == "package-apply":
            self._review_package_apply()
            return
        if button_id == "package-undo":
            self.run_worker(self._prepare_package_undo(), group="package-undo", exclusive=True)
            return
        if button_id == "package-archive":
            self.run_worker(
                self._prepare_package_archive(), group="package-archive", exclusive=True
            )
            return
        if button_id in {"package-page-prev", "package-page-next"}:
            self._package_page = max(
                0, self._package_page + (-1 if button_id.endswith("prev") else 1)
            )
            self._render_packages()
            return
        if button_id == "package-details":
            name = self.query_one("#package-name", Input).value.strip()
            try:
                value = enrich_package(name)
                self._set_package_details(json.dumps(value, indent=2, sort_keys=True))
            except Exception as exc:
                self._system_message(f"Package details unavailable: {type(exc).__name__}")
            return
        if button_id == "package-docs":
            name = self.query_one("#package-name", Input).value.strip()
            try:
                self._set_package_details(
                    json.dumps(package_documentation(name), indent=2, sort_keys=True)
                )
            except Exception as exc:
                self._system_message(f"Package documentation unavailable: {type(exc).__name__}")
            return
        if button_id == "package-origins":
            try:
                self._set_package_details(
                    json.dumps(list(repository_origins()), indent=2, sort_keys=True)
                )
            except Exception as exc:
                self._system_message(f"Repository origins unavailable: {type(exc).__name__}")
            return
        if button_id == "package-history":
            try:
                self._set_package_details("\n".join(dnf_history()))
            except Exception as exc:
                self._system_message(f"DNF history unavailable: {type(exc).__name__}")
            return
        if button_id == "package-relationships":
            name = self.query_one("#package-name", Input).value.strip()
            try:
                self._set_package_details(
                    json.dumps(relationship_queries(name), indent=2, sort_keys=True)
                )
            except Exception as exc:
                self._system_message(f"Package relationships unavailable: {type(exc).__name__}")
            return
        if button_id == "package-advisories":
            try:
                self._set_package_details("\n".join(advisories(allow_network=False)))
            except Exception:
                self._system_message(
                    "Advisories require explicit network approval and remain disabled."
                )
            return
        if button_id == "lighting-preview":
            self._render_lighting_preview()
            return
        if button_id == "lighting-apply":
            self._review_lighting_change()
            return
        return

    def _toggle_checkpoint(self, checkpoint_id: str) -> None:
        checkpoint = self._checkpoint_for_id(checkpoint_id)
        if checkpoint is not None:
            open_menu = self._checkpoint_selector_id != checkpoint.checkpoint_id
            self._checkpoint_selector_id = checkpoint.checkpoint_id if open_menu else None
            self.query_one("#conversation-log", ConversationPanel).set_checkpoint_menu(
                checkpoint_id, open_menu
            )

    def action_open_checkpoint(self) -> None:
        focused = self.focused
        parent = getattr(focused, "parent", None)
        if parent is not None and hasattr(parent, "open_menu"):
            parent.open_menu()

    # Conversation management methods

    def _checkpoints_by_message_key(self) -> dict[str, ConversationCheckpoint]:
        return {
            checkpoint.user_message_key: checkpoint for checkpoint in self._conversation_checkpoints
        }

    @staticmethod
    def _checkpoint_entry(entry: ConversationEntry) -> dict[str, Any]:
        return {
            "key": entry.key,
            "role": entry.role,
            "text": entry.text,
            "status": entry.status,
            "task_id": entry.task_id,
            "turn_id": entry.turn_id,
            "specialist_id": entry.specialist_id,
            "specialist_version": entry.specialist_version,
        }

    def _create_user_checkpoint(self, task: TaskRecord) -> None:
        if task.action is not None:
            return
        conversation = self.conversation_manager.get_current_conversation()
        user_entry = next(
            (
                entry
                for entry in reversed(self.presentation.conversation)
                if entry.key == f"task:{task.task_id}" and entry.role == "user"
            ),
            None,
        )
        if conversation is None or user_entry is None:
            return
        try:
            journal = self.broker.journal.read()
            checkpoint = ConversationCheckpoint.create(
                conversation_id=conversation.id,
                user_message_key=user_entry.key,
                entries=[self._checkpoint_entry(entry) for entry in self.presentation.conversation],
                journal_sequence=int(journal[-1]["sequence"]) if journal else 0,
                action_task_ids=tuple(sorted(self.broker._tasks)),
            )
            self._conversation_checkpoints = self._checkpoint_store.save(checkpoint)
        except (OSError, ValueError, KeyError):
            self._system_message(
                "Conversation checkpoint was unavailable; the message was not blocked."
            )

    def _checkpoint_for_id(self, checkpoint_id: str) -> ConversationCheckpoint | None:
        return next(
            (
                item
                for item in self._conversation_checkpoints
                if item.checkpoint_id == checkpoint_id
            ),
            None,
        )

    def _restore_checkpoint_context(self, checkpoint: ConversationCheckpoint) -> None:
        if self._submission_busy or self.session.snapshot.active_turn_id:
            self._system_message("Checkpoint restore is blocked until active work settles.")
            return
        conversation = self.conversation_manager.get_current_conversation()
        if conversation is None or conversation.id != checkpoint.conversation_id:
            self._system_message(
                "Checkpoint belongs to a different conversation; restore was blocked."
            )
            return
        self._sync_conversation_to_manager()
        archived = Conversation(
            title=f"{conversation.title} (before checkpoint restore)",
            messages=copy.deepcopy(conversation.messages),
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )
        self.conversation_manager.save_conversation(archived)
        restored_items: list[dict[str, Any]] = []
        draft_text: str | None = None
        for item in checkpoint.entries:
            if str(item.get("key")) == checkpoint.user_message_key:
                draft_text = str(item.get("text", ""))
                break
            restored_items.append(item)
        if draft_text is None:
            self._system_message("Checkpoint restore was blocked: its user message is unavailable.")
            return
        entries = tuple(
            ConversationEntry(
                key=str(item["key"]),
                role=str(item["role"]),
                text=str(item["text"]),
                status=str(item["status"]),
                task_id=str(item["task_id"]) if item.get("task_id") else None,
                turn_id=str(item["turn_id"]) if item.get("turn_id") else None,
                specialist_id=str(item["specialist_id"]) if item.get("specialist_id") else None,
                specialist_version=str(item["specialist_version"])
                if item.get("specialist_version")
                else None,
            )
            for item in restored_items
        )
        self.presentation.reset_conversation(entries)
        snapshot = {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at,
            "updated_at": conversation.updated_at,
            "messages": [
                {
                    "key": entry.key,
                    "role": entry.role,
                    "content": entry.text,
                    "status": entry.status,
                    "task_id": entry.task_id,
                    "turn_id": entry.turn_id,
                    "specialist_id": entry.specialist_id,
                    "specialist_version": entry.specialist_version,
                }
                for entry in entries
            ],
        }
        self.conversation_manager.replace_current_conversation(snapshot)
        self._synced_entry_state.clear()
        self._conversation_message_indices.clear()
        self._last_rendered_conversation_length = 0
        self._last_conversation_entries_hash = []
        self._checkpoint_selector_id = None
        self._system_message(
            "Checkpoint context restored before the selected message. "
            "Its text was returned to the composer for editing; current conversation was saved first."
        )
        composer = self.query_one("#composer", Input)
        composer.value = draft_text
        composer.focus()

    def _later_mutation_events(
        self, checkpoint: ConversationCheckpoint
    ) -> tuple[dict[str, Any], ...]:
        mutation_events = {
            "package.transaction.completed",
            "local_mutation.completed",
            "local_mutation.execution.reserved",
            "package.transaction.execution.reserved",
            "package.rollback.execution.reserved",
            "package.rollback.completed",
            "registered_mutation.execution.reserved",
        }
        return tuple(
            event
            for event in self.broker.journal.read()
            if int(event.get("sequence", 0)) > checkpoint.journal_sequence
            and event.get("event_type") in mutation_events
        )

    def _checkpoint_work_active(self) -> bool:
        return bool(
            self._submission_busy
            or self.session.snapshot.active_turn_id
            or self._package_mutation_busy
            or self._operation_busy
            or any(worker.is_running and "mutation" in worker.group for worker in self.workers)
        )

    def _checkpoint_recovery_binding(self, checkpoint: ConversationCheckpoint) -> str | None:
        if checkpoint.schema_version < 2:
            raise ValueError("legacy checkpoints lack complete mutation tracking")
        return recovery_binding(self._later_mutation_events(checkpoint))

    def _request_checkpoint_restore(self, checkpoint: ConversationCheckpoint, mode: str) -> None:
        if self._checkpoint_work_active():
            self._system_message("Checkpoint restore is blocked until active work settles.")
            return
        if mode == "full":
            try:
                self._checkpoint_recovery_binding(checkpoint)
            except ValueError:
                self._system_message(
                    "Full checkpoint restore is unavailable: later mutations or legacy history require "
                    "their own exact recovery workflow. No conversation or host state was changed."
                )
                return
        label = "full" if mode == "full" else "chat/context"
        recovery_note = (
            " One later package transaction has an exact registered rollback; a separate rollback confirmation will follow."
            if mode == "full" and self._later_mutation_events(checkpoint)
            else ""
        )
        details = (
            f"Restore mode: {label}\n"
            f"Checkpoint: {checkpoint.created_at}\n"
            f"User message: {checkpoint.user_message_key}\n\n"
            "The current conversation will be saved first. This restores the conversation before "
            "the selected user message and returns that message to the composer for editing. "
            f"No action is replayed.{recovery_note}"
        )
        self.push_screen(
            PowerChangeReviewScreen(
                title=f"Confirm one-use {label} checkpoint restoration",
                details=details,
                confirm_label="Restore checkpoint",
            ),
            lambda confirmed, checkpoint=checkpoint: self._restore_context_checkpoint_if_confirmed(
                checkpoint, mode, bool(confirmed)
            ),
        )

    def _restore_context_checkpoint_if_confirmed(
        self, checkpoint: ConversationCheckpoint, mode: str, confirmed: bool
    ) -> None:
        if not confirmed:
            self._checkpoint_selector_id = None
            self._render_all()
            return
        if self._checkpoint_work_active():
            self._system_message("Checkpoint restore is blocked until active work settles.")
            return
        if mode == "full":
            try:
                binding = self._checkpoint_recovery_binding(checkpoint)
            except ValueError:
                self._system_message("Checkpoint recovery history changed; prepare a fresh review.")
                return
            if binding:
                self.run_worker(
                    self._prepare_package_undo(checkpoint),
                    group="checkpoint-recovery",
                    exclusive=True,
                )
                return
        self._restore_checkpoint_context(checkpoint)
        self._live_activity.reset_context()
        current = self.conversation_manager.get_current_conversation()
        if current is not None:
            self._queue_conversation_persistence(current)
        self._render_all()

    def _start_new_conversation(self):
        """Start a new conversation, saving the current one first."""
        try:
            # Sync any pending messages first
            self._sync_conversation_to_manager()

            # Get message count before creating new
            current_conv = self.conversation_manager.get_current_conversation()
            msg_count = len(current_conv.messages) if current_conv else 0
            if current_conv is not None:
                self._queue_conversation_persistence(current_conv)

            # Create new conversation (auto-saves previous if it has messages)
            self.conversation_manager.new_conversation()
            self._live_activity.reset_context()
            self._conversation_checkpoints = ()
            self._checkpoint_selector_id = None

            # Reset sync counter
            self._last_synced_conversation_count = 0
            self._synced_entry_state.clear()
            self._conversation_message_indices.clear()

            self.session.reset_conversation_thread()

            # Clear display
            self._clear_conversation_display()

            # Show helpful message
            if msg_count > 0:
                self._system_message(
                    f"Previous conversation saved ({msg_count} messages). Started new conversation."
                )
            else:
                self._system_message("Started new conversation.")

        except Exception as e:
            self._system_message(f"Failed to start new conversation: {e}")

    def _clear_conversation_display(self):
        """Clear the active view and its matching model-context epoch."""
        try:
            self.presentation.reset_conversation()
            configured_context = getattr(self, "_selected_context", "auto")
            self._live_activity = LiveActivity()
            if configured_context.isdigit():
                self._live_activity.context_window = int(configured_context)
            self._checkpoint_selector_id = None
            self._synced_entry_state.clear()
            self._conversation_message_indices.clear()
            self._last_rendered_conversation_length = 0
            self._schedule_conversation_render()
            # Reset incremental rendering tracking
            self._last_rendered_conversation_length = 0
            self._last_conversation_entries_hash = []
        except Exception:
            pass

    def _show_conversation_history(self):
        """Show conversation history in modal dialog."""
        try:
            history = self.conversation_manager.list_conversations()

            if not history:
                self._system_message("No saved conversations found.")
                return

            # Push the modal screen and handle result
            self.push_screen(ConversationHistoryModal(history), self._handle_history_action)

        except Exception as e:
            self._system_message(f"Failed to load history: {e}")

    def _handle_history_action(self, result: tuple[str, str] | None) -> None:
        """Handle action from history modal.

        Args:
            result: Tuple of (action, conversation_id) or None
        """
        if result is None:
            return

        action, conv_id = result

        try:
            if action == "delete":
                # Delete the conversation
                success = self.conversation_manager.delete_conversation(conv_id)
                if success:
                    self._system_message(f"Conversation deleted: {conv_id}")
                else:
                    self._system_message(f"Failed to delete conversation: {conv_id}")

            elif action == "load":
                if self._submission_busy:
                    self._system_message(
                        "Wait for or cancel the active submission before loading another conversation."
                    )
                    return
                # Resume the conversation
                conversation = self.conversation_manager.resume_conversation(conv_id)

                if conversation:
                    try:
                        loaded_entries = tuple(
                            ConversationEntry(
                                key=str(msg.get("key", f"loaded:{idx}")),
                                role=str(msg["role"]),
                                text=str(msg["content"]),
                                status=str(msg.get("status", "completed")),
                                task_id=str(msg["task_id"]) if msg.get("task_id") else None,
                                turn_id=str(msg["turn_id"]) if msg.get("turn_id") else None,
                                specialist_id=(
                                    str(msg["specialist_id"]) if msg.get("specialist_id") else None
                                ),
                                specialist_version=(
                                    str(msg["specialist_version"])
                                    if msg.get("specialist_version")
                                    else None
                                ),
                            )
                            for idx, msg in enumerate(conversation.messages)
                        )
                        self.presentation.reset_conversation(loaded_entries)
                        self._live_activity = LiveActivity()
                        self._restore_conversation_usage(loaded_entries)
                        self._synced_entry_state.clear()
                        self._conversation_message_indices.clear()
                        for message_index, entry in enumerate(self.presentation.conversation):
                            if entry.role in {"user", "agent", "jarvis", "action", "system"}:
                                self._synced_entry_state[entry.key] = (
                                    len(entry.text),
                                    entry.status,
                                )
                                self._conversation_message_indices[entry.key] = message_index

                        self._conversation_checkpoints = self._checkpoint_store.load(
                            conversation.id
                        )
                        self._last_rendered_conversation_length = 0
                        self._schedule_conversation_render()
                        self._last_rendered_conversation_length = 0
                        self._last_conversation_entries_hash = []
                        self._last_synced_conversation_count = len(conversation.messages)
                        self._render_all()

                        self._system_message(
                            f"✓ Loaded: {conversation.title[:50]} ({len(conversation.messages)} messages)"
                        )
                    except Exception as exc:
                        self._system_message(
                            f"Conversation load failed (conversation.load_{type(exc).__name__.casefold()})."
                        )
                else:
                    self._system_message(f"✗ Could not find conversation: {conv_id}")

        except Exception as exc:
            self._system_message(
                f"Conversation history action failed (conversation.history_{type(exc).__name__.casefold()})."
            )

    def _restore_conversation_usage(self, entries: tuple[ConversationEntry, ...]) -> None:
        """Restore persisted usage for a loaded conversation before new input."""
        task_ids = {entry.task_id for entry in entries if entry.task_id}
        if not task_ids:
            return
        latest_by_task: dict[str, dict[str, Any]] = {}
        for event in self.broker.journal.read():
            if event.get("event_type") != "context.usage" or event.get("task_id") not in task_ids:
                continue
            latest_by_task[str(event["task_id"])] = event.get("details", {})
        if not latest_by_task:
            return
        logical_total = 0
        cached_total = 0
        last_response = None
        for details in latest_by_task.values():
            logical = details.get("logical_turn", {})
            response = details.get("response", {})
            logical_total += int(logical.get("total_count", 0) or 0)
            cached_total += int(logical.get("total_cached_input_count", 0) or 0)
            if isinstance(response.get("last_total_count"), int):
                last_response = response["last_total_count"]
        configured = getattr(self, "_selected_context", "auto")
        window = int(configured) if isinstance(configured, str) and configured.isdigit() else None
        self._live_activity.restore_usage(
            cumulative=logical_total or None,
            cached_input=cached_total or None,
            last_response=last_response,
            context_window=window,
        )

    def _copy_conversation_to_clipboard(self):
        """Copy conversation text to system clipboard."""
        try:
            conversation_text = self.query_one("#conversation-log", ConversationPanel).text

            if not conversation_text or not conversation_text.strip():
                self._system_message("No conversation to copy.")
                return

            # Run copy operation in worker to avoid blocking UI
            self.run_worker(
                self._do_clipboard_copy(conversation_text),
                group="clipboard-copy",
                exclusive=False,
            )

        except Exception as exc:
            self._system_message(
                f"Conversation copy failed (clipboard.{type(exc).__name__.casefold()})."
            )

    async def _do_clipboard_copy(self, text: str):
        """Copy through a fixed local client without persisting a fallback file."""
        import os
        import subprocess

        candidates = (
            ("wl-copy", Path("/usr/bin/wl-copy"), ["/usr/bin/wl-copy"]),
            (
                "xclip",
                Path("/usr/bin/xclip"),
                ["/usr/bin/xclip", "-selection", "clipboard"],
            ),
            ("xsel", Path("/usr/bin/xsel"), ["/usr/bin/xsel", "--clipboard", "--input"]),
            ("pbcopy", Path("/usr/bin/pbcopy"), ["/usr/bin/pbcopy"]),
        )
        for name, executable, argv in candidates:
            if not executable.is_file() or not os.access(executable, os.X_OK):
                continue
            try:
                process = await run_blocking_once(
                    subprocess.run,
                    argv,
                    call_kwargs={
                        "input": text.encode("utf-8"),
                        "capture_output": True,
                        "timeout": 5,
                        "check": False,
                    },
                    thread_name="jarvis-clipboard-copy",
                )
            except Exception:
                continue
            if process.returncode == 0:
                self._system_message(f"Copied {len(text)} characters to clipboard ({name}).")
                return
        self._system_message(
            "Clipboard unavailable; no conversation or timeline text was written to disk. "
            "Install wl-clipboard, xclip, xsel, or pbcopy to enable copying."
        )

    def _copy_timeline_to_clipboard(self):
        """Copy timeline text to system clipboard."""
        try:
            # Get timeline entries from presentation
            timeline_lines = self.presentation.render_timeline()

            if not timeline_lines:
                self._system_message("No timeline entries to copy.")
                return

            # Join timeline entries into text
            timeline_text = "\n".join(timeline_lines)

            if not timeline_text.strip():
                self._system_message("Timeline is empty.")
                return

            # Run copy operation in worker to avoid blocking UI
            self.run_worker(
                self._do_clipboard_copy(timeline_text),
                group="clipboard-copy",
                exclusive=False,
            )

        except Exception as exc:
            self._system_message(
                f"Timeline copy failed (clipboard.{type(exc).__name__.casefold()})."
            )

    def _refresh_conversation_display(self):
        """Refresh conversation display from manager."""
        try:
            self._replace_log("#conversation-log", self.presentation.render_conversation())
        except Exception:
            pass

    def _add_user_message_to_conversation(self, text: str):
        """Add user message to conversation."""
        try:
            self.conversation_manager.add_message("user", text)
            self._queue_conversation_persistence()
            self._refresh_conversation_display()
        except Exception:
            pass

    def _add_agent_message_to_conversation(self, text: str):
        """Add agent message to conversation."""
        try:
            self.conversation_manager.add_message("agent", text)
            self._queue_conversation_persistence()
            self._refresh_conversation_display()
        except Exception:
            pass

    def on_mouse_down(self, event: Any) -> None:
        parent = self.parent
        if parent is not None and hasattr(parent, "open_menu"):
            parent.open_menu()
