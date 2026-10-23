#!/usr/bin/env python3
"""Contact sheet of a captured take around its marks.

Reads tmp/promo/takes/<take>/take.json (every frame's virtual time, the marks) and the f#####.jpg
frames, and writes one JPEG grid. Two modes:

  marks (default)  one row per mark, the frames at --offsets ms after it; the label on each thumb is
                   "<mark>+<ms>". This is the check before and after a 4K run: did every mark fire,
                   is the move on screen, is a banner or the cursor in the frame.
  uniform          --every ms (with --from/--to) samples the whole take evenly.

Usage:
    python3 take_sheet.py tmp/promo/takes/turn --out tmp/promo/turn.jpg
    python3 take_sheet.py tmp/promo/takes/moneymaker --marks fin_release --offsets 224,304,484,724,1224,2500
    python3 take_sheet.py tmp/promo/takes/table --every 500 --from 9000 --to 16000 --cols 6

Needs Pillow.
"""

from __future__ import annotations

import argparse
import json
import sys
from bisect import bisect_right
from pathlib import Path

from PIL import Image, ImageDraw


def frame_at(frames: list[float], vt: float) -> int:
    i = bisect_right(frames, vt + 1e-6) - 1
    return max(0, min(len(frames) - 1, i))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("take", type=Path, help="take directory with take.json and f#####.jpg")
    ap.add_argument("--out", type=Path, default=None, help="output JPEG (default: <take>/sheet.jpg)")
    ap.add_argument("--marks", default=None, help="comma list of mark labels (default: every mark)")
    ap.add_argument("--offsets", default="0,100,250,500,1000", help="ms after each mark")
    ap.add_argument("--every", type=float, default=None, help="uniform sampling interval (ms) instead of marks")
    ap.add_argument("--from", dest="t_from", type=float, default=None, help="uniform mode start (ms)")
    ap.add_argument("--to", dest="t_to", type=float, default=None, help="uniform mode end (ms)")
    ap.add_argument("--cols", type=int, default=None, help="columns (default: one row per mark, or 6)")
    ap.add_argument("--width", type=int, default=480, help="thumbnail width (px)")
    ap.add_argument("--quality", type=int, default=88)
    args = ap.parse_args()

    meta = json.loads((args.take / "take.json").read_text(encoding="utf-8"))
    frames: list[float] = meta["frames"]
    marks = {m["label"]: m["vt"] for m in meta.get("marks", [])}

    cells: list[tuple[int, str]] = []
    if args.every:
        t0 = args.t_from if args.t_from is not None else frames[0]
        t1 = args.t_to if args.t_to is not None else frames[-1]
        t = t0
        while t <= t1:
            cells.append((frame_at(frames, t), f"{t / 1000:.2f}s"))
            t += args.every
        cols = args.cols or 6
    else:
        labels = args.marks.split(",") if args.marks else list(marks)
        offsets = [float(o) for o in args.offsets.split(",")]
        missing = [m for m in labels if m not in marks]
        if missing:
            raise SystemExit(f"{args.take}: marks missing from take.json: {', '.join(missing)}")
        for label in labels:
            for off in offsets:
                cells.append((frame_at(frames, marks[label] + off), f"{label}+{off:g}"))
        cols = args.cols or len(offsets)
    if not cells:
        raise SystemExit("nothing to draw")

    first = Image.open(args.take / f"f{cells[0][0]:05d}.jpg")
    tw = args.width
    th = round(first.height * tw / first.width)
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (0, 0, 0))
    draw = ImageDraw.Draw(sheet)
    for k, (idx, label) in enumerate(cells):
        y, x = divmod(k, cols)
        with Image.open(args.take / f"f{idx:05d}.jpg") as im:
            thumb = im.convert("RGB").resize((tw, th), Image.LANCZOS)
        sheet.paste(thumb, (x * tw, y * th))
        text = f"{label}  f{idx}"
        draw.rectangle((x * tw, y * th, x * tw + 7 * len(text) + 8, y * th + 16), fill=(0, 0, 0))
        draw.text((x * tw + 4, y * th + 2), text, fill=(80, 230, 255))

    out = args.out or (args.take / "sheet.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, quality=args.quality)
    print(f"{out} ({sheet.width}x{sheet.height}, {len(cells)} frames)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
