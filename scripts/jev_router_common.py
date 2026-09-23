#!/usr/bin/env python3
"""Shared Jev client: presence check, redaction, cache, breaker, and call log.

The presence check answers one question: can `jev-route.py` legitimately call the live Jev
endpoint right now? Two independent conditions must both hold — the API key
is present in the environment, and the typesafe plugin is enabled in the
merged Claude Code settings. Neither condition substitutes for the other: a
present key with the plugin disabled is not available, and an enabled plugin
with no key is not available either.

Underscore filename: importable by name, the same convention
`routing_index_merge.py` uses among the hyphen-named routing scripts (which
run as files, not as a package, and shell out to each other instead).
`jev-route.py` imports this module directly.

Usage:
    python3 scripts/jev_router_common.py --check
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_limits
import jev_redact

_HOOKS_LIB = _SCRIPTS_DIR.parent / "hooks" / "lib"
if str(_HOOKS_LIB) not in sys.path:
    sys.path.insert(0, str(_HOOKS_LIB))
try:
    from learning_db_v2 import record_jev_call as _record_jev_call
except Exception:  # pragma: no cover - telemetry is optional
    _record_jev_call = None


def _caller_script() -> str:
    return Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "unknown"


# ---------------------------------------------------------------------------
# Payload hashing
# ---------------------------------------------------------------------------


def _payload_hash(payload: dict) -> str:
    """SHA-256 of the canonical JSON of the redacted payload, first 16 hex chars."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:16]


