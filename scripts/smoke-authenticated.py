#!/usr/bin/env python3
"""Check existing authentication in a separate App Server, without a model turn.

Only the installed Codex process accesses its usual authentication. This script
does not read credentials, start login, refresh tokens, create a thread, or
grant a tool request. Output deliberately excludes identity and raw errors.
"""

# ruff: noqa: E402
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tui/src"))
from jarvis_tui.app_server import StdioAppServerClient


async def probe(client: Any) -> dict[str, Any]:
    """Return a fixed, non-identifying result; never print an RPC payload."""
    try:
        async with asyncio.timeout(30):
            await client.start()
            result = await client.request("account/read", {"refreshToken": False})
            account = result.get("account") if isinstance(result, dict) else None
            authenticated = isinstance(account, dict) and account.get("type") in {
                "chatgpt",
                "apiKey",
                "apikey",
            }
            return {
                "status": "account_available" if authenticated else "login_required",
                "account_available": authenticated,
                "authenticated_turn_verified": False,
                "tool_calls": 0,
                "scope": "authenticated_connection_only",
            }
    except Exception as error:
        # Provider exceptions can contain identifying data or credentials.
        return {
            "status": "account_probe_failed",
            "authenticated_turn_verified": False,
            "error_type": type(error).__name__,
        }
    finally:
        await client.stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve-account-probe", action="store_true", required=True)
    parser.add_argument("--codex-bin", default="codex")
    args = parser.parse_args()
    result = asyncio.run(probe(StdioAppServerClient(codex_bin=args.codex_bin, request_timeout=20)))
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "account_available" else 1


if __name__ == "__main__":
    raise SystemExit(main())
