#!/usr/bin/env python3
"""
Threat Surface Scanner — Phase 1 of the security-threat-model skill.

Enumerates the active attack surface of the current toolkit installation:
- Registered hooks (from ~/.claude/settings.json)
- Installed MCP servers (from ~/.claude/mcp.json and .mcp.json)
- Installed skills (from skills/) with allowed-tools entries
- Files in hooks/, skills/, agents/ containing ANTHROPIC_BASE_URL
- Files in hooks/, skills/ with unscoped allowed-tools (Read(*) or Write(*))

Output: security/surface-report.json

Usage:
    python3 scripts/scan-threat-surface.py --output security/surface-report.json
    python3 scripts/scan-threat-surface.py --output security/surface-report.json --verbose
    python3 scripts/scan-threat-surface.py --help
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ─── Patterns ──────────────────────────────────────────────────

_BASE_URL_PATTERN = re.compile(r"ANTHROPIC_BASE_URL", re.IGNORECASE)
_UNSCOPED_TOOL_PATTERN = re.compile(r"\b(Read|Write)\(\s*\*\s*\)")
_CURL_WGET_PATTERN = re.compile(r"\b(curl|wget)\b")
_SSH_SCP_PATTERN = re.compile(r"\b(ssh|scp)\b")
_NC_PATTERN = re.compile(r"\bnc\b")


# ─── Helpers ───────────────────────────────────────────────────


def _load_json_file(path: Path) -> dict | None:
    """Load JSON from a file, returning None on any error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _scan_hooks_config(settings_path: Path, verbose: bool) -> list[dict]:
    """Parse registered hooks from ~/.claude/settings.json."""
    hooks = []
    data = _load_json_file(settings_path)
    if not data:
        if verbose:
            print(f"  [surface] No settings.json at {settings_path}", file=sys.stderr)
        return hooks

    raw_hooks = data.get("hooks", {})
    for event_type, hook_list in raw_hooks.items():
        if not isinstance(hook_list, list):
            hook_list = [hook_list]
        for entry in hook_list:
            if isinstance(entry, dict):
                hooks.append(
                    {
                        "event_type": event_type,
                        "command": entry.get("command", ""),
                        "timeout": entry.get("timeout"),
                        "source": str(settings_path),
                    }
                )
            elif isinstance(entry, str):
                hooks.append(
                    {
                        "event_type": event_type,
                        "command": entry,
                        "timeout": None,
                        "source": str(settings_path),
                    }
                )
    return hooks


def _scan_mcp_config(mcp_path: Path, verbose: bool) -> list[dict]:
    """Parse MCP servers from an mcp.json file."""
    servers = []
    data = _load_json_file(mcp_path)
    if not data:
        return servers

    # Handle both {"mcpServers": {...}} and flat {"name": {...}} formats
    raw = data.get("mcpServers", data)
    if not isinstance(raw, dict):
        return servers

    for name, cfg in raw.items():
        if not isinstance(cfg, dict):
            continue
        servers.append(
            {
                "name": name,
                "command": cfg.get("command", ""),
                "args": cfg.get("args", []),
                "env": list(cfg.get("env", {}).keys()),
                "source": str(mcp_path),
            }
        )
    return servers


def _scan_skill_frontmatter(skill_file: Path, verbose: bool) -> dict | None:
    """Extract name and allowed-tools from a SKILL.md YAML frontmatter."""
    try:
        text = skill_file.read_text(encoding="utf-8")
    except Exception:
        return None

    if not text.startswith("---"):
        return None

    end = text.find("---", 3)
    if end == -1:
        return None

    frontmatter = text[3:end]
    name = None
    allowed_tools = []
    unscoped = False
    in_allowed_tools = False

    for line in frontmatter.splitlines():
        stripped = line.strip()
        # Detect the allowed-tools: key
        if stripped.startswith("allowed-tools:") and not stripped.startswith("- "):
            in_allowed_tools = True
            continue
        # Another YAML key at the same indentation level ends the block
        if stripped and not stripped.startswith("- ") and ":" in stripped and in_allowed_tools:
            in_allowed_tools = False
        # End of frontmatter resets state
        if stripped == "---":
            in_allowed_tools = False
        if stripped.startswith("name:"):
            name = stripped[5:].strip().strip('"').strip("'")
        if stripped.startswith("- ") and in_allowed_tools:
            tool = stripped[2:].strip()
            allowed_tools.append(tool)
            if _UNSCOPED_TOOL_PATTERN.search(tool):
                unscoped = True

    # Also check for inline allowed-tools list on same line
    at_match = re.search(r"allowed-tools\s*:\s*\[([^\]]+)\]", frontmatter)
    if at_match:
        for tool in at_match.group(1).split(","):
            t = tool.strip().strip('"').strip("'")
            allowed_tools.append(t)
            if _UNSCOPED_TOOL_PATTERN.search(t):
                unscoped = True

    return {
        "name": name or skill_file.parent.name,
        "file": str(skill_file),
        "allowed_tools": allowed_tools,
        "has_unscoped_tools": unscoped,
    }


