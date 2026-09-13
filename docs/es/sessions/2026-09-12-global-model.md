# Selector global de modelo

Added one `Global model` selector to the Agents view. It deliberately sits
outside the specialist editor: all specialists share the selected model.
Choices are the supported Codex models gpt-6-astra, gpt-5.6-sol, gpt-5.6-terra,
gpt-5.6-luna and gpt-5.5. Values are allowlisted, persisted to the candidate's
runtime/jarvis-model.json, and applied to `thread/start` for new turns. Existing
turns keep their model.

The session controller validates the value and falls back to gpt-5.6-terra if
the settings file is absent or invalid. No credentials or account data are
written. Ruff, release-manifest verification, documentation verification and
the 37 App Server/session tests passed after integration.
