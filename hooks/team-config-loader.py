#!/usr/bin/env python3
# hook-version: 1.0.0
"""
SessionStart Hook: Team Configuration Loader

Discovers a team-config.yaml file from priority-ordered locations and injects
its contents into the session as context lines.

Priority order:
  1. $CLAUDE_TEAM_CONFIG env var (explicit override)
  2. .claude/team-config.yaml  (project-local)
  3. ~/.claude/team-config.yaml (user-global)
  4. /etc/claude/team-config.yaml (system-wide)

Design Principles:
- SILENT when no config file is found (zero noise for solo users)
- Non-blocking: always exits 0
- Sub-50ms: reads one small YAML file, no DB, no network
- CLAUDE_HOOKS_DEBUG=1 logs errors to stderr
"""

import os
import sys
from pathlib import Path

DEBUG = os.environ.get("CLAUDE_HOOKS_DEBUG") == "1"


def debug(msg: str) -> None:
    if DEBUG:
        print(f"[team-config-loader] {msg}", file=sys.stderr)


def find_config() -> Path | None:
    """Return the first config file found, in priority order."""
    candidates = []

    # 1. Explicit env override
    env_path = os.environ.get("CLAUDE_TEAM_CONFIG")
    if env_path:
        candidates.append(Path(env_path))

    # 2. Project-local
    candidates.append(Path.cwd() / ".claude" / "team-config.yaml")

    # 3. User-global
    candidates.append(Path.home() / ".claude" / "team-config.yaml")

    # 4. System-wide
    candidates.append(Path("/etc/claude/team-config.yaml"))

    for path in candidates:
        if path.is_file():
            debug(f"found config at {path}")
            return path

    return None


def load_yaml(path: Path) -> dict:
    """
    Load YAML from path. Uses PyYAML if available; falls back to simple
    line-by-line parser for basic key: value (and indented block scalar) structure.
    """
    text = path.read_text(encoding="utf-8")

    try:
        import yaml  # pyyaml

        return yaml.safe_load(text) or {}
    except ImportError:
        debug("pyyaml not available, using fallback parser")
        return _fallback_parse(text)


def _fallback_parse(text: str) -> dict:
    """
    Minimal YAML parser for the team-config schema only.
    Handles:
      - top-level scalar keys:  key: value
      - block scalar (|):       context: |
                                   line one
                                   line two
      - simple list:            hints:
                                  - item
      - simple dict:            env:
                                  KEY: value
    Comments (#) and blank lines are skipped.
    """
    result: dict = {}
    lines = text.splitlines()
    i = 0

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # Skip comments and blanks
        if not stripped or stripped.startswith("#"):
            i += 1
            continue

        # Top-level key
        if not raw[0].isspace() and ":" in stripped:
            key, _, rest = stripped.partition(":")
            key = key.strip()
            rest = rest.strip()

            if rest == "|":
                # Block scalar — collect indented lines that follow
                i += 1
                block_lines = []
                while i < len(lines):
                    next_raw = lines[i]
                    if next_raw and not next_raw[0].isspace():
                        break
                    block_lines.append(next_raw.strip())
                    i += 1
                result[key] = "\n".join(block_lines).strip()
                continue

            if rest == "":
                # Mapping or sequence — peek at children
                i += 1
                children_raw = []
                while i < len(lines):
                    next_raw = lines[i]
                    next_stripped = next_raw.strip()
                    if not next_stripped or next_stripped.startswith("#"):
                        i += 1
                        continue
                    if next_raw and not next_raw[0].isspace():
                        break
                    children_raw.append(next_stripped)
                    i += 1

                if children_raw and children_raw[0].startswith("- "):
                    result[key] = [c[2:].strip() for c in children_raw if c.startswith("- ")]
                else:
                    mapping = {}
                    for child in children_raw:
                        if ":" in child:
                            ck, _, cv = child.partition(":")
                            mapping[ck.strip()] = cv.strip()
                    result[key] = mapping
                continue

            # Inline scalar
            result[key] = rest
            i += 1
            continue

        i += 1

    return result


def inject_config(config: dict, config_path: Path) -> None:
    """Print context lines from the loaded config to stdout."""
    version = config.get("version")
    # Fallback parser returns strings; PyYAML returns int. Accept both.
    if str(version) != "1":
        debug(f"unsupported config version: {version!r}")
        return

    team = config.get("team", "")
    operator = config.get("operator", "")

    # Header line
    label = f" for team: {team}" if team else ""
    print(f"[team-config] Loaded {config_path.name}{label}")

    if operator:
        print(f"[team-config] Operator: {operator}")

    # Free-form context block
    context = config.get("context", "")
    if context:
        for line in str(context).splitlines():
            stripped = line.strip()
            if stripped:
                print(f"[team-config] {stripped}")

    # Hints
    hints = config.get("hints") or []
    if isinstance(hints, list):
        for hint in hints:
            if hint:
                print(f"[team-hint] {hint}")

    # Env vars
    env = config.get("env") or {}
    if isinstance(env, dict):
        for key, value in env.items():
            print(f"[team-config] Env: {key}={value}")


def main() -> None:
    try:
        config_path = find_config()
        if config_path is None:
            return  # Silent — no config found

        config = load_yaml(config_path)
        inject_config(config, config_path)

    except Exception as e:
        debug(f"error loading team config: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if DEBUG:
            print(f"[team-config-loader] fatal: {e}", file=sys.stderr)
    finally:
        sys.exit(0)
