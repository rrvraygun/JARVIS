#!/bin/sh
set -eu
: "${JARVIS_CODEX_HOME:?set JARVIS_CODEX_HOME to the reviewed profile}"
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
export CODEX_HOME="$JARVIS_CODEX_HOME"
codex exec --ephemeral --strict-config --sandbox read-only --ask-for-approval never \
  --output-schema "$root/automation/schemas/observation-output.schema.json" \
  --output-last-message "$root/control-store/reports/latest-observation.json" \
  - < "$root/automation/prompts/observe.md"
