# Phase 5 — supervised mutation foundation

## Construction status

The admission contract is implemented in
`vm-lab/scripts/phase5_executor.py`. It binds an operation ID/revision,
parameters, target, policy digest, expiry, idempotency key, and one-use
approval. Admission derives the target digest from the resolved target and
requires an exact active-policy digest. Any future enabled path must atomically
consume the approval through the trusted authority ledger before an adapter can
have an effect; the in-memory ledger in tests is not production authorization.
The executor is intentionally disabled and has no subprocess, shell,
privilege, network, device, or filesystem-mutation implementation.

Phase 4 remains limited to the registered H1 Tier-0 observation scope. The TUI
may present and later submit typed requests, but it does not receive arbitrary
command authority. Fact persistence remains disabled until the encrypted
backend is explicitly bound and separately reviewed.

The disposable-only `jarvis.rehearsal.marker@1.0.0` candidate is implemented,
independently approved, and has passed one user-authorized disposable
present→absent rehearsal. It remains unregistered and disabled; the rehearsal
did not run through or enable the executor.

## Required promotion gates

Before any real adapter is enabled:

1. choose one exact reversible operation and target class;
2. implement the adapter without arbitrary command or parameter expansion;
3. rehearse success, interruption, rollback, stale state, and validation in a
   disposable environment;
4. bind the OS authorization boundary and recovery evidence;
5. obtain a fresh independent review and explicit user approval;
6. execute one supervised attempt and independently verify the postcondition.

No TUI feature, model response, or simulated approval can bypass these gates.
