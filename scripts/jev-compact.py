#!/usr/bin/env python3
"""Jev-powered context compaction: verbatim pruning, zero generation.

Replaces LLM-generated compaction summaries with Jev-judged per-tool-call
keep/drop decisions. Items Jev says are stale get deleted; everything kept
stays verbatim. The LLM never rewrites anything.

Architecture: three tiers applied to compaction.
  Tier 1 (programs): pair tool calls with results, pin recent turns,
    pre-filter obvious keeps/drops (Edit results, Glob listings, acks).
  Tier 2 (Jev): judge each remaining call with criteria-rich Nouls.
  Tier 3 (LLM): not needed — zero generation.

Input: a conversation transcript (list of messages with tool_use/tool_result
blocks) and optionally the last few user prompts as goal context.

Output: a pruned transcript where dropped tool blocks are removed and
truncated results keep only a head + note.

Usage:
    python3 scripts/jev-compact.py --transcript transcript.json --json-compact
    python3 scripts/jev-compact.py --transcript transcript.json --dry-run

Exit codes:
    0 -- always (JSON to stdout; errors to stderr)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import sys
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_redact
import jev_router_common

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REDACT_STATE = True  # run jev_redact.redact_text on every text/tool input placed into Jev state
PRESERVE_RECENT = 6  # newest N messages always pinned
MAX_STATE_TOKENS = 12000
# Jev accepts 64k tokens per request; state plus the longest question must stay
# under 32k. Both limits leave margin for the rough token estimate. State is
# billed once per request, so each request carries as many questions as fit.
MAX_REQUEST_TOKENS = 56000
STATE_HARD_LIMIT_TOKENS = 28000
MAX_REQUESTS_PER_COMPACTION = 4  # past this, the run costs more than it saves
KEEP_THRESHOLD = 0.5
TRUNCATE_HEAD_CHARS = 300
MIN_REDUCTION_RATIO = 0.25
MAX_GOAL_PROMPTS = 3
MAX_GOAL_CHARS = 500
MAX_INPUT_CHARS_STAGES = [1000, 200, 60]
ABRIDGE_TEXT_THRESHOLD = 550
ABRIDGE_HEAD = 400
ABRIDGE_TAIL = 150
DEFAULT_TIMEOUT = 10.0

# Per-tool threshold adjustments (lower = more likely to keep)
TOOL_THRESHOLDS: dict[str, float] = {
    "Edit": 0.35,  # edits are high-value; keep more aggressively
    "Write": 0.35,
    "NotebookEdit": 0.35,
}


# ---------------------------------------------------------------------------
# Token estimation (ported from fast-jev-compaction state.ts:28-38)
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[a-zA-Z]+")
_DIGIT_RE = re.compile(r"[0-9]+")


def estimate_tokens(text: str) -> int:
    """Estimate token count without a tokenizer.

    Words cost 1 token per 6 letters, digits cost 0.5 tokens each,
    other symbols cost 0.9 each. Calibrated to land 2-18% above true
    Jev-reported counts for JSON-heavy states.
    """
    if not text:
        return 0
    tokens = 0.0
    pos = 0
    for m in _WORD_RE.finditer(text):
        # Count non-word chars before this match
        gap = text[pos : m.start()]
        for ch in gap:
            if ch.isdigit():
                tokens += 0.5
            else:
                tokens += 0.9
        # Word: 1 token per 6 letters
        tokens += len(m.group()) / 6.0
        pos = m.end()
    # Trailing non-word chars
    for ch in text[pos:]:
        if ch.isdigit():
            tokens += 0.5
        else:
            tokens += 0.9
    return int(tokens) + 1


# ---------------------------------------------------------------------------
# Tool call collection and pairing
# ---------------------------------------------------------------------------


def load_transcript_jsonl(path: Path | str) -> list[dict]:
    """Load a Claude Code JSONL transcript as the message list ``compact()`` takes.

    Each row is one JSON object. Rows with ``type`` of ``user`` or
    ``assistant`` carry a ``message`` dict with ``role`` and ``content``
    (a string or a list of ``text`` / ``tool_use`` / ``tool_result`` blocks);
    that dict is what ``collect_tool_calls`` and ``_extract_goal`` read, so it
    is passed through as ``{"role", "content"}``. Every other row type
    (summary, system, compact_boundary, ...) and every unparseable line is
    skipped. A missing file yields an empty list.
    """
    path = Path(path)
    messages: list[dict] = []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(row, dict) or row.get("type") not in ("user", "assistant"):
                    continue
                message = row.get("message")
                if not isinstance(message, dict):
                    continue
                role = message.get("role") or row["type"]
                content = message.get("content")
                if content is None:
                    continue
                messages.append({"role": role, "content": content})
    except OSError:
        return []
    return messages


def collect_tool_calls(
    messages: list[dict],
    preserve_recent: int = PRESERVE_RECENT,
) -> list[dict]:
    """Pair tool_use blocks with their tool_result by tool_use_id.

    Returns a list of call dicts:
      {id, seq_id, tool, input, result, result_chars, call_index,
       result_index, pinned, call_block, result_block}

    A call is pinned if its message index is 0 or within the newest
    `preserve_recent` messages.
    """
    # Build tool_use_id -> (tool_use_block, message_index) map
    uses: dict[str, tuple[dict, int]] = {}
    results: dict[str, tuple[dict, int]] = {}

    for i, msg in enumerate(messages):
        content = msg.get("content", [])
        if isinstance(content, str):
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                uid = block.get("id", "")
                if uid:
                    uses[uid] = (block, i)
            elif block.get("type") == "tool_result":
                uid = block.get("tool_use_id", "")
                if uid:
                    results[uid] = (block, i)

    total = len(messages)
    calls: list[dict] = []
    seq = 0

    for uid, (use_block, use_idx) in uses.items():
        if uid not in results:
            continue
        res_block, res_idx = results[uid]

        seq += 1
        seq_id = f"t{seq}"

        # Pin: first message or within newest preserve_recent
        pinned = (
            use_idx == 0 or res_idx == 0 or use_idx >= total - preserve_recent or res_idx >= total - preserve_recent
        )

        # Extract result text
        res_content = res_block.get("content", "")
        if isinstance(res_content, list):
            parts = []
            for part in res_content:
                if isinstance(part, dict) and part.get("type") == "text":
                    parts.append(part.get("text", ""))
                elif isinstance(part, str):
                    parts.append(part)
            res_text = "\n".join(parts)
        elif isinstance(res_content, str):
            res_text = res_content
        else:
            res_text = str(res_content)

        # Extract input
        inp = use_block.get("input", {})
        if isinstance(inp, dict):
            inp_text = json.dumps(inp, separators=(",", ":"))
        else:
            inp_text = str(inp)

        calls.append(
            {
                "id": uid,
                "seq_id": seq_id,
                "tool": use_block.get("name", "unknown"),
                "input": inp_text,
                "result": res_text,
                "result_chars": len(res_text),
                "call_index": use_idx,
                "result_index": res_idx,
                "pinned": pinned,
                "call_block": use_block,
                "result_block": res_block,
                "is_error": res_block.get("is_error", False),
            }
        )

    return calls


# ---------------------------------------------------------------------------
# Tier 1: Programmatic pre-filters
# ---------------------------------------------------------------------------


def _is_obvious_drop(call: dict) -> bool | None:
    """Return True for obvious drops, False for obvious keeps, None for Jev.

    Tier 1 deterministic pre-filter. Reduces Jev call count and improves
    accuracy by removing noise from the judgment set.
    """
    tool = call["tool"]
    result = call["result"]
    result_len = call["result_chars"]
    inp = call["input"]
    is_err = call.get("is_error", False)

    # Obvious keeps: never drop these
    # - Most recent Edit/Write result (the change record)
    # - Error results that are long (likely contain diagnostic info)
    if is_err and result_len > 200:
        return False  # keep

    # Obvious drops:
    # - Glob results (just file listings, always reproducible)
    if tool == "Glob":
        return True

    # - Very short acknowledgment results (< 50 chars, not errors)
    if not is_err and result_len < 50 and tool in ("Edit", "Write", "NotebookEdit"):
        # Short ack like "OK" or empty result from a successful edit
        # The call itself may matter (what was edited) but the result is trivial
        return None  # let Jev decide, but this is a hint

    # - `ls` / `pwd` / simple directory listing commands
    if tool == "Bash":
        try:
            cmd = json.loads(inp).get("command", "") if inp.startswith("{") else inp
        except (json.JSONDecodeError, AttributeError):
            cmd = inp
        cmd_stripped = cmd.strip()
        if cmd_stripped in ("ls", "pwd", "ls -la", "ls -l", "ls -a"):
            return True
        # `git status` is reproducible
        if cmd_stripped.startswith("git status"):
            return True

    # - ListDirectory results
    if tool == "ListDirectory":
        return True

    return None  # Jev decides


def prefilter_calls(calls: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    """Apply Tier 1 pre-filters. Returns (candidates_for_jev, prefilter_decisions)."""
    candidates: list[dict] = []
    decisions: dict[str, dict] = {}

    for call in calls:
        if call["pinned"]:
            decisions[call["seq_id"]] = {
                "action": "keep",
                "reason": "pinned",
                "keep_call": 1.0,
                "keep_result": 1.0,
            }
            continue

        verdict = _is_obvious_drop(call)
        if verdict is True:
            decisions[call["seq_id"]] = {
                "action": "drop_call",
                "reason": "prefilter_obvious_drop",
                "keep_call": 0.0,
                "keep_result": 0.0,
            }
        elif verdict is False:
            decisions[call["seq_id"]] = {
                "action": "keep",
                "reason": "prefilter_obvious_keep",
                "keep_call": 1.0,
                "keep_result": 1.0,
            }
        else:
            candidates.append(call)

    return candidates, decisions


# ---------------------------------------------------------------------------
# State building and fitting
# ---------------------------------------------------------------------------


def _extract_goal(messages: list[dict]) -> str:
    """Extract goal from the last few user prompts."""
    user_texts: list[str] = []
    for msg in reversed(messages):
        if msg.get("role") != "user":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            text_parts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
                elif isinstance(block, str):
                    text_parts.append(block)
            text = " ".join(text_parts)
        elif isinstance(content, str):
            text = content
        else:
            continue
        if text.strip():
            user_texts.append(text.strip()[:MAX_GOAL_CHARS])
        if len(user_texts) >= MAX_GOAL_PROMPTS:
            break

    user_texts.reverse()
    goal = "\n---\n".join(user_texts) if user_texts else ""
    return _redact_for_state(goal)


def _redact_for_state(text: str) -> str:
    """Redact secrets from text bound for Jev state when REDACT_STATE is on."""
    if not REDACT_STATE or not text:
        return text
    return jev_redact.redact_text(text)[0]


def _build_history_entry(
    msg: dict,
    idx: int,
    calls_by_msg: dict[int, list[dict]],
    input_limit: int,
    abridge: bool,
    collapse: bool,
    pinned_indices: set[int],
) -> dict | None:
    """Build one history entry for the Jev state."""
    role = msg.get("role", "unknown")

    # Extract text
    content = msg.get("content", "")
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)
        text = " ".join(text_parts)
    elif isinstance(content, str):
        text = content
    else:
        text = ""
    text = _redact_for_state(text)

    # Collapse non-pinned messages
    if collapse and idx not in pinned_indices and not calls_by_msg.get(idx):
        if not text.strip():
            return None
        return {"i": idx, "role": role, "text": f"[... {len(text)} chars omitted ...]"}

    # Abridge long non-pinned text
    if abridge and idx not in pinned_indices and len(text) > ABRIDGE_TEXT_THRESHOLD:
        text = (
            text[:ABRIDGE_HEAD]
            + f"\n[... {len(text) - ABRIDGE_HEAD - ABRIDGE_TAIL} chars omitted ...]\n"
            + text[-ABRIDGE_TAIL:]
        )

    entry: dict = {"i": idx, "role": role, "text": text}

    # Add tool calls for this message
    msg_calls = calls_by_msg.get(idx, [])
    if msg_calls:
        tc_list = []
        for call in msg_calls:
            inp = call["input"][:input_limit] if len(call["input"]) > input_limit else call["input"]
            inp = _redact_for_state(inp)
            status = "error" if call.get("is_error") else "ok"
            tc_list.append(
                {
                    "id": call["seq_id"],
                    "tool": call["tool"],
                    "input": inp,
                    "result": f"{status}, {call['result_chars']} chars (omitted)",
                }
            )
        entry["tool_calls"] = tc_list

    return entry


def fit_state(
    messages: list[dict],
    calls: list[dict],
    goal: str,
    max_tokens: int = MAX_STATE_TOKENS,
) -> dict:
    """Build the Jev state, shrinking in stages until it fits.

    Stages (applied one at a time):
    1. full: tool inputs truncated to 1000 chars
    2. inputs<=200: truncated to 200
    3. inputs<=60: truncated to 60
    4. texts abridged: long message texts head+tail
    5. old messages collapsed: text replaced with char count
    6. drop text-only messages: non-pinned messages without tool calls removed
    """
    # Index calls by message index
    calls_by_msg: dict[int, list[dict]] = {}
    pinned_indices: set[int] = set()
    for call in calls:
        calls_by_msg.setdefault(call["call_index"], []).append(call)
        if call["pinned"]:
            pinned_indices.add(call["call_index"])
            pinned_indices.add(call["result_index"])

    # Also pin the most recent messages
    total = len(messages)
    for i in range(max(0, total - PRESERVE_RECENT), total):
        pinned_indices.add(i)
    # Always pin first message
    pinned_indices.add(0)

    context_text = (
        "A coding assistant conversation is being compacted to free context. "
        "`history` is the whole conversation so far, oldest first; tool outputs "
        "are replaced by a short `result` note and long texts may be abridged. "
        "Each question asks whether one tool call, or the full output of that "
        "call, still needs to stay in the history verbatim. Whatever is not kept "
        "is deleted permanently, but the assistant can always re-run a tool or "
        "re-read a file."
    )

    stages = [
        ("full", 1000, False, False, False),
        ("inputs<=200", 200, False, False, False),
        ("inputs<=60", 60, False, False, False),
        ("texts_abridged", 60, True, False, False),
        ("collapsed", 60, True, True, False),
        ("drop_text_only", 60, True, True, True),
    ]

    for stage_name, input_limit, abridge, collapse, drop_text_only in stages:
        history: list[dict] = []
        for i, msg in enumerate(messages):
            entry = _build_history_entry(msg, i, calls_by_msg, input_limit, abridge, collapse, pinned_indices)
            if entry is None:
                continue
            if drop_text_only and i not in pinned_indices and not calls_by_msg.get(i):
                continue
            history.append(entry)

        state = {
            "context": context_text,
            "goal": goal,
            "history": history,
        }

        state_json = json.dumps(state, separators=(",", ":"))
        tokens = estimate_tokens(state_json)

        if tokens <= max_tokens:
            return state

    # If we still can't fit, return the smallest version
    return state  # type: ignore[possibly-undefined]


# ---------------------------------------------------------------------------
# Jev questions with criteria blocks
# ---------------------------------------------------------------------------


def questions_for(call: dict) -> dict:
    """Build Jev questions for one tool call.

    Two core Nouls with criteria blocks (improvement over fast-jev-compaction's
    bare instructions), plus additional targeted questions for richer signal.
    """
    seq_id = call["seq_id"]
    tool = call["tool"]
    result_chars = call["result_chars"]

    questions: dict[str, dict] = {}

    # Question 1: keep the call?
    questions[f"call_{seq_id}"] = {
        "type": "noul",
        "instructions": {
            "question": (
                f"Tool call {seq_id} ({tool}) should stay in the history: "
                f"knowing this call was made, with its input, still matters "
                f"for what the assistant does next."
            ),
            "criteria": {
                "true": (
                    "The call's input or the fact it was made is referenced, "
                    "constrains, or informs later actions. A Read of a file "
                    "that was then edited counts. An error that led to a fix "
                    "counts. A constraint or configuration that is still active "
                    "counts."
                ),
                "false": (
                    "The call was exploratory, its result was superseded by a "
                    "later call to the same tool on the same target, or its "
                    "input is fully captured in later context. A Glob or ls "
                    "whose results were consumed and not needed again."
                ),
            },
        },
    }

    # Question 2: keep the result verbatim?
    questions[f"result_{seq_id}"] = {
        "type": "noul",
        "instructions": {
            "question": (
                f"The full output of tool call {seq_id} ({tool}, "
                f"{result_chars} chars) should stay in the history verbatim: "
                f"the assistant still needs its contents and re-running the "
                f"tool would not reproduce it."
            ),
            "criteria": {
                "true": (
                    "The result text contains information not available "
                    "elsewhere in the history that the assistant may need: "
                    "error details, file contents being modified, constraint "
                    "definitions, test output revealing a pattern. Re-running "
                    "the tool would not reproduce it (file changed, transient "
                    "error, command output differs)."
                ),
                "false": (
                    "The result is a simple acknowledgment, a file listing "
                    "whose contents are available from later reads, a passing "
                    "test whose status is noted in assistant text, or output "
                    "that can be reproduced by re-running the tool."
                ),
            },
        },
    }

    # Question 3: was the result referenced later?
    questions[f"referenced_{seq_id}"] = {
        "type": "noul",
        "instructions": {
            "question": (
                f"The result of tool call {seq_id} ({tool}) was referenced, "
                f"quoted, or used in a later assistant message or tool call "
                f"input — meaning its content informed a decision, fix, or "
                f"response that is still visible in the history."
            ),
        },
    }

    return questions


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------


def _question_tokens(call: dict) -> int:
    """Estimated tokens for one call's questions; a flat figure when the call lacks fields."""
    try:
        return estimate_tokens(json.dumps(questions_for(call)))
    except (KeyError, TypeError):
        return 400


