"""``rollback`` puts back what one run trashed and the settings.json it replaced (lane C, C-07).

install.sh --rollback used to restore the newest settings backup and the newest trash session,
each on its own. The newest trash session was often a later sync's, or the prune that install.sh
runs right after apply, so the apply's own takeover displacements stayed in trash, and a sync's
backup could stand in for the settings.json from before the install.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from scripts.tests.vexinstall_support import Env, commit_all, git, skill_md, world

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vexinstall import apply as apply_mod
from vexinstall import rollback as rollback_mod

__all__ = ["world"]

USER_SETTINGS = {"model": "user-choice", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}
USER_ALPHA = "---\nname: alpha\ndescription: the user's own alpha\n---\n"
USER_OMEGA = "---\nname: omega\ndescription: the user's own omega\n---\n"


def _ok(res) -> None:
    assert res.code == 0, f"exit {res.code}\nout={res.out}\nerr={res.err}"


def _state(env: Env) -> Path:
    return env.home / ".claude" / "vexjoy"


def _point(env: Env) -> dict:
    return json.loads((_state(env) / "rollback.json").read_text())


def _user_home(env: Env) -> tuple[Path, Path]:
    """A user skill at a desired dest (apply --takeover trashes it) and a user settings.json."""
    alpha = env.skills("claude") / "alpha"
    alpha.mkdir(parents=True)
    (alpha / "SKILL.md").write_text(USER_ALPHA)
    spath = env.home / ".claude" / "settings.json"
    spath.write_text(json.dumps(USER_SETTINGS, indent=2) + "\n")
    return alpha, spath


def _users_alpha_is_back(alpha: Path) -> bool:
    return (alpha / "SKILL.md").read_text() == USER_ALPHA


def test_rollback_restores_its_own_run_not_a_later_sync(world: Env) -> None:
    alpha, spath = _user_home(world)
    before = spath.read_bytes()
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    assert not _users_alpha_is_back(alpha)
    # A later sync trashes a skill whose source left the repo, and backs up the settings it rewrites.
    git(world.repo, "rm", "-r", "-q", "skills/content/zeta")
    commit_all(world.repo, "drop zeta")
    edited = json.loads(spath.read_text())
    edited["hooks"].pop("SessionStart")
    spath.write_text(json.dumps(edited))
    _ok(world.run("sync", "--target", "claude"))
    zeta = world.skills("claude") / "zeta"
    assert not os.path.lexists(zeta)
    assert len(list((_state(world) / "trash").iterdir())) == 2
    assert len(list((_state(world) / "backups").glob("settings.*.json"))) == 2

    res = world.run("rollback")
    _ok(res)
    assert _users_alpha_is_back(alpha)
    assert spath.read_bytes() == before, "the backup apply took, not the one the sync took"
    assert not os.path.lexists(zeta), "the sync's trash is not part of the run"
    assert str(alpha) not in world.ledger_dests("claude")
    assert res.out[0].startswith("[rollback] run run-1 (apply)"), res.out


def test_rollback_restores_the_apply_and_the_prune_of_one_run(world: Env) -> None:
    alpha, _ = _user_home(world)
    gone = world.skills("claude") / "gone-skill"
    gone.symlink_to(world.home / "nowhere")
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    _ok(world.run("prune", "--unowned", "--confirm", "--target", "claude", "--run-id", "run-1"))
    assert not os.path.lexists(gone)
    point = _point(world)
    assert point["run"] == "run-1" and point["commands"] == ["apply", "prune"] and len(point["trash"]) == 2
    _ok(world.run("rollback"))
    assert os.path.islink(gone)
    assert _users_alpha_is_back(alpha), "the apply's trash, older than the prune's, is restored too"


def test_rollback_undoes_an_uninstall(world: Env) -> None:
    _ok(world.run("apply", "--target", "claude"))
    spath = world.home / ".claude" / "settings.json"
    installed = spath.read_bytes()
    _ok(world.run("uninstall", "--target", "claude", "--run-id", "un-1"))
    assert not os.path.lexists(world.skills("claude") / "alpha")
    res = world.run("rollback")
    _ok(res)
    assert (world.skills("claude") / "alpha" / "SKILL.md").is_file()
    assert spath.read_bytes() == installed
    assert res.out[0].startswith("[rollback] run un-1 (uninstall)"), res.out


def test_steps_that_change_nothing_and_syncs_keep_the_last_point(world: Env) -> None:
    _user_home(world)
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    first = (_state(world) / "rollback.json").read_bytes()
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-2"))
    _ok(world.run("prune", "--unowned", "--confirm", "--target", "claude", "--run-id", "run-2"))
    git(world.repo, "rm", "-r", "-q", "skills/content/zeta")
    commit_all(world.repo, "drop zeta")
    _ok(world.run("sync", "--target", "claude"))  # trashes zeta, records nothing
    assert (_state(world) / "rollback.json").read_bytes() == first


def test_a_step_without_a_run_id_is_its_own_run(world: Env) -> None:
    _user_home(world)
    gone = world.skills("claude") / "gone-skill"
    gone.symlink_to(world.home / "nowhere")
    _ok(world.run("apply", "--target", "claude", "--takeover"))
    apply_run = _point(world)["run"]
    _ok(world.run("prune", "--unowned", "--confirm", "--target", "claude"))
    point = _point(world)
    assert point["run"] != apply_run and point["commands"] == ["prune"] and len(point["trash"]) == 1


def test_rollback_runs_once_and_a_new_run_starts_a_new_point(world: Env) -> None:
    alpha, spath = _user_home(world)
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    _ok(world.run("rollback"))
    assert _point(world)["restored_at"]
    after = spath.read_bytes()
    again = world.run("rollback")
    _ok(again)
    assert "already rolled back" in again.out[0], again.out
    assert spath.read_bytes() == after
    (alpha / "SKILL.md").write_text(USER_ALPHA.replace("own", "second"))
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    point = _point(world)
    assert point["restored_at"] is None and point["commands"] == ["apply"]


def test_dry_run_lists_the_point_and_writes_nothing(world: Env) -> None:
    alpha, _ = _user_home(world)
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    point = _point(world)
    res = world.run("rollback", "--dry-run")
    _ok(res)
    text = "\n".join(res.out)
    assert "would restore" in text and point["trash"][0] in text and point["settings_backup"] in text
    assert _point(world) == point and not _users_alpha_is_back(alpha)


def test_nothing_recorded(world: Env) -> None:
    res = world.run("rollback")
    _ok(res)
    assert "nothing to roll back" in res.out[0]


def test_missing_trash_or_backup_is_reported(world: Env) -> None:
    alpha, spath = _user_home(world)
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    point = _point(world)
    (_state(world) / "backups" / f"settings.{point['settings_backup']}.json").unlink()
    res = world.run("rollback")
    assert res.code == 1, res
    assert any("settings backup" in line and point["settings_backup"] in line for line in res.err), res.err
    assert _users_alpha_is_back(alpha), "the trash that is still there comes back"
    assert _point(world)["restored_at"]


def test_a_damaged_session_is_reported_and_the_rest_still_comes_back(world: Env) -> None:
    alpha, _ = _user_home(world)
    gone = world.skills("claude") / "gone-skill"
    gone.symlink_to(world.home / "nowhere")
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    _ok(world.run("prune", "--unowned", "--confirm", "--target", "claude", "--run-id", "run-1"))
    apply_ts, prune_ts = _point(world)["trash"]
    (_state(world) / "trash" / prune_ts / "manifest.json").write_text("{not json")
    res = world.run("rollback")
    assert res.code == 1, res
    assert any(prune_ts in line and "not fully restored" in line for line in res.err), res.err
    assert _users_alpha_is_back(alpha) and not os.path.lexists(gone)
    assert str(alpha) not in world.ledger_dests("claude"), "the displaced entry left the saved ledger"
    assert res.data["failed"] == [prune_ts] and apply_ts not in res.data["failed"]


def _fail(*_args: object, **_kwargs: object) -> None:
    raise PermissionError(13, "simulated write failure")


def _interrupt(*_args: object, **_kwargs: object) -> None:
    raise KeyboardInterrupt


@pytest.mark.parametrize("stop", ["oserror", "interrupt"])
def test_an_apply_that_dies_partway_is_the_run_rolled_back(
    world: Env, monkeypatch: pytest.MonkeyPatch, stop: str
) -> None:
    # The run that died after its takeover is what --rollback undoes. The earlier run-1, never rolled
    # back, used to stand in for it: rollback put back run-1's alpha and the settings.json from before
    # run-1, and left the failed run's displaced omega in trash. An OSError stops the run with exit 1
    # (it saves the ledger and records its point as usual); Ctrl-C or a bug re-raises after both.
    alpha, spath = _user_home(world)
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    installed = spath.read_bytes()
    md = world.repo / "skills" / "meta" / "omega" / "SKILL.md"
    md.parent.mkdir(parents=True)
    md.write_text(skill_md("omega"))
    commit_all(world.repo, "add omega")
    omega = world.skills("claude") / "omega"
    omega.mkdir()
    (omega / "SKILL.md").write_text(USER_OMEGA)
    with monkeypatch.context() as mp:
        # dies after the takeover moved omega to trash
        mp.setattr(apply_mod, "apply_settings", _fail if stop == "oserror" else _interrupt)
        if stop == "oserror":
            res = world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-2")
            assert res.code == 1 and any("run stopped early" in line for line in res.err), res
        else:
            with pytest.raises(KeyboardInterrupt):
                world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-2")
    assert _point(world)["run"] == "run-2"
    assert str(omega) in world.ledger_dests("claude"), "the ledger keeps what the failed run installed"
    res = world.run("rollback")
    _ok(res)
    assert res.out[0].startswith("[rollback] run run-2 (apply)"), res.out
    assert (omega / "SKILL.md").read_text() == USER_OMEGA
    assert not _users_alpha_is_back(alpha), "run-1 is not part of the run that failed"
    assert spath.read_bytes() == installed


def test_an_uninstall_that_dies_partway_is_the_run_rolled_back(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    alpha, _ = _user_home(world)
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    beta = world.skills("claude") / "beta"
    with monkeypatch.context() as mp:
        mp.setattr(apply_mod, "apply_settings", _fail)  # dies after every owned entry went to trash
        with pytest.raises(PermissionError):
            world.run("uninstall", "--target", "claude", "--run-id", "un-1")
    assert not os.path.lexists(beta)
    assert str(beta) not in world.ledger_dests("claude"), "the ledger drops what the failed uninstall removed"
    res = world.run("rollback")
    _ok(res)
    assert res.out[0].startswith("[rollback] run un-1 (uninstall)"), res.out
    assert (beta / "SKILL.md").is_file()
    assert not _users_alpha_is_back(alpha), "the uninstall trashed the engine's alpha, which comes back"


def test_a_prune_that_dies_partway_is_the_run_rolled_back(world: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    alpha, _ = _user_home(world)
    _ok(world.run("apply", "--target", "claude", "--takeover", "--run-id", "run-1"))
    gone = world.skills("claude") / "gone-skill"
    gone.symlink_to(world.home / "nowhere")
    with monkeypatch.context() as mp:
        mp.setattr(apply_mod, "write_report", _fail)  # dies after the move
        with pytest.raises(PermissionError):
            world.run("prune", "--unowned", "--confirm", "--target", "claude", "--run-id", "pr-1")
    assert not os.path.lexists(gone)
    res = world.run("rollback")
    _ok(res)
    assert res.out[0].startswith("[rollback] run pr-1 (prune)"), res.out
    assert os.path.islink(gone)
    assert not _users_alpha_is_back(alpha)


def test_damaged_point_never_names_a_path_outside_the_state_dir(world: Env) -> None:
    sdir = _state(world)
    sdir.mkdir(parents=True, exist_ok=True)
    bad = {"run": "r", "commands": ["apply"], "trash": ["../../../etc", "20260101T000000000000Z"]}
    (sdir / "rollback.json").write_text(json.dumps({**bad, "settings_backup": "../x"}))
    point = rollback_mod.load(sdir)
    assert point is not None
    assert point.trash == ["20260101T000000000000Z"] and point.settings_backup is None
    (sdir / "rollback.json").write_text("{not json")
    assert rollback_mod.load(sdir) is None
    res = world.run("rollback")
    _ok(res)
    assert "unreadable" in res.out[0], res.out


@pytest.mark.parametrize("bad", ["", "-x", "a b", "x" * 65, "../up", "run-1\n"])
def test_run_id_is_checked(world: Env, bad: str) -> None:
    with pytest.raises(SystemExit):
        world.run("apply", "--target", "claude", "--run-id", bad)
