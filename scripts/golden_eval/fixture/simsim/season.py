"""Season standings."""

from __future__ import annotations

MAX_TABLE_ROWS = 12


def standings(results: dict[str, int]) -> list[tuple[str, int]]:
    """Teams sorted by points, highest first, ties by name."""
    ordered = sorted(results.items(), key=lambda item: (-item[1], item[0]))
    return ordered[:MAX_TABLE_ROWS]
