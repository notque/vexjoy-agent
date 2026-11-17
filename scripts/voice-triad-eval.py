#!/usr/bin/env python3
"""Voice triad eval: deterministic plumbing for pairwise voice-skill testing.

Splits a writing corpus into train and holdout sets, builds brief-extraction
and pairwise-judge job files, and scores returned judgments with order-swap
consistency.  Calls no model and no network.

Design record: ADR-voice-triad-eval (local-only).

Usage:
    python3 scripts/voice-triad-eval.py split --corpus DIR --out FILE
    python3 scripts/voice-triad-eval.py brief-jobs --manifest FILE --corpus DIR --out DIR
    python3 scripts/voice-triad-eval.py judge-jobs --manifest FILE --corpus DIR \\
        --drafts DIR --arms A B --out DIR
    python3 scripts/voice-triad-eval.py score --jobs DIR --judgments FILE [--json]
    python3 scripts/voice-triad-eval.py distill --briefs DIR --finals DIR [--json]

Exit codes:
    0  success (or complete score set)
    1  runtime error
    2  validation error (too few pieces, missing drafts, incomplete judgments)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from random import Random

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_PIECES = 8
_WARN_PIECES = 12

BRIEF_PROMPT = (
    "Extract a substance-only brief from the piece below.  Include:\n"
    "- The thesis or central argument\n"
    "- A section-by-section outline\n"
    "- Every fact, statistic, and data point\n"
    "- Every named source and attribution\n"
    "- Every anecdote, example, and case study\n"
    "- Every exact quote needed to write the piece\n\n"
    "Exclude all style, phrasing, hooks, jokes, rhetorical devices,\n"
    "transitions, and voice.  The brief is raw material, not a draft.\n\n"
    "Return the brief as plain text with markdown headings for sections."
)

_JUDGE_PROMPT_TEMPLATE = (
    "You are a writing judge.  Below are three texts:\n\n"
    "REFERENCE (the real piece):\n{reference}\n\n"
    "Draft 1:\n{draft_1}\n\n"
    "Draft 2:\n{draft_2}\n\n"
    "Which draft reads closer to the REFERENCE in voice, rhythm, word choice,\n"
    "and overall feel?  Ignore substance differences; focus on style.\n\n"
    'Return JSON: {{"closer": 1 or 2, "note_draft_1": "how Draft 1 differs '
    'from the reference", "note_draft_2": "how Draft 2 differs from the '
    'reference"}}'
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    """Return the hex sha256 digest of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _piece_date(path: Path) -> float:
    """Return a sort key: leading YYYY-MM-DD in the filename, else mtime."""
    match = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
    if match:
        parts = match.group(1).split("-")
        # Return a timestamp-like float from the date string.
        return float(parts[0]) * 10000 + float(parts[1]) * 100 + float(parts[2])
    return path.stat().st_mtime


def _collect_pieces(corpus: Path) -> list[Path]:
    """Return sorted *.md and *.txt files in a corpus directory."""
    pieces = sorted(p for p in corpus.iterdir() if p.is_file() and p.suffix in (".md", ".txt"))
    return pieces


def _piece_id(path: Path) -> str:
    """Derive a stable id from the filename without extension."""
    return path.stem


# ---------------------------------------------------------------------------
# Subcommand: split
# ---------------------------------------------------------------------------


