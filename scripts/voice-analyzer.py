#!/usr/bin/env python3
"""
Voice metrics analyzer CLI.

Extracts quantitative voice metrics from text samples and outputs as JSON or text report.
Designed for Phase 1 of voice system infrastructure.

Usage:
    python3 scripts/voice-analyzer.py analyze \
        --samples file1.md file2.md file3.md \
        --output profile.json

    python3 scripts/voice-analyzer.py analyze \
        --samples file1.md file2.md file3.md \
        --format text

    python3 scripts/voice-analyzer.py compare \
        --profile1 voice_a.json \
        --profile2 voice_b.json

Exit codes:
    0 = success
    1 = error
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ============================================================================
# Constants
# ============================================================================

CONTRACTIONS = {
    "can't",
    "won't",
    "it's",
    "don't",
    "isn't",
    "i'm",
    "you're",
    "we're",
    "they're",
    "he's",
    "she's",
    "that's",
    "what's",
    "there's",
    "here's",
    "who's",
    "how's",
    "let's",
    "couldn't",
    "wouldn't",
    "shouldn't",
    "didn't",
    "hasn't",
    "haven't",
    "hadn't",
    "wasn't",
    "weren't",
    "aren't",
    "i've",
    "you've",
    "we've",
    "they've",
    "i'd",
    "you'd",
    "he'd",
    "she'd",
    "we'd",
    "they'd",
    "i'll",
    "you'll",
    "he'll",
    "she'll",
    "we'll",
    "they'll",
    "it'll",
    "ain't",
    "y'all",
    "gonna",
    "wanna",
    "gotta",
    "kinda",
    "sorta",
}

# Expanded forms that could be contracted
EXPANDABLE_FORMS = {
    "cannot",
    "will not",
    "it is",
    "do not",
    "is not",
    "i am",
    "you are",
    "we are",
    "they are",
    "he is",
    "she is",
    "that is",
    "what is",
    "there is",
    "here is",
    "who is",
    "how is",
    "let us",
    "could not",
    "would not",
    "should not",
    "did not",
    "has not",
    "have not",
    "had not",
    "was not",
    "were not",
    "are not",
    "i have",
    "you have",
    "we have",
    "they have",
    "i would",
    "you would",
    "he would",
    "she would",
    "we would",
    "they would",
    "i will",
    "you will",
    "he will",
    "she will",
    "we will",
    "they will",
    "it will",
    "going to",
    "want to",
    "got to",
    "kind of",
    "sort of",
}

FUNCTION_WORDS = {
    "the",
    "a",
    "an",
    "and",
    "but",
    "or",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "by",
    "from",
    "as",
    "is",
    "was",
    "are",
    "were",
    "be",
    "been",
    "being",
    "have",
    "has",
    "had",
    "do",
    "does",
    "did",
    "will",
    "would",
    "could",
    "should",
    "may",
    "might",
    "must",
    "can",
    "this",
    "that",
    "these",
    "those",
    "it",
    "its",
    "if",
    "then",
    "than",
    "so",
    "such",
    "no",
    "not",
    "only",
    "just",
    "also",
    "very",
    "too",
    "more",
    "most",
    "some",
    "any",
    "all",
    "each",
    "every",
    "both",
    "few",
    "many",
    "much",
    "other",
    "another",
    "same",
    "different",
    "however",
    "therefore",
    "thus",
    "hence",
    "moreover",
    "furthermore",
    "additionally",
    "nevertheless",
    "nonetheless",
    "although",
    "though",
    "while",
    "whereas",
    "because",
    "since",
    "unless",
    "until",
    "when",
    "where",
    "which",
    "who",
    "whom",
    "whose",
    "what",
    "how",
    "why",
    "whether",
}

FIRST_PERSON_PRONOUNS = {"i", "me", "my", "mine", "myself", "we", "us", "our", "ours", "ourselves"}
SECOND_PERSON_PRONOUNS = {"you", "your", "yours", "yourself", "yourselves"}
THIRD_PERSON_PRONOUNS = {
    "he",
    "him",
    "his",
    "himself",
    "she",
    "her",
    "hers",
    "herself",
    "it",
    "its",
    "itself",
    "they",
    "them",
    "their",
    "theirs",
    "themselves",
}

TRANSITION_WORDS = {
    "but",
    "so",
    "and",
    "also",
    "however",
    "therefore",
    "thus",
    "hence",
    "moreover",
    "furthermore",
    "additionally",
    "nevertheless",
    "nonetheless",
    "consequently",
    "meanwhile",
    "otherwise",
    "instead",
    "rather",
    "similarly",
    "likewise",
    "indeed",
    "certainly",
    "clearly",
    "obviously",
    "naturally",
    "finally",
    "ultimately",
    "overall",
    "basically",
    "essentially",
    "actually",
    "anyway",
    "besides",
    "still",
    "yet",
    "then",
    "now",
    "first",
    "second",
    "next",
    "later",
    "eventually",
    "subsequently",
    "previously",
    "formerly",
}

PRONOUN_STARTERS = {
    "i",
    "we",
    "you",
    "he",
    "she",
    "it",
    "they",
    "this",
    "that",
    "these",
    "those",
    "who",
    "which",
    "what",
}

CONJUNCTION_STARTERS = {
    "and",
    "but",
    "or",
    "so",
    "yet",
    "for",
    "nor",
    "because",
    "although",
    "though",
    "while",
    "whereas",
    "if",
    "unless",
    "until",
    "when",
    "where",
    "since",
    "as",
}

ARTICLE_STARTERS = {"the", "a", "an"}

ADVERB_STARTERS = {
    "however",
    "therefore",
    "thus",
    "hence",
    "moreover",
    "furthermore",
    "additionally",
    "nevertheless",
    "nonetheless",
    "consequently",
    "meanwhile",
    "otherwise",
    "instead",
    "rather",
    "similarly",
    "likewise",
    "indeed",
    "certainly",
    "clearly",
    "obviously",
    "naturally",
    "finally",
    "ultimately",
    "overall",
    "basically",
    "essentially",
    "actually",
    "anyway",
    "besides",
    "still",
    "now",
    "then",
    "here",
    "there",
    "never",
    "always",
    "often",
    "sometimes",
    "usually",
    "rarely",
    "perhaps",
    "maybe",
    "probably",
    "definitely",
    "absolutely",
    "simply",
    "just",
    "only",
    "even",
    "also",
    "too",
    "very",
    "really",
    "quite",
    "almost",
    "nearly",
}


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class VoiceProfile:
    """Complete voice metrics profile."""

    meta: dict[str, Any] = field(default_factory=dict)
    sentence_metrics: dict[str, Any] = field(default_factory=dict)
    punctuation_metrics: dict[str, Any] = field(default_factory=dict)
    word_metrics: dict[str, Any] = field(default_factory=dict)
    structure_metrics: dict[str, Any] = field(default_factory=dict)
    pattern_signatures: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "meta": self.meta,
            "sentence_metrics": self.sentence_metrics,
            "punctuation_metrics": self.punctuation_metrics,
            "word_metrics": self.word_metrics,
            "structure_metrics": self.structure_metrics,
            "pattern_signatures": self.pattern_signatures,
        }


@dataclass
class AnalysisResult:
    """Result of analysis operation."""

    status: str  # "success" or "error"
    data: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {"status": self.status}
        if self.data:
            result["data"] = self.data
        if self.errors:
            result["errors"] = self.errors
        return result


# ============================================================================
# Text Preprocessing
# ============================================================================


def strip_markdown(text: str) -> str:
    """Remove markdown formatting from text."""
    # Remove code blocks (fenced)
    text = re.sub(r"```[\s\S]*?```", "", text)

    # Remove inline code
    text = re.sub(r"`[^`]+`", "", text)

    # Remove headers (keep the text)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Remove links but keep text: [text](url) -> text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # Remove images: ![alt](url)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", "", text)

    # Remove bold/italic markers
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"__([^_]+)__", r"\1", text)
    text = re.sub(r"_([^_]+)_", r"\1", text)

    # Remove blockquotes
    text = re.sub(r"^>\s*", "", text, flags=re.MULTILINE)

    # Remove horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Remove list markers
    text = re.sub(r"^\s*[-*+]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)

    return text


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs on double newlines."""
    # Normalize line endings
    text = text.replace("\r\n", "\n")

    # Split on double newlines
    paragraphs = re.split(r"\n\s*\n", text)

    # Clean and filter empty paragraphs
    return [p.strip() for p in paragraphs if p.strip()]


