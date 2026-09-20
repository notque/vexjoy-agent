"""Selectable Jev transport for /d.

``JEV_TRANSPORT`` accepts ``auto`` (default), ``vercel``, or ``direct``.
Auto selects TypeSafe's direct Jev API when its key is configured; otherwise
it selects Vercel AI Gateway. A failed selected transport is not retried
through the other provider.
"""

from __future__ import annotations

import os
import time
from typing import Any

import jev_router_common
import jev_vercel

try:
    from dotenv import load_dotenv
except ImportError:  # install.sh installs python-dotenv; exported vars still work without it.
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(os.path.expanduser("~/.env"), override=False)

VERCEL = "vercel-ai-gateway"
DIRECT = "typesafe-jev-api"
_ALIASES = {
    "auto": "auto",
    "vercel": VERCEL,
    "gateway": VERCEL,
    VERCEL: VERCEL,
    "direct": DIRECT,
    "jev": DIRECT,
    "jev-api": DIRECT,
    DIRECT: DIRECT,
}


class JevTransportError(RuntimeError):
    """A selected Jev transport failed with a safe optional receipt."""

    def __init__(self, message: str, *, source: str, telemetry: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.source = source
        self.telemetry = telemetry


def select() -> tuple[str | None, str]:
    """Return the configured available transport and a safe explanation."""
    raw = os.environ.get("JEV_TRANSPORT", "auto").strip().lower() or "auto"
    requested = _ALIASES.get(raw)
    if requested is None:
        return None, f"invalid JEV_TRANSPORT={raw!r}; use auto, vercel, or direct"
    has_vercel = bool(os.environ.get("AI_GATEWAY_API_KEY", "").strip())
    has_direct = bool(os.environ.get("TYPESAFE_API_KEY", "").strip())
    if requested == VERCEL:
        return (
            (VERCEL, "AI_GATEWAY_API_KEY set")
            if has_vercel
            else (None, "JEV_TRANSPORT=vercel but AI_GATEWAY_API_KEY is unset")
        )
    if requested == DIRECT:
        return (
            (DIRECT, "TYPESAFE_API_KEY set")
            if has_direct
            else (None, "JEV_TRANSPORT=direct but TYPESAFE_API_KEY is unset")
        )
    if has_direct:
        return DIRECT, "auto selected TYPESAFE_API_KEY"
    if has_vercel:
        return VERCEL, "auto selected AI_GATEWAY_API_KEY"
    return None, "neither AI_GATEWAY_API_KEY nor TYPESAFE_API_KEY is set"


def available() -> tuple[bool, str]:
    transport, reason = select()
    return transport is not None, reason


def evaluate(state: Any, questions: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    """Evaluate one state through the selected Jev transport."""
    transport, reason = select()
    if transport is None:
        raise JevTransportError(reason, source="unavailable")
    if transport == VERCEL:
        try:
            return jev_vercel.evaluate(state, questions, timeout=timeout)
        except jev_vercel.JevGatewayError as exc:
            raise JevTransportError(str(exc), source=VERCEL, telemetry=exc.telemetry) from exc

    started = time.monotonic()
    payload = {"state": state, "model": jev_router_common.JEV_MODEL, "questions": questions}
    try:
        data, _ = jev_router_common.call_jev(
            payload,
            os.environ["TYPESAFE_API_KEY"],
            timeout,
            script_name="jev_transport.py",
        )
    except Exception as exc:
        telemetry = {
            "attempts": None,
            "retries": None,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        }
        raise JevTransportError(str(exc)[:300], source=DIRECT, telemetry=telemetry) from exc
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
        data["_meta"] = meta
    meta["transport"] = DIRECT
    data.setdefault("model", jev_router_common.JEV_MODEL)
    return data
