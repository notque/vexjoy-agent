"""Box locate: geometry, tiling, and the orchestrator against a scripted fake transport."""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

pytest.importorskip("PIL")
import jev_box
import jev_images
import jev_transport
from jev_box import Box, JevBoxError
from PIL import Image

# --- geometry ----------------------------------------------------------------------------------


def test_box_rejects_bad_edges() -> None:
    with pytest.raises(JevBoxError):
        Box(top=0.5, bottom=0.4, left=0.1, right=0.2)
    with pytest.raises(JevBoxError):
        Box(top=0.1, bottom=1.2, left=0.1, right=0.2)
    with pytest.raises(JevBoxError):
        Box.from_answer({"top": 0.1})


def test_from_answer_clamps_small_overshoot() -> None:
    box = Box.from_answer({"top": -0.01, "bottom": 1.02, "left": 0.2, "right": 0.4})
    assert (box.top, box.bottom) == (0.0, 1.0)


def test_to_pixels_and_center() -> None:
    box = Box(top=0.25, bottom=0.75, left=0.1, right=0.5)
    assert jev_box.to_pixels(box, 800, 600) == (80, 150, 400, 450)
    assert jev_box.center(box, 800, 600) == (240.0, 300.0)


def test_pad_clamps_to_unit_square() -> None:
    padded = jev_box.pad(Box(top=0.0, bottom=0.5, left=0.8, right=1.0), 0.5)
    assert (padded.top, padded.right) == (0.0, 1.0)
    assert padded.bottom == pytest.approx(0.75)
    assert padded.left == pytest.approx(0.7)


def test_iou() -> None:
    a = Box(top=0, bottom=0.5, left=0, right=0.5)
    assert jev_box.iou(a, a) == pytest.approx(1.0)
    assert jev_box.iou(a, Box(top=0.5, bottom=1, left=0.5, right=1)) == 0.0
    assert jev_box.iou(a, Box(top=0, bottom=0.5, left=0.25, right=0.75)) == pytest.approx(1 / 3)


def test_crop_round_trip_maps_back_to_parent() -> None:
    src = Image.new("RGB", (3000, 2000), "white")
    target = Box(top=0.5, bottom=0.515, left=0.5, right=0.51)  # 30 px square-ish
    piece = jev_box.crop(src, target, pad_frac=0.5, min_side_px=560)
    w, h = piece.image.size
    assert min(w, h) >= 560
    # The target's position inside the crop, mapped back, returns the original box.
    inner = Box(
        top=(target.top - piece.box.top) / piece.box.height,
        bottom=(target.bottom - piece.box.top) / piece.box.height,
        left=(target.left - piece.box.left) / piece.box.width,
        right=(target.right - piece.box.left) / piece.box.width,
    )
    back = jev_box.to_parent(inner, piece.box)
    assert back.left == pytest.approx(target.left)
    assert back.bottom == pytest.approx(target.bottom)


def test_crop_slides_inside_the_image_and_caps_at_whole_image() -> None:
    src = Image.new("RGB", (400, 300), "white")
    corner = jev_box.crop(src, Box(top=0, bottom=0.02, left=0, right=0.02), min_side_px=280)
    assert corner.box.top == 0.0 and corner.box.left == 0.0
    assert corner.image.size[0] >= 280
    whole = jev_box.crop(src, Box(top=0.1, bottom=0.2, left=0.1, right=0.2), min_side_px=900)
    assert whole.image.size == (400, 300)


def test_crop_limits_aspect_unless_told_not_to() -> None:
    src = Image.new("RGB", (3000, 2000), "white")
    thin = Box(top=0.5, bottom=0.51, left=0.1, right=0.9)  # 2400 x 20 px
    wide = jev_box.crop(src, thin, min_side_px=1)
    assert wide.image.size[0] / wide.image.size[1] <= jev_box.MAX_ASPECT + 0.01
    tight = jev_box.crop(src, thin, min_side_px=1, max_aspect=None)
    assert tight.image.size[1] == 20


def test_crops_meet_image_limits_after_prepare() -> None:
    src = Image.new("RGB", (3000, 2000), "white")
    piece = jev_box.crop(src, Box(top=0.5, bottom=0.505, left=0.5, right=0.505), pad_frac=0.2)
    prepared = jev_images.JevImage(piece.image).resolve()
    assert prepared.width >= 280 and prepared.height >= 280


