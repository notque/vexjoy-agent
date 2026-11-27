"""/d upgrade: route-time gate preflight (scripts/d-preflight.py) and the Jev-down signal fallback."""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    with patch("sys.exit"):
        spec.loader.exec_module(mod)
    return mod


preflight = _load(SCRIPTS / "d-preflight.py", "d_preflight")
sys.path.insert(0, str(SCRIPTS))
jev_route = _load(SCRIPTS / "jev-route.py", "jev_route_signals")


def test_new_agent_file_reports_adr_and_consultation_cost(monkeypatch) -> None:
    monkeypatch.chdir(REPO)
    report = preflight.preflight(["agents/brand-new-thing.md"], REPO)
    costs = " ".join(report["paths"][0]["costs"])
    assert "adr/brand-new-thing.md" in costs and "adr-query.py register" in costs
    assert "synthesis.md" in costs


def test_new_hook_reports_the_adr_gate(monkeypatch) -> None:
    monkeypatch.chdir(REPO)
    costs = preflight.preflight(["hooks/brand-new-gate.py"], REPO)["paths"][0]["costs"]
    assert any("ADR gate" in c and "brand-new-gate" in c for c in costs)


def test_existing_file_edit_has_no_creation_cost(tmp_path: Path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    (repo / "skills" / "meta" / "d").mkdir(parents=True)
    (repo / "skills" / "meta" / "d" / "SKILL.md").write_text("---\nname: d\n---\n", encoding="utf-8")
    (repo / "hooks").mkdir(parents=True)
    shutil.copytree(REPO / "hooks" / "lib", repo / "hooks" / "lib")
    for name in (
        "pretool-unified-gate.py",
        "pretool-adr-creation-gate.py",
        "pretool-synthesis-gate.py",
        "pretool-private-name-leak-gate.py",
    ):
        shutil.copy2(REPO / "hooks" / name, repo / "hooks" / name)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    monkeypatch.chdir(repo)
    report = preflight.preflight(["skills/meta/d/SKILL.md"], repo)
    assert all(report["gates_loaded"].values())
    assert report["paths"][0]["costs"] == []


def test_key_shaped_string_is_reported_redacted(tmp_path: Path) -> None:
    # Built at runtime so the repo's own commit-time scan does not flag this fixture.
    sample = "".join(["AK", "IA", "QWERTYUI", "OPASDFGH"])
    field = "_".join(["aws", "access", "key"])
    target = tmp_path / "example.yml"
    target.write_text(field + ": " + sample + "\n", encoding="utf-8")
    report = preflight.preflight([str(target)], tmp_path)
    assert report["security"], report
    rendered = preflight.render(report)
    assert sample not in rendered and "security review blocks the commit" in rendered


def test_private_terms_are_redacted(tmp_path: Path) -> None:
    import re

    class Leak:
        @staticmethod
        def private_terms(_root):
            return {"secretskill"}, set()

        @staticmethod
        def term_pattern(_leaves, _strong):
            return re.compile("secretskill")

        @staticmethod
        def _redact(name: str) -> str:
            return name[0] + "…" + name[-1]

    f = tmp_path / "notes.md"
    f.write_text("see secretskill for details\n", encoding="utf-8")
    hits = preflight.private_term_hits([str(f)], Leak, tmp_path)
    assert hits == [{"file": str(f), "line": 1, "term": "s…l"}]


def test_preflight_never_fails_the_route(capsys) -> None:
    with patch.object(preflight, "preflight", side_effect=RuntimeError("boom")):
        assert preflight.main(["--paths", "x"]) == 0
    assert "skipped" in capsys.readouterr().out


def test_signals_fall_back_to_the_session_when_jev_gave_none() -> None:
    prepared = {"signals": None, "error": "Jev unavailable: test"}
    signals, source = jev_route._signals(prepared, {"signals": {"tests_requested": True, "bogus": True}})
    assert source == "session" and signals == {"tests_requested": True}
    assert jev_route._signals({"signals": {"local_only": True}}, {"signals": {"tests_requested": True}}) == (
        {"local_only": True},
        "jev",
    )
    assert jev_route._signals({"signals": None}, {}) == (None, "none")


def test_session_signals_count_only_real_true() -> None:
    signals, _ = jev_route._signals({"signals": None}, {"signals": {"tests_requested": "false", "local_only": True}})
    assert signals == {"tests_requested": False, "local_only": True}
