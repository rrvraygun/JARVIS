#!/usr/bin/env bash
set -euo pipefail

if [[ ${EUID} -ne 0 ]]; then
  printf 'Run this installer with sudo.\n' >&2
  exit 1
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
bundle_root=$(cd -- "$script_dir/../.." && pwd -P)
source_file="$bundle_root/vm-lab/scripts/jarvis_power_control.py"
destination=/usr/libexec/jarvis-power-control
policy_source="$bundle_root/deployment/host/org.jarvis.power-control.policy"
policy_destination=/usr/share/polkit-1/actions/org.jarvis.power-control.policy
expected_sha256=8e8850a5804d20529e09cff294ab506835b4de9be54dcb705be5a3d5fd4f6b58
expected_policy_sha256=b85af02160d6682e3d75af15c4e98508be4a115350a3ca3fe531bc0b011d5460
staged=$(mktemp /usr/libexec/.jarvis-power-control.XXXXXX)
staged_policy=$(mktemp /usr/share/polkit-1/actions/.org.jarvis.power-control.XXXXXX)
trap 'rm -f -- "$staged" "$staged_policy"' EXIT

if [[ ! -f "$source_file" || -L "$source_file" || ! -f "$policy_source" || -L "$policy_source" ]]; then
  printf 'Power helper or policy source is missing or unsafe.\n' >&2
  exit 1
fi

install -o root -g root -m 0755 "$source_file" "$staged"
install -o root -g root -m 0644 "$policy_source" "$staged_policy"
staged_hash=$(sha256sum -- "$staged")
staged_hash=${staged_hash%% *}
if [[ "$staged_hash" != "$expected_sha256" ]]; then
  printf 'Power helper does not match the independently reviewed digest.\n' >&2
  exit 1
fi
policy_hash=$(sha256sum -- "$staged_policy")
policy_hash=${policy_hash%% *}
if [[ "$policy_hash" != "$expected_policy_sha256" ]]; then
  printf 'Power authorization policy does not match the reviewed digest.\n' >&2
  exit 1
fi
python3 -m py_compile "$staged"
rm -f /usr/libexec/__pycache__/.jarvis-power-control.*.pyc
mv -f -- "$staged" "$destination"
mv -f -- "$staged_policy" "$policy_destination"
trap - EXIT

owner_mode=$(stat -c '%u:%g:%a' "$destination")
if [[ "$owner_mode" != '0:0:755' ]]; then
  printf 'Installed helper ownership/mode verification failed.\n' >&2
  exit 1
fi
destination_hash=$(sha256sum -- "$destination")
destination_hash=${destination_hash%% *}
if [[ "$destination_hash" != "$expected_sha256" ]]; then
  printf 'Installed helper digest verification failed.\n' >&2
  exit 1
fi
policy_owner_mode=$(stat -c '%u:%g:%a' "$policy_destination")
if [[ "$policy_owner_mode" != '0:0:644' ]]; then
  printf 'Installed power authorization policy ownership/mode verification failed.\n' >&2
  exit 1
fi
installed_policy_hash=$(sha256sum -- "$policy_destination")
installed_policy_hash=${installed_policy_hash%% *}
if [[ "$installed_policy_hash" != "$expected_policy_sha256" ]]; then
  printf 'Installed power authorization policy digest verification failed.\n' >&2
  exit 1
fi

printf 'Installed bounded Jarvis power helper: %s\n' "$destination"
printf 'No power setting was changed.\n'
