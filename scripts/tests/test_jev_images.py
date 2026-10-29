"""Image support for Jev: preparation, reference binding, multipart wire shape, routing, splitting."""

from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

PIL = pytest.importorskip("PIL")
import jev_images
import jev_limits
import jev_router_common
import jev_transport
from jev_images import JevImage, JevImageError
from PIL import Image


def _png(path: Path, size: tuple[int, int], color: Any = (200, 30, 30), mode: str = "RGB") -> Path:
    Image.new(mode, size, color).save(path, "PNG")
    return path


def _decode(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data))


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("JEV_TRANSPORT", "AI_GATEWAY_API_KEY", "TYPESAFE_API_KEY"):
        monkeypatch.delenv(name, raising=False)


# --- preparation -------------------------------------------------------------------------------


def test_large_image_shrinks_to_fit_and_becomes_baseline_jpeg(tmp_path: Path) -> None:
    prepared = jev_images.prepare_image(_png(tmp_path / "big.png", (3000, 2000)))
    assert prepared.fmt == "jpg"
    assert (prepared.width, prepared.height) == (1568, 1045)
    im = _decode(prepared.data)
    assert im.format == "JPEG"
    assert not im.info.get("progressive")
    assert im.size == (prepared.width, prepared.height)


def test_small_image_upscales_to_min_side(tmp_path: Path) -> None:
    prepared = jev_images.prepare_image(_png(tmp_path / "small.png", (100, 200)))
    assert (prepared.width, prepared.height) == (280, 560)


def test_extreme_aspect_ratio_is_padded_not_distorted(tmp_path: Path) -> None:
    prepared = jev_images.prepare_image(_png(tmp_path / "wide.png", (3000, 40)))
    assert prepared.width == 1568
    assert prepared.height == 280


def test_transparency_keeps_png(tmp_path: Path) -> None:
    path = tmp_path / "alpha.png"
    Image.new("RGBA", (400, 400), (255, 0, 0, 60)).save(path)
    prepared = jev_images.prepare_image(path)
    assert prepared.fmt == "png"
    assert _decode(prepared.data).mode == "RGBA"


def test_opaque_rgba_becomes_jpeg(tmp_path: Path) -> None:
    path = tmp_path / "opaque.png"
    Image.new("RGBA", (400, 400), (255, 0, 0, 255)).save(path)
    assert jev_images.prepare_image(path).fmt == "jpg"


def test_exif_rotation_is_applied(tmp_path: Path) -> None:
    path = tmp_path / "rot.jpg"
    im = Image.new("RGB", (600, 300), (10, 120, 10))
    exif = Image.Exif()
    exif[0x0112] = 6  # rotate 90 degrees clockwise to display
    im.save(path, "JPEG", exif=exif)
    prepared = jev_images.prepare_image(path)
    assert (prepared.width, prepared.height) == (300, 600)


@pytest.mark.parametrize("size", [(280, 280), (1568, 1568), (500, 1568), (1568, 280)])
def test_prepared_images_always_meet_every_limit(tmp_path: Path, size: tuple[int, int]) -> None:
    prepared = jev_images.prepare_image(_png(tmp_path / "x.png", size))
    assert jev_images.MIN_PIXELS <= prepared.width * prepared.height <= jev_images.MAX_PIXELS
    assert len(prepared.data) <= jev_images.MAX_FILE_BYTES


def test_undecodable_and_missing_sources_raise_clear_errors(tmp_path: Path) -> None:
    with pytest.raises(JevImageError, match="cannot decode"):
        jev_images.prepare_image(b"not an image")
    with pytest.raises(JevImageError, match="cannot read"):
        jev_images.prepare_image(tmp_path / "missing.png")


def test_prepare_false_validates_and_never_resizes(tmp_path: Path) -> None:
    good = _png(tmp_path / "ok.png", (400, 300))
    prepared = JevImage(good, prepare=False).resolve()
    assert prepared.data == good.read_bytes()
    assert prepared.fmt == "png"
    with pytest.raises(JevImageError, match="each side"):
        JevImage(_png(tmp_path / "tiny.png", (100, 100)), prepare=False).resolve()
    gif = tmp_path / "a.gif"
    Image.new("RGB", (400, 400)).save(gif, "GIF")
    with pytest.raises(JevImageError, match="PNG and JPEG"):
        JevImage(gif, prepare=False).resolve()