def split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    # Handle common abbreviations that shouldn't split sentences
    text = re.sub(r"\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e)\.", r"\1<ABBR>", text)

    # Split on sentence-ending punctuation followed by space or end
    sentences = re.split(r"(?<=[.!?])\s+", text)

    # Restore abbreviations
    sentences = [s.replace("<ABBR>", ".") for s in sentences]

    # Clean and filter
    return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 1]


def tokenize_words(text: str) -> list[str]:
    """Tokenize text into words (lowercase)."""
    # Remove punctuation except apostrophes in contractions
    text = re.sub(r"[^\w\s']", " ", text)

    # Split and lowercase
    words = text.lower().split()

    # Filter empty and single-character tokens (except 'i' and 'a')
    return [w for w in words if len(w) > 1 or w in ("i", "a")]


# ============================================================================
# Metric Calculations
# ============================================================================


def calculate_sentence_metrics(sentences: list[str]) -> dict[str, Any]:
    """Calculate sentence-related metrics."""
    if not sentences:
        return {
            "length_distribution": {
                "short_3_10": 0.0,
                "medium_11_20": 0.0,
                "long_21_30": 0.0,
                "very_long_31_plus": 0.0,
            },
            "average_length": 0.0,
            "variance": 0.0,
            "max_consecutive_similar": 0,
        }

    # Calculate word counts for each sentence
    lengths = [len(tokenize_words(s)) for s in sentences]

    # Length distribution
    short = sum(1 for l in lengths if 3 <= l <= 10)
    medium = sum(1 for l in lengths if 11 <= l <= 20)
    long_ = sum(1 for l in lengths if 21 <= l <= 30)
    very_long = sum(1 for l in lengths if l >= 31)

    total = len(lengths)
    distribution = {
        "short_3_10": round(short / total, 3) if total > 0 else 0.0,
        "medium_11_20": round(medium / total, 3) if total > 0 else 0.0,
        "long_21_30": round(long_ / total, 3) if total > 0 else 0.0,
        "very_long_31_plus": round(very_long / total, 3) if total > 0 else 0.0,
    }

    # Average and variance
    avg_length = statistics.mean(lengths) if lengths else 0.0
    variance = statistics.stdev(lengths) if len(lengths) > 1 else 0.0

    # Max consecutive similar (within 5 words of each other)
    max_consecutive = 0
    current_streak = 1

    for i in range(1, len(lengths)):
        if abs(lengths[i] - lengths[i - 1]) <= 5:
            current_streak += 1
            max_consecutive = max(max_consecutive, current_streak)
        else:
            current_streak = 1

    if len(lengths) == 1 or (max_consecutive == 0 and len(lengths) > 0):
        max_consecutive = 1

    return {
        "length_distribution": distribution,
        "average_length": round(avg_length, 1),
        "variance": round(variance, 1),
        "max_consecutive_similar": max_consecutive,
    }


