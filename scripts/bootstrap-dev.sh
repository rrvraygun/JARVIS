#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
bundle_root=$(cd -- "$script_dir/.." && pwd -P)
python_bin="$bundle_root/.venv/bin/python"

if [[ ! -x "$python_bin" ]]; then
  printf 'Missing project interpreter: %s\n' "$python_bin" >&2
  exit 1
fi

exec "$python_bin" -m pip install --disable-pip-version-check --no-input \
  -r "$bundle_root/requirements-dev.lock"
