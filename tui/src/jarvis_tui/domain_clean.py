"""Human-readable, bounded projections for raw domain evidence."""

from __future__ import annotations

from typing import Any

EXPLANATIONS = {
    "available": "Whether the collector could retrieve evidence for this view.",
    "read_only": "Confirms this collection only read information and did not change the system.",
    "stale": "Whether the view fell back to an earlier local copy because refresh failed.",
    "error": "A short collection error code. It does not mean any system change was attempted.",
    "collected_at": "When this evidence was collected.",
    "installed_count": "Number of installed packages detected by the inventory.",
    "available_count": "Number of packages available from the local DNF cache.",
    "matches": "Entries matching this view's query or scope.",
    "sources": "Local sources used to prepare this evidence.",
}


def _label(path: str) -> str:
    return path.replace("_", " ").replace(".", " › ").capitalize()


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if value is None:
        return "Not available"
    if isinstance(value, list):
        return f"{len(value)} entries"
    if isinstance(value, dict):
        return f"{len(value)} fields"
    return str(value)[:240]


def fields(evidence: dict[str, Any], limit: int = 40) -> list[tuple[str, str, str]]:
    """Flatten safe scalar evidence without dumping raw nested JSON."""
    result: list[tuple[str, str, str]] = []

    def visit(path: str, value: Any) -> None:
        if len(result) >= limit:
            return
        if isinstance(value, dict):
            if not value:
                result.append(
                    (
                        path,
                        "No entries",
                        EXPLANATIONS.get(path.rsplit(".", 1)[-1], "No data was reported."),
                    )
                )
            for key, child in value.items():
                if isinstance(key, str):
                    visit(f"{path}.{key}" if path else key, child)
            return
        key = path.rsplit(".", 1)[-1]
        result.append(
            (
                _label(path),
                _value(value),
                EXPLANATIONS.get(
                    key, f"Value reported by the {path.replace('_', ' ')} evidence field."
                ),
            )
        )

    visit("", evidence)
    return result
