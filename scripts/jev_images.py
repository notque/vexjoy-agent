"""Image support for Jev requests: prepare pictures, bind references, encode multipart.

TypeSafe's System One API (dreamer-ready, prototype-grade) accepts PNG and JPEG
images. Request side, in one line: write a ``JevImage`` (or a ``{img:name}``
placeholder) anywhere in the state or in a question; ``bind_images`` swaps each
one for a fresh uuid reference and returns the ``assets`` the API needs.

Design:
    * Objects in place: a ``JevImage`` used as a value in state, instructions,
      or criteria becomes its reference string. The same object used twice is
      one asset.
    * Named placeholders: pass ``images={"name": JevImage(...)}`` and write
      ``"{img:name}"`` inside any string, mid-sentence or as the whole value.
    * Text-only requests never touch this module's heavy paths. Pillow loads
      only when an image is prepared.

Limits (checked 2026-10-16 against the TypeSafe docs): PNG or JPEG, 16 MiB per
file, each side 280-1568 px, 78,400-2,458,624 pixels, 32 MiB request body, 32 MiB
expanded request. The API never resizes: one bad image fails the whole request.
``prepare_image`` makes an image valid before it is sent.

Nothing here logs image bytes or base64.
"""

from __future__ import annotations

import io
import json
import math
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, NamedTuple

# --- Documented image limits ---
MIN_SIDE = 280
MAX_SIDE = 1568
MIN_PIXELS = 78_400
MAX_PIXELS = 2_458_624
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_REQUEST_BYTES = 32 * 1024 * 1024
# 95, not 90 (2026-10-16): TypeSafe says Jev reads JPEGs of about 512 KB-2 MB best. A 1568x1176 UI-like
# image encodes to 247 KB at q90 and 291 KB at q95; a noisy photo-like one to 450 KB and 615 KB.
JPEG_QUALITY = 95

# --- Token estimate (MEASURED once, 2026-10-16; re-measure when the model changes) ---
# TypeSafe publishes no per-image token count. Measured on the direct API
# (jev-latest): one synthetic image in state vs the same request with a text
# stand-in. Added input tokens: 300x300 -> 271, 800x600 -> 1301, 1568x1568 -> 6300,
# about width * height / 390 plus roughly 40 tokens. The constant is the middle of
# that range, so the estimate is within ~10% of the measured cost at all three sizes.
IMAGE_PIXELS_PER_TOKEN = 375
IMAGE_TOKEN_MEASUREMENT = "2026-10-16 direct API: 300x300=271, 800x600=1301, 1568x1568=6300 tokens"

IMAGES_HEADER = "TypeSafe-Danger-Zone-Images"
# Box questions need Jev 1.14; "jev-latest" resolved to 1.13 and returned 400
# on 2026-10-16, and "jev-1.14" was also refused. Move back to "jev-latest"
# once it reaches 1.14.
BOX_MODEL = "jev-1.14.0"

_PLACEHOLDER = re.compile(r"\{img:([A-Za-z0-9_.-]+)\}")
_MIME = {"jpg": "image/jpeg", "png": "image/png"}


class JevImageError(ValueError):
    """An image cannot be made valid, or a request's images are inconsistent."""


class PreparedImage(NamedTuple):
    """Encoded image bytes plus the facts the limits depend on."""

    data: bytes
    fmt: str  # "jpg" or "png"
    width: int
    height: int

    @property
    def mime(self) -> str:
        return _MIME[self.fmt]

    @property
    def est_tokens(self) -> int:
        return estimate_image_tokens(self.width, self.height)


def estimate_image_tokens(width: int, height: int) -> int:
    """Estimated billed input tokens for one use of a width x height image (measured; see IMAGE_TOKEN_MEASUREMENT)."""
    return math.ceil(width * height / IMAGE_PIXELS_PER_TOKEN)


def _pil() -> Any:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:  # pragma: no cover - depends on the environment
        raise JevImageError("Pillow is required to send images to Jev: pip install Pillow") from exc
    return Image, ImageOps


def _check_dims(width: int, height: int) -> None:
    if not (MIN_SIDE <= width <= MAX_SIDE and MIN_SIDE <= height <= MAX_SIDE):
        raise JevImageError(f"image is {width}x{height}; each side must be {MIN_SIDE}-{MAX_SIDE} px")
    if not (MIN_PIXELS <= width * height <= MAX_PIXELS):
        raise JevImageError(f"image has {width * height} pixels; allowed {MIN_PIXELS}-{MAX_PIXELS}")


