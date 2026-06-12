#!/usr/bin/env python3
"""Deterministic stylometry lenses for the voice system.

ADR voice-stylometry-upgrade. Three lenses plus decay metadata:
1. Burstiness band — sentence-length variance band measured from the author
   corpus; drafts whose variance falls outside the band are flagged.
2. Punctuation profile — em-dash/semicolon/parenthetical rates classified as
   never/rare/habitual; drafts that deviate from the author's class are flagged.
3. Inverse AI-tell detectors — corrective antithesis ("not X, it's Y"),
   throat-clearing temporal openers, uniform paragraph shapes.

Decay: profiles carry analyzed_at + refresh_after_days; a stale profile emits
an advisory finding that never blocks (verdict stays "pass").

Usage:
    python3 scripts/voice-stylometry.py band --samples s1.md s2.md \
        [--refresh-after-days 90] [--analyzed-at ISO] > stylometry.json
    python3 scripts/voice-stylometry.py check --profile profile.json \
        --draft draft.md [--now ISO]

Exit codes (check): 0 = pass (advisory findings allowed), 1 = fail, 2 = usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Severity ladder: error/warning fail the check; advisory never blocks.
BLOCKING_SEVERITIES = ("error", "warning")

# Punctuation class thresholds (rate = marks per sentence).
RARE_THRESHOLD = 0.15

# Burstiness band: corpus stdev s -> accepted draft stdev in [0.5*s, 1.5*s].
BAND_LOW_FACTOR = 0.5
BAND_HIGH_FACTOR = 1.5
MIN_SENTENCES_FOR_BURSTINESS = 4

# Uniform-paragraph tell: need this many paragraphs, each with >= 2 sentences,
# all with the same sentence count.
MIN_PARAGRAPHS_FOR_UNIFORMITY = 4

DEFAULT_REFRESH_AFTER_DAYS = 90

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")

# Curly apostrophe and en dash spelled as escapes so the regexes match
# typographic drafts without tripping ambiguous-Unicode lint (RUF001).
_APO = "'\u2019"
# "not X, it's Y" within one sentence.
_ANTITHESIS_INLINE = re.compile(
    rf"\bnot\s+(?:just\s+|only\s+|merely\s+|about\s+)?[\w{_APO}-]+(?:\s+[\w{_APO}-]+){{0,6}}"
    rf"\s*[,;—\u2013]\s*(?:it|that|this|they)(?:[{_APO}]s|[{_APO}]re|\s+is|\s+was|\s+are)\b",
    re.IGNORECASE,
)
# "It is not X. It is Y." across a sentence boundary.
_ANTITHESIS_PAIR = re.compile(
    rf"\b(?:it|this|that)(?:[{_APO}]s|\s+is)\s+not\b[^.!?\n]{{0,80}}[.!?]\s+(?:it|this|that)(?:[{_APO}]s|\s+is)\b",
    re.IGNORECASE,
)
_TEMPORAL_OPENER = re.compile(
    r"^(?:in\s+today'?s|in\s+an\s+era|in\s+a\s+world|in\s+recent\s+(?:years|months|times)"
    r"|in\s+the\s+(?:modern|digital|current)\s+(?:age|era|world|landscape)"
    r"|as\s+we\s+(?:move|navigate|enter)|nowadays|now\s+more\s+than\s+ever)\b",
    re.IGNORECASE,
)
_EM_DASH = re.compile(r"—|--")


@dataclass
class Finding:
    """One structured violation: rule, location, severity, human message."""

    rule_id: str
    severity: str
    span: tuple[int, int]
    line: int
    message: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "span": {"start": self.span[0], "end": self.span[1]},
            "line": self.line,
            "message": self.message,
        }


# ---------------------------------------------------------------------------
# Text primitives
# ---------------------------------------------------------------------------


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on terminal punctuation. Deterministic, no NLP."""
    parts = _SENTENCE_SPLIT.split(text.strip())
    return [p.strip() for p in parts if p.strip()]


def sentence_word_counts(text: str) -> list[int]:
    return [len(s.split()) for s in split_sentences(text)]


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _doc_finding(rule_id: str, severity: str, text: str, message: str) -> Finding:
    return Finding(rule_id=rule_id, severity=severity, span=(0, len(text)), line=1, message=message)


# ---------------------------------------------------------------------------
# Lens 1: burstiness band
# ---------------------------------------------------------------------------


def _stdev(values: list[int]) -> float:
    return statistics.pstdev(values) if len(values) >= 2 else 0.0


