#!/bin/sh
set -eu
bundle=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
python_bin=${JARVIS_PYTHON:-"$bundle/.venv/bin/python"}
validator=/home/tipexxx/.codex/skills/.system/skill-creator/scripts/quick_validate.py
plugin_validator=/home/tipexxx/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py

if [ ! -x "$python_bin" ]; then
  echo "missing project Python interpreter: $python_bin" >&2
  exit 2
fi
if ! "$python_bin" -c 'import textual'; then
  echo "pinned Textual dependency is required for TUI release validation" >&2
  exit 2
fi

[ -f "$bundle/AGENTS.md" ]
[ -f "$bundle/codex/jarvis.config.example.toml" ]
[ -f "$bundle/codex/agents/deep-researcher.toml" ]
[ -f "$bundle/codex/agents/system-administrator.toml" ]

python3 - "$bundle" <<'PY'
import json, pathlib, sys, tomllib
root = pathlib.Path(sys.argv[1])
for path in root.glob("codex/**/*.toml"):
    with path.open("rb") as handle:
        tomllib.load(handle)
json.loads((root / "codex/hooks.example.json").read_text())
with (root / "tui/pyproject.toml").open("rb") as handle:
    tui_project = tomllib.load(handle)
assert tui_project["project"]["dependencies"] == ["textual==8.2.8"]
PY

