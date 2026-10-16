"""Locate a target in an image with Jev's Box primitive: geometry helpers plus one orchestrator.

``locate(image, target)`` asks one request with a Box, a presence Choice (or Noul), and a
count Choice. A Box always returns edges, so code reads the presence answer and
the count first and ignores the box when the target is absent. Then, as needed:

    * refine: confidence under ``confidence_min`` -> crop a padded region from the
      ORIGINAL full-resolution image and ask again, then map the box back;
    * tiles: with ``tile_grid``, a Choice over tile pictures finds the region of a
      small target (or one instance of several), and a Box runs on that tile;
    * edge check: crop to the box and ask one Noul per edge ("does the target
      continue past the top edge?"); move each yes-edge outward and ask again.

All boxes are fractions 0-1 of the image from the top-left (``left < right``,
``top < bottom``). Fractions survive resizing, so a box found on a shrunk or
cropped copy maps back to the full image with ``to_parent``. Pixels only appear
in ``to_pixels`` and ``center``. Nothing here logs image bytes.

Crops keep each side at 280 px or more and the aspect under 5.5:1 where the source
allows, so ``prepare_image`` never pads (padding would shift the fractions).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, NamedTuple

import jev_images
import jev_transport
from jev_images import MIN_SIDE, JevImage, JevImageError
from PIL import Image

# --- Tunables ---
# Box confidence threshold. TypeSafe publishes none; this is MEASURED, provisional, 2026-10-16, jev-1.14.0,
# synthetic shapes. Clean cases scored 0.85-0.95 (IoU 0.91-0.97). A 30 px target in a 3000x2000 image scored
# 0.64-0.74 with IoU 0.09-0.50 in one prompt layout and 0.75-0.84 with IoU 0.06-0.18 in the final one, so
# confidence alone does NOT flag a small-target miss. SMALL_BOX_PX adds a size rule that does (all six of those
# first boxes were under 64 px as sent). Refine crops scored 0.90-0.97 with IoU 0.55-0.69. Re-measure on your images.
CONFIDENCE_MIN = 0.8
PRESENCE_MIN = 0.7
SMALL_BOX_PX = 64  # a first box under this many px as sent is coarse (edges land on a ~2% grid): refine it
EDGE_YES = 0.5  # an edge Noul above this means the target continues past that edge
EDGE_PAD = 0.1  # margin around the box in the edge-check crop, as a fraction of the box size
EDGE_STEP = 0.15  # how far a yes-edge moves outward, as a fraction of the current box size
REFINE_PAD = 0.5
REFINE_MIN_SIDE = 560  # px of source context in a refine crop
REFINE_UPSCALE_PX = 1080  # refine crops are enlarged toward this long side: Jev reads high-resolution images better
LOW_RES_PX = 1080  # an image sent with a shorter long side gets a warning
INDECISIVE_PRESENCE = 0.3  # presence from here up to presence_min is a coin flip worth a smarter model
MAX_ASPECT = 5.5  # prepare_image pads beyond 1568:280 = 5.6
COUNTS = ("none", "one", "several")
PRESENCE_MODES = ("choice", "noul")


class JevBoxError(ValueError):
    """A Box request cannot be built, or Jev's answer is malformed."""


