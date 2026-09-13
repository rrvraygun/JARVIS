# OpenAI feature basis

The platform uses current documented Codex surfaces selectively:

- Hooks and trust review: https://learn.chatgpt.com/docs/hooks
- MCP configuration and approval modes: https://learn.chatgpt.com/docs/extend/mcp
- Plugins: https://learn.chatgpt.com/docs/build-plugins
- Skills: https://learn.chatgpt.com/docs/build-skills
- Custom agents and orchestration: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Persistent repository guidance: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Non-interactive automation: https://learn.chatgpt.com/docs/non-interactive-mode
- Rich client integration: https://learn.chatgpt.com/docs/app-server
- Python and TypeScript integration: https://learn.chatgpt.com/docs/codex-sdk
- ChatGPT-plan access:
  https://help.openai.com/en/articles/11369540-using-codex-with-chatgpt
- Configuration and managed requirements: https://learn.chatgpt.com/docs/config-file/config-reference

Design implications:

- Hooks are useful but incomplete and cannot undo completed side effects.
- Plugin hooks require explicit trust review unless centrally managed.
- A required MCP server makes automation fail if governance tools do not start.
- MCP allowlists and per-tool approval modes reduce exposed authority.
- `codex exec` defaults to read-only and supports JSONL and output schemas.
- App Server exposes threads, turns, streamed items, user-input requests,
  approvals, interruption, and version-generated protocol schemas for rich
  clients.
- The Python SDK controls local App Server over JSON-RPC, but a safety-critical
  client must verify that the SDK exposes every required approval/event feature
  or use the generated protocol schema directly.
- The planned TUI uses App Server with ChatGPT-managed authentication. It does
  not require or silently fall back to a separately billed API key.
- Subagents improve independent evidence and review, but the primary retains
  authorization and integration responsibility.
- Skills provide progressive disclosure; detailed procedures should not bloat
  the always-loaded agent prompt.
