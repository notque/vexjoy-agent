"""Tests for credential redaction in scripts/search-engine-indexer.py."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

SCRIPT = Path(__file__).resolve().parent.parent / "search-engine-indexer.py"

FAKE_TOKEN = "tok-FAKE-0000-wxyz"
FAKE_KEY = "key-FAKE-1111-abcd"
TEST_URL = "https://example.com/new-post"
TEST_SITE = "https://example.com"
TEST_HOST = "example.com"


def _load_mod():
    """Load search-engine-indexer.py as a module (hyphenated name requires importlib)."""
    spec = importlib.util.spec_from_file_location("search_engine_indexer", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# -- Case 1: Baidu dry-run redacts token --------------------------------


def test_baidu_dry_run_redacts_token() -> None:
    """Baidu dry-run result must not contain the real push token."""
    mod = _load_mod()
    result = mod.submit_baidu(TEST_URL, TEST_SITE, FAKE_TOKEN, dry_run=True)
    serialized = json.dumps(result)
    assert FAKE_TOKEN not in serialized
    assert "<redacted:token:wxyz>" in result["endpoint"]


# -- Case 2: IndexNow dry-run redacts key -------------------------------


def test_indexnow_dry_run_redacts_key() -> None:
    """IndexNow dry-run result must not contain the real API key."""
    mod = _load_mod()
    result = mod.submit_indexnow(TEST_URL, TEST_HOST, FAKE_KEY, dry_run=True)
    serialized = json.dumps(result)
    assert FAKE_KEY not in serialized


# -- Case 3: Baidu error path redacts token ------------------------------


def test_baidu_error_redacts_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Baidu connection error must not leak the push token."""
    mod = _load_mod()
    endpoint_with_token = f"http://data.zz.baidu.com/urls?site={TEST_SITE}&token={FAKE_TOKEN}"

    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise requests.exceptions.ConnectionError(f"failed: {endpoint_with_token}")

    monkeypatch.setattr(mod.requests, "post", _raise)
    result = mod.submit_baidu(TEST_URL, TEST_SITE, FAKE_TOKEN, dry_run=False)
    assert FAKE_TOKEN not in result["error"]


# -- Case 4: IndexNow error path redacts key -----------------------------


def test_indexnow_error_redacts_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """IndexNow connection error must not leak the API key."""
    mod = _load_mod()

    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise requests.exceptions.ConnectionError(f"failed: key={FAKE_KEY}")

    monkeypatch.setattr(mod.requests, "post", _raise)
    result = mod.submit_indexnow(TEST_URL, TEST_HOST, FAKE_KEY, dry_run=False)
    assert FAKE_KEY not in result["error"]


# -- Case 5: Non-success response redacts token --------------------------


def test_baidu_non_success_redacts_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Baidu 500 response text must not leak the push token."""
    mod = _load_mod()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = f"server error token={FAKE_TOKEN} oops"
    monkeypatch.setattr(mod.requests, "post", lambda *_a, **_kw: mock_resp)
    result = mod.submit_baidu(TEST_URL, TEST_SITE, FAKE_TOKEN, dry_run=False)
    assert FAKE_TOKEN not in result["error"]


# -- Case 6: Live call still sends real credential -----------------------


def test_live_call_sends_real_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """The actual requests.post call must carry the real token and key."""
    mod = _load_mod()
    calls: list[dict[str, Any]] = []

    def _capture(*args: Any, **kwargs: Any) -> MagicMock:
        calls.append({"args": args, "kwargs": kwargs})
        resp = MagicMock()
        resp.status_code = 200
        return resp

    monkeypatch.setattr(mod.requests, "post", _capture)

    mod.submit_baidu(TEST_URL, TEST_SITE, FAKE_TOKEN, dry_run=False)
    assert FAKE_TOKEN in calls[0]["args"][0]

    calls.clear()
    mod.submit_indexnow(TEST_URL, TEST_HOST, FAKE_KEY, dry_run=False)
    assert calls[0]["kwargs"]["json"]["key"] == FAKE_KEY


# -- Case 7: _output_result hides credentials in both modes -------------


def test_output_result_hides_credentials(capsys: pytest.CaptureFixture[str]) -> None:
    """Human and JSON output of a dry-run result must not contain credentials."""
    mod = _load_mod()
    baidu = mod.submit_baidu(TEST_URL, TEST_SITE, FAKE_TOKEN, dry_run=True)
    indexnow = mod.submit_indexnow(TEST_URL, TEST_HOST, FAKE_KEY, dry_run=True)
    google = {
        "status": "dry_run",
        "endpoint": "https://indexing.googleapis.com/v3/urlNotifications:publish",
        "payload": {},
    }

    result = {
        "status": "dry_run",
        "url": TEST_URL,
        "google": google,
        "indexnow": indexnow,
        "baidu": baidu,
    }

    # Human mode
    mod._output_result(result, human=True)
    captured = capsys.readouterr()
    assert FAKE_TOKEN not in captured.out
    assert FAKE_KEY not in captured.out

    # JSON mode
    mod._output_result(result, human=False)
    captured = capsys.readouterr()
    assert FAKE_TOKEN not in captured.out
    assert FAKE_KEY not in captured.out


# -- Case 8: Truncation boundary does not leak a credential prefix ------


def test_truncation_boundary_redacts_before_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    """A credential straddling the 300-char boundary must be scrubbed before truncation."""
    mod = _load_mod()
    # Place FAKE_TOKEN so it starts at position 290 and extends past 300
    filler = "X" * 290
    body = filler + FAKE_TOKEN + " tail"
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = body
    monkeypatch.setattr(mod.requests, "post", lambda *_a, **_kw: mock_resp)
    result = mod.submit_baidu(TEST_URL, TEST_SITE, FAKE_TOKEN, dry_run=False)
    # Neither the full token nor its leading 8-char prefix should appear
    assert FAKE_TOKEN not in result["error"]
    assert FAKE_TOKEN[:8] not in result["error"]
