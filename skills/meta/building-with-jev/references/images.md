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

Capture sharp. Jev reads high-resolution images better, and a TypeSafe engineer advises a long side of at least 1080 px, with JPEGs of about 512 KB to 2 MB. Shoot phone viewports at `deviceScaleFactor` 2 or 3, crop to the region instead of shrinking a full page, and pay the extra tokens rather than downscaling. Upscaling a small capture adds no detail. Send structured facts (measured numbers, a one-line legend per image) beside every image: the image and the structure together beat either alone.

## Token cost and splitting

Image bytes never count toward the text estimate. `jev_limits` adds `width * height / 375` tokens per use (`jev_images.IMAGE_PIXELS_PER_TOKEN`). Measured on the direct API on 2026-10-16: 300x300 cost 271 tokens, 800x600 cost 1,301, 1568x1568 cost 6,300. Read `usage.input_tokens` in the response for the real cost, and re-measure when the model changes.

Billing is per request, not per question: three state images cost 9,614, 10,190, and 12,258 input tokens with 1, 6, and 24 questions. A split is what multiplies it: 7 state images with 230 questions became 7 requests that each resent all 7 images (179,022 tokens against 37,898 for 140 questions in one request). `evaluate()` records `_meta.split.state_image_tokens_resent` and warns when it happens. Keep state images few, send one request per image or per 3 or 4 images, and keep questions per image modest. The estimate runs about 25% low, so a split starts later than it says.

Image requests split only above 32,000 estimated tokens (the 3,500 and 4,500 limits come from Gateway failures and do not apply to direct calls). A split request carries the state images and only the question images its own questions use. Every split resends every state image, so keep images out of state when only one question needs them.

## Defect checks on screenshots

A broad "is something broken here" Noul over-flags: on 4 clean synthetic pages with an intentional scrolling tab strip and silhouette avatars it read 0.85 and 0.80 on two of them (on 100 real app screens it flagged 54 for 3 real defects). Ask one Noul per defect kind instead, with the intent in the wording: broken-image icon, overlapping text, error banner, text cut off "where the content is not meant to scroll". That gave 0 of 4 clean flagged (all 0.15 or lower) and 6 of 6 defects found at 0.90 to 1.00, and the firing kind named the defect (a follow-up kind Choice was wrong on 2 of 3 real defects).

- Spell out the visual signature in exemption wording ("dark or gray card"), not the category: on real screens an exemption fired on dark portrait cards until it did. Put the decisive DOM fact inside the visual Noul's wording ("answer true when `dom.failed_image_requests` lists a failed image"): an 8 px broken-image glyph went from 0.28 to 0.97 with no new clean flags, and it beat zoom crops. On 100 real app screens, per-kind Nouls flagged 6 of 73 clean screens at 0.6 against 52 of 73 for the broad Noul. Wait for SPA skeletons to settle (at least 1 s and two consecutive clear polls) before you capture, and allow-list intentionally dark art, which reads as broken to Jev and Box.
- A list of `intentional_patterns` in state cut false positives to 0 of 4 but also dropped a real broken-image defect to 0.47 and 0.25. List patterns narrowly, then check that real defects of the same kind still fire.
- Pair every flag with the app's own facts (DOM errors, failed requests, store state): they beat a visual read. For image QA, check references against disk and fetch status first; Jev adds little over Pillow for corruption and is best for semantic checks (wrong content, colours, crop).
- Jev cannot judge pixel sizes, counts, exact measurements, or small text from an image: a 32 px button read 0.71 for "44 px or more", and a visibility Noul missed small tab labels. Measure each in code (sizes, bounding-box overlap, DOM visibility) and send the number; each is a code guard, not a Jev question.
- Full-page stitches create artifacts that judges read as defects: fixed and sticky elements repainted over content, and intentional horizontal clipping (a swipe carousel, reserved empty space). On 31 full-page captures a "broken?" Noul flagged 16 at 0.6 or more while measures found 0 problems; after a state fact ("image edges are viewport or crop edges; content past them is scrolling") and a question narrowed to defects inside the image, 7 flagged and 12 were undecided, and by eye the rest were artifacts. Capture viewport tiles at scroll positions, hide or capture fixed and sticky elements separately, give DOM facts for fixed, sticky, and overflow-x elements, and calibrate on a labeled broken set before you trust flags.
- A section cut off by a fixed bottom tab bar read as normal (0.02 and 0.03 while measurably cut, n=2). "Cut by the viewport or a fixed bar" is a measured guard: compare the element's bounding box with the fixed bar's rect in code. Jev's read flipped with how much of the element showed (0.02 and 0.03 to 0.90) while the bounding-box guard stayed steady.
- Re-render and look at the screenshot after every CSS change, before you ask Jev: an unlayered component rule beat a Tailwind `max-sm:hidden` utility and only the render showed it. Pair this with the hash-diff rule.
- Hide fixed-position bars before a full-page capture, take viewport slices, and send the frames that show the property under judgment: a key-pose strip in time order, not the impact frame with a damage badge on it (on a card-battler move poster `anatomy_broken` read 0.83 to 0.86 on the static frame and 0.34 to 0.44 on the strip, n=4). Remove overlays that are not part of the property.
- A flag is not a verdict on a person's photo: use a deterministic allow-list or a "was this intended?" step for unexpected-but-real content, audit false positives by subgroup, and never act automatically on a Jev flag of a person.
- Fine pose or near-miss identity in stylised art is at chance on 1.14 (20 of 36 correct, AUC 0.554, with confident errors); use it only as a labeled re-test benchmark.


