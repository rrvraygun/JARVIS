#!/usr/bin/env bash
set -euo pipefail

# Provision a TPM-resident HMAC key for the Jarvis checkpoint provider.
# This script is intentionally explicit and unactivated: it creates one
# persistent TPM object and never exports the key material.

if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
  printf 'must run as root (use sudo from the user terminal)\n' >&2
  exit 2
fi

command -v tpm2_getcap >/dev/null
command -v tpm2_createprimary >/dev/null
command -v tpm2_create >/dev/null
command -v tpm2_load >/dev/null
command -v tpm2_evictcontrol >/dev/null
command -v tpm2_flushcontext >/dev/null
command -v tpm2_hmac >/dev/null
command -v tpm2_readpublic >/dev/null

target_user=${SUDO_USER:-}
if [[ -z $target_user || $target_user == root ]]; then
  printf 'run through sudo so the target user is unambiguous\n' >&2
  exit 2
fi
target_group=$(id -gn "$target_user")

handle=${JARVIS_TPM_HMAC_HANDLE:-0x81000010}
if [[ ! $handle =~ ^0x81[0-9a-fA-F]{6}$ ]]; then
  printf 'invalid persistent handle: %s\n' "$handle" >&2
  exit 2
fi

if tpm2_getcap handles-persistent | grep -Fq -- "- $handle"; then
  printf 'persistent handle already exists: %s\n' "$handle" >&2
  exit 1
fi

# Keep the directory root-controlled because this script runs as root. The
# authorization files remain owned by the target user so an unprivileged
# provider can read them, but the user cannot replace the containing path.
key_dir=/var/lib/jarvis/tpm
auth_file="$key_dir/hmac.auth"
metadata_file="$key_dir/hmac-key.json"

ensure_root_controlled_dir() {
  local path=$1 mode=$2 group=$3
  if [[ -e $path ]]; then
    [[ -d $path && ! -L $path ]] || { printf 'unsafe directory: %s\n' "$path" >&2; exit 2; }
    local owner current_mode
    owner=$(stat -c '%u' "$path")
    current_mode=$(stat -c '%a' "$path")
    (( owner == 0 )) || { printf 'directory is not root-owned: %s\n' "$path" >&2; exit 2; }
    (( (8#$current_mode & 022) == 0 )) || { printf 'directory is group/world-writable: %s\n' "$path" >&2; exit 2; }
  else
    install -d -m "$mode" -o root -g "$group" "$path"
  fi
}

ensure_root_controlled_dir /var/lib/jarvis 755 root
ensure_root_controlled_dir "$key_dir" 750 "$target_group"

if [[ -e $auth_file || -e $metadata_file ]]; then
  printf 'refusing to overwrite existing HMAC key metadata\n' >&2
  exit 1
fi

tmp_dir=$(mktemp -d)
persistent_candidate=0
completed=0
primary_loaded=0
hmac_loaded=0
rollback_failed=0
cleanup() {
  local status=$?
  if (( ! completed )); then
    if (( persistent_candidate )) && [[ -s "$tmp_dir/hmac.name" ]]; then
      # Evict only when the persistent object still has the exact name of the
      # HMAC object created by this run. If the handle was claimed or changed
      # concurrently, fail safe and leave it untouched.
      if tpm2_readpublic -Q -c "$handle" -n "$tmp_dir/persistent.name" >/dev/null 2>&1 &&
         cmp -s "$tmp_dir/hmac.name" "$tmp_dir/persistent.name"; then
        if tpm2_evictcontrol -Q -C o -c "$handle" >/dev/null 2>&1; then
          rm -f -- "$auth_file" "$metadata_file"
        else
          rollback_failed=1
          printf 'ERROR: TPM rollback failed; preserving %s for manual recovery\n' "$auth_file" >&2
        fi
      else
        rollback_failed=1
        printf 'ERROR: TPM rollback identity could not be confirmed; preserving %s\n' "$auth_file" >&2
      fi
    elif (( persistent_candidate )); then
      rollback_failed=1
      printf 'ERROR: TPM rollback could not inspect the candidate; preserving %s\n' "$auth_file" >&2
    else
      rm -f -- "$auth_file" "$metadata_file"
    fi
  fi
  if (( hmac_loaded )); then
    tpm2_flushcontext -Q -c "$tmp_dir/hmac.ctx" >/dev/null 2>&1 || true
  fi
  if (( primary_loaded )); then
    tpm2_flushcontext -Q -c "$tmp_dir/primary.ctx" >/dev/null 2>&1 || true
  fi
  rm -rf -- "$tmp_dir"
  if (( rollback_failed )); then
    exit 70
  fi
  exit "$status"
}
trap cleanup EXIT

umask 077
openssl rand 32 > "$tmp_dir/auth"
install -m 600 -o "$target_user" -g "$target_group" "$tmp_dir/auth" "$auth_file"

tpm2_createprimary -Q -C o -g sha256 -G rsa2048 -c "$tmp_dir/primary.ctx"
primary_loaded=1
tpm2_create -Q -C "$tmp_dir/primary.ctx" -g sha256 -G hmac \
  -p "file:$auth_file" -u "$tmp_dir/hmac.pub" -r "$tmp_dir/hmac.priv"
tpm2_load -Q -C "$tmp_dir/primary.ctx" -u "$tmp_dir/hmac.pub" -r "$tmp_dir/hmac.priv" -c "$tmp_dir/hmac.ctx"
hmac_loaded=1
# Capture the transient object's canonical TPM name before the stateful
# persistent-handle mutation. The cleanup trap uses it to avoid evicting an
# unrelated object if the handle is claimed concurrently.
tpm2_readpublic -Q -c "$tmp_dir/hmac.ctx" -n "$tmp_dir/hmac.name"
# Arm rollback before the stateful TPM mutation. If the command is interrupted
# after creating the persistent object but before returning, the EXIT trap can
# clean it up after identity verification.
persistent_candidate=1
tpm2_evictcontrol -Q -C o -c "$tmp_dir/hmac.ctx" "$handle"

printf 'jarvis checkpoint test' | tpm2_hmac -Q -c "$handle" -p "file:$auth_file" --hex >/dev/null
printf '{"schema_version":1,"handle":"%s","auth_file":"%s","status":"prepared_unactivated"}\n' \
  "$handle" "$auth_file" > "$tmp_dir/metadata"
install -m 600 -o "$target_user" -g "$target_user" "$tmp_dir/metadata" "$metadata_file"
completed=1

printf 'TPM HMAC key provisioned at %s\n' "$handle"
printf 'metadata: %s\n' "$metadata_file"
printf 'Jarvis remains unactivated.\n'
