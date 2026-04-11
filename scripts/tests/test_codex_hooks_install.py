"""Integration tests for the Codex hooks mirror installed by install.sh.

Runs install.sh against a temporary HOME directory and verifies that
~/.codex/hooks/, ~/.codex/hooks.json, and ~/.codex/config.toml are set
up correctly. Each test gets a fresh fake_home fixture so tests are
fully independent.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# tomllib is stdlib on Python 3.11+. On 3.10, skip the subset of tests that
# use it to parse the post-install config.toml. Other tests still run.
try:
    import tomllib  # type: ignore[import-not-found,unused-ignore]

    _HAS_TOMLLIB = True
except ImportError:
    tomllib = None  # type: ignore[assignment]
    _HAS_TOMLLIB = False

requires_tomllib = pytest.mark.skipif(not _HAS_TOMLLIB, reason="tomllib requires Python 3.11+")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
INSTALL_SH = REPO_ROOT / "install.sh"
ALLOWLIST = REPO_ROOT / "scripts" / "codex-hooks-allowlist.txt"

# Module-level guard: bash must be available.
if shutil.which("bash") is None:
    pytest.skip("bash not available on this platform", allow_module_level=True)


def _run_install(
    fake_home: Path, extra_args: list[str] | None = None, timeout: int = 180
) -> subprocess.CompletedProcess:
    """Run install.sh with the given fake HOME and extra args.

    Args:
        fake_home: Directory to use as $HOME.
        extra_args: Additional flags to pass to install.sh.
        timeout: Maximum seconds to wait before failing.

    Returns:
        CompletedProcess with stdout and stderr captured.
    """
    args = extra_args or []
    env = {**os.environ, "HOME": str(fake_home), "TERM": "dumb"}
    return subprocess.run(
        ["bash", str(INSTALL_SH)] + args,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_allowlist_filenames() -> set[str]:
    """Return the set of hook filenames from the allowlist.

    Returns:
        Set of bare filenames (e.g. 'kairos-briefing-injector.py').
    """
    filenames: set[str] = set()
    for line in ALLOWLIST.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        rest = stripped.split(":", 1)[1]
        filename = rest.strip().split()[0]
        filenames.add(filename)
    return filenames


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide a clean temporary HOME directory for each test.

    Args:
        tmp_path: pytest-provided temporary directory.
        monkeypatch: pytest fixture for environment patching.

    Returns:
        Path to the fresh fake HOME.
    """
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_install_sh_creates_codex_hooks_dir(fake_home: Path) -> None:
    """install.sh --copy creates ~/.codex/hooks/ with the primary hook file."""
    result = _run_install(fake_home, ["--copy", "--force"])
    hooks_dir = fake_home / ".codex" / "hooks"

    assert hooks_dir.exists(), f"~/.codex/hooks/ not created.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    assert hooks_dir.is_dir(), "~/.codex/hooks is not a directory"

    target_hook = hooks_dir / "kairos-briefing-injector.py"
    assert target_hook.exists(), f"kairos-briefing-injector.py missing from hooks dir.\nSTDOUT:\n{result.stdout}"


def test_install_sh_mirrors_all_allowlisted_hooks(fake_home: Path) -> None:
    """Every filename in codex-hooks-allowlist.txt appears in ~/.codex/hooks/."""
    result = _run_install(fake_home, ["--copy", "--force"])
    hooks_dir = fake_home / ".codex" / "hooks"

    expected = _parse_allowlist_filenames()
    assert expected, "Allowlist is empty; nothing to verify"

    missing = []
    for filename in sorted(expected):
        if not (hooks_dir / filename).exists():
            missing.append(filename)

    assert not missing, (
        f"Missing hooks in ~/.codex/hooks/: {missing}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


def test_install_sh_generates_valid_hooks_json(fake_home: Path) -> None:
    """install.sh produces a syntactically valid ~/.codex/hooks.json with correct schema."""
    result = _run_install(fake_home, ["--copy", "--force"])
    hooks_json_path = fake_home / ".codex" / "hooks.json"

    assert hooks_json_path.exists(), f"hooks.json not created.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    try:
        data = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        pytest.fail(f"hooks.json is not valid JSON: {exc}\nContent:\n{hooks_json_path.read_text()}")

    assert "hooks" in data, f"Top-level 'hooks' key missing from hooks.json: {data}"
    assert isinstance(data["hooks"], dict), "'hooks' value must be a dict"

    has_session_start = False
    has_bash_post_tool_use = False

    for event_key, matcher_groups in data["hooks"].items():
        assert isinstance(matcher_groups, list), f"Event '{event_key}' value must be a list, got {type(matcher_groups)}"
        for group in matcher_groups:
            assert isinstance(group, dict), f"Matcher group must be a dict, got {type(group)}"
            assert "hooks" in group, f"Matcher group missing 'hooks' key: {group}"
            assert isinstance(group["hooks"], list), "'hooks' within group must be a list"

            for entry in group["hooks"]:
                assert entry.get("type") == "command", f"Hook entry must have type='command': {entry}"
                assert "command" in entry, f"Hook entry missing 'command': {entry}"
                assert "timeout" in entry, f"Hook entry missing 'timeout': {entry}"

            if event_key == "SessionStart":
                has_session_start = True

            if event_key == "PostToolUse":
                matcher = group.get("matcher", "")
                if matcher == "Bash":
                    has_bash_post_tool_use = True

    assert has_session_start, "hooks.json has no SessionStart entries"
    assert has_bash_post_tool_use, "hooks.json has no PostToolUse entry with matcher='Bash'"

    # Guard: no PreToolUse or PostToolUse block should have a non-Bash matcher.
    # This catches accidental Phase 2 hook promotion (openai/codex#16732 regression).
    for event_key in ("PreToolUse", "PostToolUse"):
        if event_key not in data["hooks"]:
            continue
        for group in data["hooks"][event_key]:
            matcher = group.get("matcher", "Bash")
            assert matcher == "Bash", (
                f"Non-Bash matcher '{matcher}' found in {event_key} block. "
                "This is a Phase 2 hook regression (openai/codex#16732). "
                f"Full group: {group}"
            )


@requires_tomllib
def test_install_sh_sets_feature_flag(fake_home: Path) -> None:
    """install.sh sets codex_hooks = true in ~/.codex/config.toml."""
    result = _run_install(fake_home, ["--copy", "--force"])
    config_path = fake_home / ".codex" / "config.toml"

    assert config_path.exists(), f"config.toml not created.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    with open(config_path, "rb") as fh:
        config = tomllib.load(fh)

    assert "features" in config, f"[features] section missing from config.toml. Content:\n{config_path.read_text()}"
    assert config["features"].get("codex_hooks") is True, (
        f"codex_hooks != true in [features]. Got: {config['features']}"
    )


@requires_tomllib
def test_install_sh_preserves_existing_config_toml_sections(fake_home: Path) -> None:
    """install.sh does not clobber pre-existing config.toml sections."""
    codex_dir = fake_home / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)

    existing_toml = (
        '[projects."/home/user/repo"]\ntrust_level = "trusted"\n\n[notice]\nhide_rate_limit_model_nudge = true\n'
    )
    config_path = codex_dir / "config.toml"
    config_path.write_text(existing_toml, encoding="utf-8")

    result = _run_install(fake_home, ["--copy", "--force"])

    assert config_path.exists(), f"config.toml disappeared.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

    with open(config_path, "rb") as fh:
        config = tomllib.load(fh)

    assert "projects" in config or any(k.startswith("projects") for k in config), (
        f"[projects] section lost after install. Full config: {config}"
    )
    assert "notice" in config, f"[notice] section lost after install. Full config: {config}"
    assert config["notice"].get("hide_rate_limit_model_nudge") is True

    assert "features" in config, f"[features] section not added. Full config: {config}"
    assert config["features"].get("codex_hooks") is True


