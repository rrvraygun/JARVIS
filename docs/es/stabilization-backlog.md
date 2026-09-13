# Stabilization backlog

Only medium/low work may remain here. Critical and high findings block the
stabilization completion record.

| Priority | Item | Exit criterion |
| --- | --- | --- |
| M1 | Extract package, power/lighting, conversation, and submission workflow controllers from `app.py`. | `app.py` owns composition/event wiring only; workflow regression tests remain green. |
| M1 | Split session transport ingestion from context/turn orchestration. | Bounded ingress and turn state tests target separate modules. |
| M1 | Harden MCP store-root ownership, temporary files, and event payload schema/size. | Symlink, unowned-root, malformed, and oversized payload tests fail closed. |
| M1 | Replace hard-coded hook/project paths with reviewed deployment configuration. | Launch and hook configuration work from a validated configured bundle root. |
| M2 | Replace remaining broad UI catches with typed safe diagnostics. | No raw exception/traceback reaches Conversation or Timeline. |
| M2 | Establish a documented coverage baseline and enforce 90% branch coverage for authority modules. | Quality gate parses Coverage JSON and fails below the agreed threshold. |
| M2 | Archive clearly superseded phase documents under `docs/history/`. | Every moved document has a banner and all local links validate. |
| L1 | Normalize residual style and typing warnings. | Each rule is either fixed or has a narrow justified suppression. |
