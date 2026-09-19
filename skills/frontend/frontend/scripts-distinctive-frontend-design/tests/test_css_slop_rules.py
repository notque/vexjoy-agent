"""Golden-fixture tests for css_slop_rules.scan_css.

Each rule has one positive fixture (rule fires) and one negative (rule silent).
The contrast canary covers both the hex and the oklch color paths.
"""

from __future__ import annotations

import sys
import time
from importlib import import_module
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
slop = import_module("css_slop_rules")
scan_css = slop.scan_css


def ids(css: str) -> set[str]:
    """Return the set of rule_ids fired for a CSS string."""
    return {f.rule_id for f in scan_css(css)}


# --- transition-all ---


def test_transition_all_fires() -> None:
    css = ".btn { transition: all 0.2s ease; }"
    assert "transition-all" in ids(css)


def test_transition_all_silent_on_named_property() -> None:
    css = ".btn { transition: opacity 0.2s ease, transform 0.2s ease; }"
    assert "transition-all" not in ids(css)


# --- universal-hover-scale ---


def test_universal_hover_scale_fires() -> None:
    css = ".card:hover { transform: scale(1.05); }"
    assert "universal-hover-scale" in ids(css)


def test_universal_hover_scale_silent_when_hover_does_more() -> None:
    css = ".card:hover { transform: scale(1.05); box-shadow: 0 4px 12px #0003; }"
    assert "universal-hover-scale" not in ids(css)


# --- gradient-text-headline ---


def test_gradient_text_headline_fires_webkit() -> None:
    css = "h1 { -webkit-background-clip: text; color: transparent; }"
    assert "gradient-text-headline" in ids(css)


def test_gradient_text_headline_fires_standard() -> None:
    css = "h2 { background-clip: text; }"
    assert "gradient-text-headline" in ids(css)


def test_gradient_text_headline_silent_on_body() -> None:
    css = ".badge { -webkit-background-clip: text; }"
    assert "gradient-text-headline" not in ids(css)


# --- focus-ring-fade ---


def test_focus_ring_fade_fires() -> None:
    css = ".input:focus { outline: 2px solid #09f; transition: outline 0.3s ease; }"
    assert "focus-ring-fade" in ids(css)


def test_focus_ring_fade_silent_when_instant() -> None:
    css = ".input:focus { outline: 2px solid #09f; }"
    assert "focus-ring-fade" not in ids(css)


# --- emoji-feature-icon ---


def test_emoji_feature_icon_fires() -> None:
    css = '.feature li::before { content: "\U0001f680"; }'
    assert "emoji-feature-icon" in ids(css)


def test_emoji_feature_icon_silent_on_text_content() -> None:
    css = '.tag::before { content: "New"; }'
    assert "emoji-feature-icon" not in ids(css)


# --- two-line-cta ---


def test_two_line_cta_fires() -> None:
    html = '<button class="cta">Start your free<br>trial today</button>'
    assert "two-line-cta" in ids(html)


def test_two_line_cta_silent_on_single_line() -> None:
    html = '<button class="cta">Get started</button>'
    assert "two-line-cta" not in ids(html)


# --- contrast-canary (hex path) ---


def test_contrast_canary_fires_hex() -> None:
    # dark-gray text on a marginally different dark-gray surface (black-on-black slop)
    css = ".x { color: #1a1a1a; background-color: #1e1e1e; }"
    assert "contrast-canary" in ids(css)


def test_contrast_canary_silent_hex_high_contrast() -> None:
    css = ".x { color: #ffffff; background-color: #111111; }"
    assert "contrast-canary" not in ids(css)


# --- contrast-canary (oklch path) ---


def test_contrast_canary_fires_oklch() -> None:
    css = ".y { color: oklch(0.20 0.02 250); background-color: oklch(0.22 0.03 250); }"
    assert "contrast-canary" in ids(css)


def test_contrast_canary_silent_oklch_high_contrast() -> None:
    css = ".y { color: oklch(0.95 0.02 250); background-color: oklch(0.20 0.03 250); }"
    assert "contrast-canary" not in ids(css)


# --- Finding shape contract ---


def test_finding_has_required_fields() -> None:
    findings = scan_css(".btn { transition: all 0.2s; }")
    assert findings
    f = findings[0]
    assert f.rule_id
    assert f.severity == "warning"
    assert isinstance(f.message, str) and f.message
    assert isinstance(f.line, int) and f.line >= 1


def test_clean_css_silent() -> None:
    css = ".btn { transition: opacity 0.2s ease; color: #1a1a1a; background: #fafafa; }"
    assert scan_css(css) == []


# --- ReDoS regression: large single-line input must scan fast ---


def test_scan_css_fast_on_large_single_line() -> None:
    """A ~1MB single-line artifact must scan in well under a second.

    Guards the block-iterating scanners against the O(n^2) backtracking that
    hung scan_css on minified single-line input (the "[^{}]*" pre-brace run).
    """
    unit = '<div class="btn cta" style="color:#111;background:#222">text</div>'
    big = "<html><body>" + unit * 16000 + "</body></html>"
    assert len(big) >= 1_000_000
    start = time.perf_counter()
    scan_css(big)
    assert time.perf_counter() - start < 1.0


def test_scan_css_correct_after_large_block_fix() -> None:
    """Fix must not change findings on normal nested CSS (at-rule + blocks)."""
    css = (
        "h1 { -webkit-background-clip: text; } "
        ".card:hover { transform: scale(1.0); } "
        "@media (min-width: 600px) { .x { color: #1a1a1a; background-color: #1e1e1e; } }"
    )
    assert ids(css) == {"gradient-text-headline", "universal-hover-scale", "contrast-canary"}
