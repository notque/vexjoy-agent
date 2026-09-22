"""The profile picker writes .local/profile.yaml without questionary.

Profile filtering itself is covered by scripts/tests/test_vexinstall_profile.py.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIGURE = REPO_ROOT / "scripts" / "configure-profile.py"


def _first_agent() -> str:
    return sorted(p.stem for p in (REPO_ROOT / "agents").glob("*.md") if not p.stem.upper().startswith("README"))[0]


def test_configure_plain_fallback_writes_profile(tmp_path: Path) -> None:
    """Picker works without questionary: --plain reads names from stdin."""
    agent = _first_agent()
    out = tmp_path / "profile.yaml"
    result = subprocess.run(
        [sys.executable, str(CONFIGURE), "--plain", "--output", str(out)],
        input=f"\n{agent}\n\n",
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    text = out.read_text(encoding="utf-8")
    assert agent in text
    assert "disabled:" in text
