#!/usr/bin/env python3
"""Single redaction library for anything that leaves this host to the Jev API.

Owner rule: nothing goes to api.typesafe.ai with a secret in it. Every Jev
caller runs its payload through :func:`redact_payload` (``jev_router_common.call_jev``
does this unconditionally), and hooks run :func:`redact_text` locally before
deciding whether to call Jev at all.

Patterns started from ``hooks/lib/hook_utils.py`` ``_secrets_pattern()`` /
``_redact_secrets()`` (``Bearer``, ``token=``, ``key=``, ``password=``,
``secret=``). That module lives under ``hooks/lib`` and is not importable from
``scripts/``, so the patterns are ported here and extended. Stdlib only.

Replacement format: ``<redacted:TYPE:last4>`` when the matched value is at
least 12 characters, otherwise ``<redacted:TYPE>``. The last four characters
let a human confirm which credential fired without exposing it.

Usage:
    python3 scripts/jev_redact.py < text   # prints redacted text, types to stderr
"""

from __future__ import annotations

import copy
import re
import sys
from pathlib import PurePath
from typing import Any

LAST4_MIN_LEN = 12

# Key names that mark the following value as sensitive (KEY=VALUE / "key": "value").
_SENSITIVE_KEY = r"(?:secret|token|passw|api[_-]?key|private|credential|auth)"
_VALUE_CHARS = r"[A-Za-z0-9._~+/=\-]"

# (type, compiled regex, group index holding the secret value)
# Order matters: whole-block and header patterns first, then vendor formats,
# then generic key/value, then bare high-entropy strings next to a key name.
_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    (
        "pem",
        re.compile(
            r"(-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----)",  # security-review: ignore - detection regex, not a credential
        ),
        1,
    ),
    ("cookie", re.compile(r"(?i)\b(?:Set-Cookie|Cookie)\s*[:=]\s*([^\r\n]+)"), 1),
    ("bearer", re.compile(r"(?i)\bBearer\s+(" + _VALUE_CHARS + r"{8,})"), 1),
    (
        "authorization",
        re.compile(r"(?i)\bAuthorization\s*[:=]\s*[\"']?(?:Basic\s+)?(" + _VALUE_CHARS + r"{8,})"),
        1,
    ),
    (
        "jwt",
        re.compile(r"\b(eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})"),
        1,
    ),
    ("aws-key", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"), 1),
    ("github", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b"), 1),
    ("slack", re.compile(r"\b(xox[abp]-[A-Za-z0-9-]{10,})\b"), 1),
    ("google", re.compile(r"\b(AIza[0-9A-Za-z_-]{35})\b"), 1),
    ("stripe", re.compile(r"\b(sk_(?:live|test)_[A-Za-z0-9]{8,})\b"), 1),
    ("openai", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"), 1),
    (
        "url-cred",
        re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s/:@]+:([^\s/@]+)@"),
        1,
    ),
    (
        "kv",
        re.compile(
            r"(?i)[\"']?\b(?:[A-Za-z0-9_.-]*"
            + _SENSITIVE_KEY
            + r"[A-Za-z0-9_.-]*)[\"']?\s*[:=]\s*[\"']?("
            + _VALUE_CHARS
            + r"{8,})"
        ),
        1,
    ),
    (
        "entropy",
        re.compile(
            r"(?i)\b[A-Za-z0-9_.-]*"
            + _SENSITIVE_KEY
            + r"[A-Za-z0-9_.-]*\W{1,6}((?:[A-Za-z0-9+/=_-]{32,}|[0-9a-f]{32,}))"
        ),
        1,
    ),
]

_PROTECTED_NAMES = frozenset({".env", "token.json", ".tokens", "keyring"})
_PROTECTED_DIRS = frozenset({".ssh", ".gnupg", ".aws", ".config", "secrets", "keyring"})
_PROTECTED_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx"})


def _placeholder(kind: str, value: str) -> str:
    if len(value) >= LAST4_MIN_LEN:
        return f"<redacted:{kind}:{value[-4:]}>"
    return f"<redacted:{kind}>"


def redact_text(text: str) -> tuple[str, list[str]]:
    """Redact secrets in ``text``.

    Args:
        text: Any string. Non-strings are returned unchanged with no types.

    Returns:
        ``(redacted_text, types)`` where ``types`` lists one entry per redacted
        value (duplicates kept so ``len(types)`` is the count).
    """
    if not isinstance(text, str) or not text:
        return text, []

    found: list[str] = []

    for kind, pattern, group in _PATTERNS:

        def _sub(m: re.Match[str], kind: str = kind, group: int = group) -> str:
            value = m.group(group)
            found.append(kind)
            head = m.string[m.start() : m.start(group)]
            tail = m.string[m.end(group) : m.end()]
            return head + _placeholder(kind, value) + tail

        text = pattern.sub(_sub, text)

    return text, found


def _walk(node: Any, counter: list[int]) -> Any:
    if isinstance(node, str):
        out, types = redact_text(node)
        counter[0] += len(types)
        return out
    if isinstance(node, dict):
        return {k: _walk(v, counter) for k, v in node.items()}
    if isinstance(node, list):
        return [_walk(v, counter) for v in node]
    return node


def redact_payload(payload: dict) -> tuple[dict, int]:
    """Deep-copy ``payload`` and redact secrets from the parts that carry request text.

    Walks ``payload["state"]`` (str, dict, list, recursively) and the
    ``instructions`` / ``criteria`` strings of each entry in
    ``payload["questions"]``.

    Returns:
        ``(redacted_payload, count)`` with ``count`` the number of values redacted.
    """
    out = copy.deepcopy(payload)
    counter = [0]
    if "state" in out:
        out["state"] = _walk(out["state"], counter)
    questions = out.get("questions")
    if isinstance(questions, dict):
        question_values = questions.values()
    elif isinstance(questions, list):
        question_values = questions
    else:
        question_values = ()
    for q in question_values:
        if not isinstance(q, dict):
            continue
        for field in ("instructions", "criteria"):
            if field in q:
                q[field] = _walk(q[field], counter)
    return out, counter[0]


def is_protected_path(path: str | PurePath) -> bool:
    """Return True when ``path`` names a credential/secret file or lives under a secret directory."""
    p = PurePath(str(path))
    name = p.name
    parts = set(p.parts[:-1])
    if parts & _PROTECTED_DIRS:
        return True
    if name in _PROTECTED_NAMES:
        return True
    if name.startswith(".env"):
        return True
    if p.suffix.lower() in _PROTECTED_SUFFIXES:
        return True
    if name.startswith("id_"):
        return True
    if name.startswith("credentials"):
        return True
    return bool(name.startswith("service-account") and name.endswith(".json"))


def main() -> int:
    text = sys.stdin.read()
    out, types = redact_text(text)
    sys.stdout.write(out)
    if types:
        print(f"[jev-redact] {len(types)} value(s) redacted: {sorted(set(types))}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
