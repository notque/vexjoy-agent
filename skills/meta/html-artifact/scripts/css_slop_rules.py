#!/usr/bin/env python3
# Vendored verbatim from skills/frontend/distinctive-frontend-design/scripts/css_slop_rules.py — keep in sync.
"""Canonical rendered-CSS slop rules. Self-contained, dependency-free.

Public surface:
    scan_css(css_text: str) -> list[Finding]
    Finding(rule_id, severity, message, line)

Deterministic regex/parse only — no LLM. Designed to be vendored as-is into
other skills (e.g. html-artifact). Findings start at "warning" severity; the
promote-to-error path is documented per rule below and gated by the caller.

Rules:
    transition-all          `transition: all` (shorthand spanning all properties)
    universal-hover-scale   :hover whose only effect is a broad transform: scale()
    gradient-text-headline  background-clip:text / -webkit-background-clip:text on h1/h2
    focus-ring-fade         focus outline/ring animated via transition (fades in)
    emoji-feature-icon      emoji codepoint as a feature/list icon (CSS content or markup)
    two-line-cta            clickable/button text that wraps to two lines (heuristic)
    contrast-canary         adjacent fg/bg within delta-L <= 0.05 AND delta-chroma <= 0.05
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """One slop-rule hit.

    rule_id:  stable identifier (see module docstring table).
    severity: "warning" for every rule today; callers promote to "error".
    message:  human-readable explanation and fix direction.
    line:     1-based best-effort source line.
    """

    rule_id: str
    severity: str
    message: str
    line: int


# Contrast-canary thresholds (oklch space): treat as too-low-contrast when BOTH hold.
_CONTRAST_DELTA_L = 0.05  # lightness L is 0..1; <=5% apart
_CONTRAST_DELTA_C = 0.05  # chroma

_EMOJI_RE = re.compile(
    "["
    "\U0001f300-\U0001faff"  # symbols, pictographs, emoji
    "\U00002600-\U000027bf"  # misc symbols + dingbats
    "\U0001f000-\U0001f0ff"  # mahjong/dominoes/cards
    "\U00002190-\U000021ff"  # arrows (often used as icons)
    "\U00002b00-\U00002bff"  # misc symbols and arrows (stars, checks)
    "\U0000fe0f"  # variation selector-16
    "]"
)


def _line_of(text: str, index: int) -> int:
    """Return the 1-based line number for a character offset."""
    return text.count("\n", 0, index) + 1


# --- color parsing (hex + oklch) → (L, chroma) in oklch space ---


def _parse_hex(token: str) -> tuple[float, float, float] | None:
    """Parse #rgb / #rrggbb (alpha ignored) → sRGB 0..1 triple."""
    h = token.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h[:3])
    elif len(h) in (6, 8):
        h = h[:6]
    else:
        return None
    try:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
    except ValueError:
        return None
    return (r, g, b)


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _srgb_to_oklch_lc(rgb: tuple[float, float, float]) -> tuple[float, float]:
    """sRGB triple → (L, chroma) in OKLCH. Hue is dropped (not needed here)."""
    r, g, b = (_srgb_to_linear(c) for c in rgb)
    lm = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    mm = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    sm = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_ = lm ** (1 / 3)
    m_ = mm ** (1 / 3)
    s_ = sm ** (1 / 3)
    big_l = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b2 = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
    chroma = math.hypot(a, b2)
    return (big_l, chroma)


_OKLCH_RE = re.compile(r"oklch\(\s*([0-9.]+%?)\s+([0-9.]+)\s+", re.IGNORECASE)


def _parse_oklch(token: str) -> tuple[float, float] | None:
    """Parse oklch(L C H ...) → (L, chroma). L may be a percentage."""
    m = _OKLCH_RE.search(token)
    if not m:
        return None
    raw_l, raw_c = m.group(1), m.group(2)
    try:
        big_l = float(raw_l[:-1]) / 100.0 if raw_l.endswith("%") else float(raw_l)
        chroma = float(raw_c)
    except ValueError:
        return None
    return (big_l, chroma)