def test_tiny_crop_without_min_is_upscaled_by_prepare() -> None:
    src = Image.new("RGB", (3000, 2000), "white")
    piece = jev_box.crop(src, Box(top=0.5, bottom=0.51, left=0.5, right=0.505), min_side_px=1, max_aspect=None)
    assert min(piece.image.size) < 280
    prepared = jev_images.JevImage(piece.image).resolve()
    assert min(prepared.width, prepared.height) >= 280


def test_tiles_cover_image_and_respect_minimum() -> None:
    src = Image.new("RGB", (3000, 2000), "white")
    cells = jev_box.tiles(src, 3, 3, overlap=0.1)
    assert len(cells) == 9
    assert min(min(c.image.size) for c in cells) >= 280
    assert cells[0].box.left == 0.0 and cells[0].box.top == 0.0
    assert cells[-1].box.right == pytest.approx(1.0, abs=1e-3) and cells[-1].box.bottom == pytest.approx(1.0, abs=1e-3)
    row0 = [c for c in cells if c.row == 0]
    assert row0[0].box.right > row0[1].box.left  # neighbors overlap


def test_tiles_merge_when_too_small() -> None:
    src = Image.new("RGB", (600, 900), "white")
    cells = jev_box.tiles(src, 4, 4, overlap=0.0)
    assert min(min(c.image.size) for c in cells) >= 280
    assert len(cells) < 16
    tiny = Image.new("RGB", (200, 150), "white")
    assert len(jev_box.tiles(tiny, 3, 3)) == 1


def test_tile_box_maps_to_full_image() -> None:
    src = Image.new("RGB", (3000, 2000), "white")
    cell = next(c for c in jev_box.tiles(src, 2, 2, overlap=0.1) if (c.row, c.col) == (1, 1))
    inner = Box(top=0.5, bottom=0.6, left=0.5, right=0.6)
    full = jev_box.to_parent(inner, cell.box)
    assert full.left == pytest.approx(cell.box.left + 0.5 * cell.box.width)
    assert 0.5 < full.left < 1 and 0.5 < full.top < 1


def test_tiles_bad_args() -> None:
    with pytest.raises(JevBoxError):
        jev_box.tiles(Image.new("RGB", (400, 400)), 0, 2)
    with pytest.raises(JevBoxError):
        jev_box.tiles(Image.new("RGB", (400, 400)), 2, 2, overlap=0.6)


# --- orchestrator with a scripted transport ------------------------------------------------------

BOX_DICT = {"top": 0.4, "bottom": 0.6, "left": 0.4, "right": 0.6}


def _box_ans(conf: float = 0.9, **edges: float) -> dict[str, Any]:
    return {"type": "box", "box": {**BOX_DICT, **edges}, "confidence": conf}


def _noul_ans(p: float) -> dict[str, Any]:
    return {"type": "noul", "noul": p}


def _choice_ans(name: str) -> dict[str, Any]:
    return {"type": "choice", "choice": name, "probabilities": {name: 1.0}, "confidence": 1.0}


class Fake:
    """Replaces jev_transport.evaluate. ``script`` gets (call_index, name, questions) and returns answers."""

    def __init__(self, script: Callable[[int, str, dict[str, Any]], dict[str, Any]]) -> None:
        self.script = script
        self.calls: list[dict[str, Any]] = []

    def __call__(self, state: Any, questions: dict[str, Any], *, timeout: float, images: Any = None) -> dict[str, Any]:
        bound = jev_images.bind_images(state, questions, images)  # real binding: placeholders must resolve
        name = "edge_check" if "edge_top" in questions else "tile_pick" if "tile" in questions else None
        if name is None:
            name = "locate" if "count" in questions else "region"
        self.calls.append({"name": name, "questions": questions, "bound": bound, "state": state, "images": images})
        answers = self.script(len(self.calls) - 1, name, questions)
        return {"answers": answers, "usage": {"input_tokens": 100, "output_tokens": 5}}


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> Callable[[Callable[..., dict[str, Any]]], Fake]:
    def install(script: Callable[[int, str, dict[str, Any]], dict[str, Any]]) -> Fake:
        f = Fake(script)
        monkeypatch.setattr(jev_transport, "evaluate", f)
        return f

    return install


