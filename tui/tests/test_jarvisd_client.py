from __future__ import annotations

import json
from pathlib import Path
import socket
import threading
import tempfile
import unittest
import sys

TUI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TUI_ROOT / "src"))

from jarvis_tui.jarvisd_client import JarvisdClientError, JarvisdStatusClient  # noqa: E402


class JarvisdClientTests(unittest.TestCase):
    def test_reads_only_health_and_activation_projection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            socket_path = parent / "jarvisd.sock"
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                server.bind(str(socket_path))
            except Exception:
                server.close()
                raise
            socket_path.chmod(0o600)
            server.listen(2)
            requests: list[str] = []

            def serve() -> None:
                try:
                    for _ in range(2):
                        client, _ = server.accept()
                        with client:
                            line = client.recv(4096).split(b"\n", 1)[0]
                            request = json.loads(line.decode())
                            requests.append(request["method"])
                            if request["method"] == "health.read":
                                response = {
                                    "schema_version": 1,
                                    "request_id": request["request_id"],
                                    "status": "ok",
                                    "service": "jarvisd-user-service-v1",
                                }
                            else:
                                response = {
                                    "schema_version": 1,
                                    "request_id": request["request_id"],
                                    "status": "ok",
                                    "activation": {
                                        "controller_host_observation_enabled": True,
                                        "broker_host_observation_enabled": True,
                                        "live_observation_performed": False,
                                        "service_uid": __import__("os").getuid(),
                                    },
                                }
                            client.sendall((json.dumps(response) + "\n").encode())
                finally:
                    server.close()

            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            status = JarvisdStatusClient(socket_path).read_status()
            thread.join(timeout=2)
            self.assertEqual(requests, ["health.read", "activation.status"])
            self.assertEqual(status.host_authority, "H1 Tier-0 read-only enabled")
            self.assertFalse(status.live_observation_performed)

    def test_unavailable_socket_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(JarvisdClientError):
                JarvisdStatusClient(Path(directory) / "missing.sock").read_status()


if __name__ == "__main__":
    unittest.main()
