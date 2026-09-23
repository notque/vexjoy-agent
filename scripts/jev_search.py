"""Checkpointed beam search with Jev as the step judge.

Long agent tasks fail from branching, not reasoning. Jev judges a bounded set of
options cheaply but only sees the current snapshot, so per-step error compounds
over a long horizon. This module splits the horizon:

- A caller (usually an LLM) supplies checkpoints: subgoals a few steps apart.
- Between checkpoints, code expands candidate next states and Jev ranks them by
  progress toward the current subgoal. Code keeps the top ``width`` branches and
  records pruned ones as dead ends.
- A near-tie at the beam boundary (the last kept candidate and the first pruned
  one within ``margin``; with ``width=1`` that is the top two), a "no candidate
  makes progress" pick, or a missing or malformed answer escalates to a caller-supplied reasoning function. With none, the search
  stops with status ``escalated`` instead of guessing.
- A small ``TaskLedger`` carries goal, facts, and dead ends as bounded, labeled
  state, so context compression cannot silently drop them.

Do not use it for short tasks (just ask one Choice), for unbounded answer spaces
(Jev only picks among candidates code supplies), or when a program can compute
progress (use the program).

No network at import: the default judge (``jev_transport.evaluate_packed``) is
imported on first use.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar, cast

import jev_limits

S = TypeVar("S")

# --- Bounds (characters unless named tokens) ---
GOAL_CHARS = 400
CHECKPOINT_CHARS = 300
LEDGER_ITEM_CHARS = 200
CANDIDATE_CHARS = 300
LABEL_CHARS = 80
LEDGER_TOKEN_BUDGET = 1_200
# A Choice cannot be split across requests, so it is used only while every
# candidate fits one request; above this count or size, per-candidate Scores.
MAX_CHOICE_OPTIONS = 12
REQUEST_TARGET_TOKENS = jev_limits.TARGET_REQUEST_TOKENS
DEFAULT_MARGIN = 0.1
DEFAULT_TIMEOUT_S = 10.0

# Reserved Choice option: lets Jev say every candidate is a step backward.
NO_PROGRESS = "no candidate makes progress"
_PROBABILITY_SUM_TOLERANCE = 0.05

# Score levels, low to high; each a standalone situation.
PROGRESS_LEVELS = [
    "Moves away from the subgoal, repeats an entry in `ledger.dead_ends`, or changes nothing the subgoal needs.",
    "Touches the subgoal but leaves all of its main remaining work undone.",
    "Completes a clear part of the remaining work toward the subgoal.",
    "Meets the subgoal, or leaves only a trivial final step.",
]

Status = Literal["done", "exhausted", "step_limit", "escalated", "failed"]
Evaluate = Callable[..., dict[str, Any]]


def _clip(text: str, limit: int) -> str:
    """Keep the head of ``text`` within ``limit`` chars and say how much was cut."""
    text = " ".join(str(text).split())
    if len(text) <= limit:
        return text
    notice = f" [{len(text) - limit} chars omitted]"
    return text[: max(0, limit - len(notice))] + notice


@dataclass
class TaskLedger:
    """Structured task memory that survives compression.

    Attributes:
        goal: The whole task, in one or two sentences.
        checkpoint: The current subgoal.
        facts: Observed facts, oldest first.
        dead_ends: Pruned or failed branches, oldest first.
    """

    goal: str
    checkpoint: str = ""
    facts: list[str] = field(default_factory=list)
    dead_ends: list[str] = field(default_factory=list)

    def add_fact(self, fact: str) -> None:
        """Append a fact unless it is already recorded."""
        if fact not in self.facts:
            self.facts.append(fact)

    def add_dead_end(self, dead_end: str) -> None:
        """Append a dead end unless it is already recorded."""
        if dead_end not in self.dead_ends:
            self.dead_ends.append(dead_end)

    def render(self, budget_tokens: int = LEDGER_TOKEN_BUDGET) -> dict[str, Any]:
        """Render bounded, labeled state within ``budget_tokens``.

        Drops the oldest items first, from whichever list is longer, and records
        how many were dropped in ``omitted``.

        Raises:
            ValueError: The budget cannot hold even the goal and checkpoint.
        """
        facts = [_clip(f, LEDGER_ITEM_CHARS) for f in self.facts]
        dead_ends = [_clip(d, LEDGER_ITEM_CHARS) for d in self.dead_ends]
        dropped_facts = dropped_dead = 0

        def build() -> dict[str, Any]:
            out: dict[str, Any] = {
                "goal": _clip(self.goal, GOAL_CHARS),
                "checkpoint": _clip(self.checkpoint, CHECKPOINT_CHARS),
                "facts": facts,
                "dead_ends": dead_ends,
            }
            if dropped_facts or dropped_dead:
                out["omitted"] = f"{dropped_facts} oldest facts and {dropped_dead} oldest dead ends omitted"
            return out

        rendered = build()
        while jev_limits.estimate_tokens(rendered) > budget_tokens:
            if not facts and not dead_ends:
                raise ValueError(f"ledger budget {budget_tokens} tokens cannot hold the goal and checkpoint")
            if len(dead_ends) >= len(facts):
                dead_ends.pop(0)
                dropped_dead += 1
            else:
                facts.pop(0)
                dropped_facts += 1
            rendered = build()
        return rendered


def progress_questions(subgoal: str, candidates: Sequence[str]) -> dict[str, dict[str, Any]]:
    """Build the Jev question(s) that rank candidate next states by progress.

    Candidate descriptions live in state at ``candidates.<label>``; questions
    refer to them by label. Up to ``MAX_CHOICE_OPTIONS`` labels get one Choice
    (relative ranking from ``probabilities``, plus a ``NO_PROGRESS`` option).
    More labels get one Score per candidate (absolute, packable across requests).

    Args:
        subgoal: The current checkpoint.
        candidates: Unique candidate labels.

    Returns:
        Question ID to question. IDs are ``progress`` (Choice) or ``progress:<label>`` (Score).
    """
    labels = list(candidates)
    if len(set(labels)) != len(labels) or NO_PROGRESS in labels:
        raise ValueError("candidate labels must be unique and must not use the reserved NO_PROGRESS label")
    focus = f"Subgoal: {_clip(subgoal, CHECKPOINT_CHARS)}"
    if len(labels) <= MAX_CHOICE_OPTIONS:
        options: dict[str, Any] = dict.fromkeys(labels)
        options[NO_PROGRESS] = {
            "what": "Every entry in `candidates` moves away from the subgoal or repeats `ledger.dead_ends`.",
        }
        return {
            "progress": {
                "type": "choice",
                "instructions": {
                    "question": "Which next state in `candidates` makes the most progress toward the subgoal?",
                    "inspect": ["candidates", "ledger.facts", "ledger.dead_ends"],
                    "focus": focus,
                    "note": "Judge progress on the subgoal only; a repeat of `ledger.dead_ends` is no progress.",
                },
                "criteria": options,
            }
        }
    return _score_questions(subgoal, labels)


@dataclass
class Escalation:
    """What the reasoning function receives when Jev cannot decide.

    Attributes:
        reason: ``tie``, ``no_progress``, or ``invalid_answer``.
        subgoal: The current checkpoint.
        ledger: Rendered ledger state.
        options: ``(label, description)`` pairs, best first when a ranking exists.
        ranking: ``(label, progress)`` pairs from Jev, or empty when the answer failed.
    """

    reason: str
    subgoal: str
    ledger: dict[str, Any]
    options: list[tuple[str, str]]
    ranking: list[tuple[str, float]]


@dataclass
class SearchResult(Generic[S]):
    """Outcome of a search.

    Attributes:
        path: Labels from the start state to ``state``.
        status: ``done``, ``exhausted``, ``step_limit``, ``escalated``, or ``failed``.
        state: The final state of the lead branch, or ``None`` when no branch exists.
        escalations: Times the reasoning function was asked (or would have been).
        calls: Jev requests sent.
        steps: Expansion rounds run.
        reason: Why the search stopped, for logs.
        ledger: The ledger after the search.
        checkpoints_reached: Subgoals met (``checkpoint_search`` only).
    """

    path: list[str]
    status: Status
    state: S | None
    escalations: int = 0
    calls: int = 0
    steps: int = 0
    reason: str = ""
    ledger: TaskLedger | None = None
    checkpoints_reached: int = 0


@dataclass
class _Branch(Generic[S]):
    path: list[str]
    state: S


def _default_evaluate() -> Evaluate:
    import jev_transport  # deferred: loads env and transport config

    return jev_transport.evaluate_packed


def _unique_keys(candidates: list[_Branch[S]]) -> list[str]:
    """Give each candidate a unique, readable label for Jev (label over index)."""
    keys: list[str] = []
    seen: set[str] = {NO_PROGRESS}
    for branch in candidates:
        base = _clip(branch.path[-1], LABEL_CHARS)
        key = base
        if key in seen and len(branch.path) > 1:
            key = f"{base} (after {_clip(branch.path[-2], LABEL_CHARS)})"
        n = 2
        while key in seen:
            key = f"{base} #{n}"
            n += 1
        seen.add(key)
        keys.append(key)
    return keys


def _plan_requests(
    ledger_state: dict[str, Any], subgoal: str, descriptions: dict[str, str]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Return ``(state, questions)`` requests, each at or under ``REQUEST_TARGET_TOKENS``."""
    state = {"ledger": ledger_state, "candidates": descriptions}
    questions = progress_questions(subgoal, list(descriptions))
    if "progress" in questions and jev_limits.estimate_tokens({"state": state, "questions": questions}) <= (
        REQUEST_TARGET_TOKENS
    ):
        return [(state, questions)]
    # Score per candidate; each request carries only its own candidates.
    requests: list[tuple[dict[str, Any], dict[str, Any]]] = []
    chunk: dict[str, str] = {}
    labels = list(descriptions)
    base = jev_limits.estimate_tokens({"state": {"ledger": ledger_state, "candidates": {}}, "questions": {}})
    used = base
    for label in labels:
        one = {label: descriptions[label]}
        cost = jev_limits.estimate_tokens(one) + jev_limits.estimate_tokens(_score_questions(subgoal, one))
        if base + cost > REQUEST_TARGET_TOKENS:
            raise jev_limits.RequestTooLarge(f"ledger plus one candidate is ~{base + cost} tokens; shrink the ledger")
        if chunk and used + cost > REQUEST_TARGET_TOKENS:
            requests.append(_score_request(ledger_state, subgoal, chunk))
            chunk, used = {}, base
        chunk[label] = descriptions[label]
        used += cost
    if chunk:
        requests.append(_score_request(ledger_state, subgoal, chunk))
    return requests