def _load_bytes(src: Any) -> bytes | None:
    if isinstance(src, (bytes, bytearray)):
        return bytes(src)
    if isinstance(src, (str, Path)):
        try:
            return Path(src).read_bytes()
        except OSError as exc:
            raise JevImageError(f"cannot read image file: {exc.strerror or type(exc).__name__}") from exc
    return None


def _open(src: Any) -> Any:
    Image, _ = _pil()
    raw = _load_bytes(src)
    if raw is None:
        if hasattr(src, "size") and hasattr(src, "mode"):
            return src
        raise JevImageError(f"unsupported image source type {type(src).__name__}")
    try:
        im = Image.open(io.BytesIO(raw))
        im.load()
    except Exception as exc:
        raise JevImageError(f"cannot decode image ({type(exc).__name__})") from exc
    return im


def open_image(src: Any) -> Any:
    """Open a path, bytes, or Pillow image as an RGB Pillow image with EXIF rotation applied.

    Use it to crop or tile a full-resolution source before wrapping the pieces in ``JevImage``.
    """
    _, ImageOps = _pil()
    im = _open(src)
    im = ImageOps.exif_transpose(im) or im
    return im.convert("RGB")


def _has_transparency(im: Any) -> bool:
    if im.mode in ("RGBA", "LA", "PA"):
        alpha = im.convert("RGBA").getchannel("A")
        return alpha.getextrema()[0] < 255
    return im.mode == "P" and "transparency" in im.info and im.convert("RGBA").getchannel("A").getextrema()[0] < 255


def validate_image_bytes(data: bytes) -> PreparedImage:
    """Check already-encoded bytes against the limits without changing them.

    Raises JevImageError for the wrong format, a bad size, or a bad dimension.
    EXIF orientation is not applied: use ``prepare_image`` for camera photos.
    """
    if len(data) > MAX_FILE_BYTES:
        raise JevImageError(f"image is {len(data)} bytes; limit {MAX_FILE_BYTES}")
    Image, _ = _pil()
    try:
        with Image.open(io.BytesIO(data)) as im:
            fmt = {"JPEG": "jpg", "PNG": "png"}.get(im.format or "")
            width, height = im.size
    except Exception as exc:
        raise JevImageError(f"cannot decode image ({type(exc).__name__})") from exc
    if fmt is None:
        raise JevImageError("only PNG and JPEG images are accepted")
    _check_dims(width, height)
    return PreparedImage(data, fmt, width, height)


