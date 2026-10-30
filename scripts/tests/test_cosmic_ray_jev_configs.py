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

from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[2]
LIMITS_CONFIG = REPO_ROOT / "scripts" / "cosmic-ray-jev-limits.toml"
ROUTER_CONFIG = REPO_ROOT / "scripts" / "cosmic-ray-jev-router-common.toml"


def _load(path: Path) -> dict:
    with path.open("rb") as f:
        return tomllib.load(f)


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
    limits_cfg = _load(LIMITS_CONFIG)
    router_cfg = _load(ROUTER_CONFIG)

    limits_exclude = limits_cfg["cosmic-ray"]["filters"]["operators-filter"]["exclude-operators"]
    router_exclude = router_cfg["cosmic-ray"]["filters"]["operators-filter"]["exclude-operators"]

    assert limits_exclude == router_exclude, (
        "scripts/cosmic-ray-jev-limits.toml and scripts/cosmic-ray-jev-router-common.toml "
        "exclude-operators lists have drifted apart; update both together."
    )


def test_both_configs_scope_module_path_to_one_file_each() -> None:
    """Each config mutates exactly the one script it is named for."""
    limits_cfg = _load(LIMITS_CONFIG)
    router_cfg = _load(ROUTER_CONFIG)

    assert limits_cfg["cosmic-ray"]["module-path"] == ["scripts/jev_limits.py"]
    assert router_cfg["cosmic-ray"]["module-path"] == ["scripts/jev_router_common.py"]
