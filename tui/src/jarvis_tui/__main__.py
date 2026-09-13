"""Jarvis TUI entry point."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis terminal interface")
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=Path(__file__).resolve().parents[3],
        help="Codex agent-system bundle root",
    )
    parser.add_argument(
        "--connect-app-server",
        action="store_true",
        help="connect to the local Codex App Server and read ChatGPT auth/capacity state",
    )
    parser.add_argument(
        "--enable-live-turns",
        action="store_true",
        help="allow typed-preflight, risk-governed execution turns (requires --connect-app-server)",
    )
    parser.add_argument(
        "--connect-jarvisd",
        action="store_true",
        help="read jarvisd health and H1 status over the owner-only socket (no observation or mutation)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="use semantic text labels without relying on color styling",
    )
    args = parser.parse_args()
    if args.enable_live_turns and not args.connect_app_server:
        parser.error("--enable-live-turns requires --connect-app-server")
    try:
        from .app import JarvisTui
    except ModuleNotFoundError as exc:
        if exc.name == "textual":
            parser.error(
                "Textual is not installed; install the reviewed tui project dependencies first"
            )
        raise
    JarvisTui(
        args.bundle_root,
        connect_app_server=args.connect_app_server,
        enable_live_turns=args.enable_live_turns,
        connect_jarvisd=args.connect_jarvisd,
        plain_mode=args.plain,
    ).run()


if __name__ == "__main__":
    main()