@dataclass(frozen=True)
class Box:
    """Edges as fractions 0-1 of an image, measured from the top-left."""

    top: float
    bottom: float
    left: float
    right: float

    def __post_init__(self) -> None:
        for name in ("top", "bottom", "left", "right"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0.0 <= v <= 1.0:
                raise JevBoxError(f"box {name}={v!r} is not a fraction in [0, 1]")
        if not (self.left < self.right and self.top < self.bottom):
            raise JevBoxError("box needs left < right and top < bottom")

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @classmethod
    def from_answer(cls, raw: Any) -> Box:
        """Build a Box from Jev's ``{top, bottom, left, right}`` dict; clamp tiny overshoot, reject junk."""
        if not isinstance(raw, dict) or not {"top", "bottom", "left", "right"} <= raw.keys():
            raise JevBoxError("box answer lacks top/bottom/left/right")
        try:
            vals = {k: min(1.0, max(0.0, float(raw[k]))) for k in ("top", "bottom", "left", "right")}
        except (TypeError, ValueError) as exc:
            raise JevBoxError("box answer has a non-numeric edge") from exc
        return cls(**vals)

    def as_dict(self) -> dict[str, float]:
        return {"top": self.top, "bottom": self.bottom, "left": self.left, "right": self.right}


class Crop(NamedTuple):
    """A Pillow crop of a parent image plus where it sits in the parent."""

    image: Any
    box: Box  # the crop's rectangle in parent fractions


class Tile(NamedTuple):
    """One tile of a grid: Pillow image, its rectangle in parent fractions, and its grid cell."""

    image: Any
    box: Box
    row: int
    col: int


# --- Geometry ---


def to_pixels(box: Box, width: int, height: int) -> tuple[int, int, int, int]:
    """Return ``(left, top, right, bottom)`` in pixels: edges floor/ceil outward and stay inside the image."""
    return (
        max(0, math.floor(box.left * width)),
        max(0, math.floor(box.top * height)),
        min(width, math.ceil(box.right * width)),
        min(height, math.ceil(box.bottom * height)),
    )


def center(box: Box, width: int, height: int) -> tuple[float, float]:
    """The box center ``(x, y)`` in pixels: the point to click."""
    return (box.left + box.right) / 2 * width, (box.top + box.bottom) / 2 * height


def iou(a: Box, b: Box) -> float:
    """Intersection over union of two boxes in the same frame."""
    w = min(a.right, b.right) - max(a.left, b.left)
    h = min(a.bottom, b.bottom) - max(a.top, b.top)
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / (a.width * a.height + b.width * b.height - inter)


def pad(box: Box, frac: float) -> Box:
    """Grow the box by ``frac`` of its own width and height on every side, clamped to 0-1."""
    dx, dy = box.width * frac, box.height * frac
    return Box(max(0.0, box.top - dy), min(1.0, box.bottom + dy), max(0.0, box.left - dx), min(1.0, box.right + dx))


def to_parent(child: Box, crop_box: Box) -> Box:
    """Map edges measured inside a crop back to fractions of the crop's parent image."""
    return Box(
        top=crop_box.top + child.top * crop_box.height,
        bottom=crop_box.top + child.bottom * crop_box.height,
        left=crop_box.left + child.left * crop_box.width,
        right=crop_box.left + child.right * crop_box.width,
    )


def _span(lo: float, hi: float, need: float, limit: float) -> tuple[float, float]:
    """Grow [lo, hi] about its center to length ``need``, sliding inside [0, limit]."""
    if hi - lo >= need or need >= limit:
        return (0.0, limit) if need >= limit else (lo, hi)
    mid = (lo + hi) / 2
    lo, hi = mid - need / 2, mid + need / 2
    if lo < 0:
        lo, hi = 0.0, need
    elif hi > limit:
        lo, hi = limit - need, limit
    return lo, hi


def crop(
    source: Any,
    box: Box,
    *,
    pad_frac: float = 0.0,
    min_side_px: int = MIN_SIDE,
    max_aspect: float | None = MAX_ASPECT,
    upscale_to: int | None = None,
) -> Crop:
    """Crop ``box`` (plus ``pad_frac`` margin) from a full-resolution Pillow image.

    The crop grows about its center until each side has at least ``min_side_px`` source
    pixels and the aspect is at most ``max_aspect`` (pass ``None`` to keep a tight crop).
    It slides to stay inside the image. Take ``source`` from the original, not a
    downscaled copy, or the crop loses the resolution that makes it worth taking.
    ``upscale_to`` enlarges a crop whose long side is shorter (Lanczos, capped at 1568 px); fractions are unchanged.
    Returns the crop and its rectangle in parent fractions.
    """
    width, height = source.size
    grown = pad(box, pad_frac) if pad_frac else box
    l, t, r, b = grown.left * width, grown.top * height, grown.right * width, grown.bottom * height
    need_w, need_h = max(min_side_px, 1), max(min_side_px, 1)
    if max_aspect is not None:
        need_w = max(need_w, (b - t) / max_aspect)
        need_h = max(need_h, (r - l) / max_aspect)
    l, r = _span(l, r, need_w, width)
    t, b = _span(t, b, need_h, height)
    px = (math.floor(l), math.floor(t), min(width, math.ceil(r)), min(height, math.ceil(b)))
    if px[2] <= px[0] or px[3] <= px[1]:
        raise JevBoxError("crop has no pixels")
    parent = Box(px[1] / height, px[3] / height, px[0] / width, px[2] / width)
    piece = source.crop(px)
    if upscale_to and max(piece.size) < upscale_to:
        k = min(upscale_to, jev_images.MAX_SIDE) / max(piece.size)
        piece = piece.resize((round(piece.width * k), round(piece.height * k)), Image.Resampling.LANCZOS)
    return Crop(piece, parent)


def tiles(source: Any, rows: int, cols: int, *, overlap: float = 0.1, min_side_px: int = MIN_SIDE) -> list[Tile]:
    """Cut ``source`` into a grid of overlapping tiles, each at least ``min_side_px`` per side.

    ``overlap`` is the fraction of a tile shared with each neighbor, so a target on a
    seam still sits whole in one tile. When the grid would make a tile too small, rows
    and cols shrink (merging tiles) until every tile fits; an image under the minimum
    in either direction gives one tile on that axis. Tiles come from the full-resolution source.
    """
    if rows < 1 or cols < 1:
        raise JevBoxError("tile grid needs rows >= 1 and cols >= 1")
    if not 0.0 <= overlap < 0.5:
        raise JevBoxError("overlap must be in [0, 0.5)")
    width, height = source.size

    def tile_len(total: int, n: int) -> float:
        return total / (n - (n - 1) * overlap)  # n tiles overlapping by `overlap` of a tile cover the span

    while rows > 1 and tile_len(height, rows) < min_side_px:
        rows -= 1
    while cols > 1 and tile_len(width, cols) < min_side_px:
        cols -= 1
    th, tw = tile_len(height, rows), tile_len(width, cols)
    out: list[Tile] = []
    for row in range(rows):
        for col in range(cols):
            top = row * th * (1 - overlap) if rows > 1 else 0.0
            left = col * tw * (1 - overlap) if cols > 1 else 0.0
            px = (
                round(left),
                round(top),
                min(width, round(left + tw)),
                min(height, round(top + th)),
            )
            parent = Box(px[1] / height, px[3] / height, px[0] / width, px[2] / width)
            out.append(Tile(source.crop(px), parent, row, col))
    return out


# --- Result types ---


@dataclass
class Step:
    """One request in a locate run."""

    name: str
    questions: list[str]
    input_tokens: int | None


@dataclass
class LocateResult:
    """Outcome of ``locate``. ``box`` is in fractions of the original image; ``None`` when absent."""

    status: str  # found | absent | several | low_confidence
    present: float
    count: str | None  # none | one | several
    count_exact: int | None  # set when count_max was given and the count is within it
    box: Box | None
    pixel_box: tuple[int, int, int, int] | None
    confidence: float | None
    image_size: tuple[int, int]
    steps: list[Step] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    edge_verified: bool | None = None  # None: edge check off or skipped
    box_before_edge: Box | None = None  # the box as it stood before the edge check moved any edge
    escalation_reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def needs_escalation(self) -> bool:
        """True when Jev is not confident: hand the image to a stronger model or a person instead of looping.

        Box is experimental. Treat this result as signals (presence, count, confidence, edge check, notes),
        and check with the app (DOM, preview state) when it can answer.
        """
        return bool(self.escalation_reasons)

    @property
    def input_tokens(self) -> int:
        """Sum of ``usage.input_tokens`` over all requests (a request without usage adds 0)."""
        return sum(s.input_tokens or 0 for s in self.steps)

    @property
    def requests(self) -> int:
        return len(self.steps)

    @property
    def center(self) -> tuple[float, float] | None:
        return center(self.box, *self.image_size) if self.box else None


# --- Orchestrator ---


class _Run:
    """State of one locate call: sends requests, sums tokens, keeps the log."""

    def __init__(self, timeout: float, size: tuple[int, int], context: dict[str, Any] | None = None) -> None:
        self.timeout = timeout
        self.size = size
        self.context = context
        self.warnings: list[str] = []
        self.steps: list[Step] = []
        self.notes: list[str] = []

    def ask(
        self,
        name: str,
        state: dict[str, Any],
        questions: dict[str, Any],
        images: dict[str, JevImage] | None = None,
    ) -> dict[str, Any]:
        if self.context and name != "edge_check":
            state = {**state, "context": self.context}  # structured facts (DOM, app data) beside the picture
        if name != "edge_check":
            for value in state.values():
                if isinstance(value, JevImage):
                    prepared = value.resolve()
                    if max(prepared.width, prepared.height) < LOW_RES_PX:
                        self.warnings.append(
                            f"{name}: picture sent at {prepared.width}x{prepared.height}, long side under "
                            f"{LOW_RES_PX} px; Box is less accurate on low-resolution images"
                        )
        result = jev_transport.evaluate(state, questions, timeout=self.timeout, images=images)
        usage = result.get("usage")
        tokens = usage.get("input_tokens") if isinstance(usage, dict) else None
        self.steps.append(Step(name, list(questions), tokens if isinstance(tokens, int) else None))
        answers = result.get("answers")
        if not isinstance(answers, dict):
            raise JevBoxError("Jev response has no answers")
        return answers


def _box_answer(answers: dict[str, Any], key: str) -> tuple[Box, float]:
    a = answers.get(key)
    if not isinstance(a, dict):
        raise JevBoxError(f"no answer for {key}")
    conf = a.get("confidence")
    if isinstance(conf, bool) or not isinstance(conf, (int, float)):
        raise JevBoxError(f"{key} answer has no numeric confidence")
    return Box.from_answer(a.get("box")), float(conf)


def _noul(answers: dict[str, Any], key: str) -> float:
    v = (answers.get(key) or {}).get("noul")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise JevBoxError(f"no numeric noul for {key}")
    return float(v)


def _choice(answers: dict[str, Any], key: str) -> str:
    v = (answers.get(key) or {}).get("choice")
    if not isinstance(v, str):
        raise JevBoxError(f"no choice for {key}")
    return v


def _target_clause(target: str, reference: JevImage | None) -> str:
    return f"{target}, the one that matches the reference picture {{img:reference}}" if reference else target


def _count_question(subject: str, target: str, count_max: int | None = None) -> dict[str, Any]:
    if count_max is not None:
        # Exact count: a Choice whose options are "0".."N" reads counts more reliably than a Noul.
        criteria: dict[str, Any] = {
            str(n): {"what": f"Exactly {n} instance(s) of the target."} for n in range(count_max + 1)
        }
        criteria[f"{count_max + 1}+"] = {"what": f"More than {count_max} instances."}
    else:
        criteria = {
            "none": {"what": "The target is not in the image.", "not_for": "A similar but different object."},
            "one": {"what": "Exactly one instance of the target."},
            "several": {"what": "Two or more instances that look the same or fit the description equally well."},
        }
    return {"type": "choice", "instructions": f"How many instances of {target} are in {subject}?", "criteria": criteria}


def _normalize_count(choice: str, count_max: int | None) -> tuple[str, int | None]:
    """Map a count Choice answer to ``(none|one|several, exact count or None)``."""
    if count_max is None:
        if choice not in COUNTS:
            raise JevBoxError(f"count choice {choice!r} is not one of {COUNTS}")
        return choice, None
    digits = choice.rstrip("+")
    if not digits.isdigit():
        raise JevBoxError(f"count choice {choice!r} is not a number")
    n = int(digits)
    return ("none" if n == 0 else "one" if n == 1 else "several"), (None if choice.endswith("+") else n)


def _presence_question(clause: str, subject: str, mode: str) -> dict[str, Any]:
    """Is the target visible? A Choice present/absent by default: on images it reads more decisively than a Noul."""
    if mode == "noul":
        return {"type": "noul", "instructions": f"Is {clause} visible in {subject}?"}
    return {
        "type": "choice",
        "instructions": f"Is {clause} visible in {subject}?",
        "criteria": {
            "present": {"what": "The target is visible, whole or mostly whole."},
            "absent": {"what": "The target is not visible.", "not_for": "A similar but different object."},
        },
    }


def _present(answers: dict[str, Any], key: str) -> float:
    """Probability that the target is present, from a Noul or a present/absent Choice answer."""
    a = answers.get(key)
    if not isinstance(a, dict):
        raise JevBoxError(f"no answer for {key}")
    if "noul" in a:
        return _noul(answers, key)
    probs = a.get("probabilities")
    if isinstance(probs, dict) and isinstance(probs.get("present"), (int, float)):
        return float(probs["present"])
    return 1.0 if a.get("choice") == "present" else 0.0


def _edge_questions(target: str, subject: str) -> dict[str, Any]:
    return {
        f"edge_{side}": {
            "type": "noul",
            "instructions": (
                f"Does {target} continue past the {side} edge of {subject}, so the {side} edge cuts part of it off?"
            ),
        }
        for side in ("top", "bottom", "left", "right")
    }


def _legend(image: bool = False, reference: bool = False, **named: str) -> dict[str, str]:
    """One line per picture saying what it shows, so Jev does not guess."""
    out = dict(named)
    if image:
        out["image"] = "the full picture to search"
    if reference:
        out["reference"] = "a separate picture of the target, in the instructions, to match against"
    return out


def _escalation(
    status: str,
    present: float,
    presence_min: float,
    count: str | None,
    confidence: float | None,
    confidence_min: float,
    verified: bool | None,
    notes: list[str],
) -> list[str]:
    """Why a caller should not trust this result alone. Empty means Jev was decisive."""
    reasons: list[str] = []
    if INDECISIVE_PRESENCE <= present < presence_min:
        reasons.append(f"presence {present:.2f} is indecisive")
    if count == "none" and present >= presence_min:
        reasons.append("presence and count disagree")
    if status == "several":
        reasons.append("several instances and no tile_grid")
    if status == "low_confidence":
        reasons.append(f"box confidence {confidence:.2f} under {confidence_min}")
    if verified is False:
        reasons.append("edge check still moving an edge after the last round")
    reasons.extend(n for n in notes if "did not show the target" in n)
    return reasons


def _sent_px(box: Box, width: int, height: int) -> float:
    """The box's longer side in pixels as Jev sees it (the image shrinks to fit 1568 px)."""
    scale = min(1.0, jev_images.MAX_SIDE / max(width, height))
    return max(box.width * width, box.height * height) * scale


def _check_aspect(width: int, height: int) -> None:
    if max(width, height) / min(width, height) > MAX_ASPECT:
        raise JevBoxError(f"image is {width}x{height}; aspect over {MAX_ASPECT}:1 shifts box fractions. Tile it first")


def locate(
    image: Any,
    target: str,
    *,
    reference: Any = None,
    timeout: float = 90,
    presence_min: float = PRESENCE_MIN,
    confidence_min: float = CONFIDENCE_MIN,
    refine: bool = True,
    edge_check: bool = True,
    max_rounds: int = 2,
    tile_grid: tuple[int, int] | None = None,
    presence: str = "choice",
    count_max: int | None = None,
    context: dict[str, Any] | None = None,
) -> LocateResult:
    """Find ``target`` in ``image`` and return its box as fractions of the ORIGINAL image.

    ``image`` is a path, bytes, or Pillow image; ``reference`` (same types) is a second picture to
    match against. Name one target per call, in words that single out one instance.

    Rounds (requests batch independent questions):
        1. One request: Box + presence Choice + count Choice (none/one/several).
        2. ``present < presence_min`` or count ``none`` -> status ``absent``, no box.
           ``several`` without ``tile_grid`` -> status ``several``: the caller decides.
        3. Tile search (``tile_grid=(rows, cols)``): on ``several``, or when a refine fails, a Choice
           over tile pictures picks a region and a Box runs on that tile.
        4. ``confidence < confidence_min`` and ``refine`` -> re-ask on a padded crop of the original.
        5. ``edge_check`` -> up to ``max_rounds`` requests of four edge Nouls on a crop of the box;
           each yes-edge moves outward and the check repeats. ``edge_verified`` says whether the last
           check came back clean.

    ``presence`` is ``"choice"`` (present/absent; default) or ``"noul"``. ``count_max=N`` swaps the
    none/one/several Choice for exact options "0".."N" and "N+1+"; the result gets ``count_exact``.
    ``context`` is structured JSON (DOM facts, app data, measured numbers) sent beside every picture.
    Box and Choice answers are model reads: when the app can answer (DOM, preview state), trust it over them.

    Raises JevBoxError for a malformed answer and JevTransportError/JevImageError from the transport.
    """
    if presence not in PRESENCE_MODES:
        raise JevBoxError(f"presence must be one of {PRESENCE_MODES}")
    source = jev_images.open_image(image)
    width, height = source.size
    _check_aspect(width, height)
    ref_img = JevImage(reference) if reference is not None else None
    run = _Run(timeout, (width, height), context)
    full = JevImage(source)
    clause = _target_clause(target, ref_img)
    subject = "the picture `image`"

    questions = {
        "box": {"type": "box", "instructions": f"{clause}, in {subject}"},
        "present": _presence_question(clause, subject, presence),
        "count": _count_question(subject, clause, count_max),
    }
    state: dict[str, Any] = {"legend": _legend(image=True, reference=ref_img is not None), "image": full}
    images = {"reference": ref_img} if ref_img else None
    answers = run.ask("locate", state, questions, images)
    box, conf = _box_answer(answers, "box")
    present = _present(answers, "present")
    count, count_exact = _normalize_count(_choice(answers, "count"), count_max)

    def result(
        status: str,
        found: Box | None,
        confidence: float | None,
        verified: bool | None = None,
        before_edge: Box | None = None,
    ) -> LocateResult:
        return LocateResult(
            status=status,
            present=present,
            count=count,
            count_exact=count_exact,
            box=found,
            pixel_box=to_pixels(found, width, height) if found else None,
            confidence=confidence,
            image_size=(width, height),
            steps=run.steps,
            notes=run.notes,
            edge_verified=verified,
            box_before_edge=before_edge,
            escalation_reasons=_escalation(
                status, present, presence_min, count, confidence, confidence_min, verified, run.notes
            ),
            warnings=run.warnings,
        )

    if present < presence_min or count == "none":
        run.notes.append("absent: presence below minimum or count none")
        return result("absent", None, None)

    searched = False
    if count == "several":
        if tile_grid is None:
            run.notes.append("several instances and no tile_grid: returning the count, box is the first guess")
            return result("several", box, conf)
        found = _tile_search(run, source, target, ref_img, tile_grid, presence)
        searched = True
        if found is not None:
            box, conf = found
    elif refine and (conf < confidence_min or _sent_px(box, width, height) < SMALL_BOX_PX):
        refined = _refine(run, source, box, target, ref_img, presence)
        if refined is not None:
            box, conf = refined
        elif tile_grid is not None:
            found = _tile_search(run, source, target, ref_img, tile_grid, presence)
            searched = True
            if found is not None:
                box, conf = found
    if conf < confidence_min and tile_grid is not None and not searched and refine:
        found = _tile_search(run, source, target, ref_img, tile_grid, presence)
        if found is not None:
            box, conf = found

    verified: bool | None = None
    before_edge = box
    if edge_check:
        box, verified = _edge_check(run, source, box, target, max_rounds)
    status = "found" if conf >= confidence_min else "low_confidence"
    return result(status, box, conf, verified, before_edge)


def _refine(
    run: _Run, source: Any, box: Box, target: str, ref_img: JevImage | None, presence: str
) -> tuple[Box, float] | None:
    """Re-ask Box on a padded crop of the original. None when the crop does not show the target."""
    piece = crop(source, box, pad_frac=REFINE_PAD, min_side_px=REFINE_MIN_SIDE, upscale_to=REFINE_UPSCALE_PX)
    clause = _target_clause(target, ref_img)
    subject = "the picture `region`"
    answers = run.ask(
        "refine",
        {
            "legend": _legend(region="a crop of the original, enlarged around the likely spot"),
            "region": JevImage(piece.image),
        },
        {
            "box": {"type": "box", "instructions": f"{clause}, in {subject}"},
            "present": _presence_question(clause, subject, presence),
        },
        {"reference": ref_img} if ref_img else None,
    )
    inner, conf = _box_answer(answers, "box")
    if _present(answers, "present") < PRESENCE_MIN:
        run.notes.append("refine crop did not show the target")
        return None
    return to_parent(inner, piece.box), conf


def _tile_search(
    run: _Run, source: Any, target: str, ref_img: JevImage | None, grid: tuple[int, int], presence: str
) -> tuple[Box, float] | None:
    """Choice over tile pictures, then Box on the chosen tile. None when no tile shows the target."""
    cells = tiles(source, *grid)
    if len(cells) < 2:
        run.notes.append("tile grid collapsed to one tile")
        return None
    names = {f"tile_{c.row}_{c.col}": c for c in cells}
    images: dict[str, JevImage] = {f"t_{c.row}_{c.col}": JevImage(c.image) for c in cells}
    if ref_img:
        images["reference"] = ref_img
    clause = _target_clause(target, ref_img)
    criteria = {
        name: {"what": f"The tile shown in {{img:t_{c.row}_{c.col}}} (row {c.row}, column {c.col})"}
        for name, c in names.items()
    }
    answers = run.ask(
        "tile_pick",
        {
            "legend": "Each option is one tile of a larger picture. Tiles overlap a little, so a target on a seam can show whole in one tile."
        },
        {"tile": {"type": "choice", "instructions": f"Which tile shows {clause} most clearly?", "criteria": criteria}},
        images,
    )
    pick = _choice(answers, "tile")
    chosen = names.get(pick)
    if chosen is None:
        raise JevBoxError(f"tile choice {pick!r} is not a tile")
    answers = run.ask(
        "tile_box",
        {"legend": _legend(region="one tile of the original"), "region": images[f"t_{chosen.row}_{chosen.col}"]},
        {
            "box": {"type": "box", "instructions": f"{clause}, in the picture `region`"},
            "present": _presence_question(clause, "the picture `region`", presence),
        },
        {"reference": ref_img} if ref_img else None,
    )
    inner, conf = _box_answer(answers, "box")
    if _present(answers, "present") < PRESENCE_MIN:
        run.notes.append(f"tile {pick} did not show the target")
        return None
    return to_parent(inner, chosen.box), conf


def _edge_check(run: _Run, source: Any, box: Box, target: str, max_rounds: int) -> tuple[Box, bool | None]:
    """Ask four edge Nouls on a tight crop; grow each yes-edge; repeat. Returns the box and whether the last check was clean."""
    verified: bool | None = None
    for _ in range(max(1, max_rounds)):
        piece = crop(source, pad(box, EDGE_PAD), min_side_px=1, max_aspect=None)
        w, h = piece.image.size
        if max(w, h) / max(1, min(w, h)) > MAX_ASPECT:
            run.notes.append("edge check skipped: box is too elongated to crop without padding")
            return box, None
        answers = run.ask(
            "edge_check",
            {
                "legend": _legend(crop="a tight crop around a candidate box, with a small margin"),
                "crop": JevImage(piece.image),
            },
            _edge_questions(target, "the picture `crop`"),
        )
        yes = {s for s in ("top", "bottom", "left", "right") if _noul(answers, f"edge_{s}") > EDGE_YES}
        # A cut by the image's own border cannot move outward.
        movable = {
            s
            for s in yes
            if (s == "top" and box.top > 0)
            or (s == "bottom" and box.bottom < 1)
            or (s == "left" and box.left > 0)
            or (s == "right" and box.right < 1)
        }
        if not movable:
            return box, True
        dx, dy = box.width * EDGE_STEP, box.height * EDGE_STEP
        box = Box(
            top=max(0.0, box.top - dy) if "top" in movable else box.top,
            bottom=min(1.0, box.bottom + dy) if "bottom" in movable else box.bottom,
            left=max(0.0, box.left - dx) if "left" in movable else box.left,
            right=min(1.0, box.right + dx) if "right" in movable else box.right,
        )
        verified = False
    return box, verified


__all__ = [
    "Box",
    "Crop",
    "JevBoxError",
    "JevImageError",
    "LocateResult",
    "Step",
    "Tile",
    "center",
    "crop",
    "iou",
    "locate",
    "pad",
    "tiles",
    "to_parent",
    "to_pixels",
]