def _score_questions(subgoal: str, labels: Iterable[str]) -> dict[str, dict[str, Any]]:
    """One progress Score per label; used above the Choice cutoff and for every split request."""
    return {
        f"progress:{label}": {
            "type": "score",
            "instructions": {
                "question": f"How much progress toward the subgoal does `candidates.{label}` make?",
                "inspect": [f"candidates.{label}", "ledger.dead_ends"],
                "focus": f"Subgoal: {_clip(subgoal, CHECKPOINT_CHARS)}",
            },
            "criteria": PROGRESS_LEVELS,
        }
        for label in labels
    }


def _score_request(
    ledger_state: dict[str, Any], subgoal: str, chunk: dict[str, str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    return {"ledger": ledger_state, "candidates": dict(chunk)}, _score_questions(subgoal, chunk)


def _probability(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    v = float(value)
    return v if 0.0 <= v <= 1.0 and not math.isnan(v) else None


def _read_ranking(questions: dict[str, Any], answers: Any) -> tuple[list[tuple[str, float]], bool] | None:
    """Turn answers into ``(label, progress in [0, 1])`` best first, plus a no-progress flag.

    Returns ``None`` when any required answer is missing or malformed.
    """
    if not isinstance(answers, dict):
        return None
    if "progress" in questions:
        answer = answers.get("progress")
        if not isinstance(answer, dict) or not isinstance(answer.get("choice"), str):
            return None
        probs = answer.get("probabilities")
        options = questions["progress"]["criteria"]
        if not isinstance(probs, dict) or answer["choice"] not in options:
            return None
        read = {key: _probability(probs.get(key)) for key in options}
        if any(v is None for v in read.values()):
            return None
        if abs(sum(v for v in read.values() if v is not None) - 1.0) > _PROBABILITY_SUM_TOLERANCE:
            return None
        ranking = sorted(((k, v) for k, v in read.items() if k != NO_PROGRESS and v is not None), key=lambda kv: -kv[1])
        no_progress = max(read, key=lambda k: read[k] or 0.0) == NO_PROGRESS
        return ranking, no_progress
    ranking = []
    for qid, question in questions.items():
        answer = answers.get(qid)
        top = len(question["criteria"]) - 1
        if not isinstance(answer, dict):
            return None
        score = answer.get("score")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0.0 <= float(score) <= top:
            return None
        # score is a probability-weighted mean of 0-based levels; normalize to [0, 1] to rank.
        ranking.append((qid.split(":", 1)[1], float(score) / top))
    ranking.sort(key=lambda kv: -kv[1])
    return ranking, False


def _judge(
    requests: list[tuple[dict[str, Any], dict[str, Any]]], evaluate: Evaluate, timeout: float
) -> tuple[list[tuple[str, float]], bool] | None:
    """Send every request at once and merge rankings. Any failure fails the whole judgment."""
    for state, questions in requests:
        jev_limits.check_request_size(state, questions)

    def send(req: tuple[dict[str, Any], dict[str, Any]]) -> tuple[list[tuple[str, float]], bool] | None:
        state, questions = req
        try:
            response = evaluate(state, questions, timeout=timeout)
        except Exception:  # transport, timeout, or size refusal: counts as a failed answer
            return None
        return _read_ranking(questions, response.get("answers") if isinstance(response, dict) else None)

    if len(requests) == 1:
        parts = [send(requests[0])]
    else:
        with ThreadPoolExecutor(max_workers=min(len(requests), jev_limits.SPLIT_MAX_IN_FLIGHT)) as pool:
            parts = list(pool.map(send, requests))
    if any(p is None for p in parts):
        return None
    ranking = sorted((kv for p in parts if p is not None for kv in p[0]), key=lambda kv: -kv[1])
    return ranking, any(p is not None and p[1] for p in parts)


def beam_search(
    start: S,
    expand: Callable[[S], Iterable[tuple[str, S]]],
    subgoal: str,
    *,
    is_done: Callable[[S], bool],
    width: int = 3,
    max_steps: int = 8,
    escalate: Callable[[Escalation], str | None] | None = None,
    evaluate: Evaluate | None = None,
    ledger: TaskLedger | None = None,
    margin: float = DEFAULT_MARGIN,
    describe: Callable[[S], str] = str,
    timeout: float = DEFAULT_TIMEOUT_S,
    ledger_tokens: int = LEDGER_TOKEN_BUDGET,
) -> SearchResult[S]:
    """Search toward one subgoal, keeping the ``width`` branches Jev ranks highest.

    Code checks ``is_done`` before any Jev call. When candidates fit in the beam,
    no call is made. Otherwise Jev ranks them; a boundary gap under ``margin``
    (last kept minus first pruned; the top two when ``width`` is 1), a
    ``NO_PROGRESS`` pick, or a missing or malformed answer escalates. A tie inside
    the beam does not escalate: both branches are kept.

    Args:
        start: Initial state.
        expand: Caller code: ``state -> [(label, next_state), ...]``.
        subgoal: Current checkpoint.
        is_done: Program check for the subgoal; Jev never decides "done".
        width: Branches kept per step.
        max_steps: Expansion rounds before ``step_limit``.
        escalate: Reasoning function; returns the chosen label or ``None`` to stop.
        evaluate: Jev call ``(state, questions, *, timeout) -> response``.
            Defaults to ``jev_transport.evaluate_packed``.
        ledger: Carried memory; created from ``subgoal`` when omitted.
        margin: Minimum gap in [0, 1] between the last kept and first pruned candidate
            to act without escalation.
        describe: Renders a state for Jev; clipped to ``CANDIDATE_CHARS``.
        timeout: Per-request timeout in seconds.
        ledger_tokens: Token budget for the rendered ledger.

    Returns:
        A ``SearchResult``; ``path`` and ``state`` belong to the lead branch.
    """
    if width < 1 or max_steps < 0:
        raise ValueError("width must be >= 1 and max_steps >= 0")
    ledger = ledger if ledger is not None else TaskLedger(goal=subgoal)
    ledger.checkpoint = subgoal
    judge = evaluate
    beam: list[_Branch[S]] = [_Branch([], start)]
    calls = escalations = 0

    def result(status: Status, branch: _Branch[S] | None, steps: int, reason: str) -> SearchResult[S]:
        return SearchResult(
            path=list(branch.path) if branch else [],
            status=status,
            state=branch.state if branch else None,
            escalations=escalations,
            calls=calls,
            steps=steps,
            reason=reason,
            ledger=ledger,
        )

    if is_done(start):
        return result("done", beam[0], 0, "start state meets the subgoal")
    for step in range(1, max_steps + 1):
        candidates = [_Branch([*b.path, label], nxt) for b in beam for label, nxt in expand(b.state)]
        if not candidates:
            return result("exhausted", beam[0], step, "no branch has a next state")
        for branch in candidates:
            if is_done(branch.state):
                return result("done", branch, step, "subgoal met")
        if len(candidates) <= width:
            beam = candidates
            continue

        keys = _unique_keys(candidates)
        by_key = dict(zip(keys, candidates))
        descriptions = {k: _clip(describe(b.state), CANDIDATE_CHARS) for k, b in by_key.items()}
        ledger_state = ledger.render(ledger_tokens)
        requests = _plan_requests(ledger_state, subgoal, descriptions)
        if judge is None:
            judge = _default_evaluate()
        calls += len(requests)
        judged = _judge(requests, judge, timeout)

        reason = ""
        ranking: list[tuple[str, float]] = []
        if judged is None:
            reason = "invalid_answer"
        else:
            ranking, no_progress = judged
            if no_progress:
                reason = "no_progress"
            elif len(ranking) > width and ranking[width - 1][1] - ranking[width][1] < margin:
                # Only the tie at the cut changes which branches survive.
                reason = "tie"
        order = [k for k, _ in ranking] if ranking else list(keys)

        if reason:
            escalations += 1
            if escalate is None:
                return result("escalated", beam[0], step, f"{reason}; no escalate function")
            pick = escalate(
                Escalation(
                    reason=reason,
                    subgoal=subgoal,
                    ledger=ledger_state,
                    options=[(k, descriptions[k]) for k in order],
                    ranking=ranking,
                )
            )
            if pick is None:
                return result("escalated", beam[0], step, f"{reason}; escalate declined")
            if pick not in by_key:
                return result("failed", beam[0], step, f"{reason}; escalate returned an unknown label")
            order = [pick, *(k for k in order if k != pick)]

        beam = [by_key[k] for k in order[:width]]
        for key in order[width:]:
            ledger.add_dead_end(f"{' > '.join(by_key[key].path)} (pruned for: {_clip(subgoal, LABEL_CHARS)})")
    return result("step_limit", beam[0], max_steps, f"subgoal not met in {max_steps} steps")


def checkpoint_search(
    start: S,
    subgoals: Sequence[str],
    expand: Callable[[S], Iterable[tuple[str, S]]],
    *,
    is_done_for: Callable[[str], Callable[[S], bool]],
    ledger: TaskLedger | None = None,
    **kwargs: Any,
) -> SearchResult[S]:
    """Run ``beam_search`` per subgoal, carrying the ledger; stop at the first unmet one.

    Args:
        start: Initial state.
        subgoals: Checkpoints in order, a few steps apart.
        expand: Caller code: ``state -> [(label, next_state), ...]``.
        is_done_for: Returns the program check for one subgoal.
        ledger: Carried memory; created from the last subgoal when omitted.
        **kwargs: Passed to ``beam_search`` (width, max_steps, escalate, evaluate, margin, ...).

    Returns:
        A ``SearchResult`` with the joined path, summed calls and escalations, and
        ``checkpoints_reached``. Its status is ``done`` only when every subgoal was met.
    """
    if not subgoals:
        raise ValueError("at least one subgoal is required")
    ledger = ledger if ledger is not None else TaskLedger(goal=subgoals[-1])
    path: list[str] = []
    state: S = start
    calls = escalations = steps = 0
    for reached, subgoal in enumerate(subgoals):
        part = beam_search(state, expand, subgoal, is_done=is_done_for(subgoal), ledger=ledger, **kwargs)
        path += part.path
        calls += part.calls
        escalations += part.escalations
        steps += part.steps
        if part.status != "done":
            return SearchResult(
                path=path,
                status=part.status,
                state=part.state,
                escalations=escalations,
                calls=calls,
                steps=steps,
                reason=f"checkpoint {reached + 1} ({_clip(subgoal, LABEL_CHARS)}): {part.reason}",
                ledger=ledger,
                checkpoints_reached=reached,
            )
        state = cast(S, part.state)  # done always carries a branch
        ledger.add_fact(f"reached checkpoint: {_clip(subgoal, LEDGER_ITEM_CHARS)}")
    return SearchResult(
        path=path,
        status="done",
        state=state,
        escalations=escalations,
        calls=calls,
        steps=steps,
        reason="every checkpoint met",
        ledger=ledger,
        checkpoints_reached=len(subgoals),
    )
