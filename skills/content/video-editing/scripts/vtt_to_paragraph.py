#!/usr/bin/env python3
"""Clean a WebVTT subtitle file into readable paragraph text.

Handles both uploader subtitles and YouTube auto-captions (rolling
duplicate lines, inline <c>/timing tags, [Music]-style cues).
Stdlib only.
"""

import argparse
import re
import sys
from pathlib import Path

TIMESTAMP_LINE = re.compile(r"^(\d{2}:)?\d{2}:\d{2}\.\d{3}\s+-->\s+(\d{2}:)?\d{2}:\d{2}\.\d{3}")
INLINE_TAG = re.compile(r"<[^>]+>")
BRACKET_CUE = re.compile(r"\[[^\]]*\]|\([^)]*\)")
HEADER_PREFIXES = ("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE", "REGION")
PARAGRAPH_GAP_SECONDS = 4.0
SENTENCES_PER_PARAGRAPH = 5


def parse_start_seconds(line: str) -> float:
    """Return the cue start time in seconds."""
    start = line.split("-->")[0].strip()
    parts = start.split(":")
    seconds = 0.0
    for part in parts:
        seconds = seconds * 60 + float(part)
    return seconds


def extract_cues(text: str, keep_brackets: bool) -> list[tuple[float, str]]:
    """Return (start_seconds, text) cues, deduplicated and tag-free."""
    cues: list[tuple[float, str]] = []
    current_start = 0.0
    seen_tail: str = ""
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.isdigit() or line.startswith(HEADER_PREFIXES):
            continue
        if TIMESTAMP_LINE.match(line):
            current_start = parse_start_seconds(line)
            continue
        line = INLINE_TAG.sub("", line)
        if not keep_brackets:
            line = BRACKET_CUE.sub("", line)
        line = re.sub(r"\s+", " ", line).strip()
        # Auto-captions roll: each cue repeats the previous line, then adds one.
        if not line or line == seen_tail:
            continue
        seen_tail = line
        cues.append((current_start, line))
    return cues


def format_timestamp(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"[{hours}:{minutes:02d}:{secs:02d}]"
    return f"[{minutes}:{secs:02d}]"


def build_paragraphs(cues: list[tuple[float, str]], timestamps: bool) -> str:
    """Join cues into paragraphs, breaking on silence gaps or sentence count."""
    paragraphs: list[str] = []
    chunk: list[str] = []
    sentence_count = 0
    previous_start = None
    for start, line in cues:
        gap = previous_start is not None and start - previous_start > PARAGRAPH_GAP_SECONDS
        if chunk and (gap or sentence_count >= SENTENCES_PER_PARAGRAPH):
            paragraphs.append(" ".join(chunk))
            chunk = []
            sentence_count = 0
        if timestamps and not chunk:
            chunk.append(format_timestamp(start))
        chunk.append(line)
        sentence_count += len(re.findall(r"[.!?](?:\s|$)", line))
        previous_start = start
    if chunk:
        paragraphs.append(" ".join(chunk))
    return "\n\n".join(paragraphs) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vtt_file", type=Path, help="input .vtt file")
    parser.add_argument("-o", "--output", type=Path, help="write result to file")
    parser.add_argument("--timestamps", action="store_true", help="prefix paragraphs with [mm:ss]")
    parser.add_argument("--keep-brackets", action="store_true", help="keep [Music]-style cues")
    args = parser.parse_args()

    try:
        text = args.vtt_file.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    cues = extract_cues(text, keep_brackets=args.keep_brackets)
    if not cues:
        print("error: no subtitle text found in file", file=sys.stderr)
        return 1

    result = build_paragraphs(cues, timestamps=args.timestamps)
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
