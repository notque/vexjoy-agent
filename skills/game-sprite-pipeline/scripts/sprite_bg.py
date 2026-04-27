#!/usr/bin/env python3
"""Background-removal primitives for the game-sprite-pipeline skill.

Owns the chroma-key + despill chain, the gray-tolerance road-to-aew
algorithm, the rembg fallback, and the `remove-bg` CLI subcommand. All
operations are local + deterministic (apart from rembg, which is opt-in).

Public surface (re-exported through `sprite_process` for backward compat):
    Constants:
        MAGENTA, DEFAULT_CHROMA_THRESHOLD, DEFAULT_PASS2_THRESHOLD,
        DEFAULT_DESPILL_STRENGTH, DEFAULT_ALPHA_DILATE_RADIUS,
        DEFAULT_MIN_COMPONENT_PIXELS, GRAY_BG_DEFAULT,
        GRAY_BG_TOLERANCE_DEFAULT, WATERMARK_MARGIN_DEFAULT,
        WATERMARK_BRIGHTNESS_THRESHOLD, BG_MODE_CHOICES.
    Pixel helpers:
        chroma_pass1, chroma_pass2_edge_flood, dilate_alpha_zero,
        color_despill_magenta, kill_pink_fringe,
        neutralize_interior_magenta_spill, matte_composite,
        alpha_fade_magenta_fringe.
    File-level helpers:
        remove_bg_chroma, remove_watermark_corners,
        gray_tolerance_to_alpha, remove_bg_gray_tolerance,
        remove_bg_rembg.
    CLI:
        cmd_remove_bg, _alpha_coverage_too_low.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import deque
from pathlib import Path

logger = logging.getLogger("sprite-pipeline.sprite_bg")

try:
    from PIL import Image
except ImportError as e:
    logger.error("Pillow not installed: %s", e)
    logger.error("Install with: pip install pillow")
    sys.exit(1)

try:
    import numpy as np

    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAGENTA = (255, 0, 255)
DEFAULT_CHROMA_THRESHOLD = 30
# Pass-2 default loosened from 60 (= 2 * pass1) to 90 because despill now
# protects character pixels at the fringe. See bg-removal-local.md.
DEFAULT_PASS2_THRESHOLD = 90
DEFAULT_DESPILL_STRENGTH = 0.5
DEFAULT_ALPHA_DILATE_RADIUS = 1
DEFAULT_MIN_COMPONENT_PIXELS = 200
DEFAULT_BOTTOM_MARGIN = 8
DEFAULT_GIF_FPS = 10

# Adapted from ~/road-to-aew/scripts/generate_enemy_sprite.py (lines 1048-1128).
# road-to-aew uses Gemini Nano Banana which paints a #3a3a3a background;
# this skill exposes the same algorithm under --bg-mode gray-tolerance for
# any backend that does not honor the magenta-bg prompt.
GRAY_BG_DEFAULT = (58, 58, 58)
GRAY_BG_TOLERANCE_DEFAULT = 30
WATERMARK_MARGIN_DEFAULT = 40
WATERMARK_BRIGHTNESS_THRESHOLD = 180

# Canonical --bg-mode CLI choices. Owned here because every bg-removal
# command-line surface (sprite_process.py, sprite_pipeline.py,
# portrait_pipeline.py) should advertise the same set.
#
# `chroma`: two-pass chroma key (default magenta #FF00FF matte). Default.
# `gray-tolerance`: tolerance-banded gray-to-alpha (road-to-aew #3a3a3a algorithm).
# `rembg`: ONNX-model-based bg removal (opt-in dep).
# `auto`: try chroma; fall back if mask coverage looks suspicious.
#
# See ADR-204 for the unified vocabulary across pipelines. The legacy
# `magenta` alias was dropped — it was always a misnomer for the chroma
# algorithm with the default magenta matte.
BG_MODE_CHOICES = ("chroma", "gray-tolerance", "rembg", "auto")


# ---------------------------------------------------------------------------
# Chroma key (portrait Phase B + spritesheet Phase E)
# ---------------------------------------------------------------------------
def chroma_pass1(img: Image.Image, chroma: tuple[int, int, int], threshold: int) -> Image.Image:
    """Mask pixels within sum-of-abs-diff threshold of chroma."""
    img = img.convert("RGBA")
    if HAS_NUMPY:
        arr = np.array(img)
        rgb = arr[..., :3].astype(int)
        diff = np.abs(rgb - np.array(chroma)).sum(axis=-1)
        mask = diff <= threshold
        arr[mask, 3] = 0
        return Image.fromarray(arr, "RGBA")

    # Pure-Python fallback
    pixels = img.load()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixels[x, y]
            if abs(r - chroma[0]) + abs(g - chroma[1]) + abs(b - chroma[2]) <= threshold:
                pixels[x, y] = (r, g, b, 0)
    return img


def chroma_pass2_edge_flood(
    img: Image.Image,
    chroma: tuple[int, int, int],
    threshold: int,
    despill_strength: float = DEFAULT_DESPILL_STRENGTH,
) -> Image.Image:
    """Despill-aware flood-fill from canvas edges with looser threshold.

    Pass 2 walks inward from canvas edges and zeros alpha for any pixel that
    is "close enough" to the chroma color (`threshold`). The despill check
    protects pixels whose RGB is off-color relative to the chroma — this is
    the character's anti-aliased fringe where lighting/spill has shifted the
    pixel away from pure magenta. Without despill, threshold=90 bites into
    character silhouettes; with despill it cleans the halo while preserving
    art.

    A pixel is preserved (not zeroed) when:
      diff <= threshold (i.e. nominally background) AND
      color_balance(max-min RGB) > 20 * despill_strength

    `color_balance` is large for "saturated, distinct" colors and small for
    pure magenta-ish pixels. Set `despill_strength=0` to disable.
    """
    img = img.convert("RGBA")
    if not HAS_NUMPY:
        # Without numpy this would be very slow; skip pass 2 in pure-Python mode
        return img

    arr = np.array(img)
    h, w = arr.shape[:2]
    visited = np.zeros((h, w), dtype=bool)
    chroma_arr = np.array(chroma)

    queue: deque[tuple[int, int]] = deque()
    for y in (0, h - 1):
        for x in range(w):
            queue.append((y, x))
    for x in (0, w - 1):
        for y in range(h):
            queue.append((y, x))

    # Despill: a pixel is "off the magenta axis" when its chroma-orthogonal
    # channel (green for magenta) is closer to the off-axis channels (R, B)
    # than expected for true magenta. For magenta=(255,0,255), the off-axis
    # channel is green; pure-magenta pixels have G near 0 and R, B near 255.
    # Spill pixels (character art tinted by magenta) have G high relative to
    # the on-axis channels: a TRUE character pixel has G close to or higher
    # than R+B/2; a halo pixel has G << R+B/2.
    despill_lift_cutoff = int(80 * despill_strength)

    def is_off_axis(rgb_arr: np.ndarray) -> bool:
        """Return True if this pixel is off the chroma axis (preserve as character).

        For magenta=(255,0,255): a character pixel has its OFF-AXIS channel (G)
        lifted toward the ON-AXIS channels (R, B). The "off-axis lift ratio" is
        G compared to (R+B)/2; if G is at least `despill_lift_cutoff` of (R+B)/2,
        the pixel is sufficiently de-magenta to count as character.

        At cutoff=40 (default 0.5 strength * 80): G must be at least 40 less
        than (R+B)/2 to be classified as halo. Halo pixels like (252,33,219)
        have (R+B)/2=235, gap=235-33=202 → not preserved (halo).
        Character pixels like skin (220,130,100) have (R+B)/2=160, gap=30 →
        preserved (character).
        """
        r_, g_, b_ = int(rgb_arr[0]), int(rgb_arr[1]), int(rgb_arr[2])
        if chroma == (255, 0, 255):
            on_axis_avg = (r_ + b_) / 2
            gap = on_axis_avg - g_
            # Pixel is off-axis (character) if gap from on-axis avg to G is small.
            return gap < despill_lift_cutoff
        # Generic fallback: deviations from chroma color.
        deviations = [abs(p - c) for p, c in zip((r_, g_, b_), chroma)]
        return max(deviations) >= despill_lift_cutoff

    while queue:
        y, x = queue.popleft()
        if not (0 <= y < h and 0 <= x < w):
            continue
        if visited[y, x]:
            continue
        if arr[y, x, 3] == 0:
            visited[y, x] = True
            for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                queue.append((y + dy, x + dx))
            continue
        rgb = arr[y, x, :3].astype(int)
        diff = int(np.abs(rgb - chroma_arr).sum())
        if diff > threshold:
            continue
        # Despill: a pixel that nominally matches the bg threshold but has
        # significant off-axis lift (e.g. green channel for magenta-bg) is
        # character spill. Preserve it.
        if despill_strength > 0 and arr[y, x, 3] > 128 and is_off_axis(rgb):
            visited[y, x] = True
            continue
        visited[y, x] = True
        arr[y, x, 3] = 0
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            queue.append((y + dy, x + dx))

    return Image.fromarray(arr, "RGBA")


def dilate_alpha_zero(arr: np.ndarray, radius: int = DEFAULT_ALPHA_DILATE_RADIUS) -> np.ndarray:
    """Expand the alpha=0 region by `radius` pixels (4-connected dilation).

    Kills the 1-pixel halo that survives even pass-2 flood-fill on
    anti-aliased generator output. Pure numpy, no scipy. The 4-connected
    shifted-OR is correct for radius=1; iterate for larger radii.
    """
    if radius <= 0:
        return arr
    alpha = arr[..., 3]
    mask = alpha == 0
    for _ in range(radius):
        shifted = np.zeros_like(mask)
        shifted[1:, :] |= mask[:-1, :]
        shifted[:-1, :] |= mask[1:, :]
        shifted[:, 1:] |= mask[:, :-1]
        shifted[:, :-1] |= mask[:, 1:]
        mask = mask | shifted
    arr[..., 3] = np.where(mask, 0, alpha)
    return arr


def color_despill_magenta(arr: np.ndarray) -> np.ndarray:
    """VFX-style despill: bleach magenta tint from semi-transparent silhouette.

    For magenta=(255,0,255), a pixel at the silhouette has high R, low G,
    high B (pink). Despill clamps R and B to max(G, R, B) when G < min(R, B):
    in practice, set R = min(R, max(G, B-margin)) so the pink fringe gets
    pulled toward neutral.

    This runs AFTER pass-2 alpha masking so it only touches non-zero alpha
    pixels (the surviving fringe).
    """
    rgb = arr[..., :3].astype(int)
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    # A pixel "leans magenta" when both R and B are higher than G by a margin.
    # We pull R and B down toward G (kills the pink/magenta tint).
    leans_magenta = (r > g + 10) & (b > g + 10) & (arr[..., 3] > 0) & (arr[..., 3] < 255)
    # Cap R and B at a value that keeps the pixel hue-balanced
    cap = np.maximum(g, np.minimum(r, b))
    new_r = np.where(leans_magenta, np.minimum(r, cap + 30), r)
    new_b = np.where(leans_magenta, np.minimum(b, cap + 30), b)
    arr[..., 0] = np.clip(new_r, 0, 255).astype(np.uint8)
    arr[..., 2] = np.clip(new_b, 0, 255).astype(np.uint8)
    return arr


def kill_pink_fringe(arr: np.ndarray, alpha_ceiling: int = 220) -> np.ndarray:
    """Zero alpha on semi-transparent pink-cast pixels at the silhouette edge.

    The despill chain (chroma_pass2_edge_flood + color_despill_magenta +
    alpha_fade_magenta_fringe + dilate_alpha_zero) leaves a residual class of
    fringe pixels that survive because their per-pixel color spread is high
    enough to look like saturated character art (despill protects them) yet
    they sit exactly at the anti-aliased silhouette boundary with non-full
    alpha. Visually, these read as a pink halo or wisp.

    The wide pink criterion catches them: R > 130 AND B > 120 AND G < 80
    AND R - G > 50 AND B - G > 40. Restricting the kill to alpha < 220
    ensures we only touch edge pixels — full-opacity character art (e.g. a
    purple costume center, alpha 255) is preserved.

    Tuning:
      alpha_ceiling=220 (default): only edge pixels with anti-aliased alpha.
      alpha_ceiling=255: also kill fully-opaque pink — DANGEROUS; can erase
        intentional pink/magenta costume art. Don't raise without verifying.
      alpha_ceiling=180: more conservative; preserves more fringe.

    Pure numpy. ~5ms / 1024px image.
    """
    rgb = arr[..., :3].astype(int)
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    alpha = arr[..., 3]
    pink_cast = (
        (r > 130) & (b > 120) & (g < 80) & ((r - g) > 50) & ((b - g) > 40) & (alpha > 0) & (alpha < alpha_ceiling)
    )
    arr[pink_cast, 3] = 0
    return arr


def neutralize_interior_magenta_spill(arr: np.ndarray) -> np.ndarray:
    """Recolor full-opacity pink-cast pixels INSIDE the silhouette toward neutral.

    Distinct from `kill_pink_fringe` (edge alpha-kill) and from
    `color_despill_magenta` (semi-transparent fringe color clamp). This
    targets the case where the generator painted PINK-CAST pixels INSIDE
    the character silhouette (typically inside dark hair or shadow
    regions), where R is high, G is low, B is moderate-high. Visually a
    pink streak or wisp inside dark hair.

    Two-tier criterion (tightened to protect intentional costume color):

    Tier A — pure magenta cast:
      R >= 200 AND B >= 200 AND G <= 80 AND R-G > 120 AND B-G > 120
      Catches near-pure (255,0,255)-cast pixels.

    Tier B — moderate pink cast WITH B > R*0.6 (so it's not just orange/red):
      R >= 150 AND G <= 80 AND B >= 90 AND R-G > 90 AND B-G > 50
      AND B*1.4 >= R   (pink/magenta hue, not red)
      Catches the (233, 56, 165) class of "diluted spill into hair" that
      Tier A misses because B=165 < 200.

    Both tiers require alpha == 255 to skip edge anti-aliased pixels.

    Costume protection examples (all preserved):
    - Magenta showman shorts (190, 20, 190): R=190 < 200 (fails A), B=190 OK
      (B*1.4=266 >= R=190) — but R<150? No, R=190. So Tier B catches it!
      That's a problem — magenta costumes ARE pink. Mitigation: the criterion
      catches pixels that look "like background bleed", not "like a magenta
      costume". A magenta costume painting has SHADING and varied saturation;
      a few pixels recolored is invisible. The skill prompts for non-magenta
      costumes anyway, and where magenta IS used (showman archetype), users
      should accept this as a known limitation logged in
      `references/bg-removal-local.md`.
    - Purple suit highlights (180, 80, 200): G=80 fails (G<=80, so passes B).
      B*1.4=280 >= R=180. R-G=100>90. B-G=120>50. → Tier B fires.
      Recolor to (80, 80, 80) which DESTROYS the purple suit. So we need a
      tighter B-vs-R relationship: PURE pink has B ≈ R, purple has B > R*1.1.
      Add: AND B <= R*1.05  (pink: B ≈ R; reject purple: B much higher).
      Re-check examples:
        - (233, 56, 165): B/R = 0.71 → passes (it's pink/red, not purple)
        - (180, 80, 200): B/R = 1.11 → REJECTED (it's purple, leave alone)
        - magenta (255, 0, 255): B/R = 1.0 → passes
        - showman pink (250, 50, 230): B/R = 0.92 → passes
        - manager suit (150, 30, 180): B/R = 1.20 → REJECTED (purple)

    Recoloring strategy: pull R and B down to G — neutralizes hue while
    preserving brightness of G (hair stays dark, highlights stay brighter).

    Pure numpy. ~10ms / 1024px image.
    """
    rgb = arr[..., :3].astype(int)
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    alpha = arr[..., 3]
    # Tier A: near-pure magenta cast inside silhouette (G strict <=80).
    # Loosened r-g and b-g from >120 to >100 so pixels like (209,90,217)
    # at r-g=119 still get neutralized.
    tier_a = (r >= 200) & (b >= 200) & (g <= 100) & ((r - g) > 100) & ((b - g) > 100) & (alpha == 255)
    # Tier B: moderate pink cast (catches diluted spill that GIF dithered).
    # Loosened from r>=150,g<=80 to r>=130,g<=100 so darker pinks like
    # (149,6,123) and shaded magentas like (234,93,208) on full-opacity
    # interior pixels are recolored. Critical: B <= R*1.10 distinguishes
    # pink/magenta (B near R) from purple (B much higher). Costume protect:
    # purple suit (180,80,200) has B/R=1.11 → still rejected.
    tier_b = (
        (r >= 130)
        & (g <= 100)
        & (b >= 90)
        & ((r - g) > 90)
        & ((b - g) > 50)
        & (b * 100 <= r * 110)  # pink hue, not purple (B near or below R)
        & (alpha == 255)
    )
    pink_inside = tier_a | tier_b
    # Pull R and B down to G — neutralizes hue while preserving brightness
    arr[..., 0] = np.where(pink_inside, g.astype(np.uint8), arr[..., 0])
    arr[..., 2] = np.where(pink_inside, g.astype(np.uint8), arr[..., 2])
    return arr


def matte_composite(img: Image.Image, matte: tuple[int, int, int] = (40, 40, 40)) -> Image.Image:
    """Blend an RGBA image over a neutral matte color and return RGB.

    Used BEFORE GIF palette quantization. The 1-bit-alpha + adaptive 256-
    color GIF format reintroduces magenta-tinted edges at the silhouette
    even when the RGBA source is clean — the adaptive palette allocates
    indices for pink fringe pixels and the quantizer rounds nearby
    anti-aliased pixels to those entries. Pre-mattering over a neutral
    middle-gray (default 40,40,40) gives the quantizer no pink reference
    to lock onto: anti-aliased pixels blend to neutral gray instead of
    pink/plum, the palette stays neutral, and surviving GIF edges look
    like dark gray (visually neutral) instead of pink.

    The matte color choice matters. Brighter mattes (e.g. 128,128,128) wash
    out the silhouette against a dark page bg. Pure black (0,0,0) shows up
    as a hard edge against any non-black page. Middle-gray (40,40,40)
    matches typical dark-theme page bgs (~#181a21 to #2a2a2e) closely
    enough to disappear, while still desaturating the fringe.
    """
    img = img.convert("RGBA")
    bg = Image.new("RGB", img.size, matte)
    bg.paste(img, (0, 0), img)
    return bg


def alpha_fade_magenta_fringe(arr: np.ndarray, threshold: int = 130) -> np.ndarray:
    """Flood-zero pink/magenta-leaning regions connected to alpha=0.

    Strategy: classify each opaque pixel as "pink-leaning" or not. Then flood
    from the alpha=0 boundary INTO connected pink-leaning regions, zeroing
    them. This kills entire halo blobs (any thickness) without eroding into
    non-pink character pixels — the flood stops as soon as it hits
    non-pink-leaning pixels.

    Pink-leaning rule:
      (a) "Saturated pink/magenta": R > 180, B > 100, R+B-2G > 180
      (b) "Near-magenta": weighted distance (R + 2G + B)-space < threshold
    """
    rgb = arr[..., :3].astype(int)
    r = rgb[..., 0]
    g = rgb[..., 1]
    b = rgb[..., 2]
    alpha = arr[..., 3]
    chroma = np.array((255, 0, 255), dtype=int)
    weighted = np.abs(r - chroma[0]) + 2 * np.abs(g - chroma[1]) + np.abs(b - chroma[2])
    pink_leaning = ((r > 180) & (b > 100) & ((r + b - 2 * g) > 180)) | (weighted < threshold)

    # Iterative dilation flood: at each step, mark as fringe any opaque-pink
    # pixel adjacent to a fringe pixel (or alpha=0). Stop when no new pixels
    # are marked (or after a sane upper bound).
    cur_alpha = alpha.copy()
    for _ in range(20):
        zero_mask = cur_alpha == 0
        # 4-connected expansion of zero_mask
        adj = np.zeros_like(zero_mask)
        adj[1:, :] |= zero_mask[:-1, :]
        adj[:-1, :] |= zero_mask[1:, :]
        adj[:, 1:] |= zero_mask[:, :-1]
        adj[:, :-1] |= zero_mask[:, 1:]
        new_zero = (cur_alpha > 0) & adj & pink_leaning
        if not new_zero.any():
            break
        cur_alpha = np.where(new_zero, 0, cur_alpha)
    arr[..., 3] = cur_alpha
    return arr


def remove_bg_chroma(
    input_path: Path,
    output_path: Path,
    threshold: int,
    pass2_threshold: int | None = None,
    despill_strength: float = DEFAULT_DESPILL_STRENGTH,
    alpha_dilate_radius: int = DEFAULT_ALPHA_DILATE_RADIUS,
) -> None:
    """Two-pass despill-aware chroma key + alpha-fade + dilation.

    pass1: tight match to chroma color (default threshold=30) — catches the
        bulk solid magenta.
    pass2: edge flood with looser threshold (default 90) and despill — catches
        feathered fringe without biting into character interior.
    fringe-fade: any remaining pixels close to magenta in weighted-RGB space
        get their alpha attenuated proportionally (kills the visible pink halo).
    color-despill: bleach magenta tint out of remaining semi-opaque pixels.
    dilate: expand alpha=0 by 1 px so the 1-pixel residual halo at the
        silhouette is removed.
    """
    if pass2_threshold is None:
        pass2_threshold = DEFAULT_PASS2_THRESHOLD
    img = Image.open(input_path)
    pass1 = chroma_pass1(img, MAGENTA, threshold)
    pass2 = chroma_pass2_edge_flood(
        pass1,
        MAGENTA,
        pass2_threshold,
        despill_strength=despill_strength,
    )
    if HAS_NUMPY:
        arr = np.array(pass2.convert("RGBA"))
        # Fringe alpha-fade: kill remaining pink halo by attenuating alpha
        # in proportion to magenta-distance.
        arr = alpha_fade_magenta_fringe(arr, threshold=130)
        # Color despill: bleach the magenta tint out of surviving fringe pixels.
        arr = color_despill_magenta(arr)
        # Interior spill: neutralize full-opacity PURE-magenta pixels the
        # generator painted INSIDE the silhouette (e.g. pink streaks in
        # dark hair). Must run BEFORE kill_pink_fringe so the recolored
        # pixels don't get re-classified as fringe.
        arr = neutralize_interior_magenta_spill(arr)
        # Alpha dilation: expand alpha=0 region to kill 1-px residual halo.
        if alpha_dilate_radius > 0:
            arr = dilate_alpha_zero(arr, alpha_dilate_radius)
        # Final pink-fringe kill: zero alpha on semi-transparent pink-cast
        # pixels that despill protected as "saturated". See bg-removal-local.md
        # "GIF format bleed at silhouette edges" for the full rationale.
        arr = kill_pink_fringe(arr)
        pass2 = Image.fromarray(arr, "RGBA")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pass2.save(output_path, format="PNG")


# Adapted from ~/road-to-aew/scripts/generate_enemy_sprite.py lines 1048-1128
# (`remove_watermark` + `make_background_transparent`). road-to-aew has produced
# 87 clean transparent PNGs in production with this algorithm. Used here as
# the secondary backend for image generators that paint a gray background
# (Gemini Nano Banana) instead of honoring our magenta-bg prompt.
def remove_watermark_corners(
    img: Image.Image,
    bg_color: tuple[int, int, int],
    margin: int,
    brightness_threshold: int = WATERMARK_BRIGHTNESS_THRESHOLD,
) -> Image.Image:
    """Replace bright corner pixels with bg_color so they get masked later."""
    img = img.convert("RGBA")
    if not HAS_NUMPY:
        # Slow path: per-pixel
        pixels = img.load()
        w, h = img.size
        corner_boxes = [
            (0, 0, margin, margin),
            (w - margin, 0, w, margin),
            (0, h - margin, margin, h),
            (w - margin, h - margin, w, h),
        ]
        for x1, y1, x2, y2 in corner_boxes:
            for y in range(max(0, y1), min(h, y2)):
                for x in range(max(0, x1), min(w, x2)):
                    r, g, b, _ = pixels[x, y]
                    if (r + g + b) / 3 > brightness_threshold:
                        pixels[x, y] = (bg_color[0], bg_color[1], bg_color[2], 255)
        return img
    arr = np.array(img)
    h, w = arr.shape[:2]
    brightness = arr[..., :3].mean(axis=-1)
    corner_mask = np.zeros((h, w), dtype=bool)
    m = min(margin, h, w)
    corner_mask[:m, :m] = True
    corner_mask[:m, w - m :] = True
    corner_mask[h - m :, :m] = True
    corner_mask[h - m :, w - m :] = True
    bright_corners = corner_mask & (brightness > brightness_threshold)
    arr[bright_corners, 0] = bg_color[0]
    arr[bright_corners, 1] = bg_color[1]
    arr[bright_corners, 2] = bg_color[2]
    arr[bright_corners, 3] = 255
    return Image.fromarray(arr, "RGBA")


def gray_tolerance_to_alpha(
    img: Image.Image,
    bg_color: tuple[int, int, int],
    tolerance: int,
) -> Image.Image:
    """Set alpha=0 for any pixel within `tolerance` of `bg_color` (per channel)."""
    img = img.convert("RGBA")
    if not HAS_NUMPY:
        pixels = img.load()
        w, h = img.size
        for y in range(h):
            for x in range(w):
                r, g, b, a = pixels[x, y]
                if (
                    abs(r - bg_color[0]) <= tolerance
                    and abs(g - bg_color[1]) <= tolerance
                    and abs(b - bg_color[2]) <= tolerance
                ):
                    pixels[x, y] = (r, g, b, 0)
        return img
    arr = np.array(img)
    rgb = arr[..., :3].astype(int)
    bg_arr = np.array(bg_color, dtype=int)
    within = np.all(np.abs(rgb - bg_arr) <= tolerance, axis=-1)
    arr[within, 3] = 0
    return Image.fromarray(arr, "RGBA")


def remove_bg_gray_tolerance(
    input_path: Path,
    output_path: Path,
    bg_color: tuple[int, int, int] = GRAY_BG_DEFAULT,
    tolerance: int = GRAY_BG_TOLERANCE_DEFAULT,
    watermark_margin: int = WATERMARK_MARGIN_DEFAULT,
    alpha_dilate_radius: int = DEFAULT_ALPHA_DILATE_RADIUS,
) -> None:
    """road-to-aew's algorithm: watermark-corner clean + gray-tolerance alpha.

    Step 1: bright pixels in the four corner boxes get repainted to bg_color
        (kills Gemini's watermark before the mask sees it).
    Step 2: any pixel within `tolerance` of bg_color (per-channel abs-diff)
        gets alpha=0.
    Step 3: alpha dilation by 1 px (kills 1-pixel halo).
    """
    img = Image.open(input_path)
    cleaned = remove_watermark_corners(img, bg_color, watermark_margin)
    transparent = gray_tolerance_to_alpha(cleaned, bg_color, tolerance)
    if HAS_NUMPY and alpha_dilate_radius > 0:
        arr = np.array(transparent.convert("RGBA"))
        arr = dilate_alpha_zero(arr, alpha_dilate_radius)
        transparent = Image.fromarray(arr, "RGBA")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    transparent.save(output_path, format="PNG")


def remove_bg_rembg(input_path: Path, output_path: Path) -> None:
    """rembg fallback for non-magenta backgrounds. Opt-in dep."""
    try:
        from rembg import remove
    except ImportError as e:
        raise RuntimeError(
            "rembg not installed. Run `pip install rembg onnxruntime`, or use --bg-mode chroma (default)."
        ) from e

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(remove(input_path.read_bytes()))


def cmd_remove_bg(args: argparse.Namespace) -> int:
    inputs = [Path(p) for p in args.input]
    output_dir = Path(args.output_dir) if args.output_dir else None
    if len(inputs) > 1 and output_dir is None:
        logger.error("--output-dir required when processing multiple inputs")
        return 2

    bg_mode = args.bg_mode

    for src in inputs:
        if output_dir:
            dst = output_dir / src.name
        else:
            dst = Path(args.output) if args.output else src.with_suffix(".nobg.png")

        try:
            # Dispatch on bg_mode against the unified ADR-204 vocabulary:
            # chroma | gray-tolerance | rembg | auto. The legacy `magenta`
            # alias was dropped — `chroma` (with the default magenta matte)
            # is the only spelling.
            if bg_mode == "chroma":
                remove_bg_chroma(
                    src,
                    dst,
                    args.chroma_threshold,
                    pass2_threshold=args.pass2_threshold,
                    despill_strength=args.despill_strength,
                    alpha_dilate_radius=args.alpha_dilate,
                )
            elif bg_mode == "gray-tolerance":
                remove_bg_gray_tolerance(
                    src,
                    dst,
                    bg_color=tuple(args.gray_bg),
                    tolerance=args.gray_tolerance,
                    watermark_margin=args.watermark_margin,
                    alpha_dilate_radius=args.alpha_dilate,
                )
            elif bg_mode == "rembg":
                remove_bg_rembg(src, dst)
            elif bg_mode == "auto":
                # try chroma; if alpha mask is suspiciously small, fall through to rembg
                remove_bg_chroma(
                    src,
                    dst,
                    args.chroma_threshold,
                    pass2_threshold=args.pass2_threshold,
                    despill_strength=args.despill_strength,
                    alpha_dilate_radius=args.alpha_dilate,
                )
                if _alpha_coverage_too_low(dst):
                    logger.warning("[remove-bg] auto: chroma low-coverage; falling back to rembg for %s", src.name)
                    remove_bg_rembg(src, dst)
            else:
                logger.error("unknown bg-mode %r", bg_mode)
                return 2
        except RuntimeError as e:
            logger.error("%s", e)
            return 4
        logger.info("[remove-bg] %s -> %s (bg-mode=%s)", src, dst, bg_mode)
    return 0


def _alpha_coverage_too_low(path: Path) -> bool:
    """Return True if the alpha-mask coverage is below 30% of canvas."""
    img = Image.open(path).convert("RGBA")
    if HAS_NUMPY:
        arr = np.array(img)
        opaque = (arr[..., 3] > 0).sum()
        total = arr.shape[0] * arr.shape[1]
        return (opaque / total) < 0.3
    return False  # without numpy we don't run auto mode anyway