def batch_calls(
    candidates: list[dict],
    state_tokens: int,
    max_request_tokens: int = MAX_REQUEST_TOKENS,
) -> list[list[dict]] | None:
    """Pack candidate calls into as few Jev requests as fit.

    Every request re-sends the whole state, so requests are filled by the
    measured size of their questions. Returns ``None`` when the state is over
    the hard limit or the run needs more than ``MAX_REQUESTS_PER_COMPACTION``
    requests; the caller then leaves the conversation unchanged.
    """
    if not candidates:
        return []
    if state_tokens > STATE_HARD_LIMIT_TOKENS:
        return None

    available = max_request_tokens - state_tokens
    batches: list[list[dict]] = []
    current: list[dict] = []
    used = 0
    for call in candidates:
        cost = _question_tokens(call)
        if current and used + cost > available:
            batches.append(current)
            current, used = [], 0
        current.append(call)
        used += cost
    if current:
        batches.append(current)

    if len(batches) > MAX_REQUESTS_PER_COMPACTION:
        return None
    return batches


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


def decide_call(
    call: dict,
    keep_call: float,
    keep_result: float,
    referenced: float,
) -> dict:
    """Three outcomes based on Jev probabilities.

    Per-tool thresholds: Edit/Write results use a lower threshold (0.35)
    because they record changes that are harder to reproduce.

    The `referenced` signal boosts the keep probability: if Jev says the
    result was referenced later, that's strong evidence to keep it.
    """
    tool = call["tool"]
    threshold = TOOL_THRESHOLDS.get(tool, KEEP_THRESHOLD)

    # Boost keep_result if referenced is high
    effective_keep_result = keep_result
    if referenced >= 0.6:
        effective_keep_result = max(keep_result, 0.5 + (referenced - 0.6) * 0.5)

    if effective_keep_result >= threshold:
        return {
            "action": "keep",
            "reason": "kept",
            "keep_call": round(keep_call, 4),
            "keep_result": round(keep_result, 4),
            "referenced": round(referenced, 4),
        }
    elif keep_call >= threshold:
        return {
            "action": "drop_result",
            "reason": "result_dropped",
            "keep_call": round(keep_call, 4),
            "keep_result": round(keep_result, 4),
            "referenced": round(referenced, 4),
        }
    else:
        return {
            "action": "drop_call",
            "reason": "call_dropped",
            "keep_call": round(keep_call, 4),
            "keep_result": round(keep_result, 4),
            "referenced": round(referenced, 4),
        }


