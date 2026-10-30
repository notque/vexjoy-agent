"""The alt-model answerer behind the two scoped Jev fallback/second-opinion modes.

Scope (owner, 2026-10-30, after a fresh Jev Noul on this exact framing scored
0.75 worth-building / 0.04 same-as-the-rejected-generic-abstraction): exactly
one named alt model answers the same Noul/Choice/Score question set Jev
answers, for two callers in ``jev_transport.py`` (`evaluate_with_fallback`,
`evaluate_second_opinion`). This is not a provider plugin architecture: there
is no registry, no discovery, and no interface other callers implement. The
dual backend below (direct Anthropic API, else the logged-in `claude -p` CLI)
copies the pattern `jev-browser-agent.py`'s `generate_text` already uses in
this toolkit for "ask the session's own model" -- it is not a new mechanism.

Every answer this module returns carries ``_meta.is_jev = False`` and
``_meta.source = "alt-model"``. Callers must report it as a labeled
non-Jev answer, never as if Jev had answered.
"""

from __future__ import annotations

import ipaddress
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_images
import jev_router_common

SOURCE = "alt-model"
ALT_MODEL = os.environ.get("JEV_ALT_MODEL", "claude-sonnet-4-6")
ALT_MODEL_BASE_URL = os.environ.get("JEV_ALT_MODEL_BASE_URL", "https://api.anthropic.com").rstrip("/")
# "api" (Anthropic Messages via urllib), "claude-cli" (`claude -p`, logged-in
# CLI, no key needed), or "auto" (api when a key is set, else claude-cli).
ALT_MODEL_BACKEND = os.environ.get("JEV_ALT_MODEL_BACKEND", "auto")
DEFAULT_TIMEOUT_S = 60.0
# The CLI backend starts a full `claude -p` subprocess; it routinely needs
# more wall time than the API backend's typical call. `answer()` floors the
# caller's timeout at this value on the CLI path only, so a timeout sized
# for a fast API/Gateway call does not starve the slower CLI fallback.
CLAUDE_CLI_TIMEOUT_S = 90.0
# Output budget scales with question count (each Choice/Score answer carries
# a probabilities entry per option/level); capped so one malformed request
# cannot ask for an unbounded reply.
_BASE_OUTPUT_TOKENS = 512
_OUTPUT_TOKENS_PER_QUESTION = 256
_MAX_OUTPUT_TOKENS = 4096


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect: urllib would resend the ``x-api-key`` header to the new host."""

    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        return None


_NO_REDIRECT_OPENER = urllib.request.build_opener(_NoRedirect)
_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _is_loopback(url: str) -> bool:
    """True for localhost or a literal loopback address. A name like 127.evil.com is not loopback."""
    host = (urlparse(url).hostname or "").lower()
    if host in _LOOPBACK_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _base_url_ok(url: str) -> bool:
    """The alt-model API key travels in a header: require TLS, except for a loopback test server."""
    scheme = urlparse(url).scheme
    return scheme == "https" or (scheme == "http" and _is_loopback(url))


class AltModelError(RuntimeError):
    """The alt model produced no usable answer. ``reason`` is a short, safe label."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _alt_model_api_key() -> str:
    """Return the configured alt-model API key, or ``""`` when none is set."""
    return os.environ.get("JEV_ALT_MODEL_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or ""


def _resolve_backend(api_key: str) -> str:
    """Resolve ``ALT_MODEL_BACKEND`` to ``"api"`` or ``"claude-cli"`` (or pass through an invalid value).

    One place for the ``"auto"`` rule so ``available()`` and ``answer()`` can never drift apart on
    which backend a given key/env combination actually resolves to.
    """
    backend = ALT_MODEL_BACKEND
    if backend == "auto":
        return "api" if api_key else "claude-cli"
    return backend


def available() -> tuple[bool, str]:
    """Return whether this process can reach the alt model right now, and how."""
    api_key = _alt_model_api_key()
    backend = _resolve_backend(api_key)
    if backend == "api":
        return (True, "JEV_ALT_MODEL_API_KEY or ANTHROPIC_API_KEY set") if api_key else (False, "no alt-model API key")
    if backend == "claude-cli":
        return (True, "claude CLI on PATH") if shutil.which("claude") else (False, "claude CLI not on PATH")
    return False, f"invalid JEV_ALT_MODEL_BACKEND={backend!r}"


def _prompt(state: Any, questions: dict[str, Any]) -> str:
    """One prompt asking the alt model to answer every question in the Jev response shape."""
    schema = (
        "You are answering a fixed judgment schema, not having a conversation. "
        'Reply with ONLY one JSON object: {"answers": {"<question_id>": <answer>}}, '
        "one entry per question id below, no prose before or after it. "
        'A "noul" question answers {"type": "noul", "noul": <float 0..1>}. '
        'A "choice" question answers {"type": "choice", "choice": "<one listed option>", '
        '"probabilities": {"<option>": <float>, ...}} covering every option, summing to about 1. '
        'A "score" question answers {"type": "score", "score": <float level index>, '
        '"probabilities": {"<level index as string>": <float>, ...}} summing to about 1.'
    )
    return (
        f"{schema}\n\nSTATE:\n{json.dumps(state, ensure_ascii=False)}\n\n"
        f"QUESTIONS:\n{json.dumps(questions, ensure_ascii=False)}"
    )


def _find_json_object(text: str) -> str | None:
    """Return the first ``{...}`` substring that is both balanced and valid JSON.

    A greedy ``{.*}`` regex would span from the first ``{`` to the LAST ``}`` in
    the whole reply, swallowing any aside the alt model adds before or after
    the answer object. A single depth-tracking scan anchored at the very first
    ``{`` is not enough either: a short aside placed before the real object
    (for example "for {ambiguous} cases...") is itself a balanced brace pair,
    so anchoring at the first ``{`` returns that aside, not the real answer.
    Instead, try each ``{`` in the text as a candidate start, extract its
    balanced span (tracking depth through string literals so a nested object
    like ``{"answers": {"ok": {...}}}`` stays whole), and return the first
    span that actually parses as JSON -- an aside's brace pair almost never
    does, since bare words are not valid JSON, so this skips past it to the
    real object.
    """
    pos = 0
    while True:
        start = text.find("{", pos)
        if start == -1:
            return None
        depth = 0
        in_string = False
        escape = False
        end = None
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        if end is not None:
            candidate = text[start : end + 1]
            try:
                json.loads(candidate)
            except json.JSONDecodeError:
                pass
            else:
                return candidate
        pos = start + 1


def _parse_reply(text: str) -> dict[str, Any] | None:
    """Extract the first JSON object from a reply that may carry code fences or prose around it."""
    candidate = _find_json_object(text)
    if candidate is None:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _answer_cli(prompt: str, timeout: float) -> tuple[dict[str, Any] | None, str]:
    """Answer via the logged-in `claude -p` CLI. No API key, no tools, no session."""
    if not shutil.which("claude"):
        return None, "claude-cli-missing"
    cmd = ["claude", "-p", "--no-session-persistence", "--model", ALT_MODEL, "--allowed-tools", ""]
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),  # outside any repo: no project hooks or CLAUDE.md
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return None, f"claude-cli-error: {type(exc).__name__}"
    if result.returncode != 0:
        return None, f"claude-cli-exit-{result.returncode}"
    parsed = _parse_reply(result.stdout)
    return (parsed, "claude-cli") if parsed is not None else (None, "claude-cli-unparseable")


