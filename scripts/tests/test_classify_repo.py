"""Tests for classify-repo.py domain detection and repo classification."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Import the hyphenated module using importlib
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
classify_repo = importlib.import_module("classify-repo")

classify_repo_fn = classify_repo.classify_repo
detect_domain = classify_repo.detect_domain


# --- classify_repo tests ---


class TestClassifyRepo:
    """Tests for the existing classify_repo function."""

    def test_no_remote_url(self):
        result = classify_repo_fn(None)
        assert result["type"] == "unknown"
        assert result["org"] is None

    def test_github_ssh_url(self):
        result = classify_repo_fn("git@github.com:someuser/somerepo.git")
        assert result["type"] == "personal"
        assert result["org"] == "someuser"

    def test_github_https_url(self):
        result = classify_repo_fn("https://github.com/someuser/somerepo.git")
        assert result["type"] == "personal"
        assert result["org"] == "someuser"

    def test_non_github_remote(self):
        result = classify_repo_fn("https://gitlab.com/someuser/somerepo.git")
        assert result["type"] == "personal"
        assert result["org"] is None

    def test_protected_org(self, monkeypatch):
        monkeypatch.setenv("PROTECTED_ORGS", "acme-corp")
        result = classify_repo_fn("git@github.com:acme-corp/somerepo.git")
        assert result["type"] == "protected-org"
        assert result["org"] == "acme-corp"


# --- detect_domain tests ---


class TestDetectDomain:
    """Tests for domain detection using tmp_path fixtures."""

    def test_go_repo(self, tmp_path):
        (tmp_path / "go.mod").write_text("module example.com/foo")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "go"
        assert result["is_toolkit"] is False

    def test_typescript_repo(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        (tmp_path / "tsconfig.json").write_text("{}")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "typescript"
        assert result["is_toolkit"] is False

    def test_javascript_repo(self, tmp_path):
        (tmp_path / "package.json").write_text("{}")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "javascript"
        assert result["is_toolkit"] is False

    def test_python_repo_pyproject(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "python"
        assert result["is_toolkit"] is False

    def test_python_repo_setup_py(self, tmp_path):
        (tmp_path / "setup.py").write_text("from setuptools import setup")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "python"
        assert result["is_toolkit"] is False

    def test_hugo_repo_hugo_toml(self, tmp_path):
        (tmp_path / "hugo.toml").write_text("baseURL = 'https://example.com'")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "hugo"
        assert result["is_toolkit"] is False

    def test_hugo_repo_hugo_yaml(self, tmp_path):
        (tmp_path / "hugo.yaml").write_text("baseURL: https://example.com")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "hugo"
        assert result["is_toolkit"] is False

    def test_hugo_repo_config_toml_with_content(self, tmp_path):
        (tmp_path / "config.toml").write_text("baseURL = 'https://example.com'")
        (tmp_path / "content").mkdir()
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "hugo"
        assert result["is_toolkit"] is False

    def test_config_toml_without_content_dir_is_general(self, tmp_path):
        """config.toml alone (no content/ dir) should NOT classify as hugo."""
        (tmp_path / "config.toml").write_text("something = true")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "general"

    def test_general_repo(self, tmp_path):
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "general"
        assert result["is_toolkit"] is False

    def test_toolkit_detection(self, tmp_path):
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "INDEX.json").write_text("{}")
        result = detect_domain(root=tmp_path)
        assert result["is_toolkit"] is True
        assert result["domain"] == "general"

    def test_toolkit_with_domain(self, tmp_path):
        """A toolkit repo that also has a go.mod should report both."""
        (tmp_path / "skills").mkdir()
        (tmp_path / "skills" / "INDEX.json").write_text("{}")
        (tmp_path / "go.mod").write_text("module example.com/foo")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "go"
        assert result["is_toolkit"] is True

    def test_none_root_without_git(self, monkeypatch):
        """When root is None and git root fails, return general."""
        # Ensure _get_git_root returns None
        monkeypatch.setattr(
            classify_repo, "_get_git_root", lambda: None
        )
        result = detect_domain(root=None)
        assert result["domain"] == "general"
        assert result["is_toolkit"] is False

    def test_priority_go_over_python(self, tmp_path):
        """Go takes priority when both go.mod and pyproject.toml exist."""
        (tmp_path / "go.mod").write_text("module example.com/foo")
        (tmp_path / "pyproject.toml").write_text("[project]")
        result = detect_domain(root=tmp_path)
        assert result["domain"] == "go"
