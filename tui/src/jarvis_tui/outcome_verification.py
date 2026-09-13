"""Separate-process outcome checks; no mutation or approval capability."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import (
    cargo_dependencies,
    configuration_operations,
    dependency_apply,
    isolated_execution,
    private_records,
    privileged_operations,
    project_snapshot,
    service_operations,
)
from .observation_safety import open_project, timestamp
from .operation_workflow import OperationWorkflow


def verify(bundle: Path, operation_id: str) -> dict[str, Any]:
    workflow = OperationWorkflow(bundle)
    plan = workflow.load(operation_id)
    result = private_records.read(workflow.root / "results", operation_id + ".json")
    reserved = private_records.read(workflow.root / "reservations", operation_id + ".json")
    report: dict[str, Any] = {
        "id": operation_id,
        "digest": plan["digest"],
        "observed_at": timestamp(),
        "verifier": "separate-read-only-process-v1",
        "verdict": "unknown",
        "checks": {},
    }
    if result.get("digest") != plan["digest"] or reserved.get("digest") != plan["digest"]:
        return report
    if plan.get("privileged_request"):
        receipt = result.get("root_receipt", {})
        request = plan["privileged_request"]
        report["checks"] = {
            "root_receipt_binding": receipt.get("id") == request["id"]
            and receipt.get("request_digest") == plan["request_digest"],
            "root_command_exit": receipt.get("exit_code") == 0
            and receipt.get("attempts") == 1
            and receipt.get("status") == "command_completed_requires_independent_verification",
            "root_post_state": False,
        }
        api = privileged_operations.contract(bundle)
        try:
            if plan["privileged_kind"] == "update":
                report["checks"]["root_post_state"] = (
                    api.rpm_state()
                    == receipt.get("post_state_digest")
                    == receipt.get("expected_post_state_digest")
                )
            elif request["operation"] == "repair_initramfs":
                report["checks"]["root_post_state"] = receipt.get(
                    "image_parse_exit"
                ) == 0 and api.read_file(Path(receipt["staged_image"]))[0] == receipt.get(
                    "staged_sha256"
                )
            else:
                report["checks"]["root_post_state"] = api.boot_state(request) == receipt.get(
                    "post_state"
                )
        except (OSError, ValueError, KeyError):
            report["verdict"] = "unknown"
            report["limitation"] = (
                "Independent root-state read unavailable; privilege-specific verification remains required."
            )
            return report
        report["verdict"] = "pass" if all(report["checks"].values()) else "fail"
        report["bootability_verified"] = False
        return report
    if (plan["domain"], plan["operation"]) in {
        ("network", "configure"),
        ("security", "selinux"),
        ("security", "firewall"),
    }:
        current = configuration_operations.module(bundle).observe(
            plan["adapter"], plan["target"], plan["desired"]
        )
        expected = (
            plan["pre_state"]["expected"]
            if plan["adapter"] == "security.restore_labels"
            else plan["desired"]
        )
        identities = (
            ("device", "inode", "links", "expected")
            if plan["adapter"] == "security.restore_labels"
            else ("definition_digest",)
            if plan["adapter"] == "security.firewall_service"
            else ("target",)
        )
        report["checks"] = {
            "configuration_execution_receipt": result.get("status") == "applied_unverified"
            and result.get("exit_code") == 0
            and result.get("attempts") == 1
            and all(result.get(key) == plan[key] for key in ("adapter", "target", "desired")),
            "configuration_expected_state": current["value"] == expected,
            "configuration_identity": all(
                current.get(key) == plan["pre_state"].get(key) for key in identities
            ),
        }
        report["verdict"] = "pass" if all(report["checks"].values()) else "fail"
        return report
    if plan["domain"] == "health" and plan["operation"] in {"restart", "enable", "disable"}:
        current = service_operations.module(bundle).observe(plan["target"])
        expected_file_state = {"enable": "enabled", "disable": "disabled"}.get(
            plan["operation"], plan["pre_state"]["UnitFileState"]
        )
        expected_active = (
            plan["service_policy"].get("restart_expected_active", "active")
            if plan["operation"] == "restart"
            else plan["pre_state"]["ActiveState"]
        )
        before_links = json.loads(plan["pre_state"].get("current_links", "[]"))
        declared_links = json.loads(plan["pre_state"].get("expected_enabled_links", "[]"))
        expected_links = (
            sorted(set(before_links) | set(declared_links))
            if plan["operation"] == "enable"
            else []
            if plan["operation"] == "disable"
            else before_links
        )
        report["checks"] = {
            "service_link_effects": json.loads(current.get("current_links", "[]"))
            == expected_links,
            "service_execution_receipt": result.get("status") == "applied_unverified"
            and result.get("exit_code") == 0
            and result.get("attempts") == 1
            and result.get("unit") == plan["target"]
            and result.get("operation") == plan["operation"],
            "service_expected_state": current["UnitFileState"] == expected_file_state
            and current["ActiveState"] == expected_active,
            "service_fragment_unchanged": current["fragment_sha256"]
            == plan["pre_state"]["fragment_sha256"],
        }
        report["verdict"] = "pass" if all(report["checks"].values()) else "fail"
        return report
    if plan["domain"] == "network" and plan["operation"] == "external_check":
        report["checks"] = {
            "exact_target_receipt": result.get("target") == plan["target"]
            and result.get("port") == plan["arguments"]["port"],
            "one_attempt_receipt": result.get("attempts") == 1
            and result.get("status") == "observed",
        }
        report["verdict"] = "pass" if all(report["checks"].values()) else "unknown"
        report["limitation"] = (
            "Validates the recorded single attempt, not a new independent remote observation."
        )
        return report
    if plan["domain"] not in {"development", "recovery"}:
        return report
    current = project_snapshot.inspect(Path(plan["target"]))[1]
    if plan["operation"] == "fetch_dependency":
        report["checks"] = {
            "source_tree_unchanged": current == plan["source_tree"],
            "archive_checksum": cargo_dependencies.archive_digest(Path(plan["destination"]))
            == plan["checksum"],
            "download_receipt": result.get("status") == "downloaded"
            and result.get("sha256") == plan["checksum"]
            and result.get("attempts") == 1,
        }
    elif plan["operation"] == "apply_dependencies":
        names = set(plan["files"])
        retained = {name: ".jarvis-dependency-" + plan["id"] + "-" + name for name in names}
        fd = open_project(Path(plan["target"]))
        try:
            originals = all(
                dependency_apply.retained_digest(fd, saved) == plan["source_tree"]["files"][name]
                and dependency_apply.file_metadata(fd, saved) == plan["file_metadata"][name]
                for name, saved in retained.items()
            )
            preserved = all(
                dependency_apply.file_metadata(fd, name) == plan["file_metadata"][name]
                for name in names
            )
        finally:
            os.close(fd)
        report["checks"] = {
            "dependency_metadata_exact": preserved,
            "dependency_files_exact": result.get("status") == "applied_unverified"
            and all(current["files"].get(name) == plan["expected_files"][name] for name in names),
            "retained_originals_exact": originals,
            "unchanged_other_files": current["files"] == plan["expected_files"]
            and set(current["omitted"])
            == set(plan["source_tree"]["omitted"]) | set(retained.values()),
        }
    elif plan["operation"] in {"dependencies", "backup", "restore"}:
        expected = dict(plan["snapshot_tree"]["files"])
        expected.update(
            {
                name: hashlib.sha256(text.encode()).hexdigest()
                for name, text in plan["arguments"].get("files", {}).items()
            }
        )
        workspace = project_snapshot.inspect(Path(plan["destination"]))[1]
        report["checks"] = {
            "source_tree_unchanged": current == plan["source_tree"],
            "exact_workspace_tree": workspace["files"] == expected and not workspace["omitted"],
        }
    else:
        report["checks"] = {
            "source_tree_unchanged": current == plan["source_tree"],
            "snapshot_tree_unchanged": project_snapshot.inspect(Path(plan["snapshot"]))[1]
            == plan["snapshot_tree"],
            "process_exit_zero": result.get("status") == "completed"
            and result.get("exit_code") == 0,
        }
    if "execution_settled" in plan["postconditions"]:
        report["checks"]["execution_settled"] = isolated_execution.settled(workflow.root, plan)
    if plan["operation"] == "command":
        report["goal_verified"] = False
        report["limitation"] = (
            "Verifies process exit, settlement receipt and unchanged input trees; the user's objective requires separate postconditions."
        )
    report["verdict"] = "pass" if all(report["checks"].values()) else "fail"
    return report


if __name__ == "__main__":
    try:
        answer = verify(Path(sys.argv[1]), sys.argv[2])
    except (OSError, ValueError, KeyError, IndexError):
        answer = {"verdict": "unknown", "error": "verification_evidence_unavailable"}
    print(json.dumps(answer, sort_keys=True))
