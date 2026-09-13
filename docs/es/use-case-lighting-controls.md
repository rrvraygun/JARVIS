# Prepared use case: display brightness and keyboard lighting

## User report

> Display brightness and keyboard lighting appear to stop working when the
> NVIDIA GPU is off under the current low-consumption settings.

This statement is a symptom report and causal hypothesis, not a verified fact.
The diagnostic design preserves both while testing the relationship.

## Supported entry points

The same case can begin through either interface:

- natural language, including phrases such as “brightness stopped working,”
  “keyboard light keys do nothing,” or “this happens when NVIDIA sleeps”;
- the `health.lighting.diagnose@1.0.0` catalog action and its typed form.

Both create the same task type and use the same procedure. The catalog form
captures affected controls, the strength of the reported NVIDIA correlation,
onset, trigger, external-display behavior, and notes.

## Prepared user journey

1. Select **Diagnose display and keyboard lighting** or describe the problem.
2. Review the captured symptom and confirm that no command has run.
3. Review the exact bounded Tier-0 adapter preview; it reads only allowlisted
   sysfs/proc metadata and does not intentionally wake devices.
4. Run the registered Tier-0 observation once, followed only when justified by
   the passive Tier-1 platform/provider observer. Protected logs, session-bus
   activation, or an interactive hotkey monitor receive separate gates.
5. Review evidence by layer and the ranked hypotheses.
6. If evidence is insufficient, approve only the next discriminating check.
7. Select **Prepare a lighting repair** after a diagnosis is reviewed.
8. Review one exact intervention, its pre-state, validation, recovery, and
   independent review.
9. In a future stage-4 release, approve one exact state-changing command.
10. Validate display brightness, keyboard lighting, hotkeys, session health,
    suspend/resume, GPU availability, and the low-power objective.

Step 3 and the Tier-0 and passive platform/provider Tier-1 parts of step 4 are
executable on the enrolled workstation under active H1 bounded read-only
authority. Session integration, protected evidence, interactive observation,
state comparison, and every repair remain separate, unimplemented, protected,
or approval-gated as described below.

## Diagnostic separation

| Layer | Evidence to compare | Conclusion it may support |
|---|---|---|
| Display backlight | Provider set, requested/actual/max brightness, type, power | Kernel display-control presence and behavior |
| Keyboard lighting | LED providers, brightness/max, UPower exposure | Kernel and userspace keyboard-control presence |
| Hotkeys | User keypress, input event, firmware change, desktop indication | Where the control event stops |
| Desktop integration | GNOME, UPower, power profile, service exposure | Whether UI/session control differs from kernel state |
| Graphics topology | Integrated/discrete adapters, drivers, connectors, routing | Whether the internal panel may depend on a powered GPU |
| Runtime power | Timestamped GPU runtime state | Correlation with provider/routing changes |
| Version/change history | Kernel, driver, packages, boot parameters, current-boot warnings | Regression or configuration hypotheses |

Display and keyboard lighting share a report but not necessarily a driver or
control path. A single fault may affect both through firmware or power policy;
two simultaneous faults are also possible.

## Hypotheses the agent must distinguish

- A backlight or keyboard LED provider disappears when a device/runtime state
  changes.
- Providers remain present but requested values do not reach hardware.
- Kernel providers work while UPower or GNOME integration does not.
- Firmware handles hotkeys incorrectly or does not emit an event.
- A power profile or desktop policy dims/disables a control as designed.
- Internal-panel routing actually depends on the discrete GPU on this topology.
- The NVIDIA state is merely correlated with a different low-power transition.
- A kernel, graphics driver, desktop, firmware, or configuration update caused
  a regression.

No hypothesis is selected before live evidence exists.

## Prepared artifacts

- Catalog: `plugins/jarvis-system-admin/registry/actions.json`
- Diagnostic procedure:
  `plugins/jarvis-system-admin/registry/procedures/lighting-diagnose.json`
- Repair procedure:
  `plugins/jarvis-system-admin/registry/procedures/lighting-repair.json`
- Non-executable evidence map:
  `plugins/jarvis-system-admin/registry/collector-plans/lighting-controls.json`
- Executable Tier-0 collector policy:
  `plugins/jarvis-system-admin/registry/collectors/lighting-tier0.json`
- Fixed Tier-0 filesystem adapter:
  `plugins/jarvis-system-admin/scripts/collect_lighting_tier0.py`
- Executable passive Tier-1 collector policy:
  `plugins/jarvis-system-admin/registry/collectors/lighting-tier1-platform.json`
- Fixed passive Tier-1 platform/provider adapter:
  `plugins/jarvis-system-admin/scripts/collect_lighting_tier1_platform.py`
