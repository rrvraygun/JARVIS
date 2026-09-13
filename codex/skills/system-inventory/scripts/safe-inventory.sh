#!/bin/sh
set -eu
umask 077
output=${1:-inventory.txt}
case "$output" in /*|*..*) echo "output must be a relative path without .." >&2; exit 2;; esac
{
  echo "schema=1"
  date -u '+collected_at=%Y-%m-%dT%H:%M:%SZ'
  printf 'kernel='; uname -srmo 2>/dev/null || echo unavailable
  if [ -r /etc/os-release ]; then
    sed -n 's/^\(ID\|VERSION_ID\|VERSION_CODENAME\)=/os_\1=/p' /etc/os-release
  else
    echo 'os_release=unavailable'
  fi
  printf 'architecture='; uname -m 2>/dev/null || echo unavailable
  printf 'uptime='; uptime 2>/dev/null || echo unavailable
  printf 'filesystem_capacity_begin\n'; df -P 2>/dev/null || true
  printf 'filesystem_capacity_end\n'
  if command -v systemctl >/dev/null 2>&1; then
    printf 'failed_units_begin\n'; systemctl --failed --no-legend --no-pager 2>/dev/null || true
    printf 'failed_units_end\n'
  fi
} > "$output"
chmod 600 "$output"
printf '%s\n' "$output"
