#!/usr/bin/env python3
"""Ensure ~/.codex/config.toml contains the hooks feature flag.

Performs a TOML-aware merge: adds [features] and hooks = true if absent,
while preserving all existing sections unchanged. Backs up the config
before writing unless --no-backup is passed.

Codex CLI renamed this flag from codex_hooks to hooks (codex_hooks now
prints a deprecation warning). This script writes the new hooks key and
removes any deprecated codex_hooks line it finds, migrating old configs.

Exit codes:
  0  success (including already-present)
  1  unexpected error
  2  hooks = false detected; manual resolution required
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

_FEATURES_HEADER = "[features]"
# Match the current key. ^\s*hooks does not match "codex_hooks" because that
# line begins with "codex_", so the deprecated key is handled separately.
_KEY_PATTERN = re.compile(r"^\s*hooks\s*=\s*(true|false)\s*$", re.MULTILINE)
# Match the deprecated key so we can strip it during migration.
_DEPRECATED_KEY_PATTERN = re.compile(r"^[ \t]*codex_hooks\s*=\s*(true|false)\s*$\n?", re.MULTILINE)
_SECTION_PATTERN = re.compile(r"^\[features\]", re.MULTILINE)


_MISSING = object()  # Sentinel: file did not exist at read time.


def read_config(path: Path) -> str:
    """Read the config file and return its text content.

    Returns an empty string if the file exists but is empty.
    Returns the sentinel value _MISSING (not a string) when the file is absent.
    Callers should treat any falsy str result as "file present, empty content".

    Args:
        path: Absolute path to the TOML config file.

    Returns:
        File content as a string, or empty string if the file is missing or empty.

    Note:
        Use ``needs_update`` directly when you need to distinguish
        "file absent" from "file present but empty". ``read_config`` is a
        convenience wrapper for callers that only need the text.
    """
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _classify_content(content: str, file_exists: bool) -> tuple[bool, str]:
    """Internal classification that takes file-existence into account.

    Args:
        content: The file text (empty string when file is absent or empty).
        file_exists: True when the file exists on disk (even if empty).

    Returns:
        A tuple of (needs_write, action_tag).

    Raises:
        SystemExit: With exit code 2 when hooks (or deprecated codex_hooks) is false.
    """
    if not file_exists:
        return True, "created-file"

    # File exists (possibly empty): fall through to section analysis.
    return _analyse_content(content)


def _analyse_content(content: str) -> tuple[bool, str]:
    """Classify content that belongs to a file that already exists.

    Args:
        content: File text. May be empty.

    Returns:
        A tuple of (needs_write, action_tag).

    Raises:
        SystemExit: With exit code 2 when hooks (or deprecated codex_hooks) is false.
    """
    new_match = _KEY_PATTERN.search(content)
    dep_match = _DEPRECATED_KEY_PATTERN.search(content)
    has_deprecated = dep_match is not None

    if new_match:
        if new_match.group(1) == "false":
            _exit_on_disabled()
        # hooks = true. Still rewrite when a deprecated codex_hooks line is
        # present so we can strip it and clear the deprecation warning.
        if has_deprecated:
            return True, "migrated"
        return False, "already-present"

    # No new key. A deprecated codex_hooks = false is a deliberate disable.
    if dep_match:
        if dep_match.group(1) == "false":
            _exit_on_disabled()
        return True, "migrated"

    has_features_section = bool(_SECTION_PATTERN.search(content))
    if has_features_section:
        return True, "added-key"
    return True, "added-section"


def _exit_on_disabled() -> None:
    """Print guidance and exit 2 when the hooks flag is explicitly disabled."""
    print(
        "ERROR: hooks = false (or deprecated codex_hooks = false) found in config. "
        "This appears to be a deliberate user setting. "
        "Edit the file manually to set hooks = true before re-running.",
        file=sys.stderr,
    )
    sys.exit(2)


def needs_update(content: str) -> tuple[bool, str]:
    """Determine whether the config needs to be updated and which action to take.

    This function treats empty ``content`` as "file does not exist" for
    backward compatibility. For precise file-existence handling, the CLI
    uses ``_classify_content`` directly.

    Args:
        content: The current file content. Pass empty string to represent a
            missing file.

    Returns:
        A tuple of (needs_write, action_tag) where action_tag is one of:
        'already-present', 'added-section', 'added-key', 'created-file',
        'migrated'.

    Raises:
        SystemExit: With exit code 2 when hooks (or deprecated codex_hooks) is false.
    """
    if not content:
        return True, "created-file"
    return _analyse_content(content)


def _strip_deprecated(content: str) -> str:
    """Remove any deprecated codex_hooks line from the content."""
    return _DEPRECATED_KEY_PATTERN.sub("", content)


def apply_update(content: str) -> str:
    """Return the updated config content with hooks = true set.

    Adds [features] if absent, or injects hooks under the existing [features]
    section. Removes any deprecated codex_hooks line. Does not modify any
    other section.

    Args:
        content: The current file content (may be empty).

    Returns:
        Updated TOML content as a string.
    """
    _, action = needs_update(content)

    if action == "already-present":
        return content

    if action == "migrated":
        # Drop the deprecated key. If hooks = true was not already present,
        # insert the current key below [features].
        content = _strip_deprecated(content)
        if _KEY_PATTERN.search(content):
            return content

    if action in ("created-file", "added-section"):
        # Append a new [features] block. Ensure a trailing newline before it
        # when appending to non-empty content.
        if content and not content.endswith("\n"):
            content += "\n"
        if content:
            content += "\n"
        content += "[features]\nhooks = true\n"
        return content

    # action == "added-key" or migrated-without-hooks: strip any deprecated key,
    # then insert hooks after the [features] header.
    content = _strip_deprecated(content)
    lines = content.splitlines(keepends=True)
    result: list[str] = []
    injected = False
    for line in lines:
        result.append(line)
        if not injected and line.strip() == "[features]":
            result.append("hooks = true\n")
            injected = True
    return "".join(result)


def _write_with_backup(path: Path, new_content: str, backup: bool) -> None:
    """Write new_content to path, optionally backing up the existing file.

    Args:
        path: Destination path for the updated config.
        new_content: Content to write.
        backup: When True, copy the existing file to a timestamped .bak file.
    """
    if path.exists() and backup:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak_path = path.with_suffix(f".toml.bak.{stamp}")
        bak_path.write_bytes(path.read_bytes())

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(new_content, encoding="utf-8")


def main() -> None:
    """Parse arguments, determine required action, and update the config file."""
    parser = argparse.ArgumentParser(description="Ensure ~/.codex/config.toml has the hooks feature flag.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path.home() / ".codex" / "config.toml",
        help="Path to config.toml (default: ~/.codex/config.toml)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the would-be new content without modifying the file.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating a backup of the existing config before writing.",
    )
    args = parser.parse_args()

    config_path: Path = args.config
    file_exists = config_path.exists()
    content = read_config(config_path)
    # Use _classify_content so that an empty-but-existing file maps to
    # "added-section" rather than "created-file".
    write_needed, action = _classify_content(content, file_exists)

    if not write_needed:
        print(action)
        return

    new_content = apply_update(content)

    if args.dry_run:
        print(new_content, end="")
        return

    _write_with_backup(config_path, new_content, backup=not args.no_backup)
    print(action)


if __name__ == "__main__":
    main()