- Executable passive Tier-2 WMI-binding collector policy:
  `plugins/jarvis-system-admin/registry/collectors/lighting-tier2-wmi-binding.json`
- Fixed passive Tier-2 WMI-binding adapter:
  `plugins/jarvis-system-admin/scripts/collect_lighting_tier2_wmi_binding.py`
- Approved Tier-3 connector/provider association policy:
  `plugins/jarvis-system-admin/registry/collectors/lighting-tier3-connector-association.json`
- Fixed Tier-3 eDP association adapter:
  `plugins/jarvis-system-admin/scripts/collect_lighting_tier3_connector_association.py`
- Diagnostic skill reference:
  `codex/skills/system-health/references/lighting-controls.md`
- Repair skill reference:
  `codex/skills/system-repair/references/lighting-repair.md`

## Current safety state

- The diagnosis action is prepared and non-mutating. Its first observation
  layer is implemented by a fixed, unprivileged Tier-0 adapter with one-attempt
  behavior and bounded output.
- The broader collector map retains `execution_enabled: false`: it is a design
  map for later protected/session layers and contains no executable command
  arrays. This does not disable the separately registered Tier-0 adapter.
- Tier-0 directly reads only allowlisted provider values, adapter metadata,
  connector names (never connector status), and filtered graphics/backlight
  kernel context. It launches no subprocess, makes no D-Bus/network call, and
  performs no device or sysfs write.
- Passive Tier-1 reads only non-secret DMI identity fields, allowlisted
  platform/module names, backlight bus/driver topology, candidate LED names,
  and candidate input-device identity. It explicitly excludes serials, UUIDs,
  input events, physical/unique input fields, D-Bus, logs, subprocesses,
  connector status, and all writes.
- Passive Tier-2 is limited to the fixed NVIDIA brightness WMI GUID instance
  names, its driver-binding names, the read-only module `force` value, and
  registered backlight provider names/types. It never evaluates a WMI method,
  binds a driver, or writes a module parameter.
- The approved Tier-3 association adapter reads only DRM card identity,
  internal eDP connector status, and fixed backlight-provider symlink targets.
  Connector-status reads may wake display hardware; this effect is disclosed
  and separately approved. It performs no writes, WMI/ACPI calls, D-Bus calls,
  subprocesses, log reads, or input-event reads.
- The repair-planning action can represent a future plan but cannot change the
  host.
- The repair-execution action is visible and unavailable.
- No GPU toggle, sysfs write, module operation, service change, package change,
  boot-parameter change, or privileged command is present.

## Current enrolled-host diagnosis (2026-08-06)

The user-confirmed symptom is recorded separately from machine evidence: GNOME
shows the shortcut response, but neither physical display brightness nor
keyboard illumination changes. The passive Tier-2 observation then found the
NVIDIA brightness WMI GUID instance present, the matching driver directory
present, no bound GUID instance, `force=false`, and only the raw
`intel_backlight` and `nvidia_0` providers. Combined with the earlier filtered
`acpi_backlight=native` boot parameter, this makes a provider-selection mismatch
the high-confidence display hypothesis. Upstream Linux gives an explicit
`acpi_backlight` command-line setting precedence and the NVIDIA WMI EC driver
normally waits for the `nvidia_wmi_ec` selection.

The keyboard conclusion remains separate and lower confidence: no standard
`kbd_backlight`/`kbd_zoned_backlight` LED provider or candidate keyboard LED was
observed. Current upstream `acer-wmi` recognizes the AN515-58 and handles an
automatic keyboard-background-light key event, but this does not establish a
standard keyboard LED backend on the installed kernel. The NVIDIA-off
correlation is still unproven because no controlled power-state comparison was
performed.

The complete evidence-backed record is
`runtime/reports/2026-08-06-recovery-bootstrap/diagnosis-lighting-controls-tier2-correlated.json`.
The next safe gates are a passive brightness-transition observation, a
separately gated read-only UPower/session exposure check for the keyboard, and,
only if needed, a one-time boot comparison with `acpi_backlight=native` removed.
No repair is approved by this diagnosis.

## Tier-3 connector association result (2026-08-06)

The separately approved bounded connector read found `card1-eDP-1` connected
on Intel `i915` (`0000:00:02.0`). The relevant firmware-provider candidates are
`acpi_video1` and `acpi_video2`; `acpi_video0` belongs to the disconnected
NVIDIA connector `card0-eDP-2`. This makes the integrated provider path the
high-confidence target for a future display test, while still not proving that
either provider applies physical luminance.

The result is recorded in
`runtime/state/snapshots/2026-08-06-lighting-tier3-connector-association-live.json`
and diagnosed in
`runtime/reports/2026-08-06-recovery-bootstrap/diagnosis-lighting-controls-tier3-connector-association-revision-1.json`.

Two distinct gates are now prepared:

