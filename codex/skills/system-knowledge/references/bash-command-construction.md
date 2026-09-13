# Bash command construction

## Construction order

1. Confirm the installed executable and version.
2. Resolve syntax from local help or the matching manual.
3. Represent the executable and each argument separately.
4. Identify every expansion, glob, substitution, pipeline, redirection, and
   control operator before rendering Bash text.
5. Resolve exact targets with a read-only command before any mutation.
6. Prefer native dry-run, check, download-only, query, or transaction-preview
   modes.
7. Define expected exit codes and output patterns.
8. Define bounded output, timeout, stop conditions, verification, and recovery.

## Rules

- Prefer direct process invocation to `bash -c`.
- Use `--` before positional paths when the command supports it.
- Quote variables and paths; do not let untrusted data become shell syntax.
- Avoid `eval`, remote-content pipes, implicit globs, ambiguous relative paths,
  and command substitutions in administrative actions.
- Treat pipelines as multiple commands with separate failure modes. In Bash,
  use `pipefail` only when its changed status semantics are intended.
- Do not infer success from an empty screen. Check exit status and postconditions.
- Never use `sudo` automatically. A privileged command requires fresh user
  approval for the exact executable, arguments, targets, relevant state digest,
  and expiry.
- Run one attempt only. On any unexpected output or effect, stop, record, and
  diagnose before proposing a different command.

