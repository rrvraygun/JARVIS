# JARVIS Architect and Power Expert

The JARVIS Architect is the primary project-aware specialist. It reads the
versioned project contracts, registered capabilities, local knowledge records,
and current workstation evidence in order to produce bounded specialist agents.
It can prepare changes in an isolated worktree and validate them, but it cannot
merge, deploy, approve, or independently attest to its own changes.

The Power Expert is the first generated specialist. It combines the Power tab's
observed host inventory with RPM/local documentation and the official-source
policy in `plugins/jarvis-power-expert/policy/sources.json`. Its answers must
identify evidence freshness and provenance, distinguish recommendations from
facts, and stage only existing registered actions.

Network research may consult the configured official source classes. Persisting
new content remains visible and auditable: the source locator, retrieval time,
content hash, applicable version, and authority tier are recorded in the
existing immutable knowledge database. Community content is not authoritative.

Conversation shows the active specialist selector. Selecting a specialist adds
its versioned context to the conversation task; it does not grant host authority
or bypass the broker, action registry, confirmation, verification, or undo
requirements.

The Architect workflow can now create a digest-bound specialist proposal under
`runtime/agent-proposals/`. Proposals remain inactive and require independent
review plus explicit user approval before they can become a plugin. Generated
agents request `gpt-5.6-luna` with low reasoning by policy, but activation stays
blocked when that model is unavailable in the configured runtime.

Package changes currently support a cache-only DNF transaction preview through
`dnf --cacheonly --assumeno`. A preview is evidence for a later approval, never
an approval or an installation. The privileged package executor remains a
separate deployment step.
