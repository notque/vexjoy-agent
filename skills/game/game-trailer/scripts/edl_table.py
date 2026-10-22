#!/usr/bin/env python3
"""Shot and overlay table for a promo EDL, with a pace lint.

Reads the edit decision list (tmp/promo/edl.json, written by scripts/promo/edl.mjs) and prints every
shot (output span, length, take, fastest footage speed, tightest zoom) and every overlay (span,
length, kind, text). Then it flags what the owner's reviews rejected: shots shorter than --min-shot,
footage faster than --max-speed, zooms past --max-zoom, captions shorter than --min-caption, VS cards
shorter than --min-vs. The defaults are the edge of what the approved cut 6 of ROAD TO THE BIG TIME
contains (its fastest footage 1.13x, its quickest cuts 0.47 s inside a slow-motion sequence, its
shortest caption 0.9 s), so a clean run means nothing has slid back toward the cuts the owner
rejected. Speeds and camera keys in the EDL are already stretched by the running-order layout, so the
numbers are what the viewer sees.

Usage:
    python3 edl_table.py tmp/promo/edl.json [--min-shot 0.45] [--max-speed 1.15] [--max-zoom 2.5]
                         [--min-caption 0.9] [--min-vs 0.9] [--strict] [--json]

--strict exits 1 when any flag fires. Poster shots (take "black") are judged by their overlay, not by
the shot length.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

EPS = 1e-3  # a millisecond of slack: beat arithmetic lands a hair under round values


def overlay_text(el: dict) -> str:
    kind = el.get("kind")
    if kind == "caption":
        text = " / ".join(el.get("lines") or [])
        band = el.get("band")
        return f"{text} [{band}]" if band else text or "(band only)"
    if kind == "vs":
        opp = el.get("opp") or []
        lands = opp[-1] if opp else "?"
        return f"VS {lands}" + (f" (slot of {len(opp)})" if len(opp) > 1 else "")
    if kind == "cta":
        return f"CTA {el.get('url', '')}"
    return kind or "?"


def shot_rows(edl: dict, args: argparse.Namespace) -> list[dict]:
    rows = []
    for s in edl["shots"]:
        dur = s["t1"] - s["t0"]
        take = s.get("take") or "-"
        speeds = [v for _, v in (s.get("speed") or [[0, 1.0]])]
        zooms = [c.get("z", 1.0) for c in (s.get("cam") or [])] or [1.0]
        flags = []
        if take != "black":
            if dur < args.min_shot - EPS:
                flags.append(f"short {dur:.2f}s")
            if max(speeds) > args.max_speed + EPS:
                flags.append(f"fast {max(speeds):.2f}x")
            if max(zooms) > args.max_zoom + EPS:
                flags.append(f"zoom {max(zooms):.2f}")
        rows.append(
            {
                "t0": s["t0"],
                "t1": s["t1"],
                "dur": dur,
                "take": take,
                "speed_max": max(speeds),
                "speed_min": min(speeds),
                "zoom_max": max(zooms),
                "flags": flags,
            }
        )
    return rows


def overlay_rows(edl: dict, args: argparse.Namespace) -> list[dict]:
    rows = []
    for el in edl.get("overlays", []):
        dur = el["t1"] - el["t0"]
        kind = el.get("kind", "?")
        flags = []
        if kind == "caption" and dur < args.min_caption - EPS:
            flags.append(f"brief {dur:.2f}s")
        if kind == "vs" and dur < args.min_vs - EPS:
            flags.append(f"brief {dur:.2f}s")
        rows.append(
            {"t0": el["t0"], "t1": el["t1"], "dur": dur, "kind": kind, "text": overlay_text(el), "flags": flags}
        )
    rows.sort(key=lambda r: r["t0"])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("edl", type=Path)
    ap.add_argument("--min-shot", type=float, default=0.45, help="shortest acceptable take shot (s)")
    ap.add_argument("--max-speed", type=float, default=1.15, help="fastest acceptable footage speed")
    ap.add_argument("--max-zoom", type=float, default=2.5, help="tightest acceptable camera zoom")
    ap.add_argument("--min-caption", type=float, default=0.9, help="shortest acceptable caption (s)")
    ap.add_argument("--min-vs", type=float, default=0.9, help="shortest acceptable VS card (s)")
    ap.add_argument("--strict", action="store_true", help="exit 1 when any flag fires")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    edl = json.loads(args.edl.read_text(encoding="utf-8"))
    shots = shot_rows(edl, args)
    overlays = overlay_rows(edl, args)
    take_shots = [r for r in shots if r["take"] != "black"]
    flagged = sum(1 for r in shots + overlays if r["flags"])
    summary = {
        "duration": edl.get("duration"),
        "shots": len(shots),
        "poster_shots": len(shots) - len(take_shots),
        "median_shot": statistics.median(r["dur"] for r in take_shots) if take_shots else None,
        "overlays": len(overlays),
        "flagged": flagged,
    }

    if args.json:
        print(json.dumps({"summary": summary, "shots": shots, "overlays": overlays}, indent=1))
    else:
        print("SHOTS    t0      t1     len  take        speed       zoom  flags")
        for r in shots:
            speed = (
                f"{r['speed_min']:.2f}-{r['speed_max']:.2f}x"
                if r["speed_min"] != r["speed_max"]
                else f"{r['speed_max']:.2f}x"
            )
            print(
                f"{r['t0']:8.2f} {r['t1']:7.2f} {r['dur']:6.2f}  {r['take']:<10} {speed:<11} {r['zoom_max']:5.2f}  "
                + ", ".join(r["flags"])
            )
        print("\nOVERLAYS t0      t1     len  kind     text")
        for r in overlays:
            print(
                f"{r['t0']:8.2f} {r['t1']:7.2f} {r['dur']:6.2f}  {r['kind']:<8} {r['text'][:70]}  "
                + ", ".join(r["flags"])
            )
        med = f"{summary['median_shot']:.2f} s" if summary["median_shot"] is not None else "-"
        print(
            f"\n{summary['duration']:.2f} s, {summary['shots']} shots ({summary['poster_shots']} poster), "
            f"median take shot {med}, {summary['overlays']} overlays, {flagged} flagged"
        )
    return 1 if (args.strict and flagged) else 0


if __name__ == "__main__":
    sys.exit(main())
