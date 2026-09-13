# Automation design

Use `codex exec` with read-only sandbox, explicit approval mode, ephemeral
sessions, JSONL when full tracing is required, and an output schema for stable
results. Configure the Jarvis MCP server as `required` so automation fails rather
than running without policy and audit tools.

Scheduled automation is observation-only by default. It may produce alerts and
approval-ready plans but cannot interpret an old conversational approval as a
new change authorization. Each mutating run needs a matching action digest,
targets, actor, expiry, procedure version, maintenance window, and recovery.

Store prompts and schemas in version control. Pin the Codex/plugin release in
production automation, validate updates in a disposable environment, and retain
JSONL traces according to the data lifecycle. Never expose API keys to jobs that
execute untrusted repository code.