def compute_burstiness(sample_texts: list[str]) -> dict:
    """Pool sentence lengths across the corpus; band = [0.5*stdev, 1.5*stdev]."""
    lengths: list[int] = []
    for text in sample_texts:
        lengths.extend(sentence_word_counts(text))
    stdev = round(_stdev(lengths), 2)
    return {
        "stdev": stdev,
        "band": {
            "min": round(BAND_LOW_FACTOR * stdev, 2),
            "max": round(BAND_HIGH_FACTOR * stdev, 2),
        },
    }


def check_burstiness(profile: dict, draft: str) -> list[Finding]:
    """Flag drafts whose sentence-length stdev falls outside the author band."""
    band = profile.get("stylometry", {}).get("burstiness", {}).get("band")
    if not band:
        return []
    counts = sentence_word_counts(draft)
    if len(counts) < MIN_SENTENCES_FOR_BURSTINESS:
        return []
    draft_stdev = round(_stdev(counts), 2)
    if band["min"] <= draft_stdev <= band["max"]:
        return []
    return [
        _doc_finding(
            "burstiness.band",
            "warning",
            draft,
            f"sentence-length stdev {draft_stdev} outside author band "
            f"[{band['min']}, {band['max']}] (uniform length is an AI tell)",
        )
    ]


# ---------------------------------------------------------------------------
# Lens 2: punctuation profile
# ---------------------------------------------------------------------------


def classify_rate(rate: float) -> str:
    if rate == 0:
        return "never"
    if rate <= RARE_THRESHOLD:
        return "rare"
    return "habitual"


def _punctuation_rates(text: str) -> dict[str, float]:
    sentences = max(len(split_sentences(text)), 1)
    return {
        "em_dash": len(_EM_DASH.findall(text)) / sentences,
        "semicolon": text.count(";") / sentences,
        "parenthetical": text.count("(") / sentences,
    }


def compute_punctuation(sample_texts: list[str]) -> dict:
    """Per-mark rate (marks per sentence) and never/rare/habitual class."""
    corpus = "\n".join(sample_texts)
    rates = _punctuation_rates(corpus)
    return {mark: {"rate": round(rate, 3), "class": classify_rate(rate)} for mark, rate in rates.items()}


