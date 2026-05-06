#!/usr/bin/env python3
"""Per-row job manifest for subagent orchestration (Phase 4).

Tracks per-row generation status so the orchestration layer can delegate
individual rows to subagents and resume on failure. The manifest is a
JSON file (``row-jobs.json``) in the work directory.

Subcommands:
    init            Create manifest from preset
    status          Print summary of row statuses
    mark            Update a row's status
    list-pending    List rows that still need work (pending or failed)

Usage:
    python3 row_job_status.py init --preset fighter --output-dir /tmp/work
    python3 row_job_status.py status --work-dir /tmp/work
    python3 row_job_status.py mark --work-dir /tmp/work --row 0 --status done
    python3 row_job_status.py list-pending --work-dir /tmp/work
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.row_job_status")

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sprite_prompt

VALID_STATUSES = ("pending", "in-progress", "done", "failed")
MANIFEST_FILENAME = "row-jobs.json"


def _manifest_path(work_dir: Path) -> Path:
    """Return path to the row-jobs manifest."""
    return work_dir / MANIFEST_FILENAME


def init_manifest(preset_name: str, work_dir: Path) -> dict:
    """Create a row-jobs manifest from a named preset.

    Args:
        preset_name: Preset key (e.g., "fighter", "rpg-character").
        work_dir: Directory to write row-jobs.json into.

    Returns:
        The manifest dict that was written.
    """
    preset = sprite_prompt.resolve_preset(preset_name)
    rows = preset["rows"]

    jobs = []
    for idx, row_def in enumerate(rows):
        jobs.append(
            {
                "row_index": idx,
                "state": row_def["state"],
                "frames": row_def["frames"],
                "action": row_def["action"],
                "status": "pending",
                "updated_at": None,
                "output_path": None,
                "error": None,
            }
        )

    manifest = {
        "preset": preset_name,
        "total_rows": len(rows),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "jobs": jobs,
    }

    work_dir.mkdir(parents=True, exist_ok=True)
    out = _manifest_path(work_dir)
    out.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("[row-jobs] init: %d rows from preset %r -> %s", len(rows), preset_name, out)
    return manifest


def load_manifest(work_dir: Path) -> dict:
    """Load the manifest from work_dir.

    Raises:
        FileNotFoundError: If row-jobs.json does not exist.
    """
    path = _manifest_path(work_dir)
    if not path.exists():
        raise FileNotFoundError(f"No manifest at {path}. Run 'init' first.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(work_dir: Path, manifest: dict) -> None:
    """Write manifest back to work_dir."""
    path = _manifest_path(work_dir)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def mark_row(
    work_dir: Path,
    row_index: int,
    status: str,
    output_path: str | None = None,
    error: str | None = None,
) -> dict:
    """Update a row's status in the manifest.

    Args:
        work_dir: Directory containing row-jobs.json.
        row_index: Zero-based row index.
        status: One of pending, in-progress, done, failed.
        output_path: Path to output strip (set on done).
        error: Error message (set on failed).

    Returns:
        The updated manifest.

    Raises:
        ValueError: On invalid status or row_index.
    """
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}. Choose from {VALID_STATUSES}")

    manifest = load_manifest(work_dir)
    jobs = manifest["jobs"]
    if row_index < 0 or row_index >= len(jobs):
        raise ValueError(f"row_index {row_index} out of range [0, {len(jobs)})")

    job = jobs[row_index]
    job["status"] = status
    job["updated_at"] = datetime.now(timezone.utc).isoformat()
    if output_path is not None:
        job["output_path"] = output_path
    if error is not None:
        job["error"] = error

    save_manifest(work_dir, manifest)
    return manifest


def get_status_summary(manifest: dict) -> dict[str, int]:
    """Return counts per status."""
    counts: dict[str, int] = {s: 0 for s in VALID_STATUSES}
    for job in manifest["jobs"]:
        s = job["status"]
        counts[s] = counts.get(s, 0) + 1
    return counts


def list_pending_rows(manifest: dict) -> list[dict]:
    """Return jobs that are pending or failed (need work)."""
    return [j for j in manifest["jobs"] if j["status"] in ("pending", "failed")]


# ---------------------------------------------------------------------------
# CLI subcommands
# ---------------------------------------------------------------------------
def cmd_init(args: argparse.Namespace) -> int:
    """init subcommand: create manifest from preset."""
    try:
        manifest = init_manifest(args.preset, Path(args.output_dir))
    except ValueError as e:
        logger.error("%s", e)
        return 1
    summary = get_status_summary(manifest)
    print(json.dumps({"action": "init", "preset": args.preset, "summary": summary}, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """status subcommand: print summary."""
    try:
        manifest = load_manifest(Path(args.work_dir))
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    summary = get_status_summary(manifest)
    print(json.dumps({"preset": manifest["preset"], "summary": summary}, indent=2))
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    """mark subcommand: update row status."""
    try:
        manifest = mark_row(
            Path(args.work_dir),
            args.row,
            args.status,
            output_path=args.output_path,
            error=args.error,
        )
    except (FileNotFoundError, ValueError) as e:
        logger.error("%s", e)
        return 1
    job = manifest["jobs"][args.row]
    print(json.dumps({"action": "mark", "row": args.row, "status": job["status"]}, indent=2))
    return 0


def cmd_list_pending(args: argparse.Namespace) -> int:
    """list-pending subcommand: rows needing work."""
    try:
        manifest = load_manifest(Path(args.work_dir))
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    pending = list_pending_rows(manifest)
    print(
        json.dumps(
            {"pending_count": len(pending), "rows": [{"row": j["row_index"], "state": j["state"]} for j in pending]},
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="Create manifest from preset")
    init_p.add_argument("--preset", required=True, choices=["fighter", "rpg-character", "platformer", "pet"])
    init_p.add_argument("--output-dir", required=True, help="Work directory to write row-jobs.json")
    init_p.set_defaults(func=cmd_init)

    status_p = sub.add_parser("status", help="Print status summary")
    status_p.add_argument("--work-dir", required=True, help="Work directory containing row-jobs.json")
    status_p.set_defaults(func=cmd_status)

    mark_p = sub.add_parser("mark", help="Update a row's status")
    mark_p.add_argument("--work-dir", required=True, help="Work directory containing row-jobs.json")
    mark_p.add_argument("--row", type=int, required=True, help="Zero-based row index")
    mark_p.add_argument("--status", required=True, choices=list(VALID_STATUSES))
    mark_p.add_argument("--output-path", help="Path to output strip (set on done)")
    mark_p.add_argument("--error", help="Error message (set on failed)")
    mark_p.set_defaults(func=cmd_mark)

    lp = sub.add_parser("list-pending", help="List rows needing work")
    lp.add_argument("--work-dir", required=True, help="Work directory containing row-jobs.json")
    lp.set_defaults(func=cmd_list_pending)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="[%(name)s] %(levelname)s: %(message)s",
            stream=sys.stderr,
        )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
