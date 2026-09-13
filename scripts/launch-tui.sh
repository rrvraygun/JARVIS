#!/usr/bin/env bash
# Launch the TUI from this checkout, never an installed/stale jarvis_tui copy.
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
bundle_root=$(cd -- "$script_dir/.." && pwd -P)
python_bin="$bundle_root/.venv/bin/python"
expected_module="$bundle_root/tui/src/jarvis_tui/package_inventory.py"

if [[ ! -x "$python_bin" ]]; then
  printf 'Missing reviewed TUI interpreter: %s\n' "$python_bin" >&2
  exit 1
fi

export PYTHONPATH="$bundle_root/tui/src${PYTHONPATH:+:$PYTHONPATH}"
export CODEX_HOME="$bundle_root/runtime/codex-home"
loaded_module=$("$python_bin" -c 'import jarvis_tui.package_inventory as module; print(module.__file__)')
if [[ "$loaded_module" != "$expected_module" ]]; then
  printf 'Refusing to launch stale JARVIS source: %s\n' "$loaded_module" >&2
  exit 1
fi

if ! "$python_bin" -c '
from jarvis_tui.package_inventory import _preview_removed_packages
sample = "Removing:\n transient-status\nPackage Arch Version Repository Size\n rust x86_64 1 repo 1 MiB\nTransaction Summary:\n Removing: 1 package\n"
assert _preview_removed_packages(sample) == ("rust",)
'; then
  printf 'Refusing to launch: the DNF5 package-preview parser self-check failed.\n' >&2
  exit 1
fi

printf 'Launching JARVIS TUI from: %s\n' "$loaded_module"
printf 'DNF5 package-preview parser self-check: passed\n'
exec "$python_bin" -m jarvis_tui \
  --bundle-root "$bundle_root" \
  --connect-app-server \
  --enable-live-turns \
  "$@"