def calculate_punctuation_metrics(text: str, sentences: list[str]) -> dict[str, Any]:
    """Calculate punctuation-related metrics."""
    words = tokenize_words(text)
    word_count = len(words)
    sentence_count = len(sentences)

    # Count punctuation
    commas = text.count(",")
    exclamations = text.count("!")
    questions = text.count("?")
    em_dashes = text.count("--") + text.count("\u2014")  # -- and actual em-dash
    semicolons = text.count(";")

    return {
        "comma_density": round(commas / word_count, 3) if word_count > 0 else 0.0,
        "exclamation_rate": round(exclamations / sentence_count, 3) if sentence_count > 0 else 0.0,
        "question_rate": round(questions / sentence_count, 3) if sentence_count > 0 else 0.0,
        "em_dash_count": em_dashes,
        "semicolon_rate": round(semicolons / sentence_count, 3) if sentence_count > 0 else 0.0,
    }


def calculate_word_metrics(words: list[str]) -> dict[str, Any]:
    """Calculate word-related metrics."""
    if not words:
        return {
            "contraction_rate": 0.0,
            "first_person_rate": 0.0,
            "second_person_rate": 0.0,
            "function_word_signature": {},
        }

    word_count = len(words)

    # Contraction rate
    contractions_found = sum(1 for w in words if w in CONTRACTIONS)

    # Count expandable forms (2-word combinations)
    text_lower = " ".join(words)
    expandable_found = sum(1 for form in EXPANDABLE_FORMS if form in text_lower)

    total_contractable = contractions_found + expandable_found
    contraction_rate = round(contractions_found / total_contractable, 2) if total_contractable > 0 else 0.0

    # Person rates
    first_person = sum(1 for w in words if w in FIRST_PERSON_PRONOUNS)
    second_person = sum(1 for w in words if w in SECOND_PERSON_PRONOUNS)

    first_person_rate = round(first_person / word_count, 3) if word_count > 0 else 0.0
    second_person_rate = round(second_person / word_count, 3) if word_count > 0 else 0.0

    # Function word signature (top 20)
    function_word_counts: dict[str, int] = {}
    for word in words:
        if word in FUNCTION_WORDS:
            function_word_counts[word] = function_word_counts.get(word, 0) + 1

    # Sort by frequency and take top 20
    sorted_function_words = sorted(function_word_counts.items(), key=lambda x: x[1], reverse=True)[:20]

    function_word_signature = {word: round(count / word_count, 3) for word, count in sorted_function_words}

    return {
        "contraction_rate": contraction_rate,
        "first_person_rate": first_person_rate,
        "second_person_rate": second_person_rate,
        "function_word_signature": function_word_signature,
    }


