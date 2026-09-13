"""Textual-independent presentation state for the hybrid terminal UI."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .event_reducer import NormalizedEvent
from .local_filesystem import LocalFilesystemReadResult
from .local_mutation import LocalFilesystemMutationResult
from .models import (
    AssessmentDecision,
    ConversationContextEntry,
    ConversationContextSnapshot,
    TaskAdmission,
    TaskRecord,
)
from .operational_export import ExportDeliveryResult, deliver_redacted_export
from .session import SessionSnapshot
from .terminal_safety import sanitize_and_redact_terminal_text

DISPLAY_LIMIT = 16_000
COLLECTION_LIMIT = 500
JOURNAL_TIMELINE_LIMIT = 100
ACTIVE_CONTEXT_CHARACTER_LIMIT = 64_000
CONTEXT_OMISSION_TEXT = (
    "Earlier complete exchanges were omitted from this active conversation context."
)


def safe_text(value: Any, limit: int = DISPLAY_LIMIT) -> str:
    text = str(value)
    safe, _ = sanitize_and_redact_terminal_text(text, limit=limit)
    return safe


_SENSITIVE_EXPORT = re.compile(
    r"(?i)\bauthorization\s*:\s*bearer\s+[^\s,;]+|\b(?P<key>password|passphrase|token|secret|api[_-]?key|authorization|bearer|credential|private[_-]?key|cookie)\b\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)


def redact_export_text(value: Any, limit: int = 500) -> str:
    def replacement(match: re.Match[str]) -> str:
        label = match.group("key") or "authorization"
        return f"{label}=[redacted]"

    return _SENSITIVE_EXPORT.sub(replacement, safe_text(value, limit))


@dataclass
class ConversationEntry:
    key: str
    role: str
    text: str
    status: str
    task_id: str | None = None
    turn_id: str | None = None
    specialist_id: str | None = None
    specialist_version: str | None = None


_ACTIVE_ACTIVITY_STATES = frozenset({"in_progress", "running", "streaming", "pending", "waiting"})
_ACTIVITY_OUTPUT_LIMIT = 4_000


@dataclass(frozen=True)
class PlanStepView:
    step: str
    status: str


@dataclass(frozen=True)
class TimelineEntry:
    sequence: int
    kind: str
    status: str
    summary: str
    task_id: str | None = None
    turn_id: str | None = None


@dataclass
class CodexServerRequestView:
    request_id: str
    request_type: str
    status: str
    thread_id: str | None
    turn_id: str | None
    item_id: str | None


@dataclass
class OverviewState:
    connection: str = "offline"
    auth: str = "not connected"
    thread: str = "not loaded"
    active_turn: str = "none"
    pending_requests: int = 0
    rate_limit_summary: str = "unavailable"
    capabilities: int = 0
    enabled_actions: int = 0
    unavailable_actions: int = 0
    knowledge: str = "unavailable"
    recovered_tasks: int = 0
    jarvisd: str = "not connected"
    h1_scope: str = "not loaded"
    recovery: str = "not loaded"
    phase5: str = "not loaded"
    safety: tuple[str, ...] = (
        "execution: typed preflight; read-only agent; registered one-use operations",
        "privilege: no standing root; registered helpers preferred",
        "live turns: explicit opt-in",
        "risk 0/1: exact scope may proceed from original request",
        "risk 2+: exact one-use confirmation required",
    )


@dataclass
class OperationalConsoleState:
    """Read-only Phase 6 projection; it carries no control authority."""

    authority: str = "not loaded"
    policy: str = "read-only projection; no mutation authority"
    errors: tuple[str, ...] = ()
    lessons: tuple[str, ...] = (
        "candidate lessons are evidence-backed and user-promoted only",
        "automatic policy or profile promotion: disabled",
    )
    recovery: tuple[str, ...] = ("recovery boundary: not loaded",)
    settings: tuple[str, ...] = (
        "settings: display-only; changes require a separately approved adapter",
        "safe default: no executor, no policy mutation, no automatic rollback",
        "prepared operations: lighting observation/repair and power-profile transition; unregistered",
    )
    audit: tuple[str, ...] = ("audit projection: local journal; redacted display only",)
    notifications: tuple[str, ...] = ()
    reconnect: str = "reconnect state: not loaded"


class JarvisPresentation:
    """Deterministic projection shared by Textual and headless tests."""

    def __init__(self) -> None:
        self.overview = OverviewState()
        self.operational = OperationalConsoleState()
        self.conversation: list[ConversationEntry] = []
        self._conversation_index: dict[str, ConversationEntry] = {}
        self._activity_index: dict[str, ConversationEntry] = {}
        self.activity_owner = "Agent"
        self.plan_steps: list[PlanStepView] = []
        self.plan_text = ""
        self.timeline: list[TimelineEntry] = []
        self.knowledge_kind = "facts"
        self.knowledge_query = ""
        self.knowledge_results: list[str] = []
        self.knowledge_error: str | None = None
        self.admissions: dict[str, TaskAdmission] = {}
        self.codex_requests: dict[str, CodexServerRequestView] = {}
        self._sequence = 0
        self._conversation_sequence = 0
        self._context_epoch = 0

    def refresh_operational_console(
        self,
        *,
        jarvisd_status: dict[str, Any] | None = None,
        recovery_status: dict[str, Any] | None = None,
        knowledge_status: dict[str, Any] | None = None,
    ) -> None:
        """Project bounded status for Phase 6 without reading or changing host state."""
        status = jarvisd_status or {}
        recovery = recovery_status or {}
        failures = tuple(
            safe_text(
                f"{entry.kind}: status={entry.status}; sequence={entry.sequence}; diagnosis=unavailable",
                300,
            )
            for entry in self.timeline
            if entry.status.casefold() in {"failed", "error", "blocked"}
        )[-8:]
        r1_value = recovery.get("r1") if isinstance(recovery, dict) else None
        r2_value = recovery.get("r2") if isinstance(recovery, dict) else None
        r1 = r1_value.get("status", "unavailable") if isinstance(r1_value, dict) else "unavailable"
        r2 = r2_value.get("status", "unavailable") if isinstance(r2_value, dict) else "unavailable"
        gaps = recovery.get("proof_gaps") or recovery.get("gaps") or ()
        recovery_lines = [
            f"R1={safe_text(r1, 100)} (unverified); R2={safe_text(r2, 100)} (unverified)"
        ]
        if gaps:
            recovery_lines.append(f"proof gaps reported: {len(gaps)}")
        notifications = status.get("notifications") or ()
        if isinstance(notifications, str):
            notifications = (notifications,)
        elif not isinstance(notifications, (list, tuple)):
            notifications = ("unknown: notifications unavailable",)
        connection = status.get("connection", status.get("state", "not connected"))
        if connection in {"available", "ready", "connected"}:
            reconnect = "reconnect state: connected"
        elif connection in {"offline", "unavailable", "disconnected"}:
            reconnect = "reconnect state: unavailable; no replay or authority granted"
        else:
            reconnect = "reconnect state: unknown; no replay or authority granted"
        knowledge = knowledge_status or {}
        lessons = (
            (
                "candidate lessons are evidence-backed and user-promoted only",
                "automatic policy or profile promotion: disabled",
            )
            if knowledge.get("available") and knowledge.get("integrity") in {"ok", "verified"}
            else (
                "unknown: lesson evidence unavailable or integrity unverified",
                "automatic policy or profile promotion: disabled",
            )
        )
        raw_authority = safe_text(status.get("host_authority", "not connected"), 200)
        authority = (
            raw_authority
            if raw_authority in {"read-only", "H1 Tier-0 read-only enabled", "not connected"}
            else "unknown (unrecognized authority status)"
        )
        storage_reason = knowledge.get("reason")
        if storage_reason in {"knowledge_database_locked", "store_locked", "locked"}:
            lessons = (
                "restricted store: locked; evidence and lessons unavailable (fail closed)",
                "automatic policy or profile promotion: disabled",
            )
        audit_integrity = status.get("audit_integrity", status.get("journal_integrity"))
        audit_lines = [
            f"journal events projected: {len(self.timeline)}",
            "integrity: unverified bounded projection",
            "journal availability: not independently attested",
            "export: redacted display only; no filesystem write",
        ]
        if audit_integrity in {"ok", "verified"}:
            audit_lines[1] = (
                f"integrity: {audit_integrity} (status projection; not attested by TUI)"
            )
        elif audit_integrity in {"failed", "corrupt", "invalid"}:
            audit_lines[1] = "integrity: failed; audit-dependent actions unavailable"
        elif audit_integrity in {"locked", "unavailable"}:
            audit_lines[1] = f"integrity: {audit_integrity}; audit-dependent actions unavailable"
        self.operational = OperationalConsoleState(
            authority=authority,
            errors=failures or ("unknown: no verified failure evidence loaded",),
            lessons=lessons,
            recovery=tuple(recovery_lines),
            audit=tuple(audit_lines),
            notifications=tuple(redact_export_text(item, 500) for item in notifications[:8]),
            reconnect=reconnect,
        )

    def _append_timeline(
        self,
        kind: str,
        status: str,
        summary: str,
        *,
        task_id: str | None = None,
        turn_id: str | None = None,
    ) -> None:
        self._sequence += 1
        self.timeline.append(
            TimelineEntry(
                sequence=self._sequence,
                kind=safe_text(kind, 100),
                status=safe_text(status, 100),
                summary=safe_text(summary, 1_000),
                task_id=task_id,
                turn_id=turn_id,
            )
        )
        if len(self.timeline) > COLLECTION_LIMIT:
            self.timeline = self.timeline[-COLLECTION_LIMIT:]

    def add_notice(self, text: str, status: str = "notice") -> None:
        self._append_timeline("ui", status, text)

    def add_local_conversation(
        self,
        text: str,
        status: str = "completed",
        *,
        task_id: str | None = None,
    ) -> None:
        """Display deterministic control-plane outcomes beside agent messages."""
        if task_id:
            key = f"local:{task_id}"
        else:
            self._conversation_sequence += 1
            key = f"local:{self._conversation_sequence}"
        entry = self._conversation_index.get(key)
        if entry is None:
            entry = ConversationEntry(
                key=key,
                role="jarvis",
                text=safe_text(text),
                status=status,
                task_id=task_id,
            )
            self._conversation_index[key] = entry
            self.conversation.append(entry)
        else:
            entry.text = safe_text(text)
            entry.status = status
        self._trim_conversation()

    def add_agent_conversation(
        self,
        text: str,
        status: str = "completed",
        *,
        task_id: str | None = None,
        specialist_id: str | None = None,
        specialist_version: str | None = None,
    ) -> None:
        """Add a durable agent-authored lifecycle result to the active context."""
        self._conversation_sequence += 1
        key = f"agent:local:{task_id or self._conversation_sequence}"
        entry = ConversationEntry(
            key=key,
            role="agent",
            text=safe_text(text),
            status=status,
            task_id=task_id,
            specialist_id=specialist_id,
            specialist_version=specialist_version,
        )
        self._conversation_index[key] = entry
        self.conversation.append(entry)
        self._trim_conversation()

    def add_agent_package_handoff(self, task: TaskRecord) -> None:
        """Show the agent's typed handoff before the registered preview dialog."""
        plan = task.package_plan
        if plan is None:
            return
        key = f"agent-package:{task.task_id}"
        if key in self._conversation_index:
            return
        entry = ConversationEntry(
            key=key,
            role="agent",
            text=(
                f"I identified an exact system package {plan.operation.value} request for: "
                f"{', '.join(plan.packages)}. I’ll resolve the DNF transaction and request one approval "
                "for its exact effect."
            ),
            status="completed",
            task_id=task.task_id,
            specialist_id=task.agent_id,
            specialist_version=task.agent_version,
        )
        self._conversation_index[key] = entry
        self.conversation.append(entry)
        self._trim_conversation()
        self._append_timeline(
            "agent.package_handoff",
            "planning",
            "agent confirmed registered package workflow; exact preview pending",
            task_id=task.task_id,
        )

    def _trim_conversation(self) -> None:
        marker_entries = [
            entry for entry in self.conversation if entry.key.startswith("context:omitted:")
        ]
        working = [entry for entry in self.conversation if entry not in marker_entries]
        visible_characters = sum(
            len(entry.text) for entry in working if entry.role in {"user", "agent", "jarvis"}
        )
        marker_characters = sum(
            len(entry.text) for entry in marker_entries if entry.role in {"user", "agent", "jarvis"}
        )
        if (
            len(working) + len(marker_entries) <= COLLECTION_LIMIT
            and visible_characters + marker_characters <= ACTIVE_CONTEXT_CHARACTER_LIMIT
        ):
            return

        starts = [index for index, entry in enumerate(working) if entry.role in {"user", "action"}]
        boundaries = starts if starts and starts[0] == 0 else [0, *starts]
        boundaries = sorted(set(boundaries))
        groups = [
            working[start : boundaries[index + 1] if index + 1 < len(boundaries) else len(working)]
            for index, start in enumerate(boundaries)
        ]
        removed: list[ConversationEntry] = list(marker_entries)
        while groups:
            flattened = [entry for group in groups for entry in group]
            characters = sum(
                len(entry.text) for entry in flattened if entry.role in {"user", "agent", "jarvis"}
            )
            if (
                len(flattened) <= COLLECTION_LIMIT - 1
                and characters + len(CONTEXT_OMISSION_TEXT) <= ACTIVE_CONTEXT_CHARACTER_LIMIT
            ):
                break
            removed.extend(groups.pop(0))

        retained = [entry for group in groups for entry in group]
        self._context_epoch += 1
        marker = ConversationEntry(
            key=f"context:omitted:{self._context_epoch}",
            role="jarvis",
            text=CONTEXT_OMISSION_TEXT,
            status="completed",
        )
        self.conversation = [marker, *retained]
        self._conversation_index[marker.key] = marker
        for entry in removed:
            self._conversation_index.pop(entry.key, None)

    @property
    def context_epoch(self) -> int:
        return self._context_epoch

    def reset_conversation(self, entries: tuple[ConversationEntry, ...] = ()) -> None:
        """Replace active view/context without retaining local results across sessions."""
        self._context_epoch += 1
        self.conversation = []
        self._conversation_index.clear()
        self._activity_index.clear()
        self.admissions.clear()
        for entry in entries:
            if entry.role == "activity":
                continue
            sanitized = ConversationEntry(
                key=entry.key,
                role=entry.role,
                text=safe_text(entry.text),
                status=entry.status,
                task_id=entry.task_id,
                turn_id=entry.turn_id,
                specialist_id=entry.specialist_id,
                specialist_version=entry.specialist_version,
            )
            self.conversation.append(sanitized)
            self._conversation_index[sanitized.key] = sanitized
            if sanitized.role == "activity":
                self._activity_index[sanitized.key] = sanitized
        self._trim_conversation()

    def context_snapshot(
        self, *, exclude_task_id: str | None = None
    ) -> ConversationContextSnapshot:
        """Return exactly the bounded, sanitized content visible in clean Conversation."""
        entries: list[ConversationContextEntry] = []
        for entry in self.conversation:
            if (
                exclude_task_id is not None and entry.task_id == exclude_task_id
            ) or entry.role not in {"user", "agent", "jarvis", "action", "system"}:
                continue
            text = safe_text(entry.text)
            if not text:
                continue
            entries.append(ConversationContextEntry(key=entry.key, role=entry.role, text=text))
        character_count = sum(len(entry.text) for entry in entries)
        return ConversationContextSnapshot(
            epoch=self._context_epoch,
            entries=tuple(entries),
            character_count=character_count,
        )

    def capture_pending_task(self, task: TaskRecord, *, display_text: str | None = None) -> None:
        """Project one captured request before any admission or network wait."""
        key = f"task:{task.task_id}"
        existing = self._conversation_index.get(key)
        if existing is not None:
            existing.status = "resolving_intent"
            return
        if task.action:
            parameters = json.dumps(
                task.intent.parameters,
                sort_keys=True,
                ensure_ascii=False,
                separators=(", ", ": "),
            )
            text = f"{task.action.title} [{task.action.id}@{task.action.version}]\n{parameters}"
            role = "action"
        else:
            text = display_text if display_text is not None else (task.intent.text or "")
            role = "user"
        entry = ConversationEntry(
            key=key,
            role=role,
            text=safe_text(text),
            status="resolving_intent",
            task_id=task.task_id,
            specialist_id=task.agent_id,
            specialist_version=task.agent_version,
        )
        self.conversation.append(entry)
        self._conversation_index[entry.key] = entry
        self._trim_conversation()
        self._append_timeline(
            "task.captured",
            "captured",
            f"{role} request captured; admission not yet decided",
            task_id=task.task_id,
        )
        self._append_timeline(
            "task.resolving_intent",
            "resolving_intent",
            "resolving intent; no execution authority granted",
            task_id=task.task_id,
        )

    def apply_assessment(self, task: TaskRecord) -> None:
        assessment = task.assessment
        if assessment is None:
            return
        entry = self._conversation_index.get(f"task:{task.task_id}")
        if assessment.decision == AssessmentDecision.CLARIFY:
            if entry:
                entry.status = "needs_clarification"
            self.add_local_conversation(
                f"{assessment.clarification_question}\nOptions: "
                + " / ".join(assessment.clarification_options),
                "needs_clarification",
                task_id=task.task_id,
            )
            self._append_timeline(
                "task.needs_clarification",
                "needs_clarification",
                f"no execution authority; {assessment.reason}",
                task_id=task.task_id,
            )
        elif assessment.decision == AssessmentDecision.DENY:
            if entry:
                entry.status = "blocked"
            self.add_local_conversation(
                f"The request was blocked safely: {assessment.reason}",
                "blocked",
                task_id=task.task_id,
            )
            self._append_timeline(
                "task.blocked",
                "blocked",
                f"policy block; no authority; {assessment.reason}",
                task_id=task.task_id,
            )

    def apply_admission(self, task: TaskRecord, admission: TaskAdmission) -> None:
        self.admissions[task.task_id] = admission
        entry = self._conversation_index.get(f"task:{task.task_id}")
        if entry:
            entry.status = admission.decision
        if admission.route.value == "local_read":
            summary = (
                "admitted to bounded local-read executor; read-only; no mutation or privilege"
                if admission.authority == "bounded-local-read"
                else "admitted to registered local read; no mutation or privilege"
            )
        elif admission.route.value == "local_mutation":
            summary = (
                "reviewed bounded local mutation; current-user filesystem only; "
                "execution withheld pending one fresh exact approval"
            )
        elif admission.route.value == "registered_mutation":
            summary = (
                "exact registered package mutation; execution withheld pending a bounded "
                "DNF preview and one fresh approval; privilege only through the root-owned helper"
            )
        elif admission.route.value == "agent_conversation":
            summary = (
                f"admitted to current-user agent surface; sandbox={admission.sandbox_policy}; "
                "exact App Server review boundary; mutation not authorized at admission"
            )
        else:
            summary = f"blocked; no authority; {admission.reason}"
        self._append_timeline(
            f"task.admitted.{admission.route.value}",
            admission.decision,
            summary,
            task_id=task.task_id,
        )

    def capture_task(self, task: TaskRecord, admission: TaskAdmission) -> None:
        """Compatibility wrapper for callers that already have admission."""
        self.capture_pending_task(task)
        self.apply_admission(task, admission)

    def mark_classifier_failure(
        self, task: TaskRecord, code: str, category: str | None = None
    ) -> None:
        diagnostic = code if not category else f"{code}; category={category}"
        entry = self._conversation_index.get(f"task:{task.task_id}")
        if entry:
            entry.status = "classifier_failed"
        self.add_local_conversation(
            f"Intent classification failed safely ({diagnostic}). This was an internal "
            "classifier/schema failure, not a policy denial; no operation ran.",
            "classifier_failed",
            task_id=task.task_id,
        )
        self._append_timeline(
            "task.classifier_failed",
            "classifier_failed",
            f"internal classification failure ({diagnostic}); this is not a policy-risk determination",
            task_id=task.task_id,
        )

    def mark_context_sync_failure(self, task: TaskRecord, code: str) -> None:
        entry = self._conversation_index.get(f"task:{task.task_id}")
        if entry:
            entry.status = "failed"
        self.add_local_conversation(
            "Conversation context could not be synchronized safely. No classifier or "
            "agent turn was submitted; please start a new conversation or reconnect once.",
            "failed",
            task_id=task.task_id,
        )
        self._append_timeline(
            "task.context_sync_failed",
            "failed",
            f"active conversation context synchronization failed ({code}); no model turn submitted",
            task_id=task.task_id,
        )

    def set_local_read_result(self, task: TaskRecord, result: LocalFilesystemReadResult) -> None:
        self.add_local_conversation(
            result.display_text,
            result.status,
            task_id=task.task_id,
        )
        self.update_task_status(task)
        limitations = ", ".join(result.applied_caps)
        self._append_timeline(
            "task.local_read.completed"
            if result.status == "completed"
            else "task.local_read.failed",
            result.status,
            (
                f"bounded local read {result.status}; results={result.result_count}; "
                f"files_examined={result.files_examined}; duration_ms={result.duration_ms}; "
                f"caps: {limitations}; error={result.error_code or 'none'}"
            ),
            task_id=task.task_id,
        )

    def mark_local_mutation_approved(self, task: TaskRecord) -> None:
        entry = self._conversation_index.get(f"task:{task.task_id}")
        if entry:
            entry.status = "approved"
        self._append_timeline(
            "task.local_mutation.approved",
            "approved_once",
            "fresh one-use approval captured for the exact reviewed plan",
            task_id=task.task_id,
        )

    def mark_local_mutation_declined(self, task: TaskRecord) -> None:
        self.add_local_conversation(
            "The filesystem change was not approved; nothing was changed.",
            "cancelled",
            task_id=task.task_id,
        )
        self._append_timeline(
            "task.local_mutation.cancelled",
            "cancelled",
            "user declined the exact mutation; no execution authority granted",
            task_id=task.task_id,
        )

    def set_local_mutation_result(
        self, task: TaskRecord, result: LocalFilesystemMutationResult
    ) -> None:
        self.add_local_conversation(
            result.display_text,
            result.status,
            task_id=task.task_id,
        )
        self.update_task_status(task)
        self._append_timeline(
            (
                "task.local_mutation.completed"
                if result.status == "completed"
                else "task.local_mutation.failed"
            ),
            result.status,
            (
                f"bounded local mutation {result.status}; operation={result.operation.value}; "
                f"duration_ms={result.duration_ms}; "
                f"rollback_available={str(result.rollback_available).lower()}; "
                f"error={result.error_code or 'none'}"
            ),
            task_id=task.task_id,
        )

    def mark_package_mutation_approved(self, task: TaskRecord) -> None:
        entry = self._conversation_index.get(f"task:{task.task_id}")
        if entry:
            entry.status = "approved"
        self._append_timeline(
            "task.package_mutation.approved",
            "approved_once",
            "fresh one-use approval captured for the exact DNF preview",
            task_id=task.task_id,
        )

    def set_package_mutation_result(self, task: TaskRecord, text: str, status: str) -> None:
        self.add_local_conversation(text, status, task_id=task.task_id)
        self.update_task_status(task)
        self._append_timeline(
            "task.package_mutation.completed"
            if status == "completed"
            else "task.package_mutation.terminal",
            status,
            f"registered package transaction {status}; one attempt; no automatic retry",
            task_id=task.task_id,
        )

    def mark_package_preview_failure(self, task: TaskRecord, code: str) -> None:
        self._append_timeline(
            "task.package_mutation.preview_failed",
            "failed",
            f"cache-only package preview failed safely; code={code}; no execution authority granted",
            task_id=task.task_id,
        )

    def mark_task_terminal(self, task: TaskRecord, reason: str) -> None:
        self.update_task_status(task)
        self._append_timeline(
            f"task.{task.state.value}",
            task.state.value,
            f"task {task.state.value}; {reason}",
            task_id=task.task_id,
            turn_id=task.turn_id,
        )

    def update_task_status(self, task: TaskRecord) -> None:
        entry = self._conversation_index.get(f"task:{task.task_id}")
        if entry:
            entry.status = task.state.value

    def _message(self, key: str, role: str, event: NormalizedEvent, replace: bool) -> None:
        text = safe_text(event.text or "")
        entry = self._conversation_index.get(key)
        if entry is None:
            entry = ConversationEntry(
                key=key,
                role=role,
                text=text,
                status=event.status,
                turn_id=event.turn_id,
            )
            self._conversation_index[key] = entry
            self.conversation.append(entry)
        elif replace:
            entry.text = text
            entry.status = event.status
        else:
            entry.text = safe_text(entry.text + text)
            entry.status = event.status
        self._trim_conversation()

    @staticmethod
    def _activity_title(event: NormalizedEvent) -> str:
        if event.kind == "tool_execution":
            tool_type = safe_text(
                event.metadata.get("tool") or event.metadata.get("tool_type", "tool"), 80
            )
            return f"Tool · {tool_type}"
        if event.kind == "command_output":
            return "Command output"
        if event.kind in {"plan_delta", "plan_message", "plan_updated"}:
            return "Plan"
        if event.kind == "reasoning_withheld":
            return "Reasoning · withheld"
        if event.kind == "server_request":
            return "Approval or input required"
        if event.kind == "server_request_resolved":
            return "Approval or input resolved"
        if event.kind == "turn_started":
            return "Agent turn"
        if event.kind == "turn_completed":
            return "Agent turn"
        if event.item_type:
            return f"Activity · {safe_text(event.item_type, 80)}"
        return safe_text(event.kind.replace("_", " ").title(), 100)

    @staticmethod
    def _activity_key(event: NormalizedEvent) -> str:
        if event.kind == "server_request":
            return f"activity:request:{event.request_id if event.request_id is not None else event.fingerprint}"
        if event.kind == "server_request_resolved":
            return f"activity:request:{event.request_id if event.request_id is not None else event.fingerprint}"
        if event.kind in {"turn_started", "turn_completed"}:
            return f"activity:{event.turn_id or 'unbound'}:turn"
        return f"activity:{event.turn_id or 'unbound'}:{event.item_id or event.kind}"

    def _activity_body(self, event: NormalizedEvent, existing: str = "") -> str:
        if event.kind == "reasoning_withheld":
            return "Private reasoning is withheld."
        if event.kind == "command_output":
            output = safe_text(event.text or "", _ACTIVITY_OUTPUT_LIMIT)
            previous = existing.split("\n", 1)[1] if "\n" in existing else ""
            combined = safe_text(previous + output, _ACTIVITY_OUTPUT_LIMIT)
            return combined or "No command output was supplied."
        details: list[str] = []
        if event.kind == "tool_execution" and event.metadata.get("query"):
            details.append("query: " + safe_text(event.metadata["query"], 160))
        if event.kind == "tool_execution" and event.metadata.get("command"):
            details.append(f"command: {safe_text(event.metadata['command'], 500)}")
        if event.kind == "tool_execution" and event.metadata.get("path"):
            details.append(f"path: {safe_text(event.metadata['path'], 500)}")
        if event.kind == "tool_execution" and event.metadata.get("cwd"):
            details.append(f"cwd: {safe_text(event.metadata['cwd'], 500)}")
        if event.kind == "server_request":
            details.append(f"request: {safe_text(event.method, 200)}")
            if event.metadata.get("reason"):
                details.append(f"reason: {safe_text(event.metadata['reason'], 500)}")
        if event.kind == "plan_updated":
            details.extend(
                f"{safe_text(item.get('status', 'unknown'), 40)} · {safe_text(item.get('step', ''), 300)}"
                for item in event.metadata.get("steps", [])
                if isinstance(item, dict)
            )
        if event.text and event.kind not in {"agent_delta", "agent_message"}:
            details.append(safe_text(event.text, _ACTIVITY_OUTPUT_LIMIT))
        return "\n".join(details) or f"status: {safe_text(event.status, 80)}"

    def _activity(self, event: NormalizedEvent) -> None:
        key = self._activity_key(event)
        if event.kind == "server_request_resolved" and key not in self._activity_index:
            return
        existing = self._activity_index.get(key)
        title = self._activity_title(event)
        body = self._activity_body(event, existing.text if existing else "")
        if event.kind == "tool_execution" and existing is not None:
            previous = existing.text.split("\n", 1)[1] if "\n" in existing.text else ""
            if previous and body.startswith("status:"):
                body = f"{previous}\n{body}"
        text = f"{title}\n{body}"
        if existing is None:
            entry = ConversationEntry(
                key=key,
                role="activity",
                text=safe_text(text, _ACTIVITY_OUTPUT_LIMIT + 1_000),
                status=event.status,
                turn_id=event.turn_id,
            )
            self._activity_index[key] = entry
            self._conversation_index[key] = entry
            self.conversation.append(entry)
        else:
            existing.text = safe_text(text, _ACTIVITY_OUTPUT_LIMIT + 1_000)
            existing.status = event.status
        self._trim_conversation()

    def add_local_activity(
        self, title: str, detail: str, status: str, *, task_id: str | None = None
    ) -> None:
        """Project a Jarvis-owned operation through the same activity-card lane."""
        key = f"activity:local:{task_id or title}"
        entry = self._activity_index.get(key)
        text = f"{safe_text(title, 160)}\n{safe_text(detail, _ACTIVITY_OUTPUT_LIMIT)}"
        if entry is None:
            entry = ConversationEntry(
                key=key,
                role="activity",
                text=text,
                status=safe_text(status, 80),
                task_id=task_id,
            )
            self._activity_index[key] = entry
            self._conversation_index[key] = entry
            self.conversation.append(entry)
        else:
            entry.text = text
            entry.status = safe_text(status, 80)
        self._trim_conversation()

    def finish_local_activity(self, task_id: str, status: str = "completed") -> None:
        """Close the immediate submission indicator once task dispatch settles."""
        entry = self._activity_index.get(f"activity:local:{task_id}")
        if entry is not None:
            entry.status = safe_text(status, 80)

    def set_activity_owner(self, owner: str) -> None:
        """Set the safe display label for the currently active specialist."""
        self.activity_owner = safe_text(owner, 100) or "Agent"

    def apply_event(self, event: NormalizedEvent) -> None:
        item_key = event.item_id or event.turn_id or event.fingerprint
        if event.kind == "agent_delta":
            self._message(f"agent:{item_key}", "agent", event, replace=False)
        elif event.kind == "agent_message":
            self._message(f"agent:{item_key}", "agent", event, replace=True)
            if event.turn_id:
                activity = [
                    entry
                    for entry in self.conversation
                    if entry.role == "activity" and entry.turn_id == event.turn_id
                ]
                agent = self._conversation_index.get(f"agent:{item_key}")
                if agent is not None and activity:
                    ordered = [
                        entry
                        for entry in self.conversation
                        if entry not in activity and entry is not agent
                    ]
                    position = ordered.index(agent) + 1
                    self.conversation = ordered[:position] + activity + ordered[position:]
        elif event.kind == "plan_delta":
            self.plan_text = safe_text(self.plan_text + (event.text or ""))
        elif event.kind == "plan_message":
            self.plan_text = safe_text(event.text or "")
        elif event.kind == "plan_updated":
            self.plan_steps = [
                PlanStepView(
                    step=safe_text(item.get("step", ""), 500),
                    status=safe_text(item.get("status", "unknown"), 50),
                )
                for item in event.metadata.get("steps", [])
                if isinstance(item, dict)
            ][:100]
        elif event.kind == "server_request":
            request_id = (
                str(event.request_id) if event.request_id is not None else event.fingerprint
            )
            self.codex_requests[request_id] = CodexServerRequestView(
                request_id=request_id,
                request_type=safe_text(event.method, 200),
                status="pending",
                thread_id=event.thread_id,
                turn_id=event.turn_id,
                item_id=event.item_id,
            )
        elif event.kind == "server_request_resolved":
            request_id = str(event.request_id) if event.request_id is not None else ""
            request = self.codex_requests.get(request_id)
            if request:
                request.status = "resolved"
        elif event.kind in {"warning", "error", "protocol_error", "disconnected"}:
            self._message(f"system:{event.fingerprint}", "system", event, replace=True)
        elif event.kind in {
            "unexpected_tool_item",
            "unexpected_tool_output",
            "unexpected_file_diff",
        }:
            self._message(
                f"blocked:{event.fingerprint}",
                "system",
                NormalizedEvent(
                    fingerprint=event.fingerprint,
                    method=event.method,
                    kind=event.kind,
                    status="blocked",
                    turn_id=event.turn_id,
                    item_id=event.item_id,
                    text=f"Unexpected {event.kind} was withheld and blocked.",
                ),
                replace=True,
            )
        elif event.kind == "item" and event.item_type:
            pass

        summary = event.kind
        if event.kind == "turn_completed":
            summary = f"turn completed: {event.status}"
        elif event.kind == "server_request":
            summary = f"blocked pending request: {event.method}"
        elif event.kind == "item" and event.item_type:
            summary = f"item {event.item_type}: {event.status}"
        elif event.text and event.kind in {"warning", "error"}:
            summary = f"{event.kind}: {event.text}"
        self._append_timeline(
            event.kind,
            event.status,
            summary,
            turn_id=event.turn_id,
        )

    def load_journal(self, events: tuple[dict[str, Any], ...]) -> None:
        projected: list[dict[str, Any]] = []
        omitted_protocol_events = 0
        material_normalized_kinds = {
            "disconnected",
            "error",
            "protocol_error",
            "server_request",
            "server_request_resolved",
            "turn_completed",
            "unexpected_file_diff",
            "unexpected_tool_item",
            "unexpected_tool_output",
        }
        for event in events:
            if event.get("event_type") == "codex.event.normalized":
                details = event.get("details")
                details = details if isinstance(details, dict) else {}
                kind = str(details.get("kind", "protocol_event"))
                if kind not in material_normalized_kinds:
                    omitted_protocol_events += 1
                    continue
            projected.append(event)

        omitted_material_events = max(0, len(projected) - JOURNAL_TIMELINE_LIMIT)
        if omitted_material_events:
            self._append_timeline(
                "journal.history.summary",
                "summarized",
                (
                    f"older material journal records omitted: {omitted_material_events}; "
                    "retained in the append-only audit journal"
                ),
            )
        if omitted_protocol_events:
            self._append_timeline(
                "codex.protocol.summary",
                "summarized",
                (
                    "legacy/non-material protocol records omitted: "
                    f"{omitted_protocol_events}; retained in the append-only audit journal"
                ),
            )

        for event in projected[-JOURNAL_TIMELINE_LIMIT:]:
            event_type = str(event.get("event_type", "event"))
            details = event.get("details")
            details = details if isinstance(details, dict) else {}
            kind = str(details.get("kind", ""))
            method = str(details.get("method", ""))
            summary = f"journal sequence {event.get('sequence', '?')}"
            if event_type == "codex.event.normalized" and kind:
                summary = f"codex {kind}; method={method or 'unknown'}; {summary}"
            self._append_timeline(
                event_type,
                str(event.get("status", "recorded")),
                summary,
                task_id=event.get("task_id"),
            )

    def refresh_overview(
        self,
        snapshot: SessionSnapshot,
        *,
        capabilities: int,
        enabled_actions: int,
        unavailable_actions: int,
        knowledge_status: dict[str, Any],
        recovered_tasks: int,
        jarvisd_status: dict[str, Any] | None = None,
        h1_scope: str = "not loaded",
        recovery_status: dict[str, Any] | None = None,
        phase5_status: dict[str, Any] | None = None,
    ) -> None:
        primary = snapshot.rate_limits.get("rate_limits") or {}
        window = primary.get("primary") or {}
        used = window.get("used_percent")
        reset = window.get("resets_at")
        rate_summary = "unavailable"
        if used is not None:
            rate_summary = f"{used}% used"
            if reset is not None:
                rate_summary += f"; resets at {reset}"
        self.overview = OverviewState(
            connection=snapshot.connection.value,
            auth=snapshot.plan_type or snapshot.auth_mode or "not connected",
            thread=snapshot.thread_status,
            active_turn=snapshot.active_turn_id or "none",
            pending_requests=len(snapshot.pending_requests),
            rate_limit_summary=rate_summary,
            capabilities=capabilities,
            enabled_actions=enabled_actions,
            unavailable_actions=unavailable_actions,
            knowledge=(
                f"read-only; integrity {knowledge_status.get('integrity', 'unknown')}"
                if knowledge_status.get("available")
                else str(knowledge_status.get("reason", "unavailable"))
            ),
            recovered_tasks=recovered_tasks,
            jarvisd=(jarvisd_status or {}).get("host_authority", "not connected"),
            h1_scope=h1_scope,
            recovery=self._recovery_summary(recovery_status or {}),
            phase5=self._phase5_summary(phase5_status or {}),
        )

    @staticmethod
    def _recovery_summary(value: dict[str, Any]) -> str:
        r1 = value.get("r1", {}).get("status", "unavailable")
        r2 = value.get("r2", {})
        r2_status = r2.get("status", "unavailable")
        mismatches = r2.get("mismatch_total")
        if mismatches is not None:
            r2_status = f"{r2_status}; mismatches={mismatches}"
        return f"R1={r1}; R2={r2_status}"

    @staticmethod
    def _phase5_summary(value: dict[str, Any]) -> str:
        status = value.get("status", "unavailable")
        rollback = value.get("rollback_verified")
        if rollback is not None:
            status += f"; rollback={str(rollback).lower()}"
        return status

    def set_knowledge_results(
        self,
        kind: str,
        query: str,
        results: tuple[dict[str, Any], ...],
    ) -> None:
        self.knowledge_kind = kind
        self.knowledge_query = safe_text(query, 500)
        self.knowledge_results = [
            safe_text(json.dumps(item, sort_keys=True, ensure_ascii=False, default=str), 4_000)
            for item in results[:100]
        ]
        self.knowledge_error = None
        self._append_timeline(
            "knowledge",
            "completed",
            f"local {kind} query returned {len(results)} result(s)",
        )

    def set_knowledge_error(self, kind: str, query: str, error: Exception) -> None:
        self.knowledge_kind = kind
        self.knowledge_query = safe_text(query, 500)
        self.knowledge_results = []
        self.knowledge_error = safe_text(type(error).__name__, 100)
        self._append_timeline(
            "knowledge",
            "failed",
            f"local {kind} query failed: {type(error).__name__}",
        )

    def render_overview(self) -> str:
        view = self.overview
        lines = [
            "SESSION",
            f"  connection: {view.connection}",
            f"  authentication: {view.auth}",
            f"  thread: {view.thread}",
            f"  active turn: {view.active_turn}",
            f"  pending requests: {view.pending_requests}",
            f"  capacity: {view.rate_limit_summary}",
            "LOCAL CONTROL PLANE",
            f"  capabilities: {view.capabilities}",
            f"  actions: {view.enabled_actions} enabled, {view.unavailable_actions} unavailable",
            f"  knowledge: {view.knowledge}",
            f"  recovered task records: {view.recovered_tasks}",
            "DIRECT-HOST SHADOW STATUS",
            f"  jarvisd: {view.jarvisd}",
            f"  H1 scope: {view.h1_scope}",
            f"  recovery evidence: {view.recovery}",
            "PHASE 5 EXECUTION FOUNDATION",
            f"  rehearsal: {view.phase5}",
            "SAFETY BOUNDARY",
            *(f"  {item}" for item in view.safety),
        ]
        return "\n".join(lines)

    def render_operational_console(self) -> tuple[str, ...]:
        view = self.operational
        return (
            "PHASE 6 OPERATIONAL CONSOLE — READ ONLY",
            f"AUTHORITY: {view.authority}",
            f"POLICY: {view.policy}",
            "",
            "ERRORS / ATTEMPTS (IMMUTABLE PROJECTION)",
            *(f"  {item}" for item in view.errors),
            "",
            "LESSONS (EVIDENCE-BACKED; USER PROMOTION ONLY)",
            *(f"  {item}" for item in view.lessons),
            "",
            "RECOVERY BOUNDARY",
            *(f"  {item}" for item in view.recovery),
            "",
            "SETTINGS / SAFE DEFAULTS",
            *(f"  {item}" for item in view.settings),
            "",
            "AUDIT / REDACTED EXPORT",
            *(f"  {item}" for item in view.audit),
            f"  {view.reconnect}",
            "",
            "NOTIFICATIONS",
            *(f"  {item}" for item in (view.notifications or ("none",))),
        )

    def redacted_operational_export(self) -> str:
        """Return a deterministic, bounded report payload without writing it."""
        view = self.operational
        allowed_authority = {
            "read-only",
            "H1 Tier-0 read-only enabled",
            "not connected",
        }
        payload = {
            "schema_version": 1,
            "kind": "jarvis.phase6.operational-report",
            "status": "read_only_projection",
            "authority": view.authority
            if view.authority in allowed_authority
            else "unavailable (unrecognized authority)",
            "policy": view.policy,
            "errors": list(view.errors),
            "lessons": list(view.lessons),
            "recovery": list(view.recovery),
            "settings": list(view.settings),
            "audit": list(view.audit),
            "notifications": ["notification_present"] * min(len(view.notifications), 8),
            "capabilities": {
                "trigger_observations": False,
                "execute_commands": False,
                "persist_facts": False,
                "mutate_policies": False,
                "answer_approvals": False,
            },
        }

        def sanitize_value(value: Any) -> Any:
            if isinstance(value, str):
                return redact_export_text(value, 500)
            if isinstance(value, list):
                return [sanitize_value(item) for item in value[:8]]
            if isinstance(value, dict):
                return {str(key): sanitize_value(item) for key, item in value.items()}
            return value

        encoded = json.dumps(
            sanitize_value(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if len(encoded) > 32_000:
            return json.dumps(
                {
                    "schema_version": 1,
                    "kind": "jarvis.phase6.operational-report",
                    "status": "unavailable",
                    "reason": "bounded_export_overflow",
                    "capabilities": {key: False for key in payload["capabilities"]},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        return encoded

    def deliver_redacted_operational_export(self, destination: Any) -> ExportDeliveryResult:
        """Deliver only after an explicit caller-selected destination is supplied."""
        return deliver_redacted_export(self.redacted_operational_export(), destination)

    def render_conversation(self) -> tuple[str, ...]:
        return tuple(
            f"[{entry.role.upper()} | {entry.status}]\n{entry.text}" for entry in self.conversation
        )

    def render_plan(self) -> tuple[str, ...]:
        lines = [f"[{step.status}] {step.step}" for step in self.plan_steps]
        if self.plan_text:
            lines.extend(("", self.plan_text))
        return tuple(lines or ["No agent plan has been received."])

    def render_knowledge(self) -> tuple[str, ...]:
        heading = f"{self.knowledge_kind} search: {self.knowledge_query or '(none)'}"
        if self.knowledge_error:
            return heading, f"Failed safely: {self.knowledge_error}"
        return tuple([heading, *(self.knowledge_results or ["No local results loaded."])])

    def render_approvals(self) -> tuple[str, ...]:
        lines = [
            "CODEX APP SERVER REQUESTS",
            "  Exact command/file decisions: approve once, decline, or cancel.",
        ]
        if self.codex_requests:
            for request in self.codex_requests.values():
                lines.append(
                    f"  [{request.status}] {request.request_type} · request {request.request_id} "
                    f"· turn {request.turn_id or 'unknown'}"
                )
        else:
            lines.append("  No App Server request has been received.")
        return tuple(lines)

    def render_timeline(self) -> tuple[str, ...]:
        return tuple(
            f"{entry.sequence:04d} | {entry.status:<18} | {entry.kind} | {entry.summary}"
            for entry in self.timeline
        )
