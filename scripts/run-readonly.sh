#!/bin/sh
set -eu
bundle=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
export CODEX_HOME="$bundle/runtime/codex-home"
exec codex --strict-config --sandbox read-only --ask-for-approval on-request "$@"
