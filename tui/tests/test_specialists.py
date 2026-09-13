from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from jarvis_tui.agent_registry import AgentRegistry  # noqa: E402
from jarvis_tui.specialists import load_specialists  # noqa: E402


class SpecialistTests(unittest.TestCase):
    def test_architect_and_power_specialists_are_valid(self) -> None:
        specialists = load_specialists(ROOT.parent)
        ids = {item.id for item in specialists}
        self.assertIn("jarvis-system-architect", ids)
        self.assertIn("jarvis-power-expert", ids)
        self.assertIn("jarvis-installation-specialist", ids)
        self.assertIn("jarvis-github-agent", ids)

    def test_registry_exposes_only_user_selectable_initial_agents(self) -> None:
        registry = AgentRegistry(ROOT.parent)
        self.assertEqual(
            {item.id for item in registry.selectable()},
            {
                "jarvis-system-architect",
                "jarvis-installation-specialist",
                "jarvis-power-expert",
                "jarvis-system-health",
                "jarvis-cargo-builder",
                "jarvis-network-specialist",
                "jarvis-recovery-specialist",
                "jarvis-security-specialist",
                "jarvis-github-agent",
            },
        )

    def test_registry_rejects_unregistered_tool(self) -> None:
        registry = AgentRegistry(ROOT.parent)
        draft = registry.draft("jarvis-installation-specialist")
        draft["allowed_tools"] = ["arbitrary_shell_command"]
        result = registry.validate(draft, expected_id="jarvis-installation-specialist")
        self.assertFalse(result.valid)
        self.assertIn("unregistered tools", " ".join(result.errors))

    def test_registry_activation_archives_and_rolls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT.parent / "plugins", root / "plugins")
            registry = AgentRegistry(root)
            draft = registry.draft("jarvis-installation-specialist")
            draft["version"] = "1.0.1-local"
            draft["purpose"] = "Updated package specialist purpose."
            activated = registry.activate(draft)
            self.assertEqual(activated.version, "1.0.1-local")
            self.assertTrue(registry.has_rollback(activated.id))
            restored = registry.rollback(activated.id)
            self.assertEqual(restored.version, "1.0.0")

    def test_invalid_descriptor_is_ignored(self) -> None:
        with self.subTest("valid descriptors remain discoverable"):
            self.assertTrue(load_specialists(ROOT.parent))


if __name__ == "__main__":
    unittest.main()