A literal, single-condition image Noul works. "Is the bottom cut off?" on labeled crops: clean 0.03 to 0.05, cropped 0.99, 10 of 10 (the pixel measure was also 10 of 10); 58 real 1200x630 cards all read 0.02 to 0.05 with the edge measure at 0; 2.4 to 4.6k tokens per card. Scope: crop-style cutoffs only. Pair it with the pixel edge measure.

## Contact grids

To check many tiles (product photos, avatars), draw one image with a visible number on every tile and a legend in state (`grid` has 24 numbered tiles, 6 columns, each should show X). On a synthetic 24-tile grid with 8 planted defects:

| Shape | Input tokens | Result |
|---|---|---|
| 24 six-way Choices, short criteria | 6,634 | 8 of 8 found and labeled |
| 24 per-tile Noul "is this normal?" | 3,897 | 8 of 8 found, 0 false positives |
| 5 per-kind Choices over tile numbers plus `none` | 4,324 | one tile per kind: 5 of 8 |
| 1 grid-level Noul | 3,345 | gross defects 0.00; clean grids only 0.78 |

- Use a per-tile Noul to find candidates; ask the six-way Choice only on the flagged tiles. Keep criteria to a few words: repeated long criteria were most of the 18.7k tokens per grid in one field run.
- Act at `p_normal` of 0.1 or less on a per-tile Noul and send the rest to review; on real grids this cut false flags from 36% to 13% and tokens per grid from about 18k to 8 to 12k. Dark helmets are the main false-flag group, clustered at `p_normal` 0.31 to 0.44.
- Gate on the chosen option's probability (0.9 or more), not on the label. Real tiles produced false positives at 0.47 to 0.80 that our synthetic tiles did not.
- A per-kind Choice names one tile per kind, so it misses repeats. A grid-level Noul does not locate and read 0.0 to 0.8 on real grids; never make it the only check. Jev does not count or aggregate.

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
- Box is not a UI-defect locator: on real hits IoU against DOM rects was 0.095 and 0.012, and it was absent on a real near-black helmet. Use it for controls and clear objects.
- Name one target per call, in words that single out one instance and that the page can match: "the broken image" found a broken-image icon 2 of 2 (IoU 0.88 and 0.93) and "the clipped text" aimed at overlapping text returned `several` 2 of 2. A concrete location added no IoU. On a screen a Noul flagged, `absent` is evidence against the flag: 55 calls on flagged real screens found 0 because 52 of 54 had no defect.
- Run our Jev client without `python3 -I`: it hides a user-site Pillow, and `jev_images` and `jev_box` fail to import. Use a venv with Pillow when you must isolate.
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

On an image goal, put the anchor images into the Score ladder levels ("reads like the owner's 1/10 {img:base}" up to "9/10 {img:mod}"). A ladder of text signals alone failed the anchor check: the owner's 9/10 mod read 2.03 against 1.98 for the 1/10 base, flat over levels 1 to 3. With anchor images in the levels, mod read 2.26 to 2.48 and base 1.14 to 1.54: ordered right, but base did not land at level 0 even though level 0 was its own image (0.11 to 0.18 there). Expect partial calibration. It cost 31 to 41k tokens per request with 6 to 8 images (fine on the direct API).

Before every image before/after:

- Hash-diff kept against candidate (`hashlib.sha1` of each file or tile) and prove the pixels changed. A render path at resolution 2 ignored the edits (0 of 16 tiles changed), and Jev would have judged identical images.
- Include a byte-identical control pair (same sha1 as kept) in the batch as a free noise check: `better` and `worse` read 0.11 to 0.17 on identical images, which is the noise floor for that question.
- Check that the measured number is the visual cause Jev named, by looking, before the round. An eye-window luma gain of +4 and +7 did not register as better (0.19 to 0.32) and both rounds were reverted: the number agreed with Jev only by accident, and the real cause was the eye pixels.

Validate each anchor before you score against it (data present, not an error page, a validity Noul; an empty capture read 0.50, real pages 0.96 to 0.98), and rate anchors with a Score in the same image form as candidates (provisional: real table crops 2.26 to 2.60, an empty capture 0.60). A ladder saturates at the top: to rank two good candidates, add a level above the reference or use a pairwise Compare in both orders.

When the owner's eye and Jev disagree, write the owner's note into the ladder level and re-score the baseline. See `references/iteration-with-jev.md`.
