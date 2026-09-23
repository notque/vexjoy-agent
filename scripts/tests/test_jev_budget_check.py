from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import jev_limits

_spec = importlib.util.spec_from_file_location("jev_budget_check", SCRIPTS / "jev-budget-check.py")
budget_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(budget_cli)


def _request(products: int, detail_chars: int = 900) -> dict:
    state = {
        "query": "pay contractors",
        "products": {f"p{i}": {"details": "x" * detail_chars} for i in range(products)},
    }
    questions = {
        f"{h}{i}": {
            "type": "noul",
            "instructions": {"question": "q" * 120, "inspect": f"products.p{i}"},
            "criteria": {"true": "t" * 60, "false": "f" * 60},
        }
        for i in range(products)
        for h in "pmdx"
    }
    return {"state": state, "questions": questions}


def test_small_program_is_ok() -> None:
    result = jev_limits.check_run([_request(4)], concurrency=1)
    assert result["verdict"] == "ok"
    assert result["findings"] == []


def test_catches_full_catalog_fanout_that_fits_every_request() -> None:
    # The jev-sap failure: 20 requests of 16 products, each far under 64k, all at once.
    requests = [_request(16) for _ in range(20)]
    result = jev_limits.check_run(requests, concurrency=20, attempts=3)
    assert result["largest_request_tokens"] < jev_limits.REQUEST_TOKEN_LIMIT
    assert result["verdict"] == "fail"
    messages = " ".join(f["message"] for f in result["findings"])
    assert "tokens/s" in messages and "cascade" in messages


def test_request_over_documented_limit_fails() -> None:
    result = jev_limits.check_run([_request(40, detail_chars=6000)])
    assert result["verdict"] == "fail"
    assert any("request limit" in f["message"] for f in result["findings"])


def test_measured_tokens_override_estimate() -> None:
    result = jev_limits.check_run([_request(4)], measured_tokens_per_run=100_000)
    assert result["tokens_per_run"] == 100_000
    assert any("cascade" in f["message"] for f in result["findings"])


def test_eval_is_priced_and_paced() -> None:
    result = jev_limits.check_run([_request(16)] * 20, concurrency=4, eval_cases=81)
    assert result["eval"]["tokens"] == result["tokens_per_run"] * 81
    assert result["eval"]["min_seconds_between_cases"] > 0
    assert any("eval spends" in f["message"] for f in result["findings"])


def test_backoff_has_jitter_floor_cap_and_honors_retry_after() -> None:
    assert jev_limits.backoff_delay(0, rng=lambda: 0.0) == pytest.approx(0.25)
    assert jev_limits.backoff_delay(0, rng=lambda: 1.0) == pytest.approx(0.5)
    assert jev_limits.backoff_delay(10, rng=lambda: 1.0) == pytest.approx(jev_limits.RETRY_MAX_S)
    assert jev_limits.backoff_delay(0, retry_after=3, rng=lambda: 0.0) == pytest.approx(3.0)


def test_gateway_503_is_a_backoff_signal() -> None:
    assert 503 in jev_limits.RETRY_STATUSES_GATEWAY
    assert 503 not in jev_limits.RETRY_STATUSES_DIRECT


@pytest.mark.parametrize("shape", ["single", "list", "wrapped"])
def test_cli_accepts_payload_shapes_and_sets_exit_code(tmp_path: Path, shape: str, capsys) -> None:
    req = _request(2)
    data = {"single": req, "list": [req], "wrapped": {"requests": [req]}}[shape]
    path = tmp_path / "run.json"
    path.write_text(json.dumps(data))
    assert budget_cli.main(["--payload", str(path)]) == 0
    assert "verdict: OK" in capsys.readouterr().out


def test_cli_fails_on_bad_payload(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("[1, 2]")
    assert budget_cli.main(["--payload", str(path)]) == 2
