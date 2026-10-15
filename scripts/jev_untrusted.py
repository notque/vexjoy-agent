#!/usr/bin/env python3
"""Helpers that keep untrusted page text from steering a model.

``flat`` turns any page-supplied value into one capped line, so a label or
title cannot forge a new line in an element table or prompt. ``fence`` wraps a
block of page data in marker tags after redacting secrets and removing any
copy of the marker the page itself planted.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_redact

TAG = "untrusted-page-data"
_TAG_RE = re.compile(r"<\s*/?\s*" + re.escape(TAG), re.IGNORECASE)


def flat(value: object, limit: int) -> str:
    """Return ``value`` as one printable line of at most ``limit`` characters."""
    text = "" if value is None else str(value)
    text = "".join(ch if ch.isprintable() else " " for ch in text)
    return " ".join(text.split())[:limit]


def fence(text: object, limit: int) -> str:
    """Wrap page data in marker tags: redacted, marker-free, capped to ``limit``."""
    body = jev_redact.redact_text("" if text is None else str(text))[0]
    body = _TAG_RE.sub("[marker removed]", body)[:limit]
    return f"<{TAG}>\n{body}\n</{TAG}>"