def _answers_json(data: dict) -> str | None:
    """Extract the ``answers`` dict as compact JSON. Never includes state text."""
    answers = data.get("answers")
    if not isinstance(answers, dict):
        return None
    try:
        text = json.dumps(answers, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None
    if len(text) > 65536:
        return None
    return text


# ---------------------------------------------------------------------------
# Shared state directory (cache + breaker files)
# ---------------------------------------------------------------------------


def _state_dir() -> Path:
    """Return the Jev state directory, honoring env ``JEV_STATE_DIR``.

    Default: ``~/.claude/state``. Tests override this to a temp directory
    so they never read or write the real state files.
    """
    env = os.environ.get("JEV_STATE_DIR")
    if env:
        return Path(env)
    return Path.home() / ".claude" / "state"


def _breaker_path() -> Path:
    return _state_dir() / "jev-breaker.json"


def _cache_db_path() -> Path:
    return _state_dir() / "jev-cache.sqlite"


# ---------------------------------------------------------------------------
# Circuit breaker — stops wasted calls on auth/billing errors
# ---------------------------------------------------------------------------

_BREAKER_LOCK = threading.Lock()
_jev_down: tuple[int, float] | None = None  # (http_status, monotonic_time)
_BREAKER_CODES = frozenset({401, 402})


def _breaker_ttl() -> float:
    """Return the cross-process breaker TTL in seconds (env JEV_BREAKER_TTL_S, default 60)."""
    raw = os.environ.get("JEV_BREAKER_TTL_S", "60")
    try:
        return max(0.0, float(raw))
    except (ValueError, TypeError):
        return 60.0


def _write_breaker(status: int) -> None:
    """Write breaker state to disk. Best-effort; never raises."""
    try:
        bp = _breaker_path()
        bp.parent.mkdir(parents=True, exist_ok=True)
        bp.write_text(json.dumps({"status": status, "ts": time.time()}), encoding="utf-8")
        os.chmod(bp, 0o600)
    except OSError:
        pass


def _clear_breaker() -> None:
    """Remove the breaker file and in-process flag."""
    global _jev_down
    _jev_down = None
    try:
        _breaker_path().unlink(missing_ok=True)
    except OSError:
        pass


def _check_breaker() -> int | None:
    """Return the tripped HTTP status if the breaker is active, else None."""
    global _jev_down
    ttl = _breaker_ttl()
    if ttl <= 0:
        return None
    # In-process check first (fast path).
    if _jev_down is not None:
        status, ts = _jev_down
        if (time.monotonic() - ts) < ttl:
            return status
        _jev_down = None
    # Cross-process file check.
    try:
        raw = json.loads(_breaker_path().read_text(encoding="utf-8"))
        file_ts = float(raw.get("ts", 0))
        if (time.time() - file_ts) < ttl:
            file_status = int(raw["status"])
            _jev_down = (file_status, time.monotonic())
            return file_status
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        pass
    return None


def _trip_breaker(status: int) -> None:
    """Trip the breaker for the given HTTP status code."""
    global _jev_down
    _jev_down = (status, time.monotonic())
    _write_breaker(status)


# ---------------------------------------------------------------------------
# On-disk cache — avoids duplicate Jev calls
# ---------------------------------------------------------------------------

_cache_conn_lock = threading.Lock()
_cache_conn: sqlite3.Connection | None = None
_cache_conn_path: str | None = None  # tracks which DB the conn is for


def _cache_ttl() -> float:
    """Return the cache TTL in seconds (env JEV_CACHE_TTL_S, default 1800). 0 disables.

    The default is 30 minutes, longer than one round of an iteration loop, so
    a round re-bills only the requests whose payload changed. Identical
    payloads return nearly identical answers, so a cached answer stands in
    for a repeat.
    """
    raw = os.environ.get("JEV_CACHE_TTL_S", "1800")
    try:
        return max(0.0, float(raw))
    except (ValueError, TypeError):
        return 1800.0


def _get_cache_conn() -> sqlite3.Connection:
    """Return a long-lived cache DB connection (created once per process).

    Reopens if ``JEV_STATE_DIR`` changed since the connection was made
    (happens when tests redirect the state dir between calls).
    """
    global _cache_conn, _cache_conn_path
    db_path = _cache_db_path()
    db_str = str(db_path)
    if _cache_conn is not None and _cache_conn_path == db_str:
        return _cache_conn
    # Close stale connection if the path changed.
    if _cache_conn is not None:
        try:
            _cache_conn.close()
        except Exception:
            pass
        _cache_conn = None
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_str, timeout=2.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS cache ("
        "  hash TEXT PRIMARY KEY,"
        "  ts REAL NOT NULL,"
        "  answers_json TEXT NOT NULL,"
        "  model TEXT"
        ")"
    )
    conn.commit()
    try:
        os.chmod(db_path, 0o600)
    except OSError:
        pass
    _cache_conn = conn
    _cache_conn_path = db_str
    return conn


def _cache_lookup(phash: str) -> dict | None:
    """Return cached answers dict if a fresh entry exists, else None."""
    ttl = _cache_ttl()
    if ttl <= 0:
        return None
    try:
        conn = _get_cache_conn()
        row = conn.execute("SELECT ts, answers_json, model FROM cache WHERE hash = ?", (phash,)).fetchone()
        if row is None:
            return None
        age = time.time() - row["ts"]
        if age > ttl:
            conn.execute("DELETE FROM cache WHERE hash = ?", (phash,))
            conn.commit()
            return None
        return json.loads(row["answers_json"])
    except Exception:
        return None


def _cache_store(phash: str, answers: dict, model: str | None = None) -> None:
    """Write an answers dict to the cache."""
    if _cache_ttl() <= 0:
        return
    try:
        conn = _get_cache_conn()
        answers_text = json.dumps(answers, sort_keys=True, separators=(",", ":"))
        conn.execute(
            "INSERT OR REPLACE INTO cache (hash, ts, answers_json, model) VALUES (?, ?, ?, ?)",
            (phash, time.time(), answers_text, model),
        )
        conn.commit()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# In-flight dedupe — one network request per unique payload
# ---------------------------------------------------------------------------

_inflight_lock = threading.Lock()
_inflight: dict[str, threading.Event] = {}
_inflight_results: dict[str, tuple[dict, float]] = {}


def _count_call(
    *,
    ok: bool,
    latency_ms: float | None,
    data: dict | None,
    n_questions: int,
    n_redacted: int,
    error: str | None,
    payload_hash: str | None = None,
    answers_json: str | None = None,
    cached: bool | None = None,
    script_name: str | None = None,
) -> None:
    """Best-effort telemetry; never raises, never delays the call path measurably."""
    if _record_jev_call is None:
        return
    usage = (data or {}).get("usage") if isinstance(data, dict) else None
    usage = usage if isinstance(usage, dict) else {}
    try:
        sid = os.environ.get("JEV_SESSION_ID") or os.environ.get("CLAUDE_SESSION_ID")
        agent_id = os.environ.get("JEV_AGENT_ID")
        if sid and agent_id:
            sid = f"{sid}:{agent_id}"
        _record_jev_call(
            script=script_name or _caller_script(),
            ok=ok,
            latency_ms=latency_ms,
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            n_questions=n_questions,
            n_redacted=n_redacted,
            error=error,
            session_id=sid,
            payload_hash=payload_hash,
            answers_json=answers_json,
            cached=cached,
        )
    except Exception:
        pass


TYPESAFE_PLUGIN_KEY = "typesafe@typesafe-ai"
TYPESAFE_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"


def _read_json_object(path: Path) -> dict:
    """Read one settings file as a dict. Any failure -> {} (never raises)."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _merged_enabled_plugins() -> dict:
    """Merge `enabledPlugins` from settings.json and settings.local.json.

    Local wins on any key present in both (shallow merge). A missing or
    malformed file resolves to {} for that file and never raises.
    """
    global_settings = _read_json_object(Path.home() / ".claude" / "settings.json")
    local_settings = _read_json_object(Path.home() / ".claude" / "settings.local.json")

    global_plugins = global_settings.get("enabledPlugins")
    local_plugins = local_settings.get("enabledPlugins")

    merged: dict = {}
    if isinstance(global_plugins, dict):
        merged.update(global_plugins)
    if isinstance(local_plugins, dict):
        merged.update(local_plugins)
    return merged


def typesafe_available() -> tuple[bool, str]:
    """Return (available, reason).

    available is True only when BOTH hold:
      1. TYPESAFE_API_KEY is set in the environment and non-empty after
         stripping whitespace. The value itself is never returned or logged.
      2. enabledPlugins["typesafe@typesafe-ai"] == True in the merged
         settings (settings.local.json wins over settings.json on conflict).

    Never raises: any failure while reading settings is swallowed and counts
    against availability, not against the caller.
    """
    try:
        api_key = os.environ.get("TYPESAFE_API_KEY", "")
        has_key = bool(api_key.strip())

        plugins = _merged_enabled_plugins()
        plugin_enabled = plugins.get(TYPESAFE_PLUGIN_KEY) is True

        if has_key and plugin_enabled:
            return True, "TYPESAFE_API_KEY set and typesafe@typesafe-ai enabled"
        # Standalone CLI/cron use outside Claude Code has no plugin settings.
        if has_key and os.environ.get("JEV_KEY_ONLY", "") == "1":
            return True, "TYPESAFE_API_KEY set; JEV_KEY_ONLY=1 skips plugin check"
        if not has_key and not plugin_enabled:
            return False, "TYPESAFE_API_KEY unset and typesafe@typesafe-ai not enabled"
        if not has_key:
            return False, "TYPESAFE_API_KEY unset"
        return False, "typesafe@typesafe-ai not enabled in settings"
    except Exception as exc:
        return False, f"presence check error: {type(exc).__name__}: {exc}"


# Retry numbers come from jev_limits, the single home of the documented limits
# and backoff policy (api.md: exponential backoff for 429 and 529).
_RETRY_CODES = jev_limits.RETRY_STATUSES_DIRECT
_RETRY_BASE_S = jev_limits.RETRY_BASE_S
_RETRY_MAX_SLEEP_S = jev_limits.RETRY_MAX_S
_jitter = random.random  # tests pin this for exact delays


def _retry_max() -> int:
    """Retries after a rate-limit or overload response (env JEV_RETRY_MAX, default 3, 0 disables)."""
    try:
        return max(0, int(os.environ.get("JEV_RETRY_MAX", "3")))
    except (ValueError, TypeError):
        return 3


def _retry_delay(exc: urllib.error.HTTPError, attempt: int) -> float | None:
    """Seconds to wait before retrying, or None when this error is not retried.

    Only HTTP 429 and 529 are retried. The wait doubles each attempt with
    jitter, so parallel callers that failed together do not retry together
    (synchronized retries turn a rate limit into a retry storm). It honors a
    numeric ``Retry-After`` header as a floor and never exceeds
    ``_RETRY_MAX_SLEEP_S`` so a hook's own timeout still bounds the call.
    """
    if exc.code not in _RETRY_CODES or attempt >= _retry_max():
        return None
    retry_after = None
    header = exc.headers.get("Retry-After") if exc.headers is not None else None
    if header:
        try:
            retry_after = float(header)
        except (ValueError, TypeError):
            pass
    return jev_limits.backoff_delay(attempt, retry_after, rng=_jitter, base=_RETRY_BASE_S, cap=_RETRY_MAX_SLEEP_S)


def _error_kind(exc: urllib.error.HTTPError) -> str:
    """Short, body-free label for an HTTP error: the API's own error ``type`` when present."""
    try:
        body = json.loads(exc.read(2000).decode("utf-8", errors="replace"))
    except Exception:
        return ""
    err = body.get("error") if isinstance(body, dict) else None
    kind = err.get("type") if isinstance(err, dict) else None
    if isinstance(kind, str) and kind.replace("_", "").isalnum() and len(kind) <= 40:
        return f" ({kind})"
    if isinstance(body, dict) and isinstance(body.get("detail"), list):
        locs = [".".join(str(x) for x in d.get("loc", [])) for d in body["detail"][:3] if isinstance(d, dict)]
        locs = [loc for loc in locs if loc and len(loc) <= 120]
        if locs:
            return " (invalid: " + "; ".join(locs) + ")"
    return ""


def call_jev(
    payload: dict,
    api_key: str,
    timeout: float,
    *,
    script_name: str | None = None,
) -> tuple[dict, float]:
    """POST one Jev call. Returns (response_json, latency_ms).

    Stdlib urllib.request only (no third-party HTTP dependency).
    Raises on any failure; the caller catches broadly and never includes
    the Authorization header or key value in any error message.

    Pass ``script_name`` to override the auto-detected caller for telemetry
    (useful when sub-scripts run in-process under an orchestrator).

    Layers applied before the network call:
    1. Redaction -- secrets stripped from payload.
    2. Payload hash -- sha256 of canonical JSON, first 16 hex.
    3. Circuit breaker -- HTTP 401/402 trips a breaker; subsequent
       calls in the same process (and across processes for ``JEV_BREAKER_TTL_S``
       seconds) return the same failure without a network request.
    4. Cache -- on-disk SQLite cache keyed by payload hash with
       configurable TTL (``JEV_CACHE_TTL_S``, default 120s, 0 disables).
    5. In-flight dedupe -- concurrent calls with the same hash wait
       for one in-flight request instead of sending duplicates.
    """
    payload, n_redacted = jev_redact.redact_payload(payload)
    if n_redacted > 0:
        print(f"[jev-redact] {n_redacted} value(s) redacted before send", file=sys.stderr)

    phash = _payload_hash(payload)
    n_questions = len(payload.get("questions") or {}) if isinstance(payload.get("questions"), dict) else 0

    # --- Circuit breaker ---
    breaker_status = _check_breaker()
    if breaker_status is not None:
        error_msg = f"HTTP {breaker_status} (breaker)"
        _count_call(
            ok=False,
            latency_ms=0,
            data=None,
            n_questions=n_questions,
            n_redacted=n_redacted,
            error=error_msg,
            payload_hash=phash,
            cached=False,
            script_name=script_name,
        )
        raise RuntimeError(error_msg)

    # --- Cache lookup ---
    cached_answers = _cache_lookup(phash)
    if cached_answers is not None:
        data = {"answers": cached_answers, "_meta": {"cached": True}}
        _count_call(
            ok=True,
            latency_ms=0,
            data=data,
            n_questions=n_questions,
            n_redacted=n_redacted,
            error=None,
            payload_hash=phash,
            answers_json=_answers_json(data),
            cached=True,
            script_name=script_name,
        )
        return data, 0.0

    # --- In-flight dedupe ---
    event: threading.Event | None = None
    owner = False
    with _inflight_lock:
        if phash in _inflight:
            event = _inflight[phash]
        else:
            event = threading.Event()
            _inflight[phash] = event
            owner = True

    if not owner:
        # Wait for the in-flight request to complete.
        event.wait(timeout=timeout + 5.0)
        result = _inflight_results.pop(phash, None)
        if result is not None:
            data, latency_ms = result
            _count_call(
                ok=True,
                latency_ms=0,
                data=data,
                n_questions=n_questions,
                n_redacted=n_redacted,
                error=None,
                payload_hash=phash,
                answers_json=_answers_json(data),
                cached=True,
                script_name=script_name,
            )
            return data, latency_ms
        # Fallthrough: the owner failed or timed out; make our own request.

    # --- Network call ---
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        TYPESAFE_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    start = time.monotonic()
    attempt = 0
    try:
        while True:
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    raw = response.read()
                break
            except urllib.error.HTTPError as exc:
                delay = _retry_delay(exc, attempt)
                if delay is None:
                    raise
                # One log row per refused attempt, so the call log stays truthful.
                _count_call(
                    ok=False,
                    latency_ms=(time.monotonic() - start) * 1000.0,
                    data=None,
                    n_questions=n_questions,
                    n_redacted=n_redacted,
                    error=f"HTTP {exc.code} (retrying)",
                    payload_hash=phash,
                    script_name=script_name,
                )
                time.sleep(delay)
                attempt += 1
                start = time.monotonic()
    except urllib.error.HTTPError as exc:
        latency_ms = (time.monotonic() - start) * 1000.0
        # Trip breaker on auth/billing errors.
        if exc.code in _BREAKER_CODES:
            _trip_breaker(exc.code)
        _count_call(
            ok=False,
            latency_ms=latency_ms,
            data=None,
            n_questions=n_questions,
            n_redacted=n_redacted,
            error=f"HTTP {exc.code}",
            payload_hash=phash,
            script_name=script_name,
        )
        if owner:
            with _inflight_lock:
                _inflight.pop(phash, None)
            event.set()
        # Status only: an error body can echo part of the request.
        raise RuntimeError(f"HTTP {exc.code}{_error_kind(exc)}") from exc
    except Exception as exc:
        latency_ms = (time.monotonic() - start) * 1000.0
        _count_call(
            ok=False,
            latency_ms=latency_ms,
            data=None,
            n_questions=n_questions,
            n_redacted=n_redacted,
            error=type(exc).__name__,
            payload_hash=phash,
            script_name=script_name,
        )
        if owner:
            with _inflight_lock:
                _inflight.pop(phash, None)
            event.set()
        raise

    latency_ms = (time.monotonic() - start) * 1000.0
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict) or "answers" not in data:
        _count_call(
            ok=False,
            latency_ms=latency_ms,
            data=None,
            n_questions=n_questions,
            n_redacted=n_redacted,
            error="missing answers",
            payload_hash=phash,
            script_name=script_name,
        )
        if owner:
            with _inflight_lock:
                _inflight.pop(phash, None)
            event.set()
        raise ValueError("Jev response missing 'answers' key")

    # Success: clear breaker, cache, record, and release waiters.
    _clear_breaker()
    answers = data.get("answers", {})
    _cache_store(phash, answers, data.get("model"))
    aj = _answers_json(data)
    _count_call(
        ok=True,
        latency_ms=latency_ms,
        data=data,
        n_questions=n_questions,
        n_redacted=n_redacted,
        error=None,
        payload_hash=phash,
        answers_json=aj,
        cached=False,
        script_name=script_name,
    )
    if owner:
        _inflight_results[phash] = (data, latency_ms)
        with _inflight_lock:
            _inflight.pop(phash, None)
        event.set()

        # Schedule cleanup so non-owner threads have time to pop the result.
        # 10s is generous; if no one consumes it by then, discard it.
        def _cleanup(h=phash):
            import time as _t

            _t.sleep(10)
            _inflight_results.pop(h, None)

        import threading as _thr

        _thr.Thread(target=_cleanup, daemon=True).start()
    return data, latency_ms


