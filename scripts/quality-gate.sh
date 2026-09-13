#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
bundle_root=$(cd -- "$script_dir/.." && pwd -P)
python_bin=${JARVIS_PYTHON:-"$bundle_root/.venv/bin/python"}
profile=${1:---full}

if [[ ! -x "$python_bin" ]]; then
  printf 'Missing project interpreter: %s\n' "$python_bin" >&2
  exit 2
fi

case "$profile" in
  --fast|--headless|--full) ;;
  *) printf 'Usage: %s [--fast|--headless|--full]\n' "$0" >&2; exit 2 ;;
esac

"$python_bin" -m pip check
"$python_bin" -c 'import textual' || {
  printf 'Pinned Textual dependency is required for the quality gate.\n' >&2
  exit 2
}
"$python_bin" -m ruff format --check "$bundle_root/tui/src" "$bundle_root/plugins" "$bundle_root/vm-lab" "$bundle_root/deployment" "$bundle_root/scripts" "$bundle_root/automation" "$bundle_root/tests"
"$python_bin" -m ruff check "$bundle_root/tui/src" "$bundle_root/plugins" "$bundle_root/vm-lab" "$bundle_root/deployment" "$bundle_root/scripts" "$bundle_root/automation" "$bundle_root/tests"
"$python_bin" "$bundle_root/scripts/codebase_inventory.py" --verify
"$python_bin" "$bundle_root/scripts/verify_docs.py"
"$python_bin" -m mypy \
  "$bundle_root/tui/src/jarvis_tui/app_server.py" \
  "$bundle_root/tui/src/jarvis_tui/async_boundary.py" \
  "$bundle_root/tui/src/jarvis_tui/conversation_manager.py" \
  "$bundle_root/tui/src/jarvis_tui/event_reducer.py" \
  "$bundle_root/tui/src/jarvis_tui/event_store.py" \
  "$bundle_root/tui/src/jarvis_tui/local_filesystem.py" \
  "$bundle_root/tui/src/jarvis_tui/local_mutation.py"

if [[ "$profile" == "--fast" ]]; then
  "$python_bin" -m unittest \
    tui.tests.test_app_server tui.tests.test_event_reducer tui.tests.test_conversation_manager \
    tui.tests.test_async_boundary
  exit 0
fi

PYTHONPATH="$bundle_root/tui/src" "$python_bin" -m unittest discover \
  -s "$bundle_root/tui/tests" -p 'test_*.py'

if [[ "$profile" == "--headless" ]]; then
  exit 0
fi

find "$bundle_root/scripts" "$bundle_root/deployment" "$bundle_root/automation" -type f -name '*.sh' -print0 \
  | xargs -0 -r bash -n
"$python_bin" -m bandit -q -lll -r "$bundle_root/tui/src" "$bundle_root/plugins/jarvis-system-admin/scripts" "$bundle_root/vm-lab/scripts" "$bundle_root/deployment/host"
JARVIS_SKIP_TUI_TESTS=1 "$script_dir/validate-bundle.sh"
