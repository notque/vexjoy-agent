"""Runtime mirror gating tests for install.sh.

install.sh syncs an optional runtime mirror (codex, factory, hermes,
reasonix) only when the runtime's command is on PATH or its home dir
already exists. A clean HOME gains no runtime dirs for absent runtimes;
a pre-existing runtime dir keeps syncing even without the command.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

# Shells out to the full install.sh. Deselected from the default local run
# by the marker filter in pyproject.toml; CI still runs it via `-m ""`.
pytestmark = [pytest.mark.slow, pytest.mark.integration]

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
NODE = shutil.which("node")

RUNTIMES = ("codex", "factory", "hermes", "reasonix")
ALL_RUNTIMES = ("claude", *RUNTIMES)
HOOK_RUNTIMES = ("claude", "codex", "factory", "reasonix")
EXACT_PRIMARY_CALL = "Call the Skill tool with `testing`."
EXACT_STACK_CALL = "Call the Skill tool with `process`."

if shutil.which("bash") is None:
    pytest.skip("bash not available on this platform", allow_module_level=True)


def _run_install(
    fake_home: Path,
    args: tuple[str, ...] = ("--copy", "--force"),
    *,
    install_sh: Path = INSTALL_SH,
    profile: Path | None = None,
    stdin: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    env = {**os.environ, "HOME": str(fake_home), "TERM": "dumb"}
    if profile is not None:
        env["VEXJOY_INSTALL_PROFILE"] = str(profile)
    if extra_env is not None:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(install_sh), *args],
        env=env,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=300,
    )


def _install_all_runtimes(
    fake_home: Path,
    args: tuple[str, ...] = ("--copy", "--force"),
    *,
    profile: Path | None = None,
) -> subprocess.CompletedProcess:
    for runtime in RUNTIMES:
        (fake_home / f".{runtime}").mkdir(exist_ok=True)
    return _run_install(fake_home, args, profile=profile)


def _installed_do_skill(fake_home: Path, runtime: str) -> Path:
    suffix = Path("skills") / "do/SKILL.md" if runtime == "reasonix" else Path("skills/meta/do/SKILL.md")
    return fake_home / f".{runtime}" / suffix


def _run_installed_builder(
    fake_home: Path,
    runtime: str,
    *,
    skill: str = "testing",
    stack: tuple[str, ...] = ("process",),
) -> subprocess.CompletedProcess:
    payload = {
        "agent": "python-general-engineer",
        "skill": skill,
        "complexity": "medium",
        "model": "opus",
        "health": "-",
        "stack": list(stack),
        "task_spec": {"intent": "verify installed Skill-tool calls"},
    }
    return subprocess.run(
        [
            "python3",
            str(fake_home / f".{runtime}" / "scripts/build-dispatch.py"),
            "--json",
            json.dumps(payload),
        ],
        env={**os.environ, "HOME": str(fake_home), "TERM": "dumb"},
        capture_output=True,
        text=True,
        timeout=30,
    )


def _assert_installed_contract(fake_home: Path, runtime: str) -> None:
    result = _run_installed_builder(fake_home, runtime)
    assert result.returncode == 0, f"{runtime}: {result.stderr}"
    assert result.stdout.count(EXACT_PRIMARY_CALL) == 1, runtime
    assert result.stdout.count(EXACT_STACK_CALL) == 1, runtime
    assert "Call the Skill tool with" in _installed_do_skill(fake_home, runtime).read_text(encoding="utf-8")
    helper = fake_home / f".{runtime}" / "skills/process/workflow/references/workflow-helpers.js"
    if helper.exists():
        assert "Call the Skill tool with" in helper.read_text(encoding="utf-8")
    if runtime in HOOK_RUNTIMES:
        hook_helper = fake_home / f".{runtime}" / "hooks/lib/skill_directives.py"
        assert "Call the Skill tool with" in hook_helper.read_text(encoding="utf-8")


@pytest.fixture
def fake_home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    return home


def _fake_npm(tmp_path: Path) -> tuple[Path, Path]:
    """Return a PATH prefix with a network-free npm that records clean installs."""
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    npm_log = tmp_path / "npm.log"
    npm = fake_bin / "npm"
    npm.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        'printf \'%s|%s\\n\' "$PWD" "$*" >> "$FAKE_NPM_LOG"\n'
        'rm -rf "$PWD/node_modules"\n'
        'mkdir -p "$PWD/node_modules"\n'
        'touch "$PWD/node_modules/.installed-by-test"\n',
        encoding="utf-8",
    )
    npm.chmod(0o755)
    return fake_bin, npm_log


def _isolated_source(tmp_path: Path) -> Path:
    """Copy tracked installer inputs without local private/untracked state."""
    source = tmp_path / "source"
    source.mkdir()
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout.split(b"\0")
    for raw_path in tracked:
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        original = REPO_ROOT / relative
        if not original.is_file() or "node_modules" in relative.parts:
            continue
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
    return source


def _gateway_install_dirs(npm_log: Path) -> set[Path]:
    lines = npm_log.read_text(encoding="utf-8").splitlines()
    expected_args = "ci --ignore-scripts --no-audit --no-fund"
    assert lines
    assert all(line.endswith(f"|{expected_args}") for line in lines)
    return {Path(line.split("|", 1)[0]) for line in lines}


def test_copy_mode_installs_gateway_in_repository_and_each_runtime_copy(
    fake_home: Path,
    tmp_path: Path,
) -> None:
    """Every real scripts copy gets an isolated, lockfile-backed npm install."""
    for runtime in RUNTIMES:
        (fake_home / f".{runtime}").mkdir()
    source = _isolated_source(tmp_path)
    fake_bin, npm_log = _fake_npm(tmp_path)

    result = _run_install(
        fake_home,
        install_sh=source / "install.sh",
        extra_env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "FAKE_NPM_LOG": str(npm_log),
        },
    )
    assert result.returncode == 0, result.stderr[-2000:]

    expected = {source / "scripts/jev_gateway"}
    expected.update(fake_home / f".{runtime}/scripts/jev_gateway" for runtime in ALL_RUNTIMES)
    assert _gateway_install_dirs(npm_log) == expected
    for gateway_dir in expected:
        assert (gateway_dir / "package-lock.json").is_file()
        assert (gateway_dir / "node_modules/.installed-by-test").is_file()


def test_symlink_mode_installs_gateway_once_and_runtime_links_share_it(
    fake_home: Path,
    tmp_path: Path,
) -> None:
    """Symlink mirrors do not repeat npm ci against the same repository tree."""
    for runtime in RUNTIMES:
        (fake_home / f".{runtime}").mkdir()
    # Force the installer's conflict prompt into whole-directory replacement
    # mode; otherwise skills use the independent per-item layout path.
    existing_skills = fake_home / ".claude/skills"
    existing_skills.mkdir(parents=True)
    (existing_skills / "external-skill").mkdir()
    source = _isolated_source(tmp_path)
    fake_bin, npm_log = _fake_npm(tmp_path)

    result = _run_install(
        fake_home,
        ("--symlink", "--force"),
        install_sh=source / "install.sh",
        extra_env={
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "FAKE_NPM_LOG": str(npm_log),
        },
        stdin="2\n",
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert _gateway_install_dirs(npm_log) == {source / "scripts/jev_gateway"}

    for runtime in ALL_RUNTIMES:
        scripts_dir = fake_home / f".{runtime}/scripts"
        assert scripts_dir.is_symlink(), runtime
        assert (scripts_dir / "jev_gateway/node_modules/.installed-by-test").is_file(), runtime


def test_clean_home_skips_absent_runtimes(fake_home: Path) -> None:
    """No runtime dir is created for a runtime with no command and no dir."""
    absent = [r for r in RUNTIMES if shutil.which(r) is None]
    if not absent:
        pytest.skip("every runtime command is on PATH; nothing to verify")

    result = _run_install(fake_home)
    assert result.returncode == 0, result.stderr[-2000:]

    for runtime in absent:
        runtime_dir = fake_home / f".{runtime}"
        assert not runtime_dir.exists(), (
            f"~/.{runtime} was created although the {runtime} command is absent.\nSTDOUT:\n{result.stdout[-2000:]}"
        )


def test_existing_dir_syncs_without_command(fake_home: Path) -> None:
    """A pre-existing runtime dir keeps syncing even without the command."""
    candidates = [r for r in RUNTIMES if shutil.which(r) is None]
    if not candidates:
        pytest.skip("every runtime command is on PATH; nothing to verify")

    runtime = candidates[0]
    runtime_dir = fake_home / f".{runtime}"
    runtime_dir.mkdir()

    result = _run_install(fake_home)
    assert result.returncode == 0, result.stderr[-2000:]

    skills_dir = runtime_dir / "skills"
    assert skills_dir.exists() and any(skills_dir.iterdir()), (
        f"pre-existing ~/.{runtime} was not synced (skills missing/empty).\nSTDOUT:\n{result.stdout[-2000:]}"
    )


def test_installed_skill_call_contract_operates_in_every_runtime(fake_home: Path) -> None:
    """Each installed harness can render exact primary and stack Skill-tool calls."""
    result = _install_all_runtimes(fake_home)
    assert result.returncode == 0, result.stderr[-2000:]
    for runtime in ALL_RUNTIMES:
        _assert_installed_contract(fake_home, runtime)


@pytest.mark.skipif(NODE is None, reason="node not available; native workflow import requires node")
def test_clean_copy_generates_installed_agent_index_before_workflow_import(tmp_path: Path) -> None:
    """A source tree without agents/INDEX.json still installs an importable workflow helper."""
    source = tmp_path / "source"
    home = tmp_path / "home"
    for directory in ("agents", "skills/process/workflow/references", "scripts/lib"):
        (source / directory).mkdir(parents=True, exist_ok=True)
    home.mkdir()

    shutil.copy2(INSTALL_SH, source / "install.sh")
    (source / "requirements.txt").write_text("", encoding="utf-8")
    shutil.copy2(REPO_ROOT / "agents/reviewer-system.md", source / "agents/reviewer-system.md")
    shutil.copy2(REPO_ROOT / "skills/process/workflow/SKILL.md", source / "skills/process/workflow/SKILL.md")
    shutil.copy2(
        REPO_ROOT / "skills/process/workflow/references/workflow-helpers.js",
        source / "skills/process/workflow/references/workflow-helpers.js",
    )
    for script in ("generate-agent-index.py", "generate-skill-index.py"):
        shutil.copy2(REPO_ROOT / "scripts" / script, source / "scripts" / script)
    shutil.copy2(REPO_ROOT / "scripts/lib/frontmatter.py", source / "scripts/lib/frontmatter.py")
    assert not (source / "agents/INDEX.json").exists()

    installed = subprocess.run(
        ["bash", str(source / "install.sh"), "--copy", "--force"],
        cwd=source,
        env={**os.environ, "HOME": str(home), "PATH": "/usr/bin:/bin", "TERM": "dumb"},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert installed.returncode == 0, installed.stderr[-2000:]

    installed_index = home / ".claude/agents/INDEX.json"
    assert installed_index.is_file()
    assert "reviewer-system" in json.loads(installed_index.read_text(encoding="utf-8"))["agents"]

    helper = home / ".claude/skills/process/workflow/references/workflow-helpers.js"
    imported = subprocess.run(
        [NODE, "--input-type=module", "-e", "await import(process.argv[1])", helper.as_uri()],
        cwd=home,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert imported.returncode == 0, imported.stderr


def test_whole_directory_symlink_inventory_keeps_nested_skills(fake_home: Path) -> None:
    """Replace-mode symlinks index their deployed nested paths without flattening."""
    external = fake_home / ".claude/skills/external"
    external.mkdir(parents=True)
    result = _run_install(fake_home, ("--symlink", "--force"), stdin="2\n")
    assert result.returncode == 0, result.stderr[-2000:]

    skills_dir = fake_home / ".claude/skills"
    assert skills_dir.is_symlink()
    index = json.loads((skills_dir / "INDEX.json").read_text(encoding="utf-8"))["skills"]
    entry = index["testing"]
    assert entry["file"] == "skills/process/testing/SKILL.md"
    assert (fake_home / ".claude" / entry["file"]).is_file()
    _assert_installed_contract(fake_home, "claude")


@pytest.mark.parametrize("mode", ["--copy", "--symlink"])
def test_profile_filtered_installed_inventory_drives_dispatch(
    fake_home: Path,
    tmp_path: Path,
    mode: str,
) -> None:
    """Every runtime validates Skill calls against its deployed, filtered inventory."""
    disabled = "quick"
    enabled = "testing"
    disabled_agent = "reviewer-system"
    enabled_agent = "python-general-engineer"
    profile = tmp_path / "profile.yaml"
    profile.write_text(
        f"disabled:\n  skills:\n    - {disabled}\n  agents:\n    - {disabled_agent}\n  hooks: []\n",
        encoding="utf-8",
    )

    result = _install_all_runtimes(fake_home, (mode, "--force"), profile=profile)
    assert result.returncode == 0, result.stderr[-2000:]

    for runtime in ALL_RUNTIMES:
        index_path = fake_home / f".{runtime}" / "skills" / "INDEX.json"
        local_index_path = index_path.with_name("INDEX.local.json")
        assert index_path.is_file(), runtime
        assert not index_path.is_symlink(), runtime
        assert local_index_path.is_file(), runtime
        assert not local_index_path.is_symlink(), runtime
        installed = json.loads(index_path.read_text(encoding="utf-8"))["skills"]
        installed_local = json.loads(local_index_path.read_text(encoding="utf-8"))["skills"]
        assert disabled not in installed, runtime
        assert disabled not in installed_local, runtime
        assert enabled in installed, runtime
        assert enabled in installed_local, runtime

        rejected = _run_installed_builder(fake_home, runtime, skill=disabled, stack=())
        assert rejected.returncode == 2, runtime
        assert "absent from skills/INDEX.json" in rejected.stderr, runtime

    for runtime in ("claude", "codex"):
        agent_index_path = fake_home / f".{runtime}" / "agents/INDEX.json"
        installed_agents = json.loads(agent_index_path.read_text(encoding="utf-8"))["agents"]
        assert disabled_agent not in installed_agents, runtime
        assert enabled_agent in installed_agents, runtime


def test_symlink_profile_transition_removes_disabled_skill_links_and_inventory(
    fake_home: Path,
    tmp_path: Path,
) -> None:
    """Reapplying a stricter profile removes links installed by the prior profile."""
    disabled = "quick"
    enabled = "testing"
    install_args = ("--symlink", "--force")

    initial = _install_all_runtimes(fake_home, install_args)
    assert initial.returncode == 0, initial.stderr[-2000:]

    profile = tmp_path / "stricter-profile.yaml"
    profile.write_text(
        f"disabled:\n  skills:\n    - {disabled}\n  agents: []\n  hooks: []\n",
        encoding="utf-8",
    )
    reapplied = _install_all_runtimes(fake_home, install_args, profile=profile)
    assert reapplied.returncode == 0, reapplied.stderr[-2000:]

    for runtime in ALL_RUNTIMES:
        skills_dir = fake_home / f".{runtime}" / "skills"
        stale_paths = [skills_dir / disabled]
        if runtime != "reasonix":
            stale_paths.append(skills_dir / "process" / disabled)
        for stale_path in stale_paths:
            assert not stale_path.exists() and not stale_path.is_symlink(), (
                runtime,
                stale_path,
            )

        installed = json.loads((skills_dir / "INDEX.json").read_text(encoding="utf-8"))["skills"]
        installed_local = json.loads((skills_dir / "INDEX.local.json").read_text(encoding="utf-8"))["skills"]
        assert disabled not in installed, runtime
        assert disabled not in installed_local, runtime
        assert enabled in installed, runtime
        assert enabled in installed_local, runtime


def test_reasonix_install_restores_preexisting_index_on_uninstall(fake_home: Path) -> None:
    """A VexJoy-managed Reasonix index must not destroy the user's prior inventory."""
    skills_dir = fake_home / ".reasonix" / "skills"
    skills_dir.mkdir(parents=True)
    original = '{"skills":{"user-owned":{"file":"skills/user-owned/SKILL.md"}}}\n'
    index_path = skills_dir / "INDEX.json"
    index_path.write_text(original, encoding="utf-8")

    install_args = ("--symlink", "--force")
    installed = _install_all_runtimes(fake_home, install_args)
    assert installed.returncode == 0, installed.stderr[-2000:]
    assert index_path.read_text(encoding="utf-8") != original

    reinstalled = _install_all_runtimes(fake_home, install_args)
    assert reinstalled.returncode == 0, reinstalled.stderr[-2000:]

    uninstalled = _run_install(fake_home, ("--uninstall", "--force"))
    assert uninstalled.returncode == 0, uninstalled.stderr[-2000:]
    assert index_path.read_text(encoding="utf-8") == original


def test_reasonix_uninstall_leaves_unmanaged_index_untouched(fake_home: Path) -> None:
    """Uninstall removes an index only when an earlier install claimed ownership."""
    skills_dir = fake_home / ".reasonix" / "skills"
    skills_dir.mkdir(parents=True)
    original = '{"skills":{"user-owned":{}}}\n'
    index_path = skills_dir / "INDEX.json"
    index_path.write_text(original, encoding="utf-8")

    result = _run_install(fake_home, ("--uninstall", "--force"))
    assert result.returncode == 0, result.stderr[-2000:]
    assert index_path.read_text(encoding="utf-8") == original