def validate_jev_response(data: dict) -> tuple[bool, list[str]]:
    """Validate structural integrity of a Jev API response.

    Checks:
      - ``answers`` exists and is a dict.
      - Each answer contains a recognized type field (noul, choice, score).
      - Noul values are floats in [0, 1].
      - Choice values are strings.
      - Score values are numeric.
      - ``probabilities``, when present, has float values in [0, 1] summing
        to ~1.0 (within 0.05).
      - ``confidence``, when present, is a float in [0, 1].

    Returns ``(is_valid, errors)`` and never raises.
    """
    errors: list[str] = []
    try:
        if not isinstance(data, dict):
            return False, ["response is not a dict"]

        answers = data.get("answers")
        if not isinstance(answers, dict):
            return False, ["'answers' key missing or not a dict"]

        for key, answer in answers.items():
            if not isinstance(answer, dict):
                errors.append(f"{key}: answer is not a dict")
                continue

            has_type = False

            # Noul
            if "noul" in answer:
                has_type = True
                val = answer["noul"]
                if not isinstance(val, (int, float)):
                    errors.append(f"{key}: noul is not numeric ({type(val).__name__})")
                elif not (0.0 <= float(val) <= 1.0):
                    errors.append(f"{key}: noul {val} outside [0, 1]")

            # Choice
            if "choice" in answer:
                has_type = True
                val = answer["choice"]
                if not isinstance(val, str):
                    errors.append(f"{key}: choice is not a string ({type(val).__name__})")

            # Score
            if "score" in answer:
                has_type = True
                val = answer["score"]
                if not isinstance(val, (int, float)):
                    errors.append(f"{key}: score is not numeric ({type(val).__name__})")

            if not has_type:
                errors.append(f"{key}: no recognized type field (noul/choice/score)")

            # Probabilities (optional, present on Choice answers)
            probs = answer.get("probabilities")
            if probs is not None:
                if not isinstance(probs, dict):
                    errors.append(f"{key}: probabilities is not a dict")
                else:
                    total = 0.0
                    for pk, pv in probs.items():
                        if not isinstance(pv, (int, float)):
                            errors.append(f"{key}: probabilities[{pk}] is not numeric")
                        else:
                            fv = float(pv)
                            if not (0.0 <= fv <= 1.0):
                                errors.append(f"{key}: probabilities[{pk}] = {fv} outside [0, 1]")
                            total += fv
                    if probs and abs(total - 1.0) > 0.05:
                        errors.append(f"{key}: probabilities sum to {total:.4f}, expected ~1.0")

            # Confidence (optional)
            conf = answer.get("confidence")
            if conf is not None:
                if not isinstance(conf, (int, float)):
                    errors.append(f"{key}: confidence is not numeric")
                elif not (0.0 <= float(conf) <= 1.0):
                    errors.append(f"{key}: confidence {conf} outside [0, 1]")

    except Exception as exc:
        return False, [f"validation error: {type(exc).__name__}: {exc}"]

    return (len(errors) == 0, errors)


