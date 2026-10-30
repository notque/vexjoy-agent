"""Keep the two scoped Jev cosmic-ray configs' operator filters in sync.

scripts/cosmic-ray-jev-limits.toml and scripts/cosmic-ray-jev-router-common.toml
each carry their own copy of the same exclude-operators regex (see either
file's comment for why cosmic-ray's full operator matrix is mostly noise on
these two files). Nothing in cosmic-ray reuses one config from the other, so
a future edit to the keep-list in one file can drift from the other silently.
This test catches that drift the moment either file changes, without running
any mutation testing itself.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

# `tomllib` is stdlib only from Python 3.11; this repo's CI matrix still runs
# 3.10 (no `tomli` fallback is installed there, and these configs are
# deliberately NOT a CI dependency -- see either .toml file's own comment).
# A real TOML parser is unnecessary for what this test actually checks: two
# single-line scalars/arrays and one multi-line array whose exact text must
# match byte-for-byte across both files. Targeted regexes on the raw text
# cover that without adding a parser or a new dependency.
REPO_ROOT = Path(__file__).resolve().parents[2]
LIMITS_CONFIG = REPO_ROOT / "scripts" / "cosmic-ray-jev-limits.toml"
ROUTER_CONFIG = REPO_ROOT / "scripts" / "cosmic-ray-jev-router-common.toml"

_MODULE_PATH_RE = re.compile(r"^module-path\s*=\s*(\[.*\])\s*$", re.MULTILINE)
_EXCLUDE_OPERATORS_RE = re.compile(r"^exclude-operators\s*=\s*\[(.*?)^\]\s*$", re.MULTILINE | re.DOTALL)


def _module_path(path: Path) -> list[str]:
    """Return the config's `module-path` array, e.g. `["scripts/jev_limits.py"]`."""
    text = path.read_text(encoding="utf-8")
    match = _MODULE_PATH_RE.search(text)
    assert match is not None, f"{path} has no top-level module-path = [...] line"
    return ast.literal_eval(match.group(1))


def _exclude_operators_block(path: Path) -> str:
    """Return the raw text inside `exclude-operators = [ ... ]`, whitespace-normalized.

    Returned as text, not a parsed list: the value is a single TOML
    triple-quoted literal string holding a regex, and comparing the raw
    block is exactly as strict as comparing a parsed value for this test's
    purpose (byte-for-byte drift between the two files) without needing a
    TOML string-literal parser.
    """
    text = path.read_text(encoding="utf-8")
    match = _EXCLUDE_OPERATORS_RE.search(text)
    assert match is not None, f"{path} has no top-level exclude-operators = [...] block"
    return re.sub(r"\s+", " ", match.group(1)).strip()


def test_both_configs_exist() -> None:
    """Both scoped Jev mutation-testing configs are present."""
    assert LIMITS_CONFIG.is_file()
    assert ROUTER_CONFIG.is_file()


def test_exclude_operators_identical_across_both_configs() -> None:
    """The operator-filter keep-list must match between the two files.

    They are hand-maintained duplicates by design (cosmic-ray's TOML config
    format has no include/anchor mechanism), so this is the guard that
    replaces sharing a single source of truth.
    """
    limits_exclude = _exclude_operators_block(LIMITS_CONFIG)
    router_exclude = _exclude_operators_block(ROUTER_CONFIG)

    assert limits_exclude == router_exclude, (
        "scripts/cosmic-ray-jev-limits.toml and scripts/cosmic-ray-jev-router-common.toml "
        "exclude-operators lists have drifted apart; update both together."
    )


def test_both_configs_scope_module_path_to_one_file_each() -> None:
    """Each config mutates exactly the one script it is named for."""
    assert _module_path(LIMITS_CONFIG) == ["scripts/jev_limits.py"]
    assert _module_path(ROUTER_CONFIG) == ["scripts/jev_router_common.py"]
