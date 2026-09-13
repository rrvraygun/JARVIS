#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest


TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.event_store import (  # noqa: E402
    EventJournal,
    JournalIntegrityError,
    ZERO_HASH,
    _canonical,
)


def write_chain(path: Path, count: int) -> None:
    previous = ZERO_HASH
    with path.open("wb") as handle:
        for sequence in range(1, count + 1):
            event = {
                "schema_version": 1,
                "sequence": sequence,
                "id": f"evt_fixture_{sequence}",
                "timestamp": "2026-08-20T00:00:00Z",
                "event_type": "fixture.event",
                "actor": "broker",
                "status": "recorded",
                "task_id": None,
                "details": {"index": sequence},
                "previous_hash": previous,
            }
            event["event_hash"] = hashlib.sha256(previous.encode() + _canonical(event)).hexdigest()
            handle.write(_canonical(event) + b"\n")
            previous = event["event_hash"]


class IncrementalEventJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "events.jsonl"

    def test_fourteen_thousand_record_prefix_is_parsed_once_for_subsequent_appends(self) -> None:
        write_chain(self.path, 14_000)
        journal = EventJournal(self.path)
        self.assertEqual(len(journal.read()), 14_000)
        self.assertEqual(journal.full_scan_count, 1)
        self.assertEqual(journal.cache_parsed_line_count, 14_000)
        journal.append("fixture.append", "broker", "completed", {"value": 1})
        journal.append("fixture.append", "broker", "completed", {"value": 2})
        self.assertEqual(journal.full_scan_count, 1)
        self.assertEqual(journal.cache_parsed_line_count, 14_000)
        self.assertEqual(journal.read()[-1]["sequence"], 14_002)
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_external_suffix_is_validated_incrementally_and_idempotency_is_constant_lookup(
        self,
    ) -> None:
        journal = EventJournal(self.path)
        first, created = journal.append_once(
            "operation:one", "fixture.reserve", "broker", "reserved", {}
        )
        self.assertTrue(created)
        again, created = journal.append_once(
            "operation:one", "fixture.reserve", "broker", "reserved", {}
        )
        self.assertFalse(created)
        self.assertEqual(again["id"], first["id"])
        other = EventJournal(self.path)
        other.append("fixture.external", "broker", "completed", {"external": True})
        before = journal.cache_parsed_line_count
        journal.append("fixture.local", "broker", "completed", {})
        self.assertEqual(journal.full_scan_count, 1)
        self.assertEqual(journal.incremental_scan_count, 1)
        self.assertEqual(journal.cache_parsed_line_count, before + 1)
        self.assertEqual(len(journal.read()), 3)

    def test_replacement_forces_full_rescan_and_independent_verify_detects_tampering(self) -> None:
        write_chain(self.path, 3)
        journal = EventJournal(self.path)
        journal.read()
        replacement = Path(self.temporary.name) / "replacement.jsonl"
        write_chain(replacement, 2)
        os.replace(replacement, self.path)
        self.assertEqual(len(journal.read()), 2)
        self.assertEqual(journal.full_scan_count, 2)
        records = list(journal.read())
        records[0]["details"]["index"] = 9
        self.path.write_text(
            "\n".join(json.dumps(item, sort_keys=True, separators=(",", ":")) for item in records)
            + "\n",
            encoding="utf-8",
        )
        valid, _, reason = journal.verify()
        self.assertFalse(valid)
        self.assertEqual(reason, "event_hash_mismatch")

    def test_in_place_change_evidence_forces_rescan_and_fails_closed(self) -> None:
        write_chain(self.path, 1)
        journal = EventJournal(self.path)
        event = journal.read()[0]
        event["status"] = "tampered"
        encoded = _canonical(event) + b"\n"
        original_size = self.path.stat().st_size
        if len(encoded) != original_size:
            event["status"] = "recorded"
            event["details"]["index"] = 2
            encoded = _canonical(event) + b"\n"
        self.assertEqual(len(encoded), original_size)
        self.path.write_bytes(encoded)
        with self.assertRaisesRegex(ValueError, "event_hash_mismatch"):
            journal.read()
        self.assertEqual(journal.full_scan_count, 2)

    def test_same_file_truncation_forces_a_full_verified_rescan(self) -> None:
        write_chain(self.path, 3)
        journal = EventJournal(self.path)
        self.assertEqual(len(journal.read()), 3)
        first_line = self.path.read_bytes().splitlines(keepends=True)[0]
        self.path.write_bytes(first_line)
        self.assertEqual(len(journal.read()), 1)
        self.assertEqual(journal.full_scan_count, 2)

    def test_in_place_prefix_change_plus_valid_suffix_cannot_bypass_cache(self) -> None:
        write_chain(self.path, 2)
        journal = EventJournal(self.path)
        records = list(journal.read())
        original = self.path.read_bytes()
        first, second = original.splitlines(keepends=True)
        tampered = dict(records[0])
        tampered["status"] = "tampered"
        tampered_first = _canonical(tampered) + b"\n"
        self.assertEqual(len(tampered_first), len(first))
        third = {
            "schema_version": 1,
            "sequence": 3,
            "id": "evt_fixture_3",
            "timestamp": "2026-08-20T00:00:00Z",
            "event_type": "fixture.event",
            "actor": "broker",
            "status": "recorded",
            "task_id": None,
            "details": {"index": 3},
            "previous_hash": records[1]["event_hash"],
        }
        third["event_hash"] = hashlib.sha256(
            third["previous_hash"].encode() + _canonical(third)
        ).hexdigest()
        self.path.write_bytes(tampered_first + second + _canonical(third) + b"\n")
        with self.assertRaisesRegex(JournalIntegrityError, "event_hash_mismatch"):
            journal.append("fixture.must_not_append", "broker", "completed", {})
        self.assertEqual(journal.full_scan_count, 2)


if __name__ == "__main__":
    unittest.main()