def _answer_api(prompt: str, timeout: float, api_key: str, max_tokens: int) -> tuple[dict[str, Any] | None, str]:
    """Answer via the Anthropic Messages API."""
    body = {"model": ALT_MODEL, "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]}
    request = urllib.request.Request(
        f"{ALT_MODEL_BASE_URL}/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
        method="POST",
    )
    try:
        with _NO_REDIRECT_OPENER.open(request, timeout=timeout) as response:
            data = json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return None, f"alt-model-api-error: {type(exc).__name__}"
    raw = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
    parsed = _parse_reply(raw)
    return (parsed, "api") if parsed is not None else (None, "alt-model-unparseable")


def answer(state: Any, questions: dict[str, Any], *, timeout: float = DEFAULT_TIMEOUT_S) -> dict[str, Any]:
    """Answer ``questions`` over ``state`` with the alt model, in the Jev response shape.

    Tries the Anthropic API (``JEV_ALT_MODEL_API_KEY`` or ``ANTHROPIC_API_KEY``) when
    ``JEV_ALT_MODEL_BACKEND`` allows it, else the logged-in ``claude -p`` CLI. Raises
    ``AltModelError`` on any failure; never fabricates an answer, and never silently
    drops a question the caller asked. The returned dict's ``_meta`` always carries
    ``is_jev: False`` and ``source: "alt-model"`` so a caller cannot mistake this for
    a Jev response.

    Text-only: raises ``AltModelError("images-unsupported")`` when ``state`` or
    ``questions`` carries a ``JevImage`` or a Box question, even when the caller
    did not route through `jev_transport.py`'s own image guard.
    """
    if jev_images.contains_images(state, questions) or jev_images.has_box(questions):
        raise AltModelError("images-unsupported")

    api_key = _alt_model_api_key()
    backend = _resolve_backend(api_key)
    prompt = _prompt(state, questions)
    if backend == "claude-cli":
        # The CLI starts a full subprocess and routinely needs more wall time
        # than a caller sizes for a fast API/Gateway call; never starve it
        # below its own measured floor.
        parsed, source = _answer_cli(prompt, max(timeout, CLAUDE_CLI_TIMEOUT_S))
    elif backend == "api":
        if not api_key:
            raise AltModelError("no-alt-model-key")
        if not _base_url_ok(ALT_MODEL_BASE_URL):
            raise AltModelError("alt-model-insecure-url")
        max_tokens = min(_MAX_OUTPUT_TOKENS, _BASE_OUTPUT_TOKENS + _OUTPUT_TOKENS_PER_QUESTION * max(1, len(questions)))
        parsed, source = _answer_api(prompt, timeout, api_key, max_tokens)
    else:
        raise AltModelError(f"invalid-backend:{backend}")
    if parsed is None:
        raise AltModelError(source)

    answers = parsed.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise AltModelError("alt-model-incomplete-answers")

    result: dict[str, Any] = {
        "answers": answers,
        "model": ALT_MODEL,
        "_meta": {"is_jev": False, "source": SOURCE, "backend": source},
    }
    valid, errors = jev_router_common.validate_jev_response(result)
    if not valid:
        raise AltModelError("alt-model-invalid-shape:" + "; ".join(errors[:3]))
    return result
