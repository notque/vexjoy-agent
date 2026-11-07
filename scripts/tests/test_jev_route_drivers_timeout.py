"""The two /d routing drivers pass their --timeout to the prepare step (was ignored)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]


def _load(filename: str):
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_").removesuffix(".py"), SCRIPTS / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_route(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    import d_route_model

    seen: dict[str, object] = {}

    def prepare(request, project=None, timeout=20.0):
        seen["timeout"] = timeout
        return {"prepared_for": request}

    def pick_route(request, project=None, model=None, scratch=None, prepared=None):
        seen["prepared"] = prepared
        return {"skill": "x", "agent": "a", "prepared": prepared}

    monkeypatch.setattr(d_route_model, "prepare", prepare)
    monkeypatch.setattr(d_route_model, "pick_route", pick_route)
    return seen


def test_corpus_driver_honors_timeout(fake_route, tmp_path: Path) -> None:
    module = _load("jev-" + "eval.py")
    result = module.run_d_route({"request": "fix it"}, None, 3.25, "sonnet", tmp_path)
    assert fake_route["timeout"] == 3.25
    assert fake_route["prepared"] == {"prepared_for": "fix it"}
    assert result["skill"] == "x"


def test_trigger_driver_honors_timeout(fake_route) -> None:
    module = _load("jev-" + "eval-live.py")
    result = module.route_one("review my pr", 2.5)
    assert fake_route["timeout"] == 2.5
    assert fake_route["prepared"] == {"prepared_for": "review my pr"}
    assert result["skill"] == "x"
