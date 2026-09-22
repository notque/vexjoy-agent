"""Hermetic fixtures for vexinstall tests: temp HOME, fixture git repo, fixture overlays.

Nothing here reads or writes the real HOME. Every CLI call passes --home and
--source-root, and the test process HOME env var points at the temp HOME.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from vexinstall import adapters, common, fsops, gitutil, profile, sources
from vexinstall import settings as settings_mod
from vexinstall.adapters import ADAPTERS
from vexinstall.cli import build_parser, dispatch, to_options
from vexinstall.context import Result

__all__ = ["ADAPTERS", "adapters", "common", "fsops", "profile", "settings_mod", "sources"]

TARGETS = ("claude", "codex", "factory", "hermes", "reasonix")
PUBLIC_SKILLS = {
    "meta": ["alpha", "beta"],
    "process": ["gamma", "delta"],
    "content": ["epsilon", "zeta"],
}
BULK_SKILLS = [f"bulk-{i:02d}" for i in range(12)]
SUPPORT = ("shared-patterns", "kb", "voice-shared")
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_NOSYSTEM": "1",
}


def _w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def skill_md(name: str, extra: str = "") -> str:
    """Minimal SKILL.md with frontmatter."""
    return f"---\nname: {name}\ndescription: {name} skill for tests. Use for {name} work.\n{extra}---\n\n# {name}\n"


def git(repo: Path, *args: str) -> str:
    """Run git in the fixture repo."""
    env = {**os.environ, **GIT_ENV}
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env, check=True)
    return out.stdout


def make_repo(path: Path, *, bulk: bool = False) -> Path:
    """Build and commit a toolkit-shaped fixture repo."""
    for cat, names in PUBLIC_SKILLS.items():
        for n in names:
            _w(path / "skills" / cat / n / "SKILL.md", skill_md(n))
    _w(path / "skills" / "process" / "delta" / "references" / "ref.md", "delta reference\n")
    _w(path / "skills" / "process" / "old-thing" / "SKILL.md", skill_md("old-thing", "promoted_to: gamma\n"))
    if bulk:
        for n in BULK_SKILLS:
            _w(path / "skills" / "bulk" / n / "SKILL.md", skill_md(n))
    _w(path / "skills" / "shared-patterns" / "README.md", "shared patterns\n")
    _w(path / "skills" / "kb" / "scripts" / "compile.sh", "#!/bin/sh\necho kb\n")
    _w(path / "skills" / "voice-shared" / "docs" / "VOICE.md", "voice docs\n")
    for a in ("a-eng", "b-eng", "c-eng"):
        _w(path / "agents" / f"{a}.md", f"---\nname: {a}\ndescription: {a} agent\n---\n# {a}\n")
    _w(path / "agents" / "a-eng" / "references" / "r.md", "agent ref\n")
    _w(path / "commands" / "cmd-one.md", "# cmd one\n")
    _w(path / "commands" / "alpha.md", "# shadowed by skill alpha\n")
    for h in ("h1.py", "h2.py", "h3.py"):
        _w(path / "hooks" / h, f"# hook {h}\n")
    _w(path / "hooks" / "lib" / "util.py", "# util\n")
    _w(path / "hooks" / "lib" / "more.py", "# more\n")
    _w(path / "hooks" / "tests" / "test_x.py", "# not installed per-entry\n")
    _w(path / "scripts" / "s1.py", "# s1\n")
    _w(path / "scripts" / "s2.py", "# s2\n")
    _w(path / "scripts" / "tool" / "x.py", "# tool x\n")
    _w(path / "scripts" / "codex-hooks-allowlist.txt", "SessionStart:h1.py matcher=startup\nStop:h2.py\n")
    _w(path / "scripts" / "reasonix-hooks-allowlist.txt", "# comment\nUserPromptSubmit:h1.py\n")
    settings = {
        "attribution": {"commit": "", "pr": ""},
        "hooks": {
            "SessionStart": [
                {
                    "hooks": [
                        {"type": "command", "command": 'python3 "$HOME/.claude/hooks/h1.py"', "timeout": 20000},
                        {"type": "command", "command": 'python3 "$HOME/.claude/hooks/h2.py"'},
                    ]
                }
            ],
            "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/h3.py"}]}],
        },
    }
    _w(path / ".claude" / "settings.json", json.dumps(settings, indent=2))
    _w(path / ".gitignore", "__pycache__/\n*.pyc\nskills/INDEX.json\n")
    git(path, "init", "-q", "-b", "main")
    git(path, "add", "-A")
    git(path, "-c", "commit.gpgsign=false", "commit", "-q", "-m", "fixture")
    gitutil.clear_cache()
    return path


def make_overlays(work: Path, home: Path, *, extra: list[dict] | None = None) -> Path:
    """Private overlay (category) with an excluded voice sub-root overlay (flat, prefixed)."""
    priv = work / "private-skills"
    _w(priv / "priv" / "private-one" / "SKILL.md", skill_md("private-one"))
    _w(priv / "priv" / "private-two" / "SKILL.md", skill_md("private-two"))
    _w(priv / "priv" / "agents" / "p-agent.md", "---\nname: p-agent\ndescription: private agent\n---\n")
    _w(priv / "voice" / "v1" / "skill" / "SKILL.md", skill_md("voice-v1"))
    _w(priv / "voice" / "v1" / "profile.json", '{"name": "v1"}\n')
    _w(priv / "voice" / "v2" / "profile.json", '{"name": "v2"}\n')
    cfg = {
        "overlays": [
            {
                "id": "private",
                "root": str(priv),
                "layout": "category",
                "kinds": ["skills", "agents"],
                "exclude": ["voice"],
            },
            {"id": "voices", "root": str(priv / "voice"), "layout": "flat", "prefix": "voice-"},
            *(extra or []),
        ]
    }
    write_overlays(home, cfg)
    return priv


def write_overlays(home: Path, cfg: dict) -> None:
    """Write ~/.claude/vexjoy/overlays.json under the temp HOME."""
    _w(home / ".claude" / "vexjoy" / "overlays.json", json.dumps(cfg, indent=2))


@dataclass
class Env:
    """One hermetic world."""

    home: Path
    repo: Path
    work: Path
    priv: Path

    def run(self, *args: str, source: Path | None = None) -> Result:
        """Run the CLI in-process."""
        argv = [*args, "--home", str(self.home), "--source-root", str(source or self.repo)]
        gitutil.clear_cache()
        return dispatch(to_options(build_parser().parse_args(argv)))

    def cli(self, *args: str, source: Path | None = None) -> subprocess.CompletedProcess[str]:
        """Run the CLI as a subprocess (python3 -m vexinstall)."""
        env = {
            **os.environ,
            "PYTHONPATH": str(SCRIPTS_DIR),
            "HOME": str(self.home),
            "VEXINSTALL_EPHEMERAL_PREFIXES": os.environ.get("VEXINSTALL_EPHEMERAL_PREFIXES", ""),
        }
        argv = [
            sys.executable,
            "-m",
            "vexinstall",
            *args,
            "--home",
            str(self.home),
            "--source-root",
            str(source or self.repo),
        ]
        return subprocess.run(argv, capture_output=True, text=True, env=env, timeout=120)

    def root(self, target: str) -> Path:
        """Runtime root of a target."""
        return ADAPTERS[target].root_path(self.home)

    def skills(self, target: str) -> Path:
        """Skills dir of a target."""
        return self.root(target) / "skills"

    def ledger(self) -> dict:
        """Parsed ledger."""
        return json.loads((self.home / ".claude" / "vexjoy" / "ledger.json").read_text())

    def ledger_dests(self, target: str) -> set[str]:
        """Ledger dests of one target."""
        return {e["dest"] for e in self.ledger()["entries"] if e["target"] == target}


def tree_hash(root: Path, exclude: tuple[str, ...] = ()) -> str:
    """Hash of names, types, link targets, and bytes under *root* (never follows links)."""
    h = hashlib.sha256()
    if not root.exists():
        return "absent"
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel_dir = os.path.relpath(dirpath, root)
        dirnames[:] = sorted(d for d in dirnames if os.path.normpath(os.path.join(rel_dir, d)) not in exclude)
        for name in sorted(dirnames + filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.normpath(os.path.join(rel_dir, name))
            if rel in exclude:
                continue
            h.update(rel.encode() + b"\0")
            if os.path.islink(full):
                h.update(b"L" + os.readlink(full).encode())
            elif os.path.isfile(full):
                with open(full, "rb") as fh:
                    h.update(b"F" + fh.read())
                h.update(oct(os.stat(full).st_mode & 0o777).encode())
            else:
                h.update(b"D")
    return h.hexdigest()


def repo_hash(repo: Path) -> str:
    """Fixture repo tree hash, excluding .git internals."""
    return tree_hash(repo, exclude=(".git",))


def assert_repo_clean(repo: Path) -> None:
    """``git status --porcelain`` must be empty."""
    status = git(repo, "status", "--porcelain")
    assert status == "", f"fixture repo dirty:\n{status}"


def expected_skill_names(target: str, *, overlays: bool = True, bulk: bool = False) -> set[str]:
    """Flat skill-root names a target should hold after apply."""
    names = {n for ns in PUBLIC_SKILLS.values() for n in ns} | set(SUPPORT)
    if bulk:
        names |= set(BULK_SKILLS)
    if overlays:
        names |= {"private-one", "private-two", "voice-v1", "voice-v2"}
    return names


def commit_all(repo: Path, msg: str) -> None:
    """Stage and commit everything in the fixture repo."""
    git(repo, "add", "-A")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-q", "-m", msg)
    gitutil.clear_cache()


def make_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, bulk: bool = False, overlays: bool = True) -> Env:
    """Temp HOME + fixture repo + fixture overlays; HOME env points at the temp HOME."""
    home = tmp_path / "home"
    home.mkdir(parents=True)
    work = tmp_path / "work"
    repo = make_repo(work / "repo", bulk=bulk)
    priv = make_overlays(work, home) if overlays else work / "no-overlay"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("VEXINSTALL_EPHEMERAL_PREFIXES", "/nonexistent-ephemeral-prefix")
    monkeypatch.delenv("VEXINSTALL_SOURCE_ROOT", raising=False)
    monkeypatch.delenv("VEXJOY_INSTALL_PROFILE", raising=False)
    return Env(home=home, repo=repo, work=work, priv=priv)


@pytest.fixture
def world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    """Standard world; asserts the fixture repo is clean after the test."""
    env = make_world(tmp_path, monkeypatch)
    yield env
    assert_repo_clean(env.repo)


@pytest.fixture
def bulk_world(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Env]:
    """World with 12 extra public skills (for the mass-removal cap)."""
    env = make_world(tmp_path, monkeypatch, bulk=True)
    yield env
    assert_repo_clean(env.repo)


def find_named(root: Path, name: str) -> list[Path]:
    """Every path under *root* named *name*, including dangling symlinks.

    ``Path.rglob`` skips broken symlinks on Python 3.10, and trashed dangling
    links are exactly what the prune tests look for.
    """
    import os

    hits: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        for entry in (*dirnames, *filenames):
            if entry == name:
                hits.append(Path(dirpath) / entry)
    return hits
