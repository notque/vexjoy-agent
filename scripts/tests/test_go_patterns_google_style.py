"""Contracts for the pinned Google Go style guide snapshot.

Snapshot part sizes are covered by `validate-references.py --check-size`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "programming" / "programming"
STYLE_DIR = SKILL_DIR / "references" / "go" / "google-style-guide"
DOCUMENTS = ("index.md", "guide.md", "decisions.md", "best-practices.md")
REVISION = "1809c769de31ba388c755ad15dd057a9ba8531fd"
EXPECTED_SHA256 = {
    "index.md": "95f228a13481ffefab9da3303446484e2b22c6cffa34a273169c844ad33a3435",
    "guide.md": "f12051c22045953c3688a85f9eba94f7cf61b6a769762671cdbf1ca4d2b3aa1b",
    "decisions.md": "3a0b54ef41aca49f8bf0a4d4ce2d0b4662721b52197256d121b6cc95616f4850",
    "best-practices.md": "e44180b492c3585b4a20bd44e7cb277a55a9f264ad352f33f287b639e9e75b56",
}
GENERIC_ERROR_WRAP_RE = re.compile(r'fmt\.Errorf\("(?:operation|request|call|processing) failed: %w"')


def test_complete_snapshot_matches_recorded_checksums() -> None:
    recorded = {}
    for line in (STYLE_DIR / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        digest, name = line.split("  ", 1)
        recorded[name] = digest

    assert (STYLE_DIR / "UPSTREAM_REVISION").read_text(encoding="utf-8").strip() == REVISION
    assert recorded == EXPECTED_SHA256
    for name in DOCUMENTS:
        direct = STYLE_DIR / name
        if direct.exists():
            content = direct.read_bytes()
        else:
            content = b"".join(
                path.read_bytes() for path in sorted((STYLE_DIR / name.removesuffix(".md")).glob("part-*.md"))
            )
        assert hashlib.sha256(content).hexdigest() == recorded[name]


def test_prescriptive_go_guidance_has_no_generic_error_wraps() -> None:
    """Scan instructional examples while preserving explicit bad examples."""
    roots = (ROOT / "agents", SKILL_DIR / "references")
    violations = []
    for root in roots:
        for path in root.rglob("*.md"):
            if STYLE_DIR in path.parents:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
            mode = None
            for number, line in enumerate(lines, start=1):
                heading = line.strip().lower()
                if re.match(r"^(?:#{1,6}\s*)?(?:\*\*)?(fix|solution|good)\b", heading):
                    mode = "prescriptive"
                elif re.match(r"^(?:#{1,6}\s*)?(?:\*\*)?(bad|before|anti-pattern)\b", heading):
                    mode = "negative"
                elif line.startswith("#") and mode is not None:
                    mode = None
                if mode == "prescriptive" and GENERIC_ERROR_WRAP_RE.search(line):
                    violations.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
    assert violations == []


def test_sync_removes_obsolete_chunk_directory(tmp_path: Path) -> None:
    script = SKILL_DIR / "scripts" / "sync-google-style-guide.py"
    spec = importlib.util.spec_from_file_location("sync_google_style", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    chunked = b"line\n" * (module.CHUNK_LINES + 1)
    direct = b"short\n"
    module.write_document(tmp_path, "guide.md", chunked)
    assert (tmp_path / "guide").is_dir()

    written = module.write_document(tmp_path, "guide.md", direct)
    assert written == [tmp_path / "guide.md"]
    assert (tmp_path / "guide.md").read_bytes() == direct
    assert not (tmp_path / "guide").exists()
