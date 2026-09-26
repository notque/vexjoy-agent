"""Tests for manage-accounts.py — covers _upsert_managed_block, cmd_add, cmd_list."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "manage-accounts.py"
SPEC = importlib.util.spec_from_file_location("manage_accounts", SCRIPT)
ma = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ma)


@pytest.fixture(autouse=True)
def _fake_default_config(tmp_path, monkeypatch):
    """Point ~/.claude at a temp dir so no test links to the real one."""
    default = tmp_path / "dot-claude"
    for entry in ma.SHARED_ENTRIES:
        (default / entry).mkdir(parents=True)
    monkeypatch.setattr(ma, "DEFAULT_CONFIG", default)
    return default


# ---------------------------------------------------------------------------
# _upsert_managed_block
# ---------------------------------------------------------------------------

HEADER = "# managed-start"
FOOTER = "# managed-end"


def test_upsert_inserts_into_empty_file(tmp_path):
    f = tmp_path / "config.fish"
    block = f"{HEADER}\nfunction c1\nend\n{FOOTER}\n"
    changed = ma._upsert_managed_block(f, block, HEADER, FOOTER)
    assert changed
    assert "function c1" in f.read_text()


def test_upsert_replaces_existing_block(tmp_path):
    f = tmp_path / "config.fish"
    f.write_text(f"# existing\n{HEADER}\nfunction c1\nend\n{FOOTER}\n# after\n", encoding="utf-8")
    new_block = f"{HEADER}\nfunction c1\nend\nfunction c2\nend\n{FOOTER}\n"
    changed = ma._upsert_managed_block(f, new_block, HEADER, FOOTER)
    assert changed
    content = f.read_text()
    assert "function c2" in content
    assert "# existing" in content
    assert "# after" in content


def test_upsert_returns_false_when_unchanged(tmp_path):
    f = tmp_path / "config.fish"
    block = f"{HEADER}\nfunction c1\nend\n{FOOTER}\n"
    f.write_text(block, encoding="utf-8")
    changed = ma._upsert_managed_block(f, block, HEADER, FOOTER)
    assert not changed


def test_upsert_appends_when_only_header_present(tmp_path):
    """Partial marker (header only, footer missing) → safe append, not corruption."""
    f = tmp_path / "config.fish"
    f.write_text(f"# existing\n{HEADER}\n# orphaned\n", encoding="utf-8")
    block = f"{HEADER}\nfunction c1\nend\n{FOOTER}\n"
    changed = ma._upsert_managed_block(f, block, HEADER, FOOTER)
    assert changed
    content = f.read_text()
    # Original content preserved; new block appended
    assert "# existing" in content
    assert f"{HEADER}\nfunction c1\nend\n{FOOTER}" in content


def test_upsert_appends_when_footer_before_header(tmp_path):
    """Corrupted order (footer before header) → safe append."""
    f = tmp_path / "config.fish"
    f.write_text(f"{FOOTER}\n{HEADER}\n", encoding="utf-8")
    block = f"{HEADER}\nfunction c1\nend\n{FOOTER}\n"
    changed = ma._upsert_managed_block(f, block, HEADER, FOOTER)
    assert changed


def test_upsert_creates_parent_dirs(tmp_path):
    f = tmp_path / "deep" / "nested" / "config.fish"
    block = f"{HEADER}\nstuff\n{FOOTER}\n"
    ma._upsert_managed_block(f, block, HEADER, FOOTER)
    assert f.exists()


# ---------------------------------------------------------------------------
# cmd_add
# ---------------------------------------------------------------------------


def _make_args(**kwargs):
    """Build a minimal Namespace for testing."""
    import argparse

    return argparse.Namespace(**kwargs)


def test_cmd_add_creates_account(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")
    # Prevent auto install-aliases from touching the real shell config
    monkeypatch.setattr(ma, "_do_install_aliases", lambda *_a, **_kw: 0)

    rc = ma.cmd_add(_make_args(name="work", alias="cwork"))
    assert rc == 0
    registry = json.loads((tmp_path / "accounts.json").read_text())
    assert "work" in registry
    assert registry["work"]["alias"] == "cwork"
    assert (tmp_path / "work").is_dir()


def test_cmd_add_rejects_duplicate_name(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")
    monkeypatch.setattr(ma, "_do_install_aliases", lambda *_a, **_kw: 0)

    ma.cmd_add(_make_args(name="work", alias="c1"))
    rc = ma.cmd_add(_make_args(name="work", alias="c2"))
    assert rc == 1


def test_cmd_add_rejects_duplicate_alias(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")
    monkeypatch.setattr(ma, "_do_install_aliases", lambda *_a, **_kw: 0)

    ma.cmd_add(_make_args(name="work", alias="c1"))
    rc = ma.cmd_add(_make_args(name="personal", alias="c1"))
    assert rc == 1


def test_cmd_add_rejects_invalid_names(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")
    monkeypatch.setattr(ma, "_do_install_aliases", lambda *_a, **_kw: 0)

    for bad in ("", "foo/bar", ".hidden"):
        rc = ma.cmd_add(_make_args(name=bad, alias=None))
        assert rc == 1


def test_cmd_add_auto_assigns_alias(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")
    monkeypatch.setattr(ma, "_do_install_aliases", lambda *_a, **_kw: 0)

    ma.cmd_add(_make_args(name="work", alias=None))
    ma.cmd_add(_make_args(name="personal", alias=None))
    registry = json.loads((tmp_path / "accounts.json").read_text())
    aliases = {v["alias"] for v in registry.values()}
    assert aliases == {"c1", "c2"}


# ---------------------------------------------------------------------------
# cmd_list
# ---------------------------------------------------------------------------


def test_cmd_list_shows_default_account(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")

    ma.cmd_list(_make_args())
    out = capsys.readouterr().out
    assert "(default)" in out
    assert "No managed accounts" in out


def test_cmd_list_shows_managed_accounts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")
    monkeypatch.setattr(ma, "_do_install_aliases", lambda *_a, **_kw: 0)

    (tmp_path / "work").mkdir()
    (tmp_path / "accounts.json").write_text(
        json.dumps({"work": {"alias": "cwork", "config_dir": str(tmp_path / "work")}}),
        encoding="utf-8",
    )

    ma.cmd_list(_make_args())
    out = capsys.readouterr().out
    assert "cwork" in out
    assert "work" in out
    assert "(default)" in out


def test_cmd_list_flags_missing_config_dir(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")

    (tmp_path / "accounts.json").write_text(
        json.dumps({"ghost": {"alias": "c1", "config_dir": str(tmp_path / "ghost")}}),
        encoding="utf-8",
    )

    ma.cmd_list(_make_args())
    out = capsys.readouterr().out
    assert "missing" in out


# ---------------------------------------------------------------------------
# cmd_check
# ---------------------------------------------------------------------------


def test_cmd_check_passes_when_credentials_present(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")

    cfg = tmp_path / "work"
    cfg.mkdir()
    (cfg / "credentials.json").write_text("{}", encoding="utf-8")
    ma._link_shared(cfg)
    (tmp_path / "accounts.json").write_text(
        json.dumps({"work": {"alias": "cwork", "config_dir": str(cfg)}}),
        encoding="utf-8",
    )

    rc = ma.cmd_check(_make_args())
    assert rc == 0


def test_cmd_check_fails_when_credentials_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")

    cfg = tmp_path / "work"
    cfg.mkdir()
    (tmp_path / "accounts.json").write_text(
        json.dumps({"work": {"alias": "cwork", "config_dir": str(cfg)}}),
        encoding="utf-8",
    )

    rc = ma.cmd_check(_make_args())
    assert rc == 1


def test_cmd_check_fails_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")

    (tmp_path / "accounts.json").write_text(
        json.dumps({"ghost": {"alias": "c1", "config_dir": str(tmp_path / "ghost")}}),
        encoding="utf-8",
    )

    rc = ma.cmd_check(_make_args())
    assert rc == 1


# ---------------------------------------------------------------------------
# _fish_alias_block / _bash_alias_block
# ---------------------------------------------------------------------------


def test_fish_alias_block_uses_set_lx():
    accounts = {"work": {"alias": "cwork", "config_dir": "/tmp/work"}}
    block = ma._fish_alias_block(accounts)
    assert "set -lx CLAUDE_CONFIG_DIR" in block
    assert "function cwork" in block
    assert 'claude --dangerously-skip-permissions --system-prompt="." $argv' in block


def test_bash_alias_block_inlines_env():
    accounts = {"work": {"alias": "cwork", "config_dir": "/tmp/work"}}
    block = ma._bash_alias_block(accounts)
    assert "alias cwork=" in block
    assert "CLAUDE_CONFIG_DIR" in block
    assert 'claude --dangerously-skip-permissions --system-prompt="."' in block


# ---------------------------------------------------------------------------
# Integration: add → check alias in block
# ---------------------------------------------------------------------------


def test_add_then_install_aliases_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")
    captured = []
    monkeypatch.setattr(ma, "_do_install_aliases", lambda shell, dry_run: captured.append((shell, dry_run)) or 0)

    ma.cmd_add(_make_args(name="work", alias="cwork"))
    assert len(captured) == 1
    assert captured[0][1] is False  # dry_run=False on auto-install


# ---------------------------------------------------------------------------
# _link_shared / cmd_link
# ---------------------------------------------------------------------------


def test_cmd_add_links_shared_dirs(tmp_path, monkeypatch, _fake_default_config):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")
    monkeypatch.setattr(ma, "_do_install_aliases", lambda *_a, **_kw: 0)

    assert ma.cmd_add(_make_args(name="work", alias="c1")) == 0
    for entry in ma.SHARED_ENTRIES:
        link = tmp_path / "work" / entry
        assert link.is_symlink()
        assert link.resolve() == (_fake_default_config / entry).resolve()


def test_link_shared_replaces_empty_dir_and_is_idempotent(tmp_path):
    cfg = tmp_path / "acct"
    (cfg / "skills").mkdir(parents=True)
    assert ma._link_shared(cfg) == []
    assert (cfg / "skills").is_symlink()
    assert ma._link_shared(cfg) == []


def test_link_shared_merges_synced_skills(tmp_path, _fake_default_config):
    """skills/synced/<uuid>/ written by Claude Code moves into the shared dir."""
    cfg = tmp_path / "acct"
    (cfg / "skills" / "synced" / "uuid-b" / "pdf").mkdir(parents=True)
    (_fake_default_config / "skills" / "synced" / "uuid-a").mkdir(parents=True)
    assert ma._link_shared(cfg) == []
    assert (cfg / "skills").is_symlink()
    assert (_fake_default_config / "skills" / "synced" / "uuid-a").is_dir()
    assert (_fake_default_config / "skills" / "synced" / "uuid-b" / "pdf").is_dir()


def test_link_shared_keeps_conflicting_entries(tmp_path, _fake_default_config):
    cfg = tmp_path / "acct"
    (cfg / "skills").mkdir(parents=True)
    (cfg / "skills" / "mine").write_text("account copy", encoding="utf-8")
    (_fake_default_config / "skills" / "mine").write_text("shared copy", encoding="utf-8")
    problems = ma._link_shared(cfg)
    assert len(problems) == 1 and "conflict" in problems[0]
    assert (cfg / "skills" / "mine").read_text() == "account copy"
    assert (cfg / "agents").is_symlink()


def test_cmd_link_all_accounts_and_check(tmp_path, monkeypatch):
    monkeypatch.setattr(ma, "ACCOUNTS_ROOT", tmp_path)
    monkeypatch.setattr(ma, "REGISTRY", tmp_path / "accounts.json")
    reg = {}
    for name in ("max1", "max2"):
        cfg = tmp_path / name
        cfg.mkdir()
        (cfg / "credentials.json").write_text("{}", encoding="utf-8")
        reg[name] = {"alias": f"c{name[-1]}", "config_dir": str(cfg)}
    (tmp_path / "accounts.json").write_text(json.dumps(reg), encoding="utf-8")

    assert ma.cmd_check(_make_args()) == 1
    assert ma.cmd_link(_make_args(name=None)) == 0
    assert ma.cmd_check(_make_args()) == 0
    assert ma.cmd_link(_make_args(name="nope")) == 1
