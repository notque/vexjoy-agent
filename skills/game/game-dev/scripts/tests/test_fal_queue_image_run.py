"""Tests for fal_queue_image_run.py import safety."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from unittest.mock import patch

SCRIPTS_DIR = Path(__file__).parent.parent


def test_import_without_fal_key_does_not_exit() -> None:
    """Importing the module with FAL_KEY unset must not call sys.exit."""
    env = {k: v for k, v in os.environ.items() if k != "FAL_KEY"}
    with patch.dict(os.environ, env, clear=True):
        spec = importlib.util.spec_from_file_location(
            "fal_queue_image_run_test_import",
            SCRIPTS_DIR / "fal_queue_image_run.py",
        )
        mod = importlib.util.module_from_spec(spec)
        # If this calls sys.exit, the test fails with SystemExit.
        spec.loader.exec_module(mod)
        # The module loaded without exiting -- FAL_KEY should be None at import.
        assert mod.FAL_KEY is None
