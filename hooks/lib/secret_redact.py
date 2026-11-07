"""Secret redaction for text that hooks store locally (prompts, snippets).

Hooks cannot import ``scripts/jev_redact.py`` (hooks/lib must stay
self-contained), and ``hook_utils._redact_secrets`` only covers
``key=value`` and ``Bearer`` shapes, which misses vendor keys, JWTs and PEM
blocks pasted into a prompt. The patterns here are ported from
``scripts/jev_redact.py``; keep the two lists in step.

Replacement format: ``<redacted:TYPE:last4>`` when the matched value is at
least 12 characters, otherwise ``<redacted:TYPE>``. Stdlib only, and the
regexes compile on first use so importing this module costs nothing.
"""

from __future__ import annotations

import re

LAST4_MIN_LEN = 12

_SENSITIVE_KEY = r"(?:secret|token|passw|api[_-]?key|private|credential|auth)"
_VALUE_CHARS = r"[A-Za-z0-9._~+/=\-]"
# Key-name characters around the sensitive word, bounded: an unbounded run made
# the kv and entropy patterns quadratic on long dotted or dashed tokens (12 KB
# took ~10 s, past the hook timeout). The url-cred scheme is bounded the same
# way. jev_redact.py still uses ``*`` in both places.
_KEY_CHARS = r"[A-Za-z0-9_.-]{0,64}"

_PATTERNS: list[tuple[str, re.Pattern[str], int]] | None = None


def _patterns() -> list[tuple[str, re.Pattern[str], int]]:
    """(type, regex, group holding the secret). Whole blocks and headers first, then vendors, then generic."""
    global _PATTERNS
    if _PATTERNS is None:
        _PATTERNS = [
            (
                "pem",
                re.compile(
                    r"(-----BEGIN [A-Z ]*"
                    + "PRIVATE "
                    + r"KEY-----[\s\S]*?-----END [A-Z ]*"
                    + "PRIVATE "
                    + r"KEY-----)"
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
            ("jwt", re.compile(r"\b(eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})"), 1),
            ("aws-key", re.compile(r"\b((?:AKIA|ASIA)[0-9A-Z]{16})\b"), 1),
            ("github", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,})\b"), 1),
            ("slack", re.compile(r"\b(xox[abp]-[A-Za-z0-9-]{10,})\b"), 1),
            ("gitlab", re.compile(r"\b(glpat-[A-Za-z0-9_-]{20,})"), 1),
            ("npm", re.compile(r"\b(npm_[A-Za-z0-9]{30,})\b"), 1),
            ("huggingface", re.compile(r"\b(hf_[A-Za-z0-9]{30,})\b"), 1),
            ("vercel", re.compile(r"\b(vck_[A-Za-z0-9_-]{20,})"), 1),
            ("docker", re.compile(r"\b(dckr_pat_[A-Za-z0-9_-]{20,})"), 1),
            ("google", re.compile(r"\b(AIza[0-9A-Za-z_-]{35})\b"), 1),
            ("stripe", re.compile(r"\b(sk_(?:live|test)_[A-Za-z0-9]{8,})\b"), 1),
            ("openai", re.compile(r"\b(sk-[A-Za-z0-9_-]{20,})\b"), 1),
            ("url-cred", re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]{0,31}://[^\s/:@]+:([^\s/@]+)@"), 1),
            (
                "kv",
                re.compile(
                    r"(?i)[\"']?\b(?:"
                    + _KEY_CHARS
                    + _SENSITIVE_KEY
                    + _KEY_CHARS
                    + r")[\"']?\s*[:=]\s*[\"']?("
                    + _VALUE_CHARS
                    + r"{8,})"
                ),
                1,
            ),
            (
                "entropy",
                re.compile(
                    r"(?i)\b"
                    + _KEY_CHARS
                    + _SENSITIVE_KEY
                    + _KEY_CHARS
                    + r"\W{1,6}((?:[A-Za-z0-9+/=_-]{32,}|[0-9a-f]{32,}))"
                ),
                1,
            ),
        ]
    return _PATTERNS


def _placeholder(kind: str, value: str) -> str:
    if len(value) >= LAST4_MIN_LEN:
        return f"<redacted:{kind}:{value[-4:]}>"
    return f"<redacted:{kind}>"


def redact_text(text: str) -> str:
    """Return ``text`` with every secret-shaped value replaced by a placeholder.

    Non-strings and empty strings are returned unchanged.
    """
    if not isinstance(text, str) or not text:
        return text

    for kind, pattern, group in _patterns():

        def _sub(m: re.Match[str], kind: str = kind, group: int = group) -> str:
            head = m.string[m.start() : m.start(group)]
            tail = m.string[m.end(group) : m.end()]
            return head + _placeholder(kind, m.group(group)) + tail

        text = pattern.sub(_sub, text)
    return text
