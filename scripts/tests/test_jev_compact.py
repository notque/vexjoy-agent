"""Tests for jev-compact.py: Jev-powered verbatim context compaction.

Covers: token estimation, tool call collection, Tier 1 pre-filters,
state fitting, question building, decision logic, transcript application,
and the full pipeline with a fake Jev backend.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("jev_compact", SCRIPTS / "jev-compact.py")
jev_compact = importlib.util.module_from_spec(spec)
spec.loader.exec_module(jev_compact)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _msg(role: str, text: str = "", tool_uses: list | None = None, tool_results: list | None = None) -> dict:
    """Build a message with optional tool blocks."""
    content: list = []
    if text:
        content.append({"type": "text", "text": text})
    if tool_uses:
        content.extend(tool_uses)
    if tool_results:
        content.extend(tool_results)
    return {"role": role, "content": content}


def _tool_use(uid: str, name: str, inp: dict | None = None) -> dict:
    return {"type": "tool_use", "id": uid, "name": name, "input": inp or {}}


def _tool_result(uid: str, text: str = "ok", is_error: bool = False) -> dict:
    return {"type": "tool_result", "tool_use_id": uid, "content": text, "is_error": is_error}


def _transcript_with_calls(n: int) -> list[dict]:
    """Build a transcript with n tool call/result pairs."""
    messages = [_msg("user", "Do the thing")]
    for i in range(n):
        uid = f"call_{i}"
        messages.append(
            _msg("assistant", f"Running step {i}", tool_uses=[_tool_use(uid, "Read", {"file_path": f"file{i}.py"})])
        )
        messages.append(_msg("user", tool_results=[_tool_result(uid, f"contents of file{i}.py " * 50)]))
    messages.append(_msg("assistant", "Done"))
    return messages


# ---------------------------------------------------------------------------
# Token estimation
# ---------------------------------------------------------------------------


class TestEstimateTokens:
    def test_empty(self):
        assert jev_compact.estimate_tokens("") == 0

    def test_short_word(self):
        result = jev_compact.estimate_tokens("hello")
        assert result >= 1

    def test_json_heavy(self):
        # JSON with lots of punctuation should give higher counts
        data = json.dumps({"key": "value", "nested": {"a": 1, "b": [1, 2, 3]}})
        result = jev_compact.estimate_tokens(data)
        assert result > len(data.split()) // 2  # rough sanity

    def test_digits(self):
        result = jev_compact.estimate_tokens("12345")
        assert result >= 2  # 5 digits * 0.5 = 2.5 + 1 = 3


# ---------------------------------------------------------------------------
# Tool call collection
# ---------------------------------------------------------------------------


class TestCollectToolCalls:
    def test_basic_pairing(self):
        messages = [
            _msg("user", "read file"),
            _msg("assistant", tool_uses=[_tool_use("u1", "Read", {"file_path": "a.py"})]),
            _msg("user", tool_results=[_tool_result("u1", "file contents here")]),
            _msg("assistant", "got it"),
        ]
        calls = jev_compact.collect_tool_calls(messages, preserve_recent=2)
        assert len(calls) == 1
        assert calls[0]["tool"] == "Read"
        assert calls[0]["seq_id"] == "t1"
        assert calls[0]["result_chars"] == len("file contents here")

    def test_unpaired_use_skipped(self):
        messages = [
            _msg("user", "go"),
            _msg("assistant", tool_uses=[_tool_use("u1", "Read")]),
            # No tool_result for u1
            _msg("assistant", "failed"),
        ]
        calls = jev_compact.collect_tool_calls(messages)
        assert len(calls) == 0

    def test_pinning_first_and_recent(self):
        messages = _transcript_with_calls(10)
        calls = jev_compact.collect_tool_calls(messages, preserve_recent=4)
        # First message's calls are pinned
        pinned = [c for c in calls if c["pinned"]]
        not_pinned = [c for c in calls if not c["pinned"]]
        assert len(pinned) > 0
        assert len(not_pinned) > 0

    def test_error_flag_propagated(self):
        messages = [
            _msg("user", "go"),
            _msg("assistant", tool_uses=[_tool_use("u1", "Bash")]),
            _msg("user", tool_results=[_tool_result("u1", "command not found", is_error=True)]),
        ]
        calls = jev_compact.collect_tool_calls(messages)
        assert calls[0]["is_error"] is True


# ---------------------------------------------------------------------------
# Tier 1 pre-filters
# ---------------------------------------------------------------------------


class TestPrefilter:
    def test_glob_dropped(self):
        call = {
            "seq_id": "t1",
            "tool": "Glob",
            "input": '{"pattern":"*.py"}',
            "result": "a.py\nb.py",
            "result_chars": 10,
            "pinned": False,
            "is_error": False,
        }
        assert jev_compact._is_obvious_drop(call) is True

    def test_list_directory_dropped(self):
        call = {
            "seq_id": "t1",
            "tool": "ListDirectory",
            "input": '{"path":"."}',
            "result": "dir listing",
            "result_chars": 20,
            "pinned": False,
            "is_error": False,
        }
        assert jev_compact._is_obvious_drop(call) is True

    def test_long_error_kept(self):
        call = {
            "seq_id": "t1",
            "tool": "Bash",
            "input": '{"command":"make"}',
            "result": "x" * 300,
            "result_chars": 300,
            "pinned": False,
            "is_error": True,
        }
        assert jev_compact._is_obvious_drop(call) is False  # obvious keep

    def test_edit_goes_to_jev(self):
        call = {
            "seq_id": "t1",
            "tool": "Edit",
            "input": '{"file_path":"a.py"}',
            "result": "Applied edit",
            "result_chars": 12,
            "pinned": False,
            "is_error": False,
        }
        # Short Edit result: Jev decides
        result = jev_compact._is_obvious_drop(call)
        assert result is None

    def test_ls_command_dropped(self):
        call = {
            "seq_id": "t1",
            "tool": "Bash",
            "input": json.dumps({"command": "ls -la"}),
            "result": "total 42\ndrwxr-xr-x ...",
            "result_chars": 50,
            "pinned": False,
            "is_error": False,
        }
        assert jev_compact._is_obvious_drop(call) is True

    def test_git_status_dropped(self):
        call = {
            "seq_id": "t1",
            "tool": "Bash",
            "input": json.dumps({"command": "git status --short"}),
            "result": "M file.py",
            "result_chars": 10,
            "pinned": False,
            "is_error": False,
        }
        assert jev_compact._is_obvious_drop(call) is True

    def test_pinned_always_kept(self):
        calls = [
            {
                "seq_id": "t1",
                "tool": "Glob",
                "input": "",
                "result": "",
                "result_chars": 0,
                "pinned": True,
                "is_error": False,
            }
        ]
        candidates, decisions = jev_compact.prefilter_calls(calls)
        assert len(candidates) == 0
        assert decisions["t1"]["action"] == "keep"
        assert decisions["t1"]["reason"] == "pinned"


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


class TestQuestions:
    def test_three_questions_per_call(self):
        call = {"seq_id": "t1", "tool": "Read", "result_chars": 500}
        qs = jev_compact.questions_for(call)
        assert "call_t1" in qs
        assert "result_t1" in qs
        assert "referenced_t1" in qs
        assert len(qs) == 3

    def test_criteria_present(self):
        call = {"seq_id": "t1", "tool": "Edit", "result_chars": 100}
        qs = jev_compact.questions_for(call)
        call_q = qs["call_t1"]
        assert "criteria" in call_q["instructions"]
        assert "true" in call_q["instructions"]["criteria"]
        assert "false" in call_q["instructions"]["criteria"]


# ---------------------------------------------------------------------------
# Decision logic
# ---------------------------------------------------------------------------


class TestDecision:
    def test_keep_high_result(self):
        call = {"tool": "Read"}
        d = jev_compact.decide_call(call, 0.8, 0.7, 0.5)
        assert d["action"] == "keep"

    def test_drop_result_low_result_high_call(self):
        call = {"tool": "Read"}
        d = jev_compact.decide_call(call, 0.7, 0.3, 0.3)
        assert d["action"] == "drop_result"

    def test_drop_call_both_low(self):
        call = {"tool": "Read"}
        d = jev_compact.decide_call(call, 0.3, 0.2, 0.2)
        assert d["action"] == "drop_call"

    def test_edit_lower_threshold(self):
        # Edit uses 0.35 threshold
        call = {"tool": "Edit"}
        d = jev_compact.decide_call(call, 0.4, 0.4, 0.3)
        assert d["action"] == "keep"  # 0.4 >= 0.35

    def test_referenced_boost(self):
        call = {"tool": "Read"}
        # Low keep_result but high referenced → boosted
        d = jev_compact.decide_call(call, 0.6, 0.3, 0.8)
        # referenced=0.8 → effective = max(0.3, 0.5 + (0.8-0.6)*0.5) = max(0.3, 0.6) = 0.6
        assert d["action"] == "keep"


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------


class TestBatching:
    def test_single_batch_small(self):
        candidates = [{"seq_id": f"t{i}"} for i in range(3)]
        batches = jev_compact.batch_calls(candidates, 5000)
        assert len(batches) == 1

    def test_many_calls_share_one_request(self):
        candidates = [{"seq_id": f"t{i}"} for i in range(60)]
        batches = jev_compact.batch_calls(candidates, 8000)
        assert len(batches) == 1 and len(batches[0]) == 60

    def test_splits_when_questions_exceed_the_request_budget(self):
        candidates = [{"seq_id": f"t{i}"} for i in range(200)]
        batches = jev_compact.batch_calls(candidates, 20000)
        assert 2 <= len(batches) <= jev_compact.MAX_REQUESTS_PER_COMPACTION
        assert sum(len(b) for b in batches) == 200

    def test_state_over_hard_limit_sends_nothing(self):
        candidates = [{"seq_id": "t1"}]
        assert jev_compact.batch_calls(candidates, jev_compact.STATE_HARD_LIMIT_TOKENS + 1) is None

    def test_too_many_requests_sends_nothing(self):
        candidates = [{"seq_id": f"t{i}"} for i in range(2000)]
        assert jev_compact.batch_calls(candidates, 20000) is None

    def test_empty_candidates(self):
        assert jev_compact.batch_calls([], 5000) == []


# ---------------------------------------------------------------------------
# Apply decisions
# ---------------------------------------------------------------------------


class TestApplyDecisions:
    def test_drop_call_removes_both_blocks(self):
        messages = [
            _msg("user", "go"),
            _msg("assistant", "reading", tool_uses=[_tool_use("u1", "Read")]),
            _msg("user", tool_results=[_tool_result("u1", "big content " * 100)]),
        ]
        calls = jev_compact.collect_tool_calls(messages, preserve_recent=0)
        decisions = {calls[0]["seq_id"]: {"action": "drop_call"}}

        result = jev_compact.apply_decisions(messages, decisions, calls)
        # The tool_use and tool_result blocks should be gone
        all_text = json.dumps(result)
        assert "big content" not in all_text

    def test_drop_result_truncates(self):
        messages = [
            _msg("user", "go"),
            _msg("assistant", "reading", tool_uses=[_tool_use("u1", "Read")]),
            _msg("user", tool_results=[_tool_result("u1", "x" * 1000)]),
        ]
        calls = jev_compact.collect_tool_calls(messages, preserve_recent=0)
        decisions = {calls[0]["seq_id"]: {"action": "drop_result"}}

        result = jev_compact.apply_decisions(messages, decisions, calls, head_chars=50)
        all_text = json.dumps(result)
        assert "jev-compact truncated" in all_text
        # Result should be much shorter
        assert len(all_text) < len(json.dumps(messages))

    def test_keep_preserves_content(self):
        messages = [
            _msg("user", "go"),
            _msg("assistant", "reading", tool_uses=[_tool_use("u1", "Read")]),
            _msg("user", tool_results=[_tool_result("u1", "important content")]),
        ]
        calls = jev_compact.collect_tool_calls(messages, preserve_recent=0)
        decisions = {calls[0]["seq_id"]: {"action": "keep"}}

        result = jev_compact.apply_decisions(messages, decisions, calls)
        assert json.dumps(result) == json.dumps(messages)


# ---------------------------------------------------------------------------
# State fitting
# ---------------------------------------------------------------------------


class TestStateFitting:
    def test_fits_small_transcript(self):
        messages = _transcript_with_calls(3)
        calls = jev_compact.collect_tool_calls(messages)
        state = jev_compact.fit_state(messages, calls, "do the thing")
        assert "context" in state
        assert "goal" in state
        assert "history" in state

    def test_shrinks_large_transcript(self):
        messages = _transcript_with_calls(50)
        calls = jev_compact.collect_tool_calls(messages)
        state = jev_compact.fit_state(messages, calls, "do the thing", max_tokens=5000)
        state_json = json.dumps(state, separators=(",", ":"))
        tokens = jev_compact.estimate_tokens(state_json)
        assert tokens <= 5000 or len(state["history"]) < len(messages)


# ---------------------------------------------------------------------------
# Full pipeline (with mock Jev)
# ---------------------------------------------------------------------------


class TestCompactPipeline:
    def _fake_jev(self, calls_to_drop: set[str]):
        """Return a mock validated_call_jev that drops specified seq_ids."""

        def mock_call(payload, api_key, timeout):
            questions = payload.get("questions", {})
            answers = {}
            for qname in questions:
                if qname.startswith("call_"):
                    seq_id = qname[5:]
                    answers[qname] = {"noul": 0.1 if seq_id in calls_to_drop else 0.9}
                elif qname.startswith("result_"):
                    seq_id = qname[7:]
                    answers[qname] = {"noul": 0.1 if seq_id in calls_to_drop else 0.9}
                elif qname.startswith("referenced_"):
                    seq_id = qname[11:]
                    answers[qname] = {"noul": 0.1 if seq_id in calls_to_drop else 0.8}
            return {"answers": answers, "usage": {"input_tokens": 100, "output_tokens": 50}}, 50.0

        return mock_call

    def test_basic_compaction(self):
        messages = _transcript_with_calls(10)
        # Drop the oldest calls (t1-t4), keep the rest
        drops = {"t1", "t2", "t3", "t4"}

        with (
            patch.object(jev_compact.jev_router_common, "typesafe_available", return_value=(True, "ok")),
            patch.object(jev_compact.jev_router_common, "validated_call_jev", side_effect=self._fake_jev(drops)),
            patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}),
        ):
            result = jev_compact.compact(messages, preserve_recent=4)

        stats = result["stats"]
        assert stats["total_calls"] == 10
        assert stats["dropped_call"] > 0
        assert stats["reduction_ratio"] > 0
        assert stats["jev_calls"] >= 1

        # Verify the dropped content is actually gone
        result_text = json.dumps(result["messages"])
        assert len(result_text) < len(json.dumps(messages))

    def test_unavailable_returns_original(self):
        messages = _transcript_with_calls(5)
        with patch.object(jev_compact.jev_router_common, "typesafe_available", return_value=(False, "no key")):
            result = jev_compact.compact(messages)

        assert result["messages"] is messages
        assert "error" in result["stats"]

    def test_dry_run(self):
        messages = _transcript_with_calls(8)
        with patch.object(jev_compact.jev_router_common, "typesafe_available", return_value=(True, "ok")):
            result = jev_compact.compact(messages, dry_run=True)

        assert result["stats"].get("dry_run") is True
        assert result["stats"]["jev_candidates"] > 0
        assert result["messages"] is messages  # unchanged

    def test_missing_answer_keeps_by_default(self):
        """Missing Jev answers should fail-safe to keep."""
        messages = _transcript_with_calls(5)

        def mock_empty(payload, api_key, timeout):
            return {"answers": {}, "usage": {"input_tokens": 10, "output_tokens": 5}}, 10.0

        with (
            patch.object(jev_compact.jev_router_common, "typesafe_available", return_value=(True, "ok")),
            patch.object(jev_compact.jev_router_common, "validated_call_jev", side_effect=mock_empty),
            patch.dict(os.environ, {"TYPESAFE_API_KEY": "test-key"}),
        ):
            result = jev_compact.compact(messages)

        # All candidates should have action=keep with reason=missing_answer
        for seq_id, decision in result["decisions"].items():
            if decision.get("reason") not in ("pinned", "prefilter_obvious_drop", "prefilter_obvious_keep"):
                assert decision["action"] == "keep"
                assert decision["reason"] == "missing_answer"


import os


class TestLoadTranscriptJsonl:
    """load_transcript_jsonl maps user/assistant JSONL rows to compact()'s {role, content} shape."""

    def _write(self, tmp_path, rows):
        path = tmp_path / "session.jsonl"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return path

    def test_maps_rows_and_skips_others(self, tmp_path):
        rows = [
            json.dumps({"type": "summary", "summary": "x"}),
            json.dumps({"type": "user", "message": {"role": "user", "content": "read foo.py"}}),
            "not json",
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "content": [{"type": "tool_use", "id": "t1", "name": "Read", "input": {"file_path": "foo.py"}}],
                    },
                }
            ),
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "print(1)"}],
                    },
                }
            ),
            json.dumps({"type": "system", "subtype": "compact_boundary", "compactMetadata": {}}),
            json.dumps({"type": "user"}),  # no message dict
        ]
        messages = jev_compact.load_transcript_jsonl(self._write(tmp_path, rows))
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        assert set(messages[0]) == {"role", "content"}
        calls = jev_compact.collect_tool_calls(messages, preserve_recent=0)
        assert len(calls) == 1
        assert calls[0]["tool"] == "Read"
        assert calls[0]["result"] == "print(1)"
        assert jev_compact._extract_goal(messages) == "read foo.py"

    def test_role_falls_back_to_row_type(self, tmp_path):
        rows = [json.dumps({"type": "assistant", "message": {"content": "hi"}})]
        messages = jev_compact.load_transcript_jsonl(self._write(tmp_path, rows))
        assert messages == [{"role": "assistant", "content": "hi"}]

    def test_missing_file_is_empty(self, tmp_path):
        assert jev_compact.load_transcript_jsonl(tmp_path / "nope.jsonl") == []