def validated_call_jev(
    payload: dict,
    api_key: str,
    timeout: float,
    *,
    script_name: str | None = None,
) -> tuple[dict, float]:
    """Call Jev and validate the response (fail-open).

    Wraps ``call_jev`` with ``validate_jev_response``. Invalid responses
    log warnings to stderr but still return the data so callers degrade
    gracefully.

    Returns ``(response_json, latency_ms)`` — same as ``call_jev``.
    """
    import sys

    data, latency_ms = call_jev(payload, api_key, timeout, script_name=script_name)
    is_valid, errors = validate_jev_response(data)
    if not is_valid:
        for err in errors[:5]:
            print(f"[jev-validate] WARNING: {err}", file=sys.stderr)
    return data, latency_ms


def extract_usage(data: dict) -> dict | None:
    """Passthrough token usage from one Jev response. Never fabricated."""
    usage_raw = data.get("usage")
    if not isinstance(usage_raw, dict):
        return None
    input_tokens = usage_raw.get("input_tokens")
    output_tokens = usage_raw.get("output_tokens")
    if isinstance(input_tokens, int) and isinstance(output_tokens, int):
        return {"input_tokens": input_tokens, "output_tokens": output_tokens}
    return None


def _score_mean(answer: dict) -> float | None:
    """Return ``answer["score"]`` as a float, or None when it is not int/float.

    ``bool`` is excluded: ``True`` is an ``int`` subclass but never a Jev mean.
    """
    value = answer.get("score")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def score_level(answer: dict, n_levels: int) -> int | None:
    """Bucket one Jev Score answer into a criteria index.

    A live Jev Score answer carries ``score`` as a probability-weighted mean
    of the level numbers ``0..n_levels-1`` (a float such as ``2.3``), never a
    label string and never ``choice``. This helper rounds that mean to the
    nearest level and clamps it to ``[0, n_levels-1]`` so callers can index
    their criteria list.

    Rounding is for bucketing only. The mean already blends the levels; when
    the split matters (a ``1.5`` could be a coin flip between two levels or a
    firm 50/50), read ``answer["probabilities"]`` instead of this bucket.

    Args:
        answer: One Jev answer dict (``{"score": float, "probabilities": ...}``).
        n_levels: Length of the criteria list the question was asked with.

    Returns:
        The rounded, clamped level index, or None when ``score`` is missing or
        not numeric (``bool`` counts as non-numeric) or ``n_levels < 1``.
    """
    mean = _score_mean(answer)
    if mean is None or n_levels < 1:
        return None
    level = round(mean)
    return max(0, min(n_levels - 1, level))


