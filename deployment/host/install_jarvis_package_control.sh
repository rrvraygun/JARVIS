#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  printf 'Run this installer with sudo.\n' >&2
  exit 1
fi
script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
bundle_root=$(cd -- "$script_dir/../.." && pwd -P)
source_file="$bundle_root/vm-lab/scripts/jarvis_package_control.py"
destination=/usr/libexec/jarvis-package-control
policy_source="$bundle_root/deployment/host/org.jarvis.package-control.policy"
policy_destination=/usr/share/polkit-1/actions/org.jarvis.package-control.policy
expected_sha256=477a36cf07de052643af1537a408cb782093cf6afe34fa6958ebcf62ce5e354e
expected_policy_sha256=595523c071f87ef507d85498ee63068b1a0c12079debf34cfe826b40904161ad
staged=$(mktemp /usr/libexec/.jarvis-package-control.XXXXXX)
staged_policy=$(mktemp /usr/share/polkit-1/actions/.org.jarvis.package-control.XXXXXX)
trap 'rm -f -- "$staged" "$staged_policy"' EXIT
if [[ ! -f "$source_file" || -L "$source_file" || ! -f "$policy_source" || -L "$policy_source" ]]; then
  printf 'Package helper or policy source is missing or unsafe.\n' >&2; exit 1
fi
install -o root -g root -m 0755 "$source_file" "$staged"
install -o root -g root -m 0644 "$policy_source" "$staged_policy"
staged_hash=$(sha256sum -- "$staged"); staged_hash=${staged_hash%% *}
policy_hash=$(sha256sum -- "$staged_policy"); policy_hash=${policy_hash%% *}
if [[ "$staged_hash" != "$expected_sha256" || "$policy_hash" != "$expected_policy_sha256" ]]; then
  printf 'Package helper or authorization policy does not match the reviewed digest.\n' >&2; exit 1
fi
python3 -m py_compile "$staged"
rm -f /usr/libexec/__pycache__/.jarvis-package-control.*.pyc
mv -f -- "$staged" "$destination"
mv -f -- "$staged_policy" "$policy_destination"
trap - EXIT
[[ "$(stat -c '%u:%g:%a' "$destination")" == '0:0:755' ]]
[[ "$(sha256sum -- "$destination")" == "$expected_sha256  $destination" ]]
[[ "$(stat -c '%u:%g:%a' "$policy_destination")" == '0:0:644' ]]
[[ "$(sha256sum -- "$policy_destination")" == "$expected_policy_sha256  $policy_destination" ]]
printf 'Installed bounded Jarvis package helper: %s\n' "$destination"
printf 'No package transaction was run by the installer.\n'
