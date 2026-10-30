"""Selectable Jev transport for /d.

``JEV_TRANSPORT`` accepts ``auto`` (default), ``vercel``, or ``direct``.
Auto selects Vercel AI Gateway when its key is configured; otherwise it
selects TypeSafe's direct Jev API. A failed selected transport is not retried
through the other provider.

Two scoped exceptions to that last rule (owner, 2026-10-30; a fresh Jev Noul
on this exact framing scored 0.75 worth-building, 0.04 same-as-the-rejected
generic-abstraction -- see the PR description for the full question and
state): ``evaluate_with_fallback`` and ``evaluate_second_opinion``, both
calling the single named alt model in ``jev_alt_model.py``. Neither is a
provider plugin architecture -- there is no registry, no discovery, and
callers do not choose a provider by name. Every alt-model answer is tagged
``is_jev: False`` and must be reported as such, never silently presented as
if Jev had answered.
"""

from __future__ import annotations

import os
import time
import warnings
from typing import Any

import jev_alt_model
import jev_images
import jev_limits
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


REQUEST_TOO_LARGE = "request_too_large"
IMAGES_UNSUPPORTED = "images_unsupported"
INVALID_IMAGE = "invalid_image"


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
    if has_vercel:
        return VERCEL, "auto selected AI_GATEWAY_API_KEY"
    if has_direct:
        return DIRECT, "auto selected TYPESAFE_API_KEY"
    return None, "neither AI_GATEWAY_API_KEY nor TYPESAFE_API_KEY is set"


def available() -> tuple[bool, str]:
    transport, reason = select()
    return transport is not None, reason


def evaluate(
    state: Any,
    questions: dict[str, Any],
    *,
    timeout: float,
    images: dict[str, jev_images.JevImage] | None = None,
) -> dict[str, Any]:
    """Evaluate one state through the selected Jev transport.

    Images: put a ``jev_images.JevImage`` anywhere in ``state`` or a question, or
    pass ``images={"name": JevImage}`` and write ``{img:name}`` in strings. A
    request with images, or with a Box question, always uses the direct API
    (the Gateway bridge cannot carry images); without ``TYPESAFE_API_KEY`` it
    raises JevTransportError with source ``images_unsupported``.

    Too much context is the most common failure: a request over
    ``jev_limits.MAX_REQUEST_TOKENS`` is split into as many small requests as it
    takes, each with the full state, sent at once, with answers merged. Only a
    state too large for even one question is refused (source ``request_too_large``).
    """
    return _evaluate(state, questions, timeout=timeout, limit=jev_limits.MAX_REQUEST_TOKENS, images=images)


def _evaluate(
    state: Any,
    questions: dict[str, Any],
    *,
    timeout: float,
    limit: int,
    images: dict[str, jev_images.JevImage] | None = None,
) -> dict[str, Any]:
    if jev_images.contains_images(state, questions, images) or jev_images.has_box(questions):
        return _evaluate_images(state, questions, timeout=timeout, limit=limit, images=images)
    transport, reason = select()
    if transport is None:
        raise JevTransportError(reason, source="unavailable")
    try:
        if transport == VERCEL:
            try:
                return jev_vercel.evaluate(state, questions, timeout=timeout, max_request_tokens=limit)
            except jev_vercel.JevGatewayError as exc:
                raise JevTransportError(str(exc), source=VERCEL, telemetry=exc.telemetry) from exc
        return jev_limits.split_and_run(state, questions, lambda s, q: _direct_one(s, q, timeout=timeout), limit=limit)
    except jev_limits.RequestTooLarge as exc:
        raise JevTransportError(str(exc), source=REQUEST_TOO_LARGE) from exc


