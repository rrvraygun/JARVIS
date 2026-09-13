"""Typed proposals and single-attempt project operations, separate from model tools.

MCP may prepare proposals. Only the TUI can supply an in-memory review decision;
no apply, approval, or verifier-result tool is exposed to the model.
"""

from __future__ import annotations

import difflib
import fcntl
import hashlib
import ipaddress
import json
import os
import socket
import stat
import subprocess
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import (
    cargo_dependencies,
    cargo_download,
    configuration_operations,
    dependency_apply,
    isolated_execution,
    private_records,
    privileged_operations,
    project_snapshot,
    service_operations,
)
from .observation_safety import bounded_process, open_project, read_project_file, timestamp
from .terminal_safety import sanitize_and_redact_terminal_text
from .transcript_store import append as append_transcript
from .transcript_store import sanitized

CARGO_COMMANDS = {
    "check": ("check", "--offline", "--locked"),
    "build": ("build", "--offline", "--locked"),
    "test": ("test", "--offline", "--locked"),
    "fmt": ("fmt", "--all", "--", "--check"),
    "clippy": ("clippy", "--offline", "--locked"),
}
DOMAINS = {"development", "health", "network", "security", "recovery"}


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def project_state(root: Path) -> dict[str, str]:
    fd = open_project(root)
    result: dict[str, str] = {}
    try:
        for name in ("Cargo.toml", "Cargo.lock"):
            try:
                result[name] = hashlib.sha256(read_project_file(fd, name, 262144)).hexdigest()
            except FileNotFoundError:
                result[name] = "absent"
    finally:
        os.close(fd)
    if result["Cargo.toml"] == "absent":
        raise ValueError("cargo_manifest_missing")
    return result


@dataclass(frozen=True)
class Approval:
    """UI-owned ephemeral decision. Never serialized or accepted from MCP input."""

    operation_id: str
    digest: str
    expires_at: float


def validate_command(value: Any) -> list[str]:
    """Explicit argv only; interpreters remain confined to the reviewed sandbox."""
    if (
        not isinstance(value, list)
        or not 1 <= len(value) <= 128
        or not all(isinstance(item, str) and "\x00" not in item for item in value)
        or sum(len(item.encode()) for item in value) > 16000
    ):
        raise ValueError("command_arguments_invalid")
    executable = Path(value[0])
    if (
        not executable.is_absolute()
        or executable.parent != Path("/usr/bin")
        or executable.name in {".", ".."}
    ):
        raise ValueError("command_executable_must_be_usr_bin")
    for item in value:
        safe, changed = sanitize_and_redact_terminal_text(item)
        if changed or safe != item:
            raise ValueError("command_sensitive_or_unreviewable")
    return list(value)