# --- reference binding -------------------------------------------------------------------------


def test_objects_in_place_become_refs_and_dedupe(tmp_path: Path) -> None:
    a = JevImage(_png(tmp_path / "a.png", (400, 400)))
    b = JevImage(_png(tmp_path / "b.png", (400, 400), (0, 0, 255)))
    state = {"shot": a, "again": a, "ref": [b]}
    questions = {"q": {"type": "noul", "instructions": "Is there a red circle?", "criteria": {"true": a}}}
    bound = jev_images.bind_images(state, questions)
    assert len(bound.assets) == 2
    assert bound.state["shot"] == bound.state["again"]
    assert bound.questions["q"]["criteria"]["true"] == bound.state["shot"]
    assert all(re.fullmatch(r"[0-9a-f]{32}", ref) for ref in bound.assets)
    assert not any(isinstance(v, JevImage) for v in json.loads(json.dumps(bound.state)).values())


def test_refs_are_fresh_per_request(tmp_path: Path) -> None:
    a = JevImage(_png(tmp_path / "a.png", (400, 400)))
    first = jev_images.bind_images({"s": a}, {})
    second = jev_images.bind_images({"s": a}, {})
    assert set(first.assets).isdisjoint(second.assets)


def test_named_placeholders_replace_mid_sentence(tmp_path: Path) -> None:
    shot = JevImage(_png(tmp_path / "a.png", (400, 400)))
    bound = jev_images.bind_images(
        {"note": "see {img:shot} now"},
        {"q": {"type": "noul", "instructions": "Is there a red circle in {img:shot}?"}},
        {"shot": shot},
    )
    (ref,) = bound.assets
    assert bound.state["note"] == f"see {ref} now"
    assert ref in bound.questions["q"]["instructions"]


def test_unknown_or_unused_named_image_is_refused(tmp_path: Path) -> None:
    shot = JevImage(_png(tmp_path / "a.png", (400, 400)))
    with pytest.raises(JevImageError, match="no image"):
        jev_images.bind_images({"n": "{img:nope}"}, {}, {"shot": shot})
    with pytest.raises(JevImageError, match="never referenced"):
        jev_images.bind_images({"n": "text"}, {}, {"shot": shot})


def test_placeholder_text_is_left_alone_without_images() -> None:
    assert jev_images.contains_images({"n": "{img:x}"}, {}) is False


def test_unreferenced_asset_guard(tmp_path: Path) -> None:
    prepared = JevImage(_png(tmp_path / "a.png", (400, 400))).resolve()
    with pytest.raises(JevImageError, match="never referenced"):
        jev_images.check_assets({"f" * 32: prepared}, {"s": "text"}, {})


def test_expansion_counts_every_use_of_a_reference(tmp_path: Path) -> None:
    prepared = JevImage(_png(tmp_path / "a.png", (400, 400))).resolve()
    ref = "a" * 32
    big = jev_images.PreparedImage(b"x" * (9 * 1024 * 1024), "jpg", 400, 400)
    jev_images.check_assets({ref: big}, {"s": ref}, {})
    with pytest.raises(JevImageError, match="expanded"):
        jev_images.check_assets({ref: big}, {"s": [ref, ref, ref]}, {})
    assert prepared.width == 400


def test_oversized_file_is_refused() -> None:
    huge = jev_images.PreparedImage(b"x" * (jev_images.MAX_FILE_BYTES + 1), "jpg", 400, 400)
    with pytest.raises(JevImageError, match="limit"):
        jev_images.check_assets({"a" * 32: huge}, {"s": "a" * 32}, {})


def test_part_name_request_is_reserved() -> None:
    with pytest.raises(JevImageError, match="reserved"):
        jev_images.encode_multipart({}, {"request": (b"x", "image/png")})


