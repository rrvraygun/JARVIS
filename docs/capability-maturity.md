# Capability maturity model

| Stage | Meaning | Permitted use |
|---|---|---|
| 0 Defined | Instructions and schema exist | Documentation only |
| 1 Validated | Static and unit tests pass | Fixture use |
| 2 Rehearsed | Representative fixtures and non-production rehearsal pass; VM/container optional where useful | Supervised lab or isolated scratch target |
| 3 Observed | Read-only production evidence works | Live observation |
| 4 Supervised | Recovery-tested mutation works | Exact human approval |
| 5 Automated | Repeated evidence and external audit | Narrow pre-approved policy |

No capability advances because the model appears confident. Promotion requires
recorded evaluations, owner approval, known rollback, and a versioned policy
change. Self-update, security, boot, firmware, identity, encryption, storage, and
remote-access capabilities may never skip independent review.

The direct-host deployment may advance one narrowly typed reversible procedure
to stage 4 after representative fixture tests, verified action-specific
recovery, exact approval, and independent live-host validation. A VM is not a
universal promotion gate because it cannot represent physical workstation
hardware paths. Procedure and transaction approvals and the pre-authorized safe
list remain disabled until a specific procedure reaches stage 5. Lesson
promotion is separate from execution maturity: automated evidence may create a
candidate, but only the user activates it.