def _evaluate_images(
    state: Any,
    questions: dict[str, Any],
    *,
    timeout: float,
    limit: int,
    images: dict[str, jev_images.JevImage] | None,
) -> dict[str, Any]:
    """Direct-only path for requests with images or Box questions."""
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        raise JevTransportError(
            "images and Box questions need the direct API: set TYPESAFE_API_KEY "
            "(the Vercel AI Gateway bridge cannot carry images)",
            source=IMAGES_UNSUPPORTED,
        )
    try:
        bound = jev_images.bind_images(state, questions, images)
        jev_images.check_assets(bound.assets, bound.state, bound.questions)
        tokens = jev_images.image_token_map(bound.assets)
        if bound.assets:
            limit = max(limit, jev_limits.IMAGE_REQUEST_MAX_TOKENS)
            target = jev_limits.IMAGE_REQUEST_TARGET_TOKENS
        else:
            target = jev_limits.TARGET_REQUEST_TOKENS

        def send_one(s: Any, q: dict[str, Any]) -> dict[str, Any]:
            # A split request carries only the assets its state and questions reference.
            subset = jev_images.assets_for(bound.assets, s, q)
            jev_images.check_assets(subset, s, q)
            return _direct_one(s, q, timeout=timeout, assets=subset, images_header=True)

        result = jev_limits.split_and_run(
            bound.state, bound.questions, send_one, limit=limit, target=target, image_tokens=tokens
        )
    except jev_images.JevImageError as exc:
        raise JevTransportError(str(exc), source=INVALID_IMAGE) from exc
    except jev_limits.RequestTooLarge as exc:
        raise JevTransportError(str(exc), source=REQUEST_TOO_LARGE) from exc
    meta = result.setdefault("_meta", {})
    _note_resent_state_images(meta, bound, tokens)
    meta["transport"] = DIRECT
    meta["images"] = jev_images.image_meta(bound.assets)
    return result


def _note_resent_state_images(meta: dict[str, Any], bound: Any, tokens: dict[str, int]) -> None:
    """Record and warn when a split resends state images in every part (billing multiplies)."""
    split = meta.get("split")
    if not isinstance(split, dict) or not bound.assets:
        return
    uses = jev_images.ref_uses(bound.assets, bound.state, {})
    per_request = sum(tokens[ref] * n for ref, n in uses.items())
    resent = per_request * (int(split.get("requests", 1)) - 1)
    if resent <= 0:
        return
    split["state_image_tokens_resent"] = resent
    warnings.warn(
        f"Jev request split into {split['requests']} parts; each resends the state images, "
        f"about {resent} extra input tokens. Send fewer questions per state or one request per image.",
        stacklevel=3,
    )


