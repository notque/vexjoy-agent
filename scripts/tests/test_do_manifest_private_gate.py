"""The /do manifest gates private (overlay) entries on the request.

/do reads its routing manifest through `get-routing-manifest.sh
--request-file`. A private entry renders only when the request names its
domain, through the same `routing_index_merge.gate_private_entries` that
pre-route.py and jev-route.py apply. Synthetic `quuxcorp-*` and `voice-blorvik`
names stand in for real private skills.

Run with: python3 -m pytest scripts/tests/test_do_manifest_private_gate.py -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))

import routing_index_merge as rim


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


routing_manifest = _load("routing_manifest_private_gate", SCRIPTS / "routing-manifest.py")

PUBLIC_SKILLS = {
    "research": {
        "description": "Research: gather sources, compare findings, write a cited summary.",
        "triggers": ["research", "fact-check"],
        "owner": "public",
    },
    "writing": {
        "description": "Writing: articles, explainers, voice profiles.",
        "triggers": ["write article", "voice"],
        "owner": "public",
    },
}
PRIVATE_SKILLS = {
    "quuxcorp-research": {
        "description": "Research for the Quuxcorp site.",
        "triggers": ["quuxcorp-research", "quuxcorp", "research"],
        "owner": "overlay:synthetic",
    },
    "voice-blorvik": {
        "description": "Write in Blorvik's voice.",
        "triggers": ["voice-blorvik", "voice", "blorvik"],
        "owner": "overlay:synthetic",
    },
}
PUBLIC_AGENTS = {
    "research-coordinator-engineer": {"description": "Research coordination.", "owner": "public"},
}


@pytest.fixture
def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An installed index with two public and two private (overlay) skills."""
    index = tmp_path / "installed"
    index.mkdir()
    (index / "skills.json").write_text(json.dumps({"skills": {**PUBLIC_SKILLS, **PRIVATE_SKILLS}}), encoding="utf-8")
    (index / "agents.json").write_text(json.dumps({"agents": PUBLIC_AGENTS}), encoding="utf-8")
    monkeypatch.setenv("VEXJOY_INDEX_DIR", str(index))
    return index


def _manifest(tmp_path: Path, *args: str) -> str:
    env = dict(os.environ)
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "routing-manifest.py"), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        check=True,
    )
    return proc.stdout


def _skill_names(manifest: str) -> set[str]:
    section = manifest.split("SKILLS:", 1)[1].split("PIPELINES:", 1)[0]
    return {line.split()[0] for line in section.splitlines() if line.strip()}


