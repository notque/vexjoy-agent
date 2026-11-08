"""Tests for `validate-doc-commands.py --scope toolkit`: doc script calls vs the script's argparse.

Each test builds a small repo with fixture markdown under skills/ or agents/ and a fixture CLI script,
copies the validator in, and runs it as a subprocess, the way CI does.

Run with: python3 -m pytest scripts/tests/test_validate_doc_commands_toolkit.py -v
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "validate-doc-commands.py"

FIXTURE_CLI = """\
import argparse
from pathlib import Path

Path(__file__).with_name("EXECUTED").write_text("ran")  # the checker must never run this file

common = argparse.ArgumentParser(add_help=False)
common.add_argument("--json", action="store_true")


def add_window(p):
    p.add_argument("--days", type=int, default=7)


def build():
    parser = argparse.ArgumentParser(parents=[common])
    parser.add_argument("--verbose", "-v", action="store_true")
    sub = parser.add_subparsers(dest="cmd")
    report = sub.add_parser("report", parents=[common])
    report.add_argument("--min-count", type=int)
    report.add_argument("--color", action=argparse.BooleanOptionalAction)
    report.add_argument("--colorspace")
    mode = report.add_mutually_exclusive_group()
    mode.add_argument("--fast", action="store_true")
    mode.add_argument("--slow", action="store_true")
    add_window(report)
    sub.add_parser("export").add_argument("--out", required=True)
    for name in ("mark", "check"):
        p = sub.add_parser(name)
        p.add_argument("--sha")
    strict = sub.add_parser("strict", allow_abbrev=False)
    strict.add_argument("--limit", type=int)
    return parser


build().parse_args()
"""


def _repo(tmp_path: Path, docs: dict[str, str], allowlist: str = "") -> Path:
    """A repo with the validator, scripts/fixture-cli.py, a skill dir and the given markdown files."""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPT, repo / "scripts" / "validate-doc-commands.py")
    (repo / "scripts" / "fixture-cli.py").write_text(FIXTURE_CLI, encoding="utf-8")
    skill = repo / "skills" / "cat" / "demo"
    (skill / "scripts").mkdir(parents=True)
    (skill / "SKILL.md").write_text("# demo\n", encoding="utf-8")
    shutil.copy2(repo / "scripts" / "fixture-cli.py", skill / "scripts" / "tool.py")
    for rel, text in docs.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    if allowlist:
        (repo / "scripts" / "doc-command-allowlist.txt").write_text(allowlist, encoding="utf-8")
    return repo


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "validate-doc-commands.py"), "--scope", "toolkit"],
        capture_output=True,
        text=True,
        cwd=str(repo),
        timeout=60,
    )


def _bash(*lines: str) -> str:
    return "# Doc\n\n```bash\n" + "\n".join(lines) + "\n```\n"


# ---------------------------------------------------------------------------
# Valid calls pass, including the hard argparse shapes
# ---------------------------------------------------------------------------


def test_valid_calls_pass_and_script_is_never_executed(tmp_path: Path) -> None:
    doc = _bash(
        "python3 scripts/fixture-cli.py --json -v report --min-count 3 --json",
        "python3 scripts/fixture-cli.py report --min 3 --no-color --fast --days 2",  # abbrev, parents, group, helper
        "python3 scripts/fixture-cli.py export --out=/tmp/x.json | jq .",
        "python3 scripts/fixture-cli.py mark --sha abc && python3 scripts/fixture-cli.py check",
        "python3 scripts/fixture-cli.py report \\",
        "  --min-count 2 2>/dev/null",
        "python3 scripts/fixture-cli.py <subcommand> --anything",
        "python3 scripts/fixture-cli.py --help",
    )
    repo = _repo(tmp_path, {"agents/demo-agent.md": doc})
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Checked 8 script calls" in result.stdout, result.stdout
    assert not (repo / "scripts" / "EXECUTED").exists()


def test_skill_dir_variables_and_installed_skill_paths_resolve(tmp_path: Path) -> None:
    doc = _bash(
        "python3 ${CLAUDE_SKILL_DIR}/scripts/tool.py report --fast",
        "python3 ~/.claude/skills/demo/scripts/tool.py export --out a",
        "cd ~/.claude/skills/demo && python3 scripts/tool.py mark --sha HEAD",
    )
    repo = _repo(tmp_path, {"skills/cat/demo/references/usage.md": doc})
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Checked 3 script calls" in result.stdout, result.stdout


def test_out_of_scope_calls_are_skipped(tmp_path: Path) -> None:
    doc = (
        _bash(
            "python3 manage.py migrate --fake-flag",  # a file in the user's project
            "cd /path/to/project && python3 scripts/build.py --whatever",  # cd out of the toolkit
            "python3 ~/.claude/skills/private-only/scripts/x.py",  # skill not in this repo
            "python3 $HOME/tools/setup.py",
        )
        + "\n```python\nsubprocess.run(['python3', 'scripts/fixture-cli.py', 'nope'])\n```\n"
    )
    repo = _repo(tmp_path, {"skills/cat/demo/SKILL.md": doc})
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Negative controls: drift is caught and the CLI exits 1
# ---------------------------------------------------------------------------


def test_cli_with_root_flag_exits_one_on_drift(tmp_path: Path) -> None:
    """The repo's own validator, pointed at a drifted fixture repo with --root, fails the run."""
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/fixture-cli.py report --status x")})
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--scope", "toolkit", "--root", str(repo)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "agents/a.md:4: scripts/fixture-cli.py: unknown option --status" in result.stdout, result.stdout


