#!/usr/bin/env python3
"""
Extract transcripts from video URLs across platforms.

Dual-path architecture:
  - YouTube URLs: use youtube-transcript-api (fast, no download)
  - Other platforms: use yt-dlp --write-sub --skip-download + parse VTT/SRT

Usage:
    video_transcript.py transcript URL
    video_transcript.py transcript URL --timestamps --lang es
    video_transcript.py transcript URL --json -o output.json
    video_transcript.py audio URL -o output.mp3

Exit codes:
    0 = success
    1 = fatal error (no transcript available, invalid URL, missing dependency)
    2 = partial result (transcript extracted but may be auto-generated)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# --- URL detection ---


_YOUTUBE_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?.*v=([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/live/([a-zA-Z0-9_-]{11})"),
]


def extract_youtube_id(url: str) -> str | None:
    """Extract YouTube video ID from URL, or None if not a YouTube URL."""
    for pattern in _YOUTUBE_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


# --- Dependency checks ---


def _check_ytdlp() -> None:
    """Verify yt-dlp is available, exit with actionable message if not."""
    if shutil.which("yt-dlp") is None:
        print("ERROR: yt-dlp not found", file=sys.stderr)
        print("Install with: pip install yt-dlp", file=sys.stderr)
        sys.exit(1)


def _check_ffmpeg() -> None:
    """Verify ffmpeg is available, exit with actionable message if not."""
    if shutil.which("ffmpeg") is None:
        print("ERROR: ffmpeg not found", file=sys.stderr)
        print("Install via your system package manager (e.g., apt install ffmpeg)", file=sys.stderr)
        sys.exit(1)


# --- Data model ---


@dataclass
class TranscriptSegment:
    """A single segment of a transcript with timing information."""

    start: float
    end: float
    text: str


@dataclass
class TranscriptResult:
    """Complete transcript extraction result."""

    url: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    language: str = "en"
    auto_generated: bool = False
    method: str = "unknown"
    title: str = ""

    @property
    def full_text(self) -> str:
        """Join all segment text into clean paragraphs."""
        return " ".join(seg.text for seg in self.segments if seg.text.strip())

    def format_text(self) -> str:
        """Format as clean paragraph text (no timestamps)."""
        return self.full_text

    def format_timestamped(self) -> str:
        """Format with [MM:SS] timestamps at segment boundaries."""
        lines = []
        for seg in self.segments:
            if not seg.text.strip():
                continue
            minutes = int(seg.start) // 60
            seconds = int(seg.start) % 60
            lines.append(f"[{minutes:02d}:{seconds:02d}] {seg.text}")
        return "\n".join(lines)

    def format_json(self) -> str:
        """Format as structured JSON."""
        data = {
            "url": self.url,
            "title": self.title,
            "language": self.language,
            "auto_generated": self.auto_generated,
            "segments": [{"start": s.start, "end": s.end, "text": s.text} for s in self.segments],
            "full_text": self.full_text,
            "method": self.method,
        }
        return json.dumps(data, indent=2, ensure_ascii=False)


# --- Path 1: YouTube via youtube-transcript-api ---


def _fetch_youtube_transcript(video_id: str, lang: str) -> TranscriptResult | None:
    """Attempt to fetch transcript using youtube-transcript-api. Returns None on failure."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        print("INFO: youtube-transcript-api not installed, falling back to yt-dlp", file=sys.stderr)
        return None

    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
    except Exception as e:
        print(f"INFO: youtube-transcript-api failed ({e}), falling back to yt-dlp", file=sys.stderr)
        return None

    auto_generated = False
    try:
        transcript = transcript_list.find_transcript([lang])
    except Exception:
        # Try auto-generated
        try:
            transcript = transcript_list.find_generated_transcript([lang])
            auto_generated = True
        except Exception as e:
            print(f"INFO: No {lang} transcript via API ({e}), falling back to yt-dlp", file=sys.stderr)
            return None

    if transcript.is_generated:
        auto_generated = True

    try:
        entries = transcript.fetch()
    except Exception as e:
        print(f"INFO: Failed to fetch transcript data ({e}), falling back to yt-dlp", file=sys.stderr)
        return None

    segments = []
    for entry in entries:
        text = entry.get("text", "").strip()
        if not text or text == "[Music]" or text == "[Applause]":
            continue
        start = float(entry.get("start", 0))
        duration = float(entry.get("duration", 0))
        segments.append(TranscriptSegment(start=start, end=start + duration, text=text))

    return TranscriptResult(
        url=f"https://youtube.com/watch?v={video_id}",
        segments=segments,
        language=lang,
        auto_generated=auto_generated,
        method="youtube-transcript-api",
    )


