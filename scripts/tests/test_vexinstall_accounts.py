"""vexinstall installs into CLAUDE_CONFIG_DIR account profiles: links, hook registrations, backups."""

from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.tests.vexinstall_support import Env, git, world

OWNED = ["h1.py", "h2.py", "h3.py"]
USER_HOOK = {"type": "command", "command": "python3 /opt/user/hook.py"}


def add_account(world: Env, name: str, settings: dict | None = None) -> Path:
    """Create a profile dir under the temp HOME and register it."""
    cfg = world.home / ".claude-accounts" / name
    cfg.mkdir(parents=True)
    if settings is not None:
        (cfg / "settings.json").write_text(json.dumps(settings, indent=2))
    reg = world.home / ".claude-accounts" / "accounts.json"
    data = json.loads(reg.read_text()) if reg.exists() else {}
    data[name] = {"alias": f"c-{name}", "config_dir": str(cfg)}
    reg.write_text(json.dumps(data))
    return cfg


def commands(settings_path: Path) -> list[str]:
    """Every hook command in a settings.json."""
    hooks = json.loads(settings_path.read_text()).get("hooks", {})
    return [e["command"] for groups in hooks.values() for g in groups for e in g["hooks"]]


def test_apply_registers_hooks_and_links_without_touching_other_keys(world: Env) -> None:
    user_settings = {
        "env": {"ANTHROPIC_BASE_URL": "https://gateway.invalid"},
        "model": "opus",
        "permissions": {"allow": ["Bash(ls)"]},
        "enabledPlugins": {"p@m": True},
        "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [USER_HOOK]}]},
    }
    cfg = add_account(world, "max1", user_settings)
    before = (cfg / "settings.json").read_bytes()
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    assert any(line.startswith("account max1:") for line in res.out), res.out
    merged = json.loads((cfg / "settings.json").read_text())
    for key in ("env", "model", "permissions", "enabledPlugins"):
        assert merged[key] == user_settings[key]
    assert merged["hooks"]["PreToolUse"] == user_settings["hooks"]["PreToolUse"]
    cmds = commands(cfg / "settings.json")
    for name in OWNED:
        assert any(c.endswith(f'hooks/{name}"') or c.endswith(f"hooks/{name}") for c in cmds), (name, cmds)
    assert oct((cfg / "settings.json").stat().st_mode & 0o777) == "0o600"
    for entry in ("skills", "agents", "commands", "hooks", "scripts"):
        link = cfg / entry
        if (world.home / ".claude" / entry).exists():
            assert os.readlink(link) == str(world.home / ".claude" / entry)
    backups = list((world.home / ".claude" / "vexjoy" / "backups").glob("max1-settings.*.json"))
    assert len(backups) == 1 and backups[0].read_bytes() == before


def test_apply_is_idempotent_for_profiles(world: Env) -> None:
    cfg = add_account(world, "max1", {"theme": "dark"})
    assert world.run("apply", "--target", "claude").code == 0
    settled = (cfg / "settings.json").read_bytes()
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    assert not any(line.startswith("account ") for line in res.out), res.out
    assert (cfg / "settings.json").read_bytes() == settled
    backups = list((world.home / ".claude" / "vexjoy" / "backups").glob("max1-settings.*.json"))
    assert len(backups) == 1


def test_profile_without_settings_file_gets_one(world: Env) -> None:
    cfg = add_account(world, "max2")
    assert world.run("apply", "--target", "claude").code == 0
    assert len(commands(cfg / "settings.json")) >= len(OWNED)


def test_conflicting_profile_dir_is_reported_not_replaced(world: Env) -> None:
    cfg = add_account(world, "max1", {})
    (cfg / "skills").mkdir()
    (cfg / "skills" / "mine").mkdir()
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    assert not os.path.islink(cfg / "skills") and (cfg / "skills" / "mine").is_dir()
    doctor = world.run("doctor", "--target", "claude")
    assert doctor.code == 1
    assert any("account-link-conflict" in line for line in doctor.out), doctor.out


def test_doctor_reports_zero_drift_then_detects_removed_registration(world: Env) -> None:
    cfg = add_account(world, "max1", {})
    assert world.run("apply", "--target", "claude").code == 0
    clean = world.run("doctor", "--target", "claude")
    assert not any("account-" in line for line in clean.out), clean.out
    data = json.loads((cfg / "settings.json").read_text())
    data["hooks"].pop(next(iter(data["hooks"])))
    (cfg / "settings.json").write_text(json.dumps(data))
    drift = world.run("doctor", "--target", "claude")
    assert drift.code == 1
    assert any("account-hooks-drift" in line and "max1: missing=" in line for line in drift.out), drift.out
    assert world.run("apply", "--target", "claude").code == 0
    assert not any("account-" in line for line in world.run("doctor", "--target", "claude").out)


def test_stale_owned_registration_is_replaced(world: Env) -> None:
    stale = {"type": "command", "command": 'python3 "$HOME/.claude/hooks/retired-hook.py"'}
    cfg = add_account(world, "max1", {"hooks": {"Stop": [{"hooks": [stale, USER_HOOK]}]}})
    hooks_dir = world.home / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    assert world.run("apply", "--target", "claude").code == 0
    cmds = commands(cfg / "settings.json")
    assert USER_HOOK["command"] in cmds
    assert stale["command"] not in cmds


def test_unreadable_profile_settings_is_left_alone(world: Env) -> None:
    cfg = add_account(world, "max1")
    (cfg / "settings.json").write_text("{not json")
    good = add_account(world, "max2", {})
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    assert (cfg / "settings.json").read_text() == "{not json"
    assert commands(good / "settings.json")
    assert world.run("doctor", "--target", "claude").code == 1


