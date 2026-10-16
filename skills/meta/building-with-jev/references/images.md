# Send images to Jev

Jev accepts PNG and JPEG images in `state`, instructions, and criteria. The feature is "dreamer-ready": prototype-grade. Use image judgments to steer a hill climb. Never use one as the only deploy gate; pair it with a measured number.

## Send an image

Use `scripts/jev_transport.py`. It handles preparation, references, multipart encoding, and the required header.

```python
from jev_images import JevImage
import jev_transport

frame = JevImage("/path/to/frame.png")          # path, bytes, or a Pillow image
result = jev_transport.evaluate(
    {"candidate": frame, "owner_note": "arms read as too thin"},   # object in place
    {"thin": {"type": "noul", "instructions": "Do the arms in {img:frame} look thin?"}},
    timeout=90,
    images={"frame": frame},                    # named placeholder: write {img:frame}
)
```

- Put a `JevImage` anywhere as a value, or pass `images={"name": JevImage}` and write `{img:name}` in any string, mid-sentence or whole. Use either or both.
- The same `JevImage` object is one asset, however often you use it.
- Each use of an image adds its tokens again. Reference an image once per request unless a question needs it.
- `evaluate_packed` takes the same arguments.

## Routing

| Request has | Transport | Why |
|---|---|---|
| Image or Box question | Direct API only | The Vercel gateway bridge cannot carry images. |
| Image, no `TYPESAFE_API_KEY` | Raises `JevTransportError`, source `images_unsupported` | No silent fallback to text. |
| Bad image | Raises `JevTransportError`, source `invalid_image`, nothing sent | The API fails the whole request on one bad image. |

The transport sends the header `TypeSafe-Danger-Zone-Images: true` whenever the request has an image or a Box question. It sends multipart: part `request` holds the JSON, and each image is its own part. A Box question needs Jev 1.14; the transport only adds the header for it.

## Limits

| Limit | Value |
|---|---|
| Format | PNG or JPEG |
| File size | 16 MiB |
| Each side | 280-1568 px |
| Total pixels | 78,400-2,458,624 |
| Request body | 32 MiB |
| Expanded request | 32 MiB (counts each use of an image) |

The API never resizes. One image outside a limit fails the whole request with 400 or 413.

## Prepare an image

`JevImage` calls `prepare_image` for you. It applies EXIF rotation, shrinks to fit 1568 px, upscales a side under 280 px (pads instead when upscaling would pass 1568 px), and saves a baseline JPEG at quality 90. An image with real transparency stays PNG. It raises `JevImageError` if the image cannot be made valid.

Pass `JevImage(path, prepare=False)` to send bytes unchanged. They must already pass the limits.

## Token cost and splitting

Image bytes never count toward the text estimate. `jev_limits` adds `width * height / 375` tokens per use (`jev_images.IMAGE_PIXELS_PER_TOKEN`). Measured on the direct API on 2026-10-16: 300x300 cost 271 tokens, 800x600 cost 1,301, 1568x1568 cost 6,300. Read `usage.input_tokens` in the response for the real cost, and re-measure when the model changes.

Image requests split only above 32,000 estimated tokens (the 3,500 and 4,500 limits come from Gateway failures and do not apply to direct calls). A split request carries the state images and only the question images its own questions use. Each split resends the state images, so keep images out of state when only one question needs them.

## Hill-climb with images

Jev reads the description and the image together, but it ranks a candidate against what you show it. Anchor it to reality:

1. Get the owner to rate a few reference images once on the Score ladder (for example, "this reference is 9/10, ours is 1/10").
2. Put each rated reference in the state as an image, with the owner's rating in text next to it.
3. Put the candidate render in the state the same way, plus the measured numbers (pixel widths, timings).
4. Ask "how far is the candidate from the reference" as a Score, and ask a separate Noul: "did anything get worse?"
5. Show the owner a side-by-side before you report progress.

When the owner's eye and Jev disagree, write the owner's note into the ladder level and re-score the baseline. See `references/iteration-with-jev.md`.
