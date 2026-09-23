#!/usr/bin/env python3
"""
Tests for the pretool-private-name-leak-gate hook.

All fixtures use SYNTHETIC names (secret-example-skill, nested-package-skill,
hidden-fixture-agent, shared-fixture-name, translate, acmebrand-writer,
acmebrand-news-editor, fixturekit, zorblat). The real
~/private-skills tree is never read: every test patches mod._PRIVATE_DIR to a
tmp dir, so no real private name can reach test output.

Run with: python3 -m pytest hooks/tests/test_pretool_private_name_leak_gate.py -v
"""

import importlib.util
import io
import json
import os
import subprocess
import time
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-private-name-leak-gate.py"

spec = importlib.util.spec_from_file_location("pretool_private_name_leak_gate", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SYNTH = "secret-example-skill"  # synthetic private component name
SYNTH_REDACTED = "s…l"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def private_dir(tmp_path, monkeypatch):
    """Synthetic ~/private-skills tree; patched into the module.

    Shape exercises every collection rule: a leaf skill dir, a nested
    <name>/skill/SKILL.md package, an agents/*.md stem, plus interior noise
    (reference stems, asset dirs) that must NOT enter the name set.
    """
    root = tmp_path / "private-tree"
    (root / SYNTH).mkdir(parents=True)
    (root / SYNTH / "SKILL.md").write_text("---\nname: x\n---\n")
    # Interior noise inside the package: excluded from the name set.
    (root / SYNTH / "references").mkdir()
    (root / SYNTH / "references" / "interior-topic-map.md").write_text("ref\n")
    (root / SYNTH / "asset-bundle-dir").mkdir()
    # Nested package layout: <name>/skill/SKILL.md -> <name>.
    (root / "nested-package-skill" / "skill").mkdir(parents=True)
    (root / "nested-package-skill" / "skill" / "SKILL.md").write_text("---\nname: n\n---\n")
    # Agent component: agents/*.md stem.
    (root / "agents").mkdir()
    (root / "agents" / "hidden-fixture-agent.md").write_text("agent\n")
    monkeypatch.setattr(mod, "_PRIVATE_DIR", root)
    # Point the user-index fallback at nothing so only the project INDEX counts.
    monkeypatch.setattr(mod, "_USER_INDEX", tmp_path / "no-user-index.json")
    return root


@pytest.fixture()
def toolkit_repo(tmp_path):
    """Toolkit-shaped git repo (agents/ + skills/) with a public INDEX.json."""
    repo = tmp_path / "toolkit"
    (repo / "agents").mkdir(parents=True)
    (repo / "skills").mkdir()
    (repo / "skills" / "INDEX.json").write_text(json.dumps({"version": "2.0", "skills": {"translate": {}}}))
    _git(repo, "init", "-q")
    return repo


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
    )


def _event(command: str, cwd: Path | None = None) -> str:
    event: dict = {"tool_input": {"command": command}}
    if cwd:
        event["cwd"] = str(cwd)
    return json.dumps(event)


def _run_main(stdin_payload: str, env: dict | None = None) -> tuple[int, dict | None, str, str]:
    """Invoke mod.main() in-process.

    Returns (logical_exit_code, parsed_stdout_json, raw_stdout, raw_stderr).
    logical_exit_code is 2 if permissionDecision:deny was emitted, 0 otherwise.
    """
    base_env = dict(os.environ)
    for var in ("PRIVATE_NAME_GATE_BYPASS", "CLAUDE_PROJECT_DIR", "CLAUDE_HOOKS_DEBUG"):
        base_env.pop(var, None)
    if env:
        base_env.update(env)

    stdout_capture = io.StringIO()
    stderr_capture = io.StringIO()
    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        patch.object(mod, "record_governance", lambda *_args, **_kwargs: None),
        patch("sys.stdout", stdout_capture),
        patch("sys.stderr", stderr_capture),
    ):
        try:
            mod.main()
        except SystemExit:
            pass

    out = stdout_capture.getvalue()
    parsed = None
    if out.strip():
        try:
            parsed = json.loads(out.strip())
        except json.JSONDecodeError:
            pass

    code = 0
    if parsed and parsed.get("hookSpecificOutput", {}).get("permissionDecision") == "deny":
        code = 2
    return code, parsed, out, stderr_capture.getvalue()