for skill in "$bundle"/codex/skills/*; do
  python3 "$validator" "$skill"
done
python3 "$validator" "$bundle/plugins/jarvis-system-admin/skills/jarvis-control-plane"
python3 "$plugin_validator" "$bundle/plugins/jarvis-system-admin"
python3 "$bundle/plugins/jarvis-system-admin/scripts/jarvisctl.py" validate
python3 "$bundle/plugins/jarvis-system-admin/tests/test_control_plane.py"
python3 "$bundle/plugins/jarvis-system-admin/tests/test_knowledge_store.py"
python3 "$bundle/plugins/jarvis-system-admin/tests/test_mcp_server.py"
python3 "$bundle/vm-lab/scripts/labctl.py" validate >/dev/null
python3 "$bundle/vm-lab/tests/test_vm_lab.py"
python3 "$bundle/vm-lab/scripts/controller_contract.py" >/dev/null
python3 "$bundle/vm-lab/tests/test_controller_contract.py"
python3 "$bundle/vm-lab/scripts/observation_contract.py" >/dev/null
python3 "$bundle/vm-lab/tests/test_observation_contract.py"
python3 "$bundle/vm-lab/scripts/vm_blueprint_contract.py" >/dev/null
python3 "$bundle/vm-lab/tests/test_vm_blueprint_contract.py"
python3 "$bundle/vm-lab/scripts/readiness_contract.py" >/dev/null
python3 "$bundle/vm-lab/tests/test_readiness_contract.py"
python3 "$bundle/deployment/host/validate_policy.py" >/dev/null
python3 "$bundle/tests/host/test_direct_host_policy.py"
python3 "$bundle/deployment/host/validate_recovery_set.py" >/dev/null
python3 "$bundle/tests/host/test_recovery_set.py"
python3 "$bundle/tests/host/test_verify_restored_boundaries.py"
python3 "$bundle/tests/host/test_diagnose_restored_tokens.py"
if [ "${JARVIS_SKIP_TUI_TESTS:-0}" != 1 ]; then
  PYTHONPATH="$bundle/tui/src" "$python_bin" -m unittest discover \
    -s "$bundle/tui/tests" -p 'test_*.py'
fi
for fixture in read-only update forbidden; do
  python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
    "$bundle/plugins/jarvis-system-admin/schemas/action-context.schema.json" \
    "$bundle/plugins/jarvis-system-admin/tests/fixtures/$fixture.json" >/dev/null
done
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/plugins/jarvis-system-admin/schemas/approval.schema.json" \
  "$bundle/plugins/jarvis-system-admin/tests/fixtures/knowledge/approval.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/plugins/jarvis-system-admin/schemas/system-fact.schema.json" \
  "$bundle/plugins/jarvis-system-admin/tests/fixtures/knowledge/fact.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/plugins/jarvis-system-admin/schemas/lesson.schema.json" \
  "$bundle/plugins/jarvis-system-admin/tests/fixtures/knowledge/lesson.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/plugins/jarvis-system-admin/schemas/decision-record.schema.json" \
  "$bundle/plugins/jarvis-system-admin/tests/fixtures/knowledge/decision.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/plugins/jarvis-system-admin/schemas/error-revision.schema.json" \
  "$bundle/plugins/jarvis-system-admin/tests/fixtures/knowledge/error-revision.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/plugins/jarvis-system-admin/schemas/remote-sink.schema.json" \
  "$bundle/plugins/jarvis-system-admin/policy/remote-sink.example.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/schemas/intent-envelope.schema.json" \
  "$bundle/tui/tests/fixtures/intent-lighting.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/schemas/task-record.schema.json" \
  "$bundle/tui/tests/fixtures/task-lighting.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/schemas/broker-event.schema.json" \
  "$bundle/tui/tests/fixtures/broker-event.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/schemas/session-snapshot.schema.json" \
  "$bundle/tui/tests/fixtures/session-ready.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/schemas/task-admission.schema.json" \
  "$bundle/tui/tests/fixtures/task-admission-scoped.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/schemas/task-admission.schema.json" \
  "$bundle/tui/tests/fixtures/task-admission-local-read.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/schemas/task-admission.schema.json" \
  "$bundle/tui/tests/fixtures/task-admission-registered-read.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/schemas/task-admission.schema.json" \
  "$bundle/tui/tests/fixtures/task-admission-local-mutation.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/schemas/task-admission.schema.json" \
  "$bundle/tui/tests/fixtures/task-admission-registered-mutation.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/twin-profile.schema.json" \
  "$bundle/vm-lab/profiles/fedora-workstation-template.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/lab-policy.schema.json" \
  "$bundle/vm-lab/policy/lab-policy.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/image-lock.schema.json" \
  "$bundle/vm-lab/images/fedora-workstation-image-lock.template.json" >/dev/null
for matrix in lighting-controls sysadmin-control-plane; do
  python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
    "$bundle/vm-lab/schemas/scenario-matrix.schema.json" \
    "$bundle/vm-lab/matrices/$matrix.json" >/dev/null
done
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/scenario-catalog.schema.json" \
  "$bundle/vm-lab/scenarios/catalog.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/run-record.schema.json" \
  "$bundle/vm-lab/fixtures/run-record.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/physical-gap-catalog.schema.json" \
  "$bundle/vm-lab/coverage/physical-gaps.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/coverage-expectation.schema.json" \
  "$bundle/vm-lab/coverage/expected.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/controller-policy.schema.json" \
  "$bundle/vm-lab/controller/policy.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/controller-operation-registry.schema.json" \
  "$bundle/vm-lab/controller/operations.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/controller-state-machine.schema.json" \
  "$bundle/vm-lab/controller/state-machine.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/enrollment-source-catalog.schema.json" \
  "$bundle/vm-lab/enrollment/source-catalog.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/enrollment-proposal.schema.json" \
  "$bundle/vm-lab/enrollment/fedora-workstation-proposal.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/enrollment-review.schema.json" \
  "$bundle/vm-lab/enrollment/review.pending.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/controller-request.schema.json" \
  "$bundle/vm-lab/fixtures/controller-request.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/controller-response.schema.json" \
  "$bundle/vm-lab/fixtures/controller-response.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/observation-adapter-registry.schema.json" \
  "$bundle/vm-lab/observation/adapter-registry.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/observation-broker-policy.schema.json" \
  "$bundle/vm-lab/observation/broker-policy.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/observation-request.schema.json" \
  "$bundle/vm-lab/fixtures/observation-request.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/observation-response.schema.json" \
  "$bundle/vm-lab/fixtures/observation-response.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/full-vm-blueprint.schema.json" \
  "$bundle/vm-lab/blueprints/fedora-workstation-full.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/readiness-plan.schema.json" \
  "$bundle/vm-lab/readiness/fedora-kvm-readiness-plan.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/provisioning-gates.schema.json" \
  "$bundle/vm-lab/blueprints/provisioning-gates.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/readiness-adapter-registry.schema.json" \
  "$bundle/vm-lab/readiness/adapter-registry.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/readiness-response.schema.json" \
  "$bundle/vm-lab/fixtures/readiness-response.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/schemas/host/direct-host-policy.schema.json" \
  "$bundle/deployment/host/policy.json" >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/schemas/host/recovery-set.schema.json" \
  "$bundle/deployment/host/recovery-set-plan.json" >/dev/null
python3 - "$bundle" <<'PY'
import importlib.util, json, pathlib, sys
root = pathlib.Path(sys.argv[1])
validator_path = root / "plugins/jarvis-system-admin/scripts/schema_validate.py"
spec = importlib.util.spec_from_file_location("schema_validate", validator_path)
validator = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(validator)
schema = json.loads((root / "plugins/jarvis-system-admin/schemas/action-definition.schema.json").read_text())
registry = json.loads((root / "plugins/jarvis-system-admin/registry/actions.json").read_text())
for action in registry["actions"]:
    errors = validator.validate(schema, action)
    assert not errors, f'{action.get("id")}: {errors}'
collector = json.loads((root / "plugins/jarvis-system-admin/registry/collector-plans/lighting-controls.json").read_text())
assert collector["execution_enabled"] is False
encoded = json.dumps(collector)
assert '"argv"' not in encoded and '"executable"' not in encoded
repair = next(item for item in registry["actions"] if item["id"] == "repair.lighting.execute")
assert repair["availability"] == "unavailable" and repair["implementation_status"] == "blocked"
PY
python3 "$bundle/scripts/verify-release-manifest.py"
python3 -m py_compile \
  "$bundle/plugins/jarvis-system-admin/scripts/jarvisctl.py" \
  "$bundle/plugins/jarvis-system-admin/scripts/hook_guard.py" \
  "$bundle/plugins/jarvis-system-admin/scripts/mcp_server.py" \
  "$bundle/plugins/jarvis-system-admin/scripts/knowledge_store.py" \
  "$bundle/plugins/jarvis-system-admin/scripts/collect_fedora_inventory.py" \
  "$bundle/plugins/jarvis-system-admin/scripts/index_local_docs.py" \
  "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/tui/src/jarvis_tui/__init__.py" \
  "$bundle/tui/src/jarvis_tui/__main__.py" \
  "$bundle/tui/src/jarvis_tui/actions.py" \
  "$bundle/tui/src/jarvis_tui/app.py" \
  "$bundle/tui/src/jarvis_tui/app_server.py" \
  "$bundle/tui/src/jarvis_tui/async_boundary.py" \
  "$bundle/tui/src/jarvis_tui/broker.py" \
  "$bundle/tui/src/jarvis_tui/conversation_manager.py" \
  "$bundle/tui/src/jarvis_tui/event_store.py" \
  "$bundle/tui/src/jarvis_tui/event_reducer.py" \
  "$bundle/tui/src/jarvis_tui/local_control.py" \
  "$bundle/tui/src/jarvis_tui/local_filesystem.py" \
  "$bundle/tui/src/jarvis_tui/models.py" \
  "$bundle/tui/src/jarvis_tui/presentation.py" \
  "$bundle/tui/src/jarvis_tui/preflight.py" \
  "$bundle/tui/src/jarvis_tui/session.py" \
  "$bundle/tui/src/jarvis_tui/testing.py" \
  "$bundle/tui/src/jarvis_tui/terminal_safety.py" \
  "$bundle/vm-lab/scripts/controller_contract.py" \
  "$bundle/vm-lab/scripts/observation_contract.py" \
  "$bundle/vm-lab/scripts/vm_blueprint_contract.py" \
  "$bundle/vm-lab/scripts/readiness_contract.py" \
  "$bundle/deployment/host/validate_policy.py" \
  "$bundle/deployment/host/validate_recovery_set.py" \
  "$bundle/deployment/host/diagnose_restored_tokens.py" \
  "$bundle/deployment/host/verify_restored_boundaries.py" \
  "$bundle/vm-lab/scripts/labctl.py" \
  "$bundle/vm-lab/tests/test_controller_contract.py" \
  "$bundle/vm-lab/tests/test_observation_contract.py" \
  "$bundle/vm-lab/tests/test_vm_blueprint_contract.py" \
  "$bundle/vm-lab/tests/test_readiness_contract.py" \
  "$bundle/tests/host/test_direct_host_policy.py" \
  "$bundle/tests/host/test_recovery_set.py" \
  "$bundle/tests/host/test_diagnose_restored_tokens.py" \
  "$bundle/tests/host/test_verify_restored_boundaries.py" \
  "$bundle/vm-lab/tests/test_vm_lab.py"

if rg -n 'TODO|PLACEHOLDER|Example script' "$bundle/codex/skills"; then
  echo "placeholder content remains" >&2
  exit 1
fi

python3 - "$bundle" <<'PY'
import json, pathlib, sys, tomllib
root = pathlib.Path(sys.argv[1])
for path in root.glob("**/*.json"):
    if "runtime" not in path.parts and "control-store" not in path.parts:
        json.loads(path.read_text())
