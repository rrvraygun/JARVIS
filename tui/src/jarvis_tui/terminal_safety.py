"""Neutralize untrusted terminal output before rendering."""

from __future__ import annotations

import re

OSC = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
CSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ESCAPE = re.compile(r"\x1b[ -/]*[@-~]")
C1_OSC = re.compile(r"\x9d[^\x07\x9c]*(?:\x07|\x9c)")
C1_CSI = re.compile(r"\x9b[0-?]*[ -/]*[@-~]")
BIDI = re.compile("[\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]")
SENSITIVE_VALUE = re.compile(
    r"(?i)(?P<prefix>\bauthorization\s*:\s*bearer\s+)(?P<bearer>[^\s,;]+)"
    r"|(?P<label>\b(?:password|passwd|passphrase|token|secret|api[_-]?key|"
    r"credential|private[_-]?key|cookie|session[_-]?id|contraseña|contrasena)\b[\"\']?\s*[:=]\s*)"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN (?:[A-Z0-9]+ )?PRIVATE KEY-----.*?"
    r"(?:-----END (?:[A-Z0-9]+ )?PRIVATE KEY-----|\Z)",
    re.DOTALL,
)
KNOWN_CREDENTIAL_VALUE = re.compile(
    r"(?<![A-Za-z0-9])(?:AKIA[0-9A-Z]{16}|"
    r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,}|"
    r"github_pat_[A-Za-z0-9_]{30,}|"
    r"sk-[A-Za-z0-9_-]{20,}|"
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})"
)


def sanitize_terminal_text(value: str, limit: int = 262_144) -> tuple[str, bool]:
    """Return display-safe text and whether the original was truncated."""
    truncated = len(value) > limit
    text = value[:limit]
    text = OSC.sub("[terminal-control]", text)
    text = CSI.sub("[terminal-control]", text)
    text = ESCAPE.sub("[terminal-control]", text)
    text = C1_OSC.sub("[terminal-control]", text)
    text = C1_CSI.sub("[terminal-control]", text)
    text = BIDI.sub("[direction-control]", text)
    text = "".join(
        character
        for character in text
        if character in "\n\t" or (ord(character) >= 32 and not 127 <= ord(character) <= 159)
    )
    if truncated:
        text += "\n[output truncated for display]"
    return text, truncated


def redact_sensitive_values(value: str) -> tuple[str, bool]:
    """Redact credential-shaped values without retaining the matched secret."""

    changed = False

    def replacement(match: re.Match[str]) -> str:
        nonlocal changed
        changed = True
        if match.group("prefix") is not None:
            return f"{match.group('prefix')}[redacted]"
        return f"{match.group('label')}[redacted]"

    value = re.sub(r"(?i)(https?://)[^/\s:@]+:[^/\s@]+@", r"\1[credentials-redacted]@", value)
    redacted = PRIVATE_KEY_BLOCK.sub("[private-key-redacted]", value)
    if redacted != value:
        changed = True
    known_redacted = KNOWN_CREDENTIAL_VALUE.sub("[credential-like-value-redacted]", redacted)
    if known_redacted != redacted:
        changed = True
    return SENSITIVE_VALUE.sub(replacement, known_redacted), changed


def sanitize_and_redact_terminal_text(value: str, limit: int = 262_144) -> tuple[str, bool]:
    """Apply credential redaction and terminal neutralization before display."""

    redacted, redaction_changed = redact_sensitive_values(value)
    safe, terminal_changed = sanitize_terminal_text(redacted, limit=limit)
    return safe, redaction_changed or terminal_changed or safe != redacted
