#!/usr/bin/env python3
"""Ensure ~/.codex/config.toml contains the codex_hooks feature flag.

Performs a TOML-aware merge: adds [features] and codex_hooks = true if
absent, while preserving all existing sections unchanged. Backs up the
config before writing unless --no-backup is passed.

Exit codes:
  0  success (including already-present)
  1  unexpected error
  2  codex_hooks = false detected; manual resolution required
"""

import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

_FEATURES_HEADER = "[features]"
_KEY_PATTERN = re.compile(r"^\s*codex_hooks\s*=\s*(true|false)\s*$", re.MULTILINE)
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
        SystemExit: With exit code 2 when codex_hooks = false is found.
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
        SystemExit: With exit code 2 when codex_hooks = false is found.
    """
    match = _KEY_PATTERN.search(content)
    if match:
        value = match.group(1)
        if value == "true":
            return False, "already-present"
        print(
            "ERROR: codex_hooks = false found in config. "
            "This appears to be a deliberate user setting. "
            "Edit the file manually to set codex_hooks = true before re-running.",
            file=sys.stderr,
        )
        sys.exit(2)

    has_features_section = bool(_SECTION_PATTERN.search(content))
    if has_features_section:
        return True, "added-key"
    return True, "added-section"


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
        'already-present', 'added-section', 'added-key', 'created-file'.

    Raises:
        SystemExit: With exit code 2 when codex_hooks = false is found.
    """
    if not content:
        return True, "created-file"

    match = _KEY_PATTERN.search(content)
    if match:
        value = match.group(1)
        if value == "true":
            return False, "already-present"
        # value == "false": this is a conscious user choice
        print(
            "ERROR: codex_hooks = false found in config. "
            "This appears to be a deliberate user setting. "
            "Edit the file manually to set codex_hooks = true before re-running.",
            file=sys.stderr,
        )
        sys.exit(2)

    has_features_section = bool(_SECTION_PATTERN.search(content))
    if has_features_section:
        return True, "added-key"
    return True, "added-section"


def apply_update(content: str) -> str:
    """Return the updated config content with codex_hooks = true set.

    Adds [features] if absent, or injects codex_hooks under the existing
    [features] section. Does not modify any other section.

    Args:
        content: The current file content (may be empty).

    Returns:
        Updated TOML content as a string.
    """
    _, action = needs_update(content)

    if action == "already-present":
        return content

    if action in ("created-file", "added-section"):
        # Append a new [features] block. Ensure a trailing newline before it
        # when appending to non-empty content.
        if content and not content.endswith("\n"):
            content += "\n"
        if content:
            content += "\n"
        content += "[features]\ncodex_hooks = true\n"
        return content

    # action == "added-key": insert codex_hooks after the [features] header.
    # Find the line index of [features] and insert after it.
    lines = content.splitlines(keepends=True)
    result: list[str] = []
    injected = False
    for line in lines:
        result.append(line)
        if not injected and line.strip() == "[features]":
            result.append("codex_hooks = true\n")
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
    parser = argparse.ArgumentParser(description="Ensure ~/.codex/config.toml has the codex_hooks feature flag.")
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
