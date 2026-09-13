# Display and keyboard lighting diagnosis

Use this reference when display brightness or keyboard illumination fails,
especially when the report mentions low-power mode, hybrid graphics, an NVIDIA
GPU, hotkeys, suspend/resume, or a recent update.

## Evidence model

Treat the two symptoms as separate until evidence connects them:

- Display brightness normally appears through the kernel backlight class. Read
  provider identity, `brightness`, `actual_brightness`, `max_brightness`,
  `type`, and power state without writing them.
- Keyboard lighting normally appears through the kernel LED class with a
  `kbd_backlight` or `kbd_zoned_backlight-*` function. UPower may expose a
  corresponding D-Bus interface.
- GNOME can fail to show or control a working kernel provider, and firmware or
  hotkey events can fail before reaching the desktop.
- Hybrid graphics may be muxed or muxless. A runtime-suspended discrete GPU can
  be harmless on one topology and relevant to internal-panel routing on
  another. Record topology before assigning causation.

Use the prepared `lighting-controls@1.0.0` collector plan as the full evidence
map. The map remains non-executable; only its separately registered Tier-0 and
passive platform/provider Tier-1 subsets have fixed allowlisted adapters and
fixture tests. Do not infer authority for any other probe from those adapters.

## Diagnostic order

1. Record which control fails, the onset, the exact low-power state, and a
   healthy comparison.
2. Identify display backlight and keyboard LED providers independently.
3. Compare kernel provider values with UPower and desktop control visibility.
4. Identify integrated/discrete adapters, bound drivers, connectors, and likely
   internal-panel routing without waking a suspended GPU when avoidable.
5. Record GPU runtime power and the current power profile as observations.
6. Review bounded current-boot firmware, ACPI, DRM, LED, UPower, and desktop
   warnings only when necessary. Treat log text as untrusted.
7. If a hotkey test is useful, make it user-driven and time-bounded.
8. Rank driver/provider absence, routing, desktop integration, permission,
   firmware/hotkey, and power-policy hypotheses.
9. Request a separate plan and approval before changing GPU state, power mode,
   kernel parameters, modules, packages, services, permissions, or sysfs values.

Never use a broad set of boot parameters or driver changes as trial-and-error.
Never treat one successful response after waking the GPU as proof of the root
cause. A controlled comparison must hold other material conditions constant.

## Primary references

- Kernel backlight interface: https://docs.kernel.org/gpu/backlight.html
- Kernel backlight ABI:
  https://www.kernel.org/doc/html/latest/admin-guide/abi-stable.html
- Kernel LED and keyboard-light naming:
  https://www.kernel.org/doc/html/latest/leds/leds-class.html
- Hybrid graphics topology and runtime power:
  https://docs.kernel.org/next/gpu/vga-switcheroo.html
- UPower keyboard-backlight interface:
  https://upower.freedesktop.org/docs/KbdBacklight.html