def calculate_structure_metrics(paragraphs: list[str], sentences: list[str]) -> dict[str, Any]:
    """Calculate structure-related metrics."""
    if not paragraphs or not sentences:
        return {
            "avg_paragraph_sentences": 0.0,
            "fragment_rate": 0.0,
            "sentence_starters": {
                "pronoun": 0.0,
                "conjunction": 0.0,
                "article": 0.0,
                "adverb": 0.0,
                "other": 0.0,
            },
        }

    # Average sentences per paragraph
    sentences_per_paragraph = []
    for para in paragraphs:
        para_sentences = split_sentences(para)
        sentences_per_paragraph.append(len(para_sentences))

    avg_paragraph_sentences = statistics.mean(sentences_per_paragraph) if sentences_per_paragraph else 0.0

    # Fragment rate (sentences under 5 words)
    fragments = sum(1 for s in sentences if len(tokenize_words(s)) < 5)
    fragment_rate = round(fragments / len(sentences), 2) if sentences else 0.0

    # Sentence starters
    starter_counts = {
        "pronoun": 0,
        "conjunction": 0,
        "article": 0,
        "adverb": 0,
        "other": 0,
    }

    for sentence in sentences:
        words = tokenize_words(sentence)
        if not words:
            continue

        first_word = words[0]

        if first_word in PRONOUN_STARTERS:
            starter_counts["pronoun"] += 1
        elif first_word in CONJUNCTION_STARTERS:
            starter_counts["conjunction"] += 1
        elif first_word in ARTICLE_STARTERS:
            starter_counts["article"] += 1
        elif first_word in ADVERB_STARTERS:
            starter_counts["adverb"] += 1
        else:
            starter_counts["other"] += 1

    total_starters = sum(starter_counts.values())
    sentence_starters = {
        category: round(count / total_starters, 2) if total_starters > 0 else 0.0
        for category, count in starter_counts.items()
    }

    return {
        "avg_paragraph_sentences": round(avg_paragraph_sentences, 1),
        "fragment_rate": fragment_rate,
        "sentence_starters": sentence_starters,
    }


def calculate_pattern_signatures(text: str, sentences: list[str], paragraphs: list[str]) -> dict[str, Any]:
    """Calculate pattern signatures for voice identification."""
    words = tokenize_words(text)

    # Find transition words used
    transitions_used = set()
    transitions_avoided = set()

    for word in words:
        if word in TRANSITION_WORDS:
            transitions_used.add(word)

    # Common transitions not found
    common_transitions = {"but", "so", "and", "also", "however", "therefore", "moreover", "furthermore", "additionally"}
    transitions_avoided = common_transitions - transitions_used

    # Sort by frequency of occurrence
    transition_counts = {}
    for word in words:
        if word in TRANSITION_WORDS:
            transition_counts[word] = transition_counts.get(word, 0) + 1

    sorted_transitions = sorted(transition_counts.keys(), key=lambda x: transition_counts[x], reverse=True)

    # Opening patterns (first paragraph analysis)
    opening_patterns = []
    if paragraphs:
        first_para_sentences = split_sentences(paragraphs[0])
        if first_para_sentences:
            first_sentence = first_para_sentences[0]
            first_words = tokenize_words(first_sentence)

            if first_words:
                if first_sentence.endswith("?"):
                    opening_patterns.append("question")
                elif len(first_words) < 5:
                    opening_patterns.append("fragment")
                else:
                    opening_patterns.append("direct_statement")

                if first_words[0] in PRONOUN_STARTERS:
                    opening_patterns.append("pronoun_start")
                if first_words[0] in ADVERB_STARTERS:
                    opening_patterns.append("adverb_start")

    # Closing patterns (last paragraph analysis)
    closing_patterns = []
    if paragraphs:
        last_para_sentences = split_sentences(paragraphs[-1])
        if last_para_sentences:
            last_sentence = last_para_sentences[-1]
            last_words = tokenize_words(last_sentence)

            if last_words:
                if last_sentence.endswith("?"):
                    closing_patterns.append("question")
                elif len(last_words) < 5:
                    closing_patterns.append("fragment")
                elif any(w in last_words for w in ["will", "going", "next", "future", "forward"]):
                    closing_patterns.append("forward_looking")
                else:
                    closing_patterns.append("statement")

                # Check for callback (reference to opening)
                if paragraphs and len(paragraphs) > 1:
                    first_para_words = set(tokenize_words(paragraphs[0]))
                    last_para_words = set(last_words)
                    # Exclude common function words from callback detection
                    meaningful_first = first_para_words - FUNCTION_WORDS
                    meaningful_last = last_para_words - FUNCTION_WORDS
                    if meaningful_first & meaningful_last:
                        closing_patterns.append("callback")

    return {
        "transition_words": sorted_transitions[:10],  # Top 10 most used
        "avoided_transitions": sorted(list(transitions_avoided))[:5],
        "opening_patterns": opening_patterns or ["unknown"],
        "closing_patterns": closing_patterns or ["unknown"],
    }