class OperationWorkflow:
    def __init__(self, bundle: Path):
        self.bundle = bundle
        self.root = bundle / "runtime/operations"
        self._approvals: dict[str, Approval] = {}

    def propose(
        self, domain: str, operation: str, target: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        args = arguments or {}
        if domain not in DOMAINS or not isinstance(target, str) or not target or len(target) > 512:
            raise ValueError("invalid_operation_target")
        safe, changed = sanitize_and_redact_terminal_text(target)
        if changed or safe != target:
            raise ValueError("sensitive_operation_target")
        proposal: dict[str, Any] = {
            "schema_version": 1,
            "id": uuid4().hex,
            "created_at": timestamp(),
            "expires_at": time.time() + 600,
            "domain": domain,
            "operation": operation,
            "target": target,
            "environment": {},
            "network": "denied",
            "privilege": "current-user",
            "timeout_seconds": 120,
            "output_limit_bytes": 65536,
            "attempt_limit": 1,
            "approval": "exact-one-use",
            "blockers": [],
            "arguments": args,
            "postconditions": [],
            "risk": 1,
        }
        if domain == "development" and operation in {*CARGO_COMMANDS, "command"}:
            if operation == "command":
                if set(args) != {"argv"}:
                    raise ValueError("exact_command_argv_required")
                command = validate_command(args["argv"])
            else:
                if set(args) - {"downloads"}:
                    raise ValueError("unexpected_cargo_arguments")
                command = ["/usr/bin/cargo", *CARGO_COMMANDS[operation]]
            proposal.update(
                cwd="/project",
                argv=command,
                pre_state=project_state(Path(target)),
                expected_effect="Build/test in a private copy; original project remains unchanged.",
                rollback="Original files are unchanged. Scratch artifacts are retained for reviewed cleanup.",
                isolation="bubblewrap: separate network/PID/user namespaces; read-only /usr; private /project and /tmp; fixed /etc/alternatives/ld link to /usr/bin/ld.bfd",
                postconditions=[
                    "command_exit_zero",
                    "source_manifests_unchanged",
                    "independent_verifier",
                ],
            )
            required = ["/usr/bin/bwrap", command[0]]
            if operation != "command":
                required.extend(["/usr/bin/cargo", "/usr/bin/ld.bfd"])
            if not all(Path(path).is_file() for path in required):
                proposal["blockers"] = ["reviewed_bubblewrap_or_cargo_unavailable"]
        elif domain == "development" and operation == "fetch_dependency":
            if set(args) != {"package", "version"} or not all(
                isinstance(value, str) for value in args.values()
            ):
                raise ValueError("exact_crate_identity_required")
            checksum = cargo_dependencies.locked(Path(target)).get(
                (args["package"], args["version"])
            )
            if checksum is None:
                raise ValueError("crate_not_in_approved_lockfile")
            route = cargo_download.validate(args["package"], args["version"], checksum)
            destination = self.root / "downloads" / (proposal["id"] + ".crate")
            worker = self.bundle / "tui/src/jarvis_tui/cargo_download.py"
            proposal.update(
                cwd="/",
                argv=[
                    "/usr/bin/python3",
                    "-I",
                    str(worker),
                    args["package"],
                    args["version"],
                    checksum,
                    str(destination),
                ],
                checksum=checksum,
                destination=str(destination),
                worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
                url="https://static.crates.io" + route,
                risk=2,
                timeout_seconds=30,
                environment={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                network="One HTTPS GET to the displayed static.crates.io URL, with system DNS/TLS, no redirects, authentication, proxy or retry.",
                expected_effect="Download one checksum-bound crate archive, at most 8 MiB, into a new private file. No project code runs and the original project is unchanged.",
                rollback="The remote request cannot be undone. Partial files are retained for reviewed cleanup; no automatic retry or deletion.",
                postconditions=[
                    "source_tree_unchanged",
                    "archive_checksum",
                    "download_receipt",
                    "independent_verifier",
                ],
            )
        elif domain == "development" and operation == "apply_dependencies":
            if set(args) != {"source_operation"} or not isinstance(args["source_operation"], str):
                raise ValueError("reviewed_dependency_operation_required")
            source = self.load(args["source_operation"])
            if self.result(source["id"]).get("verified") is not True:
                raise ValueError("dependency_workspace_not_verified")
            proposal.update(dependency_apply.prepare(Path(target), source))
            proposal.update(
                cwd=target,
                argv=[],
                destination=target,
                expected_effect="Replace the reviewed existing Cargo manifests individually. Each displaced original is retained in the project. A multi-file change is not atomic as a group.",
                rollback="Original manifests are retained under .jarvis-dependency-<operation>-<name>, and in the source snapshot. Failure retains partial state for separately reviewed recovery; no automatic undo or cleanup. Concurrent edits are detected and retained but may require manual recovery.",
                postconditions=[
                    "dependency_files_exact",
                    "dependency_metadata_exact",
                    "retained_originals_exact",
                    "unchanged_other_files",
                    "independent_verifier",
                ],
            )
        elif domain == "development" and operation == "dependencies":
            if (
                set(args) != {"files"}
                or not isinstance(args["files"], dict)
                or not args["files"]
                or set(args["files"]) - {"Cargo.toml", "Cargo.lock"}
            ):
                raise ValueError("exact_cargo_files_required")
            before = project_state(Path(target))
            diff: list[str] = []
            fd = open_project(Path(target))
            try:
                for name, content in args["files"].items():
                    if not isinstance(content, str) or len(content.encode()) > 262144:
                        raise ValueError("dependency_content_invalid")
                    redacted, changed = sanitize_and_redact_terminal_text(content)
                    if changed or redacted != content:
                        raise ValueError("dependency_content_sensitive")
                    tomllib.loads(content)
                    try:
                        previous = read_project_file(fd, name, 262144).decode()
                    except FileNotFoundError:
                        previous = ""
                    if sanitize_and_redact_terminal_text(previous)[1]:
                        raise ValueError("sensitive_dependency_prestate")
                    diff.extend(
                        difflib.unified_diff(
                            previous.splitlines(),
                            content.splitlines(),
                            fromfile=name + " (before)",
                            tofile=name + " (proposed)",
                            lineterm="",
                        )
                    )
            finally:
                os.close(fd)
            proposal.update(
                cwd=target,
                argv=[],
                pre_state=before,
                diff="\n".join(diff),
                expected_effect="Create a new private project copy with the reviewed Cargo files; original unchanged. No download or build.",
                rollback="Preserve exact prior files in the recovery record; restore requires a new reviewed operation.",
                postconditions=["exact_file_hashes", "independent_verifier"],
            )
        elif domain == "security" and operation in {"boot", "updates"} and args:
            if set(args) != {"request"} or not isinstance(args["request"], dict):
                raise ValueError("exact_privileged_request_required")
            proposal.update(
                privileged_operations.prepare(self.bundle, operation, target, args["request"])
            )
            proposal.update(
                cwd="/",
                risk=4,
                environment={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                privilege="Root helper plus separate root-owned exact expiring review and fresh R2 attestation",
                expected_effect="Exactly the displayed root request. select_kernel selects one next boot; repair_initramfs only stages a new image; install_initramfs publishes it after separate review. Updates replay an exact stored DNF5 transaction.",
                rollback="No automatic rollback. Previous initramfs is retained on publication. Package recovery and boot selection require their own exact review.",
                postconditions=[
                    "root_receipt_binding",
                    "root_command_exit",
                    "root_post_state",
                    "independent_verifier",
                ],
            )
        elif (domain, operation) in {
            ("network", "configure"),
            ("security", "selinux"),
            ("security", "firewall"),
        }:
            if (domain, operation) == ("network", "configure"):
                if set(args) != {"dns"}:
                    raise ValueError("exact_dns_values_required")
                adapter, desired = "network.ipv4_dns", args["dns"]
            elif operation == "selinux":
                if args:
                    raise ValueError("selinux_only_restores_default_labels")
                adapter, desired = "security.restore_labels", "default"
            else:
                if set(args) != {"state"}:
                    raise ValueError("exact_firewall_state_required")
                adapter, desired = "security.firewall_service", args["state"]
            proposal.update(configuration_operations.prepare(self.bundle, adapter, target, desired))
            proposal.update(
                cwd="/",
                argv=["/usr/bin/pkexec", str(configuration_operations.HELPER)],
                risk=2,
                environment={
                    "client": {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                    "helper": {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C"},
                },
                privilege="fixed root-owned Polkit helper; no standing authorization",
                expected_effect="Only the displayed fixed configuration command. DNS modifies the saved profile; no connection activation. Firewall changes runtime membership only. SELinux restores one file label without recursion.",
                rollback="Requires a new exact inverse operation or separately reviewed R1 recovery. External exposure cannot be undone. No automatic rollback.",
                postconditions=[
                    "configuration_execution_receipt",
                    "configuration_expected_state",
                    "configuration_identity",
                    "independent_verifier",
                ],
            )
        elif domain == "health" and operation in {"restart", "enable", "disable"}:
            if args:
                raise ValueError("service_arguments_not_permitted")
            proposal.update(service_operations.prepare(self.bundle, operation, target))
            proposal.update(
                cwd="/",
                argv=["/usr/bin/pkexec", str(service_operations.HELPER)],
                risk=2,
                environment={
                    "client": {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
                    "helper": {"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
                },
                privilege="fixed root-owned Polkit helper; no standing authorization",
                expected_effect=f"Exactly systemctl {operation} {target}; service downtime or boot-start configuration may change.",
                rollback="A new exact inverse enable/disable proposal is required. Restart cannot restore process memory. A current reviewed R1 recovery policy is required.",
                postconditions=[
                    "service_link_effects",
                    "service_execution_receipt",
                    "service_expected_state",
                    "service_fragment_unchanged",
                    "independent_verifier",
                ],
            )
        elif domain == "network" and operation == "external_check":
            address = ipaddress.ip_address(target)
            if address.is_multicast or address.is_unspecified or str(address) != target:
                raise ValueError("exact_unicast_ip_required")
            if (
                set(args) != {"port"}
                or type(args["port"]) is not int
                or not 1 <= args["port"] <= 65535
            ):
                raise ValueError("exact_tcp_port_required")
            proposal.update(
                cwd="/",
                argv=[],
                pre_state={},
                risk=2,
                network="one TCP connection; no DNS or application data",
                timeout_seconds=3,
                expected_effect=f"One TCP connection attempt to {target}:{args['port']}; the remote endpoint may log it.",
                rollback="An external connection cannot be undone. No persistent local configuration changes.",
                postconditions=[
                    "exact_target_receipt",
                    "one_attempt_receipt",
                    "independent_verifier",
                ],
            )
        elif domain == "recovery" and operation in {"backup", "restore"}:
            if set(args) != {"destination"} or not isinstance(args["destination"], str):
                raise ValueError("exact_new_recovery_destination_required")
            destination = Path(args["destination"])
            if not destination.is_absolute() or destination.exists() or destination.is_symlink():
                raise ValueError("recovery_destination_must_be_new")
            os.close(open_project(destination.parent))
            proposal.update(
                cwd=str(destination.parent),
                argv=[],
                pre_state={},
                destination=str(destination),
                expected_effect="Create a new bounded text-project copy. Never overwrite a destination. This is R0 project recovery, not full-system or binary-data backup.",
                rollback="Source remains intact. Partial copies are retained for inspection; cleanup needs a new exact approval.",
                postconditions=[
                    "source_tree_unchanged",
                    "exact_workspace_tree",
                    "independent_verifier",
                ],
            )
        else:
            # High-impact adapter identity must exist before an execution review.
            supported = {
                "health": {"restart", "enable", "disable"},
                "network": {"configure", "external_check"},
                "security": {"selinux", "firewall", "updates", "boot"},
                "recovery": {"backup", "restore"},
            }
            if operation not in supported.get(domain, set()):
                raise ValueError("operation_not_registered")
            if args:
                raise ValueError("host_adapter_arguments_not_registered")
            proposal.update(
                cwd="/",
                argv=[],
                pre_state={},
                risk=2,
                expected_effect=f"Prepare {operation} for the exact target; no host execution.",
                rollback="No host change has occurred. Recovery must be observed and rehearsed before activation.",
                blockers=[
                    "target_specific_adapter_not_activated",
                    "fresh_pre_state_required",
                    "verified_recovery_required",
                    "independent_verification_required",
                ],
                postconditions=["target_specific_postconditions_required"],
            )
        if domain == "development" or (domain == "recovery" and operation in {"backup", "restore"}):
            files, source_tree = project_snapshot.inspect(Path(target))
            snapshots = self.root / "snapshots"
            os.close(private_records.directory(snapshots))
            with os.scandir(snapshots) as entries:
                if sum(1 for _ in entries) >= 16:
                    raise ValueError("snapshot_retention_budget_requires_reviewed_cleanup")
            snapshot = snapshots / proposal["id"]
            project_snapshot.create(snapshot, files)
            proposal["source_tree"] = source_tree
            proposal["snapshot"] = str(snapshot)
            proposal["snapshot_tree"] = project_snapshot.inspect(snapshot)[1]
            if operation == "dependencies":
                proposal["destination"] = str(self.root / "workspaces" / proposal["id"])
                proposal["rollback"] = (
                    "Original project remains unchanged. The separate workspace can be retained or removed only by an explicit reviewed cleanup."
                )
                proposal["postconditions"] = [
                    "source_tree_unchanged",
                    "exact_workspace_tree",
                    "independent_verifier",
                ]
            elif domain == "development" and operation in {*CARGO_COMMANDS, "command"}:
                proposal["resource_limits"] = {
                    "MemoryMax": "1G",
                    "TasksMax": "32",
                    "CPUQuota": "100%",
                    "RuntimeMaxSec": "120",
                    "LimitFSIZE": "256M",
                    "KillMode": "control-group",
                }
                proposal["unit"] = "jarvis-build-" + proposal["id"]
                proposal["settlement_version"] = 1
                proposal["environment"] = {
                    "controller": {
                        "PATH": "/usr/bin:/bin",
                        "LANG": "C.UTF-8",
                        "XDG_RUNTIME_DIR": f"/run/user/{os.geteuid()}",
                    },
                    "sandbox": {
                        "PATH": "/usr/bin:/bin",
                        "HOME": "/tmp",
                        "CARGO_HOME": "/tmp/cargo",
                        "CARGO_TARGET_DIR": "/build",
                        "CARGO_NET_OFFLINE": "true",
                    },
                }
                proposal["postconditions"] = [
                    "source_tree_unchanged",
                    "snapshot_tree_unchanged",
                    "process_exit_zero",
                    "independent_verifier",
                ]
                proposal["postconditions"].append("execution_settled")
                if not Path("/usr/bin/systemd-run").is_file():
                    proposal["blockers"].append("resource_controller_unavailable")
        if (
            domain == "development"
            and operation in CARGO_COMMANDS
            and args.get("downloads") is not None
        ):
            identifiers = args["downloads"]
            if (
                not isinstance(identifiers, list)
                or not 1 <= len(identifiers) <= 64
                or len(set(identifiers)) != len(identifiers)
            ):
                raise ValueError("download_set_invalid")
            locked = cargo_dependencies.locked(Path(target))
            crates = []
            seen = set()
            for identity in identifiers:
                download = self.load(identity)
                pair = (download["arguments"].get("package"), download["arguments"].get("version"))
                if (
                    download["operation"] != "fetch_dependency"
                    or download["target"] != target
                    or pair in seen
                    or locked.get(pair) != download.get("checksum")
                    or not self.result(identity).get("verified")
                    or cargo_dependencies.archive_digest(Path(download["destination"]))
                    != download["checksum"]
                ):
                    raise ValueError("download_not_bound_to_project")
                seen.add(pair)
                crates.append(
                    {
                        "name": pair[0],
                        "version": pair[1],
                        "checksum": download["checksum"],
                        "archive": download["destination"],
                    }
                )
            if seen != set(locked):
                raise ValueError("locked_dependency_downloads_incomplete")
            proposal["crates"] = crates
            proposal["vendor_worker_sha256"] = hashlib.sha256(
                (self.bundle / "tui/src/jarvis_tui/cargo_vendor.py").read_bytes()
            ).hexdigest()
        if domain == "development" and operation == "command":
            resolved = Path(proposal["argv"][0]).resolve(strict=True)
            if not resolved.is_relative_to("/usr"):
                raise ValueError("command_executable_outside_readonly_mount")
            proposal["executable"] = {
                "resolved": str(resolved),
                "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
            }
            proposal["expected_effect"] = (
                "Run the exact argv in an offline, read-only project sandbox. Exit zero verifies process completion only, not achievement of the user's objective."
            )
        if domain == "development":
            guard_source = Path(__file__).parent / "resource_guard.py"
            proposal["resource_guard_sha256"] = hashlib.sha256(
                guard_source.read_bytes()
            ).hexdigest()
        proposal["digest"] = digest(proposal)
        private_records.write_once(self.root / "proposals", proposal["id"] + ".json", proposal)
        return proposal

    def load(self, operation_id: str) -> dict[str, Any]:
        if len(operation_id) != 32 or any(c not in "0123456789abcdef" for c in operation_id):
            raise ValueError("invalid_operation_id")
        value = private_records.read(self.root / "proposals", operation_id + ".json")
        material = {k: v for k, v in value.items() if k != "digest"}
        if value.get("id") != operation_id or digest(material) != value.get("digest"):
            raise ValueError("proposal_digest_mismatch")
        if value.get("domain") == "development" and value.get("operation") in CARGO_COMMANDS:
            if value.get("argv") != ["/usr/bin/cargo", *CARGO_COMMANDS[value["operation"]]]:
                raise ValueError("cargo_command_not_registered")
        if value.get("operation") == "command":
            if value.get("domain") != "development" or validate_command(
                value["arguments"]["argv"]
            ) != value.get("argv"):
                raise ValueError("command_binding_invalid")
        if "snapshot" in value and value["snapshot"] != str(self.root / "snapshots" / operation_id):
            raise ValueError("snapshot_target_not_bound")
        return value

    def approve(self, operation_id: str, reviewed_digest: str) -> Approval:
        value = self.load(operation_id)
        if (
            value["digest"] != reviewed_digest
            or value["expires_at"] < time.time()
            or value["blockers"]
        ):
            raise ValueError("proposal_not_executable")
        if value.get("operation") in {*CARGO_COMMANDS, "command"}:
            self._require_settled_commands()
        approval = Approval(
            operation_id, reviewed_digest, min(time.time() + 60, value["expires_at"])
        )
        self._approvals[operation_id] = approval
        return approval

    def _require_settled_commands(self) -> None:
        root = self.root / "reservations"
        if not root.exists():
            return
        fd = private_records.directory(root, create=False)
        try:
            with os.scandir(fd) as entries:
                for count, entry in enumerate(entries):
                    if count >= 256:
                        raise ValueError("operation_history_requires_review")
                    identity = entry.name.removesuffix(".json")
                    old = self.load(identity)
                    if old.get("domain") != "development" or old.get("operation") not in {
                        *CARGO_COMMANDS,
                        "command",
                    }:
                        continue
                    try:
                        private_records.read(self.root / "results", entry.name)
                    except FileNotFoundError:
                        raise ValueError("prior_command_outcome_pending") from None
                    if not isolated_execution.settled(self.root, old):
                        raise ValueError("prior_command_outcome_pending")
        finally:
            os.close(fd)

    def _reserve(self, plan: dict[str, Any]) -> None:
        root = private_records.directory(self.root)
        try:
            lock = os.open(
                "execution.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=root
            )
        finally:
            os.close(root)
        try:
            info = os.fstat(lock)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_nlink != 1
                or info.st_mode & 0o077
            ):
                raise ValueError("execution_lock_unsafe")
            fcntl.flock(lock, fcntl.LOCK_EX)
            if plan.get("domain") == "development" and plan.get("operation") in {
                *CARGO_COMMANDS,
                "command",
            }:
                self._require_settled_commands()
            private_records.write_once(
                self.root / "reservations",
                plan["id"] + ".json",
                {"digest": plan["digest"], "reserved_at": timestamp()},
            )
        finally:
            os.close(lock)

    def execute(self, approval: Approval) -> dict[str, Any]:
        issued = self._approvals.pop(approval.operation_id, None)
        if issued is not approval or time.time() > approval.expires_at:
            raise ValueError("approval_missing_expired_or_consumed")
        plan = self.load(approval.operation_id)
        if (
            plan["digest"] != approval.digest
            or plan["blockers"]
            or plan["expires_at"] < time.time()
        ):
            raise ValueError("proposal_not_executable")
        external = plan["domain"] == "network" and plan["operation"] == "external_check"
        configuration = (plan["domain"], plan["operation"]) in {
            ("network", "configure"),
            ("security", "selinux"),
            ("security", "firewall"),
        }
        service = plan["domain"] == "health" and plan["operation"] in {
            "restart",
            "enable",
            "disable",
        }
        privileged = plan["domain"] == "security" and bool(plan.get("privileged_request"))
        if (
            plan["domain"] != "development"
            and not (plan["domain"] == "recovery" and plan["operation"] in {"backup", "restore"})
            and not external
            and not service
            and not configuration
            and not privileged
        ):
            raise ValueError("host_adapter_not_activated")
        self._reserve(plan)
        result: dict[str, Any] = {
            "id": plan["id"],
            "digest": plan["digest"],
            "status": "indeterminate",
            "observed_at": timestamp(),
            "attempts": 1,
            "verified": False,
        }
        try:
            if privileged:
                result.update(privileged_operations.apply(self.bundle, plan))
            elif configuration:
                result.update(configuration_operations.apply(self.bundle, plan))
            elif service:
                result.update(service_operations.apply(self.bundle, plan))
            elif external:
                address = ipaddress.ip_address(plan["target"])
                family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
                with socket.socket(family, socket.SOCK_STREAM) as connection:
                    connection.settimeout(3)
                    try:
                        connection.connect((plan["target"], plan["arguments"]["port"]))
                        result.update(
                            status="observed",
                            connected=True,
                            target=plan["target"],
                            port=plan["arguments"]["port"],
                        )
                    except OSError as exc:
                        result.update(
                            status="observed",
                            connected=False,
                            target=plan["target"],
                            port=plan["arguments"]["port"],
                            error=type(exc).__name__,
                        )
            else:
                if project_snapshot.inspect(Path(plan["target"]))[1] != plan["source_tree"]:
                    raise ValueError("pre_state_drift")
                if plan["operation"] == "fetch_dependency":
                    result.update(self._fetch_dependency(plan))
                elif plan["operation"] == "apply_dependencies":
                    result.update(dependency_apply.apply(self.root, plan))
                elif plan["operation"] in {"dependencies", "backup", "restore"}:
                    result.update(self._dependencies(plan))
                else:
                    result.update(self._cargo(plan))
                result["post_state"] = project_snapshot.inspect(Path(plan["target"]))[1]
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            result["error"] = type(exc).__name__
        private_records.write_once(self.root / "results", plan["id"] + ".json", sanitized(result))
        verification = bounded_process(
            (
                "/usr/bin/bwrap",
                "--unshare-all",
                "--die-with-parent",
                "--new-session",
                "--ro-bind",
                "/",
                "/",
                "--",
                "/usr/bin/python3",
                "-m",
                "jarvis_tui.outcome_verification",
                str(self.bundle),
                plan["id"],
            ),
            timeout=10,
            limit=16000,
            env={
                "PATH": "/usr/bin:/bin",
                "PYTHONPATH": str(self.bundle / "tui/src"),
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )
        report: dict[str, Any]
        try:
            report = (
                json.loads(verification["output"])
                if verification["status"] == "completed"
                else {"verdict": "unknown"}
            )
        except (ValueError, KeyError):
            report = {"verdict": "unknown"}
        if not isinstance(report, dict):
            report = {"verdict": "unknown"}
        private_records.write_once(self.root / "verification", plan["id"] + ".json", report)
        result = self.result(plan["id"])
        try:
            append_transcript(self.bundle, "operation_result", plan["id"], result)
        except (OSError, ValueError):
            result["transcript_status"] = (
                "unavailable; durable result and verification remain available"
            )
        return result

    def result(self, operation_id: str) -> dict[str, Any]:
        plan = self.load(operation_id)
        result = private_records.read(self.root / "results", plan["id"] + ".json")
        try:
            report = private_records.read(self.root / "verification", plan["id"] + ".json")
        except FileNotFoundError:
            report = {"verdict": "unknown"}
        checks = report.get("checks", {})
        if not isinstance(checks, dict):
            checks = {}
        result["verification"] = report
        result["verified"] = (
            result.get("id") == plan["id"]
            and result.get("digest") == plan["digest"]
            and report.get("verdict") == "pass"
            and report.get("id") == plan["id"]
            and report.get("digest") == plan["digest"]
            and set(checks) == set(plan["postconditions"]) - {"independent_verifier"}
            and all(value is True for value in checks.values())
        )
        return result

    def _fetch_dependency(self, plan: dict[str, Any]) -> dict[str, Any]:
        worker = self.bundle / "tui/src/jarvis_tui/cargo_download.py"
        if hashlib.sha256(worker.read_bytes()).hexdigest() != plan["worker_sha256"]:
            raise ValueError("download_worker_drift")
        os.close(private_records.directory(self.root / "downloads"))
        result = bounded_process(
            tuple(plan["argv"]), timeout=30, limit=4000, env=plan["environment"]
        )
        if result["status"] != "completed":
            return {"status": "download_failed_or_partial", "attempts": 1}
        receipt = json.loads(result["output"])
        if (
            not isinstance(receipt, dict)
            or receipt.get("status") != "downloaded"
            or receipt.get("sha256") != plan["checksum"]
            or receipt.get("attempts") != 1
        ):
            raise ValueError("download_receipt_invalid")
        return {
            "status": "downloaded",
            "attempts": 1,
            "sha256": plan["checksum"],
            "bytes": receipt["bytes"],
        }

    def _dependencies(self, plan: dict[str, Any]) -> dict[str, Any]:
        files, tree = project_snapshot.inspect(Path(plan["snapshot"]))
        if tree != plan["snapshot_tree"]:
            raise ValueError("approved_snapshot_drift")
        for name, text in plan["arguments"].get("files", {}).items():
            files[name] = text.encode()
        destination = Path(plan["destination"])
        if plan["domain"] == "development":
            os.close(private_records.directory(destination.parent))
        project_snapshot.create(destination, files)
        return {
            "status": "prepared_workspace",
            "destination": str(destination),
            "workspace_tree": project_snapshot.inspect(destination)[1],
            "original_unchanged": True,
            "recovery_available": False,
        }

    def _cargo(self, plan: dict[str, Any]) -> dict[str, Any]:
        # No home, credentials, shared socket, device or writable source mount.
        if (
            hashlib.sha256((Path(__file__).parent / "resource_guard.py").read_bytes()).hexdigest()
            != plan["resource_guard_sha256"]
        ):
            raise ValueError("resource_guard_drift")
        if plan["operation"] == "command":
            resolved = Path(plan["argv"][0]).resolve(strict=True)
            if {
                "resolved": str(resolved),
                "sha256": hashlib.sha256(resolved.read_bytes()).hexdigest(),
            } != plan["executable"]:
                raise ValueError("command_executable_drift")
        copy = Path(plan["snapshot"])
        if project_snapshot.inspect(copy)[1] != plan["snapshot_tree"]:
            raise ValueError("approved_snapshot_drift")
        argv = (
            "/usr/bin/bwrap",
            "--unshare-all",
            "--die-with-parent",
            "--new-session",
            "--clearenv",
            "--ro-bind",
            "/usr",
            "/usr",
            "--symlink",
            "usr/bin",
            "/bin",
            "--symlink",
            "usr/lib",
            "/lib",
            "--symlink",
            "usr/lib64",
            "/lib64",
            "--dir",
            "/etc",
            "--dir",
            "/etc/alternatives",
            "--symlink",
            "/usr/bin/ld.bfd",
            "/etc/alternatives/ld",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--size",
            "268435456",
            "--tmpfs",
            "/tmp",
            "--dir",
            "/home",
            "--ro-bind",
            str(copy),
            "/project",
            "--size",
            "536870912",
            "--tmpfs",
            "/build",
            "--chdir",
            "/project",
            "--setenv",
            "PATH",
            "/usr/bin:/bin",
            "--setenv",
            "HOME",
            "/tmp",
            "--setenv",
            "CARGO_TARGET_DIR",
            "/build",
            "--setenv",
            "CARGO_HOME",
            "/tmp/cargo",
            "--setenv",
            "CARGO_NET_OFFLINE",
            "true",
            *plan["argv"],
        )
        if plan.get("crates"):
            worker = self.bundle / "tui/src/jarvis_tui/cargo_vendor.py"
            if hashlib.sha256(worker.read_bytes()).hexdigest() != plan["vendor_worker_sha256"]:
                raise ValueError("vendor_worker_drift")
            mounts = ["--dir", "/dependencies", "--ro-bind", str(worker), "/vendor-worker.py"]
            for crate in plan["crates"]:
                if cargo_dependencies.archive_digest(Path(crate["archive"])) != crate["checksum"]:
                    raise ValueError("download_archive_drift")
                mounts.extend(
                    [
                        "--ro-bind",
                        crate["archive"],
                        "/dependencies/" + crate["name"] + "-" + crate["version"] + ".crate",
                    ]
                )
            metadata = [
                {key: value for key, value in crate.items() if key != "archive"}
                for crate in plan["crates"]
            ]
            argv = (
                *argv[: -len(plan["argv"])],
                *mounts,
                "/usr/bin/python3",
                "-I",
                "/vendor-worker.py",
                json.dumps(metadata),
                *plan["argv"],
            )
        limits = tuple(
            item
            for key, value in plan["resource_limits"].items()
            for item in ("--property", key + "=" + value)
        )
        argv = (
            "/usr/bin/systemd-run",
            "--user",
            "--wait",
            "--pipe",
            "--collect",
            "--unit",
            plan["unit"],
            *limits,
            "/usr/bin/python3",
            "-I",
            str(self.bundle / "tui/src/jarvis_tui/resource_guard.py"),
            str(self.root / "starts" / (plan["id"] + ".json")),
            plan["id"],
            plan["digest"],
            *argv,
        )
        os.close(private_records.directory(self.root / "starts"))
        private_records.write_once(
            self.root / "launches", plan["id"] + ".json", {"digest": plan["digest"]}
        )
        result = bounded_process(
            argv,
            timeout=plan["timeout_seconds"],
            limit=plan["output_limit_bytes"],
            env={
                "PATH": "/usr/bin:/bin",
                "LANG": "C.UTF-8",
                "XDG_RUNTIME_DIR": f"/run/user/{os.geteuid()}",
            },
        )
        result.pop("argv", None)
        result["execution_settled"] = isolated_execution.settled(self.root, plan)
        result["unit"] = plan["unit"]
        if plan["operation"] == "command":
            result["goal_verified"] = False
        if not result["execution_settled"]:
            result["status"] = "indeterminate"
        return result

    def recovery_proposal(self, operation_id: str) -> dict[str, Any]:
        plan = self.load(operation_id)
        if plan["operation"] == "apply_dependencies":
            try:
                recovery = dependency_apply.recovery(plan)
            except (OSError, ValueError):
                recovery = {
                    "status": "blocked_current_state_requires_review",
                    "execution_authorized": False,
                }
            return {
                "recovery": recovery,
                "id": plan["id"],
                "execution_authorized": False,
                "original_unchanged_by_design": False,
                "source_snapshot": plan["snapshot"],
                "retained_candidates": {
                    name: ".jarvis-dependency-" + plan["id"] + "-" + name for name in plan["files"]
                },
                "message": "Inspect the durable result and current manifests. Displaced originals and the pre-change snapshot are retained. A partial operation may leave staged replacements instead of originals at some candidate paths: verify hashes before proposing exact recovery. No automatic recovery is authorized.",
            }
        separate_copy = (
            plan["domain"] == "development" and plan["operation"] != "apply_dependencies"
        ) or (plan["domain"] == "recovery" and plan["operation"] in {"backup", "restore"})
        return {
            "id": plan["id"],
            "execution_authorized": False,
            "original_unchanged_by_design": separate_copy,
            "message": (
                "Operations use separate copies. Original files were not overwritten. Partial workspaces require inspection and separately reviewed cleanup."
                if separate_copy
                else "Inspect the durable result and current target state. This operation may have affected the host or an external endpoint; recovery requires a separately reviewed exact operation."
            ),
        }
