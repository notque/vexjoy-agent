"""agents/README.md keeps the toolkit repo marker after plans/009 retired every agent.

The private-name leak gate and the ADR creation gate find the repo by agents/ + skills/.
A fresh clone holds only tracked files, so without a tracked file in agents/ both gates
switch off there.
"""

from __future__ import annotations

import importlib.util
import io
import subprocess
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(name: str):
    path = REPO / "hooks" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_").removesuffix(".py"), path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _export(tmp_path: Path) -> Path:
    """Tracked files only, as a fresh clone sees them."""
    blob = subprocess.run(["git", "archive", "HEAD"], cwd=REPO, capture_output=True, check=True).stdout
    out = tmp_path / "clone"
    out.mkdir()
    with tarfile.open(fileobj=io.BytesIO(blob)) as tar:
        tar.extractall(out, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    return out


def test_agents_readme_is_tracked() -> None:
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", "agents/README.md"], cwd=REPO, capture_output=True)
    assert tracked.returncode == 0, "agents/README.md must stay tracked: two safety gates use agents/ as a marker"


def test_gates_detect_a_fresh_export(tmp_path: Path) -> None:
    clone = _export(tmp_path)
    leak = _load("pretool-private-name-leak-gate.py")
    adr = _load("pretool-adr-creation-gate.py")
    assert leak._find_toolkit_root(str(clone / "skills")) == clone.resolve()
    assert adr._is_toolkit_repo(clone)
