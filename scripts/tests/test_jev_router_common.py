"""Tests for scripts/jev_router_common.py Score helpers.

A live Jev Score answer is ``{"score": <float mean of 0..n-1>, ...}``. These
helpers turn that mean into a criteria index or a [0, 1] value.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
import jev_router_common as common


class TestScoreLevel:
    @pytest.mark.parametrize(
        ("mean", "expected"),
        [(0.0, 0), (0.4, 0), (1.5, 2), (2.3, 2), (2.7, 3), (3.5, 4), (4.0, 4)],
    )
    def test_rounds_mean_to_nearest_level(self, mean: float, expected: int) -> None:
        assert common.score_level({"score": mean}, 5) == expected

    def test_clamps_above_top_level(self) -> None:
        assert common.score_level({"score": 9.9}, 5) == 4

    def test_clamps_below_zero(self) -> None:
        assert common.score_level({"score": -3.0}, 5) == 0

    def test_int_score_accepted(self) -> None:
        assert common.score_level({"score": 3}, 5) == 3

    @pytest.mark.parametrize("bad", ["High risk", None, True, False, [2], {"x": 1}])
    def test_non_numeric_returns_none(self, bad: object) -> None:
        assert common.score_level({"score": bad}, 5) is None

    def test_missing_score_returns_none(self) -> None:
        assert common.score_level({"probabilities": {"0": 1.0}}, 5) is None

    def test_zero_levels_returns_none(self) -> None:
        assert common.score_level({"score": 1.0}, 0) is None

    def test_single_level_always_zero(self) -> None:
        assert common.score_level({"score": 7.0}, 1) == 0


class TestScoreNormalized:
    @pytest.mark.parametrize(
        ("mean", "n", "expected"),
        [(0.0, 5, 0.0), (2.0, 5, 0.5), (4.0, 5, 1.0), (1.0, 3, 0.5), (1.5, 4, 0.5)],
    )
    def test_divides_by_top_level(self, mean: float, n: int, expected: float) -> None:
        assert common.score_normalized({"score": mean}, n) == pytest.approx(expected)

    def test_clamps_to_unit_interval(self) -> None:
        assert common.score_normalized({"score": 12.0}, 5) == 1.0
        assert common.score_normalized({"score": -1.0}, 5) == 0.0

    @pytest.mark.parametrize("bad", ["2.7", None, True])
    def test_non_numeric_returns_none(self, bad: object) -> None:
        assert common.score_normalized({"score": bad}, 5) is None

    @pytest.mark.parametrize("n", [0, 1])
    def test_fewer_than_two_levels_returns_none(self, n: int) -> None:
        assert common.score_normalized({"score": 0.0}, n) is None

    def test_no_rounding(self) -> None:
        assert common.score_normalized({"score": 2.3}, 5) == pytest.approx(0.575)


class TestCallJevRedaction:
    """call_jev must redact the payload before it leaves the host."""

    def test_sent_body_is_redacted(self, capsys) -> None:
        from unittest.mock import MagicMock, patch

        fake_token = "ghp_" + "x" * 36
        payload = {
            "model": "jev-latest",
            "state": {"text": f"export GITHUB_TOKEN={fake_token}"},
            "questions": [{"id": "q", "type": "noul", "instructions": f"uses {fake_token}?"}],
        }
        sent: dict[str, bytes] = {}

        def fake_urlopen(request, timeout=None):
            sent["body"] = request.data
            resp = MagicMock()
            resp.read.return_value = b'{"answers": {"q": {"noul": 0.1}}}'
            resp.__enter__.return_value = resp
            resp.__exit__.return_value = False
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            data, _latency = common.call_jev(payload, "fake-api-key-not-real", timeout=1.0)

        body = sent["body"].decode("utf-8")
        assert fake_token not in body
        assert "<redacted:github:xxxx>" in body
        assert body.count("<redacted:") == 2
        assert data["answers"]["q"]["noul"] == 0.1
        # Caller's payload is untouched (deep copy).
        assert fake_token in payload["state"]["text"]
        err = capsys.readouterr().err
        assert "[jev-redact] 2 value(s) redacted before send" in err
        assert fake_token not in err

    def test_clean_payload_no_stderr_line(self, capsys) -> None:
        from unittest.mock import MagicMock, patch

        def fake_urlopen(request, timeout=None):
            resp = MagicMock()
            resp.read.return_value = b'{"answers": {}}'
            resp.__enter__.return_value = resp
            resp.__exit__.return_value = False
            return resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            common.call_jev({"state": {"text": "hello"}, "questions": []}, "fake-api-key-not-real", timeout=1.0)
        assert "[jev-redact]" not in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Task 1/2/5 tests: payload hash, cache, dedupe, breaker, answer persistence
# ---------------------------------------------------------------------------

import hashlib
import json
import os
import sqlite3
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch


class TestPayloadHash:
    """Task 1a: sha256 of canonical JSON, first 16 hex."""

    def test_deterministic(self) -> None:
        p = {"model": "jev-latest", "questions": {"a": 1}, "state": {"x": "y"}}
        h1 = common._payload_hash(p)
        h2 = common._payload_hash(p)
        assert h1 == h2
        assert len(h1) == 16
        assert all(c in "0123456789abcdef" for c in h1)

    def test_sort_keys_matters(self) -> None:
        """Different key order produces the same hash."""
        p1 = {"a": 1, "b": 2}
        p2 = {"b": 2, "a": 1}
        assert common._payload_hash(p1) == common._payload_hash(p2)

    def test_different_payloads_differ(self) -> None:
        p1 = {"model": "a", "state": {"x": 1}}
        p2 = {"model": "a", "state": {"x": 2}}
        assert common._payload_hash(p1) != common._payload_hash(p2)


class TestAnswersJson:
    """Task 1b: extract answers dict as compact JSON."""

    def test_extracts_answers(self) -> None:
        data = {"answers": {"q1": {"noul": 0.8}}, "usage": {"input_tokens": 10}}
        aj = common._answers_json(data)
        assert aj is not None
        parsed = json.loads(aj)
        assert parsed == {"q1": {"noul": 0.8}}
        # Must not contain usage or state
        assert "input_tokens" not in aj

    def test_missing_answers_returns_none(self) -> None:
        assert common._answers_json({"usage": {}}) is None

    def test_oversized_returns_none(self) -> None:
        big = {"answers": {"k": "x" * 70000}}
        assert common._answers_json(big) is None


def _fake_urlopen_factory(response_json: dict | None = None, status_code: int = 200):
    """Return a urlopen side_effect function that returns a fixed response."""
    call_count = {"n": 0}

    def fake_urlopen(request, timeout=None):
        call_count["n"] += 1
        if status_code != 200:
            exc = MagicMock()
            exc.code = status_code
            exc.read.return_value = b"error"
            raise common.urllib.error.HTTPError(
                url="http://test",
                code=status_code,
                msg="err",
                hdrs=None,
                fp=exc,
            )
        resp = MagicMock()
        body = json.dumps(response_json or {"answers": {}}).encode()
        resp.read.return_value = body
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        return resp

    return fake_urlopen, call_count


class TestCache:
    """Task 2: on-disk cache. Isolation via autouse _isolate_jev_state fixture."""

    def test_cache_hit_no_network(self) -> None:
        """Second identical call does not hit the network."""
        resp = {"answers": {"q": {"noul": 0.7}}}
        fake_urlopen, call_count = _fake_urlopen_factory(resp)

        with (
            patch.dict(os.environ, {"JEV_CACHE_TTL_S": "120"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            data1, lat1 = common.call_jev({"state": {}, "questions": {"q": {}}}, "fk", timeout=5.0)
            data2, lat2 = common.call_jev({"state": {}, "questions": {"q": {}}}, "fk", timeout=5.0)

        assert call_count["n"] == 1  # only one network call
        assert data1["answers"]["q"]["noul"] == 0.7
        assert data2["answers"]["q"]["noul"] == 0.7
        assert lat2 == 0.0
        assert data2.get("_meta", {}).get("cached") is True

    def test_different_payload_hits_network(self) -> None:
        resp = {"answers": {"q": {"noul": 0.5}}}
        fake_urlopen, call_count = _fake_urlopen_factory(resp)

        with (
            patch.dict(os.environ, {"JEV_CACHE_TTL_S": "120"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            common.call_jev({"state": {"a": 1}, "questions": {"q": {}}}, "fk", timeout=5.0)
            common.call_jev({"state": {"a": 2}, "questions": {"q": {}}}, "fk", timeout=5.0)

        assert call_count["n"] == 2

    def test_ttl_expiry_refetches(self) -> None:
        resp = {"answers": {"q": {"noul": 0.9}}}
        fake_urlopen, call_count = _fake_urlopen_factory(resp)

        with (
            patch.dict(os.environ, {"JEV_CACHE_TTL_S": "0.1"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            common.call_jev({"state": {}, "questions": {"q": {}}}, "fk", timeout=5.0)
            time.sleep(0.15)
            common.call_jev({"state": {}, "questions": {"q": {}}}, "fk", timeout=5.0)

        assert call_count["n"] == 2

    def test_ttl_zero_disables_cache(self) -> None:
        resp = {"answers": {"q": {"noul": 0.5}}}
        fake_urlopen, call_count = _fake_urlopen_factory(resp)

        with (
            patch.dict(os.environ, {"JEV_CACHE_TTL_S": "0"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            common.call_jev({"state": {}, "questions": {"q": {}}}, "fk", timeout=5.0)
            common.call_jev({"state": {}, "questions": {"q": {}}}, "fk", timeout=5.0)

        assert call_count["n"] == 2


class TestCircuitBreaker:
    """Task 5: circuit breaker on auth/billing errors. Isolation via autouse fixture."""

    def test_402_trips_breaker_second_call_no_network(self) -> None:
        """A 402 response trips the breaker; next call raises immediately without network."""
        fake_urlopen, call_count = _fake_urlopen_factory(status_code=402)

        with (
            patch.dict(os.environ, {"JEV_CACHE_TTL_S": "0", "JEV_BREAKER_TTL_S": "60"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            with pytest.raises(RuntimeError, match="HTTP 402"):
                common.call_jev({"state": {}, "questions": {}}, "fk", timeout=5.0)

            # Second call should not hit the network
            with pytest.raises(RuntimeError, match="HTTP 402 \\(breaker\\)"):
                common.call_jev({"state": {}, "questions": {}}, "fk", timeout=5.0)

        assert call_count["n"] == 1  # only one network call

    def test_breaker_file_written(self) -> None:
        """The breaker writes to disk so other processes can read it."""
        fake_urlopen, _ = _fake_urlopen_factory(status_code=402)

        with (
            patch.dict(os.environ, {"JEV_CACHE_TTL_S": "0", "JEV_BREAKER_TTL_S": "60"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
            pytest.raises(RuntimeError),
        ):
            common.call_jev({"state": {}, "questions": {}}, "fk", timeout=5.0)

        assert common._breaker_path().exists()
        data = json.loads(common._breaker_path().read_text())
        assert data["status"] == 402
        assert "ts" in data

    def test_ttl_expiry_reprobes(self) -> None:
        """After the breaker TTL expires, the next call makes a network request."""
        call_results = []
        call_count = {"n": 0}

        def fake_urlopen(request, timeout=None):
            call_count["n"] += 1
            if call_count["n"] == 1:
                exc = MagicMock()
                exc.code = 402
                exc.read.return_value = b"billing"
                raise common.urllib.error.HTTPError(
                    url="http://test",
                    code=402,
                    msg="err",
                    hdrs=None,
                    fp=exc,
                )
            # Second attempt succeeds
            resp = MagicMock()
            resp.read.return_value = b'{"answers": {"q": {"noul": 0.5}}}'
            resp.__enter__.return_value = resp
            resp.__exit__.return_value = False
            return resp

        with (
            patch.dict(os.environ, {"JEV_CACHE_TTL_S": "0", "JEV_BREAKER_TTL_S": "0.1"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            with pytest.raises(RuntimeError, match="HTTP 402"):
                common.call_jev({"state": {}, "questions": {"q": {}}}, "fk", timeout=5.0)

            time.sleep(0.15)
            common._jev_down = None  # clear in-process flag to test file TTL

            data, _ = common.call_jev({"state": {}, "questions": {"q": {}}}, "fk", timeout=5.0)

        assert call_count["n"] == 2
        assert data["answers"]["q"]["noul"] == 0.5

    def test_success_clears_breaker(self) -> None:
        """A 2xx response clears the breaker file."""
        # Manually trip the breaker
        common._trip_breaker(402)
        assert common._breaker_path().exists()

        resp = {"answers": {"q": {"noul": 0.5}}}
        fake_urlopen, _ = _fake_urlopen_factory(resp)

        # Clear in-process flag but leave file so the function clears it
        common._jev_down = None

        with (
            patch.dict(os.environ, {"JEV_CACHE_TTL_S": "0", "JEV_BREAKER_TTL_S": "0"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            data, _ = common.call_jev({"state": {}, "questions": {"q": {}}}, "fk", timeout=5.0)

        assert data["answers"]["q"]["noul"] == 0.5
        # Breaker file should be cleared
        assert not common._breaker_path().exists()

    def test_breaker_ttl_zero_disables(self) -> None:
        """JEV_BREAKER_TTL_S=0 disables the breaker."""
        fake_urlopen, call_count = _fake_urlopen_factory(status_code=402)

        with (
            patch.dict(os.environ, {"JEV_CACHE_TTL_S": "0", "JEV_BREAKER_TTL_S": "0"}),
            patch("urllib.request.urlopen", side_effect=fake_urlopen),
        ):
            with pytest.raises(RuntimeError, match="HTTP 402"):
                common.call_jev({"state": {}, "questions": {}}, "fk", timeout=5.0)
            # With breaker disabled, the second call still hits the network
            with pytest.raises(RuntimeError, match="HTTP 402"):
                common.call_jev({"state": {}, "questions": {}}, "fk", timeout=5.0)

        assert call_count["n"] == 2  # both hit the network


class TestLearningDbAnswerPersistence:
    """Task 1b/c: stored answers and read helpers."""

    def setup_method(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        os.environ["CLAUDE_LEARNING_DIR"] = self._tmpdir
        # Reset init state for fresh db
        import importlib

        sys.path.insert(0, str(Path(__file__).resolve().parents[1].parent / "hooks" / "lib"))
        import learning_db_v2 as db

        self._db = db
        db._initialized = False

    def teardown_method(self) -> None:
        os.environ.pop("CLAUDE_LEARNING_DIR", None)
        self._db._initialized = False

    def test_record_and_retrieve_answers(self) -> None:
        db = self._db
        db.record_jev_call(
            script="test-script.py",
            ok=True,
            payload_hash="abcdef0123456789",
            answers_json='{"q1":{"noul":0.8}}',
        )

        results = db.jev_answers_for("abcdef0123456789")
        assert len(results) == 1
        assert results[0]["answers"] == {"q1": {"noul": 0.8}}
        assert results[0]["ok"] is True

    def test_jev_calls_with_answers_filter(self) -> None:
        db = self._db
        db.record_jev_call(
            script="a.py",
            ok=True,
            payload_hash="hash1",
            answers_json='{"q":{"noul":0.5}}',
        )
        db.record_jev_call(
            script="b.py",
            ok=True,
            payload_hash="hash2",
            answers_json='{"q":{"noul":0.9}}',
        )
        db.record_jev_call(
            script="a.py",
            ok=False,
            error="timeout",
        )

        all_rows = db.jev_calls_with_answers()
        assert len(all_rows) == 2

        a_rows = db.jev_calls_with_answers(script="a.py")
        assert len(a_rows) == 1
        assert a_rows[0]["script"] == "a.py"

    def test_cached_column_persisted(self) -> None:
        db = self._db
        db.record_jev_call(
            script="test.py",
            ok=True,
            payload_hash="h1",
            cached=True,
        )
        db.record_jev_call(
            script="test.py",
            ok=True,
            payload_hash="h2",
            cached=False,
        )

        rows = db.jev_calls_with_answers(script="test.py")
        # Neither has answers_json, so they don't appear in jev_calls_with_answers
        assert len(rows) == 0

        # Check raw
        db.init_db()
        with db.get_connection() as conn:
            r = conn.execute("SELECT cached FROM jev_calls WHERE payload_hash = 'h1'").fetchone()
            assert r["cached"] == 1

    def test_oversized_answers_stored_as_null(self) -> None:
        db = self._db
        big = json.dumps({"k": "x" * 70000})
        db.record_jev_call(
            script="test.py",
            ok=True,
            payload_hash="big1",
            answers_json=big,
        )
        results = db.jev_answers_for("big1")
        assert len(results) == 0  # null answers_json filtered out


# ---------------------------------------------------------------------------
# Task 4: _count_call reads JEV_SESSION_ID and JEV_AGENT_ID
# ---------------------------------------------------------------------------


class TestCountCallSessionId:
    """Verify _count_call reads JEV_SESSION_ID, CLAUDE_SESSION_ID, and JEV_AGENT_ID."""

    @patch.dict("os.environ", {"JEV_SESSION_ID": "jev-sess-1"}, clear=False)
    @patch.object(common, "_record_jev_call")
    def test_jev_session_id_preferred(self, mock_record):
        """JEV_SESSION_ID takes priority over CLAUDE_SESSION_ID."""
        mock_record.return_value = True
        common._count_call(
            ok=True,
            latency_ms=10.0,
            data=None,
            n_questions=1,
            n_redacted=0,
            error=None,
        )
        mock_record.assert_called_once()
        assert mock_record.call_args.kwargs["session_id"] == "jev-sess-1"

    @patch.dict("os.environ", {"CLAUDE_SESSION_ID": "claude-sess-2"}, clear=False)
    @patch.object(common, "_record_jev_call")
    def test_claude_session_id_fallback(self, mock_record):
        """CLAUDE_SESSION_ID is used when JEV_SESSION_ID is absent."""
        # Ensure JEV_SESSION_ID is not set
        import os

        os.environ.pop("JEV_SESSION_ID", None)
        mock_record.return_value = True
        common._count_call(
            ok=True,
            latency_ms=10.0,
            data=None,
            n_questions=1,
            n_redacted=0,
            error=None,
        )
        mock_record.assert_called_once()
        assert mock_record.call_args.kwargs["session_id"] == "claude-sess-2"

    @patch.dict("os.environ", {"JEV_SESSION_ID": "sess-3", "JEV_AGENT_ID": "py-eng"}, clear=False)
    @patch.object(common, "_record_jev_call")
    def test_agent_id_appended(self, mock_record):
        """JEV_AGENT_ID is appended as <session>:<agent>."""
        mock_record.return_value = True
        common._count_call(
            ok=True,
            latency_ms=10.0,
            data=None,
            n_questions=1,
            n_redacted=0,
            error=None,
        )
        mock_record.assert_called_once()
        assert mock_record.call_args.kwargs["session_id"] == "sess-3:py-eng"

    @patch.dict("os.environ", {}, clear=False)
    @patch.object(common, "_record_jev_call")
    def test_no_env_vars_gives_none(self, mock_record):
        """No session env vars -> session_id is None."""
        import os

        os.environ.pop("JEV_SESSION_ID", None)
        os.environ.pop("CLAUDE_SESSION_ID", None)
        os.environ.pop("JEV_AGENT_ID", None)
        mock_record.return_value = True
        common._count_call(
            ok=True,
            latency_ms=10.0,
            data=None,
            n_questions=1,
            n_redacted=0,
            error=None,
        )
        mock_record.assert_called_once()
        assert mock_record.call_args.kwargs["session_id"] is None

    @patch.dict("os.environ", {"JEV_AGENT_ID": "py-eng"}, clear=False)
    @patch.object(common, "_record_jev_call")
    def test_agent_id_without_session_not_appended(self, mock_record):
        """JEV_AGENT_ID without a session_id does not produce ':py-eng'."""
        import os

        os.environ.pop("JEV_SESSION_ID", None)
        os.environ.pop("CLAUDE_SESSION_ID", None)
        mock_record.return_value = True
        common._count_call(
            ok=True,
            latency_ms=10.0,
            data=None,
            n_questions=1,
            n_redacted=0,
            error=None,
        )
        mock_record.assert_called_once()
        assert mock_record.call_args.kwargs["session_id"] is None


# ---------------------------------------------------------------------------
# Rate-limit retry and body-free errors
# ---------------------------------------------------------------------------


def _http_error(code: int, body: bytes = b"{}", headers: dict | None = None):
    import io
    from email.message import Message

    hdrs = Message()
    for k, v in (headers or {}).items():
        hdrs[k] = v
    return common.urllib.error.HTTPError(url="http://test", code=code, msg="err", hdrs=hdrs, fp=io.BytesIO(body))


def _ok_response(answers: dict):
    resp = MagicMock()
    resp.read.return_value = json.dumps({"answers": answers}).encode()
    resp.__enter__.return_value = resp
    resp.__exit__.return_value = False
    return resp


class TestRetry:
    def _payload(self, tag: str) -> dict:
        return {"model": "m", "state": {"t": tag}, "questions": {"q": {"type": "noul", "instructions": "x"}}}

    def test_retries_429_then_succeeds(self, monkeypatch):
        sleeps: list[float] = []
        monkeypatch.setattr(common.time, "sleep", sleeps.append)
        monkeypatch.setenv("JEV_RETRY_MAX", "2")
        seq = [_http_error(429), _http_error(529), _ok_response({"q": {"noul": 0.9}})]

        def fake(request, timeout=None):
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(common.urllib.request, "urlopen", fake)
        data, _ = common.call_jev(self._payload("retry-ok"), "k", 5)
        assert data["answers"]["q"]["noul"] == 0.9
        # Filter out daemon-thread sleeps (cleanup thread sleeps 10s)
        retry_sleeps = [s for s in sleeps if s < 10]
        assert retry_sleeps == [0.5, 1.0]

    def test_honors_retry_after_up_to_the_cap(self, monkeypatch):
        sleeps: list[float] = []
        monkeypatch.setattr(common.time, "sleep", sleeps.append)
        monkeypatch.setenv("JEV_RETRY_MAX", "2")
        seq = [_http_error(429, headers={"Retry-After": "3"}), _http_error(429, headers={"Retry-After": "600"})]
        seq.append(_ok_response({"q": {"noul": 0.1}}))

        def fake(request, timeout=None):
            item = seq.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(common.urllib.request, "urlopen", fake)
        common.call_jev(self._payload("retry-after"), "k", 5)
        # Filter out daemon-thread sleeps (cleanup thread sleeps 10s)
        retry_sleeps = [s for s in sleeps if s < 10]
        assert retry_sleeps == [3.0, common._RETRY_MAX_SLEEP_S]

    def test_gives_up_after_the_retry_limit(self, monkeypatch):
        sleeps: list[float] = []
        monkeypatch.setattr(common.time, "sleep", sleeps.append)
        monkeypatch.setenv("JEV_RETRY_MAX", "2")
        calls = {"n": 0}

        def fake(request, timeout=None):
            calls["n"] += 1
            raise _http_error(429)

        monkeypatch.setattr(common.urllib.request, "urlopen", fake)
        with pytest.raises(RuntimeError, match="HTTP 429"):
            common.call_jev(self._payload("retry-limit"), "k", 5)
        assert calls["n"] == 3 and len(sleeps) == 2

    @pytest.mark.parametrize("code", [400, 401, 402, 422, 500])
    def test_other_statuses_are_not_retried(self, monkeypatch, code):
        sleeps: list[float] = []
        monkeypatch.setattr(common.time, "sleep", sleeps.append)
        calls = {"n": 0}

        def fake(request, timeout=None):
            calls["n"] += 1
            raise _http_error(code)

        monkeypatch.setattr(common.urllib.request, "urlopen", fake)
        with pytest.raises(RuntimeError):
            common.call_jev(self._payload(f"no-retry-{code}"), "k", 5)
        assert calls["n"] == 1 and sleeps == []


class TestErrorTextCarriesNoBody:
    def _payload(self, tag: str) -> dict:
        return {"model": "m", "state": {"t": tag}, "questions": {"q": {"type": "noul", "instructions": "x"}}}

    def test_422_names_the_field_and_omits_the_echoed_input(self, monkeypatch):
        body = json.dumps(
            {
                "detail": [
                    {
                        "type": "missing",
                        "loc": ["body", "questions", "q", "score", "criteria"],
                        "msg": "Field required",
                        "input": {"instructions": "PRIVATE QUESTION TEXT"},
                    }
                ]
            }
        ).encode()

        def fake(request, timeout=None):
            raise _http_error(422, body)

        monkeypatch.setattr(common.urllib.request, "urlopen", fake)
        with pytest.raises(RuntimeError) as err:
            common.call_jev(self._payload("err-422"), "k", 5)
        text = str(err.value)
        assert "body.questions.q.score.criteria" in text
        assert "PRIVATE QUESTION TEXT" not in text

    def test_402_reports_the_error_type_only(self, monkeypatch):
        body = json.dumps({"error": {"type": "billing_error", "message": "account 12345 has no credits"}}).encode()

        def fake(request, timeout=None):
            raise _http_error(402, body)

        monkeypatch.setattr(common.urllib.request, "urlopen", fake)
        with pytest.raises(RuntimeError) as err:
            common.call_jev(self._payload("err-402"), "k", 5)
        assert str(err.value) == "HTTP 402 (billing_error)"
