# Platform adapter contract

Adapters translate a generic procedure into platform-specific read and change
operations. They do not grant authority. An adapter must declare detection,
supported versions, commands, required privilege, read/write effects, network
effects, simulations, snapshots, rollback, validation, parsing stability, and
known unsafe combinations.

Selection is evidence-based and performed before procedure planning. Never infer
a package manager from a single executable when multiple host/container layers
may exist. Do not install a missing adapter tool automatically. Commands that
change semantics across versions need version gates and fixtures.

Each mutating adapter must be tested in a disposable representative environment,
including interrupted execution, partial failure, rollback failure, stale state,
and unexpected target expansion.