def score_normalized(answer: dict, n_levels: int) -> float | None:
    """Map one Jev Score answer's weighted mean onto ``[0, 1]``.

    ``score`` is a probability-weighted mean of the level numbers
    ``0..n_levels-1``. This divides it by ``n_levels-1`` and clamps to
    ``[0, 1]`` so Score answers can be compared against Noul thresholds.
    No rounding happens here; use ``score_level`` when you need a bucket, and
    read ``answer["probabilities"]`` when the split between levels matters.

    Args:
        answer: One Jev answer dict.
        n_levels: Length of the criteria list the question was asked with.

    Returns:
        The clamped normalized mean, or None when ``score`` is not numeric
        (``bool`` counts as non-numeric) or ``n_levels < 2``.
    """
    mean = _score_mean(answer)
    if mean is None or n_levels < 2:
        return None
    return max(0.0, min(1.0, mean / (n_levels - 1)))


def bound_text(text: str, limit: int, label: str = "") -> str:
    """Tail-truncate text to *limit* characters, preserving the end.

    When truncated, prepends an omission notice so Jev (and humans) know
    content was dropped. The tail is kept because the most recent content
    (latest tool output, end of diff, last lines of a file) is usually
    the most relevant.

    Args:
        text: The raw text to bound.
        limit: Maximum character count (the notice counts toward it).
        label: Optional label for the notice (e.g. "request", "diff").
    """
    if len(text) <= limit:
        return text
    omitted = len(text) - limit
    if label:
        notice = f"[{omitted} chars omitted in {label}]\n"
    else:
        notice = f"[{omitted} chars omitted]\n"
    # Reserve room for the notice itself.
    content_budget = limit - len(notice)
    if content_budget < 20:
        # Limit too small for a useful tail; just hard-truncate.
        return text[-limit:]
    return notice + text[-content_budget:]


def main() -> int:
    parser = argparse.ArgumentParser(description="Presence check for the Jev/TypeSafe routing backend.")
    parser.add_argument(
        "--check",
        action="store_true",
        help='Print {"available": bool, "reason": str} as JSON (also the default with no flags).',
    )
    parser.parse_args()

    available, reason = typesafe_available()
    print(json.dumps({"available": available, "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