# ============================================================================
# Main Analysis Functions
# ============================================================================


def analyze_text(text: str) -> VoiceProfile:
    """Analyze a single text and return voice metrics."""
    # Preprocess
    clean_text = strip_markdown(text)
    paragraphs = split_paragraphs(clean_text)
    sentences = split_sentences(clean_text)
    words = tokenize_words(clean_text)

    return VoiceProfile(
        meta={
            "samples_analyzed": 1,
            "total_words": len(words),
            "total_sentences": len(sentences),
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        sentence_metrics=calculate_sentence_metrics(sentences),
        punctuation_metrics=calculate_punctuation_metrics(clean_text, sentences),
        word_metrics=calculate_word_metrics(words),
        structure_metrics=calculate_structure_metrics(paragraphs, sentences),
        pattern_signatures=calculate_pattern_signatures(clean_text, sentences, paragraphs),
    )


def analyze_samples(sample_paths: list[str | Path]) -> VoiceProfile:
    """
    Analyze multiple text samples and return aggregated voice profile.

    This function is designed to be imported and used programmatically:
        from voice_analyzer import analyze_samples
        profile = analyze_samples(["sample1.md", "sample2.md"])
    """
    all_text = []
    samples_analyzed = 0

    for path in sample_paths:
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Sample file not found: {path}")

        text = path.read_text(encoding="utf-8")
        all_text.append(text)
        samples_analyzed += 1

    # Combine all text
    combined_text = "\n\n".join(all_text)

    # Analyze combined text
    profile = analyze_text(combined_text)

    # Update meta with correct sample count
    profile.meta["samples_analyzed"] = samples_analyzed

    return profile


def compare_profiles(profile1: VoiceProfile, profile2: VoiceProfile) -> dict[str, Any]:
    """Compare two voice profiles and return differences."""
    differences: dict[str, Any] = {
        "summary": {},
        "sentence_metrics": {},
        "punctuation_metrics": {},
        "word_metrics": {},
        "structure_metrics": {},
        "pattern_signatures": {},
    }

    # Compare sentence metrics
    s1 = profile1.sentence_metrics
    s2 = profile2.sentence_metrics

    differences["sentence_metrics"] = {
        "average_length_diff": round(s1.get("average_length", 0) - s2.get("average_length", 0), 1),
        "variance_diff": round(s1.get("variance", 0) - s2.get("variance", 0), 1),
        "length_distribution_comparison": {
            "short_3_10": round(
                s1.get("length_distribution", {}).get("short_3_10", 0)
                - s2.get("length_distribution", {}).get("short_3_10", 0),
                3,
            ),
            "medium_11_20": round(
                s1.get("length_distribution", {}).get("medium_11_20", 0)
                - s2.get("length_distribution", {}).get("medium_11_20", 0),
                3,
            ),
            "long_21_30": round(
                s1.get("length_distribution", {}).get("long_21_30", 0)
                - s2.get("length_distribution", {}).get("long_21_30", 0),
                3,
            ),
            "very_long_31_plus": round(
                s1.get("length_distribution", {}).get("very_long_31_plus", 0)
                - s2.get("length_distribution", {}).get("very_long_31_plus", 0),
                3,
            ),
        },
    }

    # Compare punctuation metrics
    p1 = profile1.punctuation_metrics
    p2 = profile2.punctuation_metrics

    differences["punctuation_metrics"] = {
        "comma_density_diff": round(p1.get("comma_density", 0) - p2.get("comma_density", 0), 3),
        "exclamation_rate_diff": round(p1.get("exclamation_rate", 0) - p2.get("exclamation_rate", 0), 3),
        "question_rate_diff": round(p1.get("question_rate", 0) - p2.get("question_rate", 0), 3),
        "em_dash_count_diff": p1.get("em_dash_count", 0) - p2.get("em_dash_count", 0),
    }

    # Compare word metrics
    w1 = profile1.word_metrics
    w2 = profile2.word_metrics

    differences["word_metrics"] = {
        "contraction_rate_diff": round(w1.get("contraction_rate", 0) - w2.get("contraction_rate", 0), 2),
        "first_person_rate_diff": round(w1.get("first_person_rate", 0) - w2.get("first_person_rate", 0), 3),
        "second_person_rate_diff": round(w1.get("second_person_rate", 0) - w2.get("second_person_rate", 0), 3),
    }

    # Compare structure metrics
    st1 = profile1.structure_metrics
    st2 = profile2.structure_metrics

    differences["structure_metrics"] = {
        "avg_paragraph_sentences_diff": round(
            st1.get("avg_paragraph_sentences", 0) - st2.get("avg_paragraph_sentences", 0), 1
        ),
        "fragment_rate_diff": round(st1.get("fragment_rate", 0) - st2.get("fragment_rate", 0), 2),
    }

    # Compare pattern signatures
    ps1 = profile1.pattern_signatures
    ps2 = profile2.pattern_signatures

    transitions1 = set(ps1.get("transition_words", []))
    transitions2 = set(ps2.get("transition_words", []))

    differences["pattern_signatures"] = {
        "unique_to_profile1": sorted(list(transitions1 - transitions2)),
        "unique_to_profile2": sorted(list(transitions2 - transitions1)),
        "shared_transitions": sorted(list(transitions1 & transitions2)),
        "opening_patterns_match": ps1.get("opening_patterns") == ps2.get("opening_patterns"),
        "closing_patterns_match": ps1.get("closing_patterns") == ps2.get("closing_patterns"),
    }

    # Summary
    differences["summary"] = {
        "profile1_words": profile1.meta.get("total_words", 0),
        "profile2_words": profile2.meta.get("total_words", 0),
        "profile1_sentences": profile1.meta.get("total_sentences", 0),
        "profile2_sentences": profile2.meta.get("total_sentences", 0),
    }

    return differences


# ============================================================================
# Output Formatting
# ============================================================================


def format_profile_text(profile: VoiceProfile) -> str:
    """Format profile as human-readable text."""
    lines = []

    lines.append("=" * 60)
    lines.append("VOICE PROFILE ANALYSIS")
    lines.append("=" * 60)
    lines.append("")

    # Meta
    lines.append("OVERVIEW")
    lines.append("-" * 40)
    lines.append(f"  Samples analyzed: {profile.meta.get('samples_analyzed', 0)}")
    lines.append(f"  Total words: {profile.meta.get('total_words', 0):,}")
    lines.append(f"  Total sentences: {profile.meta.get('total_sentences', 0):,}")
    lines.append(f"  Generated: {profile.meta.get('generated_at', 'N/A')}")
    lines.append("")

    # Sentence metrics
    lines.append("SENTENCE METRICS")
    lines.append("-" * 40)
    sm = profile.sentence_metrics
    lines.append(f"  Average length: {sm.get('average_length', 0)} words")
    lines.append(f"  Variance: {sm.get('variance', 0)}")
    lines.append(f"  Max consecutive similar: {sm.get('max_consecutive_similar', 0)}")
    lines.append("  Length distribution:")
    ld = sm.get("length_distribution", {})
    lines.append(f"    Short (3-10):      {ld.get('short_3_10', 0):.1%}")
    lines.append(f"    Medium (11-20):    {ld.get('medium_11_20', 0):.1%}")
    lines.append(f"    Long (21-30):      {ld.get('long_21_30', 0):.1%}")
    lines.append(f"    Very long (31+):   {ld.get('very_long_31_plus', 0):.1%}")
    lines.append("")

    # Punctuation metrics
    lines.append("PUNCTUATION METRICS")
    lines.append("-" * 40)
    pm = profile.punctuation_metrics
    lines.append(f"  Comma density: {pm.get('comma_density', 0):.3f} (per word)")
    lines.append(f"  Exclamation rate: {pm.get('exclamation_rate', 0):.3f} (per sentence)")
    lines.append(f"  Question rate: {pm.get('question_rate', 0):.3f} (per sentence)")
    lines.append(f"  Em-dash count: {pm.get('em_dash_count', 0)}")
    lines.append(f"  Semicolon rate: {pm.get('semicolon_rate', 0):.3f} (per sentence)")
    lines.append("")

    # Word metrics
    lines.append("WORD METRICS")
    lines.append("-" * 40)
    wm = profile.word_metrics
    lines.append(f"  Contraction rate: {wm.get('contraction_rate', 0):.0%}")
    lines.append(f"  First person rate: {wm.get('first_person_rate', 0):.1%}")
    lines.append(f"  Second person rate: {wm.get('second_person_rate', 0):.1%}")
    lines.append("  Top function words:")
    fw = wm.get("function_word_signature", {})
    for word, freq in list(fw.items())[:10]:
        lines.append(f"    {word}: {freq:.3f}")
    lines.append("")

    # Structure metrics
    lines.append("STRUCTURE METRICS")
    lines.append("-" * 40)
    stm = profile.structure_metrics
    lines.append(f"  Avg paragraph sentences: {stm.get('avg_paragraph_sentences', 0)}")
    lines.append(f"  Fragment rate: {stm.get('fragment_rate', 0):.0%}")
    lines.append("  Sentence starters:")
    ss = stm.get("sentence_starters", {})
    for category, rate in ss.items():
        lines.append(f"    {category}: {rate:.0%}")
    lines.append("")

    # Pattern signatures
    lines.append("PATTERN SIGNATURES")
    lines.append("-" * 40)
    ps = profile.pattern_signatures
    lines.append(f"  Transition words: {', '.join(ps.get('transition_words', []))}")
    lines.append(f"  Avoided transitions: {', '.join(ps.get('avoided_transitions', []))}")
    lines.append(f"  Opening patterns: {', '.join(ps.get('opening_patterns', []))}")
    lines.append(f"  Closing patterns: {', '.join(ps.get('closing_patterns', []))}")
    lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


def format_comparison_text(comparison: dict[str, Any], name1: str, name2: str) -> str:
    """Format comparison as human-readable text."""
    lines = []

    lines.append("=" * 60)
    lines.append(f"VOICE PROFILE COMPARISON: {name1} vs {name2}")
    lines.append("=" * 60)
    lines.append("")

    # Summary
    summary = comparison.get("summary", {})
    lines.append("OVERVIEW")
    lines.append("-" * 40)
    lines.append(
        f"  {name1}: {summary.get('profile1_words', 0):,} words, {summary.get('profile1_sentences', 0):,} sentences"
    )
    lines.append(
        f"  {name2}: {summary.get('profile2_words', 0):,} words, {summary.get('profile2_sentences', 0):,} sentences"
    )
    lines.append("")

    # Sentence differences
    sm = comparison.get("sentence_metrics", {})
    lines.append("SENTENCE METRICS DIFFERENCE")
    lines.append("-" * 40)
    lines.append(f"  Average length: {sm.get('average_length_diff', 0):+.1f} words")
    lines.append(f"  Variance: {sm.get('variance_diff', 0):+.1f}")
    ld = sm.get("length_distribution_comparison", {})
    lines.append("  Length distribution:")
    lines.append(f"    Short:     {ld.get('short_3_10', 0):+.1%}")
    lines.append(f"    Medium:    {ld.get('medium_11_20', 0):+.1%}")
    lines.append(f"    Long:      {ld.get('long_21_30', 0):+.1%}")
    lines.append(f"    Very long: {ld.get('very_long_31_plus', 0):+.1%}")
    lines.append("")

    # Punctuation differences
    pm = comparison.get("punctuation_metrics", {})
    lines.append("PUNCTUATION METRICS DIFFERENCE")
    lines.append("-" * 40)
    lines.append(f"  Comma density: {pm.get('comma_density_diff', 0):+.3f}")
    lines.append(f"  Exclamation rate: {pm.get('exclamation_rate_diff', 0):+.3f}")
    lines.append(f"  Question rate: {pm.get('question_rate_diff', 0):+.3f}")
    lines.append(f"  Em-dash count: {pm.get('em_dash_count_diff', 0):+d}")
    lines.append("")

    # Word differences
    wm = comparison.get("word_metrics", {})
    lines.append("WORD METRICS DIFFERENCE")
    lines.append("-" * 40)
    lines.append(f"  Contraction rate: {wm.get('contraction_rate_diff', 0):+.0%}")
    lines.append(f"  First person rate: {wm.get('first_person_rate_diff', 0):+.1%}")
    lines.append(f"  Second person rate: {wm.get('second_person_rate_diff', 0):+.1%}")
    lines.append("")

    # Structure differences
    stm = comparison.get("structure_metrics", {})
    lines.append("STRUCTURE METRICS DIFFERENCE")
    lines.append("-" * 40)
    lines.append(f"  Avg paragraph sentences: {stm.get('avg_paragraph_sentences_diff', 0):+.1f}")
    lines.append(f"  Fragment rate: {stm.get('fragment_rate_diff', 0):+.0%}")
    lines.append("")

    # Pattern signature comparison
    ps = comparison.get("pattern_signatures", {})
    lines.append("PATTERN SIGNATURE COMPARISON")
    lines.append("-" * 40)
    lines.append(f"  Unique to {name1}: {', '.join(ps.get('unique_to_profile1', [])) or 'none'}")
    lines.append(f"  Unique to {name2}: {', '.join(ps.get('unique_to_profile2', [])) or 'none'}")
    lines.append(f"  Shared transitions: {', '.join(ps.get('shared_transitions', [])) or 'none'}")
    lines.append(f"  Opening patterns match: {'Yes' if ps.get('opening_patterns_match') else 'No'}")
    lines.append(f"  Closing patterns match: {'Yes' if ps.get('closing_patterns_match') else 'No'}")
    lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)


