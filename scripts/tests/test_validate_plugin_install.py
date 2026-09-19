"""validate-plugin-install: repo plugin versions must match `claude plugin list`."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("vpi", ROOT / "scripts" / "validate-plugin-install.py")
vpi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vpi)

# The CLI prints U+276F before each plugin name.
LIST_OUT = """Installed plugins:

  \u276f jev-auto-compact@jev-auto-compact
    Version: 1.4.0
    Scope: user

  \u276f other@market
    Version: 2.0.8
"""


def test_parses_cli_list(monkeypatch):
    class P:
        stdout = LIST_OUT

    monkeypatch.setattr(vpi.subprocess, "run", lambda *_a, **_k: P())
    assert vpi.installed_versions() == {"jev-auto-compact": "1.4.0", "other": "2.0.8"}


def test_reports_version_drift_with_cli_fix(monkeypatch, tmp_path):
    monkeypatch.setattr(vpi, "repo_plugins", lambda: {"jev-auto-compact": {"version": "1.5.0", "dir": tmp_path}})
    monkeypatch.setattr(vpi, "installed_versions", lambda: {"jev-auto-compact": "1.4.0"})
    probs = vpi.check()
    assert len(probs) == 1 and "claude plugin update jev-auto-compact@jev-auto-compact" in probs[0]["fix"]


def test_reports_not_installed(monkeypatch, tmp_path):
    monkeypatch.setattr(vpi, "repo_plugins", lambda: {"p": {"version": "1.0.0", "dir": tmp_path}})
    monkeypatch.setattr(vpi, "installed_versions", lambda: {})
    probs = vpi.check()
    assert probs and probs[0]["fix"] == "claude plugin install p@p"


def test_clean_when_versions_match_and_cache_present(monkeypatch, tmp_path):
    (tmp_path / "p" / "p" / "1.0.0" / "hooks").mkdir(parents=True)
    monkeypatch.setattr(vpi, "CACHE", tmp_path)
    monkeypatch.setattr(vpi, "repo_plugins", lambda: {"p": {"version": "1.0.0", "dir": tmp_path}})
    monkeypatch.setattr(vpi, "installed_versions", lambda: {"p": "1.0.0"})
    assert vpi.check() == []