def _color_to_lc(value: str) -> tuple[float, float] | None:
    """Resolve a single CSS color value to (L, chroma) in oklch space."""
    value = value.strip()
    if value.lower().startswith("oklch("):
        return _parse_oklch(value)
    hexmatch = re.search(r"#[0-9a-fA-F]{3,8}\b", value)
    if hexmatch:
        rgb = _parse_hex(hexmatch.group(0))
        if rgb is not None:
            return _srgb_to_oklch_lc(rgb)
    return None


# --- rule scanners ---

_BLOCK_RE = re.compile(r"([^{}]*)\{([^{}]*)\}", re.DOTALL)


def _iter_blocks(css: str):
    """Yield (selector, body, body_offset) for each top-level rule block."""
    for m in _BLOCK_RE.finditer(css):
        selector = m.group(1).strip()
        body = m.group(2)
        yield selector, body, m.start(2)


def _decls(body: str) -> list[tuple[str, str]]:
    """Split a declaration block into (property, value) pairs (lowercased prop)."""
    out: list[tuple[str, str]] = []
    for chunk in body.split(";"):
        if ":" in chunk:
            prop, _, val = chunk.partition(":")
            out.append((prop.strip().lower(), val.strip()))
    return out


def _scan_transition_all(css: str) -> list[Finding]:
    findings: list[Finding] = []
    for m in re.finditer(r"transition(?:-property)?\s*:\s*([^;}]*)", css, re.IGNORECASE):
        if re.match(r"all\b", m.group(1).strip(), re.IGNORECASE):
            findings.append(
                Finding(
                    "transition-all",
                    "warning",
                    "transition: all animates every property; name the properties you "
                    "actually change (e.g. transition: opacity, transform).",
                    _line_of(css, m.start()),
                )
            )
    return findings


def _scan_universal_hover_scale(css: str) -> list[Finding]:
    findings: list[Finding] = []
    for selector, body, offset in _iter_blocks(css):
        if ":hover" not in selector.lower():
            continue
        decls = _decls(body)
        effective = [(p, v) for p, v in decls if p and v]
        if len(effective) != 1:
            continue
        prop, val = effective[0]
        if prop == "transform" and re.match(r"scale\(\s*1(\.0\d*)?\s*\)", val, re.IGNORECASE):
            findings.append(
                Finding(
                    "universal-hover-scale",
                    "warning",
                    "the only hover effect is a small transform: scale(); a uniform "
                    "scale-on-hover reads as templated. Give hover a purposeful change.",
                    _line_of(css, offset),
                )
            )
    return findings


def _scan_gradient_text_headline(css: str) -> list[Finding]:
    findings: list[Finding] = []
    for selector, body, offset in _iter_blocks(css):
        sel = selector.lower()
        if not re.search(r"\bh[12]\b", sel):
            continue
        if re.search(r"(?:-webkit-)?background-clip\s*:\s*text", body, re.IGNORECASE):
            findings.append(
                Finding(
                    "gradient-text-headline",
                    "warning",
                    "gradient-clipped headline text (background-clip: text on h1/h2) is a "
                    "signature template look; use a solid headline color.",
                    _line_of(css, offset),
                )
            )
    return findings


def _scan_focus_ring_fade(css: str) -> list[Finding]:
    findings: list[Finding] = []
    for selector, body, offset in _iter_blocks(css):
        if ":focus" not in selector.lower():
            continue
        decls = _decls(body)
        has_ring = any(p in ("outline", "box-shadow", "border", "outline-color") for p, _ in decls)
        trans = next((v for p, v in decls if p in ("transition", "transition-property")), "")
        if has_ring and re.search(r"\b(all|outline|box-shadow|border)\b", trans, re.IGNORECASE):
            findings.append(
                Finding(
                    "focus-ring-fade",
                    "warning",
                    "focus ring is animated via transition; focus indicators must appear "
                    "instantly for accessibility. Remove the transition on the ring.",
                    _line_of(css, offset),
                )
            )
    return findings


