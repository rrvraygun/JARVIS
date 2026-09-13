# Phase 5 prepared power-profile executor bridge

The bridge in `vm-lab/scripts/power_profile_executor_bridge.py` is the next
construction step after the independently approved PPD mutation adapter. It is
disabled and unregistered by default. It has no D-Bus, shell, privilege,
network, filesystem-write, service, or TUI path.

Before a future adapter call, it binds:

- operation ID and revision `jarvis.powerprofile.select@1.0.0`;
- the exact requested/pre profile, confirmation/session gates, and warning
  flags through a canonical parameters digest;
- the fixed `tuned-ppd` D-Bus target and mutation through an exact target
  document and digest;
- the canonical checked-in power-profile authorization policy digest;
- an unexpired approval and idempotency key supplied by the durable authority
  ledger.

The bridge consumes the durable one-use approval before invoking the reviewed
adapter. The prepared `PowerProfileAuthorityLedger` backend provides the
owner-controlled, descriptor-bound SQLite implementation with integrity checks,
atomic consumption, duplicate/idempotency rejection, and replay resistance.
If consumption fails, the adapter is not called. If the adapter later fails,
the approval is already consumed and the adapter's no-rollback/new-approval
rule applies. The ledger is not opened by a service in the shipped state and
does not activate a provider; those remain separate reviewed deployment
decisions.

Focused bridge tests use in-memory fake ledger and adapter objects; ledger tests
use disposable temporary SQLite databases. The shipped state remains
`enabled=false`, with no registration in the broker, executor service, or TUI.