1. `prepared-display-provider-write-test-v1.json` defines one reversible,
   bounded write to exactly one freshly selected integrated provider. It
   requires current-state capture, an exact command approval, immediate
   read-back, user confirmation of physical effect, and rollback.
2. `prepared-keyboard-upower-observation-gate-v1.json` defines a separate
   read-only UPower/session query. It requires separate approval because D-Bus
   service activation may occur. It forbids all mutating methods and firmware
   calls.

Neither gate has executed. The display write remains unavailable until the
user approves the exact target and command; the keyboard observation remains
separately gated.

## Bounded provider-write result (2026-08-06)

The user-approved test changed `acpi_video1` from 96 to 86 and then restored
96. The user confirms that the panel visibly changed, but only minimally. This
proves that the integrated provider reaches physical hardware; it does not
prove that the provider's 0–100 range is an effective luminance range. The
current leading hypothesis is firmware/provider transfer-curve or scaling
behavior, with `acpi_video2` and the native Intel path still untested under
separate approval.

The result is recorded in
`runtime/reports/2026-08-06-recovery-bootstrap/diagnosis-lighting-controls-provider-write-revision-2.json`.
No further writes are authorized by this observation.

## User-confirmed repair outcome (2026-08-06)

This is a user confirmation, not a fresh machine observation from the Jarvis
read-only adapters:

- Display brightness now increases and decreases correctly after the user's
  boot/configuration repair.
- Keyboard illumination and its keyboard shortcut now work.
- The user also confirmed that the interactive Acer RGB menu can select colors
  and animation effects repeatedly.

The keyboard result uses an unofficial Acer RGB kernel-driver setup maintained
outside this bundle. The reported host integration includes a signed `facer`
module, `/opt/acer-predator-rgb`, the setup helper
`/usr/local/sbin/acer-rgb-setup`, and the enabled
`acer-rgb-setup.service`. These paths and service state are deployment facts
that must be re-observed on the enrolled host before Jarvis presents them as
currently active. The user-visible success is nevertheless sufficient to
close the original manual symptom report while keeping the adapter diagnosis
and repair-execution gates unchanged.

## Acceptance criteria before first Tier-0 live use

- Every Tier-0 read is implemented in the fixed reviewed adapter with strict
  field and provider bounds, redaction, expected result, fail-closed parsing,
  and one-attempt behavior.
- Reads known or suspected to wake a suspended GPU are excluded; connector
  status, vendor GPU clients, PCI configuration queries, D-Bus, and logs are
  forbidden by the Tier-0 registry.
- The TUI distinguishes a plan from a running observation.
- The user can inspect and cancel every non-instant observation.
- Protected logs and interactive event monitoring cannot start automatically.
- A state comparison cannot silently change GPU or power mode.
- The fixture laboratory covers missing/multiple/malformed providers,
  permission denial, nonzero results, timeout, hostile terminal output,
  unexpected effects, desktop conflict, NVIDIA-correlation conflict, and
  external-display contexts across the pinned lighting state space.
- The repair executor remains absent until a diagnosed repair has a fixed typed
  adapter, adversarial fixture coverage, action-specific recovery evidence,
  exact command approval, and independent postcondition validation. A Fedora VM
  may optionally rehearse representative software-only behavior, but it is not
  required and cannot validate the physical lighting or GPU-power path.

The Tier-0, passive platform/provider Tier-1, and passive WMI-binding Tier-2
adapters satisfy the first-live-use criteria only for their narrow layers.
Desktop/session integration, protected logs, interactive hotkey monitoring,
and comparison across power transitions require their own adapters and gates.
The Tier-3 connector/provider association adapter is approved only for the
single current investigation and must not be generalized into a safe list.

The completed fixture boundary and the physical claims that remain impossible
to prove in a normal VM are recorded in
`phase-4-vm-lab-prerequisite.md` and
`../vm-lab/coverage/physical-gaps.json`.

## Primary technical references

- Linux backlight support: https://docs.kernel.org/gpu/backlight.html
- Linux LED and keyboard-light naming:
  https://www.kernel.org/doc/html/latest/leds/leds-class.html
- Linux hybrid graphics: https://docs.kernel.org/next/gpu/vga-switcheroo.html
- UPower keyboard backlight:
  https://upower.freedesktop.org/docs/KbdBacklight.html
- Linux ACPI backlight selection:
  https://github.com/torvalds/linux/blob/master/drivers/acpi/video_detect.c
- Linux NVIDIA WMI EC backlight driver:
  https://github.com/torvalds/linux/blob/master/drivers/platform/x86/nvidia-wmi-ec-backlight.c
- Linux Acer WMI driver:
  https://github.com/torvalds/linux/blob/master/drivers/platform/x86/acer-wmi.c
