# Conversation checkpoints — 2026-08-30

Implemented per-conversation rolling checkpoints for the five newest user
messages. A checkpoint is captured when a user message is submitted, persisted
atomically in a private `checkpoints` directory, and rendered as a `↶` control
in a separate narrow column beside that user message. The control opens compact
Chat/context and Full restore choices, each followed by a one-use confirmation.

The conversation surface uses mountable full-width message blocks and keeps
checkpoint controls outside the message boxes. User blocks remain grey and
response blocks black. Each message box has explicit top and bottom separator
rows in its own role color. Internal message roles are unchanged.

The main Conversation stream deliberately does not retain or render transient
Codex/Jarvis activity cards. Operational lifecycle detail remains in the live
App Server path and bounded audit/timeline metadata; only user-facing results,
approvals, and failures enter the conversation projection.

Context restore saves the active conversation as a separate branch before
restoring the conversation before the selected user message. The selected
message is removed from the visible conversation and its exact text is placed
back in the composer for editing. A transient notice explains the result. Full
restore blocks while active work is unsettled and fails closed when later
registered mutations do not have an exact recovery path; no action is replayed.

Validation: checkpoint, conversation-manager, and focused Textual tests passed;
Ruff, compilation, documentation, inventory, and release-manifest checks were
run after implementation. No host action was executed.
