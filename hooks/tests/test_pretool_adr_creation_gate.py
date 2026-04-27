#!/usr/bin/env python3
"""
Tests for the pretool-adr-creation-gate hook.

Run with: python3 -m pytest hooks/tests/test_pretool_adr_creation_gate.py -v
"""

import importlib.util
import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Import the module under test
# ---------------------------------------------------------------------------

HOOK_PATH = Path(__file__).parent.parent / "pretool-adr-creation-gate.py"

spec = importlib.util.spec_from_file_location("pretool_adr_creation_gate", HOOK_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_write_event(file_path: str, cwd: str | None = None) -> str:
    """Build a JSON hook event payload for a Write tool call."""
    payload = {"tool_name": "Write", "tool_input": {"file_path": file_path}}
    if cwd is not None:
        payload["cwd"] = cwd
    return json.dumps(payload)


def _run_main(stdin_payload: str, env: dict | None = None) -> int:
    """Invoke mod.main() and detect deny via stdout JSON.

    Returns 2 if the hook denied, 0 otherwise. Mirrors the helper in
    test_pretool_unified_gate.py so the assertion semantics line up.
    """
    base_env = dict(os.environ)
    base_env.pop("ADR_CREATION_GATE_BYPASS", None)
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
                return 2
        except (json.JSONDecodeError, AttributeError):
            pass
    return 0


# ---------------------------------------------------------------------------
# TestADRCreationGate
# ---------------------------------------------------------------------------


class TestADRCreationGate:
    """The ADR creation gate blocks new components without an ADR, with carve-outs."""

    def test_new_skill_without_adr_blocked(self):
        """A new component without an ADR in adr/ must be blocked."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skills" / "some-new-skill" / "SKILL.md"
            payload = _make_write_event(str(target), cwd=tmp)
            assert _run_main(payload) == 2

    def test_new_skill_with_adr_allowed(self):
        """A new component with adr/<name>.md present must pass through."""
        with tempfile.TemporaryDirectory() as tmp:
            adr_dir = Path(tmp) / "adr"
            adr_dir.mkdir()
            (adr_dir / "some-new-skill.md").write_text("# ADR\n")
            target = Path(tmp) / "skills" / "some-new-skill" / "SKILL.md"
            payload = _make_write_event(str(target), cwd=tmp)
            assert _run_main(payload) == 0

    def test_voice_skill_allowlisted_no_adr_required(self):
        """voice-* skills are produced by create-voice — no per-voice ADR required."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skills" / "voice-feynman" / "SKILL.md"
            payload = _make_write_event(str(target), cwd=tmp)
            # No adr/ directory exists; the allowlist must take precedence.
            assert _run_main(payload) == 0

    def test_voice_skill_allowlist_arbitrary_name(self):
        """Allowlist matches any voice-<name> suffix, not just one example."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skills" / "voice-someone-new" / "SKILL.md"
            payload = _make_write_event(str(target), cwd=tmp)
            assert _run_main(payload) == 0

    def test_non_voice_skill_still_requires_adr(self):
        """Allowlist must not leak: a generic skill name still needs an ADR."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skills" / "voicelike-but-not-voice" / "SKILL.md"
            # The regex requires /skills/voice-<something>/ — "voicelike-..." matches
            # because "voice-" is a prefix of "voicelike-but-not-voice"? No: the regex
            # is /skills/voice-[^/]+/SKILL\.md$, so "voicelike-but-not-voice" does NOT
            # start with "voice-" (it starts with "voicelike-"), so it must be blocked.
            payload = _make_write_event(str(target), cwd=tmp)
            assert _run_main(payload) == 2

    def test_existing_file_passes_as_update(self):
        """Updates to existing files are not creations — pass through."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "skills" / "some-skill"
            skill_dir.mkdir(parents=True)
            target = skill_dir / "SKILL.md"
            target.write_text("# existing\n")
            payload = _make_write_event(str(target), cwd=tmp)
            assert _run_main(payload) == 0

    def test_bypass_env_allows_creation(self):
        """ADR_CREATION_GATE_BYPASS=1 disables the gate entirely."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "skills" / "some-new-skill" / "SKILL.md"
            payload = _make_write_event(str(target), cwd=tmp)
            assert _run_main(payload, env={"ADR_CREATION_GATE_BYPASS": "1"}) == 0

    def test_non_component_path_passes(self):
        """Writes to non-component paths bypass the gate."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "src" / "main.py"
            payload = _make_write_event(str(target), cwd=tmp)
            assert _run_main(payload) == 0

    def test_malformed_json_fails_open(self):
        """Invalid JSON must exit cleanly without blocking."""
        assert _run_main("not valid json {{{") == 0