def _request_file(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "request.txt"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------- routing-manifest.py


def test_manifest_reuses_the_shared_gate() -> None:
    assert routing_manifest._gate_private_entries is rim.gate_private_entries


@pytest.mark.parametrize(
    "request_text",
    [
        "research how other CLI agents route requests",
        "write an article in a friendly voice",
        "",
    ],
)
def test_generic_request_hides_private_skills(installed: Path, tmp_path: Path, request_text: str) -> None:
    out = _manifest(tmp_path, "--request-file", str(_request_file(tmp_path, request_text)))
    assert _skill_names(out) == {"research", "writing"}


@pytest.mark.parametrize(
    ("request_text", "expected"),
    [
        ("research this week's Quuxcorp results", "quuxcorp-research"),
        ("use quuxcorp-research on the new roster", "quuxcorp-research"),
        ("write this in blorvik's voice", "voice-blorvik"),
    ],
)
def test_domain_request_shows_its_private_skill(
    installed: Path, tmp_path: Path, request_text: str, expected: str
) -> None:
    out = _manifest(tmp_path, "--request-file", str(_request_file(tmp_path, request_text)))
    names = _skill_names(out)
    assert expected in names
    assert {"research", "writing"} <= names
    assert len(names) == 3  # the other private skill stays hidden


def test_request_flag_gates_like_request_file(installed: Path, tmp_path: Path) -> None:
    assert _skill_names(_manifest(tmp_path, "--request", "research RSS history")) == {"research", "writing"}
    assert "quuxcorp-research" in _skill_names(_manifest(tmp_path, "--request", "quuxcorp roster"))


def test_json_output_is_gated(installed: Path, tmp_path: Path) -> None:
    out = _manifest(tmp_path, "--json", "--request", "research RSS history")
    assert not any(e.get("private") for e in json.loads(out))


def test_no_request_keeps_every_entry(installed: Path, tmp_path: Path) -> None:
    """The session cache is built without a request, so it holds every entry."""
    assert _skill_names(_manifest(tmp_path)) == set(PUBLIC_SKILLS) | set(PRIVATE_SKILLS)


def test_unreadable_request_file_hides_private_and_keeps_public(installed: Path, tmp_path: Path) -> None:
    out = _manifest(tmp_path, "--request-file", str(tmp_path / "missing.txt"))
    assert _skill_names(out) == {"research", "writing"}
    assert "research-coordinator-engineer" in out


# ---------------------------------------------------------------- get-routing-manifest.sh


def _fake_sdir(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Scripts dir with a stub generator that echoes its arguments; returns (sdir, home, index)."""
    base = tmp_path / "base"
    sdir = base / "scripts"
    sdir.mkdir(parents=True)
    shutil.copy(SCRIPTS / "get-routing-manifest.sh", sdir / "get-routing-manifest.sh")
    (sdir / "routing-manifest.py").write_text(
        "import sys\nprint('GENERATED', ' '.join(sys.argv[1:]).strip())\n", encoding="utf-8"
    )
    (sdir / "routing_index_merge.py").write_text("# merge helper\n", encoding="utf-8")
    home = tmp_path / "home"
    (home / ".claude" / "cache").mkdir(parents=True)
    index = tmp_path / "index"
    index.mkdir()
    return sdir, home, index


def _fresh_cache(sdir: Path, home: Path, index: Path) -> None:
    """Write a cache whose hash matches the inputs, as the SessionStart hook does."""
    sys.path.insert(0, str(REPO / "hooks" / "lib"))
    import manifest_cache

    old = os.environ.get("VEXJOY_INDEX_DIR")
    os.environ["VEXJOY_INDEX_DIR"] = str(index)
    try:
        digest = manifest_cache.compute_input_hash(sdir)
    finally:
        if old is None:
            os.environ.pop("VEXJOY_INDEX_DIR", None)
        else:
            os.environ["VEXJOY_INDEX_DIR"] = old
    cache = home / ".claude" / "cache"
    (cache / "routing-manifest.txt").write_text("CACHED\n", encoding="utf-8")
    (cache / "routing-manifest.hash").write_text(digest + "\n", encoding="utf-8")


def _run_sh(sdir: Path, home: Path, index: Path, *args: str) -> str:
    env = dict(os.environ, HOME=str(home), VEXJOY_INDEX_DIR=str(index))
    proc = subprocess.run(
        ["bash", str(sdir / "get-routing-manifest.sh"), *args], capture_output=True, text=True, env=env, check=True
    )
    return proc.stdout.strip()


def test_sh_passes_request_to_generator_when_a_private_overlay_exists(tmp_path: Path) -> None:
    sdir, home, index = _fake_sdir(tmp_path)
    (index / "skills.json").write_text(json.dumps({"skills": PRIVATE_SKILLS}), encoding="utf-8")
    _fresh_cache(sdir, home, index)
    request = _request_file(tmp_path, "research RSS history")
    assert _run_sh(sdir, home, index, "--request-file", str(request)) == f"GENERATED --request-file {request}"
    assert _run_sh(sdir, home, index) == "CACHED"  # no request: cache as before


def test_sh_legacy_local_index_counts_as_private_source(tmp_path: Path) -> None:
    sdir, home, index = _fake_sdir(tmp_path)
    (sdir.parent / "skills").mkdir()
    (sdir.parent / "skills" / "INDEX.local.json").write_text('{"skills": {}}', encoding="utf-8")
    _fresh_cache(sdir, home, index)
    request = _request_file(tmp_path, "anything")
    assert _run_sh(sdir, home, index, "--request-file", str(request)).startswith("GENERATED --request-file")


def test_sh_serves_cache_when_no_private_source_exists(tmp_path: Path) -> None:
    sdir, home, index = _fake_sdir(tmp_path)
    (index / "skills.json").write_text(json.dumps({"skills": PUBLIC_SKILLS}), encoding="utf-8")
    _fresh_cache(sdir, home, index)
    request = _request_file(tmp_path, "research RSS history")
    assert _run_sh(sdir, home, index, "--request-file", str(request)) == "CACHED"


def test_do_passes_the_request_to_the_manifest() -> None:
    text = (REPO / "skills" / "meta" / "do" / "SKILL.md").read_text(encoding="utf-8")
    step0 = text.split("**Step 0:", 1)[1].split("**Step 1:", 1)[0]
    assert 'bash "$SDIR/get-routing-manifest.sh" --request-file "$REQUEST_FILE"' in step0
    assert step0.index("REQUEST_FILE=$(mktemp)") < step0.index("get-routing-manifest.sh")
