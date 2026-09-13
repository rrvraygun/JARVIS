#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


sys.path.insert(0, str(ROOT.parent.parent / "tui/src"))
from jarvis_tui.specialists import load_specialists
from jarvis_tui.tool_scope import publish, revoke

scope_id = uuid4().hex
specialist = next(
    s for s in load_specialists(ROOT.parent.parent) if s.id == "jarvis-system-architect"
)
publish(ROOT.parent.parent, specialist, "mcp-protocol-fixture", scope_id)
with tempfile.TemporaryDirectory() as directory:
    environment = dict(os.environ)
    environment["JARVIS_STORE"] = directory
    server = subprocess.Popen(
        ["python3", str(ROOT / "scripts/mcp_server.py"), "--scope-id", scope_id],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=environment,
    )
    assert server.stdin and server.stdout
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2025-06-18"},
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "knowledge_status", "arguments": {}},
        },
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "list_actions", "arguments": {"capability": "health"}},
        },
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "get_action",
                "arguments": {"action_id": "health.lighting.diagnose"},
            },
        },
    ]
    for request in requests:
        server.stdin.write(json.dumps(request) + "\n")
        server.stdin.flush()
    responses = [json.loads(server.stdout.readline()) for _ in requests]
    server.stdin.close()
    assert server.wait(timeout=5) == 0
    server.stdout.close()
    if server.stderr:
        server.stderr.close()

    assert responses[0]["result"]["serverInfo"]["version"] == "0.2.0"
    names = {tool["name"] for tool in responses[1]["result"]["tools"]}
    assert {
        "list_actions",
        "get_action",
        "query_knowledge",
        "revise_error",
        "power_inventory",
        "inspect_power_inventory",
        "power_telemetry",
        "inspect_power_telemetry",
        "health_inventory",
        "health_telemetry",
        "health_processes",
        "health_services",
        "health_storage",
        "health_logs",
        "development_toolchains",
        "development_project_inspect",
        "network_inventory",
        "security_inventory",
        "recovery_inventory",
        "package_catalog",
        "package_search",
        "inspect_packages",
    } <= names
    assert not ({"shell", "bash", "sudo", "execute"} & names)
    status = json.loads(responses[2]["result"]["content"][0]["text"])
    assert status["valid"]
    actions = json.loads(responses[3]["result"]["content"][0]["text"])["actions"]
    assert actions and {item["capability"] for item in actions} == {"health"}
    lighting = json.loads(responses[4]["result"]["content"][0]["text"])["action"]
    assert lighting["procedure"] == "health.lighting-diagnose@1.0.0"
    assert lighting["mutates_host"] is False

assert "activate_lesson" not in names
revoke(ROOT.parent.parent, scope_id)
print("mcp-server tests passed")