def cmd_split(args: argparse.Namespace) -> int:
    """Split a corpus into train and holdout sets."""
    corpus = Path(args.corpus).resolve()
    if not corpus.is_dir():
        print(f"error: corpus directory does not exist: {corpus}", file=sys.stderr)
        return 1

    pieces = _collect_pieces(corpus)
    count = len(pieces)

    if count < _MIN_PIECES:
        print(
            f"error: corpus has {count} pieces, need at least {_MIN_PIECES}",
            file=sys.stderr,
        )
        return 2

    if count < _WARN_PIECES:
        print(
            f"warning: corpus has {count} pieces; {_WARN_PIECES}+ recommended",
            file=sys.stderr,
        )

    holdout_count = max(args.min_holdout, int(count * args.holdout_frac))
    holdout_count = min(holdout_count, count - 1)  # keep at least 1 for train

    if args.recent_first:
        # Sort by date descending; newest go to holdout.
        by_date = sorted(pieces, key=_piece_date, reverse=True)
        holdout_paths = by_date[:holdout_count]
        train_paths = sorted(set(pieces) - set(holdout_paths), key=lambda p: p.name)
        holdout_paths = sorted(holdout_paths, key=lambda p: p.name)
    else:
        rng = Random(args.seed)
        indices = list(range(count))
        rng.shuffle(indices)
        holdout_indices = set(indices[:holdout_count])
        holdout_paths = [pieces[i] for i in sorted(holdout_indices)]
        train_paths = [pieces[i] for i in range(count) if i not in holdout_indices]

    def entry(p: Path) -> dict[str, str]:
        return {"name": p.name, "sha256": _sha256(p)}

    manifest = {
        "corpus": str(corpus),
        "seed": args.seed,
        "recent_first": args.recent_first,
        "holdout_frac": args.holdout_frac,
        "train": [entry(p) for p in train_paths],
        "holdout": [entry(p) for p in holdout_paths],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {out}: {len(train_paths)} train, {len(holdout_paths)} holdout")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: brief-jobs
# ---------------------------------------------------------------------------


def cmd_brief_jobs(args: argparse.Namespace) -> int:
    """Write one brief-extraction job per piece."""
    manifest = json.loads(Path(args.manifest).read_text())
    corpus = Path(args.corpus).resolve()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    pieces = manifest.get(args.set, [])
    if not pieces:
        print(f"error: no pieces in set '{args.set}'", file=sys.stderr)
        return 2

    for piece in pieces:
        piece_path = corpus / piece["name"]
        piece_id = Path(piece["name"]).stem
        job = {
            "id": f"brief-{piece_id}",
            "piece_path": str(piece_path),
            "prompt": BRIEF_PROMPT,
        }
        job_path = out_dir / f"brief-{piece_id}.json"
        job_path.write_text(json.dumps(job, indent=2) + "\n")

    print(f"wrote {len(pieces)} brief jobs to {out_dir}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: judge-jobs
# ---------------------------------------------------------------------------


def cmd_judge_jobs(args: argparse.Namespace) -> int:
    """Write two judge jobs per holdout piece (one per presentation order)."""
    manifest = json.loads(Path(args.manifest).read_text())
    corpus = Path(args.corpus).resolve()
    drafts_dir = Path(args.drafts).resolve()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    arm_a, arm_b = args.arms

    holdout = manifest.get("holdout", [])
    if not holdout:
        print("error: no holdout pieces in manifest", file=sys.stderr)
        return 2

    errors: list[str] = []
    written = 0

    for piece in holdout:
        piece_id = Path(piece["name"]).stem
        piece_path = corpus / piece["name"]

        draft_a = drafts_dir / arm_a / f"{piece_id}.md"
        draft_b = drafts_dir / arm_b / f"{piece_id}.md"

        if not draft_a.is_file():
            errors.append(f"missing draft: {draft_a}")
        if not draft_b.is_file():
            errors.append(f"missing draft: {draft_b}")
        if errors and errors[-1].startswith("missing"):
            continue

        ref_text = piece_path.read_text()
        text_a = draft_a.read_text()
        text_b = draft_b.read_text()

        # Order AB: Draft 1 = arm_a, Draft 2 = arm_b
        prompt_ab = _JUDGE_PROMPT_TEMPLATE.format(reference=ref_text, draft_1=text_a, draft_2=text_b)
        job_ab = {
            "id": f"judge-{piece_id}-AB",
            "piece_id": piece_id,
            "order": "AB",
            "first_arm": arm_a,
            "second_arm": arm_b,
            "prompt": prompt_ab,
        }

        # Order BA: Draft 1 = arm_b, Draft 2 = arm_a
        prompt_ba = _JUDGE_PROMPT_TEMPLATE.format(reference=ref_text, draft_1=text_b, draft_2=text_a)
        job_ba = {
            "id": f"judge-{piece_id}-BA",
            "piece_id": piece_id,
            "order": "BA",
            "first_arm": arm_b,
            "second_arm": arm_a,
            "prompt": prompt_ba,
        }

        (out_dir / f"judge-{piece_id}-AB.json").write_text(json.dumps(job_ab, indent=2) + "\n")
        (out_dir / f"judge-{piece_id}-BA.json").write_text(json.dumps(job_ba, indent=2) + "\n")
        written += 2

    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 2

    print(f"wrote {written} judge jobs to {out_dir}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: score
# ---------------------------------------------------------------------------


def cmd_score(args: argparse.Namespace) -> int:
    """Score judgments against job files and report consistency."""
    jobs_dir = Path(args.jobs)
    judgments_path = Path(args.judgments)

    # Load all judge jobs.
    jobs: dict[str, dict] = {}
    for p in sorted(jobs_dir.iterdir()):
        if p.name.startswith("judge-") and p.suffix == ".json":
            job = json.loads(p.read_text())
            jobs[job["id"]] = job

    # Load judgments.
    judgments: dict[str, dict] = {}
    for line in judgments_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        j = json.loads(line)
        judgments[j["id"]] = j

    # Check completeness.
    missing = sorted(set(jobs) - set(judgments))
    if missing:
        print(f"error: {len(missing)} missing judgment(s):", file=sys.stderr)
        for m in missing:
            print(f"  {m}", file=sys.stderr)
        return 2

    # Map each judgment to an arm win.
    arm_wins: dict[str, int] = {}
    piece_results: dict[str, dict[str, str]] = {}  # piece_id -> {order: winning_arm}
    all_notes: dict[str, list[dict[str, str]]] = {}  # arm -> list of notes
    first_position_picks = 0
    total_judgments = 0

    for jid, judgment in judgments.items():
        if jid not in jobs:
            continue
        job = jobs[jid]
        closer = judgment["closer"]
        total_judgments += 1

        if closer == 1:
            first_position_picks += 1
            winning_arm = job["first_arm"]
        else:
            winning_arm = job["second_arm"]

        arm_wins[winning_arm] = arm_wins.get(winning_arm, 0) + 1

        piece_id = job["piece_id"]
        if piece_id not in piece_results:
            piece_results[piece_id] = {}
        piece_results[piece_id][job["order"]] = winning_arm

        # Collect notes per arm.
        for arm_key, note_key in [
            (job["first_arm"], "note_draft_1"),
            (job["second_arm"], "note_draft_2"),
        ]:
            if arm_key not in all_notes:
                all_notes[arm_key] = []
            note_text = judgment.get(note_key, "")
            if note_text:
                all_notes[arm_key].append({"piece_id": piece_id, "order": job["order"], "note": note_text})

    # Per-piece: consistent if both orders agree.
    consistent_pieces = 0
    split_pieces = 0
    piece_winners: dict[str, str | None] = {}
    for piece_id, orders in piece_results.items():
        ab_winner = orders.get("AB")
        ba_winner = orders.get("BA")
        if ab_winner and ba_winner and ab_winner == ba_winner:
            consistent_pieces += 1
            piece_winners[piece_id] = ab_winner
        else:
            split_pieces += 1
            piece_winners[piece_id] = None

    total_pieces = len(piece_results)
    consistency = consistent_pieces / total_pieces if total_pieces else 0.0
    first_position_rate = first_position_picks / total_judgments if total_judgments else 0.0

    # Win rate excluding splits.
    consistent_wins: dict[str, int] = {}
    for piece_id, winner in piece_winners.items():
        if winner is not None:
            consistent_wins[winner] = consistent_wins.get(winner, 0) + 1

    consistent_total = sum(consistent_wins.values())

    result = {
        "arm_wins_all": arm_wins,
        "consistency": round(consistency, 4),
        "first_position_rate": round(first_position_rate, 4),
        "split_count": split_pieces,
        "consistent_wins": consistent_wins,
        "consistent_win_rate": {
            arm: round(wins / consistent_total, 4) if consistent_total else 0.0 for arm, wins in consistent_wins.items()
        },
        "piece_results": {pid: winner if winner else "split" for pid, winner in piece_winners.items()},
        "notes_per_arm": all_notes,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"total judgments: {total_judgments}")
        print(f"arm wins (all judgments): {arm_wins}")
        print(f"order-swap consistency: {result['consistency']}")
        print(f"first-position rate: {result['first_position_rate']}")
        print(f"split pieces: {split_pieces}")
        print(f"consistent wins: {consistent_wins}")
        print(f"consistent win rate: {result['consistent_win_rate']}")
        for pid, winner in sorted(piece_winners.items()):
            label = winner if winner else "split"
            print(f"  {pid}: {label}")
    return 0


# ---------------------------------------------------------------------------
# Subcommand: distill
# ---------------------------------------------------------------------------


def cmd_distill(args: argparse.Namespace) -> int:
    """Report distillation ratios for brief/final pairs."""
    briefs_dir = Path(args.briefs)
    finals_dir = Path(args.finals)

    brief_files = {p.stem: p for p in briefs_dir.iterdir() if p.suffix in (".md", ".txt")}
    final_files = {p.stem: p for p in finals_dir.iterdir() if p.suffix in (".md", ".txt")}

    common = sorted(set(brief_files) & set(final_files))
    if not common:
        print("error: no matching brief/final pairs", file=sys.stderr)
        return 2

    rows: list[dict[str, str | int | float | bool]] = []
    for pid in common:
        brief_words = len(brief_files[pid].read_text().split())
        final_words = len(final_files[pid].read_text().split())
        ratio = round(brief_words / final_words, 3) if final_words else 0.0
        flagged = ratio < 1.0
        rows.append(
            {
                "id": pid,
                "brief_words": brief_words,
                "final_words": final_words,
                "ratio": ratio,
                "flagged": flagged,
            }
        )

    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for row in rows:
            flag = " [FLAGGED: ratio < 1.0]" if row["flagged"] else ""
            print(f"{row['id']}: brief={row['brief_words']}w, final={row['final_words']}w, ratio={row['ratio']}{flag}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="voice-triad-eval",
        description="Deterministic plumbing for pairwise voice-skill testing.",
    )
    subs = parser.add_subparsers(dest="command")

    # split
    sp = subs.add_parser("split", help="Split a corpus into train and holdout sets.")
    sp.add_argument("--corpus", required=True, help="Directory of *.md/*.txt pieces.")
    sp.add_argument("--out", required=True, help="Output manifest JSON path.")
    sp.add_argument("--holdout-frac", type=float, default=0.3, help="Holdout fraction (default 0.3).")
    sp.add_argument("--min-holdout", type=int, default=5, help="Minimum holdout count (default 5).")
    sp.add_argument(
        "--recent-first",
        action="store_true",
        help="Put newest files in holdout instead of random selection.",
    )
    sp.add_argument("--seed", type=int, default=0, help="Random seed (default 0).")

    # brief-jobs
    bp = subs.add_parser("brief-jobs", help="Write brief-extraction jobs.")
    bp.add_argument("--manifest", required=True, help="Manifest JSON from split.")
    bp.add_argument("--corpus", required=True, help="Corpus directory.")
    bp.add_argument("--out", required=True, help="Output directory for job files.")
    bp.add_argument(
        "--set",
        default="holdout",
        choices=["holdout", "train"],
        help="Which set to build jobs for (default holdout).",
    )

    # judge-jobs
    jp = subs.add_parser("judge-jobs", help="Write pairwise judge jobs.")
    jp.add_argument("--manifest", required=True, help="Manifest JSON from split.")
    jp.add_argument("--corpus", required=True, help="Corpus directory.")
    jp.add_argument("--drafts", required=True, help="Drafts root (DRAFTS/<arm>/<id>.md).")
    jp.add_argument("--arms", nargs=2, required=True, help="Two arm names to compare.")
    jp.add_argument("--out", required=True, help="Output directory for job files.")

    # score
    scp = subs.add_parser("score", help="Score judgments and report consistency.")
    scp.add_argument("--jobs", required=True, help="Directory of judge job JSONs.")
    scp.add_argument("--judgments", required=True, help="JSONL file of judgment results.")
    scp.add_argument("--json", action="store_true", help="Output as JSON.")

    # distill
    dp = subs.add_parser("distill", help="Report distillation ratios.")
    dp.add_argument("--briefs", required=True, help="Directory of brief files.")
    dp.add_argument("--finals", required=True, help="Directory of final draft files.")
    dp.add_argument("--json", action="store_true", help="Output as JSON.")

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point.  Returns the exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    dispatch = {
        "split": cmd_split,
        "brief-jobs": cmd_brief_jobs,
        "judge-jobs": cmd_judge_jobs,
        "score": cmd_score,
        "distill": cmd_distill,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
