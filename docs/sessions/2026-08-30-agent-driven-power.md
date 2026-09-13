# Agent-driven Power workflow — 2026-08-30

## Outcome

Power-domain requests from the selected Power Expert now enter a real App
Server agent turn instead of being answered by the local keyword parser. The
agent owns clarification, profile decisions, control recommendations,
tradeoff analysis, and explanations. The agent receives the specialist
contract and uses registered typed MCP tools for bounded inventory, telemetry,
capabilities, profile draft validation, approval staging, and recovery
proposals.

Power Expert turns use a read-only sandbox and do not receive arbitrary command
approval. Agent-generated profile drafts are revalidated by the TUI before they
are displayed. An agent activation marker can open the existing exact approval
review, but the marker itself has no authority. The existing one-use Jarvis
approval, OS authorization, registered helper, independent verification, and
recovery boundaries remain the mutation authority.

MCP elicitation requests are surfaced by the TUI as a separate one-response
Allow once/Decline/Cancel dialog. Power turns use a granular approval policy
that allows those MCP decisions while disabling command-rule and sandbox
approval; the turn itself remains read-only. The response is limited to the
pending MCP request and does not grant host mutation authority.

The Power MCP surface is registered in the Jarvis control MCP server. Profile
planning and apply proposals reject unreviewed controls, stale pre-state, and
unsupported values. The apply tool is intentionally proposal-only until the
TUI approval boundary invokes the registered helper.

The canonical launcher now exports the checkout's `runtime/codex-home`, whose
explicit required `jarvis_control` MCP configuration enables the Power tools.
This prevents a user's global Codex profile from starting the TUI without the
repository's Power MCP server.

## Validation evidence

- Focused Power, specialist, App Server, and presentation tests: 19 passed.
- Full TUI quality-gate discovery: 250 tests reached; 249 passed and 1 sandbox
  environment error occurred when a fixture attempted to bind a Unix socket
  (`PermissionError: [Errno 1] Operation not permitted`).
- Ruff formatting and lint passed for changed Python files.
- MCP tools list exposed: `power_inventory`, `power_telemetry`,
  `power_capabilities`, `power_profile_plan`, `power_profile_apply`,
  `power_profile_rollback`, and `stage_registered_power_action`.
- Documentation contract and regenerated codebase inventory passed; the release
  manifest was regenerated and verified.

No host power configuration, package transaction, service, or privileged
operation was executed during this implementation.
