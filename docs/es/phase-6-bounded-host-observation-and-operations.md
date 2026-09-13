# Bounded host observation and prepared operations

This revision adds useful host-facing construction without widening the live
H1 authority. `vm-lab/scripts/lighting_observation.py` is a passive adapter for
fixed backlight, keyboard-LED, and passive DRM card-identity paths. It uses descriptor-safe,
bounded reads and rejects symlinks, terminal controls, oversized fields, and
device-waking requests. It has no shell, network, credential, protected-log,
device-handle, or write path.

`diagnose()` converts the bounded observation into evidence-linked findings;
it never writes or recommends an unobserved repair. The prepared
`lighting_repair_plan.py` operation can bind a diagnosis and pre-state to an
exact target and recovery level, but its executor always fails closed until a
separate adapter, OS authorization, independent review, and deployment gate
exist.

The passive lighting observer is now registered at the owner-only Jarvisd
service boundary after explicit user promotion. It remains one-use,
ephemeral, and read-only; the TUI cannot call it directly. The TuneD/PPD
power-profile adapter and all lighting-repair mutation paths remain
unregistered and disabled. Operation manifests explicitly deny network,
credential, protected-read, and device-wake authority.
