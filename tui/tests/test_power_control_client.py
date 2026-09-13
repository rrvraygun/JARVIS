#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.power_control_client import (
    apply_change,
    authoritative_undo_status,
    helper_available,
    load_undo,
    undo_last,
)  # noqa: E402


class FakeRunner:
    def __init__(self) -> None:
        self.argv: list[list[str]] = []

    def __call__(self, argv: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        self.argv.append(argv)
        if "apply" in argv:
            output = {
                "status": "passed",
                "control": "cpu.epp",
                "pre_state": {"targets": {"cpu0": "balance_power"}},
                "post_value": "performance",
            }
        elif "status" in argv:
            output = {
                "status": "passed",
                "operation": "status",
                "control": "cpu.epp",
                "post_value": "performance",
                "record_digest": "a" * 64,
            }
        else:
            output = {
                "status": "passed",
                "control": "cpu.epp",
                "restored": {"cpu0": "balance_power"},
                "undone_value": "performance",
            }
        return subprocess.CompletedProcess(argv, 0, json.dumps(output), "")


class PowerControlClientTests(unittest.TestCase):
    def test_apply_persists_exact_undo_and_undo_consumes_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper = root / "helper"
            helper.write_text("fixture", encoding="utf-8")
            helper.chmod(0o755)
            journal = root / "state/last.json"
            runner = FakeRunner()
            result = apply_change(
                "cpu.epp",
                "performance",
                "balance_power",
                helper=helper,
                journal=journal,
                runner=runner,
                require_root_owned=False,
            )
            self.assertEqual(result["status"], "passed")
            self.assertEqual(load_undo(journal)["post_value"], "performance")
            status = authoritative_undo_status(
                helper=helper, runner=runner, require_root_owned=False
            )
            restored = undo_last(
                status["record_digest"],
                helper=helper,
                journal=journal,
                runner=runner,
                require_root_owned=False,
            )
            self.assertEqual(restored["status"], "passed")
            self.assertFalse(journal.exists())
            self.assertEqual(runner.argv[-1][-2:], ["--record-digest", "a" * 64])

    def test_authoritative_prepared_recovery_status_is_accepted(self) -> None:
        class RecoveryRunner(FakeRunner):
            def __call__(
                self, argv: list[str], **kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                result = super().__call__(argv, **kwargs)
                if "status" in argv:
                    value = json.loads(result.stdout)
                    value["operation"] = "recovery-status"
                    return subprocess.CompletedProcess(argv, 0, json.dumps(value), "")
                return result

        with tempfile.TemporaryDirectory() as directory:
            helper = Path(directory) / "helper"
            helper.write_text("fixture", encoding="utf-8")
            helper.chmod(0o755)
            status = authoritative_undo_status(
                helper=helper, runner=RecoveryRunner(), require_root_owned=False
            )
            self.assertEqual(status["operation"], "recovery-status")

    def test_helper_symlink_is_never_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_text("fixture", encoding="utf-8")
            target.chmod(0o755)
            link = root / "helper"
            link.symlink_to(target)
            self.assertFalse(helper_available(link, require_root_owned=False))


if __name__ == "__main__":
    unittest.main()
