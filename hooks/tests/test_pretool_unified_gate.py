#!/usr/bin/env python3
"""
Tests for the pretool-unified-gate hook.

Run with: python3 -m pytest hooks/tests/test_pretool_unified_gate.py -v
"""

import importlib.util
import io
import json
import os
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-unified-gate.py"

spec = importlib.util.spec_from_file_location("pretool_unified_gate", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bash_event(command: str) -> str:
    """Build a JSON hook event payload for a Bash tool call."""
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def _make_write_event(file_path: str) -> str:
    """Build a JSON hook event payload for a Write tool call."""
    return json.dumps({"tool_name": "Write", "tool_input": {"file_path": file_path}})


def _make_edit_event(file_path: str) -> str:
    """Build a JSON hook event payload for an Edit tool call."""
    return json.dumps({"tool_name": "Edit", "tool_input": {"file_path": file_path}})


def _run_main(stdin_payload: str, env: dict | None = None) -> int:
    """Invoke mod.main() in-process, returning a logical block/allow code.

    Args:
        stdin_payload: JSON string to supply as stdin.
        env: Optional environment variable overrides.

    Returns:
        2 if the hook denied the request (permissionDecision:deny in stdout),
        0 if the hook allowed the request.

    Note: The hook now always exits 0. This helper detects the deny decision
    from the JSON stdout output so existing test assertions remain valid.
    """
    base_env = dict(os.environ)
    # Strip all bypass vars for a clean baseline
    for var in ("CLAUDE_GATE_BYPASS", "DANGEROUS_GUARD_BYPASS", "CREATION_GATE_BYPASS", "SENSITIVE_FILE_GUARD_BYPASS"):
        base_env.pop(var, None)
    # Activate gate: default "personal" profile bypasses; tests need "work"
    base_env["CLAUDE_OPERATOR_PROFILE"] = "work"
    if env:
        base_env.update(env)

    stdout_capture = io.StringIO()
    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
        patch("sys.stdout", stdout_capture),
    ):
        try:
            mod.main()
        except SystemExit:
            pass

    output = stdout_capture.getvalue().strip()
    if output:
        try:
            parsed = json.loads(output)
            hook_out = parsed.get("hookSpecificOutput", {})
            if hook_out.get("permissionDecision") == "deny":
                return 2  # Logical block
        except (json.JSONDecodeError, AttributeError):
            pass
    return 0


# ---------------------------------------------------------------------------
# TestCheckGitignoreBypass
# ---------------------------------------------------------------------------


class TestCheckGitignoreBypass:
    """check_gitignore_bypass blocks .gitignore redirects and force-adds of ignored paths."""

    def test_gitignore_redirect_blocked(self):
        payload = _make_bash_event("echo '*.log' > .gitignore")
        assert _run_main(payload) == 2

    def test_gitignore_append_redirect_blocked(self):
        payload = _make_bash_event("echo '*.secret' >> .gitignore")
        assert _run_main(payload) == 2

    def test_gitignore_sed_blocked(self):
        payload = _make_bash_event("sed -i 's/foo/bar/' .gitignore")
        assert _run_main(payload) == 2

    def test_gitignore_tee_blocked(self):
        payload = _make_bash_event("echo 'node_modules' | tee .gitignore")
        assert _run_main(payload) == 2

    def test_gitignore_mv_blocked(self):
        payload = _make_bash_event("mv /tmp/newignore .gitignore")
        assert _run_main(payload) == 2

    def test_git_add_force_on_ignored_path_blocked(self):
        """git add -f on a gitignored path should be blocked."""
        result = subprocess_result = MagicMock()
        result.stdout = "secret.env\n"
        result.returncode = 0
        payload = _make_bash_event("git add -f secret.env")
        with patch("subprocess.run", return_value=result):
            assert _run_main(payload) == 2

    def test_git_add_force_on_non_ignored_path_allowed(self):
        """git add -f on a non-ignored path should be allowed."""
        result = MagicMock()
        result.stdout = ""
        result.returncode = 1  # git check-ignore returns 1 when nothing is ignored
        payload = _make_bash_event("git add -f main.py")
        with patch("subprocess.run", return_value=result):
            assert _run_main(payload) == 0

    def test_git_add_without_force_allowed(self):
        """git add without -f or --force is never checked for gitignore."""
        payload = _make_bash_event("git add main.py")
        assert _run_main(payload) == 0

    def test_git_add_long_force_flag_blocked_on_ignored(self):
        """git add --force on an ignored path should be blocked."""
        result = MagicMock()
        result.stdout = ".env\n"
        result.returncode = 0
        payload = _make_bash_event("git add --force .env")
        with patch("subprocess.run", return_value=result):
            assert _run_main(payload) == 2


# ---------------------------------------------------------------------------
# TestCheckGitSubmission
# ---------------------------------------------------------------------------


class TestCheckGitSubmission:
    """check_git_submission blocks raw git push, gh pr create, and gh pr merge."""

    def test_git_push_blocked(self):
        payload = _make_bash_event("git push origin main")
        assert _run_main(payload) == 2

    def test_gh_pr_create_blocked(self):
        payload = _make_bash_event("gh pr create --title 'My PR'")
        assert _run_main(payload) == 2

    def test_gh_pr_merge_blocked(self):
        payload = _make_bash_event("gh pr merge 42")
        assert _run_main(payload) == 2

    def test_bypass_allows_git_push(self):
        """CLAUDE_GATE_BYPASS=1 prefix allows git push through."""
        payload = _make_bash_event("CLAUDE_GATE_BYPASS=1 git push origin main")
        assert _run_main(payload) == 0

    def test_bypass_allows_gh_pr_create(self):
        """CLAUDE_GATE_BYPASS=1 prefix allows gh pr create through."""
        payload = _make_bash_event("CLAUDE_GATE_BYPASS=1 gh pr create --title 'x'")
        assert _run_main(payload) == 0

    def test_bypass_allows_gh_pr_merge(self):
        """CLAUDE_GATE_BYPASS=1 prefix allows gh pr merge through."""
        payload = _make_bash_event("CLAUDE_GATE_BYPASS=1 gh pr merge 7")
        assert _run_main(payload) == 0

    def test_unrelated_git_command_allowed(self):
        """git status, git log, git diff are not submission commands."""
        for cmd in ("git status", "git log --oneline", "git diff HEAD"):
            payload = _make_bash_event(cmd)
            assert _run_main(payload) == 0, f"Expected 0 for: {cmd}"

    def test_git_push_with_leading_whitespace_blocked(self):
        """Leading whitespace before CLAUDE_GATE_BYPASS must not allow bypass."""
        payload = _make_bash_event("  git push origin main")
        assert _run_main(payload) == 2


# ---------------------------------------------------------------------------
# TestCheckDangerousCommand
# ---------------------------------------------------------------------------