# --- Path 2: yt-dlp subtitle extraction ---


def _parse_vtt(content: str) -> list[TranscriptSegment]:
    """Parse VTT subtitle file into segments, deduplicating rolling captions."""
    segments: list[TranscriptSegment] = []
    seen_texts: set[str] = set()

    # Split into cue blocks (separated by blank lines)
    blocks = re.split(r"\n\s*\n", content)

    for block in blocks:
        lines = block.strip().split("\n")
        if not lines:
            continue

        # Find timestamp line
        timestamp_line = None
        text_lines: list[str] = []

        for line in lines:
            # Skip VTT headers and metadata
            if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
                continue
            if line.startswith("NOTE"):
                continue
            # Skip sequence numbers (pure digits)
            if line.strip().isdigit():
                continue
            # Detect timestamp line (HH:MM:SS.mmm --> HH:MM:SS.mmm)
            if "-->" in line:
                timestamp_line = line
                continue
            # Everything else is text
            if line.strip():
                text_lines.append(line.strip())

        if not timestamp_line or not text_lines:
            continue

        # Parse timestamps
        ts_match = re.match(r"([\d:.]+)\s*-->\s*([\d:.]+)", timestamp_line)
        if not ts_match:
            continue

        start = _parse_timestamp(ts_match.group(1))
        end = _parse_timestamp(ts_match.group(2))

        # Clean text: strip HTML/VTT tags
        raw_text = " ".join(text_lines)
        clean = _clean_subtitle_text(raw_text)

        if not clean:
            continue

        # Deduplicate consecutive identical lines (rolling caption artifact)
        if clean in seen_texts:
            continue
        seen_texts.add(clean)

        segments.append(TranscriptSegment(start=start, end=end, text=clean))

    return segments


def _parse_srt(content: str) -> list[TranscriptSegment]:
    """Parse SRT subtitle file into segments."""
    segments: list[TranscriptSegment] = []
    seen_texts: set[str] = set()

    # SRT blocks: sequence number, timestamp line, text, blank line
    blocks = re.split(r"\n\s*\n", content.strip())

    for block in blocks:
        lines = block.strip().split("\n")
        if len(lines) < 2:
            continue

        # Find timestamp line
        timestamp_line = None
        text_lines: list[str] = []

        for line in lines:
            if line.strip().isdigit():
                continue
            if "-->" in line:
                timestamp_line = line
                continue
            if line.strip():
                text_lines.append(line.strip())

        if not timestamp_line or not text_lines:
            continue

        # SRT uses comma for milliseconds: 00:00:01,234 --> 00:00:04,567
        ts_match = re.match(r"([\d:,]+)\s*-->\s*([\d:,]+)", timestamp_line)
        if not ts_match:
            continue

        start = _parse_timestamp(ts_match.group(1).replace(",", "."))
        end = _parse_timestamp(ts_match.group(2).replace(",", "."))

        raw_text = " ".join(text_lines)
        clean = _clean_subtitle_text(raw_text)

        if not clean:
            continue

        if clean in seen_texts:
            continue
        seen_texts.add(clean)

        segments.append(TranscriptSegment(start=start, end=end, text=clean))

    return segments


def _parse_timestamp(ts: str) -> float:
    """Parse VTT/SRT timestamp string to seconds as float."""
    # Handle both HH:MM:SS.mmm and MM:SS.mmm
    parts = ts.replace(",", ".").split(":")
    if len(parts) == 3:
        hours, minutes, seconds = parts
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
    elif len(parts) == 2:
        minutes, seconds = parts
        return float(minutes) * 60 + float(seconds)
    return 0.0