# ---------------------------------------------------------------------------
# Redaction of Jev state (REDACT_STATE)
# ---------------------------------------------------------------------------

FAKE_GHP = "ghp_" + "x" * 36
FAKE_AWS = "AKIA" + "X" * 16


class TestStateRedaction:
    def test_redact_state_constant_default_on(self) -> None:
        assert jev_compact.REDACT_STATE is True

    def test_extract_goal_redacts(self) -> None:
        msgs = [_msg("user", f"deploy with token {FAKE_GHP} please")]
        goal = jev_compact._extract_goal(msgs)
        assert FAKE_GHP not in goal
        assert "<redacted:github:xxxx>" in goal

    def test_history_entry_redacts_text_and_tool_input(self) -> None:
        msg = _msg("assistant", f"using {FAKE_AWS} now")
        calls_by_msg = {
            0: [
                {
                    "seq_id": "t1",
                    "tool": "Bash",
                    "input": f"export AWS_ACCESS_KEY_ID={FAKE_AWS}",
                    "is_error": False,
                    "result_chars": 10,
                }
            ]
        }
        entry = jev_compact._build_history_entry(msg, 0, calls_by_msg, 1000, False, False, {0})
        assert entry is not None
        dumped = json.dumps(entry)
        assert FAKE_AWS not in dumped
        assert "<redacted:aws-key:XXXX>" in entry["text"]
        assert "<redacted:aws-key:XXXX>" in entry["tool_calls"][0]["input"]

    def test_redact_state_off_leaves_text(self) -> None:
        msgs = [_msg("user", f"token {FAKE_GHP}")]
        with patch.object(jev_compact, "REDACT_STATE", False):
            assert FAKE_GHP in jev_compact._extract_goal(msgs)
