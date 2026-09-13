#!/usr/bin/env python3
from __future__ import annotations

import asyncio
from dataclasses import replace
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest


TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.local_filesystem import (  # noqa: E402
    BoundedLocalFilesystemExecutor,
    DISPLAY_LIMIT,
    LocalFilesystemPlanner,
)
from jarvis_tui.models import LocalReadOperation, LocalSearchMode  # noqa: E402


class LocalFilesystemTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addAsyncCleanup(self._cleanup)
        root = Path(self.temporary.name)
        self.home = root / "home"
        self.workspace = root / "workspace"
        self.desktop = self.home / "Mesa de trabajo"
        self.documents = self.home / "Documentos"
        self.downloads = self.home / "Descargas"
        for path in (self.workspace, self.desktop, self.documents, self.downloads):
            path.mkdir(parents=True, exist_ok=True)
        config = self.home / ".config/user-dirs.dirs"
        config.parent.mkdir(parents=True)
        config.write_text(
            "\n".join(
                (
                    'XDG_DESKTOP_DIR="$HOME/Mesa de trabajo"',
                    'XDG_DOCUMENTS_DIR="$HOME/Documentos"',
                    'XDG_DOWNLOAD_DIR="$HOME/Descargas"',
                    'IGNORED="$(touch should-not-run)"',
                )
            )
            + "\n",
            encoding="utf-8",
        )
        self.planner = LocalFilesystemPlanner(
            self.workspace,
            home=self.home,
            xdg_config=config,
            identifier=lambda prefix: f"{prefix}_fixture",
        )
        self.executor = BoundedLocalFilesystemExecutor(home=self.home)

    async def _cleanup(self) -> None:
        self.temporary.cleanup()

    def assert_plan(self, text: str):
        outcome = self.planner.plan(text)
        self.assertTrue(outcome.matched, text)
        self.assertIsNotNone(outcome.plan, text)
        return outcome.plan

    async def test_acceptance_request_uses_xdg_desktop_and_bounded_list(self) -> None:
        (self.desktop / "alpha.txt").write_text("alpha", encoding="utf-8")
        (self.desktop / "beta.txt").write_text("beta", encoding="utf-8")
        (self.desktop / ".hidden").write_text("hidden", encoding="utf-8")
        (self.desktop / "credentials").write_text("never display", encoding="utf-8")
        (self.desktop / "contraseñadriversgrafica.txt+").write_text(
            "never display", encoding="utf-8"
        )
        os.mkfifo(self.desktop / "special.pipe")
        plan = self.assert_plan("list the files inside Escritorio")
        self.assertEqual(plan.operation, LocalReadOperation.LIST)
        self.assertEqual(Path(plan.canonical_path), self.desktop)
        self.assertFalse(plan.recursive)
        self.assertEqual(plan.item_limit, 500)
        result = await self.executor.execute(plan)
        self.assertEqual(result.status, "completed")
        self.assertIn("alpha.txt", result.display_text)
        self.assertNotIn(".hidden", result.display_text)
        self.assertNotIn("credentials", result.display_text)
        self.assertNotIn("contraseñadriversgrafica", result.display_text)
        self.assertNotIn("special.pipe", result.display_text)
        self.assertEqual(result.skipped_hidden, 1)
        self.assertEqual(result.skipped_sensitive, 3)
        capped = replace(plan, item_limit=1, plan_digest="")
        capped_result = await self.executor.execute(capped)
        self.assertEqual(capped_result.result_count, 1)
        self.assertTrue(capped_result.truncated)

    def test_english_spanish_alias_absolute_and_workspace_relative_paths(self) -> None:
        target = self.workspace / "folder with spaces"
        target.mkdir()
        cases = {
            "listar los archivos en Documentos": self.documents,
            "lista los archivos de Descargas": self.downloads,
            f"list files in {self.desktop}": self.desktop,
            'list files in "folder with spaces"': target,
            "list files in workspace": self.workspace,
            "listar Escritorio": self.desktop,
            "list workspace/folder with spaces": target,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                plan = self.assert_plan(text)
                self.assertEqual(Path(plan.canonical_path), expected.resolve())

    def test_unique_and_ambiguous_locale_fallbacks(self) -> None:
        fallback_home = Path(self.temporary.name) / "fallback-home"
        fallback_home.mkdir()
        (fallback_home / "Escritorio").mkdir()
        planner = LocalFilesystemPlanner(
            self.workspace,
            home=fallback_home,
            xdg_config=fallback_home / "missing-user-dirs.dirs",
        )
        unique = planner.plan("list files in Desktop")
        self.assertEqual(Path(unique.plan.canonical_path), fallback_home / "Escritorio")  # type: ignore[union-attr]
        (fallback_home / "Desktop").mkdir()
        ambiguous = planner.plan("list files in Desktop")
        self.assertIsNotNone(ambiguous.clarification)
        self.assertEqual(ambiguous.clarification.code, "local_read.ambiguous_xdg_fallback")  # type: ignore[union-attr]
        self.assertEqual(len(ambiguous.clarification.options), 2)  # type: ignore[union-attr]

    async def test_file_read_truncation_binary_permission_special_and_sanitization(self) -> None:
        readable = self.workspace / "readable.txt"
        readable.write_text("token=abc123\nhello\x1b]0;forged\x07 world", encoding="utf-8")
        read_plan = self.assert_plan("read readable.txt")
        self.assertEqual(self.assert_plan("leer readable.txt").operation, LocalReadOperation.READ)
        result = await self.executor.execute(read_plan)
        self.assertEqual(result.status, "completed")
        self.assertIn("token=[redacted]", result.display_text)
        self.assertNotIn("abc123", result.display_text)
        self.assertNotIn("\x1b", result.display_text)

        oversized = self.workspace / "oversized.txt"
        oversized.write_text("x" * 80_000, encoding="utf-8")
        oversized_result = await self.executor.execute(self.assert_plan("read oversized.txt"))
        self.assertTrue(oversized_result.truncated)
        self.assertIn("source read truncated", oversized_result.display_text)
        self.assertLessEqual(len(oversized_result.display_text), DISPLAY_LIMIT + 100)

        binary = self.workspace / "binary.bin"
        binary.write_bytes(b"text\x00binary")
        binary_result = await self.executor.execute(self.assert_plan("read binary.bin"))
        self.assertEqual(binary_result.error_code, "local_read.binary_file_denied")

        permission = self.workspace / "permission.txt"
        permission.write_text("initially readable", encoding="utf-8")
        permission_plan = self.assert_plan("read permission.txt")
        permission.chmod(0)
        self.addCleanup(lambda: permission.chmod(stat.S_IRUSR | stat.S_IWUSR))
        permission_result = await self.executor.execute(permission_plan)
        self.assertEqual(permission_result.error_code, "local_read.permission_denied")

        fifo = self.workspace / "special.pipe"
        os.mkfifo(fifo)
        special = self.planner.plan("read special.pipe")
        self.assertEqual(special.denial_code, "local_read.special_file_denied")

    async def test_sensitive_target_and_symlink_escape_are_denied(self) -> None:
        ssh = self.home / ".ssh"
        ssh.mkdir()
        (ssh / "id_rsa").write_text("private", encoding="utf-8")
        denied = self.planner.plan(f"read {ssh / 'id_rsa'}")
        self.assertEqual(denied.denial_code, "local_read.sensitive_store")

        spanish_secret = self.workspace / "contraseñadriversgrafica.txt"
        spanish_secret.write_text("private", encoding="utf-8")
        spanish_denied = self.planner.plan("read contraseñadriversgrafica.txt")
        self.assertEqual(spanish_denied.denial_code, "local_read.sensitive_filename")
        spanish_store = self.workspace / "contraseñas"
        spanish_store.mkdir()
        (spanish_store / "notes.txt").write_text("private", encoding="utf-8")
        store_denial = self.planner.plan("list files in contraseñas")
        self.assertEqual(store_denial.denial_code, "local_read.sensitive_filename")

        sensitive_link = self.workspace / "sensitive-link.txt"
        sensitive_link.symlink_to(ssh / "id_rsa")
        linked_denial = self.planner.plan("read sensitive-link.txt")
        self.assertEqual(linked_denial.denial_code, "local_read.sensitive_store")

        safe_a = self.workspace / "safe-a.txt"
        safe_b = self.workspace / "safe-b.txt"
        safe_a.write_text("a", encoding="utf-8")
        safe_b.write_text("b", encoding="utf-8")
        link = self.workspace / "link.txt"
        link.symlink_to(safe_a)
        plan = self.assert_plan("read link.txt")
        link.unlink()
        link.symlink_to(safe_b)
        escaped = await self.executor.execute(plan)
        self.assertEqual(escaped.error_code, "local_read.symlink_changed")

        directory_link = self.workspace / "linked-dir"
        directory_link.symlink_to(self.desktop, target_is_directory=True)
        directory_denial = self.planner.plan("list files in linked-dir")
        self.assertEqual(directory_denial.denial_code, "local_read.directory_symlink_denied")

    async def test_filename_and_content_search_recursion_caps_hidden_and_sensitive_descent(
        self,
    ) -> None:
        nested = self.workspace / "nested"
        nested.mkdir()
        (self.workspace / "visible.txt").write_text("needle on line one", encoding="utf-8")
        (nested / "other.txt").write_text("another needle", encoding="utf-8")
        hidden = self.workspace / ".hidden"
        hidden.mkdir()
        (hidden / "hidden.txt").write_text("needle hidden", encoding="utf-8")
        sensitive = self.workspace / "credentials"
        sensitive.mkdir()
        (sensitive / "public.txt").write_text("needle secret", encoding="utf-8")

        filename_plan = self.assert_plan('find files named "*.txt" recursively in workspace')
        spanish_filename_plan = self.assert_plan(
            'buscar archivos llamados "*.txt" recursivamente en workspace'
        )
        self.assertEqual(filename_plan.search_mode, LocalSearchMode.FILENAME)
        self.assertEqual(spanish_filename_plan.search_mode, LocalSearchMode.FILENAME)
        filename_result = await self.executor.execute(filename_plan)
        self.assertIn("visible.txt", filename_result.display_text)
        self.assertIn("nested/other.txt", filename_result.display_text)
        self.assertNotIn("hidden.txt", filename_result.display_text)
        self.assertNotIn("public.txt", filename_result.display_text)

        hidden_plan = self.assert_plan(
            'find files named "*.txt" recursively including hidden files in workspace'
        )
        hidden_result = await self.executor.execute(hidden_plan)
        self.assertIn(".hidden/hidden.txt", hidden_result.display_text)
        self.assertNotIn("credentials/public.txt", hidden_result.display_text)

        content_plan = self.assert_plan('search contents for "needle" recursively in workspace')
        spanish_content_plan = self.assert_plan(
            'buscar contenido "needle" recursivamente en workspace'
        )
        content_result = await self.executor.execute(content_plan)
        self.assertEqual(content_plan.search_mode, LocalSearchMode.CONTENT)
        self.assertEqual(spanish_content_plan.search_mode, LocalSearchMode.CONTENT)
        self.assertIn("visible.txt:1", content_result.display_text)
        self.assertIn("nested/other.txt:1", content_result.display_text)
        self.assertGreaterEqual(content_result.skipped_sensitive, 1)

        capped = replace(content_plan, file_limit=1, match_limit=1, plan_digest="")
        capped_result = await self.executor.execute(capped)
        self.assertTrue(capped_result.truncated)
        self.assertLessEqual(capped_result.files_examined, 1)
        self.assertLessEqual(capped_result.result_count, 1)

        deadline = replace(content_plan, deadline_seconds=0.000001, plan_digest="")
        deadline_result = await self.executor.execute(deadline)
        self.assertTrue(deadline_result.deadline_reached)

    def test_broad_system_search_is_denied_before_execution(self) -> None:
        outcome = self.planner.plan('search contents for "needle" recursively in /etc')
        self.assertEqual(outcome.denial_code, "local_read.broad_system_search")

    def test_recognized_ambiguity_never_creates_a_plan(self) -> None:
        cases = (
            "list files",
            "read file",
            "buscar",
            "search for needle in workspace",
            "search contents for needle in workspace",
        )
        for text in cases:
            with self.subTest(text=text):
                outcome = self.planner.plan(text)
                self.assertTrue(outcome.matched)
                self.assertIsNone(outcome.plan)
                self.assertIsNotNone(outcome.clarification)
                self.assertIn(len(outcome.clarification.options), (2, 3))  # type: ignore[union-attr]

    def test_shell_syntax_never_enters_the_fast_path(self) -> None:
        outcome = self.planner.plan("list files in workspace; touch unexpected")
        self.assertFalse(outcome.matched)


if __name__ == "__main__":
    unittest.main()