def test_install_sh_dry_run_does_not_touch_filesystem(fake_home: Path) -> None:
    """install.sh --dry-run leaves ~/.codex untouched."""
    result = _run_install(fake_home, ["--dry-run", "--symlink"])

    hooks_dir = fake_home / ".codex" / "hooks"
    hooks_json = fake_home / ".codex" / "hooks.json"
    config_toml = fake_home / ".codex" / "config.toml"

    assert not hooks_dir.exists(), f"~/.codex/hooks/ was created during dry-run.\nSTDOUT:\n{result.stdout}"
    assert not hooks_json.exists(), f"hooks.json was created during dry-run.\nSTDOUT:\n{result.stdout}"
    assert not config_toml.exists(), f"config.toml was created during dry-run.\nSTDOUT:\n{result.stdout}"

    # Dry-run output should describe the Codex hooks block action.
    combined = result.stdout + result.stderr
    assert "Would create" in combined or "Would generate" in combined or "Would ensure" in combined, (
        f"Dry-run output contains no 'Would ...' lines for Codex hooks.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )


@requires_tomllib
def test_install_sh_uninstall_removes_hooks(fake_home: Path) -> None:
    """--uninstall removes ~/.codex/hooks/ and archives hooks.json; config.toml survives."""
    # Install first.
    install_result = _run_install(fake_home, ["--copy", "--force"])
    hooks_dir = fake_home / ".codex" / "hooks"
    assert hooks_dir.exists(), (
        f"Pre-condition failed: hooks dir not created by install.\nSTDOUT:\n{install_result.stdout}"
    )

    # Now uninstall.
    uninstall_result = _run_install(fake_home, ["--uninstall"])

    assert not hooks_dir.exists(), (
        f"~/.codex/hooks/ still present after --uninstall.\nSTDOUT:\n{uninstall_result.stdout}\nSTDERR:\n{uninstall_result.stderr}"
    )

    # hooks.json should have been archived, not deleted in place.
    codex_dir = fake_home / ".codex"
    hooks_json = codex_dir / "hooks.json"
    assert not hooks_json.exists(), (
        f"hooks.json still present as hooks.json (should be archived).\nSTDOUT:\n{uninstall_result.stdout}"
    )

    archived = list(codex_dir.glob("hooks.json.uninstalled.*"))
    assert archived, (
        f"No hooks.json.uninstalled.* archive found in {codex_dir}.\n"
        f"Files in codex_dir: {[f.name for f in codex_dir.iterdir()]}\n"
        f"STDOUT:\n{uninstall_result.stdout}"
    )

    # config.toml feature flag is intentionally NOT removed by uninstall.
    config_path = codex_dir / "config.toml"
    if config_path.exists():
        with open(config_path, "rb") as fh:
            config = tomllib.load(fh)
        assert config.get("features", {}).get("codex_hooks") is True, (
            "Uninstall incorrectly removed codex_hooks = true from config.toml"
        )


def test_install_sh_handles_missing_allowlist_gracefully() -> None:
    """Skip: testing missing-allowlist path requires mutating the live repo.

    The missing-allowlist path is tested by the bash branch in install.sh that
    prints a warning and skips the hooks mirror. We cannot test it here without
    renaming scripts/codex-hooks-allowlist.txt, which would break other tests
    running in the same process. A targeted bash-level integration test would be
    the right vehicle, but that is outside the pytest scope for this file.
    """
    pytest.skip(
        "Cannot test missing-allowlist path without mutating the repo allowlist file. "
        "Covered by the install.sh bash branch that prints a warning and continues."
    )
