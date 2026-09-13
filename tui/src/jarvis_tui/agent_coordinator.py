"""Explicit user-selected specialist routing and bounded context metadata."""

from __future__ import annotations

from dataclasses import dataclass

from .agent_registry import AgentRegistry
from .specialists import Specialist


@dataclass(frozen=True)
class SpecialistContext:
    """The non-secret context contract attached to one captured task."""

    specialist_id: str
    specialist_version: str
    context_limit: int
    transcript_policy: str

    def prompt_constraint(self, specialist: Specialist) -> str:
        return (
            specialist.context_prompt()
            + "\nSelected agent routing: this specialist was explicitly selected by the user; "
            "do not infer or switch specialists from the request."
            + "\nContext contract: the visible conversation is authoritative continuity data; "
            "use it when sufficient and keep any additional evidence bounded and evidence-labeled."
        )


class AgentCoordinator:
    """Coordinate selection without allowing model output to grant authority."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    def selected(self) -> Specialist | None:
        return self.registry.selected()

    def select(self, specialist_id: str) -> Specialist:
        return self.registry.select(specialist_id)

    def context(self, specialist: Specialist | None = None) -> SpecialistContext | None:
        selected = specialist or self.selected()
        if selected is None:
            return None
        return SpecialistContext(
            specialist_id=selected.id,
            specialist_version=selected.version,
            context_limit=selected.context_limit,
            transcript_policy=selected.retention,
        )

    def constraints(self, specialist: Specialist | None = None) -> tuple[str, ...]:
        selected = specialist or self.selected()
        context = self.context(selected)
        if selected is None or context is None:
            return ()
        return (context.prompt_constraint(selected),)

    def scope_message(self, specialist: Specialist | None = None) -> str:
        selected = specialist or self.selected()
        if selected is None:
            return "No specialist is currently available; no execution authority was granted."
        return (
            f"{selected.display_name} is selected. It will clarify or decline requests outside "
            "its declared scope; the system will not switch agents automatically."
        )
