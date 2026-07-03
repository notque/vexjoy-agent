"""Shared YAML frontmatter parsing for markdown-based agent/skill/doc files.

Every component in this repo (agents, skills, docs) starts with a
``---\\n ... \\n---`` YAML frontmatter block. Roughly a dozen scripts used to
hand-roll extraction of that block -- some with ad hoc regexes, some with
line-by-line ``key: value`` splitters that silently mishandle YAML block
scalars (``description: |`` or ``description: >``). This module is the
single, PyYAML-backed implementation those scripts share.

Callers with bespoke regex-fallback behavior for malformed frontmatter
(complex descriptions with unquoted colons, etc.) can use
:func:`extract_frontmatter_block` to get the raw YAML text and layer their
own fallback on top; callers that just want "parsed dict + body" should use
:func:`parse_frontmatter`.
"""

from __future__ import annotations

import re
from typing import Any

import yaml

#: Matches a leading ``---\n ... \n---`` frontmatter block. Does not require
#: a trailing newline after the closing marker, and does not anchor the end
#: of the document -- callers that need CRLF tolerance or a stricter
#: closing-marker requirement should match against their own pattern.
FRONTMATTER_PATTERN = re.compile(r"^---\n(.*?)\n---", re.DOTALL)


def extract_frontmatter_block(text: str) -> str | None:
    """Return the raw YAML text between the frontmatter ``---`` markers.

    Args:
        text: Full file content, starting at the top of the file.

    Returns:
        The raw YAML block (with the ``---`` markers stripped), or None if
        the file does not open with a frontmatter block.
    """
    match = FRONTMATTER_PATTERN.match(text)
    return match.group(1) if match else None


def load_yaml_mapping(yaml_text: str) -> dict[str, Any] | None:
    """Parse a raw YAML block into a mapping.

    Args:
        yaml_text: Raw YAML text, e.g. the block returned by
            :func:`extract_frontmatter_block`.

    Returns:
        The parsed dict, or None if the text fails to parse as YAML, or the
        parsed value is not a mapping (a list, scalar, or empty document).
    """
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str]:
    """Parse YAML frontmatter and split it from the document body.

    Parsing goes through PyYAML (``yaml.safe_load``), so block scalars
    (``description: |``, ``description: >``), quoted strings, and nested
    mappings all parse correctly -- unlike a naive line-by-line splitter.

    Args:
        text: Full file content, starting at the top of the file.

    Returns:
        A ``(frontmatter, body)`` tuple. ``frontmatter`` is the parsed
        mapping, or None when there is no frontmatter block, the block
        fails to parse as YAML, or the parsed value is not a mapping.
        ``body`` is the text following the closing ``---`` marker (with one
        immediately-following newline consumed); it is the original,
        unmodified ``text`` when no frontmatter block is found.
    """
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        return None, text

    # Reconstruct the block with its trailing newline (consumed by the
    # pattern's literal "\n---" but not part of the captured group) before
    # handing it to PyYAML. Without this, a block scalar's final line loses
    # its newline under YAML clip-chomping rules, silently truncating the
    # last line of a `description: |` or `description: >` value.
    yaml_block = match.group(1) + "\n"
    body = text[match.end() :]
    if body.startswith("\n"):
        body = body[1:]

    return load_yaml_mapping(yaml_block), body
