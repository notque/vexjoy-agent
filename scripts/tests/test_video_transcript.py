"""Tests for video-transcript.py -- URL parsing, subtitle parsing, output formatting."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

# Load kebab-case module via importlib (not a valid Python identifier)
_spec = importlib.util.spec_from_file_location(
    "video_transcript", Path(__file__).resolve().parent.parent / "video-transcript.py"
)
video_transcript = importlib.util.module_from_spec(_spec)
sys.modules["video_transcript"] = video_transcript
_spec.loader.exec_module(video_transcript)

from video_transcript import (  # noqa: E402
    TranscriptResult,
    TranscriptSegment,
    _clean_subtitle_text,
    _parse_srt,
    _parse_timestamp,
    _parse_vtt,
    extract_youtube_id,
)

# --- YouTube URL extraction ---


class TestExtractYouTubeId:
    """Test YouTube video ID extraction from various URL formats."""

    @pytest.mark.parametrize(
        "url,expected_id",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("http://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=120", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/live/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ],
    )
    def test_valid_youtube_urls(self, url: str, expected_id: str) -> None:
        assert extract_youtube_id(url) == expected_id

    @pytest.mark.parametrize(
        "url",
        [
            "https://vimeo.com/123456789",
            "https://twitch.tv/channel/video",
            "https://example.com/watch?v=abc",
            "not a url at all",
            "",
        ],
    )
    def test_non_youtube_urls_return_none(self, url: str) -> None:
        assert extract_youtube_id(url) is None


# --- Timestamp parsing ---


class TestParseTimestamp:
    """Test VTT/SRT timestamp string to seconds conversion."""

    @pytest.mark.parametrize(
        "ts,expected",
        [
            ("00:00:00.000", 0.0),
            ("00:00:01.500", 1.5),
            ("00:01:30.000", 90.0),
            ("01:00:00.000", 3600.0),
            ("00:05:23.456", 323.456),
            # MM:SS format (no hours)
            ("01:30.000", 90.0),
            ("05:23.456", 323.456),
            # SRT comma format (after replacement)
            ("00:00:01.500", 1.5),
        ],
    )
    def test_various_timestamp_formats(self, ts: str, expected: float) -> None:
        assert _parse_timestamp(ts) == pytest.approx(expected, abs=0.01)


# --- Subtitle text cleaning ---


class TestCleanSubtitleText:
    """Test stripping of VTT/SRT formatting artifacts."""

    def test_strip_html_tags(self) -> None:
        assert _clean_subtitle_text("<i>hello</i> world") == "hello world"

    def test_strip_bold_tags(self) -> None:
        assert _clean_subtitle_text("<b>important</b>") == "important"

    def test_strip_font_tags(self) -> None:
        assert _clean_subtitle_text('<font color="#CCCCCC">text</font>') == "text"

    def test_strip_vtt_cue_tags(self) -> None:
        assert _clean_subtitle_text("<c.colorCCCCCC>hello</c>") == "hello"

    def test_strip_positioning(self) -> None:
        result = _clean_subtitle_text("align:start position:10% hello")
        assert "align:" not in result
        assert "position:" not in result
        assert "hello" in result

    def test_strip_music_notes(self) -> None:
        assert _clean_subtitle_text("\u266a some music \u266b") == "some music"

    def test_collapse_whitespace(self) -> None:
        assert _clean_subtitle_text("hello    world") == "hello world"

    def test_noise_markers_return_empty(self) -> None:
        assert _clean_subtitle_text("[Music]") == ""
        assert _clean_subtitle_text("[Applause]") == ""
        assert _clean_subtitle_text("[Laughter]") == ""

    def test_clean_text_passes_through(self) -> None:
        assert _clean_subtitle_text("Hello, this is a normal sentence.") == "Hello, this is a normal sentence."


# --- VTT parsing ---


class TestParseVtt:
    """Test WebVTT subtitle file parsing."""

    def test_basic_vtt(self) -> None:
        vtt = textwrap.dedent("""\
            WEBVTT
            Kind: captions
            Language: en

            00:00:01.000 --> 00:00:04.000
            Hello, welcome to this video.

            00:00:04.000 --> 00:00:08.000
            Today we're going to talk about Python.
        """)
        segments = _parse_vtt(vtt)
        assert len(segments) == 2
        assert segments[0].text == "Hello, welcome to this video."
        assert segments[0].start == pytest.approx(1.0)
        assert segments[1].text == "Today we're going to talk about Python."

    def test_vtt_deduplicates_rolling_captions(self) -> None:
        vtt = textwrap.dedent("""\
            WEBVTT

            00:00:01.000 --> 00:00:02.000
            Hello world

            00:00:02.000 --> 00:00:03.000
            Hello world

            00:00:03.000 --> 00:00:05.000
            Something new
        """)
        segments = _parse_vtt(vtt)
        texts = [s.text for s in segments]
        assert texts == ["Hello world", "Something new"]

    def test_vtt_strips_html_in_cues(self) -> None:
        vtt = textwrap.dedent("""\
            WEBVTT

            00:00:01.000 --> 00:00:04.000
            <i>Italicized speech</i>
        """)
        segments = _parse_vtt(vtt)
        assert segments[0].text == "Italicized speech"

    def test_vtt_skips_music_markers(self) -> None:
        vtt = textwrap.dedent("""\
            WEBVTT

            00:00:01.000 --> 00:00:04.000
            [Music]

            00:00:04.000 --> 00:00:08.000
            Actual speech here.
        """)
        segments = _parse_vtt(vtt)
        assert len(segments) == 1
        assert segments[0].text == "Actual speech here."

    def test_vtt_empty_returns_no_segments(self) -> None:
        vtt = "WEBVTT\n\n"
        segments = _parse_vtt(vtt)
        assert segments == []


# --- SRT parsing ---


class TestParseSrt:
    """Test SubRip (SRT) subtitle file parsing."""

    def test_basic_srt(self) -> None:
        srt = textwrap.dedent("""\
            1
            00:00:01,000 --> 00:00:04,000
            Hello from SRT format.

            2
            00:00:04,000 --> 00:00:08,000
            Second line of dialogue.
        """)
        segments = _parse_srt(srt)
        assert len(segments) == 2
        assert segments[0].text == "Hello from SRT format."
        assert segments[0].start == pytest.approx(1.0)

    def test_srt_deduplicates(self) -> None:
        srt = textwrap.dedent("""\
            1
            00:00:01,000 --> 00:00:02,000
            Repeated line

            2
            00:00:02,000 --> 00:00:03,000
            Repeated line

            3
            00:00:03,000 --> 00:00:05,000
            New line
        """)
        segments = _parse_srt(srt)
        texts = [s.text for s in segments]
        assert texts == ["Repeated line", "New line"]


# --- TranscriptResult formatting ---


class TestTranscriptResultFormat:
    """Test the output formatting methods on TranscriptResult."""

    @pytest.fixture()
    def sample_result(self) -> TranscriptResult:
        return TranscriptResult(
            url="https://youtube.com/watch?v=abc123",
            segments=[
                TranscriptSegment(start=0.0, end=4.5, text="Welcome to the show."),
                TranscriptSegment(start=4.5, end=9.0, text="Today we discuss testing."),
                TranscriptSegment(start=65.0, end=70.0, text="And that wraps it up."),
            ],
            language="en",
            auto_generated=False,
            method="youtube-transcript-api",
            title="Test Video",
        )

    def test_format_text_joins_paragraphs(self, sample_result: TranscriptResult) -> None:
        text = sample_result.format_text()
        assert text == "Welcome to the show. Today we discuss testing. And that wraps it up."

    def test_format_timestamped(self, sample_result: TranscriptResult) -> None:
        text = sample_result.format_timestamped()
        lines = text.split("\n")
        assert lines[0] == "[00:00] Welcome to the show."
        assert lines[1] == "[00:04] Today we discuss testing."
        assert lines[2] == "[01:05] And that wraps it up."

    def test_format_json_structure(self, sample_result: TranscriptResult) -> None:
        raw = sample_result.format_json()
        data = json.loads(raw)
        assert data["url"] == "https://youtube.com/watch?v=abc123"
        assert data["title"] == "Test Video"
        assert data["language"] == "en"
        assert data["auto_generated"] is False
        assert data["method"] == "youtube-transcript-api"
        assert len(data["segments"]) == 3
        assert "Welcome to the show." in data["full_text"]

    def test_full_text_property(self, sample_result: TranscriptResult) -> None:
        assert "Welcome to the show." in sample_result.full_text
        assert "And that wraps it up." in sample_result.full_text


# --- CLI argument parsing ---


_SCRIPT_PATH = str(Path(__file__).resolve().parent.parent / "video-transcript.py")


class TestCliHelp:
    """Test that CLI --help works without dependencies installed."""

    def test_help_exits_zero(self) -> None:
        result = subprocess.run(
            [sys.executable, _SCRIPT_PATH, "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "transcript" in result.stdout
        assert "audio" in result.stdout

    def test_transcript_subcommand_help(self) -> None:
        result = subprocess.run(
            [sys.executable, _SCRIPT_PATH, "transcript", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--lang" in result.stdout
        assert "--timestamps" in result.stdout
        assert "--json" in result.stdout

    def test_audio_subcommand_help(self) -> None:
        result = subprocess.run(
            [sys.executable, _SCRIPT_PATH, "audio", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        assert "--output" in result.stdout
