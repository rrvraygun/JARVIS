"""Bounded sanitized operational transcripts, separate from Conversation and audit."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import private_records
from .observation_safety import timestamp
from .terminal_safety import sanitize_and_redact_terminal_text

ALLOWED_KINDS = {"user_message", "agent_message", "operation_result", "domain_evidence"}
MAX_ENTRIES = 128
MAX_CHARS = 32000
RETENTION_SECONDS = 7 * 24 * 60 * 60


def sanitized(value: Any, depth: int = 0) -> Any:
    if depth > 12:
        raise ValueError("transcript_depth_limit")
    if isinstance(value, str):
        return sanitize_and_redact_terminal_text(value, MAX_CHARS)[0]
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, list) and len(value) <= 200:
        return [sanitized(item, depth + 1) for item in value]
    if isinstance(value, dict) and len(value) <= 200:
        sensitive_keys = {
            "reasoning",
            "chainofthought",
            "environment",
            "env",
            "credentials",
            "credential",
            "cookies",
            "cookie",
            "privatekey",
            "token",
            "password",
            "passwd",
            "passphrase",
            "secret",
            "apikey",
            "authorization",
            "sessionid",
            "contraseña",
            "contrasena",
        }
        if any(
            not isinstance(key, str)
            or key.casefold().replace("_", "").replace("-", "").replace(" ", "") in sensitive_keys
            for key in value
        ):
            raise ValueError("transcript_field_not_permitted")
        return {
            sanitize_and_redact_terminal_text(key, 100)[0]: sanitized(item, depth + 1)
            for key, item in value.items()
        }
    raise ValueError("transcript_value_not_permitted")


def append(
    bundle: Path,
    kind: str,
    operation_id: str,
    payload: dict[str, Any],
    *,
    classification: str = "sanitized-operational",
) -> str:
    if kind not in ALLOWED_KINDS or classification != "sanitized-operational":
        raise ValueError("transcript_class_not_permitted")
    root = bundle / "runtime/transcripts"
    fd = private_records.directory(root)
    try:
        with os.scandir(fd) as entries:
            for count, _ in enumerate(entries, 1):
                if count >= MAX_ENTRIES:
                    raise ValueError("transcript_budget_requires_reviewed_rotation")
    finally:
        os.close(fd)
    safe = sanitized(payload)
    record = {
        "kind": kind,
        "operation_id": operation_id,
        "observed_at": timestamp(),
        "expires_at": time.time() + RETENTION_SECONDS,
        "payload": safe,
        "classification": classification,
    }
    identity = uuid4().hex
    private_records.write_once(root, identity + ".json", record, 65536)
    return identity


def read(bundle: Path, identity: str) -> dict[str, Any]:
    record = private_records.read(bundle / "runtime/transcripts", identity + ".json", 65536)
    if record["expires_at"] < time.time():
        return {
            "kind": record["kind"],
            "operation_id": record["operation_id"],
            "status": "expired",
            "content_digest": hashlib.sha256(str(record["payload"]).encode()).hexdigest(),
        }
    return record
