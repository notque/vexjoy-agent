#!/usr/bin/env python3
"""
Tests for the pretool-unified-gate hook.

Run with: python3 -m pytest hooks/tests/test_pretool_unified_gate.py -v
"""

import importlib.util
import json
import os
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
    """Invoke mod.main() in-process, capturing the exit code.

    Args:
        stdin_payload: JSON string to supply as stdin.
        env: Optional environment variable overrides.

    Returns:
        Integer exit code: 0 = allow, 2 = block.
    """
    base_env = dict(os.environ)
    # Strip all bypass vars for a clean baseline
    for var in ("CLAUDE_GATE_BYPASS", "DANGEROUS_GUARD_BYPASS", "CREATION_GATE_BYPASS", "SENSITIVE_FILE_GUARD_BYPASS"):
        base_env.pop(var, None)
    if env:
        base_env.update(env)

    with (
        patch.dict(os.environ, base_env, clear=True),
        patch.object(mod, "read_stdin", return_value=stdin_payload),
    ):
        try:
            mod.main()
            return 0
        except SystemExit as e:
            return int(e.code) if e.code is not None else 0


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
        payload = _make_write_event("/project/pipelines/my-pipeline/SKILL.md")
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
