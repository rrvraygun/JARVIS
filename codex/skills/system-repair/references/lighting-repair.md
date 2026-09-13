# Lighting repair gates

Use only after `health.lighting-diagnose@1.0.0` produces a reviewed diagnosis.

- Repair the demonstrated failure layer, not the user's initial causal theory.
- Change one variable at a time. Do not combine a kernel parameter, driver
  change, package update, service restart, permission change, and GPU-mode
  change into one approval.
- Capture exact configuration and package versions before any change.
- Prefer a reversible per-user or supported runtime repair over boot, driver,
  firmware, or package changes when both address the same verified cause.
- Treat module binding, initramfs, kernel command line, display-manager,
  firmware, and hybrid-GPU routing changes as high risk and independently
  review their recovery path.
- Validate display range, keyboard-light range, hotkeys, GNOME controls,
  suspend/resume, graphics availability, and the approved low-power objective.
- Stop and roll back on unexpected provider loss, black screen, session loss,
  boot risk, increased power use outside the accepted range, or a new kernel
  warning.

The current project has no lighting executor. Prepare exact commands only after
live evidence is collected and never activate a repair from this reference.
