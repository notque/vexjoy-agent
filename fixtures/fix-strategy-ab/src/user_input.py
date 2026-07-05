"""Sanitize user input for safe display. Bug: missing HTML entity escaping."""

import re


def sanitize_for_display(text: str) -> str:
    """Remove dangerous HTML but preserve safe content for display."""
    # Strip script tags
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL | re.IGNORECASE)
    # BUG: does not escape &, <, > — raw HTML entities pass through
    return text.strip()


def truncate(text: str, max_length: int = 100) -> str:
    """Truncate text to max_length, adding ellipsis if truncated."""
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