class TestCheckDangerousCommand:
    """check_dangerous_command blocks destructive operations."""

    def test_rm_rf_root_blocked(self):
        payload = _make_bash_event("rm -rf /")
        assert _run_main(payload) == 2

    def test_rm_rf_root_star_blocked(self):
        payload = _make_bash_event("rm -rf /*")
        assert _run_main(payload) == 2

    def test_rm_rf_home_blocked(self):
        payload = _make_bash_event("rm -rf ~")
        assert _run_main(payload) == 2

    def test_rm_rf_dot_blocked(self):
        payload = _make_bash_event("rm -rf .")
        assert _run_main(payload) == 2

    def test_drop_database_blocked(self):
        payload = _make_bash_event("psql -c 'DROP DATABASE mydb'")
        assert _run_main(payload) == 2

    def test_drop_database_case_insensitive_blocked(self):
        payload = _make_bash_event("psql -c 'drop database mydb'")
        assert _run_main(payload) == 2

    def test_drop_schema_blocked(self):
        payload = _make_bash_event("DROP SCHEMA public CASCADE")
        assert _run_main(payload) == 2

    def test_truncate_table_blocked(self):
        payload = _make_bash_event("TRUNCATE TABLE users")
        assert _run_main(payload) == 2

    def test_chmod_777_blocked(self):
        payload = _make_bash_event("chmod 777 /etc/passwd")
        assert _run_main(payload) == 2

    def test_chmod_recursive_777_blocked(self):
        payload = _make_bash_event("chmod -R 777 /var/www")
        assert _run_main(payload) == 2

    def test_force_push_main_blocked(self):
        payload = _make_bash_event("git push --force origin main")
        assert _run_main(payload) == 2

    def test_force_push_master_blocked(self):
        payload = _make_bash_event("git push -f origin master")
        assert _run_main(payload) == 2

    def test_terraform_destroy_blocked(self):
        payload = _make_bash_event("terraform destroy")
        assert _run_main(payload) == 2

    def test_terraform_destroy_with_target_allowed(self):
        """terraform destroy -target=resource is excepted by the pattern."""
        payload = _make_bash_event("terraform destroy -target=aws_instance.web")
        assert _run_main(payload) == 0

    def test_docker_system_prune_blocked(self):
        payload = _make_bash_event("docker system prune -af")
        assert _run_main(payload) == 2

    def test_kubectl_delete_namespace_blocked(self):
        payload = _make_bash_event("kubectl delete namespace staging")
        assert _run_main(payload) == 2

    def test_mkfs_blocked(self):
        payload = _make_bash_event("mkfs.ext4 /dev/sdb1")
        assert _run_main(payload) == 2

    def test_dd_raw_write_blocked(self):
        payload = _make_bash_event("dd if=/dev/zero of=/dev/sda")
        assert _run_main(payload) == 2

    def test_aws_s3_rb_force_blocked(self):
        payload = _make_bash_event("aws s3 rb s3://my-bucket --force")
        assert _run_main(payload) == 2

    def test_bypass_env_allows_dangerous(self):
        """DANGEROUS_GUARD_BYPASS=1 env var allows destructive commands through."""
        payload = _make_bash_event("rm -rf /")
        assert _run_main(payload, env={"DANGEROUS_GUARD_BYPASS": "1"}) == 0

    def test_safe_rm_allowed(self):
        """rm on a specific non-root file is not dangerous."""
        payload = _make_bash_event("rm -f somefile.txt")
        assert _run_main(payload) == 0

    def test_rm_specific_file_allowed(self):
        payload = _make_bash_event("rm /tmp/build-artifact.tar.gz")
        assert _run_main(payload) == 0

    def test_whitelisted_command_allowed(self):
        """A command matching .guard-whitelist passes even if pattern matches."""
        payload = _make_bash_event("rm -rf ./build")
        whitelist = ["rm -rf ./build"]
        with patch.object(mod, "_load_guard_whitelist", return_value=whitelist):
            assert _run_main(payload) == 0


# ---------------------------------------------------------------------------
# TestCheckCreationGate
# ---------------------------------------------------------------------------


class TestCheckCreationGate:
    """check_creation_gate blocks new agent/skill file creation."""

    def test_new_agent_md_blocked(self):
        """Writing a new (non-existent) agent file must be blocked."""
        payload = _make_write_event("/project/agents/my-new-agent.md")
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload) == 2

    def test_existing_agent_md_allowed(self):
        """Overwriting an existing agent file (update) must be allowed."""
        payload = _make_write_event("/project/agents/existing-agent.md")
        with patch("os.path.exists", return_value=True):
            assert _run_main(payload) == 0

    def test_new_skill_md_blocked(self):
        """Writing a new (non-existent) skill SKILL.md must be blocked."""
        payload = _make_write_event("/project/skills/my-skill/SKILL.md")
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload) == 2

    def test_new_pipeline_skill_md_blocked(self):
        """Writing a new pipeline SKILL.md must be blocked."""
        payload = _make_write_event("/project/skills/workflow/references/my-pipeline.md")
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload) == 2

    def test_existing_skill_md_allowed(self):
        """Overwriting an existing skill SKILL.md must be allowed."""
        payload = _make_write_event("/project/skills/existing-skill/SKILL.md")
        with patch("os.path.exists", return_value=True):
            assert _run_main(payload) == 0

    def test_bypass_allows_creation(self):
        """CREATION_GATE_BYPASS=1 allows new agent/skill creation."""
        payload = _make_write_event("/project/agents/my-new-agent.md")
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload, env={"CREATION_GATE_BYPASS": "1"}) == 0

    def test_non_agent_skill_write_allowed(self):
        """Writes to normal source files pass through the creation gate."""
        payload = _make_write_event("/project/src/main.py")
        assert _run_main(payload) == 0

    def test_agent_in_any_agents_dir_blocked(self):
        """_AGENT_PATTERN matches any /agents/<name>.md segment in the path."""
        payload = _make_write_event("/project/docs/agents/notes.md")
        # r"/agents/[^/]+\.md$" matches any /agents/ directory, not just the repo root
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload) == 2

    def test_voice_skill_creation_allowlisted(self):
        """skills/voice-*/SKILL.md is produced by create-voice — must pass through."""
        payload = _make_write_event("/project/skills/content/voice-feynman/SKILL.md")
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload) == 0

    def test_voice_skill_creation_allowlisted_alt_name(self):
        """The voice-* allowlist accepts any name suffix, not just one example."""
        payload = _make_write_event("/project/skills/voice-someone-else/SKILL.md")
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload) == 0

    def test_non_voice_skill_still_blocked(self):
        """Allowlist must not leak: a generic skill name still routes through skill-creator."""
        payload = _make_write_event("/project/skills/some-other-skill/SKILL.md")
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload) == 2

    def test_voice_prefix_does_not_match_non_skill_md(self):
        """Allowlist matches SKILL.md only — other files in voice-*/ aren't its concern."""
        # The creation gate doesn't fire on non-SKILL.md files anyway, so this
        # confirms the allowlist regex is anchored correctly and doesn't
        # accidentally widen the gate's surface.
        payload = _make_write_event("/project/skills/content/voice-feynman/notes.md")
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload) == 0


# ---------------------------------------------------------------------------
# TestCheckSensitiveFile
# ---------------------------------------------------------------------------


class TestCheckSensitiveFile:
    """check_sensitive_file blocks writes/edits to sensitive files."""

    def test_env_file_write_blocked(self):
        payload = _make_write_event("/project/.env")
        assert _run_main(payload) == 2

    def test_env_file_edit_blocked(self):
        payload = _make_edit_event("/project/.env")
        assert _run_main(payload) == 2

    def test_env_local_blocked(self):
        payload = _make_write_event("/project/.env.local")
        assert _run_main(payload) == 2

    def test_env_production_blocked(self):
        payload = _make_write_event("/project/.env.production")
        assert _run_main(payload) == 2

    def test_credentials_json_blocked(self):
        payload = _make_write_event("/home/user/.config/credentials.json")
        assert _run_main(payload) == 2

    def test_service_account_json_blocked(self):
        payload = _make_write_event("/project/service-account-prod.json")
        assert _run_main(payload) == 2

    def test_ssh_private_key_blocked(self):
        payload = _make_write_event("/home/user/.ssh/id_rsa")
        assert _run_main(payload) == 2

    def test_ssh_ed25519_blocked(self):
        payload = _make_write_event("/home/user/.ssh/id_ed25519")
        assert _run_main(payload) == 2

    def test_ssh_directory_blocked(self):
        payload = _make_write_event("/home/user/.ssh/config")
        assert _run_main(payload) == 2

    def test_aws_credentials_blocked(self):
        payload = _make_write_event("/home/user/.aws/credentials")
        assert _run_main(payload) == 2

    def test_kubeconfig_blocked(self):
        payload = _make_write_event("/home/user/.kube/config")
        assert _run_main(payload) == 2

    def test_p12_certificate_blocked(self):
        payload = _make_write_event("/project/certs/client.p12")
        assert _run_main(payload) == 2

    def test_key_file_blocked(self):
        payload = _make_write_event("/project/certs/server.key")
        assert _run_main(payload) == 2

    def test_token_json_blocked(self):
        payload = _make_write_event("/project/token.json")
        assert _run_main(payload) == 2

    def test_env_example_exception_allowed(self):
        """.env.example is explicitly excepted from the sensitive file guard."""
        payload = _make_write_event("/project/.env.example")
        assert _run_main(payload) == 0

    def test_env_sample_exception_allowed(self):
        payload = _make_write_event("/project/.env.sample")
        assert _run_main(payload) == 0

    def test_env_template_exception_allowed(self):
        payload = _make_write_event("/project/.env.template")
        assert _run_main(payload) == 0

    def test_testdata_exception_allowed(self):
        """Files under /testdata/ are excepted."""
        payload = _make_write_event("/project/testdata/credentials.json")
        assert _run_main(payload) == 0

    def test_fixtures_exception_allowed(self):
        payload = _make_write_event("/project/fixtures/credentials.json")
        assert _run_main(payload) == 0

    def test_dunder_fixtures_exception_allowed(self):
        payload = _make_write_event("/project/__fixtures__/credentials.json")
        assert _run_main(payload) == 0

    def test_bypass_allows_sensitive(self):
        """SENSITIVE_FILE_GUARD_BYPASS=1 allows writes to sensitive files."""
        payload = _make_write_event("/project/.env")
        assert _run_main(payload, env={"SENSITIVE_FILE_GUARD_BYPASS": "1"}) == 0

    def test_bypass_allows_ssh_key(self):
        payload = _make_edit_event("/home/user/.ssh/id_rsa")
        assert _run_main(payload, env={"SENSITIVE_FILE_GUARD_BYPASS": "1"}) == 0

    def test_normal_py_file_allowed(self):
        payload = _make_write_event("/project/src/app.py")
        assert _run_main(payload) == 0