# ---------------------------------------------------------------------------
# Apply decisions to transcript
# ---------------------------------------------------------------------------


def apply_decisions(
    messages: list[dict],
    decisions: dict[str, dict],
    calls: list[dict],
    head_chars: int = TRUNCATE_HEAD_CHARS,
) -> list[dict]:
    """Rebuild transcript by applying keep/drop/truncate decisions.

    Returns a new message list. Messages that lose all content are removed.
    """
    # Build lookup: tool_use_id -> (seq_id, decision)
    id_to_decision: dict[str, tuple[str, dict]] = {}
    for call in calls:
        seq_id = call["seq_id"]
        decision = decisions.get(seq_id)
        if decision:
            id_to_decision[call["id"]] = (seq_id, decision)

    result: list[dict] = []

    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            # Text-only message, keep as-is
            if content.strip():
                result.append(msg)
            continue

        if not isinstance(content, list):
            result.append(msg)
            continue

        new_content: list[dict] = []
        for block in content:
            if not isinstance(block, dict):
                new_content.append(block)
                continue

            block_type = block.get("type", "")

            if block_type == "tool_use":
                uid = block.get("id", "")
                if uid in id_to_decision:
                    _, decision = id_to_decision[uid]
                    if decision["action"] == "drop_call":
                        continue  # drop both call and result
                # keep the tool_use block
                new_content.append(block)

            elif block_type == "tool_result":
                uid = block.get("tool_use_id", "")
                if uid in id_to_decision:
                    _, decision = id_to_decision[uid]
                    if decision["action"] == "drop_call":
                        continue  # drop

                    if decision["action"] == "drop_result":
                        # Truncate result to head_chars + note
                        truncated = _truncate_result(block, head_chars)
                        new_content.append(truncated)
                        continue

                # keep as-is
                new_content.append(block)
            else:
                new_content.append(block)

        # Drop messages that lost all content
        if not new_content:
            continue

        # Check if there's any substance left
        has_substance = False
        for block in new_content:
            if isinstance(block, dict):
                if block.get("type") == "text" and block.get("text", "").strip():
                    has_substance = True
                    break
                if block.get("type") in ("tool_use", "tool_result"):
                    has_substance = True
                    break
            elif isinstance(block, str) and block.strip():
                has_substance = True
                break

        if has_substance:
            new_msg = dict(msg)
            new_msg["content"] = new_content
            result.append(new_msg)

    return result