# ============================================================================
# CLI Commands
# ============================================================================


def cmd_analyze(args: argparse.Namespace) -> AnalysisResult:
    """Handle analyze command."""
    sample_paths = args.samples

    # Validate all files exist
    missing = [p for p in sample_paths if not Path(p).exists()]
    if missing:
        return AnalysisResult(
            status="error",
            errors=[f"Sample file not found: {p}" for p in missing],
        )

    try:
        profile = analyze_samples(sample_paths)
    except Exception as e:
        return AnalysisResult(status="error", errors=[str(e)])

    # Output to file or stdout
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(profile.to_dict(), indent=2),
            encoding="utf-8",
        )
        return AnalysisResult(
            status="success",
            data={
                "message": f"Profile written to {args.output}",
                "profile": profile.to_dict(),
            },
        )

    return AnalysisResult(status="success", data={"profile": profile.to_dict()})


def cmd_compare(args: argparse.Namespace) -> AnalysisResult:
    """Handle compare command."""
    # Load profiles
    path1 = Path(args.profile1)
    path2 = Path(args.profile2)

    if not path1.exists():
        return AnalysisResult(status="error", errors=[f"Profile not found: {path1}"])
    if not path2.exists():
        return AnalysisResult(status="error", errors=[f"Profile not found: {path2}"])

    try:
        data1 = json.loads(path1.read_text(encoding="utf-8"))
        data2 = json.loads(path2.read_text(encoding="utf-8"))

        profile1 = VoiceProfile(
            meta=data1.get("meta", {}),
            sentence_metrics=data1.get("sentence_metrics", {}),
            punctuation_metrics=data1.get("punctuation_metrics", {}),
            word_metrics=data1.get("word_metrics", {}),
            structure_metrics=data1.get("structure_metrics", {}),
            pattern_signatures=data1.get("pattern_signatures", {}),
        )

        profile2 = VoiceProfile(
            meta=data2.get("meta", {}),
            sentence_metrics=data2.get("sentence_metrics", {}),
            punctuation_metrics=data2.get("punctuation_metrics", {}),
            word_metrics=data2.get("word_metrics", {}),
            structure_metrics=data2.get("structure_metrics", {}),
            pattern_signatures=data2.get("pattern_signatures", {}),
        )

        comparison = compare_profiles(profile1, profile2)

        return AnalysisResult(
            status="success",
            data={
                "comparison": comparison,
                "profile1_name": path1.stem,
                "profile2_name": path2.stem,
            },
        )

    except json.JSONDecodeError as e:
        return AnalysisResult(status="error", errors=[f"Invalid JSON: {e}"])
    except Exception as e:
        return AnalysisResult(status="error", errors=[str(e)])


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="Voice metrics analyzer CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # analyze command
    analyze_parser = subparsers.add_parser("analyze", help="Analyze text samples")
    analyze_parser.add_argument(
        "--samples",
        nargs="+",
        required=True,
        help="Paths to sample text files",
    )
    analyze_parser.add_argument(
        "--output",
        "-o",
        help="Output file path for JSON profile (optional, prints to stdout if not specified)",
    )
    analyze_parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )

    # compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two voice profiles")
    compare_parser.add_argument(
        "--profile1",
        required=True,
        help="Path to first voice profile JSON",
    )
    compare_parser.add_argument(
        "--profile2",
        required=True,
        help="Path to second voice profile JSON",
    )
    compare_parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )

    return parser


