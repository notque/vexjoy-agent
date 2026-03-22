#!/usr/bin/env python3
"""Manifest system for snapshot and rollback of system upgrades.

Records file state before upgrades, enables rollback via manifests,
and verifies post-upgrade integrity with optional score-component integration.

Usage:
    python3 scripts/manifest.py snapshot agents/golang-general-engineer.md skills/do/SKILL.md
    python3 scripts/manifest.py snapshot --all
    python3 scripts/manifest.py undo .claude/manifests/upgrade-2026-03-22T143000.json
    python3 scripts/manifest.py verify .claude/manifests/upgrade-2026-03-22T143000.json
    python3 scripts/manifest.py list

Exit codes:
    0 — Success (or verify found no regressions)
    1 — Verify found score regressions > 5 points
    2 — Script error (bad arguments, missing files)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFESTS_DIR = REPO_ROOT / ".claude" / "manifests"
BACKUPS_DIR = REPO_ROOT / ".claude" / "backups"

SCORE_SCRIPT = REPO_ROOT / "scripts" / "score-component.py"

# Timestamp format used in directory/file names (no colons for filesystem safety)
TS_DIR_FORMAT = "%Y-%m-%dT%H%M%S"
# ISO format used in manifest JSON
TS_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def compute_sha256(file_path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def find_all_components() -> list[Path]:
    """Find all agent and skill files in the repo."""
    components: list[Path] = []

    agents_dir = REPO_ROOT / "agents"
    if agents_dir.is_dir():
        components.extend(sorted(p for p in agents_dir.glob("*.md")))

    skills_dir = REPO_ROOT / "skills"
    if skills_dir.is_dir():
        components.extend(sorted(skills_dir.glob("*/SKILL.md")))

    return components


# ---------------------------------------------------------------------------
# Subcommand: snapshot
# ---------------------------------------------------------------------------


def cmd_snapshot(args: argparse.Namespace) -> int:
    """Record current state of files before modification."""
    # Determine target files
    if args.all:
        targets = find_all_components()
        if not targets:
            print("Error: No agent or skill files found.", file=sys.stderr)
            return 2
    else:
        if not args.files:
            print("Error: Provide file paths or use --all.", file=sys.stderr)
            return 2
        targets = []
        for f in args.files:
            p = Path(f)
            if not p.is_absolute():
                p = REPO_ROOT / f
            p = p.resolve()
            try:
                p.relative_to(REPO_ROOT.resolve())
            except ValueError:
                print(f"Error: Path outside repo root: {f}", file=sys.stderr)
                return 2
            if not p.exists():
                print(f"Error: File not found: {f}", file=sys.stderr)
                return 2
            targets.append(p)

    now = datetime.now(timezone.utc)
    ts_dir = now.strftime(TS_DIR_FORMAT)
    ts_iso = now.strftime(TS_ISO_FORMAT)

    backup_dir = BACKUPS_DIR / ts_dir
    manifest_path = MANIFESTS_DIR / f"upgrade-{ts_dir}.json"

    if manifest_path.exists():
        ts_dir = now.strftime(TS_DIR_FORMAT) + f"-{now.microsecond:06d}"
        manifest_path = MANIFESTS_DIR / f"upgrade-{ts_dir}.json"
        backup_dir = BACKUPS_DIR / ts_dir
        backup_dir.mkdir(parents=True, exist_ok=True)

    # Create directories
    backup_dir.mkdir(parents=True, exist_ok=True)
    MANIFESTS_DIR.mkdir(parents=True, exist_ok=True)

    files_entries: list[dict[str, str]] = []
    for target in targets:
        rel_path = target.relative_to(REPO_ROOT)
        sha = compute_sha256(target)

        # Copy to backup preserving relative path
        backup_dest = backup_dir / rel_path
        backup_dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(target, backup_dest)
        except OSError as e:
            print(f"Error: could not backup {rel_path}: {e}", file=sys.stderr)
            return 2

        backup_rel = backup_dest.relative_to(REPO_ROOT)
        files_entries.append(
            {
                "path": str(rel_path),
                "action": "existing",
                "sha256": sha,
                "backup_path": str(backup_rel),
            }
        )

    manifest = {
        "timestamp": ts_iso,
        "files": files_entries,
    }

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # Print manifest path (relative to repo root) to stdout
    print(str(manifest_path.relative_to(REPO_ROOT)))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: undo
# ---------------------------------------------------------------------------


def cmd_undo(args: argparse.Namespace) -> int:
    """Restore files from a manifest backup."""
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = REPO_ROOT / manifest_path

    if not manifest_path.exists():
        print(f"Error: Manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: Cannot read manifest: {e}", file=sys.stderr)
        return 2

    files = manifest.get("files", [])
    if not files:
        print("Warning: Manifest contains no file entries.", file=sys.stderr)
        return 0

    restored_count = 0
    failed_count = 0
    for entry in files:
        try:
            rel_path = entry["path"]
            backup_rel = entry["backup_path"]
        except KeyError as e:
            print(f"Warning: manifest entry missing field {e}", file=sys.stderr)
            failed_count += 1
            continue

        backup_path = (REPO_ROOT / backup_rel).resolve()
        target_path = (REPO_ROOT / rel_path).resolve()
        try:
            backup_path.relative_to(REPO_ROOT.resolve())
            target_path.relative_to(REPO_ROOT.resolve())
        except ValueError:
            print(f"Error: Path escapes repo root: {rel_path}", file=sys.stderr)
            failed_count += 1
            continue

        if not backup_path.exists():
            print(f"Warning: Backup missing, cannot restore: {rel_path}", file=sys.stderr)
            failed_count += 1
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(backup_path, target_path)
        except OSError as e:
            print(f"Error: could not restore {rel_path}: {e}", file=sys.stderr)
            failed_count += 1
            continue
        print(f"Restored: {rel_path}")
        restored_count += 1

    print(f"Restored {restored_count} files from manifest")
    if failed_count:
        print(f"Failed to restore {failed_count} files", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# Subcommand: list
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> int:
    """Show available manifests sorted by timestamp descending."""
    if not MANIFESTS_DIR.is_dir():
        print("No manifests found.")
        return 0

    manifest_files = sorted(MANIFESTS_DIR.glob("*.json"), reverse=True)
    if not manifest_files:
        print("No manifests found.")
        return 0

    print(f"{'Manifest':<50s}  {'Files':>5s}  {'Size':>8s}")
    print(f"{'─' * 50}  {'─' * 5}  {'─' * 8}")

    for mf in manifest_files:
        try:
            data = json.loads(mf.read_text(encoding="utf-8"))
            file_count = len(data.get("files", []))
            ts_display = data.get("timestamp", "unknown")
        except (json.JSONDecodeError, OSError) as e:
            print(f"Warning: cannot read manifest {mf.name}: {e}", file=sys.stderr)
            file_count = 0
            ts_display = "error"

        try:
            size_bytes = mf.stat().st_size
        except OSError as e:
            print(f"Warning: cannot stat manifest {mf.name}: {e}", file=sys.stderr)
            continue
        if size_bytes >= 1024:
            size_str = f"{size_bytes / 1024:.1f}KB"
        else:
            size_str = f"{size_bytes}B"

        rel_path = str(mf.relative_to(REPO_ROOT))
        print(f"{rel_path:<50s}  {file_count:>5d}  {size_str:>8s}")

    return 0


# ---------------------------------------------------------------------------
# Subcommand: verify
# ---------------------------------------------------------------------------


def _run_scorer(file_path: str) -> int | None:
    """Run score-component.py on a file and return total score, or None on failure."""
    if not SCORE_SCRIPT.exists():
        return None

    try:
        result = subprocess.run(
            [sys.executable, str(SCORE_SCRIPT), file_path, "--json"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=30,
        )
        if result.returncode not in (0, 1):
            return None

        data = json.loads(result.stdout)
        results = data.get("results", [])
        if results:
            return results[0].get("total")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as e:
        print(f"Warning: scoring failed for {file_path}: {e}", file=sys.stderr)
    return None


def _is_component_file(rel_path: str) -> bool:
    """Check if a relative path looks like an agent or skill file."""
    if rel_path.startswith("agents/") and rel_path.endswith(".md"):
        return True
    if re.match(r"skills/.+/SKILL\.md$", rel_path):
        return True
    return False


def cmd_verify(args: argparse.Namespace) -> int:
    """Compare current state against manifest and check for regressions."""
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = REPO_ROOT / manifest_path

    if not manifest_path.exists():
        print(f"Error: Manifest not found: {args.manifest}", file=sys.stderr)
        return 2

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error: Cannot read manifest: {e}", file=sys.stderr)
        return 2

    files = manifest.get("files", [])
    if not files:
        print("Manifest contains no file entries.")
        return 0

    unchanged = 0
    modified = 0
    deleted = 0
    regressions: list[str] = []

    for entry in files:
        try:
            rel_path = entry["path"]
            original_sha = entry["sha256"]
        except KeyError as e:
            print(f"Warning: manifest entry missing field {e}", file=sys.stderr)
            continue

        target = (REPO_ROOT / rel_path).resolve()
        try:
            target.relative_to(REPO_ROOT.resolve())
        except ValueError:
            print(f"Error: Path escapes repo root: {rel_path}", file=sys.stderr)
            continue

        if not target.exists():
            print(f"  DELETED: {rel_path}")
            deleted += 1
            continue

        current_sha = compute_sha256(target)
        if current_sha == original_sha:
            print(f"  UNCHANGED: {rel_path}")
            unchanged += 1
        else:
            detail = f"  MODIFIED: {rel_path}"

            # Score delta check for agent/skill files
            if _is_component_file(rel_path) and SCORE_SCRIPT.exists():
                current_score = _run_scorer(rel_path)
                # Score the backup to get the original score
                backup_rel = entry.get("backup_path", "")
                original_score = None
                if backup_rel:
                    backup_abs = (REPO_ROOT / backup_rel).resolve()
                    try:
                        backup_abs.relative_to(REPO_ROOT.resolve())
                        original_score = _run_scorer(backup_rel)
                    except ValueError:
                        print("Warning: backup_path escapes repo root, skipping", file=sys.stderr)

                if current_score is not None and original_score is not None:
                    delta = current_score - original_score
                    detail += f" (score: {original_score} -> {current_score}, delta: {delta:+d})"
                    if delta < -5:
                        detail += " REGRESSION"
                        regressions.append(rel_path)

            print(detail)
            modified += 1

    print()
    print(f"Summary: {unchanged} unchanged, {modified} modified, {deleted} deleted")

    if regressions:
        print(f"REGRESSIONS detected in: {', '.join(regressions)}")
        return 1

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Manifest system for snapshot and rollback of system upgrades.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 scripts/manifest.py snapshot agents/golang-general-engineer.md\n"
            "  python3 scripts/manifest.py snapshot --all\n"
            "  python3 scripts/manifest.py undo .claude/manifests/upgrade-2026-03-22T143000.json\n"
            "  python3 scripts/manifest.py verify .claude/manifests/upgrade-2026-03-22T143000.json\n"
            "  python3 scripts/manifest.py list\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # snapshot
    snap_parser = subparsers.add_parser("snapshot", help="Record current state of files before modification")
    snap_parser.add_argument("files", nargs="*", help="Files to snapshot")
    snap_parser.add_argument("--all", action="store_true", help="Snapshot all agents and skills")

    # undo
    undo_parser = subparsers.add_parser("undo", help="Restore files from a manifest backup")
    undo_parser.add_argument("manifest", help="Path to manifest JSON file")

    # list
    subparsers.add_parser("list", help="Show available manifests")

    # verify
    verify_parser = subparsers.add_parser("verify", help="Compare current state against manifest")
    verify_parser.add_argument("manifest", help="Path to manifest JSON file")

    return parser


def main() -> int:
    """Entry point."""
    parser = build_parser()
    args = parser.parse_args()

    match args.command:
        case "snapshot":
            return cmd_snapshot(args)
        case "undo":
            return cmd_undo(args)
        case "list":
            return cmd_list(args)
        case "verify":
            return cmd_verify(args)
        case _:
            parser.print_help()
            return 2


if __name__ == "__main__":
    sys.exit(main())