# ---------------------------------------------------------------------------
# TestMainDispatch
# ---------------------------------------------------------------------------


class TestMainDispatch:
    """main() routes to the correct check functions based on tool name."""

    def test_bash_tool_runs_bash_checks(self):
        """Bash tool triggers gitignore, submission, and dangerous checks."""
        payload = _make_bash_event("git push origin main")
        assert _run_main(payload) == 2

    def test_write_tool_runs_creation_and_sensitive(self):
        """Write tool triggers both creation gate and sensitive file checks."""
        # Sensitive file check fires for Write
        payload = _make_write_event("/project/.env")
        assert _run_main(payload) == 2

    def test_write_tool_runs_creation_gate(self):
        """Write to a new agent path triggers creation gate (blocked)."""
        payload = _make_write_event("/project/agents/new-one.md")
        with patch("os.path.exists", return_value=False):
            assert _run_main(payload) == 2

    def test_edit_tool_runs_sensitive_only(self):
        """Edit tool triggers sensitive file check but not creation gate."""
        # .env edit should be blocked by sensitive file guard
        payload = _make_edit_event("/project/.env")
        assert _run_main(payload) == 2

    def test_edit_tool_skips_creation_gate(self):
        """Edit on a new agent path passes — creation gate only applies to Write."""
        payload = _make_edit_event("/project/agents/new-one.md")
        with patch("os.path.exists", return_value=False):
            # Edit does NOT run creation gate; sensitive check passes for .md
            assert _run_main(payload) == 0

    def test_unknown_tool_allowed(self):
        """Read tool and other unknown tools pass through without checks."""
        payload = json.dumps({"tool_name": "Read", "tool_input": {"file_path": "/project/.env"}})
        assert _run_main(payload) == 0

    def test_unknown_tool_name_allowed(self):
        payload = json.dumps({"tool_name": "Glob", "tool_input": {"pattern": "**/*.env"}})
        assert _run_main(payload) == 0

    def test_bash_with_empty_command_allowed(self):
        """Empty command string short-circuits without error."""
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": ""}})
        assert _run_main(payload) == 0

    def test_write_with_empty_file_path_allowed(self):
        """Empty file_path short-circuits without error."""
        payload = json.dumps({"tool_name": "Write", "tool_input": {"file_path": ""}})
        assert _run_main(payload) == 0

    def test_edit_with_empty_file_path_allowed(self):
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": ""}})
        assert _run_main(payload) == 0


# ---------------------------------------------------------------------------
# TestFailOpen
# ---------------------------------------------------------------------------


class TestFailOpen:
    """Exceptions and malformed input must cause the hook to fail open (exit 0)."""

    def test_exception_in_check_fails_open(self):
        """If a check function raises an unexpected exception, exit 0 (fail open)."""
        payload = _make_bash_event("git push origin main")

        def exploding_check(command: str) -> None:
            raise RuntimeError("unexpected internal error")

        with patch.object(mod, "check_git_submission", side_effect=exploding_check):
            # The outer try/except in __main__ block isn't called — main() itself
            # does not wrap. The __main__ block wraps. Simulate the same guard:
            base_env = dict(os.environ)
            for var in (
                "CLAUDE_GATE_BYPASS",
                "DANGEROUS_GUARD_BYPASS",
                "CREATION_GATE_BYPASS",
                "SENSITIVE_FILE_GUARD_BYPASS",
            ):
                base_env.pop(var, None)
            with (
                patch.dict(os.environ, base_env, clear=True),
                patch.object(mod, "read_stdin", return_value=payload),
            ):
                try:
                    mod.main()
                    result = 0
                except SystemExit as e:
                    result = int(e.code) if e.code is not None else 0
                except Exception:
                    # Simulate the __main__ fail-open wrapper
                    result = 0
        assert result == 0

    def test_malformed_json_fails_open(self):
        """Invalid JSON in stdin must exit 0 (fail open)."""
        assert _run_main("not valid json {{{") == 0

    def test_empty_stdin_fails_open(self):
        """Empty stdin must exit 0 (fail open)."""
        assert _run_main("") == 0

    def test_null_json_crashes_main_but_outer_wrapper_fails_open(self):
        """json.loads('null') returns None; main() will AttributeError on .get().
        The __main__ try/except catches this and exits 0 (fail open).
        When calling mod.main() directly the AttributeError propagates — simulate
        the outer wrapper here to verify the intended fail-open contract."""
        base_env = dict(os.environ)
        for var in (
            "CLAUDE_GATE_BYPASS",
            "DANGEROUS_GUARD_BYPASS",
            "CREATION_GATE_BYPASS",
            "SENSITIVE_FILE_GUARD_BYPASS",
        ):
            base_env.pop(var, None)
        with (
            patch.dict(os.environ, base_env, clear=True),
            patch.object(mod, "read_stdin", return_value="null"),
        ):
            try:
                mod.main()
                result = 0
            except SystemExit as e:
                result = int(e.code) if e.code is not None else 0
            except Exception:
                result = 0  # __main__ wrapper exits 0 on any non-SystemExit exception
        assert result == 0

    def test_array_json_crashes_main_but_outer_wrapper_fails_open(self):
        """json.loads of a JSON array returns a list; main() will AttributeError on .get().
        The __main__ try/except catches this and exits 0 (fail open)."""
        base_env = dict(os.environ)
        for var in (
            "CLAUDE_GATE_BYPASS",
            "DANGEROUS_GUARD_BYPASS",
            "CREATION_GATE_BYPASS",
            "SENSITIVE_FILE_GUARD_BYPASS",
        ):
            base_env.pop(var, None)
        with (
            patch.dict(os.environ, base_env, clear=True),
            patch.object(mod, "read_stdin", return_value='["not", "an", "object"]'),
        ):
            try:
                mod.main()
                result = 0
            except SystemExit as e:
                result = int(e.code) if e.code is not None else 0
            except Exception:
                result = 0  # __main__ wrapper exits 0 on any non-SystemExit exception
        assert result == 0


# ---------------------------------------------------------------------------
# TestFieldCompatibility
# ---------------------------------------------------------------------------


class TestFieldCompatibility:
    """Hook supports both new (tool_name/tool_input) and old (tool/input) field names."""

    def test_tool_name_field_used(self):
        """Standard tool_name field is correctly dispatched."""
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "git push origin main"}})
        assert _run_main(payload) == 2

    def test_tool_field_fallback(self):
        """Legacy 'tool' field name is also recognised as a fallback."""
        payload = json.dumps({"tool": "Bash", "input": {"command": "git push origin main"}})
        assert _run_main(payload) == 2

    def test_tool_input_fallback_to_input(self):
        """Legacy 'input' field is used when 'tool_input' is absent."""
        payload = json.dumps({"tool_name": "Write", "input": {"file_path": "/project/.env"}})
        assert _run_main(payload) == 2

    def test_tool_name_takes_precedence_over_tool(self):
        """When both 'tool_name' and 'tool' are present, tool_name wins."""
        # tool_name=Bash (blocked), tool=Read (would pass) — tool_name must win
        payload = json.dumps(
            {
                "tool_name": "Bash",
                "tool": "Read",
                "tool_input": {"command": "git push origin main"},
            }
        )
        assert _run_main(payload) == 2

    def test_missing_tool_name_and_tool_allows(self):
        """Event with no tool identifier passes through (unknown tool)."""
        payload = json.dumps({"tool_input": {"command": "git push origin main"}})
        assert _run_main(payload) == 0


# ---------------------------------------------------------------------------
# TestRmFlagOrderingEvasion (Bug 1)
# ---------------------------------------------------------------------------


