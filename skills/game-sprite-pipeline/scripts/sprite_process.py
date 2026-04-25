#!/usr/bin/env python3
"""
Post-processing for the game-sprite-pipeline skill.

Phases D-H of the spritesheet pipeline + portrait-mode bg removal, trim,
and validation. All operations are local + deterministic. No paid APIs.

Subcommands:
    extract-frames      Phase D: connected-components frame detection
    remove-bg           Phase B (portrait) or Phase E (sheet): magenta chroma key
    normalize           Phase C (portrait) or Phase F (sheet): trim/scale/anchor
    validate-portrait   Phase D (portrait): width/height/aspect gate
    contact-sheet       Build a contact-sheet image from variant directories
    auto-curate         Phase G: deterministic ranking of variants
    assemble            Phase H: PNG sheet + GIF + WebP + atlas + strips
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError as e:
    print(f"ERROR: Pillow not installed: {e}", file=sys.stderr)
    print("Install with: pip install pillow", file=sys.stderr)
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
PORTRAIT_WIDTH_RANGE = (350, 850)
PORTRAIT_HEIGHT_RANGE = (900, 1100)
PORTRAIT_ASPECT_MIN = 1.5  # height / width
PORTRAIT_ASPECT_MAX = 2.5
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
    # Tier A: near-pure magenta cast inside silhouette
    tier_a = (r >= 200) & (b >= 200) & (g <= 80) & ((r - g) > 120) & ((b - g) > 120) & (alpha == 255)
    # Tier B: moderate pink cast (catches diluted spill that GIF dithered)
    # Critical: B <= R * 1.05 distinguishes pink (B≈R) from purple (B>R*1.1).
    tier_b = (
        (r >= 150)
        & (g <= 80)
        & (b >= 90)
        & ((r - g) > 90)
        & ((b - g) > 50)
        & (b * 100 <= r * 105)  # pink hue, not purple
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
        print("ERROR: --output-dir required when processing multiple inputs", file=sys.stderr)
        return 2

    bg_mode = args.bg_mode if args.bg_mode is not None else _bg_mode_from_legacy(args.mode)

    for src in inputs:
        if output_dir:
            dst = output_dir / src.name
        else:
            dst = Path(args.output) if args.output else src.with_suffix(".nobg.png")

        try:
            if bg_mode == "magenta" or args.mode == "chroma":
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
            elif args.mode == "rembg":
                remove_bg_rembg(src, dst)
            elif args.mode == "auto":
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
                    print(
                        f"[remove-bg] auto: chroma low-coverage; falling back to rembg for {src.name}", file=sys.stderr
                    )
                    remove_bg_rembg(src, dst)
            else:
                print(f"ERROR: unknown bg-mode {bg_mode!r} / mode {args.mode!r}", file=sys.stderr)
                return 2
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 4
        print(f"[remove-bg] {src} -> {dst} (bg-mode={bg_mode})", file=sys.stderr)
    return 0


def _bg_mode_from_legacy(mode: str) -> str:
    """Map legacy --mode to --bg-mode (chroma -> magenta, rembg/auto pass through)."""
    return "magenta" if mode == "chroma" else mode


def _alpha_coverage_too_low(path: Path) -> bool:
    """Return True if the alpha-mask coverage is below 30% of canvas."""
    img = Image.open(path).convert("RGBA")
    if HAS_NUMPY:
        arr = np.array(img)
        opaque = (arr[..., 3] > 0).sum()
        total = arr.shape[0] * arr.shape[1]
        return (opaque / total) < 0.3
    return False  # without numpy we don't run auto mode anyway


# ---------------------------------------------------------------------------
# Naive-grid extraction (Phase D fast path) — pitch derived from raw size
# ---------------------------------------------------------------------------
def slice_grid_cells(
    sheet: Image.Image,
    cols: int,
    rows: int,
    cell_size: int,
) -> list[Image.Image]:
    """Slice a spritesheet into ``cols * rows`` cells of ``(cell_size, cell_size)``.

    The naive-grid bug this replaces: the previous consumer code resized the
    raw sheet to ``(cols * cell_size, rows * cell_size)`` BEFORE slicing, then
    sliced at ``cell_size``. That fails whenever the raw is NOT already a clean
    multiple of the grid: image-gen backends regularly return canvases like
    1254x1254 for an 8x8 grid. A whole-image LANCZOS resize from 1254 to 1024
    does not remap sprite positions onto a 128-pixel pitch — the sprites
    stay where their natural ~157px pitch puts them, and a 128-pixel cell
    grid then cuts every character mid-body.

    The fix is to derive the cell pitch from the actual raw dimensions, slice
    at the natural pitch, and only resample each cell (not the whole sheet)
    to the target ``cell_size``. This is the hybrid algorithm:

      Case 1 (exact match):  raw_size == cols * cell_size  → direct slice.
      Case 2 (integer pitch): raw_size % cols == 0          → slice at
        ``raw_size // cols``, then per-cell LANCZOS resample to ``cell_size``.
      Case 3 (fractional pitch): otherwise                  → use a float
        pitch ``raw_size / cols`` and round per-cell crop boundaries; then
        per-cell LANCZOS resample. Per-cell crops absorb the rounding so each
        sprite stays inside one cell, regardless of canvas size.

    Why this is the correct invariant: cell pitch is a property of the
    SOURCE image (where the generator placed the characters), not a property
    of the OUTPUT canvas the post-processor wants to produce. Treating the
    output cell_size as if it dictated the input pitch is the bug.
    Cell size is derived from raw_size and grid, never assumed from final
    canvas size.

    Pure deterministic Python. No LLM, no external API. Runs in O(cols*rows)
    crops + at most ``cols*rows`` LANCZOS resamples.
    """
    if cols <= 0 or rows <= 0:
        raise ValueError(f"grid must be positive, got cols={cols} rows={rows}")
    if cell_size <= 0:
        raise ValueError(f"cell_size must be positive, got {cell_size}")

    raw_w, raw_h = sheet.size
    canonical_w = cols * cell_size
    canonical_h = rows * cell_size

    # Case 1: exact match — direct slice, no resample.
    if raw_w == canonical_w and raw_h == canonical_h:
        cells: list[Image.Image] = []
        for r in range(rows):
            for c in range(cols):
                x0 = c * cell_size
                y0 = r * cell_size
                cells.append(sheet.crop((x0, y0, x0 + cell_size, y0 + cell_size)))
        return cells

    # Case 2 & 3: derive pitch from raw size. Use float pitch + rounded
    # boundaries so fractional canvases (e.g. 1254/8) still slice cleanly.
    pitch_x = raw_w / cols
    pitch_y = raw_h / rows

    cells = []
    for r in range(rows):
        for c in range(cols):
            x0 = round(c * pitch_x)
            y0 = round(r * pitch_y)
            x1 = round((c + 1) * pitch_x)
            y1 = round((r + 1) * pitch_y)
            # Clamp to canvas (last column/row absorbs any rounding overflow).
            x1 = min(x1, raw_w)
            y1 = min(y1, raw_h)
            crop = sheet.crop((x0, y0, x1, y1))
            if crop.size != (cell_size, cell_size):
                crop = crop.resize((cell_size, cell_size), Image.Resampling.LANCZOS)
            cells.append(crop)
    return cells


# ---------------------------------------------------------------------------
# Connected-components frame detection (Phase D)
# ---------------------------------------------------------------------------
@dataclass
class Component:
    bbox: tuple[int, int, int, int]  # left, top, right, bottom
    area: int
    centroid: tuple[float, float]


def label_components_numpy(mask) -> tuple[object, int]:
    """Connected-components labeling. Tries scipy.ndimage.label first."""
    try:
        from scipy.ndimage import label

        labels, n = label(mask)
        return labels, n
    except ImportError:
        return _label_components_bfs(mask)


def _label_components_bfs(mask) -> tuple[object, int]:
    """Pure-numpy BFS labeling. Slower than scipy but correct."""
    h, w = mask.shape
    labels = np.zeros((h, w), dtype=np.int32)
    next_label = 0
    for y in range(h):
        for x in range(w):
            if not mask[y, x] or labels[y, x] != 0:
                continue
            next_label += 1
            queue: deque[tuple[int, int]] = deque([(y, x)])
            while queue:
                cy, cx = queue.popleft()
                if not (0 <= cy < h and 0 <= cx < w):
                    continue
                if not mask[cy, cx] or labels[cy, cx] != 0:
                    continue
                labels[cy, cx] = next_label
                queue.append((cy - 1, cx))
                queue.append((cy + 1, cx))
                queue.append((cy, cx - 1))
                queue.append((cy, cx + 1))
    return labels, next_label


def extract_components(
    img: Image.Image,
    chroma: tuple[int, int, int] = MAGENTA,
    chroma_threshold: int = DEFAULT_CHROMA_THRESHOLD,
    min_pixels: int = DEFAULT_MIN_COMPONENT_PIXELS,
) -> tuple[list[Image.Image], list[Component]]:
    """Connected-components extraction. Returns (cropped images, metadata)."""
    if not HAS_NUMPY:
        raise RuntimeError(
            "Frame detection requires numpy. Run `pip install numpy` "
            "(or `pip install numpy scipy` for the faster path)."
        )

    img = img.convert("RGBA")
    arr = np.array(img)
    rgb = arr[..., :3].astype(int)
    diff = np.abs(rgb - np.array(chroma)).sum(axis=-1)
    non_chroma = diff > chroma_threshold

    labels, n_labels = label_components_numpy(non_chroma)

    crops: list[Image.Image] = []
    metas: list[Component] = []
    for label_id in range(1, n_labels + 1):
        ys, xs = np.where(labels == label_id)
        if len(ys) < min_pixels:
            continue
        top = int(ys.min())
        bot = int(ys.max()) + 1
        left = int(xs.min())
        right = int(xs.max()) + 1
        crop = img.crop((left, top, right, bot))
        crops.append(crop)
        metas.append(
            Component(
                bbox=(left, top, right, bot),
                area=len(ys),
                centroid=(float(xs.mean()), float(ys.mean())),
            )
        )

    return crops, metas


def assign_components_to_cells(
    components: list[Component],
    crops: list[Image.Image],
    grid_cols: int,
    grid_rows: int,
    sheet_w: int,
    sheet_h: int,
) -> list[Image.Image | None]:
    """Map components to cells via centroid; resolve collisions by area."""
    cell_w = sheet_w / grid_cols
    cell_h = sheet_h / grid_rows
    assignments: dict[int, tuple[Component, Image.Image]] = {}

    for comp, crop in zip(components, crops):
        cx, cy = comp.centroid
        col = min(int(cx // cell_w), grid_cols - 1)
        row = min(int(cy // cell_h), grid_rows - 1)
        idx = row * grid_cols + col
        if idx in assignments:
            if comp.area > assignments[idx][0].area:
                assignments[idx] = (comp, crop)
        else:
            assignments[idx] = (comp, crop)

    return [assignments[i][1] if i in assignments else None for i in range(grid_cols * grid_rows)]


def cmd_extract_frames(args: argparse.Namespace) -> int:
    src = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(src)
    cols, rows = _parse_grid(args.grid)
    expected = cols * rows

    try:
        crops, metas = extract_components(
            img,
            chroma_threshold=args.chroma_threshold,
            min_pixels=args.min_pixels,
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 4

    if args.cell_aware and cols > 1 and rows > 1:
        ordered = assign_components_to_cells(metas, crops, cols, rows, img.width, img.height)
    else:
        # natural top-left sort
        order = sorted(range(len(crops)), key=lambda i: (metas[i].bbox[1], metas[i].bbox[0]))
        ordered = [crops[i] for i in order]

    if not args.allow_count_mismatch and len(ordered) != expected:
        if args.cell_aware:
            non_none = sum(1 for x in ordered if x is not None)
            if non_none != expected:
                print(
                    f"ERROR: detected {non_none} components, grid expected {expected}",
                    file=sys.stderr,
                )
                return 5
        else:
            print(
                f"ERROR: detected {len(ordered)} components, grid expected {expected}",
                file=sys.stderr,
            )
            return 5

    name = args.name or src.stem
    metadata: dict = {
        "sheet": str(src),
        "grid": [cols, rows],
        "components": [],
        "rejected": 0,
        "warnings": [],
    }

    for i, crop in enumerate(ordered):
        if crop is None:
            metadata["warnings"].append(f"frame {i} missing (no component mapped)")
            continue
        out = output_dir / f"{name}_frame_{i:02d}.png"
        crop.save(out, format="PNG")

    for i, comp in enumerate(metas):
        metadata["components"].append(
            {
                "index": i,
                "bbox": list(comp.bbox),
                "area": comp.area,
                "centroid": list(comp.centroid),
            }
        )
    (output_dir / "frame_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"[extract-frames] wrote {len(metas)} frames to {output_dir}", file=sys.stderr)
    return 0


def _parse_grid(s: str) -> tuple[int, int]:
    parts = s.split("x")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"grid {s!r} malformed. Use CxR like '4x4'.")
    return int(parts[0]), int(parts[1])


# ---------------------------------------------------------------------------
# Normalization (portrait Phase C / spritesheet Phase F)
# ---------------------------------------------------------------------------
def find_bottom_anchor(img: Image.Image) -> int:
    """Return y-coordinate of lowest non-transparent pixel."""
    if HAS_NUMPY:
        arr = np.array(img.convert("RGBA"))
        alpha = arr[..., 3]
        has_pixel = alpha.max(axis=1) > 0
        nonzero = np.where(has_pixel)[0]
        if len(nonzero) == 0:
            return img.height
        return int(nonzero.max())

    pixels = img.convert("RGBA").load()
    w, h = img.size
    for y in range(h - 1, -1, -1):
        for x in range(w):
            if pixels[x, y][3] > 0:
                return y
    return img.height


def find_alpha_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """Return (top, bot, left, right) bbox of all non-transparent pixels.

    Differs from PIL's getbbox in that it walks alpha explicitly (not all
    color channels), which is important after bg-removal when low-alpha
    fringe pixels survive.
    """
    if HAS_NUMPY:
        arr = np.array(img.convert("RGBA"))
        alpha = arr[..., 3]
        ys, xs = np.where(alpha > 0)
        if len(ys) == 0:
            return None
        return int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    bbox = img.convert("RGBA").getbbox()
    if bbox is None:
        return None
    left, top, right, bot = bbox
    return top, bot - 1, left, right - 1


def detect_ground_line(
    frames: list[Image.Image],
    cell_h: int,
    bottom_zone_pct: float = 0.30,
    fallback_percentile: float = 75.0,
) -> int:
    """Detect a globally-stable ground line across all frames.

    Algorithm:

    1. For each frame, find its largest connected component (alpha > 0).
       (Using the bbox-bottom of all non-transparent pixels is a good-enough
       proxy when frames have already been bg-removed and contain only one
       character per cell.)
    2. Among the frames whose bbox-bottom falls within the lower
       `bottom_zone_pct` of the cell (default lower 30%), take the median
       bbox-bottom-Y. These are the "feet-on-ground" frames; the median is
       robust to a handful of outliers (a frame where the model drew the
       character one pixel higher than the rest).
    3. Fallback: if NO frame's bbox-bottom is in the lower zone (rare —
       implies every frame is aerial), return the `fallback_percentile`-th
       percentile of all bbox-bottom-Ys.

    Returns the Y coordinate (in cell-canvas space) at which the character's
    lowest grounded pixel typically sits. Each frame is later translated so
    its bbox-bottom lands AT this Y, which keeps the visual ground steady
    across the animation cycle.

    See `references/anchor-alignment.md` for the per-frame vs global trade-off.
    """
    if not frames:
        return cell_h - DEFAULT_BOTTOM_MARGIN

    bottoms: list[int] = []
    for fr in frames:
        bbox = find_alpha_bbox(fr)
        if bbox is None:
            continue
        bottoms.append(bbox[1])

    if not bottoms:
        return cell_h - DEFAULT_BOTTOM_MARGIN

    # Frames whose bbox-bottom is in the lower 30% of the cell are the
    # feet-on-ground reference frames.
    threshold_y = int(cell_h * (1 - bottom_zone_pct))
    grounded_bottoms = [b for b in bottoms if b >= threshold_y]

    if grounded_bottoms:
        # Median: robust to a single-frame outlier where one feet pixel is
        # shifted by ±1 due to AA / chroma fringe artifact.
        sorted_b = sorted(grounded_bottoms)
        return sorted_b[len(sorted_b) // 2]

    # Pure-aerial sequence (every frame's bbox-bottom is high in the cell).
    # Use the 75th percentile of all bbox-bottoms — pins the lowest reach
    # consistently across the animation.
    sorted_all = sorted(bottoms)
    idx = min(len(sorted_all) - 1, int(len(sorted_all) * fallback_percentile / 100.0))
    return sorted_all[idx]


def apply_ground_line_anchor(
    frame: Image.Image,
    ground_line_y: int,
    cell_w: int,
    cell_h: int,
    horizontal_mode: str = "centroid",
) -> Image.Image:
    """Translate `frame` so its alpha-bbox-bottom lands at `ground_line_y`.

    Unlike per-frame bottom-anchor (which moves the FRAME bottom to the cell
    bottom — and thus the character moves with bbox-height), this places the
    CHARACTER'S OWN bottom-most pixel at a fixed, globally-stable Y. Result:
    feet stay planted; head bounces only when the actual silhouette changes.

    `horizontal_mode`:
      - `centroid` (default): center the alpha-mass centroid horizontally.
        Preferred for full-body characters where the center of mass should
        sit on the cell's vertical axis.
      - `bbox`: center the alpha-bbox horizontally (legacy behavior).
        Reasonable for symmetric stances; can drift on lunge frames where
        the bbox extends right but the center of mass is still in the middle.
    """
    out = Image.new("RGBA", (cell_w, cell_h), (0, 0, 0, 0))
    bbox = find_alpha_bbox(frame)
    if bbox is None:
        return out
    top, bot, left, right = bbox
    bbox_h = bot - top + 1
    bbox_w = right - left + 1

    # Vertical: translate so bbox bottom lands at ground_line_y.
    paste_y = ground_line_y - bot

    # Horizontal: center the bbox or centroid in the cell.
    if horizontal_mode == "centroid" and HAS_NUMPY:
        arr = np.array(frame.convert("RGBA"))
        alpha = arr[..., 3]
        ys, xs = np.where(alpha > 0)
        if len(xs) > 0:
            cx = int(xs.mean())
            paste_x = (cell_w // 2) - cx
        else:
            paste_x = (cell_w - frame.width) // 2
    else:
        # bbox-center horizontal
        bbox_cx = (left + right) // 2
        paste_x = (cell_w // 2) - bbox_cx

    # Fit-to-cell: if the frame's bbox is taller or wider than the cell after
    # translation, scale it down (preserve aspect) so it still fits. Rare but
    # possible when an aerial-leap frame extends way beyond the cell.
    scale = 1.0
    if bbox_h > cell_h or bbox_w > cell_w:
        scale = min(cell_h / max(bbox_h, 1), cell_w / max(bbox_w, 1))

    if scale < 1.0:
        new_w = max(1, int(frame.width * scale))
        new_h = max(1, int(frame.height * scale))
        frame = frame.resize((new_w, new_h), Image.Resampling.LANCZOS)
        # Recompute bbox in the scaled frame
        rescaled_bbox = find_alpha_bbox(frame)
        if rescaled_bbox is None:
            return out
        top, bot, left, right = rescaled_bbox
        paste_y = ground_line_y - bot
        if horizontal_mode == "centroid" and HAS_NUMPY:
            arr = np.array(frame.convert("RGBA"))
            alpha = arr[..., 3]
            ys, xs = np.where(alpha > 0)
            if len(xs) > 0:
                cx = int(xs.mean())
                paste_x = (cell_w // 2) - cx
            else:
                paste_x = (cell_w - frame.width) // 2
        else:
            bbox_cx = (left + right) // 2
            paste_x = (cell_w // 2) - bbox_cx

    out.paste(frame, (paste_x, paste_y), frame)
    return out


def trim_to_bbox(img: Image.Image) -> Image.Image:
    """Crop to non-transparent bounding box."""
    bbox = img.convert("RGBA").getbbox()
    if bbox is None:
        return img
    return img.crop(bbox)


def shared_scale_height(frames: list[Image.Image], percentile: float = 95) -> int:
    """Return target height = Nth percentile of frame heights."""
    heights = sorted(f.height for f in frames)
    if not heights:
        return 0
    idx = int(len(heights) * (percentile / 100.0))
    idx = min(max(idx, 0), len(heights) - 1)
    return heights[idx]


def rescale_to_height(img: Image.Image, target_h: int) -> Image.Image:
    aspect = img.width / max(img.height, 1)
    new_w = max(1, int(target_h * aspect))
    return img.resize((new_w, target_h), Image.Resampling.LANCZOS)


def anchor_to_canvas(
    frame: Image.Image,
    canvas_w: int,
    canvas_h: int,
    bottom_margin: int = DEFAULT_BOTTOM_MARGIN,
    anchor_mode: str = "bottom",
    ground_line_y: int | None = None,
) -> Image.Image:
    """Place frame on transparent canvas with anchor controlled by `anchor_mode`.

    Modes:
      - `bottom` (legacy per-frame): place this frame's lowest pixel at
        `canvas_h - bottom_margin`. Frames with different alpha-bottom Y
        produce visible bouncing — see `apply_ground_line_anchor` for the
        global alternative.
      - `center`: vertically center the frame on the canvas. Use for
        sequences where the character is genuinely off-ground throughout
        (jump-loop, fly).
      - `ground-line`: translate so the frame's alpha-bbox-bottom lands at
        `ground_line_y`. Caller must pre-compute `ground_line_y` via
        `detect_ground_line(frames, canvas_h)` once for the whole batch.
        Provides drift-free animation across mixed grounded/aerial poses.
      - `auto`: pick `bottom` for upright frames (height/width > 1.2),
        `center` otherwise. Legacy behavior; superseded by `ground-line`.
    """
    if anchor_mode == "ground-line":
        if ground_line_y is None:
            ground_line_y = canvas_h - bottom_margin
        return apply_ground_line_anchor(frame, ground_line_y, canvas_w, canvas_h)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    if anchor_mode == "center":
        paste_y = (canvas_h - frame.height) // 2
    else:
        bottom = find_bottom_anchor(frame)
        paste_y = (canvas_h - bottom_margin) - bottom
    paste_x = (canvas_w - frame.width) // 2
    canvas.paste(frame, (paste_x, paste_y), frame)
    return canvas


def normalize_portrait(
    src: Path,
    dst: Path,
    target_w: int = 600,
    target_h: int = 980,
    padding_pct: float = 0.05,
) -> dict:
    """Trim, re-canvas with padding, bottom-anchor a portrait."""
    img = Image.open(src).convert("RGBA")
    trimmed = trim_to_bbox(img)
    if trimmed.width == 0 or trimmed.height == 0:
        raise RuntimeError("trimmed image is empty (alpha mask removed all content)")

    # Scale to fit within (target_w, target_h) with padding
    avail_w = int(target_w * (1 - 2 * padding_pct))
    avail_h = int(target_h * (1 - 2 * padding_pct))
    scale = min(avail_w / trimmed.width, avail_h / trimmed.height)
    new_w = max(1, int(trimmed.width * scale))
    new_h = max(1, int(trimmed.height * scale))
    scaled = trimmed.resize((new_w, new_h), Image.Resampling.LANCZOS)

    bottom_margin = int(target_h * padding_pct)
    anchored = anchor_to_canvas(scaled, target_w, target_h, bottom_margin=bottom_margin)
    dst.parent.mkdir(parents=True, exist_ok=True)
    anchored.save(dst, format="PNG")
    return {
        "input_size": [img.width, img.height],
        "trimmed_size": [trimmed.width, trimmed.height],
        "scaled_size": [new_w, new_h],
        "output_size": [target_w, target_h],
        "scale_factor": float(scale),
    }


def normalize_spritesheet(
    frames: list[Path],
    output_dir: Path,
    cell_w: int,
    cell_h: int,
    scale_percentile: float = 95,
    bottom_margin: int = DEFAULT_BOTTOM_MARGIN,
    anchor_mode: str = "ground-line",
) -> dict:
    """Shared-scale rescale + anchor alignment for spritesheet frames.

    `anchor_mode` defaults to `ground-line` (the global, drift-free anchor).
    Pass `bottom` for the legacy per-frame behavior (kept for backward compat
    on single-pose action loops where bbox-bottom genuinely tracks the feet).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    imgs = [Image.open(p).convert("RGBA") for p in frames]
    target_h = shared_scale_height(imgs, scale_percentile)
    target_h = min(target_h, cell_h - 2 * bottom_margin)

    rescaled_imgs = [rescale_to_height(img, target_h) for img in imgs]

    # Compute the global ground line ONCE across all rescaled frames so each
    # frame's translation puts its alpha-bbox-bottom at the same Y. This is
    # the drift fix: per-frame bottom-anchor moves with bbox-height, but the
    # global ground line is invariant across the batch.
    ground_line_y: int | None = None
    if anchor_mode == "ground-line":
        # Frames are not yet on the cell canvas; we need to compute ground
        # line in the post-translation coordinate system. We assume that
        # most frames (the grounded ones) will end up with their bottom at
        # `cell_h - bottom_margin`, so use that as the ground line.
        ground_line_y = cell_h - bottom_margin

    metadata: dict = {
        "scale_percentile": scale_percentile,
        "target_height": target_h,
        "cell_size": [cell_w, cell_h],
        "anchor_mode": anchor_mode,
        "ground_line_y": ground_line_y,
        "frames": [],
    }

    for src, img, rescaled in zip(frames, imgs, rescaled_imgs):
        anchored = anchor_to_canvas(
            rescaled,
            cell_w,
            cell_h,
            bottom_margin=bottom_margin,
            anchor_mode=anchor_mode,
            ground_line_y=ground_line_y,
        )
        out = output_dir / src.name
        anchored.save(out, format="PNG")
        anchor_y = find_bottom_anchor(anchored)
        metadata["frames"].append(
            {
                "name": src.name,
                "input_size": [img.width, img.height],
                "scaled_to": [rescaled.width, rescaled.height],
                "anchor_y": anchor_y,
            }
        )

    (output_dir / "anchor_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def cmd_normalize(args: argparse.Namespace) -> int:
    if args.mode == "portrait":
        try:
            meta = normalize_portrait(
                Path(args.input),
                Path(args.output),
                target_w=args.target_w,
                target_h=args.target_h,
            )
        except RuntimeError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 4
        print(f"[normalize] portrait {args.input} -> {args.output} ({meta['output_size']})", file=sys.stderr)
        return 0

    # spritesheet
    frames = sorted(Path(args.input_dir).glob("*_frame_*.png"))
    if not frames:
        print(f"ERROR: no *_frame_*.png files in {args.input_dir}", file=sys.stderr)
        return 2
    # Map per-frame-bottom alias to the legacy `bottom` mode so internal
    # branching stays simple. ground-line is the new default.
    anchor_mode = "bottom" if args.anchor_mode == "per-frame-bottom" else args.anchor_mode
    meta = normalize_spritesheet(
        frames,
        Path(args.output_dir),
        cell_w=args.cell_size,
        cell_h=args.cell_size,
        scale_percentile=args.scale_percentile,
        anchor_mode=anchor_mode,
    )
    print(
        f"[normalize] spritesheet {len(frames)} frames -> {args.output_dir} (scaled to h={meta['target_height']})",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# Portrait dimension validator (Phase D)
# ---------------------------------------------------------------------------
def cmd_validate_portrait(args: argparse.Namespace) -> int:
    img = Image.open(args.input)
    w, h = img.size
    aspect = h / w if w > 0 else 0

    errors: list[str] = []
    if not (PORTRAIT_WIDTH_RANGE[0] <= w <= PORTRAIT_WIDTH_RANGE[1]):
        errors.append(f"width {w} outside {PORTRAIT_WIDTH_RANGE}")
    if not (PORTRAIT_HEIGHT_RANGE[0] <= h <= PORTRAIT_HEIGHT_RANGE[1]):
        errors.append(f"height {h} outside {PORTRAIT_HEIGHT_RANGE}")
    if not (PORTRAIT_ASPECT_MIN <= aspect <= PORTRAIT_ASPECT_MAX):
        errors.append(f"aspect 1:{aspect:.2f} outside [1:{PORTRAIT_ASPECT_MIN}, 1:{PORTRAIT_ASPECT_MAX}]")

    if errors:
        if args.force:
            print(
                f"WARNING: --force-dimensions used; output bypasses gate ({'; '.join(errors)})",
                file=sys.stderr,
            )
            return 0
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 6

    print(
        f"[validate-portrait] PASS ({w}x{h}, aspect 1:{aspect:.2f})",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# Auto-curation (Phase G)
# ---------------------------------------------------------------------------
@dataclass
class VariantStats:
    path: Path
    seed: int
    edge_touch_frames: int = 0
    height_variance: float = 0.0
    frame_count: int = 0


def _compute_variant_stats(frames: list[Path], seed: int) -> VariantStats:
    if not frames:
        return VariantStats(path=Path(), seed=seed)
    heights: list[int] = []
    edge_touches = 0
    for fp in frames:
        img = Image.open(fp).convert("RGBA")
        bbox = img.getbbox()
        if bbox is None:
            continue
        w, h = img.size
        if bbox[0] == 0 or bbox[1] == 0 or bbox[2] == w or bbox[3] == h:
            edge_touches += 1
        heights.append(bbox[3] - bbox[1])
    median = sorted(heights)[len(heights) // 2] if heights else 0
    variance = sum((x - median) ** 2 for x in heights) / max(len(heights), 1)
    return VariantStats(
        path=frames[0].parent,
        seed=seed,
        edge_touch_frames=edge_touches,
        height_variance=variance,
        frame_count=len(frames),
    )


def cmd_auto_curate(args: argparse.Namespace) -> int:
    variants_dir = Path(args.variants_dir)
    variants = sorted([p for p in variants_dir.iterdir() if p.is_dir()])
    if not variants:
        print(f"ERROR: no variant subdirectories in {variants_dir}", file=sys.stderr)
        return 5

    stats: list[VariantStats] = []
    for v in variants:
        seed_match = v.name.split("_")[-1] if "_" in v.name else "0"
        try:
            seed = int(seed_match)
        except ValueError:
            seed = 0
        frames = sorted(v.glob("*_frame_*.png"))
        s = _compute_variant_stats(frames, seed=seed)
        s.path = v
        stats.append(s)

    stats.sort(key=lambda s: (s.edge_touch_frames, s.height_variance, s.seed))
    winner = stats[0]
    print(
        f"[auto-curate] winner: {winner.path.name} "
        f"(edge_touch={winner.edge_touch_frames}, variance={winner.height_variance:.2f}, seed={winner.seed})",
        file=sys.stderr,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "winner": str(winner.path),
                "ranking": [
                    {
                        "path": str(s.path),
                        "edge_touch_frames": s.edge_touch_frames,
                        "height_variance": s.height_variance,
                        "seed": s.seed,
                    }
                    for s in stats
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


# ---------------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------------
def cmd_contact_sheet(args: argparse.Namespace) -> int:
    variants_dir = Path(args.variants_dir)
    variants = sorted([p for p in variants_dir.iterdir() if p.is_dir()])
    if not variants:
        print(f"ERROR: no variants in {variants_dir}", file=sys.stderr)
        return 5

    thumbs: list[Image.Image] = []
    for v in variants:
        sheet_candidate = next(v.glob("*_sheet.png"), None) or next(v.glob("*.png"), None)
        if sheet_candidate is None:
            continue
        img = Image.open(sheet_candidate).convert("RGBA")
        img.thumbnail((args.thumb_size, args.thumb_size), Image.Resampling.LANCZOS)
        thumbs.append(img)

    if not thumbs:
        print(f"ERROR: no images found in any variant dir", file=sys.stderr)
        return 5

    cols = max(1, args.cols)
    rows = (len(thumbs) + cols - 1) // cols
    cell_w = max(t.width for t in thumbs)
    cell_h = max(t.height for t in thumbs)
    sheet = Image.new("RGBA", (cell_w * cols, cell_h * rows), (32, 32, 32, 255))
    draw = ImageDraw.Draw(sheet)
    for i, thumb in enumerate(thumbs):
        r, c = divmod(i, cols)
        x = c * cell_w + (cell_w - thumb.width) // 2
        y = r * cell_h + (cell_h - thumb.height) // 2
        sheet.paste(thumb, (x, y), thumb)
        draw.text((c * cell_w + 4, r * cell_h + 4), f"#{i}", fill=(255, 255, 255, 255))

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.output, format="PNG")
    print(f"[contact-sheet] {args.output} ({len(thumbs)} variants, {cols}x{rows})", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# Final assembly (Phase H)
# ---------------------------------------------------------------------------
def assemble_outputs(
    frames: list[Image.Image],
    output_dir: Path,
    name: str,
    grid_cols: int,
    grid_rows: int,
    cell_w: int,
    cell_h: int,
    fps: int,
    emit_strips: bool,
) -> dict:
    """Phase H: PNG sheet, GIF, WebP, atlas JSON, optional per-direction strips."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # PNG sheet
    sheet = Image.new("RGBA", (cell_w * grid_cols, cell_h * grid_rows), (0, 0, 0, 0))
    for i, frame in enumerate(frames):
        if frame is None:
            continue
        r, c = divmod(i, grid_cols)
        sheet.paste(frame, (c * cell_w, r * cell_h), frame)
    sheet_path = output_dir / f"{name}_sheet.png"
    sheet.save(sheet_path, format="PNG")

    # Animated WebP — preferred output. Full 8-bit alpha, no quantization
    # bleed at silhouette edges. Modern browsers autoplay animated WebP
    # the same way they autoplay GIF.
    webp_path = output_dir / f"{name}.webp"
    duration = int(1000 / max(fps, 1))
    valid_frames = [f for f in frames if f is not None]
    if valid_frames:
        valid_frames[0].save(
            webp_path,
            save_all=True,
            append_images=valid_frames[1:],
            duration=duration,
            loop=0,
            format="WebP",
        )

    # Animated GIF — compatibility fallback. GIF's 1-bit alpha + 256-color
    # adaptive palette can resurrect magenta fringe at silhouette edges
    # even when the RGBA source is clean (the palette quantizer allocates
    # a pink index from anti-aliased boundary pixels). Matte-compositing
    # each frame over a neutral middle-gray BEFORE quantizing prevents
    # this — the palette has no pink reference, anti-aliased edges blend
    # to gray. See bg-removal-local.md "GIF format bleed at silhouette
    # edges" for details.
    gif_path = output_dir / f"{name}.gif"
    if valid_frames:
        gif_imgs = [
            matte_composite(f, matte=(40, 40, 40)).convert("P", palette=Image.Palette.ADAPTIVE) for f in valid_frames
        ]
        gif_imgs[0].save(
            gif_path,
            save_all=True,
            append_images=gif_imgs[1:],
            duration=duration,
            loop=0,
            disposal=2,
        )

    # Per-frame PNGs
    frames_dir = output_dir / f"{name}_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    for i, frame in enumerate(frames):
        if frame is None:
            continue
        frame.save(frames_dir / f"{name}_frame_{i:02d}.png", format="PNG")

    # Phaser atlas JSON
    atlas: dict = {
        "frames": {},
        "meta": {
            "app": "game-sprite-pipeline",
            "version": "1.0.0",
            "image": f"{name}_sheet.png",
            "format": "RGBA8888",
            "size": {"w": sheet.width, "h": sheet.height},
            "scale": "1",
        },
    }
    for i, frame in enumerate(frames):
        if frame is None:
            continue
        r, c = divmod(i, grid_cols)
        anchor_y = find_bottom_anchor(frame)
        atlas["frames"][f"frame_{i:02d}.png"] = {
            "frame": {"x": c * cell_w, "y": r * cell_h, "w": cell_w, "h": cell_h},
            "rotated": False,
            "trimmed": False,
            "spriteSourceSize": {"x": 0, "y": 0, "w": cell_w, "h": cell_h},
            "sourceSize": {"w": cell_w, "h": cell_h},
            "anchor": {"x": 0.5, "y": round(anchor_y / cell_h, 4) if cell_h else 0},
        }
    atlas_path = output_dir / f"{name}.json"
    atlas_path.write_text(json.dumps(atlas, indent=2), encoding="utf-8")

    # Per-direction strips (4xR or 8xR only)
    strips: dict[str, str] = {}
    if emit_strips and grid_cols in (4, 8):
        directions_4 = ["down", "left", "right", "up"]
        directions_8 = ["down", "down-left", "left", "up-left", "up", "up-right", "right", "down-right"]
        directions = directions_4 if grid_cols == 4 else directions_8
        for r in range(grid_rows):
            if r >= len(directions):
                break
            dir_name = directions[r]
            strip = Image.new("RGBA", (cell_w * grid_cols, cell_h), (0, 0, 0, 0))
            for c in range(grid_cols):
                idx = r * grid_cols + c
                if idx < len(frames) and frames[idx] is not None:
                    strip.paste(frames[idx], (c * cell_w, 0), frames[idx])
            strip_path = output_dir / f"{name}_{dir_name}.png"
            strip.save(strip_path, format="PNG")
            strips[dir_name] = str(strip_path)

    return {
        "sheet": str(sheet_path),
        "gif": str(gif_path),
        "webp": str(webp_path),
        "frames_dir": str(frames_dir),
        "atlas": str(atlas_path),
        "strips": strips,
    }


def cmd_assemble(args: argparse.Namespace) -> int:
    cols, rows = _parse_grid(args.grid)
    frame_paths = sorted(Path(args.frames_dir).glob("*_frame_*.png"))
    expected = cols * rows
    frames: list[Image.Image | None] = []
    by_idx: dict[int, Image.Image] = {}
    for p in frame_paths:
        idx_str = p.stem.split("_frame_")[-1]
        try:
            idx = int(idx_str)
        except ValueError:
            continue
        by_idx[idx] = Image.open(p).convert("RGBA")
    for i in range(expected):
        frames.append(by_idx.get(i))

    name = args.name or Path(args.frames_dir).name
    emit_strips = cols in (4, 8) and not args.no_strips
    result = assemble_outputs(
        frames=frames,
        output_dir=Path(args.output_dir),
        name=name,
        grid_cols=cols,
        grid_rows=rows,
        cell_w=args.cell_size,
        cell_h=args.cell_size,
        fps=args.fps,
        emit_strips=emit_strips,
    )
    print(
        f"[assemble] {name}: sheet+gif+webp+atlas+frames written to {args.output_dir}",
        file=sys.stderr,
    )
    if result["strips"]:
        print(f"[assemble] strips: {', '.join(result['strips'].keys())}", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    rb = sub.add_parser("remove-bg", help="Remove background (magenta chroma key default)")
    rb.add_argument("input", nargs="+", help="Input PNG path(s)")
    rb.add_argument("--output", help="Output path (single input)")
    rb.add_argument("--output-dir", help="Output directory (multi-input)")
    # Legacy --mode kept for backward compat with the pipeline orchestrator.
    rb.add_argument("--mode", choices=["chroma", "rembg", "auto"], default="chroma")
    # New canonical flag. magenta = the default two-pass despill chroma key.
    # gray-tolerance = road-to-aew's algorithm for backends that paint #3a3a3a.
    rb.add_argument(
        "--bg-mode",
        choices=["magenta", "gray-tolerance"],
        default=None,
        help="Background removal strategy. magenta=despill chroma; gray-tolerance=road-to-aew #3a3a3a algorithm.",
    )
    rb.add_argument("--chroma-threshold", type=int, default=DEFAULT_CHROMA_THRESHOLD)
    rb.add_argument(
        "--pass2-threshold",
        type=int,
        default=DEFAULT_PASS2_THRESHOLD,
        help="Pass-2 edge-flood threshold (default 90; despill protects character pixels).",
    )
    rb.add_argument(
        "--despill-strength",
        type=float,
        default=DEFAULT_DESPILL_STRENGTH,
        help="Despill strength for pass 2 (0=off; 1.0=aggressive preserve).",
    )
    rb.add_argument(
        "--alpha-dilate",
        type=int,
        default=DEFAULT_ALPHA_DILATE_RADIUS,
        help="Pixel radius for alpha-zero dilation after chroma key (kills 1-px halo).",
    )
    rb.add_argument(
        "--gray-bg",
        type=int,
        nargs=3,
        default=list(GRAY_BG_DEFAULT),
        metavar=("R", "G", "B"),
        help="Background RGB for --bg-mode gray-tolerance (default 58 58 58).",
    )
    rb.add_argument(
        "--gray-tolerance",
        type=int,
        default=GRAY_BG_TOLERANCE_DEFAULT,
        help="Per-channel tolerance for gray-tolerance mode (default 30).",
    )
    rb.add_argument(
        "--watermark-margin",
        type=int,
        default=WATERMARK_MARGIN_DEFAULT,
        help="Corner box size (px) cleaned of bright pixels before gray-tolerance masking.",
    )
    rb.set_defaults(func=cmd_remove_bg)

    ef = sub.add_parser("extract-frames", help="Phase D: connected-components frame detection")
    ef.add_argument("--input", required=True, help="Spritesheet PNG path")
    ef.add_argument("--grid", required=True, help="Expected grid CxR (e.g., 4x4)")
    ef.add_argument("--output-dir", required=True, help="Where to write frame PNGs")
    ef.add_argument("--name", help="Frame name prefix (default: input stem)")
    ef.add_argument("--chroma-threshold", type=int, default=DEFAULT_CHROMA_THRESHOLD)
    ef.add_argument("--min-pixels", type=int, default=DEFAULT_MIN_COMPONENT_PIXELS)
    ef.add_argument("--cell-aware", action="store_true", default=True, help="Map components to cells via centroid")
    ef.add_argument("--allow-count-mismatch", action="store_true", help="Tolerate component count != grid")
    ef.set_defaults(func=cmd_extract_frames)

    nz = sub.add_parser("normalize", help="Trim/scale/anchor")
    nz.add_argument("--mode", choices=["portrait", "spritesheet"], required=True)
    nz.add_argument("--input", help="Input image (portrait mode)")
    nz.add_argument("--input-dir", help="Input directory of frames (spritesheet mode)")
    nz.add_argument("--output", help="Output path (portrait)")
    nz.add_argument("--output-dir", help="Output directory (spritesheet)")
    nz.add_argument("--target-w", type=int, default=600)
    nz.add_argument("--target-h", type=int, default=980)
    nz.add_argument("--cell-size", type=int, default=256)
    nz.add_argument("--scale-percentile", type=float, default=95)
    nz.add_argument(
        "--anchor-mode",
        choices=["bottom", "center", "auto", "ground-line", "per-frame-bottom"],
        default="ground-line",
        help=(
            "Anchor strategy. ground-line (default): each frame's "
            "alpha-bbox-bottom lands at a globally-stable ground-Y; "
            "drift-free across mixed grounded/aerial poses. "
            "per-frame-bottom (alias: bottom): legacy per-frame anchor "
            "(drifts when bbox heights vary). center: vertical center. "
            "auto: heuristic legacy fallback."
        ),
    )
    nz.set_defaults(func=cmd_normalize)

    vp = sub.add_parser("validate-portrait", help="Phase D portrait dimension gate")
    vp.add_argument("input", help="Portrait PNG path")
    vp.add_argument("--force", action="store_true", dest="force", help="Skip the gate (logs warning)")
    vp.set_defaults(func=cmd_validate_portrait)

    cs = sub.add_parser("contact-sheet", help="Build a variant contact sheet image")
    cs.add_argument("--variants-dir", required=True, help="Directory containing variant_NNN/ subdirs")
    cs.add_argument("--output", required=True, help="Output contact sheet PNG")
    cs.add_argument("--cols", type=int, default=4)
    cs.add_argument("--thumb-size", type=int, default=256)
    cs.set_defaults(func=cmd_contact_sheet)

    ac = sub.add_parser("auto-curate", help="Phase G: deterministic ranking of variants")
    ac.add_argument("--variants-dir", required=True)
    ac.add_argument("--output", required=True, help="Where to write ranking JSON")
    ac.set_defaults(func=cmd_auto_curate)

    ab = sub.add_parser("assemble", help="Phase H: PNG sheet + GIF + WebP + atlas + strips")
    ab.add_argument("--frames-dir", required=True)
    ab.add_argument("--grid", required=True)
    ab.add_argument("--cell-size", type=int, default=256)
    ab.add_argument("--output-dir", required=True)
    ab.add_argument("--name")
    ab.add_argument("--fps", type=int, default=DEFAULT_GIF_FPS)
    ab.add_argument("--no-strips", action="store_true", help="Skip per-direction strips")
    ab.set_defaults(func=cmd_assemble)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
