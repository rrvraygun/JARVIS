#!/usr/bin/env bash
set -euo pipefail

# Launch a genuinely fresh Codex reviewer without inheriting this session's
# conversation. The child is always read-only and approval-free; this helper
# never installs, activates, or changes Jarvis state.

bundle_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
prompt_file=${1:-"$bundle_root/runtime/review-prompts/h1-runtime-gate-review.md"}
sandbox_mode=read-only
if [[ ${2:-} == "--writable-tests" ]]; then
  sandbox_mode=workspace-write
elif [[ -n ${2:-} ]]; then
  printf 'unknown review option: %s\n' "$2" >&2
  exit 2
fi

if [[ ! -f "$prompt_file" ]]; then
  printf 'review prompt not found: %s\n' "$prompt_file" >&2
  exit 2
fi

exec codex \
  -C "$bundle_root" \
  -s "$sandbox_mode" \
  -a never \
  exec review \
  --ephemeral \
  --ignore-user-config \
  --skip-git-repo-check \
  - < "$prompt_file"