def main() -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Dispatch to command handler
    if args.command == "analyze":
        result = cmd_analyze(args)

        if result.status == "error":
            print(json.dumps(result.to_dict(), indent=2), file=sys.stderr)
            return 1

        # Output based on format
        if args.format == "text":
            profile_data = result.data.get("profile", {})
            profile = VoiceProfile(
                meta=profile_data.get("meta", {}),
                sentence_metrics=profile_data.get("sentence_metrics", {}),
                punctuation_metrics=profile_data.get("punctuation_metrics", {}),
                word_metrics=profile_data.get("word_metrics", {}),
                structure_metrics=profile_data.get("structure_metrics", {}),
                pattern_signatures=profile_data.get("pattern_signatures", {}),
            )
            print(format_profile_text(profile))
        else:
            # JSON output
            if args.output:
                print(f"Profile written to {args.output}")
            else:
                print(json.dumps(result.data.get("profile", {}), indent=2))

    elif args.command == "compare":
        result = cmd_compare(args)

        if result.status == "error":
            print(json.dumps(result.to_dict(), indent=2), file=sys.stderr)
            return 1

        # Output based on format
        if args.format == "text":
            comparison = result.data.get("comparison", {})
            name1 = result.data.get("profile1_name", "Profile 1")
            name2 = result.data.get("profile2_name", "Profile 2")
            print(format_comparison_text(comparison, name1, name2))
        else:
            print(json.dumps(result.data.get("comparison", {}), indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
