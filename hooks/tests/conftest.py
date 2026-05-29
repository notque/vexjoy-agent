"""Shared pytest fixtures for hook tests.

Isolates per-hook on-disk dedup state so that tests which reuse an identical
working-tree diff (and therefore an identical DiffDedup signature) don't
contaminate one another through the real ~/.claude/state/ directory.

The fixture is autouse but inert for any test module that does not expose a hook
`mod` with `_STATE_DIR` / `_STATE_FILE`: it reaches the hook module via the
requesting test module's `mod` attribute (the importlib-loaded module under
test) and redirects its state to a fresh tmp dir per test. Other hook test files
that don't bind a `mod` with those attributes are unaffected.
"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_hook_dedup_state(request, tmp_path, monkeypatch):
    """Point a hook's dedup state at a fresh tmp dir for each test.

    No-op unless the requesting test module exposes `mod._STATE_DIR`. Tests that
    patch `_STATE_DIR` / `_STATE_FILE` themselves (e.g. TestDedup) take
    precedence — their `with patch.object(...)` block is entered later and
    restored on exit.
    """
    mod = getattr(request.module, "mod", None)
    if mod is not None and hasattr(mod, "_STATE_DIR"):
        state_dir = tmp_path / "hook-dedup-state"
        monkeypatch.setattr(mod, "_STATE_DIR", state_dir, raising=False)
        monkeypatch.setattr(mod, "_STATE_FILE", state_dir / "last-diff-hash.json", raising=False)
    yield