def _truncate_result(block: dict, head_chars: int) -> dict:
    """Truncate a tool_result block to head_chars + note."""
    new_block = dict(block)
    content = block.get("content", "")

    if isinstance(content, str):
        if len(content) > head_chars:
            truncated = len(content) - head_chars
            new_block["content"] = (
                content[:head_chars] + f"\n[jev-compact truncated {truncated} chars; re-run the tool if needed]"
            )
    elif isinstance(content, list):
        # Truncate text parts
        new_parts: list = []
        total_chars = 0
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                text = part.get("text", "")
                remaining = head_chars - total_chars
                if remaining <= 0:
                    break
                if len(text) > remaining:
                    truncated = len(text) - remaining
                    new_parts.append(
                        {
                            "type": "text",
                            "text": text[:remaining]
                            + f"\n[jev-compact truncated {truncated} chars; re-run the tool if needed]",
                        }
                    )
                    break
                else:
                    new_parts.append(part)
                    total_chars += len(text)
            else:
                new_parts.append(part)
        new_block["content"] = new_parts

    return new_block


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------


def compact(
    messages: list[dict],
    *,
    goal: str | None = None,
    preserve_recent: int = PRESERVE_RECENT,
    max_state_tokens: int = MAX_STATE_TOKENS,
    timeout: float = DEFAULT_TIMEOUT,
    dry_run: bool = False,
) -> dict:
    """Full compaction pipeline: collect → prefilter → fit → batch → ask Jev → decide → apply.

    Returns:
      {messages, decisions, stats: {total_calls, pinned, prefiltered,
       jev_judged, kept, dropped_result, dropped_call, reduction_chars,
       reduction_ratio, latency_ms, jev_calls, usage}}
    """
    t0 = time.monotonic()

    # Check Jev availability
    available, reason = jev_router_common.typesafe_available()
    if not available:
        return {
            "messages": messages,
            "decisions": {},
            "stats": {
                "error": f"Jev unavailable: {reason}",
                "total_calls": 0,
                "reduction_ratio": 0.0,
            },
        }

    api_key = os.environ.get("TYPESAFE_API_KEY", "").strip()

    # Step 1: Collect tool calls
    calls = collect_tool_calls(messages, preserve_recent)

    if not calls:
        return {
            "messages": messages,
            "decisions": {},
            "stats": {
                "total_calls": 0,
                "pinned": 0,
                "prefiltered": 0,
                "jev_judged": 0,
                "reduction_ratio": 0.0,
                "latency_ms": 0,
            },
        }

    # Step 2: Tier 1 pre-filter
    candidates, decisions = prefilter_calls(calls)

    prefiltered_count = len(calls) - len(candidates) - sum(1 for d in decisions.values() if d["reason"] == "pinned")
    pinned_count = sum(1 for d in decisions.values() if d["reason"] == "pinned")

    if not candidates:
        # All calls are pinned or prefiltered; apply and return
        result_messages = apply_decisions(messages, decisions, calls)
        elapsed = (time.monotonic() - t0) * 1000
        original_chars = sum(len(json.dumps(m)) for m in messages)
        result_chars = sum(len(json.dumps(m)) for m in result_messages)
        return {
            "messages": result_messages if not dry_run else messages,
            "decisions": decisions,
            "stats": {
                "total_calls": len(calls),
                "pinned": pinned_count,
                "prefiltered": prefiltered_count,
                "jev_judged": 0,
                "kept": sum(1 for d in decisions.values() if d["action"] == "keep"),
                "dropped_result": sum(1 for d in decisions.values() if d["action"] == "drop_result"),
                "dropped_call": sum(1 for d in decisions.values() if d["action"] == "drop_call"),
                "reduction_chars": original_chars - result_chars,
                "reduction_ratio": round(1 - result_chars / original_chars, 4) if original_chars else 0,
                "latency_ms": round(elapsed, 1),
                "jev_calls": 0,
            },
        }

    # Step 3: Build and fit state
    if goal is None:
        goal = _extract_goal(messages)
    state = fit_state(messages, calls, goal, max_state_tokens)
    state_tokens = estimate_tokens(json.dumps(state, separators=(",", ":")))

    # Step 4: Batch questions
    batches = batch_calls(candidates, state_tokens)
    if batches is None:
        return {
            "messages": messages,
            "decisions": decisions,
            "stats": {
                "over_budget": True,
                "total_calls": len(calls),
                "pinned": pinned_count,
                "prefiltered": prefiltered_count,
                "jev_candidates": len(candidates),
                "jev_batches": 0,
                "state_tokens": state_tokens,
                "ratio": 0.0,
            },
        }

    if dry_run:
        # Report what would happen without calling Jev
        return {
            "messages": messages,
            "decisions": decisions,
            "stats": {
                "dry_run": True,
                "total_calls": len(calls),
                "pinned": pinned_count,
                "prefiltered": prefiltered_count,
                "jev_candidates": len(candidates),
                "jev_batches": len(batches),
                "state_tokens": state_tokens,
            },
        }

    # Step 5: Ask Jev concurrently
    total_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
    jev_latency_ms = 0.0
    jev_call_count = 0
    answers: dict[str, dict] = {}

    def _ask_batch(batch: list[dict]) -> tuple[dict, float, dict | None]:
        """Ask Jev about one batch. Returns (answers, latency_ms, usage)."""
        all_questions: dict[str, dict] = {}
        for call in batch:
            all_questions.update(questions_for(call))

        payload = {
            "model": jev_router_common.JEV_MODEL,
            "state": state,
            "questions": all_questions,
        }

        data, latency = jev_router_common.validated_call_jev(payload, api_key, timeout)
        batch_answers = data.get("answers", {})
        usage = jev_router_common.extract_usage(data)
        return batch_answers, latency, usage

    if len(batches) == 1:
        # Single batch: no threading needed
        try:
            batch_answers, latency, usage = _ask_batch(batches[0])
            answers.update(batch_answers)
            jev_latency_ms = latency
            jev_call_count = 1
            if usage:
                total_usage["input_tokens"] += usage.get("input_tokens", 0)
                total_usage["output_tokens"] += usage.get("output_tokens", 0)
        except Exception as exc:
            print(f"[jev-compact] Jev error: {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr)
            return {
                "messages": messages,
                "decisions": decisions,
                "stats": {
                    "error": f"Jev call failed: {type(exc).__name__}",
                    "total_calls": len(calls),
                    "reduction_ratio": 0.0,
                },
            }
    else:
        # Multiple batches: concurrent
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(batches), 4)) as pool:
            futures = {pool.submit(_ask_batch, batch): batch for batch in batches}
            for future in concurrent.futures.as_completed(futures):
                try:
                    batch_answers, latency, usage = future.result()
                    answers.update(batch_answers)
                    jev_latency_ms = max(jev_latency_ms, latency)
                    jev_call_count += 1
                    if usage:
                        total_usage["input_tokens"] += usage.get("input_tokens", 0)
                        total_usage["output_tokens"] += usage.get("output_tokens", 0)
                except Exception as exc:
                    print(
                        f"[jev-compact] Batch error: {type(exc).__name__}: {str(exc)[:200]}",
                        file=sys.stderr,
                    )

    # Step 6: Decide per call
    for call in candidates:
        seq_id = call["seq_id"]
        keep_call_p = _noul_value(answers, f"call_{seq_id}")
        keep_result_p = _noul_value(answers, f"result_{seq_id}")
        referenced_p = _noul_value(answers, f"referenced_{seq_id}")

        if keep_call_p is None:
            # Missing answer: keep by default (fail-safe)
            decisions[seq_id] = {
                "action": "keep",
                "reason": "missing_answer",
                "keep_call": None,
                "keep_result": None,
                "referenced": None,
            }
        else:
            decisions[seq_id] = decide_call(
                call,
                keep_call_p,
                keep_result_p if keep_result_p is not None else 0.5,
                referenced_p if referenced_p is not None else 0.5,
            )

    # Step 7: Apply
    original_chars = sum(len(json.dumps(m)) for m in messages)
    result_messages = apply_decisions(messages, decisions, calls)
    result_chars = sum(len(json.dumps(m)) for m in result_messages)
    elapsed = (time.monotonic() - t0) * 1000

    return {
        "messages": result_messages,
        "decisions": decisions,
        "stats": {
            "total_calls": len(calls),
            "pinned": pinned_count,
            "prefiltered": prefiltered_count,
            "jev_judged": len(candidates),
            "kept": sum(1 for d in decisions.values() if d["action"] == "keep"),
            "dropped_result": sum(1 for d in decisions.values() if d["action"] == "drop_result"),
            "dropped_call": sum(1 for d in decisions.values() if d["action"] == "drop_call"),
            "reduction_chars": original_chars - result_chars,
            "reduction_ratio": round(1 - result_chars / original_chars, 4) if original_chars else 0,
            "latency_ms": round(elapsed, 1),
            "jev_latency_ms": round(jev_latency_ms, 1),
            "jev_calls": jev_call_count,
            "usage": total_usage,
        },
    }


