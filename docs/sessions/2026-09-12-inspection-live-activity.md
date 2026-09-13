# Package inspection and live activity

Observed MCP failure: inspect_packages returned
tool_not_authorized_for_selected_specialist. The Installation Specialist omitted
that existing read-only alias. Added it without adding mutation capabilities.

Fresh-observation query binding now permits equal normalized package term sets,
including node/nodejs and go/golang aliases, instead of requiring byte-identical
natural language. Task/generation, expiry and refresh checks remain. Unrelated,
stale and partial multi-package queries cannot satisfy the observation check.
Unavailable or error payloads no longer produce a fresh-observation receipt.

A real scoped MCP call inspect_packages(query=node, refresh=true) succeeded with
available=true, stale=false and fresh_observation=true. Installed matches included
nodejs22 22.23.1 and nodejs24 24.18.0. No package installation ran. This exercised
the actual MCP/backend; it was not a full model-driven UI inspection turn.

Unverified inspection text becomes an activity event with no chat text. Removed
the repeated canned "No fresh registered observation" replacement. Unsupported
claims are still withheld; failure is visible in activity, not reported as success.

The live indicator above chat updates every 100ms, showing phase, elapsed time,
fragment/character counts and up to four recent tools with names, query, status
and elapsed time. Full replies retain every fragment; the former every-twentieth
fragment filter was removed. Tool cards show MCP tool names and bounded query
metadata, without copying raw results or private reasoning. Disconnected or
terminated tools lacking completion events stop with outcome unknown.

Validation: 107 focused session/presentation/reducer/governed/specialist tests,
38 graphical tests (66.025 seconds), and one terminal-activity regression passed.
The graphical test checks short-stream retention, tool/query display, failure
state and absence of canned chat. Independent inspection_review identified
partial-query coverage and unfinished-spinner issues; both were fixed and tested.

Existing conversation/audit records are preserved. Restart the candidate to load
the updated modules. Installed root helpers and Polkit policies were not changed.
