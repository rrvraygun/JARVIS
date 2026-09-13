import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from jarvis_tui.package_inventory import classify, parse_rpm_output, sort_records


class PackageInventoryTests(unittest.TestCase):
    def test_classifies_hardware_and_desktop_packages(self):
        self.assertEqual(classify("nvidia-driver", "NVIDIA graphics", "NVIDIA")[0], "nvidia/gpu")
        self.assertEqual(classify("gnome-shell", "GNOME desktop", "Fedora")[0], "gnome")
        self.assertEqual(classify("intel-media-driver", "Intel media", "Intel")[0], "intel")

    def test_parses_and_sorts_inventory(self):
        records = parse_rpm_output(
            "zeta|1|1|x86_64|Fedora|misc\nalpha|1|1|x86_64|Fedora|GNOME shell\n"
        )
        self.assertEqual(sort_records(records, "alphabetical")[0].name, "alpha")
        self.assertEqual(sort_records(records, "category")[0].category, "gnome")

    def test_rejects_unknown_sort(self):
        with self.assertRaises(ValueError):
            sort_records((), "random")


if __name__ == "__main__":
    unittest.main()
