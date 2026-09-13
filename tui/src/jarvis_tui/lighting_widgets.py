"""Small keyboard-accessible graphical range control for the Lighting pane."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button, Label, ProgressBar, Static


class LightingRangeControl(Static):
    """A bounded slider-like control built from a progress bar and +/- buttons."""

    class Changed(Message):
        def __init__(self, control: LightingRangeControl, value: int) -> None:
            super().__init__()
            self.source_control = control
            self.value = value

    def __init__(
        self,
        *,
        control_id: str,
        label: str,
        minimum: int,
        maximum: int,
        value: int,
        step: int = 1,
    ) -> None:
        super().__init__(id=control_id)
        if minimum > maximum or not minimum <= value <= maximum or step < 1:
            raise ValueError("invalid lighting range")
        self.control_id = control_id
        self.label = label
        self.minimum = minimum
        self.maximum = maximum
        self.value = value
        self.step = step

    def compose(self) -> ComposeResult:
        yield Label(f"{self.label}: {self.value}", id=f"{self.control_id}-value")
        with Horizontal(classes="lighting-range-line"):
            yield Button("−", id=f"{self.control_id}-down", compact=True)
            yield ProgressBar(
                total=self.maximum - self.minimum,
                show_eta=False,
                show_percentage=True,
                id=f"{self.control_id}-bar",
            )
            yield Button("+", id=f"{self.control_id}-up", compact=True)

    def on_mount(self) -> None:
        self._refresh()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == f"{self.control_id}-down":
            self.set_value(self.value - self.step)
        elif event.button.id == f"{self.control_id}-up":
            self.set_value(self.value + self.step)

    def on_key(self, event) -> None:  # Textual's keyboard event type varies across pinned versions.
        if event.key in {"left", "down"}:
            self.set_value(self.value - self.step)
            event.stop()
        elif event.key in {"right", "up"}:
            self.set_value(self.value + self.step)
            event.stop()

    def set_value(self, value: int) -> None:
        bounded = max(self.minimum, min(self.maximum, int(value)))
        if bounded == self.value:
            return
        self.value = bounded
        self._refresh()
        self.post_message(self.Changed(self, bounded))

    def _refresh(self) -> None:
        if not self.is_mounted:
            return
        self.query_one(f"#{self.control_id}-value", Label).update(f"{self.label}: {self.value}")
        self.query_one(f"#{self.control_id}-bar", ProgressBar).progress = self.value - self.minimum


__all__ = ["LightingRangeControl"]
