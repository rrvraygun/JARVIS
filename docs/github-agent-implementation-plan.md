# GitHub Agent implementation plan

## Current phase

Phase 1 is implemented and fixture-validated. GitHub Agent is a selectable
specialist in Agents and Conversation. It has a bounded local Git inspector, a
publication preflight, and an operation-plan tool. These tools do not contact
GitHub, read file contents, store credentials, or perform writes.

## Identity and authentication

The agent uses the active configured GitHub profile. Git transport uses the
user's SSH configuration. Account selection is never inferred from a request and
credentials are never copied into the project, displayed, or persisted.

## Tool catalog

| Tool | Scope | Authority |
| --- | --- | --- |
| github_inspect | Branch, status, diffs, history, ignored paths, conflicts, remotes, Git version | Read-only |
| github_preflight | Changed paths, ignored paths, likely sensitive filenames, large files, conflicts | Read-only |
| github_operation_plan | Init, clone, branch, commit, pull/push, repository, issue, PR, release, Actions, deletion and settings operations | Plan only; fresh exact approval required |

GitHub CLI and an official GitHub MCP connector are detected and reported as
available capabilities. They are not invoked by the phase-1 tools.

## Authority model

Read-only inspection can proceed automatically for the user-selected repository.
Commits, pushes, repository creation, pull requests, merges, releases, Actions,
collaborator changes, protection changes, force-pushes, branch deletion and
repository deletion require a fresh exact user approval. Conflicts stop the
workflow; the agent does not resolve them automatically.

## Delivery phases

1. Inspection: complete. Add local status, preflight and exact plan tools.
2. Local Git actions: implement init, clone, branch, commit, pull and worktree
   execution behind the existing one-use TUI review.
3. GitHub repository actions: add GitHub CLI/API or official MCP adapters for
   repository creation, forks, templates, issues, PRs, labels and milestones.
4. CI and releases: add checks, Actions logs/reruns, artifacts, tags and
   releases with explicit network and publication approvals.
5. Hardening and acceptance: add content-aware secret scanning, large-file
   and LFS handling, branch-protection checks, audit projections, rollback
   records, and full acceptance tests.

## Acceptance criteria

- The specialist is selectable in both requested UI locations.
- Every operation identifies the active profile, repository, branch, target and
  required authority before execution.
- No write runs without a fresh exact approval.
- No credentials or private key material enter logs, prompts, or project files.
- Sensitive paths, conflicts and oversized files block publication until reviewed.
- Network-dependent GitHub work is clearly marked and remains blocked when the
  approved profile has no network capability.
- Failed or uncertain actions stop without automatic retry and retain a bounded
  recovery record.
