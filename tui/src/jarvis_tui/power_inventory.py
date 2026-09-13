"""Bounded, read-only inventory of host power drivers and settings."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

MAX_TEXT_BYTES = 16 * 1024
MAX_DEVICES = 32


@dataclass(frozen=True)
class PowerSetting:
    section: str
    setting: str
    current: str
    choices: str
    source: str
    writable_by_jarvis: bool = False
    control_id: str | None = None
    provider: str = "kernel"
    risk: int = 0
    depth: str = "basic"
    available: bool = True


@dataclass(frozen=True)
class PowerTelemetry:
    battery_capacity: str = "unavailable"
    battery_status: str = "unavailable"
    battery_rate: str = "unavailable"
    ac_online: str = "unavailable"
    temperatures: tuple[str, ...] = ()
    active_profile: str = "unavailable"
    collected_at: str = ""


@dataclass(frozen=True)
class PowerInventory:
    providers: tuple[str, ...]
    settings: tuple[PowerSetting, ...]
    limitations: tuple[str, ...]
    hardware: tuple[str, ...] = ()
    software: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    telemetry: PowerTelemetry = PowerTelemetry()


def _bounded_text(root: Path, relative: str, *, default: str = "unavailable") -> str:
    boundary = root.resolve()
    candidate = root / relative
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(boundary)
        if not resolved.is_file():
            return default
        data = resolved.read_bytes()
        if len(data) > MAX_TEXT_BYTES or b"\x00" in data:
            return default
        value = data.decode("utf-8", errors="strict").strip()
        return " ".join(value.split()) if value else default
    except (OSError, UnicodeError, ValueError):
        return default


def _setting(
    root: Path, section: str, name: str, relative: str, choices: str = "—"
) -> PowerSetting:
    return PowerSetting(section, name, _bounded_text(root, relative), choices, f"/{relative}")


def _fixed_command(argv: list[str], *, timeout: float = 3.0) -> str:
    result = subprocess.run(
        argv, check=True, capture_output=True, text=True, timeout=timeout, shell=False
    )
    if len(result.stdout.encode()) > MAX_TEXT_BYTES:
        raise RuntimeError("power provider output exceeded limit")
    return result.stdout.strip()


def _hardware_summary(root: Path) -> tuple[str, ...]:
    """Return sanitized hardware classes; never expose serials or UUIDs."""
    values: list[str] = []
    for label, relative in (
        ("System vendor", "sys/class/dmi/id/sys_vendor"),
        ("Product model", "sys/class/dmi/id/product_name"),
        ("Firmware version", "sys/class/dmi/id/bios_version"),
        ("CPU online topology", "sys/devices/system/cpu/online"),
    ):
        value = _bounded_text(root, relative)
        if value != "unavailable":
            values.append(f"{label}: {value}")
    try:
        cards = sorted((root / "sys/class/drm").glob("card[0-9]"))[:MAX_DEVICES]
    except OSError:
        cards = []
    for card in cards:
        vendor = _bounded_text(root, f"sys/class/drm/{card.name}/device/vendor")
        if vendor != "unavailable":
            values.append(f"GPU {card.name}: vendor {vendor}")
    try:
        supplies = sorted((root / "sys/class/power_supply").iterdir())[:MAX_DEVICES]
    except OSError:
        supplies = []
    for supply in supplies:
        kind = _bounded_text(root, f"sys/class/power_supply/{supply.name}/type")
        values.append(f"Power supply {supply.name}: {kind}")
    return tuple(dict.fromkeys(values))


def _software_summary() -> tuple[str, ...]:
    names = (
        "tuned-adm",
        "tlp-stat",
        "auto-cpufreq",
        "powertop",
        "busctl",
    )
    return tuple(
        f"{name}: {'available' if shutil.which(name) else 'unavailable'}" for name in names
    )


def scan_power_telemetry(*, root: Path = Path("/")) -> PowerTelemetry:
    """Read passive battery, AC, thermal, and profile values for live display."""
    root = root.resolve()
    capacity = status = rate = ac_online = "unavailable"
    try:
        supplies = sorted((root / "sys/class/power_supply").iterdir())[:MAX_DEVICES]
    except OSError:
        supplies = []
    for supply in supplies:
        kind = _bounded_text(root, f"sys/class/power_supply/{supply.name}/type").casefold()
        if kind == "battery" and capacity == "unavailable":
            capacity = _bounded_text(root, f"sys/class/power_supply/{supply.name}/capacity")
            status = _bounded_text(root, f"sys/class/power_supply/{supply.name}/status")
            rate = _bounded_text(root, f"sys/class/power_supply/{supply.name}/power_now")
            if rate == "unavailable":
                rate = _bounded_text(root, f"sys/class/power_supply/{supply.name}/current_now")
        elif kind in {"mains", "usb", "usb-c"} and ac_online == "unavailable":
            ac_online = _bounded_text(root, f"sys/class/power_supply/{supply.name}/online")
    temperatures: list[str] = []
    try:
        zones = sorted((root / "sys/class/thermal").glob("thermal_zone[0-9]*/temp"))[:MAX_DEVICES]
    except OSError:
        zones = []
    for path in zones:
        value = _bounded_text(root, str(path.relative_to(root)))
        if value != "unavailable":
            temperatures.append(f"{path.parent.name}: {value} m°C")
    active_profile = "unavailable"
    if root == Path("/") and shutil.which("busctl"):
        try:
            raw = _fixed_command(
                [
                    "busctl",
                    "get-property",
                    "org.freedesktop.UPower.PowerProfiles",
                    "/org/freedesktop/UPower/PowerProfiles",
                    "org.freedesktop.UPower.PowerProfiles",
                    "ActiveProfile",
                ]
            )
            active_profile = raw.split(maxsplit=1)[1].strip().strip('"')
        except (IndexError, OSError, RuntimeError, subprocess.SubprocessError):
            pass
    from datetime import datetime, timezone

    return PowerTelemetry(
        capacity,
        status,
        rate,
        ac_online,
        tuple(temperatures),
        active_profile,
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


def _tuned_settings() -> tuple[list[str], list[PowerSetting]]:
    providers: list[str] = []
    settings: list[PowerSetting] = []
    if not shutil.which("tuned-adm"):
        return providers, settings
    providers.append("TuneD / tuned-ppd")
    try:
        active = _fixed_command(["tuned-adm", "active"])
        active = active.partition(":")[2].strip() or active
    except (OSError, subprocess.SubprocessError, RuntimeError):
        active = "unavailable"
    try:
        listing = _fixed_command(["tuned-adm", "list"])
        profiles = sorted(
            {
                line.lstrip("-* ").split(" - ", 1)[0].strip()
                for line in listing.splitlines()
                if line.strip().startswith(("-", "*"))
            }
        )
        choices = ", ".join(profiles[:24]) or "unavailable"
    except (OSError, subprocess.SubprocessError, RuntimeError):
        choices = "unavailable"
    settings.append(
        PowerSetting(
            "Profiles",
            "Active TuneD profile",
            active,
            choices,
            "tuned-adm (fixed read-only query)",
        )
    )
    return providers, settings


def _ppd_settings() -> tuple[list[str], list[PowerSetting]]:
    if not shutil.which("busctl"):
        return [], []
    try:
        raw = _fixed_command(
            [
                "busctl",
                "get-property",
                "org.freedesktop.UPower.PowerProfiles",
                "/org/freedesktop/UPower/PowerProfiles",
                "org.freedesktop.UPower.PowerProfiles",
                "ActiveProfile",
            ]
        )
        active = raw.split(maxsplit=1)[1].strip().strip('"')
    except (OSError, subprocess.SubprocessError, RuntimeError, IndexError):
        return [], []
    if active not in {"power-saver", "balanced", "performance"}:
        return [], []
    return ["Power Profiles D-Bus (tuned-ppd)"], [
        PowerSetting(
            "Profiles",
            "Desktop power profile",
            active,
            "power-saver, balanced, performance",
            "UPower PowerProfiles D-Bus",
            True,
            "power.profile",
        )
    ]


def _gpu_settings(root: Path) -> tuple[list[str], list[PowerSetting]]:
    providers: list[str] = []
    settings: list[PowerSetting] = []
    drm = root / "sys/class/drm"
    try:
        cards: Iterable[Path] = sorted(drm.glob("card[0-9]"))[:MAX_DEVICES]
    except OSError:
        cards = []
    for card in cards:
        name = card.name
        vendor = _bounded_text(root, f"sys/class/drm/{name}/device/vendor")
        section = (
            "Intel GPU"
            if vendor.casefold() == "0x8086"
            else "NVIDIA GPU"
            if vendor.casefold() == "0x10de"
            else "Other GPU"
        )
        driver = "unavailable"
        try:
            driver = (card / "device/driver").resolve(strict=True).name
        except OSError:
            pass
        providers.append(f"{section}: {driver}")
        settings.extend(
            (
                PowerSetting(
                    section,
                    f"{name} runtime policy",
                    _bounded_text(root, f"sys/class/drm/{name}/device/power/control"),
                    "auto, on",
                    f"/sys/class/drm/{name}/device/power/control",
                    section in {"Intel GPU", "NVIDIA GPU"},
                    "intel_gpu.runtime_pm"
                    if section == "Intel GPU"
                    else "nvidia_gpu.runtime_pm"
                    if section == "NVIDIA GPU"
                    else None,
                ),
                _setting(
                    root,
                    section,
                    f"{name} runtime status",
                    f"sys/class/drm/{name}/device/power/runtime_status",
                ),
                _setting(
                    root,
                    section,
                    f"{name} autosuspend delay",
                    f"sys/class/drm/{name}/device/power/autosuspend_delay_ms",
                    "milliseconds",
                ),
            )
        )
    return providers, settings


def scan_power_inventory(
    *, root: Path = Path("/"), include_commands: bool = True
) -> PowerInventory:
    """Collect fixed sysfs/proc settings without mutation or device-waking probes."""
    root = root.resolve()
    providers: list[str] = []
    settings: list[PowerSetting] = []

    cpu_driver = _bounded_text(root, "sys/devices/system/cpu/cpu0/cpufreq/scaling_driver")
    if cpu_driver != "unavailable":
        providers.append(f"CPU frequency: {cpu_driver}")
    cpu_choices = _bounded_text(
        root, "sys/devices/system/cpu/cpu0/cpufreq/scaling_available_governors"
    )
    epp_choices = _bounded_text(
        root,
        "sys/devices/system/cpu/cpu0/cpufreq/energy_performance_available_preferences",
    )
    settings.extend(
        (
            _setting(
                root,
                "CPU",
                "Scaling driver",
                "sys/devices/system/cpu/cpu0/cpufreq/scaling_driver",
            ),
            _setting(
                root,
                "CPU",
                "Governor",
                "sys/devices/system/cpu/cpu0/cpufreq/scaling_governor",
                cpu_choices,
            ),
            PowerSetting(
                "CPU",
                "Energy performance preference",
                _bounded_text(
                    root,
                    "sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference",
                ),
                epp_choices,
                "/sys/devices/system/cpu/cpu0/cpufreq/energy_performance_preference",
                True,
                "cpu.epp",
            ),
            _setting(
                root,
                "CPU",
                "Minimum frequency",
                "sys/devices/system/cpu/cpu0/cpufreq/scaling_min_freq",
                "kHz",
            ),
            _setting(
                root,
                "CPU",
                "Maximum frequency",
                "sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq",
                "kHz",
            ),
            _setting(
                root,
                "CPU",
                "Hardware maximum frequency",
                "sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq",
                "kHz",
            ),
            _setting(
                root,
                "CPU",
                "Intel P-state mode",
                "sys/devices/system/cpu/intel_pstate/status",
                "active, passive, off",
            ),
            PowerSetting(
                "CPU",
                "CPU turbo",
                {"0": "enabled", "1": "disabled"}.get(
                    _bounded_text(root, "sys/devices/system/cpu/intel_pstate/no_turbo"),
                    "unavailable",
                ),
                "enabled, disabled",
                "/sys/devices/system/cpu/intel_pstate/no_turbo",
                True,
                "cpu.turbo",
            ),
            _setting(
                root,
                "CPU",
                "Intel minimum performance",
                "sys/devices/system/cpu/intel_pstate/min_perf_pct",
                "percent",
            ),
            _setting(
                root,
                "CPU",
                "Intel maximum performance",
                "sys/devices/system/cpu/intel_pstate/max_perf_pct",
                "percent",
            ),
        )
    )

    platform_choices = _bounded_text(root, "sys/firmware/acpi/platform_profile_choices")
    settings.append(
        _setting(
            root,
            "Platform",
            "ACPI platform profile",
            "sys/firmware/acpi/platform_profile",
            platform_choices,
        )
    )

    gpu_providers, gpu_values = _gpu_settings(root)
    providers.extend(gpu_providers)
    settings.extend(gpu_values)
    settings.extend(
        (
            _setting(
                root,
                "Intel GPU",
                "i915 display C-states",
                "sys/module/i915/parameters/enable_dc",
                "driver-specific integer mode",
            ),
            _setting(
                root,
                "Intel GPU",
                "i915 framebuffer compression",
                "sys/module/i915/parameters/enable_fbc",
                "0 disabled, 1 enabled",
            ),
            _setting(
                root,
                "Intel GPU",
                "i915 panel self refresh",
                "sys/module/i915/parameters/enable_psr",
                "driver-specific integer mode",
            ),
            _setting(
                root,
                "NVIDIA GPU",
                "Dynamic power management",
                "sys/module/nvidia/parameters/NVreg_DynamicPowerManagement",
                "0x00 disabled, 0x01 coarse, 0x02 fine",
            ),
            _setting(
                root,
                "NVIDIA GPU",
                "Preserve video memory",
                "sys/module/nvidia/parameters/NVreg_PreserveVideoMemoryAllocations",
                "0 disabled, 1 enabled",
            ),
        )
    )

    supply_root = root / "sys/class/power_supply"
    try:
        supplies = sorted(supply_root.iterdir())[:MAX_DEVICES]
    except OSError:
        supplies = []
    for supply in supplies:
        kind = _bounded_text(root, f"sys/class/power_supply/{supply.name}/type")
        providers.append(f"Power supply: {supply.name} ({kind})")
        for label, field, choices in (
            ("Status", "status", "Charging, Discharging, Full, Not charging"),
            ("Capacity", "capacity", "percent"),
            ("Online", "online", "0, 1"),
        ):
            value = _setting(
                root,
                "Battery / AC",
                f"{supply.name} {label}",
                f"sys/class/power_supply/{supply.name}/{field}",
                choices,
            )
            if value.current != "unavailable":
                settings.append(value)

    if include_commands and root == Path("/"):
        tuned_providers, tuned_values = _tuned_settings()
        providers.extend(tuned_providers)
        settings.extend(tuned_values)
        ppd_providers, ppd_values = _ppd_settings()
        providers.extend(ppd_providers)
        settings.extend(ppd_values)
    if include_commands and root == Path("/") and shutil.which("powertop"):
        providers.append("Powertop (installed; automatic probing disabled)")
    if _bounded_text(root, "proc/driver/nvidia/version") != "unavailable":
        providers.append("NVIDIA kernel driver")

    return PowerInventory(
        tuple(dict.fromkeys(providers)),
        tuple(settings),
        (
            "read-only inventory; no setting is changed",
            "nvidia-smi and powertop sampling are not run automatically because they may wake hardware or require privilege",
            "unavailable means the driver does not expose that interface or access was denied",
        ),
        hardware=_hardware_summary(root),
        software=_software_summary() if root == Path("/") else (),
        conflicts=(
            (
                "multiple power-policy providers detected; provider ownership must be resolved before writes",
            )
            if sum(bool(shutil.which(name)) for name in ("tuned-adm", "tlp-stat", "auto-cpufreq"))
            > 1
            else ()
        ),
        telemetry=scan_power_telemetry(root=root) if root == Path("/") else PowerTelemetry(),
    )