class TestRmFlagOrderingEvasion:
    """rm patterns must catch -r and -f flags in ANY order, not just -rf."""

    # --- Existing patterns that must still be blocked ---

    def test_rm_rf_root_blocked(self):
        payload = _make_bash_event("rm -rf /")
        assert _run_main(payload) == 2

    def test_rm_fr_root_blocked(self):
        payload = _make_bash_event("rm -fr /")
        assert _run_main(payload) == 2

    # --- Separated flags (previously bypassed) ---

    def test_rm_r_f_root_blocked(self):
        """rm -r -f / was bypassing the guard."""
        payload = _make_bash_event("rm -r -f /")
        assert _run_main(payload) == 2

    def test_rm_f_r_root_blocked(self):
        """rm -f -r / was bypassing the guard."""
        payload = _make_bash_event("rm -f -r /")
        assert _run_main(payload) == 2

    def test_rm_r_f_home_blocked(self):
        """rm -r -f ~ was bypassing the guard."""
        payload = _make_bash_event("rm -r -f ~")
        assert _run_main(payload) == 2

    def test_rm_r_f_dot_blocked(self):
        """rm -r -f . was bypassing the guard."""
        payload = _make_bash_event("rm -r -f .")
        assert _run_main(payload) == 2

    # --- Long-form flags (previously bypassed) ---

    def test_rm_recursive_force_root_blocked(self):
        """rm --recursive --force / was bypassing the guard."""
        payload = _make_bash_event("rm --recursive --force /")
        assert _run_main(payload) == 2

    def test_rm_recursive_f_root_blocked(self):
        """rm --recursive -f / was bypassing the guard."""
        payload = _make_bash_event("rm --recursive -f /")
        assert _run_main(payload) == 2

    def test_rm_r_force_root_blocked(self):
        """rm -r --force / was bypassing the guard."""
        payload = _make_bash_event("rm -r --force /")
        assert _run_main(payload) == 2

    # --- Long-form flags on other targets ---

    def test_rm_recursive_force_home_blocked(self):
        payload = _make_bash_event("rm --recursive --force ~")
        assert _run_main(payload) == 2

    def test_rm_recursive_force_dot_blocked(self):
        payload = _make_bash_event("rm --recursive --force .")
        assert _run_main(payload) == 2

    def test_rm_recursive_force_root_star_blocked(self):
        payload = _make_bash_event("rm --recursive --force /*")
        assert _run_main(payload) == 2

    # --- Safe rm commands that must NOT be blocked ---

    def test_rm_single_file_allowed(self):
        """rm file.txt is safe — no recursive flag."""
        payload = _make_bash_event("rm file.txt")
        assert _run_main(payload) == 0

    def test_rm_f_single_file_allowed(self):
        """rm -f file.txt is safe — force but no recursive."""
        payload = _make_bash_event("rm -f file.txt")
        assert _run_main(payload) == 0

    def test_rm_r_subdir_allowed(self):
        """rm -r ./build is safe — recursive but no force on dangerous target."""
        payload = _make_bash_event("rm -r ./build/output")
        assert _run_main(payload) == 0


# ---------------------------------------------------------------------------
# TestGuardPatternsMalformedEntry (Bug 2)
# ---------------------------------------------------------------------------


class TestGuardPatternsMalformedEntry:
    """_load_guard_patterns must not crash on malformed regex entries."""

    def test_malformed_entry_skipped_valid_entry_works(self, tmp_path):
        """A malformed .guard-patterns entry alongside a valid entry:
        (1) the valid entry still works, (2) no crash, (3) warning on stderr.
        """
        guard_file = tmp_path / ".guard-patterns"
        # Deliberately broken regex that would fail re.compile (unmatched group)
        # after re.escape, this would actually be fine, but let's use something
        # that re.escape + glob conversion wouldn't fix — actually with re.escape
        # all metacharacters get escaped, so we need to test the warning path.
        # We'll mock to force a re.error on one entry.
        guard_file.write_text("/valid/secret/path\n")

        stderr_capture = io.StringIO()
        with patch("pathlib.Path.cwd", return_value=tmp_path):
            # First: verify valid entry works normally
            patterns = mod._load_guard_patterns()
            assert len(patterns) == 1
            assert patterns[0][1] == "custom"

        # Now test with a forced re.error on one entry while a valid entry follows
        guard_file.write_text("bad-entry-here\n/valid/secret/path\n")

        original_compile = re.compile

        def patched_compile(pattern, *args, **kwargs):
            # Force error only for the pattern derived from "bad-entry-here"
            if pattern == r"bad\-entry\-here":
                raise re.error("mock error")
            return original_compile(pattern, *args, **kwargs)

        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch.object(re, "compile", side_effect=patched_compile),
            patch("sys.stderr", stderr_capture),
        ):
            patterns = mod._load_guard_patterns()

        # Valid entry survived
        assert len(patterns) == 1
        assert patterns[0][2] == "/valid/secret/path"

        # Warning was printed for the bad entry
        stderr_output = stderr_capture.getvalue()
        assert "WARN" in stderr_output
        assert "bad-entry-here" in stderr_output

    def test_all_malformed_entries_produce_empty_list(self, tmp_path):
        """If every entry is malformed, return empty list, not crash."""
        guard_file = tmp_path / ".guard-patterns"
        guard_file.write_text("bad1\nbad2\n")

        original_compile = re.compile

        def always_fail(pattern, *args, **kwargs):
            raise re.error("all bad")

        stderr_capture = io.StringIO()
        with (
            patch("pathlib.Path.cwd", return_value=tmp_path),
            patch.object(re, "compile", side_effect=always_fail),
            patch("sys.stderr", stderr_capture),
        ):
            patterns = mod._load_guard_patterns()

        assert patterns == []
        assert stderr_capture.getvalue().count("WARN") == 2


# ---------------------------------------------------------------------------
# TestGlobToRegexEscaping (Bug 3)
# ---------------------------------------------------------------------------


class TestGlobToRegexEscaping:
    """Glob-to-regex conversion must escape ALL regex metacharacters."""

    def test_brackets_treated_literally(self, tmp_path):
        """A .guard-patterns entry with brackets like /path/[secret]/config
        must match the literal path and NOT interpret [] as a character class.
        """
        guard_file = tmp_path / ".guard-patterns"
        guard_file.write_text("/path/[secret]/config\n")

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            patterns = mod._load_guard_patterns()

        assert len(patterns) == 1
        pattern = patterns[0][0]

        # Must match the literal path with brackets
        assert pattern.search("/path/[secret]/config") is not None

        # Must NOT match /path/s/config (which would happen if [] was a char class)
        assert pattern.search("/path/s/config") is None

    def test_parens_treated_literally(self, tmp_path):
        """Parentheses in .guard-patterns must be treated as literal characters."""
        guard_file = tmp_path / ".guard-patterns"
        guard_file.write_text("/path/(group)/config\n")

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            patterns = mod._load_guard_patterns()

        assert len(patterns) == 1
        pattern = patterns[0][0]

        # Must match the literal path with parens
        assert pattern.search("/path/(group)/config") is not None

        # Must NOT match /path/group/config (which would happen if () was a group)
        assert pattern.search("/path/group/config") is None

    def test_plus_caret_pipe_treated_literally(self, tmp_path):
        """Characters +, ^, | in .guard-patterns must be literal."""
        guard_file = tmp_path / ".guard-patterns"
        guard_file.write_text("/path/a+b^c|d\n")

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            patterns = mod._load_guard_patterns()

        assert len(patterns) == 1
        pattern = patterns[0][0]

        # Must match the literal path
        assert pattern.search("/path/a+b^c|d") is not None

        # Must NOT match variations that regex would allow
        assert pattern.search("/path/aab^c|d") is None  # + as quantifier
        assert pattern.search("/path/a+bXc|d") is None  # ^ as anchor
        assert pattern.search("/path/a+b^cd") is None  # | as alternation

    def test_glob_star_still_works(self, tmp_path):
        """Glob * should still convert to .* for wildcard matching."""
        guard_file = tmp_path / ".guard-patterns"
        guard_file.write_text("/secrets/*.key\n")

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            patterns = mod._load_guard_patterns()

        assert len(patterns) == 1
        pattern = patterns[0][0]

        assert pattern.search("/secrets/server.key") is not None
        assert pattern.search("/secrets/client.key") is not None
        assert pattern.search("/other/server.key") is None

    def test_glob_question_mark_still_works(self, tmp_path):
        """Glob ? should still convert to . for single-char matching."""
        guard_file = tmp_path / ".guard-patterns"
        guard_file.write_text("/secrets/key?.pem\n")

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            patterns = mod._load_guard_patterns()

        assert len(patterns) == 1
        pattern = patterns[0][0]

        assert pattern.search("/secrets/key1.pem") is not None
        assert pattern.search("/secrets/keyA.pem") is not None
        assert pattern.search("/secrets/key.pem") is None  # ? requires exactly one char
        assert pattern.search("/secrets/key12.pem") is None  # ? matches only one char