def test_plan_writes_nothing_and_lists_profiles(world: Env) -> None:
    cfg = add_account(world, "max1", {"theme": "dark"})
    before = (cfg / "settings.json").read_bytes()
    res = world.run("plan", "--target", "claude")
    assert res.code == 0
    assert any(line.startswith("account max1:") and "missing=" in line for line in res.out), res.out
    assert (cfg / "settings.json").read_bytes() == before
    assert not (cfg / "skills").exists() and not os.path.islink(cfg / "skills")


def test_sync_updates_profiles(world: Env) -> None:
    cfg = add_account(world, "max1", {})
    assert world.run("sync", "--target", "claude").code == 0
    assert commands(cfg / "settings.json")


def test_uninstall_removes_owned_registrations_only(world: Env) -> None:
    cfg = add_account(world, "max1", {"hooks": {"Stop": [{"hooks": [USER_HOOK]}]}})
    assert world.run("apply", "--target", "claude").code == 0
    assert len(commands(cfg / "settings.json")) > 1
    assert world.run("uninstall", "--target", "claude").code == 0
    assert commands(cfg / "settings.json") == [USER_HOOK["command"]]


def test_missing_profile_dir_is_skipped(world: Env) -> None:
    reg = world.home / ".claude-accounts"
    reg.mkdir()
    (reg / "accounts.json").write_text(json.dumps({"gone": {"alias": "g", "config_dir": str(reg / "gone")}}))
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    assert not (reg / "gone").exists()


def test_non_claude_target_leaves_profiles_alone(world: Env) -> None:
    cfg = add_account(world, "max1", {"theme": "dark"})
    before = (cfg / "settings.json").read_bytes()
    assert world.run("apply", "--target", "hermes").code == 0
    assert (cfg / "settings.json").read_bytes() == before


def ship_env(world: Env, env: dict[str, str]) -> None:
    """Commit *env* as the fixture repo's settings env block."""
    repo_settings = world.repo / ".claude" / "settings.json"
    data = json.loads(repo_settings.read_text())
    data["env"] = env
    repo_settings.write_text(json.dumps(data, indent=2))
    git(world.repo, "commit", "-qam", "ship env")


def test_apply_gives_profiles_the_repo_env_and_attribution(world: Env) -> None:
    ship_env(world, {"REPO_FLAG": "1", "USER_SET": "repo"})
    base = world.home / ".claude" / "settings.json"
    cfg = add_account(world, "max1", {"env": {"USER_SET": "mine", "OTHER": "x"}, "theme": "dark"})
    kept = add_account(world, "max2", {"attribution": {"commit": "custom", "pr": ""}})
    res = world.run("apply", "--target", "claude")
    assert res.code == 0, res.err
    merged = json.loads((cfg / "settings.json").read_text())
    assert merged["env"] == {"USER_SET": "mine", "OTHER": "x", "REPO_FLAG": "1"}
    assert merged["attribution"] == {"commit": "", "pr": ""}
    assert merged["theme"] == "dark"
    assert json.loads((kept / "settings.json").read_text())["attribution"] == {"commit": "custom", "pr": ""}
    base_settings = json.loads(base.read_text())
    for key in ("env", "attribution"):
        assert merged[key].keys() >= base_settings[key].keys(), key
    assert any(line.startswith("account max1:") and "attribution +1" in line for line in res.out), res.out
    again = world.run("apply", "--target", "claude")
    assert again.code == 0, again.err
    assert not any(line.startswith("account ") for line in again.out), again.out


def test_profile_old_env_default_moves_once(world: Env) -> None:
    key = "CLAUDE_CODE_AUTO_COMPACT_WINDOW"
    cfg = add_account(world, "max1", {"env": {key: "400000"}})
    ship_env(world, {key: "500000"})
    assert world.run("apply", "--target", "claude").code == 0
    assert json.loads((cfg / "settings.json").read_text())["env"][key] == "500000"
    assert f"{key}=400000" in world.ledger()["settings"]["env_migrated:max1"]
    data = json.loads((cfg / "settings.json").read_text())
    data["env"][key] = "400000"
    (cfg / "settings.json").write_text(json.dumps(data))
    assert world.run("apply", "--target", "claude").code == 0
    assert json.loads((cfg / "settings.json").read_text())["env"][key] == "400000"


def test_doctor_reports_profile_missing_attribution(world: Env) -> None:
    cfg = add_account(world, "max1", {})
    assert world.run("apply", "--target", "claude").code == 0
    data = json.loads((cfg / "settings.json").read_text())
    del data["attribution"]
    (cfg / "settings.json").write_text(json.dumps(data))
    drift = world.run("doctor", "--target", "claude")
    assert drift.code == 1
    assert any("account-settings-drift" in line and "max1: attribution +1" in line for line in drift.out), drift.out
    assert world.run("apply", "--target", "claude").code == 0
    assert not any("account-" in line for line in world.run("doctor", "--target", "claude").out)


def test_uninstall_keeps_profile_env_and_attribution(world: Env) -> None:
    ship_env(world, {"REPO_FLAG": "1"})
    cfg = add_account(world, "max1", {})
    assert world.run("apply", "--target", "claude").code == 0
    assert world.run("uninstall", "--target", "claude").code == 0
    data = json.loads((cfg / "settings.json").read_text())
    assert data["env"] == {"REPO_FLAG": "1"}
    assert data["attribution"] == {"commit": "", "pr": ""}