def prepare_image(src: Any) -> PreparedImage:
    """Make ``src`` (path, bytes, or a Pillow image) valid for Jev.

    Steps: apply EXIF rotation, shrink to fit 1568 px, upscale an image with a
    side under 280 px (padding instead when upscaling would pass 1568 px), then
    encode as baseline JPEG at quality 95. An image with real transparency stays
    PNG. Returns ``(data, fmt, width, height)``.
    """
    Image, ImageOps = _pil()
    im = _open(src)
    im = ImageOps.exif_transpose(im) or im
    if im.size[0] < 1 or im.size[1] < 1:
        raise JevImageError("image has no pixels")
    keep_alpha = _has_transparency(im)
    im = im.convert("RGBA" if keep_alpha else "RGB")

    im.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
    width, height = im.size
    if min(width, height) < MIN_SIDE:
        scale = MIN_SIDE / min(width, height)
        if max(width, height) * scale <= MAX_SIDE:
            im = im.resize(
                (max(MIN_SIDE, round(width * scale)), max(MIN_SIDE, round(height * scale))),
                Image.Resampling.LANCZOS,
            )
        else:
            # An aspect ratio past 1568:280 cannot satisfy both limits by scaling: pad the short side.
            fill = (255, 255, 255, 0) if keep_alpha else (255, 255, 255)
            canvas = Image.new(im.mode, (max(width, MIN_SIDE), max(height, MIN_SIDE)), fill)
            canvas.paste(im, ((canvas.width - width) // 2, (canvas.height - height) // 2))
            im = canvas
    width, height = im.size
    _check_dims(width, height)

    buf = io.BytesIO()
    if keep_alpha:
        im.save(buf, "PNG")
        fmt = "png"
    else:
        im.save(buf, "JPEG", quality=JPEG_QUALITY, progressive=False)
        fmt = "jpg"
    data = buf.getvalue()
    if len(data) > MAX_FILE_BYTES:
        raise JevImageError(f"encoded image is {len(data)} bytes; limit {MAX_FILE_BYTES}")
    return PreparedImage(data, fmt, width, height)


@dataclass(eq=False)
class JevImage:
    """An image to send to Jev. Identity matters: one object is one asset.

    ``source`` is a path, bytes, or a Pillow image. With ``prepare=True`` (the
    default) the image is made valid by ``prepare_image``; with ``prepare=False``
    the bytes must already be a valid PNG or JPEG and are sent unchanged.
    """

    source: Any
    prepare: bool = True
    _prepared: PreparedImage | None = field(default=None, init=False, repr=False)

    def resolve(self) -> PreparedImage:
        """Return the encoded image, preparing it once."""
        if self._prepared is None:
            if self.prepare:
                self._prepared = prepare_image(self.source)
            else:
                raw = _load_bytes(self.source)
                if raw is None:
                    raise JevImageError("prepare=False needs a path or bytes source")
                self._prepared = validate_image_bytes(raw)
        return self._prepared

    def __repr__(self) -> str:  # never show bytes
        kind = type(self.source).__name__
        return f"JevImage({kind}, prepare={self.prepare})"


@dataclass
class BoundRequest:
    """State and questions with references substituted, plus the assets they name."""

    state: Any
    questions: dict[str, Any]
    assets: dict[str, PreparedImage]  # reference -> image


def _walk(node: Any, sub: Any) -> Any:
    if isinstance(node, (JevImage, str)):
        return sub(node)
    if isinstance(node, dict):
        return {k: _walk(v, sub) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [_walk(v, sub) for v in node]
    return node


def contains_images(state: Any, questions: Any, images: dict[str, JevImage] | None = None) -> bool:
    """True when state or questions hold a JevImage, or a ``{img:name}`` placeholder with ``images`` given."""
    found = False

    def look(node: Any) -> Any:
        nonlocal found
        if isinstance(node, JevImage) or (images and isinstance(node, str) and _PLACEHOLDER.search(node)):
            found = True
        return node

    _walk(state, look)
    _walk(questions, look)
    return found


def has_box(questions: dict[str, Any]) -> bool:
    """True when any question is a Box question (it needs the images header)."""
    return any(isinstance(q, dict) and q.get("type") == "box" for q in questions.values())


def bind_images(state: Any, questions: dict[str, Any], images: dict[str, JevImage] | None = None) -> BoundRequest:
    """Replace every image in ``state`` and ``questions`` with a fresh uuid reference.

    The same ``JevImage`` used in several places is one asset. Raises
    JevImageError for an unknown placeholder name, a named image never used, or
    an image that cannot be prepared.
    """
    images = images or {}
    refs: dict[int, str] = {}  # id(JevImage) -> reference
    assets: dict[str, PreparedImage] = {}
    used_names: set[str] = set()

    def ref_for(img: JevImage) -> str:
        ref = refs.get(id(img))
        if ref is None:
            ref = uuid.uuid4().hex
            assets[ref] = img.resolve()
            refs[id(img)] = ref
        return ref

    def named(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in images:
            raise JevImageError(f"placeholder {{img:{name}}} has no image in images={sorted(images)}")
        used_names.add(name)
        return ref_for(images[name])

    def sub(node: Any) -> Any:
        if isinstance(node, JevImage):
            return ref_for(node)
        return _PLACEHOLDER.sub(named, node) if images else node

    bound_state = _walk(state, sub)
    bound_questions = _walk(questions, sub)
    # A named image nobody references is a typo or dead weight; refuse it.
    unused = sorted(n for n, img in images.items() if n not in used_names and id(img) not in refs)
    if unused:
        raise JevImageError(f"images never referenced: {unused}")
    return BoundRequest(bound_state, bound_questions, assets)


def _text(*values: Any) -> str:
    return "".join(json.dumps(v, ensure_ascii=False, separators=(",", ":")) for v in values)


def ref_uses(refs: list[str] | dict[str, Any], state: Any, questions: dict[str, Any]) -> dict[str, int]:
    """Count how often each reference appears in state and questions."""
    text = _text(state, questions)
    return {ref: text.count(ref) for ref in refs}


def assets_for(assets: dict[str, PreparedImage], state: Any, questions: dict[str, Any]) -> dict[str, PreparedImage]:
    """The assets that state and these questions reference (what a split request must carry)."""
    uses = ref_uses(assets, state, questions)
    return {ref: img for ref, img in assets.items() if uses[ref] > 0}


def image_token_map(assets: dict[str, PreparedImage]) -> dict[str, int]:
    """Reference -> estimated tokens per use, for the splitter's size estimate."""
    return {ref: img.est_tokens for ref, img in assets.items()}


def check_assets(assets: dict[str, PreparedImage], state: Any, questions: dict[str, Any]) -> None:
    """Refuse a request the API would reject: unreferenced asset, bad image, or too large.

    Each use of a reference adds the image again, so the expanded size counts
    base64 once per use.
    """
    uses = ref_uses(assets, state, questions)
    missing = sorted(ref for ref, n in uses.items() if n == 0)
    if missing:
        raise JevImageError(f"{len(missing)} asset(s) never referenced in state or questions")
    expanded = len(_text(state, questions))
    body = expanded
    for ref, img in assets.items():
        _check_dims(img.width, img.height)
        if len(img.data) > MAX_FILE_BYTES:
            raise JevImageError(f"image is {len(img.data)} bytes; limit {MAX_FILE_BYTES}")
        body += len(img.data)
        expanded += uses[ref] * math.ceil(len(img.data) * 4 / 3)
    if body > MAX_REQUEST_BYTES:
        raise JevImageError(f"request body would be {body} bytes; limit {MAX_REQUEST_BYTES}")
    if expanded > MAX_REQUEST_BYTES:
        raise JevImageError(f"expanded request would be {expanded} bytes; limit {MAX_REQUEST_BYTES}")


def wire_assets(
    assets: dict[str, PreparedImage],
) -> tuple[dict[str, dict[str, str]], dict[str, tuple[bytes, str]]]:
    """Build the JSON ``assets`` map and the multipart file parts.

    Returns ``(assets_map, parts)``: ``parts`` maps a part name to
    ``(bytes, content_type)``. Part names are ``img0``, ``img1``, ... and never
    ``request``.
    """
    assets_map: dict[str, dict[str, str]] = {}
    parts: dict[str, tuple[bytes, str]] = {}
    for i, (ref, img) in enumerate(assets.items()):
        part = f"img{i}"
        assets_map[ref] = {"type": "image", "part": part}
        parts[part] = (img.data, img.mime)
    return assets_map, parts


def encode_multipart(payload: dict[str, Any], parts: dict[str, tuple[bytes, str]]) -> tuple[bytes, str]:
    """Encode the JSON request as part ``request`` followed by one file part per image."""
    boundary = uuid.uuid4().hex
    crlf = b"\r\n"
    chunks = [
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="request"\r\n'
        "Content-Type: application/json\r\n\r\n".encode(),
        json.dumps(payload).encode("utf-8"),
        crlf,
    ]
    for name, (data, mime) in parts.items():
        if name == "request":
            raise JevImageError("part name 'request' is reserved")
        ext = "png" if mime == "image/png" else "jpg"
        chunks.append(
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="{name}"; filename="{name}.{ext}"\r\n'
                f"Content-Type: {mime}\r\n\r\n"
            ).encode()
        )
        chunks.append(data)
        chunks.append(crlf)
    chunks.append(f"--{boundary}--\r\n".encode())
    body = b"".join(chunks)
    if len(body) > MAX_REQUEST_BYTES:
        raise JevImageError(f"request body is {len(body)} bytes; limit {MAX_REQUEST_BYTES}")
    return body, f"multipart/form-data; boundary={boundary}"


def image_meta(assets: dict[str, PreparedImage]) -> dict[str, Any]:
    """Safe telemetry: count, total bytes, and dimensions. Never the bytes."""
    return {
        "count": len(assets),
        "bytes": sum(len(i.data) for i in assets.values()),
        "dims": [[i.width, i.height] for i in assets.values()],
    }