def _noul_value(answers: dict, key: str) -> float | None:
    """Extract a Noul probability from Jev answers."""
    answer = answers.get(key)
    if not isinstance(answer, dict):
        return None
    val = answer.get("noul")
    if not isinstance(val, (int, float)):
        return None
    return float(val)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Jev-powered context compaction: verbatim pruning, zero generation.")
    parser.add_argument(
        "--transcript",
        required=True,
        help="Path to JSON file with conversation messages.",
    )
    parser.add_argument(
        "--goal",
        help="Override goal text (default: extracted from last user prompts).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would happen without calling Jev.",
    )
    parser.add_argument(
        "--json-compact",
        action="store_true",
        help="Compact JSON output.",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Output only stats, not the full transcript.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Jev HTTP call timeout in seconds (default {DEFAULT_TIMEOUT}).",
    )
    args = parser.parse_args()

    try:
        transcript_path = Path(args.transcript)
        messages = json.loads(transcript_path.read_text(encoding="utf-8"))
        if not isinstance(messages, list):
            raise ValueError("Transcript must be a JSON array of messages")

        result = compact(
            messages,
            goal=args.goal,
            timeout=args.timeout,
            dry_run=args.dry_run,
        )

        if args.stats_only:
            output = {"stats": result["stats"], "decisions": result["decisions"]}
        else:
            output = result

        indent = None if args.json_compact else 2
        print(json.dumps(output, indent=indent, default=str))

    except Exception as exc:
        import traceback

        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"error": f"{type(exc).__name__}: {str(exc)[:200]}"}))

    return 0


if __name__ == "__main__":
    sys.exit(main())