for path in root.glob("codex/*.toml"):
    with path.open("rb") as handle:
        tomllib.load(handle)
PY

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
cd "$tmp"
python3 "$bundle/vm-lab/scripts/labctl.py" coverage > vm-lab-coverage.json
python3 "$bundle/plugins/jarvis-system-admin/scripts/schema_validate.py" \
  "$bundle/vm-lab/schemas/coverage-report.schema.json" \
  vm-lab-coverage.json >/dev/null
python3 "$bundle/plugins/jarvis-system-admin/scripts/collect_fedora_inventory.py" \
  --registry "$bundle/plugins/jarvis-system-admin/tests/fixtures/knowledge/collector.json" \
  --output inventory.json --fixture-mode >/dev/null
python3 - "$tmp/inventory.json" <<'PY'
import json, pathlib, sys
data = json.loads(pathlib.Path(sys.argv[1]).read_text())
assert data["collector"] == "fedora-readonly-inventory"
assert data["facts"][0]["value"] == "fixture-value"
assert len(data["attempts"]) == 1
PY
[ "$(stat -c '%a' inventory.json)" = 600 ]
python3 "$bundle/plugins/jarvis-system-admin/scripts/index_local_docs.py" \
  --output docs.jsonl --preview >/dev/null
printf '%s\n' '{"id":"test","status":"planned","schema_version":1}' > event.json
"$bundle/codex/skills/system-state/scripts/append-event.sh" event.json audit/events.jsonl
python3 -m json.tool event.json >/dev/null
[ "$(wc -l < audit/events.jsonl)" -eq 1 ]
[ "$(stat -c '%a' audit/events.jsonl)" = 600 ]

echo "bundle validation passed"
