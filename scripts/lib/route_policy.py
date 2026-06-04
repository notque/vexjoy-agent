"""Pure health-aware re-rank policy for routing decisions.

`health_adjust()` decides whether the semantic routing pick stands, is demoted
to a healthier alternate, or is tie-broken toward a healthier alternate. It is
PURE: no DB, no clock, no filesystem, no mutation of its inputs. The caller
(skills/meta/do Step 1.5) supplies the semantic pick, the alternates, the T1
weight map (`route-weights --json`), and the set of force-routed pairs.

Design (frozen spec T2):
  - Evidence gate: never demote a pick with n < MIN_OBSERVATIONS (5).
  - Floor demote: demote ONLY if confidence < FLOOR_CONFIDENCE (0.30) AND
    failure >= FLOOR_FAILURES (3) AND n >= MIN_OBSERVATIONS.
  - Force-route / security pairs are NEVER demoted (hard exempt) — checked
    first, before any health logic.
  - Tie-break toward a higher-health alternate ONLY when the semantic
    confidence is "low" (< LOW_CONFIDENCE, 0.35).
  - Default: the semantic pick stands.

On current real data the demote branch cannot fire (zero failure-bearing rows),
so the wiring is instrumentation until negative signal accumulates. The synthetic
replay arm (T7) proves the mechanism on seeded failure data.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

# Gate / floor thresholds (frozen spec T2).
MIN_OBSERVATIONS = 5
FLOOR_CONFIDENCE = 0.30
FLOOR_FAILURES = 3
LOW_CONFIDENCE = 0.35


def _key_of(item: object) -> str | None:
    """Extract the `agent:skill` key from a pick/alternate (str or mapping)."""
    if isinstance(item, str):
        return item
    if isinstance(item, Mapping):
        key = item.get("key")
        return key if isinstance(key, str) else None
    return None


def _is_exempt(key: str, force_route_flags: Iterable[str]) -> bool:
    """True iff `key` is force-routed (by full `agent:skill` pair or skill name).

    The caller may pass either full pairs (``agent:skill``) or bare skill names
    (the manifest keys force_route by skill). Both forms exempt the pick.
    """
    flags = set(force_route_flags)
    if key in flags:
        return True
    skill = key.split(":", 1)[1] if ":" in key else key
    return skill in flags


def _health_score(entry: Mapping[str, object]) -> float:
    """Rank candidates: success rate weighted by confidence. Higher = healthier."""
    n = int(entry.get("n", 0) or 0)
    success = int(entry.get("success", 0) or 0)
    confidence = float(entry.get("confidence", 0.0) or 0.0)
    rate = (success / n) if n > 0 else 0.0
    return rate * confidence


def _is_floor(entry: Mapping[str, object]) -> bool:
    """True iff the entry meets ALL floor-demote conditions."""
    n = int(entry.get("n", 0) or 0)
    failure = int(entry.get("failure", 0) or 0)
    confidence = float(entry.get("confidence", 0.0) or 0.0)
    return confidence < FLOOR_CONFIDENCE and failure >= FLOOR_FAILURES and n >= MIN_OBSERVATIONS


def _healthiest_alternate(
    alternates: Sequence[object],
    weights: Mapping[str, Mapping[str, object]],
    must_beat: float,
) -> str | None:
    """Return the alternate key with the highest health score above `must_beat`.

    Skips alternates with no weight row (no evidence to prefer them).
    Deterministic: ties resolve to the first alternate in input order.
    """
    best_key: str | None = None
    best_score = must_beat
    for alt in alternates:
        alt_key = _key_of(alt)
        if alt_key is None or alt_key not in weights:
            continue
        score = _health_score(weights[alt_key])
        if score > best_score:
            best_score = score
            best_key = alt_key
    return best_key


def health_adjust(
    semantic_pick: Mapping[str, object],
    alternates: Sequence[object],
    weights: Mapping[str, Mapping[str, object]],
    force_route_flags: Iterable[str],
) -> dict[str, object]:
    """Decide the final route given semantic pick + health weights. Pure.

    Args:
        semantic_pick: the LLM's pick. Mapping with ``key`` (``agent:skill``)
            and ``confidence`` (the semantic confidence, 0..1).
        alternates: candidate keys/dicts to re-rank toward (each a str or a
            mapping with ``key``).
        weights: the T1 weight map keyed ``agent:skill`` ->
            {confidence, n, success, failure, last_seen}.
        force_route_flags: pairs or skill names that are force-routed and must
            never be demoted.

    Returns:
        ``{final_pick, action, reason}`` where action is one of
        ``keep`` | ``demote`` | ``tiebreak``.
    """
    pick_key = _key_of(semantic_pick)
    if pick_key is None:
        return {
            "final_pick": None,
            "action": "keep",
            "reason": "no pick key supplied; nothing to adjust",
        }

    # 1) Force-route / security exemption — checked FIRST, before any health.
    if _is_exempt(pick_key, force_route_flags):
        return {
            "final_pick": pick_key,
            "action": "keep",
            "reason": f"force-route exempt: {pick_key} is never demoted",
        }

    entry = weights.get(pick_key)

    # 2) Evidence gate: no row, or n < MIN_OBSERVATIONS => never demote.
    if entry is None:
        return {
            "final_pick": pick_key,
            "action": "keep",
            "reason": "fresh pick: no health evidence; semantic pick stands",
        }
    n = int(entry.get("n", 0) or 0)
    if n < MIN_OBSERVATIONS:
        return {
            "final_pick": pick_key,
            "action": "keep",
            "reason": f"evidence gate: n={n} < {MIN_OBSERVATIONS}; semantic pick stands",
        }

    # 3) Floor demote: confidence < 0.30 AND failure >= 3 AND n >= 5.
    if _is_floor(entry):
        target = _healthiest_alternate(alternates, weights, must_beat=_health_score(entry))
        if target is not None:
            conf = float(entry.get("confidence", 0.0) or 0.0)
            fail = int(entry.get("failure", 0) or 0)
            return {
                "final_pick": target,
                "action": "demote",
                "reason": (f"floor demote: {pick_key} (conf={conf:.2f}, fail/n={fail}/{n}) -> {target}"),
            }
        # No healthier alternate to move to — pick stands.
        return {
            "final_pick": pick_key,
            "action": "keep",
            "reason": "floor met but no healthier alternate; semantic pick stands",
        }

    # 4) Low-confidence tie-break: only when the SEMANTIC confidence is low.
    sem_conf = float(semantic_pick.get("confidence", 1.0) or 0.0)
    if sem_conf < LOW_CONFIDENCE:
        target = _healthiest_alternate(alternates, weights, must_beat=_health_score(entry))
        if target is not None:
            return {
                "final_pick": target,
                "action": "tiebreak",
                "reason": (f"low semantic confidence ({sem_conf:.2f}); tie-break toward healthier {target}"),
            }

    # 5) Default: the semantic pick stands.
    return {
        "final_pick": pick_key,
        "action": "keep",
        "reason": "semantic pick stands (healthy / above floor / confident)",
    }
