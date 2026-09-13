#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import sys
import unittest


TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.terminal_safety import sanitize_terminal_text  # noqa: E402


class TerminalSafetyTests(unittest.TestCase):
    def test_terminal_controls_and_bidi_are_neutralized(self) -> None:
        hostile = "ok\x1b]0;forged-title\x07\n\x1b[31mred\x1b[0m\x9b32m\u202egpj.exe"
        safe, truncated = sanitize_terminal_text(hostile)
        self.assertFalse(truncated)
        self.assertNotIn("\x1b", safe)
        self.assertNotIn("\u202e", safe)
        self.assertNotIn("\x9b", safe)
        self.assertIn("[terminal-control]", safe)
        self.assertIn("[direction-control]", safe)

    def test_display_output_is_capped(self) -> None:
        safe, truncated = sanitize_terminal_text("abcdef", limit=3)
        self.assertTrue(truncated)
        self.assertTrue(safe.startswith("abc"))
        self.assertIn("truncated", safe)


if __name__ == "__main__":
    unittest.main()
