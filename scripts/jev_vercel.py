"""Python client for the repository's Vercel AI Gateway Jev bridge.

The bridge is intentionally the only process that receives ``AI_GATEWAY_API_KEY``.
This module owns bounded transport retries so every Python Jev caller has the same
failure behavior and receipt format.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import jev_redact

_BRIDGE = Path(__file__).with_name("jev_gateway") / "jev_vercel_gateway.mjs"

# A gateway availability blip should not turn into a false UI failure.  Keep
# retries short and bounded: callers may issue many evidence packs in parallel.
DEFAULT_MAX_ATTEMPTS = 3

# The bridge needs the gateway credential and a small set of process/network
# settings. Do not expose unrelated exported credentials to its npm dependency
# tree. In particular, NODE_OPTIONS is intentionally excluded because it can
# cause Node to load arbitrary code before the bridge starts.
_BRIDGE_ENV_KEYS = (
    "AI_GATEWAY_API_KEY",
    "PATH",
    "LANG",
    "LC_ALL",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
)


def _bridge_env() -> dict[str, str]:
    """Return the minimum environment required by the gateway bridge."""
    return {key: os.environ[key] for key in _BRIDGE_ENV_KEYS if key in os.environ}


def available() -> tuple[bool, str]:
    """Return whether this process can call Jev through Vercel AI Gateway."""
    return (
        (True, "AI_GATEWAY_API_KEY set")
        if os.environ.get("AI_GATEWAY_API_KEY", "").strip()
        else (False, "AI_GATEWAY_API_KEY unset")
    )


RETRY_BASE_SECONDS = 0.25
RETRY_MAX_SECONDS = 2.0
RETRY_AFTER_MAX_SECONDS = 5.0
TRANSIENT_STATUSES = frozenset({429, 503, 529})


class JevGatewayError(RuntimeError):
    """The Vercel gateway could not produce a valid Jev response.

    ``telemetry`` is safe to persist with an audit receipt: it contains only
    attempt counts, status/retry information, and truncated transport errors;
    it never contains the submitted state or questions.
    """

    def __init__(self, message: str, *, telemetry: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.telemetry = telemetry or _telemetry(attempts=0, receipts=[], final_error=message[:300])


def _bridge_error(stderr: str) -> dict[str, Any]:
    """Decode the bridge's safe, structured error receipt when present."""
    prefix = "Jev Vercel gateway error: "
    line = (stderr.strip().splitlines()[-1:] or [""])[0]
    detail = line[len(prefix) :] if line.startswith(prefix) else line
    try:
        parsed = json.loads(detail)
    except json.JSONDecodeError:
        return {"message": detail[:300] or "unknown bridge failure"}
    if not isinstance(parsed, dict):
        return {"message": "unknown bridge failure"}
    message = parsed.get("message")
    status = parsed.get("status")
    retry_after = parsed.get("retry_after_seconds")
    return {
        "message": str(message)[:300] if isinstance(message, str) else "unknown bridge failure",
        **({"status": status} if isinstance(status, int) else {}),
        **({"retry_after_seconds": retry_after} if isinstance(retry_after, (int, float)) and retry_after >= 0 else {}),
        **({"kind": parsed["kind"]} if isinstance(parsed.get("kind"), str) else {}),
    }


def _retry_delay(attempt: int, receipt: dict[str, Any]) -> float:
    """Return the bounded delay before retry number ``attempt + 1``."""
    retry_after = receipt.get("retry_after_seconds")
    if isinstance(retry_after, (int, float)) and retry_after >= 0:
        return min(float(retry_after), RETRY_AFTER_MAX_SECONDS)
    return min(RETRY_BASE_SECONDS * (2 ** (attempt - 1)), RETRY_MAX_SECONDS)


def _retryable(receipt: dict[str, Any]) -> bool:
    """Retry only documented transient Vercel statuses and timeouts."""
    if receipt.get("timeout") is True or receipt.get("kind") == "timeout":
        return True
    return receipt.get("status") in TRANSIENT_STATUSES


def _telemetry(*, attempts: int, receipts: list[dict[str, Any]], final_error: str | None) -> dict[str, Any]:
    retries = max(0, attempts - 1)
    return {
        "attempts": attempts,
        "retries": retries,
        "error": final_error,
        "attempt_receipts": receipts,
    }