def test_unknown_subcommand_exits_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/fixture-cli.py list --json")})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "agents/a.md:4: scripts/fixture-cli.py: unknown subcommand 'list'" in result.stdout, result.stdout
    assert "choices: check, export, mark, report, strict" in result.stdout, result.stdout


def test_unknown_flag_exits_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/fixture-cli.py report --status candidate")})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unknown option --status" in result.stdout, result.stdout


def test_flag_after_doc_placeholder_is_still_checked(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/fixture-cli.py export --out <file> --bogus")})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unknown option --bogus" in result.stdout, result.stdout


def test_subcommand_option_before_the_subcommand_exits_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/fixture-cli.py --out x.json")})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unknown option --out before a subcommand (accepted by: export)" in result.stdout, result.stdout


def test_abbreviation_is_flagged_when_allow_abbrev_is_false(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/fixture-cli.py strict --lim 3")})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unknown option --lim" in result.stdout, result.stdout


def test_ambiguous_abbreviation_exits_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/fixture-cli.py report --co")})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "ambiguous option --co" in result.stdout, result.stdout


ROOT_VALUE_CLI = """\
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--config")
parser.add_argument("-n", type=int)
sub = parser.add_subparsers(dest="cmd")
sub.add_parser("run")
parser.parse_args()
"""

OPEN_CLI = """\
import argparse
from common_cli import add_shared

parser = argparse.ArgumentParser()
add_shared(parser)
sub = parser.add_subparsers(dest="cmd")
sub.add_parser("run")
parser.parse_args()
"""


def test_abbreviated_root_option_consumes_its_value(tmp_path: Path) -> None:
    doc = _bash(
        "python3 scripts/root-value.py --conf a.json run",
        "python3 scripts/root-value.py --config a.json run",
        "python3 scripts/root-value.py -n 5 run",
        "python3 scripts/root-value.py -n5 run",
    )
    repo = _repo(tmp_path, {"agents/a.md": doc})
    (repo / "scripts" / "root-value.py").write_text(ROOT_VALUE_CLI, encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_unknown_subcommand_after_abbreviated_option_value_exits_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/root-value.py --conf a.json walk")})
    (repo / "scripts" / "root-value.py").write_text(ROOT_VALUE_CLI, encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unknown subcommand 'walk' (choices: run)" in result.stdout, result.stdout


def test_unseen_option_value_on_open_parser_is_not_read_as_a_subcommand(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/open-cli.py --shared a.json run")})
    (repo / "scripts" / "open-cli.py").write_text(OPEN_CLI, encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_inline_option_value_on_open_parser_does_not_hide_the_subcommand(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/open-cli.py --shared=a.json walk")})
    (repo / "scripts" / "open-cli.py").write_text(OPEN_CLI, encoding="utf-8")
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "unknown subcommand 'walk' (choices: run)" in result.stdout, result.stdout


def test_unknown_option_with_placeholder_value_after_equals_exits_one(tmp_path: Path) -> None:
    doc = _bash(
        "python3 scripts/fixture-cli.py export --bogus=<file>",
        "python3 scripts/fixture-cli.py --bogus=$DIR report",
        "python3 scripts/fixture-cli.py --verbose=<x> walk",
    )
    repo = _repo(tmp_path, {"agents/a.md": doc})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "agents/a.md:4: scripts/fixture-cli.py: unknown option --bogus" in result.stdout, result.stdout
    assert "agents/a.md:5: scripts/fixture-cli.py: unknown option --bogus" in result.stdout, result.stdout
    assert "unknown subcommand 'walk'" in result.stdout, result.stdout


def test_placeholder_value_after_equals_on_known_option_passes(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/fixture-cli.py export --out=<file>")})
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_claude_skill_dir_does_not_fall_back_to_repo_scripts(tmp_path: Path) -> None:
    doc = _bash("python3 ${CLAUDE_SKILL_DIR}/fixture-cli.py report", "python3 $SDIR/fixture-cli.py report")
    repo = _repo(tmp_path, {"skills/cat/demo/SKILL.md": doc})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "${CLAUDE_SKILL_DIR}/fixture-cli.py: script not found" in result.stdout, result.stdout
    assert "$SDIR/fixture-cli.py" not in result.stdout, result.stdout


def test_missing_toolkit_script_exits_one(tmp_path: Path) -> None:
    doc = _bash("python3 ${CLAUDE_SKILL_DIR}/scripts/gone.py", "python3 ~/.claude/scripts/also-gone.py run")
    repo = _repo(tmp_path, {"skills/cat/demo/SKILL.md": doc})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "${CLAUDE_SKILL_DIR}/scripts/gone.py: script not found" in result.stdout, result.stdout
    assert "~/.claude/scripts/also-gone.py: script not found" in result.stdout, result.stdout


def test_inline_code_call_is_checked(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": "Then run `python3 scripts/fixture-cli.py export --skill x`.\n"})
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "agents/a.md:1: scripts/fixture-cli.py: unknown option --skill" in result.stdout, result.stdout


# ---------------------------------------------------------------------------
# Scripts the static parse cannot see in full are checked for existence only
# ---------------------------------------------------------------------------


def test_raw_argv_and_imported_helper_scripts_skip_interface_checks(tmp_path: Path) -> None:
    doc = _bash("python3 scripts/raw.py anything --goes", "python3 scripts/helper.py --from-helper 1")
    repo = _repo(tmp_path, {"agents/a.md": doc})
    (repo / "scripts" / "raw.py").write_text("import sys\nprint(sys.argv[1])\n", encoding="utf-8")
    (repo / "scripts" / "helper.py").write_text(
        "import argparse\nfrom common_cli import add_shared\np = argparse.ArgumentParser()\nadd_shared(p)\n",
        encoding="utf-8",
    )
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Allowlist
# ---------------------------------------------------------------------------


def test_allowlist_covers_a_finding(tmp_path: Path) -> None:
    doc = _bash("python3 scripts/promo/mix.py --in a")
    allow = "# comment\nskills/cat/* :: scripts/promo/* :: runs in another repo\n"
    repo = _repo(tmp_path, {"skills/cat/demo/SKILL.md": doc}, allowlist=allow)
    result = _run(repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_stale_allowlist_entry_exits_one(tmp_path: Path) -> None:
    allow = "agents/a.md :: scripts/old.py :: fixed long ago\n"
    repo = _repo(tmp_path, {"agents/a.md": _bash("python3 scripts/fixture-cli.py report")}, allowlist=allow)
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "doc-command-allowlist.txt:0: scripts/old.py: stale entry for agents/a.md" in result.stdout, result.stdout


def test_malformed_allowlist_line_exits_one(tmp_path: Path) -> None:
    repo = _repo(tmp_path, {"agents/a.md": "# empty\n"}, allowlist="agents/a.md :: missing reason\n")
    result = _run(repo)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "bad allowlist line" in result.stderr, result.stderr
