"""The profile picker writes .local/profile.yaml without questionary.

Profile filtering itself is covered by scripts/tests/test_vexinstall_profile.py.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIGURE = REPO_ROOT / "scripts" / "configure-profile.py"


def _first_hook() -> str:
    # The repo ships no agents since plans/009, so the test disables a hook.
    return sorted(p.name for p in (REPO_ROOT / "hooks").glob("*.py") if p.name != "__init__.py")[0]


def test_configure_plain_fallback_writes_profile(tmp_path: Path) -> None:
    """Picker works without questionary: --plain reads names from stdin."""
    hook = _first_hook()
    out = tmp_path / "profile.yaml"
    result = subprocess.run(
        [sys.executable, str(CONFIGURE), "--plain", "--output", str(out)],
        input=f"\n\n{hook}\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert hook in text
    assert "disabled:" in text
