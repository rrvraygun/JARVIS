#!/usr/bin/env python3
"""Delegate to the Jarvis knowledge store without changing the host."""

from pathlib import Path
import runpy

TARGET = Path(__file__).resolve().parents[4] / "plugins/jarvis-system-admin/scripts/knowledge_store.py"
runpy.run_path(str(TARGET), run_name="__main__")