# ---------------------------------------------------------------------------
# TestCheckPublicDevServer
# ---------------------------------------------------------------------------


class TestCheckPublicDevServer:
    """check_public_dev_server blocks dev servers bound to non-loopback interfaces."""

    # --- python http.server: block-by-default (binds 0.0.0.0 by default) ---

    def test_bare_http_server_blocked(self):
        """Bare `python3 -m http.server 8080` binds 0.0.0.0 by default → BLOCK."""
        assert _run_main(_make_bash_event("python3 -m http.server 8080")) == 2

    def test_http_server_no_port_blocked(self):
        assert _run_main(_make_bash_event("python -m http.server")) == 2

    def test_http_server_explicit_public_bind_blocked(self):
        assert _run_main(_make_bash_event("python3 -m http.server 8080 --bind 0.0.0.0")) == 2

    def test_http_server_equals_public_bind_blocked(self):
        """`--bind=0.0.0.0` (equals form) must be caught."""
        assert _run_main(_make_bash_event("python3 -m http.server --bind=0.0.0.0")) == 2

    def test_http_server_no_space_after_m_blocked(self):
        """`-mhttp.server` (no space) is accepted by Python and must be caught (PR #716)."""
        assert _run_main(_make_bash_event("python3 -mhttp.server 8080")) == 2

    def test_http_server_bare_zero_bind_blocked(self):
        """`--bind 0` is shorthand for 0.0.0.0 → BLOCK."""
        assert _run_main(_make_bash_event("python3 -m http.server --bind 0")) == 2

    def test_http_server_ipv6_wildcard_bind_blocked(self):
        """`--bind ::` is the IPv6 all-interfaces wildcard → BLOCK."""
        assert _run_main(_make_bash_event("python3 -m http.server --bind ::")) == 2

    def test_simplehttpserver_blocked(self):
        """python2 SimpleHTTPServer is the legacy module name → BLOCK."""
        assert _run_main(_make_bash_event("python2 -m SimpleHTTPServer 8000")) == 2

    def test_http_server_loopback_bind_allowed(self):
        assert _run_main(_make_bash_event("python3 -m http.server 8080 --bind 127.0.0.1")) == 0

    def test_http_server_localhost_bind_allowed(self):
        assert _run_main(_make_bash_event("python3 -m http.server --bind localhost")) == 0

    def test_http_server_ipv6_loopback_bind_allowed(self):
        assert _run_main(_make_bash_event("python3 -m http.server --bind ::1")) == 0

    def test_http_server_short_bind_loopback_allowed(self):
        assert _run_main(_make_bash_event("python3 -m http.server -b 127.0.0.1")) == 0

    # --- cwd symlinked to a public path: bare http.server still blocks ---

    def test_cwd_symlinked_public_path_blocked(self, tmp_path):
        """Even from a symlinked cwd, bare http.server (no loopback bind) is blocked.

        The interface-based block does not depend on cwd, so a symlinked working
        directory that resolves to a served public path is still caught.
        """
        real = tmp_path / "served"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real)
        payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "python3 -m http.server 8080"}, "cwd": str(link)}
        )
        assert _run_main(payload) == 2

    # --- php -S ---

    def test_php_server_public_blocked(self):
        assert _run_main(_make_bash_event("php -S 0.0.0.0:8000")) == 2

    def test_php_server_loopback_allowed(self):
        assert _run_main(_make_bash_event("php -S 127.0.0.1:8000")) == 0

    def test_php_server_localhost_allowed(self):
        assert _run_main(_make_bash_event("php -S localhost:8000")) == 0

    # --- JS/static dev servers: block only on explicit public host flag ---

    def test_vite_public_host_blocked(self):
        assert _run_main(_make_bash_event("vite --host 0.0.0.0")) == 2

    def test_next_public_host_blocked(self):
        assert _run_main(_make_bash_event("next dev -H 0.0.0.0")) == 2

    def test_hugo_public_bind_blocked(self):
        assert _run_main(_make_bash_event("hugo server --bind 0.0.0.0")) == 2

    def test_http_server_npm_public_blocked(self):
        """The http-server npm package binds via -a/--address → BLOCK on 0.0.0.0."""
        assert _run_main(_make_bash_event("http-server -a 0.0.0.0")) == 2

    def test_http_server_npm_loopback_allowed(self):
        assert _run_main(_make_bash_event("http-server -a 127.0.0.1")) == 0

    def test_vite_loopback_host_allowed(self):
        assert _run_main(_make_bash_event("vite --host 127.0.0.1")) == 0

    def test_bare_npm_run_dev_allowed(self):
        """Bare `npm run dev` with no host flag defaults to localhost → ALLOW (no false positive)."""
        assert _run_main(_make_bash_event("npm run dev")) == 0

    def test_bare_vite_allowed(self):
        """Bare `vite` (no --host) defaults to localhost → ALLOW."""
        assert _run_main(_make_bash_event("vite")) == 0

    # --- deployment tooling and unrelated commands: ALLOW ---

    def test_nginx_restart_allowed(self):
        assert _run_main(_make_bash_event("sudo systemctl restart nginx")) == 0

    def test_certbot_allowed(self):
        assert _run_main(_make_bash_event("certbot --nginx -d example.com")) == 0

    def test_caddy_allowed(self):
        assert _run_main(_make_bash_event("caddy run --config /etc/caddy/Caddyfile")) == 0

    def test_cloudflared_allowed(self):
        assert _run_main(_make_bash_event("cloudflared tunnel run mytunnel")) == 0

    def test_unrelated_command_allowed(self):
        assert _run_main(_make_bash_event("ls -la")) == 0

    def test_grep_http_server_allowed(self):
        """grep for the literal string http.server must not be mistaken for an invocation."""
        assert _run_main(_make_bash_event("grep -r http.server .")) == 0

    def test_echo_http_server_allowed(self):
        assert _run_main(_make_bash_event("echo http.server")) == 0

    # --- codex-found bypasses (now fixed) ---

    def test_py_launcher_blocked(self):
        """The Windows/py launcher `py -m http.server` was a regex miss → now BLOCK."""
        assert _run_main(_make_bash_event("py -m http.server 8000")) == 2

    def test_quoted_module_name_blocked(self):
        """`python3 -m 'http.server'` (quoted module arg, still executed) → BLOCK."""
        assert _run_main(_make_bash_event("python3 -m 'http.server' 8000")) == 2

    def test_double_quoted_module_name_blocked(self):
        assert _run_main(_make_bash_event('python3 -m "http.server" 8000')) == 2

    def test_npm_run_dev_forwarded_public_host_blocked(self):
        """`npm run dev -- --host 0.0.0.0` forwards an explicit public host → BLOCK."""
        assert _run_main(_make_bash_event("npm run dev -- --host 0.0.0.0")) == 2

    def test_pnpm_dev_public_host_blocked(self):
        assert _run_main(_make_bash_event("pnpm run dev -- --host 0.0.0.0")) == 2

    # --- codex-found false positives (now fixed) ---

    def test_echo_quoting_full_command_allowed(self):
        """`echo 'python3 -m http.server 8000'` only displays a string → ALLOW."""
        assert _run_main(_make_bash_event("echo 'python3 -m http.server 8000'")) == 0

    def test_grep_quoting_full_command_allowed(self):
        assert _run_main(_make_bash_event("grep -r 'python3 -m http.server' .")) == 0

    def test_echo_quoting_vite_host_allowed(self):
        assert _run_main(_make_bash_event("echo 'vite --host 0.0.0.0'")) == 0

    def test_printf_quoting_command_allowed(self):
        assert _run_main(_make_bash_event("printf 'php -S 0.0.0.0:8000\\n'")) == 0

    # --- chaining: the real invocation in a chain is still caught ---

    def test_cd_then_http_server_blocked(self):
        """`cd ~/proj && python3 -m http.server 8080` — the served segment blocks."""
        assert _run_main(_make_bash_event("cd ~/proj && python3 -m http.server 8080")) == 2

    def test_echo_then_real_server_blocked(self):
        """A benign echo followed by a real public server still blocks the server."""
        assert _run_main(_make_bash_event("echo hi && vite --host 0.0.0.0")) == 2

    def test_printf_multiline_quoted_data_allowed(self):
        """A literal newline inside a quoted printf arg must not be mis-split into
        a fake server segment (codex-found false positive). Splitter ignores \\n."""
        assert _run_main(_make_bash_event("printf '%s\n' 'python3 -m http.server'")) == 0

    def test_heredoc_body_mentioning_server_allowed(self):
        """A heredoc body that merely contains the server string is data, not an
        invocation — must not block (codex-found false positive)."""
        assert _run_main(_make_bash_event("cat <<'EOF'\npython3 -m http.server\nEOF")) == 0

    # --- PR #719: command-token anchoring removes flag/word-collision false
    # positives. Server names in arguments (commit messages, URLs) and unrelated
    # short flags (git -a, curl -H, ssh -b) must NOT be mistaken for a server. ---

    def test_git_commit_message_named_next_allowed(self):
        """`git commit -a -m next`: `next` is a commit message, not the dev server,
        and `-a` is git's all-tracked flag, not http-server's address flag → ALLOW."""
        assert _run_main(_make_bash_event("git commit -a -m next")) == 0

    def test_git_add_then_commit_message_named_next_allowed(self):
        """Chained `git add -A && git commit -a -m next` → ALLOW (no segment is a server)."""
        assert _run_main(_make_bash_event("git add -A && git commit -a -m next")) == 0

    def test_git_commit_message_named_vite_allowed(self):
        """`git commit -a -m vite`: `vite` in a commit message is not an invocation → ALLOW."""
        assert _run_main(_make_bash_event("git commit -a -m vite")) == 0

    def test_curl_header_to_vite_dev_url_allowed(self):
        """`curl -H 'X: y' https://vite.dev`: curl's -H is a header, the host token
        is `curl`, and `vite.dev` is a URL — not the vite dev server → ALLOW."""
        assert _run_main(_make_bash_event("curl -H 'X: y' https://vite.dev")) == 0

    def test_ng_build_passthrough_dash_a_allowed(self):
        """`ng build -- -a foo`: a build (not serve) with a passthrough -a that is
        not a public host; -a's value `foo` is not a wildcard/public IP → ALLOW."""
        assert _run_main(_make_bash_event("ng build -- -a foo")) == 0

    def test_npm_run_build_allowed(self):
        """`npm run build` has no host flag → ALLOW (no false positive on build)."""
        assert _run_main(_make_bash_event("npm run build")) == 0

    def test_ssh_dash_b_bind_address_allowed(self):
        """`ssh -b 0.0.0.0 host`: ssh's -b is a bind-address for the SSH client,
        and `ssh` is not a guarded server → ALLOW (short flag not scanned)."""
        assert _run_main(_make_bash_event("ssh -b 0.0.0.0 example.com")) == 0

    def test_server_name_as_path_arg_allowed(self):
        """`ls next/` — `next` appearing as a path argument is not an invocation → ALLOW."""
        assert _run_main(_make_bash_event("ls next/")) == 0

    # --- PR #719 MEDIUM-1: command-substitution bodies are real invocations even
    # inside a display command, and must still BLOCK. ---

    def test_echo_substitution_http_server_blocked(self):
        """`echo $(python3 -m http.server 8080)` launches a real server in the
        substitution — the display wrapper must NOT suppress it → BLOCK."""
        assert _run_main(_make_bash_event("echo $(python3 -m http.server 8080)")) == 2

    def test_grep_substitution_php_server_blocked(self):
        """`grep $(php -S 0.0.0.0:8000) f` launches php's public server in a
        substitution → BLOCK."""
        assert _run_main(_make_bash_event("grep $(php -S 0.0.0.0:8000) f")) == 2

    def test_backtick_substitution_http_server_blocked(self):
        """Backtick substitution `\\`python3 -m http.server\\`` is also a real
        invocation → BLOCK."""
        assert _run_main(_make_bash_event("echo `python3 -m http.server`")) == 2

    def test_echo_substitution_loopback_allowed(self):
        """A loopback bind inside a substitution is still safe → ALLOW."""
        assert _run_main(_make_bash_event("echo $(python3 -m http.server --bind 127.0.0.1)")) == 0

    # --- PR #719 MEDIUM-2: common Python web servers (flask/uvicorn/gunicorn) on
    # a public host. Anchored at the command token, so no new false positives. ---

    def test_flask_run_public_host_blocked(self):
        """`flask run --host=0.0.0.0` exposes the Flask dev server publicly → BLOCK."""
        assert _run_main(_make_bash_event("python3 -m flask run --host=0.0.0.0")) == 2

    def test_flask_run_command_token_public_blocked(self):
        """Bare `flask run --host 0.0.0.0` (console-script form) → BLOCK."""
        assert _run_main(_make_bash_event("flask run --host 0.0.0.0")) == 2

    def test_uvicorn_public_host_blocked(self):
        """`uvicorn app:app --host 0.0.0.0` → BLOCK."""
        assert _run_main(_make_bash_event("uvicorn app:app --host 0.0.0.0")) == 2

    def test_gunicorn_public_bind_blocked(self):
        """`gunicorn -b 0.0.0.0:8000 app:app` (-b is gunicorn's bind) → BLOCK."""
        assert _run_main(_make_bash_event("gunicorn -b 0.0.0.0:8000 app:app")) == 2

    def test_php_artisan_serve_public_blocked(self):
        """`php artisan serve --host=0.0.0.0` (Laravel dev server) → BLOCK."""
        assert _run_main(_make_bash_event("php artisan serve --host=0.0.0.0")) == 2

    def test_flask_run_loopback_allowed(self):
        """`flask run --host=127.0.0.1` binds loopback → ALLOW."""
        assert _run_main(_make_bash_event("flask run --host=127.0.0.1")) == 0

    def test_uvicorn_loopback_allowed(self):
        """`uvicorn app:app --host 127.0.0.1` → ALLOW."""
        assert _run_main(_make_bash_event("uvicorn app:app --host 127.0.0.1")) == 0

    def test_gunicorn_loopback_bind_allowed(self):
        """`gunicorn -b 127.0.0.1:8000 app` → ALLOW."""
        assert _run_main(_make_bash_event("gunicorn -b 127.0.0.1:8000 app")) == 0

    def test_bare_flask_run_allowed(self):
        """Bare `flask run` (no host flag) defaults to 127.0.0.1 → ALLOW."""
        assert _run_main(_make_bash_event("flask run")) == 0

    # --- PR #719 still-block regressions for the core cases ---

    def test_bind_wildcard_still_blocked(self):
        """`python3 -m http.server --bind 0.0.0.0` still blocks after the refactor."""
        assert _run_main(_make_bash_event("python3 -m http.server --bind 0.0.0.0")) == 2

    def test_vite_public_host_still_blocked(self):
        """`vite --host 0.0.0.0` still blocks (long flag, command-token anchored)."""
        assert _run_main(_make_bash_event("vite --host 0.0.0.0")) == 2

    def test_sudo_wrapped_server_blocked(self):
        """`sudo python3 -m http.server` — wrapper stripped, server still caught → BLOCK."""
        assert _run_main(_make_bash_event("sudo python3 -m http.server")) == 2

    def test_env_prefixed_server_blocked(self):
        """`PORT=80 vite --host 0.0.0.0` — env-assignment prefix stripped → BLOCK."""
        assert _run_main(_make_bash_event("PORT=80 vite --host 0.0.0.0")) == 2

    # --- PR #719 codex round-2: wrapper-flag and exec-runner bypasses (closed) ---

    def test_sudo_value_flag_wrapped_php_blocked(self):
        """`sudo -u nobody php -S 0.0.0.0:8000` — sudo's `-u nobody` value flag is
        stripped so php becomes the command token (codex round-2 false negative)."""
        assert _run_main(_make_bash_event("sudo -u nobody php -S 0.0.0.0:8000")) == 2

    def test_npx_vite_public_host_blocked(self):
        """`npx vite --host 0.0.0.0` — the npx exec-runner prefix is stripped so
        vite is the command token (codex round-2 false negative)."""
        assert _run_main(_make_bash_event("npx vite --host 0.0.0.0")) == 2

    def test_npm_exec_next_short_flag_blocked(self):
        """`npm exec next dev -H 0.0.0.0` — exec prefix stripped, next's -H scanned."""
        assert _run_main(_make_bash_event("npm exec next dev -H 0.0.0.0")) == 2

    def test_yarn_dlx_astro_public_blocked(self):
        """`yarn dlx astro dev --host 0.0.0.0` — yarn dlx prefix stripped → BLOCK."""
        assert _run_main(_make_bash_event("yarn dlx astro dev --host 0.0.0.0")) == 2

    def test_bun_x_next_public_blocked(self):
        """`bun x next dev -H 0.0.0.0` — bun x prefix stripped → BLOCK."""
        assert _run_main(_make_bash_event("bun x next dev -H 0.0.0.0")) == 2

    def test_npx_non_server_allowed(self):
        """`npx eslint .` — exec runner of a non-server tool → ALLOW (no false positive)."""
        assert _run_main(_make_bash_event("npx eslint .")) == 0

    def test_npm_exec_non_server_allowed(self):
        """`npm exec tsc -- --noEmit` — exec of a non-server tool → ALLOW."""
        assert _run_main(_make_bash_event("npm exec tsc -- --noEmit")) == 0

    # --- PR #719 codex round-3: exec-runner option flags and php CLI scripts ---

    def test_npx_yes_flag_then_server_blocked(self):
        """`npx --yes vite --host 0.0.0.0` — npx's `--yes` option is stripped so
        vite becomes the command token (codex round-3 false negative)."""
        assert _run_main(_make_bash_event("npx --yes vite --host 0.0.0.0")) == 2

    def test_npx_package_value_flag_then_server_blocked(self):
        """`npx -p vite vite --host 0.0.0.0` — `-p vite` value flag is consumed."""
        assert _run_main(_make_bash_event("npx -p vite vite --host 0.0.0.0")) == 2

    def test_npx_yes_non_server_allowed(self):
        """`npx --yes prettier --write .` — non-server exec with an option → ALLOW."""
        assert _run_main(_make_bash_event("npx --yes prettier --write .")) == 0

    def test_php_cli_script_with_host_arg_allowed(self):
        """`php script.php --host 0.0.0.0` is an ordinary CLI script — its --host is
        the script's own arg, NOT a server bind (codex round-3 false positive)."""
        assert _run_main(_make_bash_event("php script.php --host 0.0.0.0")) == 0

    def test_php_artisan_serve_loopback_allowed(self):
        """`php artisan serve --host=127.0.0.1` binds loopback → ALLOW."""
        assert _run_main(_make_bash_event("php artisan serve --host=127.0.0.1")) == 0

    # --- PR #719 codex round-4: wrapper value-flags (nice -n, ionice -c) ---

    def test_nice_value_flag_wrapped_server_blocked(self):
        """`nice -n 5 vite --host 0.0.0.0` — nice's `-n 5` value flag is stripped so
        vite becomes the command token (codex round-4 false negative)."""
        assert _run_main(_make_bash_event("nice -n 5 vite --host 0.0.0.0")) == 2

    def test_ionice_value_flag_wrapped_server_blocked(self):
        """`ionice -c 2 vite --host 0.0.0.0` — ionice's `-c 2` value flag stripped."""
        assert _run_main(_make_bash_event("ionice -c 2 vite --host 0.0.0.0")) == 2

    def test_nice_wrapped_non_server_allowed(self):
        """`nice -n 10 npm run build` — wrapped non-server build → ALLOW."""
        assert _run_main(_make_bash_event("nice -n 10 npm run build")) == 0

    # --- PR #719 codex round-5: flask -h short flag and long wrapper value-flags ---

    def test_flask_short_host_flag_blocked(self):
        """`flask run -h 0.0.0.0` — flask's `-h` is short for --host → BLOCK."""
        assert _run_main(_make_bash_event("flask run -h 0.0.0.0")) == 2

    def test_flask_module_short_host_flag_blocked(self):
        """`python3 -m flask run -h 0.0.0.0` — module form, flask's -h → BLOCK."""
        assert _run_main(_make_bash_event("python3 -m flask run -h 0.0.0.0")) == 2

    def test_sudo_long_user_flag_wrapped_server_blocked(self):
        """`sudo --user nobody vite --host 0.0.0.0` — sudo's `--user nobody` long
        value flag is stripped so vite is the command token (codex round-5)."""
        assert _run_main(_make_bash_event("sudo --user nobody vite --host 0.0.0.0")) == 2

    def test_sudo_long_user_equals_flag_wrapped_server_blocked(self):
        """`sudo --user=nobody vite --host 0.0.0.0` — `--user=nobody` single token."""
        assert _run_main(_make_bash_event("sudo --user=nobody vite --host 0.0.0.0")) == 2

    def test_sudo_long_user_flag_non_server_allowed(self):
        """`sudo --user me ls -la` — wrapped non-server command → ALLOW."""
        assert _run_main(_make_bash_event("sudo --user me ls -la")) == 0

    # --- PR #719 codex round-6: valueless-flag mis-consume and path-qualified
    # wrappers/runners/interpreters. ---

    def test_env_valueless_flag_then_server_blocked(self):
        """`env -i vite --host 0.0.0.0` — env's `-i` is valueless; vite (an
        executable token) must not be eaten as its value (codex round-6)."""
        assert _run_main(_make_bash_event("env -i vite --host 0.0.0.0")) == 2

    def test_time_valueless_flag_then_server_blocked(self):
        """`time -p vite --host 0.0.0.0` — `-p` valueless, vite preserved → BLOCK."""
        assert _run_main(_make_bash_event("time -p vite --host 0.0.0.0")) == 2

    def test_path_qualified_wrapper_server_blocked(self):
        """`/usr/bin/env vite --host 0.0.0.0` — wrapper matched by basename → BLOCK."""
        assert _run_main(_make_bash_event("/usr/bin/env vite --host 0.0.0.0")) == 2

    def test_path_qualified_sudo_server_blocked(self):
        """`/bin/sudo vite --host 0.0.0.0` — path-qualified sudo stripped → BLOCK."""
        assert _run_main(_make_bash_event("/bin/sudo vite --host 0.0.0.0")) == 2

    def test_path_qualified_npx_server_blocked(self):
        """`/usr/local/bin/npx vite --host 0.0.0.0` — path-qualified runner → BLOCK."""
        assert _run_main(_make_bash_event("/usr/local/bin/npx vite --host 0.0.0.0")) == 2

    def test_path_qualified_python_flask_blocked(self):
        """`/usr/bin/python3 -m flask run --host=0.0.0.0` — path-qualified interpreter."""
        assert _run_main(_make_bash_event("/usr/bin/python3 -m flask run --host=0.0.0.0")) == 2

    def test_env_unset_then_non_server_allowed(self):
        """`env -u FOO npm run build` — env -u consumes FOO, non-server build → ALLOW."""
        assert _run_main(_make_bash_event("env -u FOO npm run build")) == 0

    def test_python_m_pytest_flask_keyword_allowed(self):
        """`python3 -m pytest -k flask` — pytest is not a web server; `flask` is a
        test keyword, not the flask server → ALLOW."""
        assert _run_main(_make_bash_event("python3 -m pytest -k flask")) == 0

    # --- PR #719 codex round-7: single-quoted substitution is literal data ---

    def test_single_quoted_substitution_allowed(self):
        """`echo '$(python3 -m http.server)'` — inside single quotes the `$(...)` is
        literal text, NOT a substitution → ALLOW (codex round-7 false positive)."""
        assert _run_main(_make_bash_event("echo '$(python3 -m http.server)'")) == 0

    def test_unquoted_substitution_still_blocked(self):
        """`echo $(python3 -m http.server)` (unquoted) is a real substitution → BLOCK.
        Guards that the single-quote fix did not disable MEDIUM-1 detection."""
        assert _run_main(_make_bash_event("echo $(python3 -m http.server)")) == 2

    def test_double_quoted_substitution_still_blocked(self):
        """`echo "$(python3 -m http.server)"` — double quotes DO allow substitution
        in the shell, so this is a real invocation → BLOCK."""
        assert _run_main(_make_bash_event('echo "$(python3 -m http.server)"')) == 2

    # --- PR #719 codex round-8: quoted env-assignment values with spaces ---

    def test_quoted_env_value_with_space_then_server_blocked(self):
        """`A='x y' vite --host 0.0.0.0` — shlex keeps the quoted value one token so
        the env-assignment prefix is stripped and vite is the command token
        (codex round-8 false negative; naive split() broke on the space)."""
        assert _run_main(_make_bash_event("A='x y' vite --host 0.0.0.0")) == 2

    def test_quoted_env_value_with_space_php_blocked(self):
        """`A='x y' php -S 0.0.0.0:8000` → BLOCK after shlex tokenization."""
        assert _run_main(_make_bash_event("A='x y' php -S 0.0.0.0:8000")) == 2

    def test_quoted_env_value_with_space_loopback_allowed(self):
        """`A='x y' vite --host 127.0.0.1` — loopback bind still allowed."""
        assert _run_main(_make_bash_event("A='x y' vite --host 127.0.0.1")) == 0

    def test_unbalanced_quote_does_not_crash(self):
        """An unbalanced quote must not crash shlex tokenization (fail open, exit 0).
        The real server in the segment is still caught via the naive-split fallback."""
        assert _run_main(_make_bash_event("vite --host 0.0.0.0 'unbalanced")) == 2

    # --- PR #719 codex round-9: single quotes INSIDE double quotes are not literal ---

    def test_single_quotes_inside_double_quotes_substitution_blocked(self):
        """`echo "'$(python3 -m http.server)'"` — single quotes inside double quotes
        are ordinary characters, so the `$()` STILL executes in the shell and must
        be caught (codex round-9: naive single-quote-span suppression missed this)."""
        assert _run_main(_make_bash_event("echo \"'$(python3 -m http.server)'\"")) == 2

    def test_single_quotes_inside_double_quotes_php_blocked(self):
        """`echo "'$(php -S 0.0.0.0:8000)'"` — same mixed-quoting case for php → BLOCK."""
        assert _run_main(_make_bash_event("echo \"'$(php -S 0.0.0.0:8000)'\"")) == 2

    # --- PR #719 codex round-10: backslash-escaped single quotes are not literal ---

    def test_escaped_single_quote_substitution_blocked(self):
        r"""`echo \'$(python3 -m http.server)\'` — `\'` is a literal quote char, NOT a
        single-quoted span, so the `$()` still executes → BLOCK (codex round-10)."""
        assert _run_main(_make_bash_event(r"echo \'$(python3 -m http.server)\'")) == 2

    def test_escaped_single_quote_php_substitution_blocked(self):
        r"""`echo \'$(php -S 0.0.0.0:8000)\'` — escaped quotes, php server → BLOCK."""
        assert _run_main(_make_bash_event(r"echo \'$(php -S 0.0.0.0:8000)\'")) == 2

    # --- PR #719 codex round-11: timeout-wrapped servers (common smoke-test form) ---

    def test_timeout_wrapped_vite_blocked(self):
        """`timeout 30s vite --host 0.0.0.0` — timeout's DURATION positional is
        skipped so vite is the command token (codex round-11, common in CI)."""
        assert _run_main(_make_bash_event("timeout 30s vite --host 0.0.0.0")) == 2

    def test_timeout_wrapped_flask_blocked(self):
        """`timeout 60 flask run --host 0.0.0.0` — bare-number duration skipped."""
        assert _run_main(_make_bash_event("timeout 60 flask run --host 0.0.0.0")) == 2

    def test_timeout_signal_flag_wrapped_server_blocked(self):
        """`timeout -s KILL 30 vite --host 0.0.0.0` — `-s KILL` value flag then the
        duration are both skipped → BLOCK."""
        assert _run_main(_make_bash_event("timeout -s KILL 30 vite --host 0.0.0.0")) == 2

    def test_timeout_wrapped_python_flask_blocked(self):
        """`timeout 30s python3 -m flask run --host 0.0.0.0` → BLOCK."""
        assert _run_main(_make_bash_event("timeout 30s python3 -m flask run --host 0.0.0.0")) == 2

    def test_timeout_wrapped_non_server_allowed(self):
        """`timeout 30s npm run build` — wrapped non-server build → ALLOW."""
        assert _run_main(_make_bash_event("timeout 30s npm run build")) == 0

    def test_timeout_wrapped_loopback_allowed(self):
        """`timeout 30s vite --host 127.0.0.1` — loopback bind still allowed."""
        assert _run_main(_make_bash_event("timeout 30s vite --host 127.0.0.1")) == 0

    # --- PR #719 codex round-12: npx package@version forms (common npx/dlx usage) ---

    def test_npx_versioned_package_server_blocked(self):
        """`npx vite@latest --host 0.0.0.0` — the `@version` suffix is stripped so
        vite is recognized as the server (codex round-12, common npx form)."""
        assert _run_main(_make_bash_event("npx vite@latest --host 0.0.0.0")) == 2

    def test_pnpm_dlx_versioned_http_server_blocked(self):
        """`pnpm dlx http-server@14 -a 0.0.0.0` — versioned http-server → BLOCK."""
        assert _run_main(_make_bash_event("pnpm dlx http-server@14 -a 0.0.0.0")) == 2

    def test_npx_versioned_non_server_allowed(self):
        """`npx eslint@8 .` — versioned non-server tool → ALLOW (no false positive)."""
        assert _run_main(_make_bash_event("npx eslint@8 .")) == 0

    # --- PR #719 codex round-13: shell `-c` launchers (bash/sh/zsh) recurse into payload ---

    def test_bash_c_vite_blocked(self):
        """`bash -lc 'vite --host 0.0.0.0'` — the `-c` payload is the real command;
        recurse into it so vite is caught (codex round-13, common CI wrapper)."""
        assert _run_main(_make_bash_event("bash -lc 'vite --host 0.0.0.0'")) == 2

    def test_sh_c_php_blocked(self):
        """`sh -c 'php -S 0.0.0.0:8000'` → BLOCK via payload recursion."""
        assert _run_main(_make_bash_event("sh -c 'php -S 0.0.0.0:8000'")) == 2

    def test_bash_c_flask_blocked(self):
        """`bash -c 'flask run --host 0.0.0.0'` → BLOCK."""
        assert _run_main(_make_bash_event("bash -c 'flask run --host 0.0.0.0'")) == 2

    def test_bash_c_chained_payload_blocked(self):
        """`bash -c 'cd /app && vite --host 0.0.0.0'` — chained payload, server
        segment still caught."""
        assert _run_main(_make_bash_event("bash -c 'cd /app && vite --host 0.0.0.0'")) == 2

    def test_bash_c_build_payload_allowed(self):
        """`bash -c 'npm run build'` — non-server payload → ALLOW."""
        assert _run_main(_make_bash_event("bash -c 'npm run build'")) == 0

    def test_bash_c_display_payload_allowed(self):
        """`bash -lc 'echo vite --host 0.0.0.0'` — payload is a display command → ALLOW."""
        assert _run_main(_make_bash_event("bash -lc 'echo vite --host 0.0.0.0'")) == 0

    # --- PR #719 codex round-14: wrapper + shell-launcher composition ---

    def test_env_wrapped_bash_c_blocked(self):
        """`env -i bash -c 'vite --host 0.0.0.0'` — bash is an executable token, so
        env's `-i` must not eat it; the shell launcher then recurses (codex r14)."""
        assert _run_main(_make_bash_event("env -i bash -c 'vite --host 0.0.0.0'")) == 2

    def test_time_wrapped_sh_c_blocked(self):
        """`time -p sh -c 'php -S 0.0.0.0:8000'` → BLOCK (wrapper + shell launcher)."""
        assert _run_main(_make_bash_event("time -p sh -c 'php -S 0.0.0.0:8000'")) == 2

    def test_sudo_wrapped_bash_c_blocked(self):
        """`sudo -u me bash -c 'vite --host 0.0.0.0'` → BLOCK."""
        assert _run_main(_make_bash_event("sudo -u me bash -c 'vite --host 0.0.0.0'")) == 2

    def test_env_wrapped_bash_c_non_server_allowed(self):
        """`env -i bash -c 'npm run build'` — wrapped shell launcher, non-server → ALLOW."""
        assert _run_main(_make_bash_event("env -i bash -c 'npm run build'")) == 0

    # --- bypass ---

    def test_bypass_allows_public_server(self):
        """PUBLIC_SERVER_GUARD_BYPASS=1 allows the blocked command through."""
        payload = _make_bash_event("python3 -m http.server 8080")
        assert _run_main(payload, env={"PUBLIC_SERVER_GUARD_BYPASS": "1"}) == 0
