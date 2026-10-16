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

`JevImage` calls `prepare_image` for you. It applies EXIF rotation, shrinks to fit 1568 px, upscales a side under 280 px (pads instead when upscaling would pass 1568 px), and saves a baseline JPEG at quality 95. An image with real transparency stays PNG. It raises `JevImageError` if the image cannot be made valid.

Pass `JevImage(path, prepare=False)` to send bytes unchanged. They must already pass the limits.

## Token cost and splitting

Image bytes never count toward the text estimate. `jev_limits` adds `width * height / 375` tokens per use (`jev_images.IMAGE_PIXELS_PER_TOKEN`). Measured on the direct API on 2026-10-16: 300x300 cost 271 tokens, 800x600 cost 1,301, 1568x1568 cost 6,300. Read `usage.input_tokens` in the response for the real cost, and re-measure when the model changes.

Image requests split only above 32,000 estimated tokens (the 3,500 and 4,500 limits come from Gateway failures and do not apply to direct calls). A split request carries the state images and only the question images its own questions use. Each split resends the state images, so keep images out of state when only one question needs them.

## Locate a target with Box

Box is experimental. `scripts/jev_box.py` treats it as one signal among several, and splits the goal into small Jev calls plus plain code. A Box always returns edges, so `locate` asks a presence Choice and a count Choice beside it, then refines.

```python
import jev_box

res = jev_box.locate(
    "/path/to/shot.png",
    "the round 'next turn' button",
    context={"dom_buttons": ["end turn", "menu"]},    # structured facts beside the picture
)
if res.needs_escalation:
    ...                                     # hand the image to a stronger model; read res.escalation_reasons
elif res.status == "found":
    x, y = res.center                       # pixels of the ORIGINAL image
```

The result carries every signal: `status` (`found`, `absent`, `several`, `low_confidence`), `present`, `count` and `count_exact`, `confidence`, `box`, `box_before_edge`, `edge_verified`, `steps`, `notes`, `warnings`, `requests`, and `input_tokens` (the sum of `usage.input_tokens`). Check the app first when it can answer (DOM, preview state): its ground truth beats Box, a Noul, or a Choice, especially for absence. Do not click, delete, or ship on Box alone.

| Pattern | What `locate` does | Argument |
|---|---|---|
| Presence | A present/absent Choice with the Box in one request. Below `presence_min` (0.7), or a clear count of none, it returns `absent` and no box. | `presence` (`"choice"` or `"noul"`), `presence_min` |
| Count | A Choice `none` / `one` / `several` in the same request. `several` returns the count so you can narrow the description. With `count_max=N` the options are exact: "0" to "N" and "N+1+". | `count_max` |
| Refine | Confidence under `confidence_min` (0.8), or a first box under 64 px as sent: crop a padded region from the full-resolution original, enlarge it toward 1080 px, ask again, and map the box back. | `refine`, `confidence_min` |
| Tiles | On `several`, or when a refine crop misses the target: a Choice over tile pictures picks a region, then a Box runs on that tile. | `tile_grid=(rows, cols)` |
| Edge check | Crop to the box, ask one Noul per edge ("does the target continue past the top edge?"), move each yes-edge outward, repeat. | `edge_check`, `max_rounds` |
| Reference target | A second picture goes into the instructions and the target is the shape that matches it. | `reference` |
| Context | Your JSON goes into the state of every request except edge checks, with a one-line legend for each picture. | `context` |

Rules:

- Crops come from the original image, never the shrunk copy. A crop keeps each side at 280 px or more and the aspect under 5.5:1, so `prepare_image` never pads and the fractions stay true.
- Jev reads high-resolution pictures better: aim for a long side of at least 1080 px. `res.warnings` names any picture sent below that.
- `to_parent(child_box, crop_box)` maps edges found in a crop back to the full image. `pad`, `crop`, `tiles`, `to_pixels`, `center`, and `iou` are public helpers.
- Name one target per call, in words that single out one instance.
- An image wider or taller than 5.5:1 raises `JevBoxError`: tile it first.
- `needs_escalation` is true for an indecisive presence (0.3 up to `presence_min`), presence and count that disagree, `several` with no `tile_grid`, a final confidence under the minimum, a refine or tile crop that missed, or an edge check still moving after the last round. Hand those to a stronger model instead of looping.

Measured 2026-10-16 on `jev-1.14.0`, synthetic shapes (re-measure on your images):

| Case | Result |
|---|---|
| Red square, 800x600 | confidence 0.95, IoU 0.97, 2 requests, 2,473 tokens; the edge check moved nothing |
| 30x30 square in 3000x2000, one full-image Box | confidence 0.77-0.83, IoU 0.07-0.40, 4,810 tokens |
| Same, refine crop, then edge check | confidence 0.94-0.99, IoU 0.57-0.81 (refine alone 0.52-0.77), 9,700-9,900 tokens |
| Same, tiles only (3x3) | confidence 0.84-0.97, IoU 0.40-0.58, 21,600 tokens |
| Edge check after refine | IoU +0.08, +0.02, +0.16 on three positions; it moved a good box from 0.65 to 0.81 |
| Absent target | presence 0.00, count `none`, `absent`, 1,827 tokens |
| Two identical squares | count `several`; with `tile_grid=(1,2)`, 3 requests, 4,815 tokens, one instance found (confidence 0.71-0.91 across runs) |
| Reference match, star vs triangle | IoU 0.97, 2 requests, 3,370 tokens |
| Exact count, 2 and 3 squares, `count_max=5` | "2" and "3", both right |
| Same square at 800 vs 1568 px long side | IoU 0.64-0.68 vs 0.71-0.78, confidence unchanged, 1,828 vs 5,257 tokens |
| Presence as Choice vs Noul | equal on seven clear cases; on a reference match the Choice read 0.94-0.96 and the Noul 0.84-0.87 |

Findings:

- Confidence alone does not flag a small-target miss: first boxes with IoU under 0.4 scored 0.75-0.84. The size rule (a first box under 64 px as sent) catches them. TypeSafe publishes no threshold; 0.8 is provisional.
- Refine beats tiles on cost and accuracy. Keep tiles as the fallback.
- `prepare_image` saves JPEG at quality 95. At 90 a 1568x1176 UI-like image was 247 KB and a noisy photo-like one 450 KB; at 95 they are 291 KB and 615 KB, nearer the 512 KB to 2 MB range TypeSafe recommends.
- On 2026-10-16 the model name `jev-preview` answered a Box request and reported `jev-1.14.0`. `BOX_MODEL` stays pinned to `jev-1.14.0`.

Judge the final box by IoU against a measured truth when you have one.

## Hill-climb with images

Jev reads the description and the image together, but it ranks a candidate against what you show it. Anchor it to reality:

1. Get the owner to rate a few reference images once on the Score ladder (for example, "this reference is 9/10, ours is 1/10").
2. Put each rated reference in the state as an image, with the owner's rating in text next to it.
3. Put the candidate render in the state the same way, plus the measured numbers (pixel widths, timings).
4. Ask "how far is the candidate from the reference" as a Score, and ask a separate Noul: "did anything get worse?"
5. Show the owner a side-by-side before you report progress.

When the owner's eye and Jev disagree, write the owner's note into the ladder level and re-score the baseline. See `references/iteration-with-jev.md`.