def _reason(parsed: dict) -> str:
    return parsed["hookSpecificOutput"]["permissionDecisionReason"]


# ---------------------------------------------------------------------------
# Blocks — each covered command shape fires on a synthetic name
# ---------------------------------------------------------------------------


class TestBlocks:
    def test_block_on_staged_diff(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text(f"wires {SYNTH} into the router\n")
        _git(toolkit_repo, "add", "f.txt")
        code, parsed, _, _ = _run_main(_event("git commit -m 'clean message'", toolkit_repo))
        assert code == 2
        assert "staged diff" in _reason(parsed)

    def test_block_on_commit_message_arg(self, private_dir, toolkit_repo):
        code, parsed, _, _ = _run_main(_event(f'git commit -m "wire {SYNTH} in"', toolkit_repo))
        assert code == 2
        assert "command text" in _reason(parsed)

    def test_block_on_commit_message_file(self, private_dir, toolkit_repo, tmp_path):
        msg = tmp_path / "msg.txt"
        msg.write_text(f"feat: enable {SYNTH}\n")
        code, parsed, _, _ = _run_main(_event(f"git commit -F {msg}", toolkit_repo))
        assert code == 2
        assert "commit message file" in _reason(parsed)

    def test_block_on_push_with_leaking_commit_message(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text("clean content\n")
        _git(toolkit_repo, "add", "f.txt")
        _git(toolkit_repo, "commit", "-q", "-m", f"add {SYNTH} support")
        code, parsed, _, _ = _run_main(_event("git push origin feat-x", toolkit_repo))
        assert code == 2
        assert "outgoing commit messages" in _reason(parsed)

    def test_block_on_pr_create_body_arg(self, private_dir, toolkit_repo):
        code, parsed, _, _ = _run_main(_event(f'gh pr create --title t --body "uses {SYNTH}"', toolkit_repo))
        assert code == 2

    def test_block_on_pr_create_body_file(self, private_dir, toolkit_repo, tmp_path):
        body = tmp_path / "body.md"
        body.write_text(f"## Summary\nintegrates {SYNTH}\n")
        code, parsed, _, _ = _run_main(_event(f"gh pr create --title t --body-file {body}", toolkit_repo))
        assert code == 2
        assert "PR body file" in _reason(parsed)
        assert str(body) in _reason(parsed)

    def test_block_on_pr_edit(self, private_dir, toolkit_repo):
        code, _, _, _ = _run_main(_event(f'gh pr edit 5 --body "now with {SYNTH}"', toolkit_repo))
        assert code == 2

    def test_block_on_pr_comment(self, private_dir, toolkit_repo):
        code, _, _, _ = _run_main(_event(f'gh pr comment 5 --body "see {SYNTH}"', toolkit_repo))
        assert code == 2

    def test_block_on_pr_merge_body(self, private_dir, toolkit_repo):
        code, _, _, _ = _run_main(_event(f'gh pr merge 5 --squash --body "folds in {SYNTH}"', toolkit_repo))
        assert code == 2

    def test_block_on_agent_md_stem(self, private_dir, toolkit_repo):
        """agents/*.md stems are leaf components and part of the name set."""
        code, _, _, _ = _run_main(_event('git commit -m "port hidden-fixture-agent"', toolkit_repo))
        assert code == 2

    def test_block_on_nested_package_name(self, private_dir, toolkit_repo):
        """<name>/skill/SKILL.md packages contribute <name>, not `skill`."""
        code, _, _, _ = _run_main(_event('git commit -m "port nested-package-skill"', toolkit_repo))
        assert code == 2


# ---------------------------------------------------------------------------
# Redaction — the gate never echoes the matched name
# ---------------------------------------------------------------------------


class TestRedaction:
    def test_block_output_never_contains_raw_name(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text(f"{SYNTH}\n")
        _git(toolkit_repo, "add", "f.txt")
        code, parsed, out, err = _run_main(_event("git commit -m 'clean'", toolkit_repo))
        assert code == 2
        assert SYNTH not in out
        assert SYNTH not in err
        assert SYNTH_REDACTED in _reason(parsed)
        assert SYNTH_REDACTED in err

    def test_redact_shape(self):
        assert mod._redact("secret-example-skill") == "s…l"
        assert mod._redact("ab") == "a…b"
        assert mod._redact("x") == "…"


# ---------------------------------------------------------------------------
# Pass-throughs
# ---------------------------------------------------------------------------


class TestPassThrough:
    def test_public_homonym_never_blocks(self, private_dir, toolkit_repo):
        """A private leaf name that is also a tracked public skill passes."""
        (private_dir / "translate").mkdir()
        (private_dir / "translate" / "SKILL.md").write_text("---\nname: t\n---\n")
        code, _, _, _ = _run_main(_event('git commit -m "improve translate flow"', toolkit_repo))
        assert code == 0

    def test_interior_stems_and_dirs_excluded(self, private_dir, toolkit_repo):
        """Reference stems and asset dir names inside packages never block."""
        for word in ("interior-topic-map", "asset-bundle-dir", "references"):
            code, _, _, _ = _run_main(_event(f'git commit -m "touch {word} docs"', toolkit_repo))
            assert code == 0, f"interior name {word!r} must not block"

    def test_leaf_name_already_on_main_still_blocks(self, private_dir, toolkit_repo):
        """A private leaf name already in the committed tree still blocks.

        The v1.1 "already public" exemption made a leak self-perpetuating:
        once one leak landed, every later mention passed.
        """
        (private_dir / "shared-fixture-name").mkdir()
        (private_dir / "shared-fixture-name" / "SKILL.md").write_text("---\nname: s\n---\n")
        (toolkit_repo / "docs.md").write_text("mentions shared-fixture-name already\n")
        _git(toolkit_repo, "add", "docs.md")
        _git(toolkit_repo, "commit", "-q", "-m", "public docs")
        code, _, _, _ = _run_main(_event('git commit -m "improve shared-fixture-name flow"', toolkit_repo))
        assert code == 2

    def test_toolkit_own_name_never_blocks(self, private_dir, toolkit_repo):
        """A private leaf named after the toolkit itself is public by definition."""
        (toolkit_repo / "pyproject.toml").write_text('[project]\nname = "fixturekit-agent"\n')
        (private_dir / "voice").mkdir()
        (private_dir / "voice" / "fixturekit").mkdir()
        (private_dir / "voice" / "fixturekit" / "SKILL.md").write_text("---\nname: f\n---\n")
        for msg in ("tune fixturekit voice", "bump fixturekit-agent docs"):
            code, _, _, _ = _run_main(_event(f'git commit -m "{msg}"', toolkit_repo))
            assert code == 0, msg

    def test_staged_leak_does_not_launder_name(self, private_dir, toolkit_repo):
        """The public-tree grep reads the committed ref, not the working tree.

        A just-staged leak must not make its own name look 'already public'.
        """
        (toolkit_repo / "clean.md").write_text("clean tracked file\n")
        _git(toolkit_repo, "add", "clean.md")
        _git(toolkit_repo, "commit", "-q", "-m", "public docs")
        (toolkit_repo / "leak.md").write_text(f"wires {SYNTH} in\n")
        _git(toolkit_repo, "add", "leak.md")
        code, _, _, _ = _run_main(_event("git commit -m 'clean message'", toolkit_repo))
        assert code == 2

    def test_absent_private_dir_is_noop(self, toolkit_repo, tmp_path, monkeypatch):
        """Public installs and CI have no ~/private-skills: graceful no-op."""
        monkeypatch.setattr(mod, "_PRIVATE_DIR", tmp_path / "does-not-exist")
        code, _, _, _ = _run_main(_event(f'git commit -m "wire {SYNTH} in"', toolkit_repo))
        assert code == 0

    def test_non_toolkit_repo_not_gated(self, private_dir, tmp_path):
        plain = tmp_path / "plain-repo"
        plain.mkdir()
        _git(plain, "init", "-q")
        code, _, _, _ = _run_main(_event(f'git commit -m "wire {SYNTH} in"', plain))
        assert code == 0

    def test_private_repo_itself_not_gated(self, private_dir):
        """Commits inside ~/private-skills always name private components."""
        code, _, _, _ = _run_main(_event(f'git commit -m "update {SYNTH}"', private_dir))  # nosec: fixture string, not SQL
        assert code == 0

    def test_non_matching_command_ignored(self, private_dir, toolkit_repo):
        code, _, _, _ = _run_main(_event(f"grep -rn {SYNTH} .", toolkit_repo))
        assert code == 0

    def test_clean_commit_allowed(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text("clean content\n")
        _git(toolkit_repo, "add", "f.txt")
        code, _, _, _ = _run_main(_event("git commit -m 'feat: clean change'", toolkit_repo))
        assert code == 0

    def test_substring_of_longer_kebab_name_not_matched(self, private_dir, toolkit_repo):
        """Kebab-aware boundaries: name inside a longer identifier passes."""
        code, _, _, _ = _run_main(_event(f'git commit -m "use my-{SYNTH}-fork instead"', toolkit_repo))
        assert code == 0

    def test_bypass_env(self, private_dir, toolkit_repo):
        code, _, _, err = _run_main(
            _event(f'git commit -m "wire {SYNTH} in"', toolkit_repo),
            env={"PRIVATE_NAME_GATE_BYPASS": "1"},
        )
        assert code == 0
        assert "BYPASSED (env)" in err

    def test_bypass_inline_prefix(self, private_dir, toolkit_repo):
        """Inline prefix never reaches the hook's os.environ; the command
        string form must work as documented."""
        code, _, _, err = _run_main(_event(f'PRIVATE_NAME_GATE_BYPASS=1 git commit -m "wire {SYNTH} in"', toolkit_repo))
        assert code == 0
        assert "BYPASSED (inline)" in err

    def test_bypass_inline_after_cd_segment(self, private_dir, toolkit_repo):
        code, _, _, err = _run_main(
            _event(f"cd {toolkit_repo} && PRIVATE_NAME_GATE_BYPASS=1 git push origin x", toolkit_repo)
        )
        assert code == 0
        assert "BYPASSED (inline)" in err

    def test_bypass_token_inside_message_does_not_bypass(self, private_dir, toolkit_repo):
        """Only a leading env-assignment counts — the string inside a commit
        message must not disarm the gate."""
        code, _, _, _ = _run_main(_event(f'git commit -m "docs: PRIVATE_NAME_GATE_BYPASS=1 and {SYNTH}"', toolkit_repo))
        assert code == 2

    def test_bypass_fragment_after_semicolon_in_message_does_not_bypass(self, private_dir, toolkit_repo):
        """A `; TOKEN=1 ...` fragment inside message text is not a prefix of a
        gated command and must not disarm the gate."""
        code, _, _, _ = _run_main(
            _event(f'git commit -m "a; PRIVATE_NAME_GATE_BYPASS=1 enables {SYNTH}"', toolkit_repo)
        )
        assert code == 2

    def test_malformed_stdin_allowed(self, private_dir):
        code, _, _, _ = _run_main("not json{")
        assert code == 0


# ---------------------------------------------------------------------------
# Brand terms and the owner term list
# ---------------------------------------------------------------------------

BRAND = "acmebrand"  # synthetic brand: shared first segment of two private leaves


def _skill(root: Path, *parts: str) -> None:
    d = root.joinpath(*parts)
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text("---\nname: x\n---\n")


@pytest.fixture()
def brand_dir(private_dir):
    """Private tree with a brand shared by a skill and an agent leaf."""
    _skill(private_dir, "brand", f"{BRAND}-writer")
    (private_dir / "brand" / "agents").mkdir()
    (private_dir / "brand" / "agents" / f"{BRAND}-news-editor.md").write_text("agent\n")
    return private_dir


class TestBrandTerms:
    def test_brand_derived_from_shared_segment(self, brand_dir, toolkit_repo):
        _, strong = mod.private_terms(toolkit_repo)
        assert strong == {BRAND}

    def test_bare_brand_blocks_in_commit_message(self, brand_dir, toolkit_repo):
        code, parsed, out, err = _run_main(_event(f'git commit -m "recap in {BRAND} voice"', toolkit_repo))
        assert code == 2
        assert "command text" in _reason(parsed)
        assert "a…d" in _reason(parsed)
        assert BRAND not in out.lower() and BRAND not in err.lower()

    def test_bare_brand_blocks_in_staged_diff(self, brand_dir, toolkit_repo):
        (toolkit_repo / "prompts.jsonl").write_text(f'{{"request": "Use our {BRAND} voice."}}\n')
        _git(toolkit_repo, "add", "prompts.jsonl")
        code, parsed, _, _ = _run_main(_event("git commit -m 'add prompt'", toolkit_repo))
        assert code == 2
        assert "staged diff" in _reason(parsed)

    @pytest.mark.parametrize(
        "text",
        ["AcmeBrand voice", "ACMEBRAND", "MyAcmeBrandVoice", "acmebrand-recap", "acmebrand.com", "AcmeBrands"],
    )
    def test_case_and_camelcase_forms_block(self, brand_dir, toolkit_repo, text):
        code, _, _, _ = _run_main(_event(f'git commit -m "see {text} here"', toolkit_repo))
        assert code == 2, text

    def test_brand_inside_longer_lowercase_word_passes(self, brand_dir, toolkit_repo):
        code, _, _, _ = _run_main(_event('git commit -m "the acmebrandish style"', toolkit_repo))
        assert code == 0

    def test_brand_already_on_main_still_blocks(self, brand_dir, toolkit_repo):
        (toolkit_repo / "old.md").write_text(f"old {BRAND} mention\n")
        _git(toolkit_repo, "add", "old.md")
        _git(toolkit_repo, "commit", "-q", "-m", "old leak")
        code, _, _, _ = _run_main(_event('git commit -m "more AcmeBrand notes"', toolkit_repo))
        assert code == 2

    def test_stoplist_segment_is_not_a_brand(self, private_dir, toolkit_repo):
        """`voice-a` + `voice-b` and `data-a` + `data-b` share common words."""
        for name in ("voice-alpha", "voice-beta", "data-alpha", "data-beta"):
            _skill(private_dir, "c", name)
        _, strong = mod.private_terms(toolkit_repo)
        assert strong == set()
        code, _, _, _ = _run_main(_event('git commit -m "voice and data cleanup"', toolkit_repo))
        assert code == 0

    def test_public_segment_homonym_is_not_a_brand(self, private_dir, toolkit_repo):
        """A segment of a public skill name (`translate`) never becomes a brand."""
        _skill(private_dir, "c", "translate-legal")
        _skill(private_dir, "c", "translate-poetry")
        (toolkit_repo / "agents" / "shortform-engineer.md").write_text("agent\n")
        _skill(private_dir, "c", "shortform-alpha")
        _skill(private_dir, "c", "shortform-beta")
        _, strong = mod.private_terms(toolkit_repo)
        assert strong == set()
        code, _, _, _ = _run_main(_event('git commit -m "translate and shortform tweaks"', toolkit_repo))
        assert code == 0

    def test_short_segment_is_not_a_brand(self, private_dir, toolkit_repo):
        _skill(private_dir, "c", "abc-one")
        _skill(private_dir, "c", "abc-two")
        assert mod.private_terms(toolkit_repo)[1] == set()

    def test_toolkit_name_is_not_a_brand(self, private_dir, toolkit_repo):
        (toolkit_repo / "pyproject.toml").write_text('[project]\nname = "fixturekit-agent"\n')
        _skill(private_dir, "c", "fixturekit-one")
        _skill(private_dir, "c", "fixturekit-two")
        assert mod.private_terms(toolkit_repo)[1] == set()

    def test_absent_private_dir_is_noop_for_brand(self, toolkit_repo, tmp_path, monkeypatch):
        monkeypatch.setattr(mod, "_PRIVATE_DIR", tmp_path / "does-not-exist")
        code, _, _, _ = _run_main(_event(f'git commit -m "{BRAND} recap"', toolkit_repo))
        assert code == 0


class TestOwnerTerms:
    def test_owner_term_blocks(self, private_dir, toolkit_repo):
        (private_dir / ".private-terms").write_text("# owner list\nzorblat\n\nquux-house  # trailing note\n")
        _, strong = mod.private_terms(toolkit_repo)
        assert strong == {"zorblat", "quux-house"}
        code, _, _, _ = _run_main(_event('git commit -m "Zorblat recap"', toolkit_repo))
        assert code == 2
        code, _, _, _ = _run_main(_event('git commit -m "the QuuxHouse style"', toolkit_repo))
        assert code == 0  # hyphenated term matches only its own spelling
        code, _, _, _ = _run_main(_event('git commit -m "the quux-house style"', toolkit_repo))
        assert code == 2

    def test_owner_term_blocks_even_when_already_on_main(self, private_dir, toolkit_repo):
        (private_dir / ".private-terms").write_text("zorblat\n")
        (toolkit_repo / "old.md").write_text("zorblat\n")
        _git(toolkit_repo, "add", "old.md")
        _git(toolkit_repo, "commit", "-q", "-m", "old")
        code, _, _, _ = _run_main(_event('git commit -m "zorblat again"', toolkit_repo))
        assert code == 2

    def test_comment_only_lines_are_ignored(self, private_dir, toolkit_repo):
        (private_dir / ".private-terms").write_text("# owner notes mention widget\n")
        assert mod.private_terms(toolkit_repo)[1] == set()
        code, _, _, _ = _run_main(_event('git commit -m "owner notes mention widget"', toolkit_repo))
        assert code == 0

    def test_missing_owner_file_is_fine(self, private_dir, toolkit_repo):
        assert mod._owner_terms() == set()


# ---------------------------------------------------------------------------
# Audit script — shares the gate's term set
# ---------------------------------------------------------------------------

AUDIT_PATH = Path(__file__).parent.parent.parent / "scripts" / "private-term-audit.py"


def _load_audit():
    spec = importlib.util.spec_from_file_location("private_term_audit", AUDIT_PATH)
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    return audit


class TestAuditScript:
    def test_reports_redacted_hits_in_content_and_paths(self, brand_dir, toolkit_repo):
        audit = _load_audit()
        (toolkit_repo / "notes.md").write_text("Use our AcmeBrand voice\n")
        (toolkit_repo / f"{BRAND}-thing.txt").write_text("clean\n")
        (toolkit_repo / "clean.md").write_text("nothing here\n")
        _git(toolkit_repo, "add", ".")
        lines = audit.audit(toolkit_repo, mod)
        joined = "\n".join(lines)
        assert BRAND not in joined.lower()
        assert any(line.startswith("notes.md") and "content" in line for line in lines)
        assert any(line.startswith("a…d-thing.txt") and "path" in line for line in lines)
        assert not any("clean.md" in line for line in lines)

    def test_clean_tree_reports_nothing(self, brand_dir, toolkit_repo):
        audit = _load_audit()
        (toolkit_repo / "clean.md").write_text("nothing here\n")
        _git(toolkit_repo, "add", ".")
        assert audit.audit(toolkit_repo, mod) == []

    def test_absent_private_dir_exits_zero(self, tmp_path):
        env = {k: v for k, v in os.environ.items()}
        env["HOME"] = str(tmp_path)
        result = subprocess.run(
            ["python3", str(AUDIT_PATH)], capture_output=True, text=True, env=env, check=False, timeout=30
        )
        assert result.returncode == 0
        assert "no private tree" in result.stdout


# ---------------------------------------------------------------------------
# Performance — repo benchmark budget (scripts/benchmark-hooks.py: 200ms)
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_full_scan_under_budget(self, private_dir, toolkit_repo):
        (toolkit_repo / "f.txt").write_text("clean content\n" * 200)
        _git(toolkit_repo, "add", "f.txt")
        payload = _event("git commit -m 'feat: clean change'", toolkit_repo)
        _run_main(payload)  # warm caches
        start = time.perf_counter()
        code, _, _, _ = _run_main(payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert code == 0
        assert elapsed_ms < 200, f"scan took {elapsed_ms:.1f}ms (budget 200ms)"
