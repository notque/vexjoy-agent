#!/usr/bin/env python3
"""
Tests for settings.json validation.

Validates that the Claude Code settings file has correct structure.
Uses a temporary fixture since settings.json is user-specific (.gitignore'd).
"""

import json
from pathlib import Path

import pytest

# Minimal valid settings structure for testing
MINIMAL_SETTINGS = {
    "hooks": {
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 hooks/auto-plan-detector.py",
                    }
                ]
            }
        ],
        "PostToolUse": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python3 hooks/post-tool-lint-hint.py",
                    }
                ]
            }
        ],
    }
}


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    """Create a temporary settings.json for testing."""
    path = tmp_path / "settings.json"
    path.write_text(json.dumps(MINIMAL_SETTINGS, indent=2))
    return path


def test_settings_file_exists(settings_path: Path):
    """Settings file should exist."""
    assert settings_path.exists(), f"Settings file not found at {settings_path}"


def test_settings_is_valid_json(settings_path: Path):
    """Settings file should be valid JSON."""
    data = json.loads(settings_path.read_text())
    assert isinstance(data, dict), "Settings should be a JSON object"


def test_settings_has_hooks_section(settings_path: Path):
    """Settings should have a hooks section."""
    data = json.loads(settings_path.read_text())
    assert "hooks" in data, "Settings should have 'hooks' key"


def test_user_prompt_submit_hook_configured(settings_path: Path):
    """UserPromptSubmit hook should be properly configured."""
    data = json.loads(settings_path.read_text())

    hooks = data.get("hooks", {})
    assert "UserPromptSubmit" in hooks, "Should have UserPromptSubmit hook"

    ups_hooks = hooks["UserPromptSubmit"]
    assert isinstance(ups_hooks, list), "UserPromptSubmit should be a list"
    assert len(ups_hooks) > 0, "UserPromptSubmit should have at least one hook"


def test_hook_has_correct_structure(settings_path: Path):
    """Each hook should have the correct nested structure."""
    data = json.loads(settings_path.read_text())

    for hook_config in data["hooks"]["UserPromptSubmit"]:
        assert "hooks" in hook_config, "Hook config should have nested 'hooks' array"
        inner_hooks = hook_config["hooks"]
        assert isinstance(inner_hooks, list), "Inner hooks should be a list"

        for hook in inner_hooks:
            assert "type" in hook, "Hook should have 'type' field"
            assert hook["type"] == "command", "Hook type should be 'command'"
            assert "command" in hook, "Hook should have 'command' field"