def test_references_survive_redaction(tmp_path: Path) -> None:
    import jev_redact

    a = JevImage(_png(tmp_path / "a.png", (400, 400)))
    bound = jev_images.bind_images(
        {"screenshot": a, "note": "see " + "{img:s}"}, {"q": {"instructions": "x"}}, {"s": a}
    )
    redacted, count = jev_redact.redact_payload({"state": bound.state, "questions": bound.questions})
    assert count == 0
    assert redacted["state"] == bound.state


# --- token estimate ----------------------------------------------------------------------------


def test_token_estimate_adds_constant_and_ignores_bytes(tmp_path: Path) -> None:
    img = JevImage(_png(tmp_path / "a.png", (1000, 800)))
    bound = jev_images.bind_images({"shot": img}, {})
    tokens = jev_images.image_token_map(bound.assets)
    (ref,) = tokens
    assert tokens[ref] == -(-bound.assets[ref].width * bound.assets[ref].height // jev_images.IMAGE_PIXELS_PER_TOKEN)
    with_image = jev_limits.estimate_tokens(bound.state, tokens)
    text_only = jev_limits.estimate_tokens(bound.state)
    assert with_image == text_only + tokens[ref]
    # Bytes never count: the estimate is independent of file size.
    noisy = jev_images.PreparedImage(b"\x00" * 10_000_000, "jpg", bound.assets[ref].width, bound.assets[ref].height)
    assert jev_limits.estimate_tokens(bound.state, {ref: noisy.est_tokens}) == with_image


def test_text_only_estimate_unchanged() -> None:
    assert jev_limits.estimate_tokens("a" * 40) == 10
    assert (
        jev_limits.request_tokens({"a": 1}, {"q": {"type": "noul"}})["total"]
        == jev_limits.request_tokens({"a": 1}, {"q": {"type": "noul"}}, None)["total"]
    )


# --- transport ---------------------------------------------------------------------------------


class _Resp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _Resp:
        return self

    def __exit__(self, *_a: object) -> None:
        return None


def _parse_multipart(request: Any) -> list[tuple[dict[str, str], bytes]]:
    ctype = request.get_header("Content-type")
    boundary = ctype.split("boundary=")[1].encode()
    parts = []
    for chunk in request.data.split(b"--" + boundary)[1:-1]:
        head, _, body = chunk.lstrip(b"\r\n").partition(b"\r\n\r\n")
        headers = dict(line.split(": ", 1) for line in head.decode().split("\r\n"))
        parts.append((headers, body[:-2]))
    return parts


@pytest.fixture
def wire(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Direct transport with the HTTP layer mocked; returns the captured urllib requests."""
    _clear(monkeypatch)
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key-value")
    monkeypatch.setenv("JEV_CACHE_TTL_S", "0")
    seen: list[Any] = []

    def fake_open(request: Any, timeout: float) -> _Resp:
        seen.append(request)
        ctype = request.get_header("Content-type")
        payload = (
            json.loads(_parse_multipart(request)[0][1]) if ctype.startswith("multipart") else json.loads(request.data)
        )
        answers = {k: {"type": "noul", "noul": 0.9} for k in payload["questions"]}
        return _Resp(json.dumps({"answers": answers, "usage": {"input_tokens": 10, "output_tokens": 1}}).encode())

    monkeypatch.setattr(jev_router_common, "_open_url", fake_open)
    return seen


def test_multipart_body_shape_and_header(wire: list[Any], tmp_path: Path) -> None:
    shot = JevImage(_png(tmp_path / "a.png", (400, 400)))
    ref_img = JevImage(_png(tmp_path / "b.png", (300, 300), (0, 0, 255)))
    questions = {"q": {"type": "noul", "instructions": "Is there a red circle in {img:shot}?"}}
    result = jev_transport.evaluate({"frame": shot, "ref": ref_img}, questions, timeout=5, images={"shot": shot})
    (request,) = wire
    assert request.get_header(jev_images.IMAGES_HEADER.capitalize()) == "true"
    assert request.get_header("Authorization") == "Bearer test-key-value"
    parts = _parse_multipart(request)
    assert 'name="request"' in parts[0][0]["Content-Disposition"]
    assert parts[0][0]["Content-Type"] == "application/json"
    payload = json.loads(parts[0][1])
    assert payload["model"] == jev_router_common.JEV_MODEL
    assets = payload["assets"]
    assert len(assets) == 2
    file_parts = {re.search(r'name="([^"]+)"', h["Content-Disposition"]).group(1): (h, b) for h, b in parts[1:]}
    assert sorted(a["part"] for a in assets.values()) == sorted(file_parts)
    assert all(h["Content-Type"] in ("image/jpeg", "image/png") for h, _ in file_parts.values())
    assert all(b[:2] == b"\xff\xd8" for _, b in file_parts.values())
    # Every reference in the payload text is an asset, and the images were never sent as base64.
    text = json.dumps({"state": payload["state"], "questions": payload["questions"]})
    assert all(ref in text for ref in assets)
    assert "data_base64" not in request.data.decode("latin-1")
    meta = result["_meta"]
    assert meta["transport"] == jev_transport.DIRECT
    assert meta["images"]["count"] == 2
    assert sorted(meta["images"]["dims"]) == [[300, 300], [400, 400]]
    assert "bytes" in meta["images"]


def test_images_force_direct_even_when_vercel_is_configured(
    wire: list[Any], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gateway")
    monkeypatch.setenv("JEV_TRANSPORT", "vercel")

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("gateway must not be used for images")

    monkeypatch.setattr(jev_transport.jev_vercel, "evaluate", boom)
    shot = JevImage(_png(tmp_path / "a.png", (400, 400)))
    jev_transport.evaluate({"frame": shot}, {"q": {"type": "noul", "instructions": "ok?"}}, timeout=5)
    assert len(wire) == 1


def test_images_without_direct_key_raise_images_unsupported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gateway")
    shot = JevImage(_png(tmp_path / "a.png", (400, 400)))
    with pytest.raises(jev_transport.JevTransportError) as err:
        jev_transport.evaluate({"frame": shot}, {"q": {"type": "noul", "instructions": "ok?"}}, timeout=5)
    assert err.value.source == jev_transport.IMAGES_UNSUPPORTED


def test_box_question_sends_header_and_forces_direct(wire: list[Any], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gateway")
    jev_transport.evaluate({"s": "x"}, {"q": {"type": "box", "instructions": "where?"}}, timeout=5)
    (request,) = wire
    assert request.get_header(jev_images.IMAGES_HEADER.capitalize()) == "true"
    assert request.get_header("Content-type") == "application/json"
    assert "assets" not in json.loads(request.data)
    assert json.loads(request.data)["model"] == jev_images.BOX_MODEL


def test_requests_without_box_keep_the_default_model(wire: list[Any], tmp_path: Path) -> None:
    shot = JevImage(_png(tmp_path / "a.png", (400, 400)))
    jev_transport.evaluate({"frame": shot}, {"q": {"type": "noul", "instructions": "ok?"}}, timeout=5)
    (request,) = wire
    body = request.data.decode("latin-1")
    assert '"model": "jev-1.14.0"' in body or '"model":"jev-1.14.0"' in body


def test_bad_image_is_a_transport_error_without_sending(wire: list[Any], tmp_path: Path) -> None:
    bad = JevImage(tmp_path / "missing.png")
    with pytest.raises(jev_transport.JevTransportError) as err:
        jev_transport.evaluate({"frame": bad}, {"q": {"type": "noul", "instructions": "ok?"}}, timeout=5)
    assert err.value.source == jev_transport.INVALID_IMAGE
    assert wire == []


def test_image_request_fits_without_splitting_that_a_text_request_would_need(wire: list[Any], tmp_path: Path) -> None:
    shot = JevImage(_png(tmp_path / "a.png", (1568, 1568)))  # ~3,278 estimated tokens
    questions = {f"q{i}": {"type": "noul", "instructions": "ok? " * 50} for i in range(4)}
    jev_transport.evaluate_packed({"frame": shot}, questions, timeout=5)
    assert len(wire) == 1


def test_split_sends_each_part_only_the_assets_it_references(wire: list[Any], tmp_path: Path) -> None:
    state_img = JevImage(_png(tmp_path / "s.png", (1568, 1568)))
    only_q1 = JevImage(_png(tmp_path / "q1.png", (400, 400), (0, 255, 0)))
    only_q2 = JevImage(_png(tmp_path / "q2.png", (400, 400), (0, 0, 255)))
    filler = "z" * 60_000  # ~15k tokens: one question per request
    questions = {
        "q1": {"type": "noul", "instructions": "compare to {img:a} " + filler},
        "q2": {"type": "noul", "instructions": "compare to {img:b} " + filler},
        "q3": {"type": "noul", "instructions": "state only " + filler},
    }
    # ~3.3k (state image) + 3 x 15k text > 32k limit, so the request splits.
    result = jev_transport.evaluate({"frame": state_img}, questions, timeout=5, images={"a": only_q1, "b": only_q2})
    assert set(result["answers"]) == {"q1", "q2", "q3"}
    assert len(wire) >= 2
    by_question: dict[str, int] = {}
    for request in wire:
        parts = _parse_multipart(request)
        payload = json.loads(parts[0][1])
        n_files = len(parts) - 1
        assert n_files == len(payload["assets"])
        text = json.dumps(payload["state"]) + json.dumps(payload["questions"])
        assert all(ref in text for ref in payload["assets"])  # no unreferenced asset
        state_ref = payload["state"]["frame"]
        assert state_ref in payload["assets"]  # the state image rides with every split
        for qid in payload["questions"]:
            by_question[qid] = n_files
    assert by_question["q3"] == 1
    assert by_question["q1"] == 2
    assert by_question["q2"] == 2


def test_split_reports_state_image_tokens_resent(wire: list[Any], tmp_path: Path) -> None:
    state_img = JevImage(_png(tmp_path / "s.png", (1568, 1568)))
    filler = "z" * 60_000
    questions = {f"q{i}": {"type": "noul", "instructions": "state only " + filler} for i in range(3)}
    with pytest.warns(UserWarning, match="resends the state images"):
        result = jev_transport.evaluate({"frame": state_img}, questions, timeout=5)
    split = result["_meta"]["split"]
    assert split["requests"] >= 2
    assert split["state_image_tokens_resent"] > 0


def test_unsplit_image_request_has_no_resend_note(wire: list[Any], tmp_path: Path) -> None:
    shot = JevImage(_png(tmp_path / "a.png", (800, 600)))
    result = jev_transport.evaluate({"frame": shot}, {"q": {"type": "noul", "instructions": "ok?"}}, timeout=5)
    assert "split" not in result.get("_meta", {})


def test_text_only_path_is_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("JEV_TRANSPORT", "direct")
    monkeypatch.setenv("TYPESAFE_API_KEY", "secret")
    seen: dict[str, Any] = {}

    def call(payload: dict, api_key: str, timeout: float, **kwargs: Any) -> tuple[dict, float]:
        seen.update(payload=payload, kwargs=kwargs)
        return {"answers": {}}, 1.0

    monkeypatch.setattr(jev_transport.jev_router_common, "call_jev", call)
    questions = {"ok": {"type": "noul", "instructions": "{img:x} stays text"}}
    jev_transport.evaluate({"a": 1}, questions, timeout=3)
    assert seen["kwargs"] == {"script_name": "jev_transport.py"}
    assert seen["payload"] == {"state": {"a": 1}, "model": "jev-1.14.0", "questions": questions}


def test_text_only_http_request_is_plain_json(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("TYPESAFE_API_KEY", "secret")
    monkeypatch.setenv("JEV_CACHE_TTL_S", "0")
    captured: list[Any] = []

    def fake_open(request: Any, timeout: float) -> _Resp:
        captured.append(request)
        return _Resp(b'{"answers": {}}')

    monkeypatch.setattr(jev_router_common, "_open_url", fake_open)
    jev_transport.evaluate({"a": 1}, {"q": {"type": "noul", "instructions": "ok?"}}, timeout=3)
    (request,) = captured
    assert request.get_header("Content-type") == "application/json"
    assert request.get_header(jev_images.IMAGES_HEADER.capitalize()) is None
    assert json.loads(request.data)["state"] == {"a": 1}