def check_punctuation(profile: dict, draft: str) -> list[Finding]:
    """Flag marks whose draft class deviates from the author's class."""
    punct = profile.get("stylometry", {}).get("punctuation")
    if not punct:
        return []
    findings: list[Finding] = []
    draft_rates = _punctuation_rates(draft)
    for mark, expected in punct.items():
        if mark not in draft_rates:
            continue
        draft_class = classify_rate(draft_rates[mark])
        if draft_class != expected["class"]:
            findings.append(
                _doc_finding(
                    f"punctuation.{mark}",
                    "warning",
                    draft,
                    f"{mark} usage is {draft_class} in draft but {expected['class']} for this author",
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Lens 3: inverse AI-tell detectors
# ---------------------------------------------------------------------------


def check_corrective_antithesis(draft: str) -> list[Finding]:
    """Detect 'not X, it's Y' inline and 'It is not X. It is Y.' pair forms."""
    findings: list[Finding] = []
    for pattern in (_ANTITHESIS_INLINE, _ANTITHESIS_PAIR):
        for m in pattern.finditer(draft):
            findings.append(
                Finding(
                    rule_id="ai_tell.corrective_antithesis",
                    severity="error",
                    span=(m.start(), m.end()),
                    line=_line_of(draft, m.start()),
                    message=f"corrective antithesis: {draft[m.start() : m.end()]!r}",
                )
            )
    return findings


def _paragraphs_with_offsets(text: str) -> list[tuple[int, str]]:
    paragraphs: list[tuple[int, str]] = []
    offset = 0
    for chunk in _PARAGRAPH_SPLIT.split(text):
        start = text.index(chunk, offset)
        if chunk.strip():
            lead = len(chunk) - len(chunk.lstrip())
            paragraphs.append((start + lead, chunk.strip()))
        offset = start + len(chunk)
    return paragraphs


def check_temporal_openers(draft: str) -> list[Finding]:
    """Detect throat-clearing temporal openers at paragraph starts."""
    findings: list[Finding] = []
    for start, para in _paragraphs_with_offsets(draft):
        m = _TEMPORAL_OPENER.match(para)
        if m:
            findings.append(
                Finding(
                    rule_id="ai_tell.temporal_opener",
                    severity="error",
                    span=(start, start + m.end()),
                    line=_line_of(draft, start),
                    message=f"throat-clearing temporal opener: {m.group(0)!r}",
                )
            )
    return findings


def check_uniform_paragraphs(draft: str) -> list[Finding]:
    """Flag any run of >=4 consecutive paragraphs sharing one sentence count (>=2 each)."""
    paragraphs = _paragraphs_with_offsets(draft)
    counts = [len(split_sentences(para)) for _, para in paragraphs]
    findings: list[Finding] = []
    run_start = 0
    for i in range(len(counts) + 1):
        if i < len(counts) and counts[i] == counts[run_start]:
            continue
        run_len = i - run_start
        if run_len >= MIN_PARAGRAPHS_FOR_UNIFORMITY and counts[run_start] >= 2:
            span_start = paragraphs[run_start][0]
            last_offset, last_para = paragraphs[i - 1]
            findings.append(
                Finding(
                    rule_id="ai_tell.uniform_paragraphs",
                    severity="error",
                    span=(span_start, last_offset + len(last_para)),
                    line=_line_of(draft, span_start),
                    message=f"{run_len} consecutive paragraphs all have exactly "
                    f"{counts[run_start]} sentences (uniform shape is an AI tell)",
                )
            )
        run_start = i
    return findings


# ---------------------------------------------------------------------------
# Profile decay
# ---------------------------------------------------------------------------


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def check_decay(profile: dict, now: datetime) -> list[Finding]:
    """Advisory when profile is older than its refresh window. Never blocks."""
    analyzed_at = profile.get("analyzed_at")
    refresh_days = profile.get("refresh_after_days")
    if not analyzed_at or not refresh_days:
        return []
    expires = _parse_iso(analyzed_at) + timedelta(days=int(refresh_days))
    if now <= expires:
        return []
    age_days = (now - _parse_iso(analyzed_at)).days
    return [
        Finding(
            rule_id="profile.stale",
            severity="advisory",
            span=(0, 0),
            line=1,
            message=f"profile analyzed {age_days} days ago, refresh window is "
            f"{refresh_days} days; re-run the analyzer on fresh samples",
        )
    ]


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def build_band_profile(
    sample_texts: list[str],
    refresh_after_days: int = DEFAULT_REFRESH_AFTER_DAYS,
    analyzed_at: datetime | None = None,
) -> dict:
    """Build the add-only profile block: stylometry bands + decay metadata."""
    analyzed = analyzed_at or datetime.now(timezone.utc)
    return {
        "stylometry": {
            "burstiness": compute_burstiness(sample_texts),
            "punctuation": compute_punctuation(sample_texts),
        },
        "analyzed_at": analyzed.isoformat(),
        "refresh_after_days": refresh_after_days,
    }


def check_draft(profile: dict, draft: str, now: datetime | None = None) -> list[Finding]:
    """Run all lenses plus decay. Profiles missing new fields skip those lenses."""
    now = now or datetime.now(timezone.utc)
    findings: list[Finding] = []
    findings.extend(check_burstiness(profile, draft))
    findings.extend(check_punctuation(profile, draft))
    findings.extend(check_corrective_antithesis(draft))
    findings.extend(check_temporal_openers(draft))
    findings.extend(check_uniform_paragraphs(draft))
    findings.extend(check_decay(profile, now))
    return findings


def verdict(findings: list[Finding]) -> str:
    return "fail" if any(f.severity in BLOCKING_SEVERITIES for f in findings) else "pass"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _cmd_band(args: argparse.Namespace) -> int:
    texts = [Path(p).read_text() for p in args.samples]
    analyzed_at = _parse_iso(args.analyzed_at) if args.analyzed_at else None
    profile = build_band_profile(texts, refresh_after_days=args.refresh_after_days, analyzed_at=analyzed_at)
    print(json.dumps(profile, indent=2))
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    profile = json.loads(Path(args.profile).read_text())
    draft = Path(args.draft).read_text()
    now = _parse_iso(args.now) if args.now else None
    findings = check_draft(profile, draft, now=now)
    result = verdict(findings)
    print(json.dumps({"verdict": result, "findings": [f.to_dict() for f in findings]}, indent=2))
    return 0 if result == "pass" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic stylometry lenses for voice profiles.")
    sub = parser.add_subparsers(dest="command", required=True)

    band = sub.add_parser("band", help="Compute stylometry bands + decay metadata from author samples.")
    band.add_argument("--samples", nargs="+", required=True, help="Author sample files.")
    band.add_argument("--refresh-after-days", type=int, default=DEFAULT_REFRESH_AFTER_DAYS)
    band.add_argument("--analyzed-at", help="Override analyzed_at (ISO 8601) for reproducible output.")
    band.set_defaults(func=_cmd_band)

    check = sub.add_parser("check", help="Check a draft against a profile; exit 1 on violations.")
    check.add_argument("--profile", required=True, help="Voice profile JSON.")
    check.add_argument("--draft", required=True, help="Draft file to check.")
    check.add_argument("--now", help="Override current time (ISO 8601) for reproducible decay checks.")
    check.set_defaults(func=_cmd_check)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