def _scan_emoji_feature_icon(css: str) -> list[Finding]:
    findings: list[Finding] = []
    # CSS: content property carrying an emoji (pseudo-element icon).
    for m in re.finditer(r"content\s*:\s*([\"'])(.*?)\1", css, re.IGNORECASE | re.DOTALL):
        if _EMOJI_RE.search(m.group(2)):
            findings.append(
                Finding(
                    "emoji-feature-icon",
                    "warning",
                    "emoji used as a feature/list icon (CSS content); use an inline SVG "
                    "icon set for a deliberate look.",
                    _line_of(css, m.start()),
                )
            )
    # Markup hook: emoji directly inside a list item / feature element.
    for m in re.finditer(r"<li\b[^>]*>(.*?)</li>", css, re.IGNORECASE | re.DOTALL):
        if _EMOJI_RE.search(m.group(1)):
            findings.append(
                Finding(
                    "emoji-feature-icon",
                    "warning",
                    "emoji used as a feature/list icon in markup; use an inline SVG icon set.",
                    _line_of(css, m.start()),
                )
            )
    return findings


def _scan_two_line_cta(css: str) -> list[Finding]:
    findings: list[Finding] = []
    # Heuristic: a button/CTA-classed clickable whose text contains a forced break.
    pattern = re.compile(
        r"<(?:button|a)\b[^>]*(?:class\s*=\s*\"[^\"]*(?:btn|button|cta)[^\"]*\"|role\s*=\s*\"button\")[^>]*>(.*?)</(?:button|a)>",
        re.IGNORECASE | re.DOTALL,
    )
    for m in pattern.finditer(css):
        inner = m.group(1)
        if re.search(r"<br\s*/?>", inner, re.IGNORECASE) or "\n" in inner.strip():
            findings.append(
                Finding(
                    "two-line-cta",
                    "warning",
                    "call-to-action text wraps to two lines; keep CTA labels to one short "
                    "line so the action stays scannable.",
                    _line_of(css, m.start()),
                )
            )
    return findings


def _scan_contrast_canary(css: str) -> list[Finding]:
    findings: list[Finding] = []
    for _selector, body, offset in _iter_blocks(css):
        fg = bg = None
        for prop, val in _decls(body):
            if prop == "color":
                fg = _color_to_lc(val)
            elif prop in ("background-color", "background"):
                cand = _color_to_lc(val)
                if cand is not None:
                    bg = cand
        if fg is None or bg is None:
            continue
        if abs(fg[0] - bg[0]) <= _CONTRAST_DELTA_L and abs(fg[1] - bg[1]) <= _CONTRAST_DELTA_C:
            findings.append(
                Finding(
                    "contrast-canary",
                    "warning",
                    "foreground and background are nearly identical "
                    f"(delta-L<={_CONTRAST_DELTA_L}, delta-chroma<={_CONTRAST_DELTA_C}); text "
                    "will be unreadable. Widen the lightness gap.",
                    _line_of(css, offset),
                )
            )
    return findings


_SCANNERS = (
    _scan_transition_all,
    _scan_universal_hover_scale,
    _scan_gradient_text_headline,
    _scan_focus_ring_fade,
    _scan_emoji_feature_icon,
    _scan_two_line_cta,
    _scan_contrast_canary,
)


def scan_css(css_text: str) -> list[Finding]:
    """Scan CSS (or HTML containing CSS/markup) for slop patterns.

    Returns findings sorted by line, then rule_id. Deterministic.
    """
    findings: list[Finding] = []
    for scanner in _SCANNERS:
        findings.extend(scanner(css_text))
    findings.sort(key=lambda f: (f.line, f.rule_id))
    return findings
