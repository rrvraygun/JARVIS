"""Deterministic Power Expert profile-intent parsing."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PowerProfileIntent:
    name: str | None = None
    goal: str | None = None
    scope: str | None = None
    question: str | None = None
    options: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return self.name is not None and self.goal is not None and self.scope is not None


def parse_power_profile_intent(text: str) -> PowerProfileIntent | None:
    lowered = text.casefold()
    if "profile" not in lowered or not any(
        word in lowered for word in ("create", "new", "design", "optimi", "setup", "set up")
    ):
        return None
    if (
        "max performance" in lowered
        and any(word in lowered for word in ("low-demand", "low demand", "low-requir"))
        and "new low-demand" not in lowered
    ):
        return PowerProfileIntent(
            question="Which power-profile setup do you want?",
            options=(
                "Separate Performance and Low-demand profiles",
                "One balanced profile for both",
                "Performance profile only",
            ),
        )
    if any(
        word in lowered
        for word in ("low-demand", "low demand", "low-requir", "battery saver", "quiet")
    ):
        goal = "quiet"
        name = "Low-demand"
    elif "performance" in lowered:
        goal = "performance"
        name = "Performance"
    elif "balanced" in lowered:
        goal = "balanced"
        name = "Balanced"
    elif "thermal" in lowered:
        goal = "thermal"
        name = "Thermal"
    elif "battery" in lowered:
        goal = "battery"
        name = "Battery"
    else:
        return PowerProfileIntent(
            question="What should the new power profile optimize for?",
            options=("Battery life", "Maximum performance", "Quiet or low-demand operation"),
        )
    if "both ac and battery" in lowered or "ac and battery" in lowered:
        scope = "both"
    elif "battery power only" in lowered or "battery only" in lowered:
        scope = "battery"
    elif "ac power only" in lowered or "ac only" in lowered:
        scope = "ac"
    else:
        return PowerProfileIntent(
            name=name,
            goal=goal,
            question=f"When should the {name.casefold()} profile be used?",
            options=("Battery power only", "Both AC and battery", "AC power only"),
        )
    return PowerProfileIntent(name=name, goal=goal, scope=scope)
