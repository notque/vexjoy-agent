#!/usr/bin/env python3
"""Per-beat loudness of a mix, to find holes and balance problems without listening.

Reads a PCM WAV (16, 24 or 32-bit) and prints the RMS in dB of every beat at --bpm, sixteen beats per
row, then flags beats more than --hole dB below the median of their neighbours (a music hole like the
one an unmapped ring-out tail punched into cut 3 of ROAD TO THE BIG TIME). With --timeline it also
prints the RMS of every section in output order, mapping cut beats through the running-order layout
exactly as the edit, the score and the mix do, and takes the bpm from the file.

Usage:
    python3 beat_levels.py tmp/promo/audio/mix.wav [--bpm 96] [--timeline scripts/promo/timeline.json]
                           [--hole 12] [--skip-tail 2] [--json]

Exit 1 when a hole is found.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import wave
from pathlib import Path

import numpy as np


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """Mono float signal and sample rate from a PCM WAV."""
    with wave.open(str(path), "rb") as w:
        ch, sw, sr, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, "<i2").astype(np.float64) / 32768.0
    elif sw == 4:
        x = np.frombuffer(raw, "<i4").astype(np.float64) / 2147483648.0
    elif sw == 3:
        b = np.frombuffer(raw, np.uint8).reshape(-1, 3).astype(np.int32)
        v = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        x = np.where(v >= 1 << 23, v - (1 << 24), v).astype(np.float64) / float(1 << 23)
    else:
        raise SystemExit(f"{path}: unsupported sample width {sw}")
    return x.reshape(-1, ch).mean(axis=1), sr


def rms_db(x: np.ndarray) -> float:
    return float(20 * np.log10(np.sqrt(np.mean(x * x)) + 1e-9)) if x.size else -180.0


def out_beat(tl: dict, b: float, end: bool = False) -> float | None:
    """Cut beat -> output beat through the layout; a stretched block plays k times slower; past the
    last block the tail follows it. Same rule as edl.mjs, compose_trailer.py and mix.py. None for a
    cut beat no block covers (a section the running order dropped)."""
    layout = tl.get("layout") or []
    if not layout:
        return b
    y = b - 1e-6 if end else b
    blk = next((blk for blk in layout if blk[0] <= y < blk[1]), None)
    if blk is None:
        last = max(layout, key=lambda blk: blk[1])
        blk = last if y >= last[1] else None
    if blk is None:
        return None
    a, _, c, *k = blk
    return c + (b - a) * (k[0] if k else 1)


def section_spans(tl: dict) -> list[tuple[str, float, float]]:
    """Sections in output beats, in output order; an inserted section replaces a cut section of the
    same name, and a cut section the layout no longer plays is left out."""
    spans: dict[str, tuple[float, float]] = {}
    for name, (a, z) in tl.get("sections", {}).items():
        o0, o1 = out_beat(tl, a), out_beat(tl, z, True)
        if o0 is not None and o1 is not None:
            spans[name] = (o0, o1)
    for name, (a, z) in tl.get("inserted", {}).items():
        spans[name] = (a, z)
    return sorted(((n, a, z) for n, (a, z) in spans.items()), key=lambda s: s[1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("wav", type=Path)
    ap.add_argument("--bpm", type=float, default=None, help="beats per minute (default: the timeline's, else 96)")
    ap.add_argument("--timeline", type=Path, default=None, help="timeline.json for bpm, sections and layout")
    ap.add_argument("--hole", type=float, default=12.0, help="dB below the neighbours' median that counts as a hole")
    ap.add_argument("--skip-tail", type=int, default=2, help="beats at the end exempt from the hole check (the fade)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    tl = json.loads(args.timeline.read_text(encoding="utf-8")) if args.timeline else {}
    bpm = args.bpm or float(tl.get("bpm", 96))
    x, sr = read_wav(args.wav)
    n = round(60.0 / bpm * sr)
    beats = [rms_db(x[i * n : (i + 1) * n]) for i in range(len(x) // n)]

    holes = []
    last = len(beats) - args.skip_tail
    for i in range(1, last):
        around = beats[max(0, i - 3) : i] + beats[i + 1 : min(last, i + 4)]
        if len(around) >= 2 and statistics.median(around) - beats[i] > args.hole:
            holes.append({"beat": i, "db": round(beats[i], 1), "around": round(statistics.median(around), 1)})

    sections = []
    for name, a, z in section_spans(tl):
        i0, i1 = int(a * n), min(len(x), int(z * n))
        if i1 > i0:
            sections.append(
                {"section": name, "out_beats": [round(a, 2), round(z, 2)], "db": round(rms_db(x[i0:i1]), 1)}
            )

    if args.json:
        print(
            json.dumps(
                {"bpm": bpm, "beats": [round(b, 1) for b in beats], "holes": holes, "sections": sections}, indent=1
            )
        )
    else:
        print(f"{args.wav}: {len(x) / sr:.2f} s, {bpm:g} BPM, {len(beats)} beats (dB RMS)")
        for row in range(0, len(beats), 16):
            print("  " + " ".join(f"{i}:{beats[i]:.0f}" for i in range(row, min(len(beats), row + 16))))
        if sections:
            print("\nsection           out beats        dB")
            for s in sections:
                print(f"  {s['section']:<16} {s['out_beats'][0]:6.2f}-{s['out_beats'][1]:<6.2f} {s['db']:6.1f}")
        if holes:
            print("\nHOLES: " + ", ".join(f"beat {h['beat']} at {h['db']} dB (around {h['around']})" for h in holes))
        else:
            print("\nno holes")
    return 1 if holes else 0


if __name__ == "__main__":
    sys.exit(main())
