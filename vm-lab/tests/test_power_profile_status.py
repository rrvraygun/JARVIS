from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import power_profile_status as STATUS


class FakeProperties:
    def __init__(self, values: dict[str, object]) -> None:
        self.values = values
        self.calls: list[str] = []

    def GetAll(self, interface: str) -> dict[str, object]:
        self.calls.append(interface)
        return self.values


class FakeProxy:
    def __init__(self, values: dict[str, object]) -> None:
        self.properties = FakeProperties(values)


class FakeBus:
    def __init__(self, values: dict[str, object]) -> None:
        self.proxy = FakeProxy(values)
        self.calls: list[tuple[str, str]] = []

    def get_object(self, name: str, path: str) -> FakeProxy:
        self.calls.append((name, path))
        return self.proxy


def valid_properties() -> dict[str, object]:
    return {
        "ActiveProfile": "balanced",
        "Profiles": [
            {"Profile": "power-saver", "Driver": "tuned"},
            {"Profile": "balanced", "Driver": "tuned"},
            {"Profile": "performance", "Driver": "tuned"},
        ],
        "PerformanceDegraded": "",
    }


class PowerProfileStatusTests(unittest.TestCase):
    def test_parse_normalizes_and_marks_read_only(self) -> None:
        values = valid_properties()
        values["Profiles"] = list(reversed(values["Profiles"]))  # type: ignore[arg-type]
        result = STATUS.parse_properties(values)
        self.assertEqual(result.active_profile, "balanced")
        self.assertEqual(
            [entry["Profile"] for entry in result.profiles], list(STATUS.PROFILE_NAMES)
        )
        self.assertTrue(result.as_dict()["read_only"])

    def test_reader_uses_only_fixed_bus_object_and_get_all(self) -> None:
        bus = FakeBus(valid_properties())

        class NoDbus:
            PROPERTIES_IFACE = "org.freedesktop.DBus.Properties"

            @staticmethod
            def Interface(proxy: FakeProxy, interface: str) -> FakeProperties:
                if interface != "org.freedesktop.DBus.Properties":
                    raise AssertionError("unexpected D-Bus interface")
                return proxy.properties

        # The production reader imports dbus lazily; replace it with a tiny
        # test module so the test never touches the host bus or writes state.
        import builtins

        original_import = builtins.__import__

        def fake_import(name: str, *args: object, **kwargs: object):
            if name == "dbus":
                return NoDbus
            return original_import(name, *args, **kwargs)

        builtins.__import__ = fake_import
        try:
            result = STATUS.FixedDbusPowerProfileReader(lambda: bus).read()
        finally:
            builtins.__import__ = original_import
        self.assertEqual(result.active_profile, "balanced")
        self.assertEqual(bus.calls, [(STATUS.BUS_NAME, STATUS.OBJECT_PATH)])
        self.assertEqual(bus.proxy.properties.calls, [STATUS.INTERFACE])

    def test_rejects_unknown_active_profile(self) -> None:
        values = valid_properties()
        values["ActiveProfile"] = "jarvis-balanced"
        with self.assertRaisesRegex(STATUS.PowerProfileStatusError, "unsupported active"):
            STATUS.parse_properties(values)

    def test_rejects_active_profile_missing_from_set(self) -> None:
        values = valid_properties()
        values["Profiles"] = [
            entry for entry in values["Profiles"] if entry["Profile"] != "balanced"
        ]  # type: ignore[index]
        with self.assertRaisesRegex(STATUS.PowerProfileStatusError, "not in"):
            STATUS.parse_properties(values)

    def test_rejects_duplicate_or_unknown_profiles(self) -> None:
        duplicate = valid_properties()
        duplicate["Profiles"] = list(duplicate["Profiles"]) + [
            {"Profile": "balanced", "Driver": "tuned"}
        ]  # type: ignore[arg-type]
        with self.assertRaisesRegex(STATUS.PowerProfileStatusError, "duplicate"):
            STATUS.parse_properties(duplicate)
        unknown = valid_properties()
        unknown["Profiles"] = list(unknown["Profiles"]) + [
            {"Profile": "jarvis-balanced", "Driver": "tuned"}
        ]  # type: ignore[arg-type]
        with self.assertRaisesRegex(STATUS.PowerProfileStatusError, "unsupported profile"):
            STATUS.parse_properties(unknown)

    def test_rejects_unexpected_driver(self) -> None:
        values = valid_properties()
        values["Profiles"] = [{"Profile": "balanced", "Driver": "untrusted"}]
        with self.assertRaisesRegex(STATUS.PowerProfileStatusError, "profile driver"):
            STATUS.parse_properties(values)

    def test_rejects_unbounded_or_unknown_degraded_state(self) -> None:
        for degraded in ("unknown", "x" * 4097, "\n"):
            values = valid_properties()
            values["PerformanceDegraded"] = degraded
            with (
                self.subTest(degraded=degraded),
                self.assertRaisesRegex(STATUS.PowerProfileStatusError, "performance-degraded"),
            ):
                STATUS.parse_properties(values)

    def test_rejects_malformed_provider_response(self) -> None:
        for values in (
            {"ActiveProfile": "balanced"},
            {"ActiveProfile": "balanced", "Profiles": "balanced"},
        ):
            with (
                self.subTest(values=values),
                self.assertRaises(STATUS.PowerProfileStatusError),
            ):
                STATUS.parse_properties(values)


if __name__ == "__main__":
    unittest.main()