def _with_telemetry(result: dict[str, Any], telemetry: dict[str, Any]) -> dict[str, Any]:
    """Add transport telemetry without replacing bridge-provided metadata."""
    meta = result.get("_meta")
    if not isinstance(meta, dict):
        meta = {}
        result["_meta"] = meta
    meta["retry"] = telemetry
    return result


def evaluate(
    state: dict[str, Any],
    questions: dict[str, Any],
    *,
    timeout: float,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    sleeper: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Evaluate Jev state/questions through the Vercel gateway bridge.

    Each attempt gets the caller's process timeout. Only 429, 503, 529, and a
    subprocess timeout are retried. Authentication, billing, malformed payload,
    schema, and response errors are one-shot so retries cannot hide configuration
    defects or multiply a permanently invalid request.
    """
    if not _BRIDGE.is_file():
        message = "Vercel gateway bridge is unavailable"
        raise JevGatewayError(message, telemetry=_telemetry(attempts=0, receipts=[], final_error=message))
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    safe_payload, n_redacted = jev_redact.redact_payload({"state": state, "questions": questions})
    if n_redacted:
        print(f"[jev-redact] {n_redacted} value(s) redacted before Vercel send", file=__import__("sys").stderr)
    payload = json.dumps(safe_payload, separators=(",", ":"))
    receipts: list[dict[str, Any]] = []
    for attempt in range(1, max_attempts + 1):
        started = time.monotonic()
        try:
            completed = subprocess.run(
                ["node", str(_BRIDGE)],
                input=payload,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
                env=_bridge_env(),
            )
        except FileNotFoundError as exc:
            message = "node is unavailable for the Vercel gateway bridge"
            raise JevGatewayError(
                message,
                telemetry=_telemetry(
                    attempts=attempt,
                    receipts=[
                        *receipts,
                        {
                            "attempt": attempt,
                            "error": message,
                            "duration_ms": round((time.monotonic() - started) * 1000, 2),
                        },
                    ],
                    final_error=message,
                ),
            ) from exc
        except subprocess.TimeoutExpired:
            receipt: dict[str, Any] = {
                "attempt": attempt,
                "timeout": True,
                "error": "Vercel gateway bridge timed out",
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
            }
        else:
            if completed.returncode:
                detail = _bridge_error(completed.stderr)
                receipt = {
                    "attempt": attempt,
                    "error": detail["message"],
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                    **({"status": detail["status"]} if "status" in detail else {}),
                    **({"kind": detail["kind"]} if "kind" in detail else {}),
                    **(
                        {"retry_after_seconds": detail["retry_after_seconds"]}
                        if "retry_after_seconds" in detail
                        else {}
                    ),
                }
            else:
                try:
                    result = json.loads(completed.stdout)
                except json.JSONDecodeError as exc:
                    message = "Vercel gateway bridge returned invalid JSON"
                    raise JevGatewayError(
                        message,
                        telemetry=_telemetry(
                            attempts=attempt,
                            receipts=[
                                *receipts,
                                {
                                    "attempt": attempt,
                                    "error": message,
                                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                                },
                            ],
                            final_error=message,
                        ),
                    ) from exc
                if not isinstance(result, dict) or not isinstance(result.get("answers"), dict):
                    message = "Vercel gateway bridge returned an invalid Jev response"
                    raise JevGatewayError(
                        message,
                        telemetry=_telemetry(
                            attempts=attempt,
                            receipts=[
                                *receipts,
                                {
                                    "attempt": attempt,
                                    "error": message,
                                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                                },
                            ],
                            final_error=message,
                        ),
                    )
                receipts.append(
                    {"attempt": attempt, "duration_ms": round((time.monotonic() - started) * 1000, 2), "error": None}
                )
                return _with_telemetry(result, _telemetry(attempts=attempt, receipts=receipts, final_error=None))

        receipts.append(receipt)
        if not _retryable(receipt) or attempt == max_attempts:
            message = str(receipt["error"])
            raise JevGatewayError(
                message,
                telemetry=_telemetry(attempts=attempt, receipts=receipts, final_error=message),
            )
        delay = _retry_delay(attempt, receipt)
        receipt["retry_delay_seconds"] = delay
        sleeper(delay)

    raise AssertionError("unreachable")
