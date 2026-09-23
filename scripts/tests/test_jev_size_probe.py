from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location("jev_size_probe", SCRIPTS / "jev-size-probe.py")
probe_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe_mod)


class _HTTP503(Exception):
    code = 503


def _req(chars: int) -> dict:
    return {"state": {"x": "y" * chars}, "questions": {"q": {"type": "noul", "instructions": "ok?"}}}


def test_pick_variants_spreads_sizes() -> None:
    reqs = [_req(n * 1000) for n in range(10)]
    picked = probe_mod.pick_variants(reqs, 3)
    sizes = [len(r["state"]["x"]) for r in picked]
    assert sizes == [0, 5000, 9000] or sizes == [0, 4000, 9000]


def test_probe_round_robins_and_reports_failure_by_size() -> None:
    small, large = _req(1000), _req(40000)
    order: list[int] = []

    def send(req: dict) -> int:
        order.append(len(req["state"]["x"]))
        if req is large and len(order) % 4 == 2:
            raise _HTTP503()
        return 300 if req is small else 10000

    rows = probe_mod.probe([small, large], send, rounds=4)
    assert order == [1000, 40000] * 4  # interleaved, one at a time
    assert rows[0]["failure_rate"] == 0 and rows[1]["failed"] == 2
    assert rows[1]["statuses"] == {"503": 2}
    assert rows[1]["tokens_per_answer"] == 20000  # 10k tokens x 4 sends / 2 successes
    rec = probe_mod.recommend(rows)
    assert rec["largest_reliable_request_tokens"] == 300


def test_status_of_never_uses_message_body() -> None:
    assert probe_mod.status_of(_HTTP503("secret body")) == "503"
    assert probe_mod.status_of(RuntimeError("Vercel gateway HTTP 429")) == "429"
    assert probe_mod.status_of(RuntimeError("boom")) == "RuntimeError"
