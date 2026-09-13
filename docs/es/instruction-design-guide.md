# Evidence-based Codex instruction design

## Core conclusion

Reliable Codex performance comes from a compact hierarchy of scoped guidance,
accessible repository knowledge, executable validation, and corrective feedback.
It does not come from persona language, repeated emphasis, or one giant prompt.

## Choose the smallest durable surface

| Need | Surface |
|---|---|
| One task's objective and constraints | User prompt |
| Repository map, invariants, checks | `AGENTS.md` |
| Subsystem rule | Nested `AGENTS.md` or override |
| Deep domain knowledge | Versioned documentation |
| Repeatable workflow | Skill |
| Specialized worker role | Custom-agent TOML |
| Hard invariant | Test, linter, hook, permissions, or CI |
| One-run runtime choice | CLI flag or config override |

## Rule form

Prefer: **trigger -> action -> constraints -> verification -> exception**.

Weak: `Be careful with upgrades.`

Strong: `Before a boot-critical upgrade, record installed and target versions,
verify package provenance and compatibility, confirm recovery media or rollback,
request approval with expected downtime, then validate boot and affected devices.`

State prohibitions with a safe path: `Do not X; use Y; exception Z requires
approval.` Separate hard invariants, defaults, and preferences. Specify outcomes
and boundaries; avoid micromanaging implementation when local patterns suffice.

## Task prompt template

1. Objective
2. Current behavior or evidence
3. Desired behavior
4. Relevant paths, components, examples, and documentation
5. Constraints
6. Scope and non-goals
7. Observable acceptance criteria
8. Exact verification
9. Execution and approval policy

## Context engineering

Keep the root `AGENTS.md` short and use it as a table of contents. Put detailed
knowledge in indexed, versioned documents and load task workflows progressively
through skills. Prefer repository anchors and analogous implementations over
generic style prose. Keep time-sensitive truth out of static instructions unless
it includes an owner and refresh mechanism.

## Feedback and enforcement

If a rule repeatedly fails, do not merely intensify its wording. Determine
whether the missing component is context, an example, a tool, a test, a clearer
scope, a permission boundary, or mechanical enforcement. Design validation
errors to identify the violation, safe remediation, and relevant documentation.

## Anti-patterns

- Persona-heavy prompts and claims of expertise
- Everything labelled critical
- Abstract goals without checks
- Hidden acceptance criteria
- Contradictory instructions
- Exhaustive rare-case rules in always-loaded context
- Asking for private chain-of-thought instead of evidence and decisions
- Replacing built-in model instructions for ordinary project guidance

## Evaluation

Compare instruction variants on representative repeated tasks with the same
model, state, permissions, and acceptance criteria. Track first-pass success,
instruction violations, test results, scope adherence, patch churn, review
findings, tool efficiency, and human correction time. Multiple trials are needed
because model output is stochastic.

## Source basis

- OpenAI Codex prompting: https://learn.chatgpt.com/docs/prompting
- AGENTS.md discovery: https://learn.chatgpt.com/docs/agent-configuration/agents-md
- Subagents: https://learn.chatgpt.com/docs/agent-configuration/subagents
- Skills: https://learn.chatgpt.com/docs/build-skills
- How OpenAI uses Codex: https://openai.com/business/guides-and-resources/how-openai-uses-codex/
- Harness engineering: https://openai.com/index/harness-engineering/
- Codex agent loop: https://openai.com/index/unrolling-the-codex-agent-loop/