def _scan_files_for_pattern(dirs: list[Path], pattern: re.Pattern, label: str, verbose: bool) -> list[dict]:
    """Scan files in dirs for a regex pattern. Returns list of matches."""
    findings = []
    extensions = {".py", ".md", ".json", ".yaml", ".yml"}

    for base_dir in dirs:
        if not base_dir.exists():
            continue
        for fpath in base_dir.rglob("*"):
            if not fpath.is_file():
                continue
            if fpath.suffix not in extensions:
                continue
            try:
                text = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    findings.append(
                        {
                            "file": str(fpath),
                            "line": lineno,
                            "content": line.strip()[:120],
                            "label": label,
                        }
                    )
                    break  # one finding per file per pattern
    return findings


# ─── Main ──────────────────────────────────────────────────────


def build_report(repo_root: Path, verbose: bool) -> dict:
    run_id = str(uuid.uuid4())[:8]
    scanned_at = datetime.now(timezone.utc).isoformat()

    report: dict = {
        "run_id": run_id,
        "scanned_at": scanned_at,
        "repo_root": str(repo_root),
        "hooks": [],
        "mcp_servers": [],
        "skills": [],
        "base_url_findings": [],
        "unscoped_tool_findings": [],
        "env_vars": {},
    }

    # 1. Registered hooks from ~/.claude/settings.json
    settings_path = Path.home() / ".claude" / "settings.json"
    if settings_path.exists():
        report["hooks"] = _scan_hooks_config(settings_path, verbose)
        if verbose:
            print(f"  [surface] hooks from {settings_path}: {len(report['hooks'])}", file=sys.stderr)

    # 2. MCP servers
    mcp_paths = [
        Path.home() / ".claude" / "mcp.json",
        repo_root / ".mcp.json",
    ]
    for mp in mcp_paths:
        if mp.exists():
            servers = _scan_mcp_config(mp, verbose)
            report["mcp_servers"].extend(servers)
            if verbose:
                print(f"  [surface] MCP servers from {mp}: {len(servers)}", file=sys.stderr)

    # 3. Skills from local skills/
    skills_dir = repo_root / "skills"
    if skills_dir.exists():
        for skill_dir in sorted(skills_dir.iterdir()):
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                info = _scan_skill_frontmatter(skill_file, verbose)
                if info:
                    report["skills"].append(info)
    if verbose:
        print(f"  [surface] skills scanned: {len(report['skills'])}", file=sys.stderr)

    # 4. ANTHROPIC_BASE_URL in hooks/, skills/, agents/
    scan_dirs = [repo_root / d for d in ("hooks", "skills", "agents")]
    report["base_url_findings"] = _scan_files_for_pattern(scan_dirs, _BASE_URL_PATTERN, "ANTHROPIC_BASE_URL", verbose)
    if verbose:
        print(f"  [surface] ANTHROPIC_BASE_URL findings: {len(report['base_url_findings'])}", file=sys.stderr)

    # 5. Unscoped allowed-tools (already captured in skills scan above, but also
    #    scan hooks/ for broad patterns)
    hooks_dir = repo_root / "hooks"
    if hooks_dir.exists():
        for hook_file in sorted(hooks_dir.glob("*.py")):
            try:
                text = hook_file.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if _UNSCOPED_TOOL_PATTERN.search(line):
                    report["unscoped_tool_findings"].append(
                        {
                            "file": str(hook_file),
                            "line": lineno,
                            "content": line.strip()[:120],
                        }
                    )
                    break

    # 6. Relevant env vars
    interesting_vars = [
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_KEY",
        "CLAUDE_PROJECT_DIR",
        "CLAUDE_LEARNING_DIR",
    ]
    for var in interesting_vars:
        val = os.environ.get(var)
        if val:
            # Mask secrets
            if "KEY" in var or "SECRET" in var or "TOKEN" in var:
                report["env_vars"][var] = "***REDACTED***"
            else:
                report["env_vars"][var] = val
        else:
            report["env_vars"][var] = None

    # Capture any *_TOKEN or *_KEY vars (masked)
    for key, val in os.environ.items():
        if (key.endswith("_TOKEN") or key.endswith("_KEY")) and key not in report["env_vars"]:
            report["env_vars"][key] = "***REDACTED***"

    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan toolkit installation for threat surface exposure.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--output",
        default="security/surface-report.json",
        help="Output path for surface-report.json (default: security/surface-report.json)",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Root of the toolkit repo to scan (default: current directory)",
    )
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.verbose:
        print(f"[surface] Scanning {repo_root}", file=sys.stderr)

    report = build_report(repo_root, args.verbose)

    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # Summary to stderr
    print(
        f"[surface] hooks={len(report['hooks'])} mcp_servers={len(report['mcp_servers'])} "
        f"skills={len(report['skills'])} base_url_findings={len(report['base_url_findings'])} "
        f"run_id={report['run_id']}",
        file=sys.stderr,
    )
    print(f"[surface] Written to {output_path}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"[surface] FATAL: {e}", file=sys.stderr)
        sys.exit(1)