def _clean_subtitle_text(text: str) -> str:
    """Strip VTT/SRT formatting artifacts from text."""
    # Remove HTML tags (<i>, <b>, <font>, etc.)
    clean = re.sub(r"<[^>]+>", "", text)
    # Remove VTT positioning tags (align:start, position:, etc.)
    clean = re.sub(r"\b(?:align|position|size|line):[^\s]+", "", clean)
    # Remove VTT cue tags (<c>, <c.colorCCCCCC>, etc.)
    clean = re.sub(r"<c[^>]*>", "", clean)
    clean = clean.replace("</c>", "")
    # Remove musical note characters (common in auto-captions for music)
    clean = re.sub(r"[♪♫♬♩]", "", clean)
    # Collapse whitespace
    clean = re.sub(r"\s+", " ", clean).strip()
    # Skip common noise markers
    if clean.lower() in ("[music]", "[applause]", "[laughter]", ""):
        return ""
    return clean


def _fetch_ytdlp_transcript(url: str, lang: str) -> TranscriptResult | None:
    """Fetch transcript using yt-dlp subtitle extraction."""
    _check_ytdlp()

    with tempfile.TemporaryDirectory(prefix="transcript_") as tmpdir:
        cmd = [
            "yt-dlp",
            "--write-sub",
            "--write-auto-sub",
            "--sub-lang",
            lang,
            "--skip-download",
            "--sub-format",
            "vtt",
            "-o",
            f"{tmpdir}/%(id)s.%(ext)s",
            "--no-warnings",
            url,
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

        if result.returncode != 0 and not any(Path(tmpdir).iterdir()):
            # yt-dlp may return non-zero but still write subtitle files
            print(f"ERROR: yt-dlp failed: {result.stderr.strip()}", file=sys.stderr)
            return None

        # Find subtitle files
        tmp_path = Path(tmpdir)
        sub_files = list(tmp_path.glob("*.vtt")) + list(tmp_path.glob("*.srt"))

        if not sub_files:
            print("ERROR: No subtitle files found. Video may not have captions.", file=sys.stderr)
            return None

        # Prefer .vtt over .srt
        sub_file = sub_files[0]
        for f in sub_files:
            if f.suffix == ".vtt":
                sub_file = f
                break

        content = sub_file.read_text(encoding="utf-8", errors="replace")

        # Parse based on format
        segments = _parse_srt(content) if sub_file.suffix == ".srt" else _parse_vtt(content)

        if not segments:
            print("ERROR: Subtitle file parsed but no text segments found.", file=sys.stderr)
            return None

        # Detect auto-generated from filename pattern (yt-dlp uses .XX.vtt for manual, .XX.auto.vtt pattern)
        auto_generated = ".auto." in sub_file.name or "auto" in sub_file.stem.lower()

        # Try to get title via yt-dlp
        title = _get_video_title(url)

        return TranscriptResult(
            url=url,
            segments=segments,
            language=lang,
            auto_generated=auto_generated,
            method="yt-dlp",
            title=title,
        )


def _get_video_title(url: str) -> str:
    """Get video title via yt-dlp --print title. Best effort, returns empty on failure."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--print", "title", "--no-warnings", "--no-download", url],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return ""


# --- Main extraction logic ---


def extract_transcript(url: str, lang: str = "en") -> TranscriptResult | None:
    """Extract transcript from URL using the best available method.

    For YouTube URLs, tries youtube-transcript-api first (fast), then falls back to yt-dlp.
    For all other URLs, uses yt-dlp directly.

    Args:
        url: Video URL to extract transcript from.
        lang: Language code for transcript (default: "en").

    Returns:
        TranscriptResult on success, None on failure.
    """
    video_id = extract_youtube_id(url)

    if video_id:
        # Path 1: Try youtube-transcript-api first
        result = _fetch_youtube_transcript(video_id, lang)
        if result:
            # Fill in title if we got it from API
            if not result.title:
                result.title = _get_video_title(url) if shutil.which("yt-dlp") else ""
            return result
        # Fall through to path 2

    # Path 2: yt-dlp
    return _fetch_ytdlp_transcript(url, lang)


# --- Audio extraction ---


def extract_audio(url: str, output: Path) -> int:
    """Extract audio from video URL as MP3 via yt-dlp + ffmpeg.

    Args:
        url: Video URL to extract audio from.
        output: Output file path for the MP3.

    Returns:
        Exit code (0=success, 1=failure).
    """
    _check_ytdlp()
    _check_ffmpeg()

    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format",
        "mp3",
        "--audio-quality",
        "4",
        "-o",
        str(output),
        "--no-warnings",
        url,
    ]

    print(f"Extracting audio to: {output}", file=sys.stderr)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        print(f"ERROR: Audio extraction failed: {result.stderr.strip()}", file=sys.stderr)
        return 1

    if output.exists():
        size_mb = output.stat().st_size / (1024 * 1024)
        print(f"Audio saved: {output} ({size_mb:.1f} MB)", file=sys.stderr)
        return 0
    else:
        # yt-dlp may append extension
        candidates = list(output.parent.glob(f"{output.stem}*"))
        if candidates:
            actual = candidates[0]
            size_mb = actual.stat().st_size / (1024 * 1024)
            print(f"Audio saved: {actual} ({size_mb:.1f} MB)", file=sys.stderr)
            return 0
        print("ERROR: Audio file not created.", file=sys.stderr)
        return 1


# --- CLI ---


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Extract transcripts and audio from video URLs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s transcript "https://youtube.com/watch?v=dQw4w9WgXcQ"
  %(prog)s transcript "https://youtube.com/watch?v=ID" --timestamps --lang es
  %(prog)s transcript "https://youtube.com/watch?v=ID" --json -o output.json
  %(prog)s audio "https://youtube.com/watch?v=ID" -o podcast.mp3
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- transcript subcommand ---
    transcript_parser = subparsers.add_parser("transcript", help="Extract text transcript from video URL")
    transcript_parser.add_argument("url", help="Video URL")
    transcript_parser.add_argument("--lang", default="en", help="Transcript language code (default: en)")
    transcript_parser.add_argument("--timestamps", action="store_true", help="Include [MM:SS] timestamps")
    transcript_parser.add_argument("--json", action="store_true", dest="json_output", help="Output as structured JSON")
    transcript_parser.add_argument("--output", "-o", help="Write output to file instead of stdout")

    # --- audio subcommand ---
    audio_parser = subparsers.add_parser("audio", help="Extract audio as MP3 from video URL")
    audio_parser.add_argument("url", help="Video URL")
    audio_parser.add_argument("--output", "-o", required=True, help="Output MP3 file path")

    args = parser.parse_args()

    if args.command == "transcript":
        return _cmd_transcript(args)
    elif args.command == "audio":
        return _cmd_audio(args)
    else:
        parser.print_help()
        return 1


def _cmd_transcript(args: argparse.Namespace) -> int:
    """Handle the transcript subcommand."""
    result = extract_transcript(args.url, lang=args.lang)

    if result is None:
        print("ERROR: No transcript available for this URL.", file=sys.stderr)
        return 1

    if not result.segments:
        print("ERROR: Transcript extracted but contains no text segments.", file=sys.stderr)
        return 1

    # Format output
    if args.json_output:
        output = result.format_json()
    elif args.timestamps:
        output = result.format_timestamped()
    else:
        output = result.format_text()

    # Write or print
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Transcript written to: {args.output}", file=sys.stderr)
    else:
        print(output)

    # Exit code 2 for auto-generated (partial quality)
    if result.auto_generated:
        print("NOTE: Transcript is auto-generated (may contain errors)", file=sys.stderr)
        return 2

    return 0


def _cmd_audio(args: argparse.Namespace) -> int:
    """Handle the audio subcommand."""
    return extract_audio(args.url, Path(args.output))


if __name__ == "__main__":
    sys.exit(main())
