#!/usr/bin/env bash
# Compatibility wrapper. The source-verifying launcher is canonical.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
exec "$script_dir/scripts/launch-tui.sh" "$@"