@pytest.fixture
def photo(tmp_path: Path) -> Path:
    path = tmp_path / "big.png"
    Image.new("RGB", (3000, 2000), "white").save(path)
    return path


def always(answers: dict[str, Any]) -> Callable[..., dict[str, Any]]:
    """A script that returns the same answers for every request."""
    return lambda *_args: answers


def _clean_edges() -> dict[str, Any]:
    return {f"edge_{s}": _noul_ans(0.05) for s in ("top", "bottom", "left", "right")}


def _happy(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
    if name == "locate":
        return {"box": _box_ans(0.9), "present": _noul_ans(0.95), "count": _choice_ans("one")}
    return _clean_edges()


def test_happy_path_is_two_requests_and_sums_tokens(fake: Any, photo: Path) -> None:
    f = fake(_happy)
    res = jev_box.locate(photo, "the red square")
    assert [c["name"] for c in f.calls] == ["locate", "edge_check"]
    assert res.status == "found" and res.edge_verified is True
    assert res.box == Box(**BOX_DICT)
    assert res.pixel_box == (1200, 800, 1800, 1200)
    assert res.requests == 2 and res.input_tokens == 200
    assert res.center == (1500.0, 1000.0)
    # Round 1 batches the three questions into one request.
    assert sorted(f.calls[0]["questions"]) == ["box", "count", "present"]
    assert f.calls[0]["questions"]["box"]["type"] == "box"


def test_absent_path_stops_after_one_request(fake: Any, photo: Path) -> None:
    f = fake(always({"box": _box_ans(0.9), "present": _noul_ans(0.1), "count": _choice_ans("none")}))
    res = jev_box.locate(photo, "a blue star")
    assert res.status == "absent" and res.box is None and res.pixel_box is None
    assert len(f.calls) == 1


def test_count_none_alone_means_absent(fake: Any, photo: Path) -> None:
    fake(always({"box": _box_ans(), "present": _noul_ans(0.9), "count": _choice_ans("none")}))
    assert jev_box.locate(photo, "x").status == "absent"


def test_several_without_tiles_returns_count_for_caller(fake: Any, photo: Path) -> None:
    f = fake(always({"box": _box_ans(0.9), "present": _noul_ans(0.9), "count": _choice_ans("several")}))
    res = jev_box.locate(photo, "the red square")
    assert res.status == "several" and res.count == "several"
    assert len(f.calls) == 1


def test_low_confidence_refines_from_the_original_and_maps_back(fake: Any, photo: Path) -> None:
    def script(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {"box": _box_ans(0.2), "present": _noul_ans(0.9), "count": _choice_ans("one")}
        if name == "region":
            return {"box": _box_ans(0.95, top=0.45, bottom=0.55, left=0.45, right=0.55), "present": _noul_ans(0.95)}
        return _clean_edges()

    f = fake(script)
    res = jev_box.locate(photo, "tiny thing")
    assert [c["name"] for c in f.calls] == ["locate", "region", "edge_check"]
    region_img = next(v for v in f.calls[1]["bound"].assets.values())
    assert min(region_img.width, region_img.height) >= 280
    # 560 px of a 3000 px source, native resolution: the refine crop is smaller than the shrunk full image.
    assert max(region_img.width, region_img.height) < 1568
    assert res.confidence == pytest.approx(0.95)
    assert res.box is not None and res.box.width < Box(**BOX_DICT).width  # refined box is tighter


def test_refine_off_keeps_first_box_and_flags_low_confidence(fake: Any, photo: Path) -> None:
    f = fake(always({"box": _box_ans(0.2), "present": _noul_ans(0.9), "count": _choice_ans("one")}))
    res = jev_box.locate(photo, "x", refine=False, edge_check=False)
    assert res.status == "low_confidence" and len(f.calls) == 1


def test_edge_check_expands_yes_edges_then_stops_when_clean(fake: Any, photo: Path) -> None:
    def script(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {"box": _box_ans(0.9), "present": _noul_ans(0.9), "count": _choice_ans("one")}
        edges = _clean_edges()
        if call == 1:
            edges["edge_left"] = _noul_ans(0.9)
        return edges

    f = fake(script)
    res = jev_box.locate(photo, "x", max_rounds=3)
    assert [c["name"] for c in f.calls] == ["locate", "edge_check", "edge_check"]
    assert res.edge_verified is True
    assert res.box is not None
    assert res.box.left < 0.4 and res.box.right == 0.6 and res.box.top == 0.4  # only the yes-edge moved


def test_edge_check_loop_terminates_at_max_rounds(fake: Any, photo: Path) -> None:
    def script(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {"box": _box_ans(0.9), "present": _noul_ans(0.9), "count": _choice_ans("one")}
        return {k: _noul_ans(0.99) for k in q}

    f = fake(script)
    res = jev_box.locate(photo, "x", max_rounds=2)
    assert [c["name"] for c in f.calls].count("edge_check") == 2
    assert res.edge_verified is False
    assert res.box is not None and res.box.width > 0.2


def test_edge_yes_on_image_border_does_not_loop(fake: Any, photo: Path) -> None:
    def script(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {
                "box": _box_ans(0.9, left=0.0, right=0.3),
                "present": _noul_ans(0.9),
                "count": _choice_ans("one"),
            }
        return {**_clean_edges(), "edge_left": _noul_ans(0.99)}

    f = fake(script)
    res = jev_box.locate(photo, "x", max_rounds=5)
    assert len(f.calls) == 2 and res.edge_verified is True


def test_several_with_tile_grid_picks_tile_and_maps_back(fake: Any, photo: Path) -> None:
    def script(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {"box": _box_ans(0.9), "present": _noul_ans(0.9), "count": _choice_ans("several")}
        if name == "tile_pick":
            return {"tile": _choice_ans("tile_1_1")}
        if name == "region":
            return {"box": _box_ans(0.9, top=0.4, bottom=0.6, left=0.4, right=0.6), "present": _noul_ans(0.9)}
        return _clean_edges()

    f = fake(script)
    res = jev_box.locate(photo, "the red square", tile_grid=(2, 2))
    assert [c["name"] for c in f.calls] == ["locate", "tile_pick", "region", "edge_check"]
    assert res.count == "several" and res.status == "found"
    assert res.box is not None and res.box.left > 0.5 and res.box.top > 0.5  # bottom-right tile
    pick = f.calls[1]
    assert sorted(pick["questions"]["tile"]["criteria"]) == ["tile_0_0", "tile_0_1", "tile_1_0", "tile_1_1"]
    assert len(pick["bound"].assets) == 4  # one picture per option


def test_failed_refine_falls_back_to_tiles(fake: Any, photo: Path) -> None:
    def script(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {"box": _box_ans(0.1), "present": _noul_ans(0.9), "count": _choice_ans("one")}
        if name == "tile_pick":
            return {"tile": _choice_ans("tile_0_1")}
        if name == "region":
            seen = sum(1 for c in fake_calls if c["name"] == "region")
            return {"box": _box_ans(0.9), "present": _noul_ans(0.1 if seen == 1 else 0.9)}
        return _clean_edges()

    f = fake(script)
    fake_calls = f.calls
    res = jev_box.locate(photo, "small thing", tile_grid=(3, 3), edge_check=False)
    assert [c["name"] for c in f.calls] == ["locate", "region", "tile_pick", "region"]
    assert res.status == "found" and res.confidence == pytest.approx(0.9)


def test_reference_image_is_placed_in_the_instructions(fake: Any, photo: Path, tmp_path: Path) -> None:
    ref = tmp_path / "ref.png"
    Image.new("RGB", (300, 300), "blue").save(ref)
    f = fake(_happy)
    jev_box.locate(photo, "the shape", reference=ref, edge_check=False)
    first = f.calls[0]
    assert "{img:reference}" in first["questions"]["box"]["instructions"]
    assert "{img:reference}" in first["questions"]["present"]["instructions"]
    bound = first["bound"]
    assert len(bound.assets) == 2  # the picture and the reference
    ref_id = next(r for r, a in bound.assets.items() if (a.width, a.height) == (300, 300))
    assert ref_id in bound.questions["box"]["instructions"]
    assert ref_id not in json.dumps(bound.state)  # reference lives in the instructions, not the state


def test_no_reference_means_one_image_only(fake: Any, photo: Path) -> None:
    f = fake(_happy)
    jev_box.locate(photo, "x", edge_check=False)
    assert len(f.calls[0]["bound"].assets) == 1


def test_extreme_aspect_is_refused(photo: Path, tmp_path: Path) -> None:
    path = tmp_path / "strip.png"
    Image.new("RGB", (3000, 100), "white").save(path)
    with pytest.raises(JevBoxError):
        jev_box.locate(path, "x")


def test_malformed_answer_raises(fake: Any, photo: Path) -> None:
    fake(always({"box": {"type": "box", "box": {"top": 0.1}, "confidence": 0.9}}))
    with pytest.raises(JevBoxError):
        jev_box.locate(photo, "x")


def test_missing_usage_adds_zero_tokens(monkeypatch: pytest.MonkeyPatch, photo: Path) -> None:
    def no_usage(state: Any, questions: dict[str, Any], *, timeout: float, images: Any = None) -> dict[str, Any]:
        return {"answers": _happy(0, "locate", questions)}

    monkeypatch.setattr(jev_transport, "evaluate", no_usage)
    res = jev_box.locate(photo, "x", edge_check=False)
    assert res.input_tokens == 0 and res.requests == 1


# --- presence mode, exact count, legend ----------------------------------------------------------


def _present_choice(p: float) -> dict[str, Any]:
    return {
        "type": "choice",
        "choice": "present" if p >= 0.5 else "absent",
        "probabilities": {"present": p, "absent": 1 - p},
    }


def test_presence_defaults_to_a_present_absent_choice(fake: Any, photo: Path) -> None:
    f = fake(always({"box": _box_ans(0.9), "present": _present_choice(0.95), "count": _choice_ans("one")}))
    res = jev_box.locate(photo, "x", edge_check=False)
    q = f.calls[0]["questions"]["present"]
    assert q["type"] == "choice" and sorted(q["criteria"]) == ["absent", "present"]
    assert res.present == pytest.approx(0.95) and res.status == "found"


def test_presence_choice_low_means_absent(fake: Any, photo: Path) -> None:
    fake(always({"box": _box_ans(0.9), "present": _present_choice(0.1), "count": _choice_ans("one")}))
    assert jev_box.locate(photo, "x").status == "absent"


def test_presence_noul_option(fake: Any, photo: Path) -> None:
    f = fake(_happy)
    jev_box.locate(photo, "x", presence="noul", edge_check=False)
    assert f.calls[0]["questions"]["present"]["type"] == "noul"
    with pytest.raises(JevBoxError):
        jev_box.locate(photo, "x", presence="maybe")


def test_exact_count_options_and_result(fake: Any, photo: Path) -> None:
    f = fake(always({"box": _box_ans(0.9), "present": _noul_ans(0.9), "count": _choice_ans("3")}))
    res = jev_box.locate(photo, "x", count_max=4, edge_check=False)
    assert sorted(f.calls[0]["questions"]["count"]["criteria"]) == ["0", "1", "2", "3", "4", "5+"]
    assert (res.count, res.count_exact, res.status) == ("several", 3, "several")


@pytest.mark.parametrize(
    ("choice", "expect"),
    [("0", ("none", 0)), ("1", ("one", 1)), ("5+", ("several", None))],
)
def test_normalize_count(choice: str, expect: tuple[str, int | None]) -> None:
    assert jev_box._normalize_count(choice, 4) == expect
    with pytest.raises(JevBoxError):
        jev_box._normalize_count("many", 4)


def test_state_carries_a_legend_for_each_picture(fake: Any, photo: Path, tmp_path: Path) -> None:
    ref = tmp_path / "ref.png"
    Image.new("RGB", (300, 300), "blue").save(ref)
    f = fake(_happy)
    jev_box.locate(photo, "x", reference=ref, edge_check=True)
    first, edge = f.calls
    assert set(first["state"]["legend"]) == {"image", "reference"}
    assert "crop" in edge["state"]["legend"]


# --- context, resolution, escalation ---------------------------------------------------------------


def test_context_rides_beside_every_picture_except_edge_checks(fake: Any, photo: Path) -> None:
    f = fake(_happy)
    jev_box.locate(photo, "x", context={"dom": {"buttons": 3}})
    first, edge = f.calls
    assert first["state"]["context"] == {"dom": {"buttons": 3}}
    assert "context" not in edge["state"]


def test_refine_crop_is_enlarged_toward_1080(fake: Any, photo: Path) -> None:
    def script(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {"box": _box_ans(0.2), "present": _noul_ans(0.9), "count": _choice_ans("one")}
        return {"box": _box_ans(0.95), "present": _noul_ans(0.95)}

    f = fake(script)
    jev_box.locate(photo, "x", edge_check=False)
    region = next(iter(f.calls[1]["bound"].assets.values()))
    assert max(region.width, region.height) >= 1000  # a 560 px source crop, enlarged


def test_crop_upscale_keeps_fractions_and_caps_at_1568() -> None:
    src = Image.new("RGB", (3000, 2000), "white")
    box = Box(top=0.5, bottom=0.51, left=0.5, right=0.51)
    plain = jev_box.crop(src, box, min_side_px=400)
    big = jev_box.crop(src, box, min_side_px=400, upscale_to=5000)
    assert big.box == plain.box
    assert max(big.image.size) == 1568


def test_low_resolution_picture_adds_a_warning(fake: Any, tmp_path: Path) -> None:
    small = tmp_path / "small.png"
    Image.new("RGB", (800, 600), "white").save(small)
    fake(_happy)
    res = jev_box.locate(small, "x", edge_check=False)
    assert res.warnings and "800x600" in res.warnings[0]


def test_big_picture_has_no_warning(fake: Any, photo: Path) -> None:
    fake(_happy)
    assert jev_box.locate(photo, "x").warnings == []


def test_decisive_result_does_not_need_escalation(fake: Any, photo: Path) -> None:
    fake(_happy)
    res = jev_box.locate(photo, "x")
    assert res.needs_escalation is False and res.escalation_reasons == []


def test_escalation_reasons(fake: Any, photo: Path) -> None:
    fake(always({"box": _box_ans(0.9), "present": _noul_ans(0.9), "count": _choice_ans("several")}))
    assert jev_box.locate(photo, "x").needs_escalation  # several, no tile_grid
    fake(always({"box": _box_ans(0.9), "present": _noul_ans(0.5), "count": _choice_ans("one")}))
    res = jev_box.locate(photo, "x")
    assert res.status == "absent" and res.needs_escalation  # indecisive presence
    fake(always({"box": _box_ans(0.2), "present": _noul_ans(0.9), "count": _choice_ans("one")}))
    res = jev_box.locate(photo, "x", refine=False, edge_check=False)
    assert res.status == "low_confidence" and "confidence" in res.escalation_reasons[0]
    fake(always({"box": _box_ans(0.9), "present": _noul_ans(0.0), "count": _choice_ans("none")}))
    assert jev_box.locate(photo, "x").needs_escalation is False  # a clear absent is an answer


def test_missed_refine_and_endless_edges_escalate(fake: Any, photo: Path) -> None:
    def script(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {"box": _box_ans(0.2), "present": _noul_ans(0.9), "count": _choice_ans("one")}
        return {"box": _box_ans(0.9), "present": _noul_ans(0.1)}

    fake(script)
    res = jev_box.locate(photo, "x", edge_check=False)
    assert any("did not show" in r for r in res.escalation_reasons)

    def edges(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {"box": _box_ans(0.9), "present": _noul_ans(0.9), "count": _choice_ans("one")}
        return {k: _noul_ans(0.99) for k in q}

    fake(edges)
    assert any("edge check" in r for r in jev_box.locate(photo, "x", max_rounds=1).escalation_reasons)


def test_small_first_box_is_refined_even_when_confident(fake: Any, photo: Path) -> None:
    tiny = {"top": 0.5, "bottom": 0.51, "left": 0.5, "right": 0.51}  # 30 px in 3000, ~16 px as sent

    def script(call: int, name: str, q: dict[str, Any]) -> dict[str, Any]:
        if name == "locate":
            return {"box": _box_ans(0.95, **tiny), "present": _noul_ans(0.9), "count": _choice_ans("one")}
        return {"box": _box_ans(0.95), "present": _noul_ans(0.95)}

    f = fake(script)
    jev_box.locate(photo, "x", edge_check=False)
    assert [c["name"] for c in f.calls] == ["locate", "region"]


def test_jpeg_quality_is_95() -> None:
    assert jev_images.JPEG_QUALITY == 95
