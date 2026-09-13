"""Typed, execution-free contracts shared by the TUI and broker."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4


class IntentSource(StrEnum):
    NATURAL_LANGUAGE = "natural_language"
    CATALOG_ACTION = "catalog_action"
    CONTEXTUAL_ACTION = "contextual_action"
    AUTOMATION = "automation"


class TaskMode(StrEnum):
    OBSERVE = "observe"
    DIAGNOSE = "diagnose"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    RECOVER = "recover"
    LEARN = "learn"


class TaskState(StrEnum):
    CAPTURED = "captured"
    RESOLVING_INTENT = "resolving_intent"
    NEEDS_CLARIFICATION = "needs_clarification"
    PREFLIGHT = "preflight"
    PLANNING = "planning"
    BLOCKED = "blocked"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    DIAGNOSING_UNEXPECTED_RESULT = "diagnosing_unexpected_result"
    REPLANNING = "replanning"
    RECOVERY_PLANNING = "recovery_planning"
    AWAITING_RECOVERY_APPROVAL = "awaiting_recovery_approval"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AdmissionRoute(StrEnum):
    LOCAL_READ = "local_read"
    LOCAL_MUTATION = "local_mutation"
    REGISTERED_MUTATION = "registered_mutation"
    AGENT_CONVERSATION = "agent_conversation"
    BLOCKED = "blocked"


class AssessmentDecision(StrEnum):
    EXECUTE = "execute"
    CLARIFY = "clarify"
    DENY = "deny"


class IntentClass(StrEnum):
    EXPLAIN = "explain"
    INSPECT = "inspect"
    PROJECT_CHANGE = "project_change"
    HOST_CHANGE = "host_change"
    EXTERNAL_EFFECT = "external_effect"


class ExecutionRoute(StrEnum):
    CONVERSATION = "conversation"
    REGISTERED_WORKFLOW = "registered_workflow"
    REVIEWED_BASH = "reviewed_bash"
    LOCAL_READ = "local_read"
    LOCAL_MUTATION = "local_mutation"
    NONE = "none"


class LocalReadOperation(StrEnum):
    LIST = "list"
    READ = "read"
    SEARCH = "search"


class LocalSearchMode(StrEnum):
    FILENAME = "filename"
    CONTENT = "content"


class LocalMutationOperation(StrEnum):
    CREATE_DIRECTORY = "create_directory"
    CREATE_TEXT_FILE = "create_text_file"
    TRASH = "trash"


class PackageMutationOperation(StrEnum):
    INSTALL = "install"
    REMOVE = "remove"


class IntentAssessmentValidationError(ValueError):
    """Stable, non-sensitive validation failure for classifier output."""

    def __init__(self, code: str, category: str) -> None:
        super().__init__(code)
        self.code = code
        self.category = category


def _context_entry_digest(role: str, text: str) -> str:
    encoded = json.dumps(
        {"role": role, "text": text},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_digest(value: object, *, optional: bool = False) -> bool:
    return (optional and value is None) or (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


@dataclass(frozen=True)
class ConversationContextEntry:
    """One sanitized visible conversation item bound to a stable digest."""

    key: str
    role: str
    text: str
    digest: str = ""

    def __post_init__(self) -> None:
        if (
            not isinstance(self.key, str)
            or not self.key
            or self.role not in {"user", "action", "agent", "jarvis", "system"}
            or not isinstance(self.text, str)
            or not self.text
            or len(self.text) > 16_000
        ):
            raise ValueError("invalid conversation context entry")
        expected = _context_entry_digest(self.role, self.text)
        if not self.digest:
            object.__setattr__(self, "digest", expected)
        elif self.digest != expected:
            raise ValueError("conversation context entry digest mismatch")


@dataclass(frozen=True)
class ConversationContextSnapshot:
    """Bounded active-view context; content is never written to the audit journal."""

    epoch: int
    entries: tuple[ConversationContextEntry, ...]
    character_count: int
    digest: str = ""

    def __post_init__(self) -> None:
        expected_characters = sum(len(entry.text) for entry in self.entries)
        if (
            not isinstance(self.epoch, int)
            or isinstance(self.epoch, bool)
            or self.epoch < 0
            or expected_characters != self.character_count
            or self.character_count > 64_000
            or len(self.entries) > 500
            or len({entry.key for entry in self.entries}) != len(self.entries)
        ):
            raise ValueError("invalid conversation context snapshot")
        encoded = json.dumps(
            {
                "epoch": self.epoch,
                "entries": [{"key": entry.key, "digest": entry.digest} for entry in self.entries],
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        expected_digest = hashlib.sha256(encoded).hexdigest()
        if not self.digest:
            object.__setattr__(self, "digest", expected_digest)
        elif self.digest != expected_digest:
            raise ValueError("conversation context snapshot digest mismatch")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass(frozen=True)
class ActionDefinition:
    id: str
    version: str
    title: str
    summary: str
    category: str
    capability: str
    procedure: str
    mode: TaskMode
    input_schema: dict[str, Any]
    required_facts: tuple[str, ...]
    risk_floor: int
    mutates_host: bool
    invokes_agent: bool
    availability: str
    implementation_status: str
    unavailable_reason: str | None = None
    tags: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ActionDefinition:
        required = {
            "id",
            "version",
            "title",
            "summary",
            "category",
            "capability",
            "procedure",
            "mode",
            "input_schema",
            "required_facts",
            "risk_floor",
            "mutates_host",
            "invokes_agent",
            "availability",
            "implementation_status",
        }
        missing = sorted(required - value.keys())
        if missing:
            raise ValueError(f"action is missing fields: {', '.join(missing)}")
        if value["availability"] not in {"enabled", "disabled", "unavailable"}:
            raise ValueError("invalid action availability")
        risk = int(value["risk_floor"])
        if risk < 0 or risk > 4:
            raise ValueError("risk_floor must be between 0 and 4")
        return cls(
            id=str(value["id"]),
            version=str(value["version"]),
            title=str(value["title"]),
            summary=str(value["summary"]),
            category=str(value["category"]),
            capability=str(value["capability"]),
            procedure=str(value["procedure"]),
            mode=TaskMode(value["mode"]),
            input_schema=dict(value["input_schema"]),
            required_facts=tuple(value["required_facts"]),
            risk_floor=risk,
            mutates_host=bool(value["mutates_host"]),
            invokes_agent=bool(value["invokes_agent"]),
            availability=str(value["availability"]),
            implementation_status=str(value["implementation_status"]),
            unavailable_reason=value.get("unavailable_reason"),
            tags=tuple(value.get("tags", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["mode"] = self.mode.value
        value["required_facts"] = list(self.required_facts)
        value["tags"] = list(self.tags)
        return value


@dataclass(frozen=True)
class IntentEnvelope:
    intent_id: str
    session_id: str
    source: IntentSource
    requested_mode: TaskMode
    text: str | None
    action_id: str | None
    action_version: str | None
    parameters: dict[str, Any]
    constraints: tuple[str, ...]
    created_at: str
    schema_version: int = 1

    def __post_init__(self) -> None:
        if not self.text and not self.action_id:
            raise ValueError("an intent requires text or an action_id")
        if self.action_id and not self.action_version:
            raise ValueError("an action intent requires action_version")
        if self.source == IntentSource.NATURAL_LANGUAGE and not self.text:
            raise ValueError("natural-language intent requires text")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["source"] = self.source.value
        value["requested_mode"] = self.requested_mode.value
        value["constraints"] = list(self.constraints)
        return value


@dataclass(frozen=True)
class IntentAssessment:
    """Validated authority envelope produced before an execution-capable turn."""

    assessment_id: str
    decision: AssessmentDecision
    intent_class: IntentClass
    operation: str
    targets: tuple[str, ...]
    risk: int
    route: ExecutionRoute
    reason: str
    clarification_question: str | None = None
    clarification_options: tuple[str, ...] = ()
    schema_version: int = 1

    def __post_init__(self) -> None:
        if (
            self.schema_version != 1
            or not isinstance(self.assessment_id, str)
            or not self.assessment_id
            or not isinstance(self.operation, str)
            or not self.operation.strip()
            or len(self.operation) > 300
            or not isinstance(self.reason, str)
            or not self.reason.strip()
            or len(self.reason) > 500
            or not isinstance(self.targets, tuple)
            or len(self.targets) > 32
            or any(
                not isinstance(item, str) or not item.strip() or len(item) > 1000
                for item in self.targets
            )
            or not isinstance(self.decision, AssessmentDecision)
            or not isinstance(self.intent_class, IntentClass)
            or not isinstance(self.route, ExecutionRoute)
            or not isinstance(self.clarification_options, tuple)
            or (
                self.clarification_question is not None
                and not isinstance(self.clarification_question, str)
            )
        ):
            raise IntentAssessmentValidationError("preflight.invalid_shape", "required_field")
        if (
            not isinstance(self.risk, int)
            or isinstance(self.risk, bool)
            or self.risk < 0
            or self.risk > 4
        ):
            raise IntentAssessmentValidationError("preflight.invalid_shape", "risk")
        if self.decision == AssessmentDecision.EXECUTE:
            if self.route == ExecutionRoute.NONE:
                raise IntentAssessmentValidationError("preflight.invalid_route", "execute_route")
            if self.intent_class != IntentClass.EXPLAIN and not self.targets:
                raise IntentAssessmentValidationError("preflight.missing_target", "execute_target")
            if (
                self.intent_class == IntentClass.EXPLAIN
                and self.route != ExecutionRoute.CONVERSATION
            ):
                raise IntentAssessmentValidationError("preflight.invalid_route", "explain_route")
            if self.clarification_question or self.clarification_options:
                raise IntentAssessmentValidationError(
                    "preflight.invalid_decision_variant", "execute_clarification"
                )
        elif self.decision == AssessmentDecision.CLARIFY:
            if (
                not self.clarification_question
                or len(self.clarification_question) > 300
                or not 2 <= len(self.clarification_options) <= 3
                or any(len(item) > 160 for item in self.clarification_options)
            ):
                raise IntentAssessmentValidationError(
                    "preflight.invalid_clarification", "clarification_fields"
                )
            if self.route != ExecutionRoute.NONE:
                raise IntentAssessmentValidationError(
                    "preflight.invalid_route", "clarification_route"
                )
            if self.targets:
                raise IntentAssessmentValidationError(
                    "preflight.invalid_decision_variant", "clarification_target"
                )
        else:
            if self.route != ExecutionRoute.NONE:
                raise IntentAssessmentValidationError("preflight.invalid_route", "deny_route")
            if self.targets or self.clarification_question or self.clarification_options:
                raise IntentAssessmentValidationError(
                    "preflight.invalid_decision_variant", "deny_authority_fields"
                )

    @property
    def requires_confirmation(self) -> bool:
        return self.risk >= 2 or self.intent_class in {
            IntentClass.HOST_CHANGE,
            IntentClass.EXTERNAL_EFFECT,
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any], assessment_id: str) -> IntentAssessment:
        if not isinstance(value, dict):
            raise IntentAssessmentValidationError("preflight.invalid_shape", "root_type")
        required = {
            "decision",
            "intent_class",
            "operation",
            "targets",
            "risk",
            "route",
            "reason",
            "clarification_question",
            "clarification_options",
        }
        missing = required - value.keys()
        if missing:
            code = (
                "preflight.missing_target" if missing == {"targets"} else "preflight.invalid_shape"
            )
            raise IntentAssessmentValidationError(code, "missing_field")
        if value.keys() - required:
            raise IntentAssessmentValidationError("preflight.invalid_shape", "additional_field")
        targets = value["targets"]
        options = value.get("clarification_options", [])
        if (
            not isinstance(targets, list)
            or len(targets) > 32
            or not all(
                isinstance(item, str) and item.strip() and len(item) <= 1000 for item in targets
            )
        ):
            raise IntentAssessmentValidationError("preflight.invalid_shape", "targets")
        if (
            not isinstance(options, list)
            or len(options) > 3
            or not all(
                isinstance(item, str) and item.strip() and len(item) <= 160 for item in options
            )
        ):
            raise IntentAssessmentValidationError(
                "preflight.invalid_clarification", "clarification_options"
            )
        if (
            not isinstance(value["operation"], str)
            or not value["operation"].strip()
            or len(value["operation"]) > 300
        ):
            raise IntentAssessmentValidationError("preflight.invalid_shape", "operation")
        if (
            not isinstance(value["reason"], str)
            or not value["reason"].strip()
            or len(value["reason"]) > 500
        ):
            raise IntentAssessmentValidationError("preflight.invalid_shape", "reason")
        if not isinstance(value["risk"], int) or isinstance(value["risk"], bool):
            raise IntentAssessmentValidationError("preflight.invalid_shape", "risk")
        question = value["clarification_question"]
        if question is not None and (
            not isinstance(question, str) or not question.strip() or len(question) > 300
        ):
            raise IntentAssessmentValidationError(
                "preflight.invalid_clarification", "clarification_question"
            )
        try:
            decision = AssessmentDecision(value["decision"])
            intent_class = IntentClass(value["intent_class"])
        except (TypeError, ValueError) as exc:
            raise IntentAssessmentValidationError(
                "preflight.invalid_decision_variant", "decision_enum"
            ) from exc
        try:
            route = ExecutionRoute(value["route"])
        except (TypeError, ValueError) as exc:
            raise IntentAssessmentValidationError("preflight.invalid_route", "route_enum") from exc
        if route in {ExecutionRoute.LOCAL_READ, ExecutionRoute.LOCAL_MUTATION}:
            raise IntentAssessmentValidationError(
                "preflight.invalid_route", "model_local_route_requires_bound_plan"
            )
        return cls(
            assessment_id=assessment_id,
            decision=decision,
            intent_class=intent_class,
            operation=value["operation"].strip(),
            targets=tuple(item.strip() for item in targets),
            risk=value["risk"],
            route=route,
            reason=value["reason"].strip(),
            clarification_question=question.strip() if isinstance(question, str) else None,
            clarification_options=tuple(item.strip() for item in options),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["decision"] = self.decision.value
        value["intent_class"] = self.intent_class.value
        value["route"] = self.route.value
        value["targets"] = list(self.targets)
        value["clarification_options"] = list(self.clarification_options)
        return value


@dataclass(frozen=True)
class LocalFilesystemReadPlan:
    """Immutable, digest-bound plan for one bounded local filesystem read."""

    plan_id: str
    operation: LocalReadOperation
    original_target: str
    requested_path: str
    canonical_path: str
    target_category: str
    target_digest: str
    target_device: int
    target_inode: int
    target_mode: int
    search_mode: LocalSearchMode | None
    query: str | None
    query_digest: str | None
    recursive: bool
    max_depth: int
    item_limit: int
    file_limit: int
    byte_limit: int
    per_file_byte_limit: int
    match_limit: int
    deadline_seconds: float
    include_hidden: bool
    plan_digest: str
    schema_version: int = 1

    def binding_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "operation": self.operation.value,
            "original_target": self.original_target,
            "requested_path": self.requested_path,
            "canonical_path": self.canonical_path,
            "target_category": self.target_category,
            "target_digest": self.target_digest,
            "target_device": self.target_device,
            "target_inode": self.target_inode,
            "target_mode": self.target_mode,
            "search_mode": self.search_mode.value if self.search_mode else None,
            "query": self.query,
            "query_digest": self.query_digest,
            "recursive": self.recursive,
            "max_depth": self.max_depth,
            "item_limit": self.item_limit,
            "file_limit": self.file_limit,
            "byte_limit": self.byte_limit,
            "per_file_byte_limit": self.per_file_byte_limit,
            "match_limit": self.match_limit,
            "deadline_seconds": self.deadline_seconds,
            "include_hidden": self.include_hidden,
        }

    def expected_digest(self) -> str:
        encoded = json.dumps(
            self.binding_payload(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    def __post_init__(self) -> None:
        if (
            self.schema_version != 1
            or not isinstance(self.operation, LocalReadOperation)
            or (self.search_mode is not None and not isinstance(self.search_mode, LocalSearchMode))
            or not isinstance(self.plan_id, str)
            or not self.plan_id
            or not isinstance(self.original_target, str)
            or not self.original_target.strip()
            or not isinstance(self.requested_path, str)
            or not self.requested_path
            or not isinstance(self.canonical_path, str)
            or not self.canonical_path
            or not isinstance(self.target_category, str)
            or not self.target_category
            or not _is_digest(self.target_digest)
            or not isinstance(self.target_device, int)
            or isinstance(self.target_device, bool)
            or not isinstance(self.target_inode, int)
            or isinstance(self.target_inode, bool)
            or not isinstance(self.target_mode, int)
            or isinstance(self.target_mode, bool)
            or self.target_device < 0
            or self.target_inode < 0
            or self.target_mode < 0
            or not isinstance(self.recursive, bool)
            or not isinstance(self.include_hidden, bool)
            or not isinstance(self.max_depth, int)
            or isinstance(self.max_depth, bool)
            or not isinstance(self.item_limit, int)
            or isinstance(self.item_limit, bool)
            or not isinstance(self.file_limit, int)
            or isinstance(self.file_limit, bool)
            or not isinstance(self.byte_limit, int)
            or isinstance(self.byte_limit, bool)
            or not isinstance(self.per_file_byte_limit, int)
            or isinstance(self.per_file_byte_limit, bool)
            or not isinstance(self.match_limit, int)
            or isinstance(self.match_limit, bool)
            or not isinstance(self.deadline_seconds, (int, float))
            or isinstance(self.deadline_seconds, bool)
            or not 1 <= self.item_limit <= 500
            or not 1 <= self.file_limit <= 2_000
            or not 1 <= self.byte_limit <= 64 * 1024
            or not 1 <= self.per_file_byte_limit <= 1024 * 1024
            or not 1 <= self.match_limit <= 200
            or not 0 < self.deadline_seconds <= 10
            or not 0 <= self.max_depth <= 8
            or (not self.recursive and self.max_depth != 0)
            or (self.recursive and self.max_depth == 0)
            or (self.operation == LocalReadOperation.READ and self.recursive)
        ):
            raise ValueError("invalid local read plan shape or bounds")
        if self.operation == LocalReadOperation.SEARCH:
            if (
                self.search_mode is None
                or not isinstance(self.query, str)
                or not self.query
                or len(self.query) > 1_000
                or not _is_digest(self.query_digest)
                or self.query_digest != hashlib.sha256(self.query.encode()).hexdigest()
            ):
                raise ValueError("search plan requires a mode and query binding")
        elif (
            self.search_mode is not None or self.query is not None or self.query_digest is not None
        ):
            raise ValueError("non-search plan cannot contain search fields")
        if not self.plan_digest:
            object.__setattr__(self, "plan_digest", self.expected_digest())
        elif self.plan_digest != self.expected_digest():
            raise ValueError("local read plan digest mismatch")

    def to_dict(self) -> dict[str, Any]:
        value = self.binding_payload()
        value["plan_digest"] = self.plan_digest
        return value


@dataclass(frozen=True)
class LocalFilesystemMutationPlan:
    """One exact, reversible current-user filesystem mutation proposal.

    File content is held only in memory.  The binding and serialized audit form
    contain its digest and size, never the content itself.
    """

    plan_id: str
    operation: LocalMutationOperation
    original_target: str
    target_path: str
    parent_path: str
    target_category: str
    target_digest: str
    parent_device: int
    parent_inode: int
    parent_mode: int
    existing_device: int | None
    existing_inode: int | None
    existing_mode: int | None
    content: str | None
    content_digest: str | None
    content_bytes: int
    rollback: str
    risk: int
    plan_digest: str
    schema_version: int = 1

    def binding_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "operation": self.operation.value,
            "original_target": self.original_target,
            "target_path": self.target_path,
            "parent_path": self.parent_path,
            "target_category": self.target_category,
            "target_digest": self.target_digest,
            "parent_device": self.parent_device,
            "parent_inode": self.parent_inode,
            "parent_mode": self.parent_mode,
            "existing_device": self.existing_device,
            "existing_inode": self.existing_inode,
            "existing_mode": self.existing_mode,
            "content_digest": self.content_digest,
            "content_bytes": self.content_bytes,
            "rollback": self.rollback,
            "risk": self.risk,
        }

    def expected_digest(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.binding_payload(),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()

    def __post_init__(self) -> None:
        if (
            self.schema_version != 1
            or not isinstance(self.operation, LocalMutationOperation)
            or not self.plan_id
            or not self.original_target
            or not self.target_path
            or not self.parent_path
            or not self.target_category
            or not _is_digest(self.target_digest)
            or not all(
                isinstance(value, int) and not isinstance(value, bool) and value >= 0
                for value in (self.parent_device, self.parent_inode, self.parent_mode)
            )
            or self.risk not in {1, 2}
            or not self.rollback
            or self.content_bytes < 0
            or self.content_bytes > 64 * 1024
        ):
            raise ValueError("invalid local mutation plan")
        existing = (self.existing_device, self.existing_inode, self.existing_mode)
        if any(value is None for value in existing) != all(value is None for value in existing):
            raise ValueError("partial existing-target identity")
        if self.operation == LocalMutationOperation.TRASH:
            if any(value is None for value in existing) or self.content is not None:
                raise ValueError("trash plan requires an existing target and no content")
        else:
            if any(value is not None for value in existing):
                raise ValueError("create plan requires an absent target")
        if self.operation == LocalMutationOperation.CREATE_TEXT_FILE:
            if self.content is None:
                raise ValueError("text-file plan requires content")
            encoded = self.content.encode("utf-8")
            if len(encoded) != self.content_bytes or not _is_digest(self.content_digest):
                raise ValueError("text-file content binding is invalid")
            if hashlib.sha256(encoded).hexdigest() != self.content_digest:
                raise ValueError("text-file content digest mismatch")
        elif self.content is not None or self.content_digest is not None or self.content_bytes:
            raise ValueError("non-file-create plan cannot carry content")
        if not self.plan_digest:
            object.__setattr__(self, "plan_digest", self.expected_digest())
        elif self.plan_digest != self.expected_digest():
            raise ValueError("local mutation plan digest mismatch")

    def to_dict(self) -> dict[str, Any]:
        value = self.binding_payload()
        value["plan_digest"] = self.plan_digest
        return value


@dataclass(frozen=True)
class MutationReview:
    plan_digest: str
    decision: str
    code: str
    summary: str
    rollback: str
    review_digest: str = ""
    schema_version: int = 1

    def __post_init__(self) -> None:
        material = {
            "schema_version": self.schema_version,
            "plan_digest": self.plan_digest,
            "decision": self.decision,
            "code": self.code,
            "summary": self.summary,
            "rollback": self.rollback,
        }
        expected = hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if (
            self.schema_version != 1
            or self.decision not in {"allow_for_user_review", "deny"}
            or len(self.plan_digest) != 64
            or not self.code
            or not self.summary
            or not self.rollback
        ):
            raise ValueError("invalid mutation review")
        if not self.review_digest:
            object.__setattr__(self, "review_digest", expected)
        elif self.review_digest != expected:
            raise ValueError("mutation review digest mismatch")


@dataclass(frozen=True)
class OneUseApproval:
    approval_id: str
    plan_digest: str
    review_digest: str
    approved_at: str

    def __post_init__(self) -> None:
        if (
            not self.approval_id
            or not self.approved_at
            or any(
                len(value) != 64 or any(character not in "0123456789abcdef" for character in value)
                for value in (self.plan_digest, self.review_digest)
            )
        ):
            raise ValueError("invalid one-use approval")


@dataclass(frozen=True)
class PackageTransactionPlan:
    plan_id: str
    operation: PackageMutationOperation
    packages: tuple[str, ...]
    rollback: str
    risk: int
    plan_digest: str = ""
    schema_version: int = 1

    def binding_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "operation": self.operation.value,
            "packages": list(self.packages),
            "rollback": self.rollback,
            "risk": self.risk,
        }

    def __post_init__(self) -> None:
        import re

        name = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.:-]{0,199}$")
        if (
            self.schema_version != 1
            or not isinstance(self.operation, PackageMutationOperation)
            or not self.plan_id
            or not 1 <= len(self.packages) <= 20
            or len(set(self.packages)) != len(self.packages)
            or any(not name.fullmatch(value) for value in self.packages)
            or not self.rollback
            or self.risk != 3
        ):
            raise ValueError("invalid package transaction plan")
        expected = hashlib.sha256(
            json.dumps(self.binding_payload(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if not self.plan_digest:
            object.__setattr__(self, "plan_digest", expected)
        elif self.plan_digest != expected:
            raise ValueError("package transaction plan digest mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**self.binding_payload(), "plan_digest": self.plan_digest}


@dataclass(frozen=True)
class PackageCatalogSearchPlan:
    """One bounded read-only query against the cached Fedora catalog."""

    plan_id: str
    query: str
    target: str = "cached-dnf-catalog"
    risk: int = 0
    plan_digest: str = ""
    schema_version: int = 1

    def binding_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "query": self.query,
            "target": self.target,
            "risk": self.risk,
        }

    def __post_init__(self) -> None:
        if (
            self.schema_version != 1
            or not self.plan_id
            or not isinstance(self.query, str)
            or not 1 <= len(self.query) <= 4_000
            or self.target != "cached-dnf-catalog"
            or self.risk != 0
        ):
            raise ValueError("invalid package catalog search plan")
        expected = hashlib.sha256(
            json.dumps(self.binding_payload(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if not self.plan_digest:
            object.__setattr__(self, "plan_digest", expected)
        elif self.plan_digest != expected:
            raise ValueError("package catalog search plan digest mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**self.binding_payload(), "plan_digest": self.plan_digest}


@dataclass(frozen=True)
class PowerProfileDraftPlan:
    """Bounded, read-only profile draft request before activation approval."""

    plan_id: str
    name: str
    goal: str
    scope: str
    plan_digest: str = ""
    schema_version: int = 1

    def binding_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "plan_id": self.plan_id,
            "name": self.name,
            "goal": self.goal,
            "scope": self.scope,
        }

    def __post_init__(self) -> None:
        if (
            self.schema_version != 1
            or not self.plan_id
            or not 1 <= len(self.name) <= 120
            or self.goal not in {"battery", "performance", "quiet", "thermal", "balanced"}
            or self.scope not in {"ac", "battery", "both"}
        ):
            raise ValueError("invalid power profile draft plan")
        expected = hashlib.sha256(
            json.dumps(self.binding_payload(), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if not self.plan_digest:
            object.__setattr__(self, "plan_digest", expected)
        elif self.plan_digest != expected:
            raise ValueError("power profile draft plan digest mismatch")

    def to_dict(self) -> dict[str, Any]:
        return {**self.binding_payload(), "plan_digest": self.plan_digest}


@dataclass
class TaskRecord:
    task_id: str
    session_id: str
    intent: IntentEnvelope
    state: TaskState
    created_at: str
    updated_at: str
    action: ActionDefinition | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    item_ids: list[str] = field(default_factory=list)
    agent_id: str | None = None
    agent_version: str | None = None
    assessment: IntentAssessment | None = None
    local_read_plan: LocalFilesystemReadPlan | None = None
    local_mutation_plan: LocalFilesystemMutationPlan | None = None
    mutation_review: MutationReview | None = None
    package_plan: PackageTransactionPlan | None = None
    package_catalog_plan: PackageCatalogSearchPlan | None = None
    power_profile_plan: PowerProfileDraftPlan | None = None
    schema_version: int = 1
    pipeline_version: str = "3.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "intent": self.intent.to_dict(),
            "state": self.state.value,
            "pipeline_version": self.pipeline_version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "action": self.action.to_dict() if self.action else None,
            "assessment": self.assessment.to_dict() if self.assessment else None,
            "local_read_plan": self.local_read_plan.to_dict() if self.local_read_plan else None,
            "local_mutation_plan": self.local_mutation_plan.to_dict()
            if self.local_mutation_plan
            else None,
            "mutation_review": asdict(self.mutation_review) if self.mutation_review else None,
            "package_plan": self.package_plan.to_dict() if self.package_plan else None,
            "package_catalog_plan": self.package_catalog_plan.to_dict()
            if self.package_catalog_plan
            else None,
            "power_profile_plan": self.power_profile_plan.to_dict()
            if self.power_profile_plan
            else None,
            "codex": {
                "thread_id": self.thread_id,
                "turn_id": self.turn_id,
                "item_ids": list(self.item_ids),
            },
            "agent": {
                "id": self.agent_id,
                "version": self.agent_version,
            }
            if self.agent_id
            else None,
        }


@dataclass(frozen=True)
class TaskAdmission:
    schema_version: int
    task_id: str
    route: AdmissionRoute
    decision: str
    host_authority: str
    sandbox_policy: str | None
    execution_authorized: bool
    agent_turn_authorized: bool
    mutation_authorized: bool
    authority: str
    reason: str
    action_id: str | None
    action_version: str | None
    procedure: str | None
    assessment_id: str | None
    intent_class: str | None
    risk: int | None
    route_name: str | None
    target_digest: str | None
    plan_digest: str | None
    approval_required: bool
    approval_state: str
    review_digest: str | None
    policy_digest: str

    def __post_init__(self) -> None:
        if (
            self.schema_version != 3
            or not isinstance(self.route, AdmissionRoute)
            or not isinstance(self.task_id, str)
            or not self.task_id
            or not isinstance(self.reason, str)
            or not self.reason
        ):
            raise ValueError("invalid task admission shape")
        if (
            not _is_digest(self.target_digest, optional=True)
            or not _is_digest(self.plan_digest, optional=True)
            or not _is_digest(self.review_digest, optional=True)
            or not _is_digest(self.policy_digest, optional=True)
        ):
            raise ValueError("invalid task admission digest")
        local_authority = (
            "bounded-local-read" if self.plan_digest is not None else "registered-local-read"
        )
        expected = {
            AdmissionRoute.LOCAL_READ: (
                "allow_local_read_only",
                "none",
                None,
                True,
                False,
                False,
                local_authority,
                False,
                "not_required",
            ),
            AdmissionRoute.LOCAL_MUTATION: (
                "awaiting_one_use_approval",
                "current-user-filesystem",
                None,
                False,
                False,
                False,
                "bounded-local-mutation",
                True,
                "pending",
            ),
            AdmissionRoute.REGISTERED_MUTATION: (
                "awaiting_one_use_approval",
                "registered-root-helper",
                None,
                False,
                False,
                False,
                "registered-package-mutation",
                True,
                "pending",
            ),
            AdmissionRoute.AGENT_CONVERSATION: (
                "allow_scoped_execution",
                "agent-read-only",
                "readOnly",
                True,
                True,
                False,
                "current-user-agent",
                False,
                "at_tool_boundary",
            ),
            AdmissionRoute.BLOCKED: (
                "deny",
                "none",
                None,
                False,
                False,
                False,
                "none",
                False,
                "not_required",
            ),
        }[self.route]
        actual = (
            self.decision,
            self.host_authority,
            self.sandbox_policy,
            self.execution_authorized,
            self.agent_turn_authorized,
            self.mutation_authorized,
            self.authority,
            self.approval_required,
            self.approval_state,
        )
        if actual != expected:
            raise ValueError("task admission authority fields are inconsistent")
        if (
            self.route
            not in {
                AdmissionRoute.LOCAL_READ,
                AdmissionRoute.LOCAL_MUTATION,
                AdmissionRoute.REGISTERED_MUTATION,
            }
            and self.plan_digest is not None
        ):
            raise ValueError("only a local executor admission may bind a local plan")
        if self.route == AdmissionRoute.LOCAL_READ:
            if self.target_digest is None:
                raise ValueError("local-read admission requires a target binding")
            if self.route_name == ExecutionRoute.LOCAL_READ.value:
                if self.plan_digest is None or self.authority != "bounded-local-read":
                    raise ValueError("filesystem local-read admission requires a plan binding")
            elif (
                self.route_name != ExecutionRoute.REGISTERED_WORKFLOW.value
                or self.plan_digest is not None
                or self.authority != "registered-local-read"
                or not self.action_id
                or not self.action_version
                or not self.procedure
            ):
                raise ValueError("registered local-read admission requires an action binding")
        if self.route == AdmissionRoute.LOCAL_MUTATION:
            if self.plan_digest is None or self.target_digest is None or self.review_digest is None:
                raise ValueError(
                    "local mutation admission requires plan, target, and review bindings"
                )
        elif self.review_digest is not None:
            if self.route != AdmissionRoute.REGISTERED_MUTATION:
                raise ValueError("only a mutation admission may bind a review")
        if self.route == AdmissionRoute.REGISTERED_MUTATION:
            if self.plan_digest is None or self.target_digest is None or self.review_digest is None:
                raise ValueError(
                    "registered mutation admission requires plan, target, and review bindings"
                )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["route"] = self.route.value
        return value


@dataclass(frozen=True)
class RecoveredTask:
    """Non-sensitive task metadata reconstructed from the broker journal."""

    task_id: str
    state: TaskState
    thread_id: str | None
    turn_id: str | None
    last_sequence: int
    requires_user_resubmit: bool
    uncertain_operation: bool
