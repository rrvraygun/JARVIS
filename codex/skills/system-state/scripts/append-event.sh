#!/bin/sh
set -eu
umask 077
event=${1:?event JSON path required}
log=${2:?audit JSONL path required}
[ -f "$event" ] || { echo "event file missing" >&2; exit 2; }
case "$log" in /*|*..*) echo "log must be a relative path without .." >&2; exit 2;; esac
python3 -m json.tool "$event" >/dev/null
mkdir -p "$(dirname "$log")"
chmod 700 "$(dirname "$log")"
python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1])), separators=(",",":"), sort_keys=True))' "$event" >> "$log"
chmod 600 "$log"
