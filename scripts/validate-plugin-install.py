#!/usr/bin/env python3
"""Verify every repo plugin is installed at its current version via the Claude CLI.

Rule (learned the hard way): a plugin is installed ONLY by
    claude plugin install <name>@<marketplace>    (first time)
    claude plugin update  <name>@<marketplace>    (after a version bump)
Never hand-edit ~/.claude/plugins/installed_plugins.json or copy files into
~/.claude/plugins/cache/. The engine ignores hand edits and keeps running the
old cached module -- an every-turn compaction bug shipped that way once.
Function-hook plugins load at session start, so an update also needs a restart.

Checks, for each plugins/<name>/.claude-plugin/plugin.json:
  1. the plugin is known to `claude plugin list` (installed via CLI)
  2. the installed version equals the repo manifest version
  3. the cache dir for that version exists and holds the hooks module
Exit 1 with the exact command to run on any drift. Use --json for machines.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CACHE = Path.home() / ".claude" / "plugins" / "cache"


def repo_plugins() -> dict[str, dict]:
    out = {}
    for manifest in sorted(REPO.glob("plugins/*/.claude-plugin/plugin.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = data.get("name") or manifest.parents[1].name
        out[name] = {"version": str(data.get("version", "")), "dir": manifest.parents[1]}
    return out


def installed_versions() -> dict[str, str]:
    """Parse `claude plugin list`; returns {name: version}. Empty if the CLI is unavailable."""
    try:
        proc = subprocess.run(["claude", "plugin", "list"], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    versions: dict[str, str] = {}
    current = None
    for line in proc.stdout.splitlines():
        m = re.match(r"\s*[\u276f>*-]?\s*([A-Za-z0-9_.-]+)@([A-Za-z0-9_.-]+)\s*$", line)
        if m:
            current = m.group(1)
            continue
        m = re.match(r"\s*Version:\s*(\S+)", line)
        if m and current:
            versions[current] = m.group(1)
            current = None
    return versions


def check() -> list[dict]:
    plugins = repo_plugins()
    installed = installed_versions()
    problems = []
    for name, info in plugins.items():
        want = info["version"]
        have = installed.get(name)
        marketplace = name  # repo plugins register a directory marketplace under their own name
        if have is None:
            problems.append(
                {
                    "plugin": name,
                    "problem": "not installed via CLI",
                    "fix": f"claude plugin install {name}@{marketplace}",
                }
            )
            continue
        if have != want:
            problems.append(
                {
                    "plugin": name,
                    "problem": f"installed {have}, repo {want}",
                    "fix": f"claude plugin update {name}@{marketplace}  # then restart",
                }
            )
            continue
        cache_dir = CACHE / name / name / want
        if not (cache_dir / "hooks").is_dir():
            problems.append(
                {
                    "plugin": name,
                    "problem": f"cache dir missing: {cache_dir}",
                    "fix": f"claude plugin update {name}@{marketplace}",
                }
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    problems = check()
    if args.json:
        print(json.dumps({"ok": not problems, "problems": problems}, indent=1))
    elif problems:
        print("plugin-install: DRIFT")
        for p in problems:
            print(f"  {p['plugin']}: {p['problem']}\n    fix: {p['fix']}")
    else:
        print("plugin-install: all repo plugins installed at their manifest version via the CLI")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