def _direct_one(
    state: Any,
    questions: dict[str, Any],
    *,
    timeout: float,
    assets: dict[str, jev_images.PreparedImage] | None = None,
    images_header: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    model = jev_images.BOX_MODEL if jev_images.has_box(questions) else jev_router_common.JEV_MODEL
    payload: dict[str, Any] = {"state": state, "model": model, "questions": questions}
    extras: dict[str, Any] = {}
    if images_header:
        extras["extra_headers"] = {jev_images.IMAGES_HEADER: "true"}
    if assets:
        payload["assets"], extras["image_parts"] = jev_images.wire_assets(assets)
    try:
        data, _ = jev_router_common.call_jev(
            payload,
            os.environ["TYPESAFE_API_KEY"],
            timeout,
            script_name="jev_transport.py",
            **extras,
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


def evaluate_packed(
    state: Any,
    questions: dict[str, Any],
    *,
    timeout: float,
    images: dict[str, jev_images.JevImage] | None = None,
) -> dict[str, Any]:
    """Like ``evaluate`` but split at the smaller target size (3,500 tokens) up front.

    Image requests keep the larger direct-API size (see ``jev_limits.IMAGE_REQUEST_MAX_TOKENS``)
    so an image is not resent for every question.
    """
    return _evaluate(state, questions, timeout=timeout, limit=jev_limits.TARGET_REQUEST_TOKENS, images=images)


# ---------------------------------------------------------------------------
# Fallback and second-opinion modes (owner, 2026-10-30)
#
# Exactly two modes, each calling the one named alt model in jev_alt_model.py.
# Neither mode changes `evaluate`/`evaluate_packed`'s own behavior; a plain
# Jev call still raises JevTransportError on failure with no alt-model
# involved, unless the caller opts into one of the two functions below.
# ---------------------------------------------------------------------------

FALLBACK_FAILED = "fallback_failed"


def _reject_images_for_alt_model(
    state: Any, questions: dict[str, Any], images: dict[str, jev_images.JevImage] | None
) -> None:
    """The alt-model path is text-only; refuse rather than silently drop an image."""
    if jev_images.contains_images(state, questions, images) or jev_images.has_box(questions):
        raise JevTransportError(
            "the alt-model fallback and second-opinion modes do not support images or Box questions",
            source=IMAGES_UNSUPPORTED,
        )


def _log_alt_model_event(questions: dict[str, Any], *, mode: str, reason: str | None) -> None:
    """Best-effort telemetry so a fallback or second-opinion call shows up in the cost report."""
    try:
        jev_router_common._count_call(
            ok=reason is None,
            latency_ms=None,
            data=None,
            n_questions=len(questions),
            n_redacted=0,
            error=reason,
            script_name=f"jev_transport.py:{mode}",
        )
    except Exception:
        pass


def evaluate_with_fallback(
    state: Any,
    questions: dict[str, Any],
    *,
    timeout: float,
    alt_timeout: float | None = None,
    images: dict[str, jev_images.JevImage] | None = None,
) -> dict[str, Any]:
    """Availability fallback: answer with Jev; on failure, answer with the alt model instead.

    Tries ``evaluate_packed`` first. Only when that raises ``JevTransportError``
    (no credentials, network or API failure, rate-limited, oversized request)
    does this call ``jev_alt_model.answer`` on the SAME ``state`` and
    ``questions``. The returned dict always has the normal Jev response shape
    (``answers``, ``_meta``); ``_meta["is_jev"]`` is ``True`` on the Jev path
    and ``False`` on the fallback path, and ``_meta["fallback_reason"]`` is
    set only on the fallback path. A caller must read ``is_jev`` before
    treating the answer as Jev's.

    Raises ``JevTransportError`` (source ``"fallback_failed"``) when Jev fails
    AND the alt model also fails to answer; never fabricates an answer.
    """
    try:
        result = evaluate_packed(state, questions, timeout=timeout, images=images)
        result.setdefault("_meta", {})["is_jev"] = True
        return result
    except JevTransportError as exc:
        _reject_images_for_alt_model(state, questions, images)
        reason = f"{exc.source}: {str(exc)[:200]}"
        try:
            alt = jev_alt_model.answer(state, questions, timeout=alt_timeout or timeout)
        except jev_alt_model.AltModelError as alt_exc:
            _log_alt_model_event(questions, mode="fallback", reason=f"jev={reason} alt={alt_exc.reason}")
            raise JevTransportError(
                f"Jev unavailable ({reason}); alt-model fallback also failed: {alt_exc.reason}",
                source=FALLBACK_FAILED,
            ) from alt_exc
        alt["_meta"]["fallback_reason"] = reason
        _log_alt_model_event(questions, mode="fallback", reason=None)
        return alt


def evaluate_second_opinion(
    state: Any,
    questions: dict[str, Any],
    *,
    timeout: float,
    alt_timeout: float | None = None,
    images: dict[str, jev_images.JevImage] | None = None,
) -> dict[str, Any]:
    """Explicit second opinion: ask Jev and the alt model on the SAME question set.

    Both calls run; a caller uses this only when it has explicitly asked for a
    second or different opinion, not as a silent default. Returns
    ``{"jev": ..., "alt_model": ..., "_meta": {"mode": "second_opinion"}}``.
    Either side is its own normal response dict on success, or
    ``{"error": <message>, "source": <label>}`` on failure. The two answers
    are never merged or averaged into one number -- each keeps its own
    ``answers`` dict with its own Noul/Choice/Score values, and
    ``alt_model["_meta"]["is_jev"]`` is always ``False``.
    """
    _reject_images_for_alt_model(state, questions, images)
    try:
        jev_result = evaluate_packed(state, questions, timeout=timeout, images=images)
        jev_result.setdefault("_meta", {})["is_jev"] = True
    except JevTransportError as exc:
        jev_result = {"error": str(exc)[:300], "source": exc.source}

    try:
        alt_result = jev_alt_model.answer(state, questions, timeout=alt_timeout or timeout)
    except jev_alt_model.AltModelError as exc:
        alt_result = {"error": str(exc)[:300], "source": jev_alt_model.SOURCE}

    _log_alt_model_event(
        questions,
        mode="second_opinion",
        reason=None if "error" not in jev_result and "error" not in alt_result else "partial_or_full_failure",
    )
    return {"jev": jev_result, "alt_model": alt_result, "_meta": {"mode": "second_opinion"}}
