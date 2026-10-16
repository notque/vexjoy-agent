# Grill a visual goal with images

When the plan or artifact has a visual goal ("looks like the reference", "reads clearly on mobile", "feels like a real broadcast"), put pictures in the state. A description of the output lets Jev judge the description, not the output. Shared API, limits, token cost, and routing: [images.md](../../building-with-jev/references/images.md). Image judgments are for steering and review. They are never the only gate.

## Require these in the state

| Item | Form |
|---|---|
| Rendered candidate | `JevImage` of the real output at the size a user sees |
| Reference | `JevImage` of the target, with the owner's rating in text beside it |
| Measured numbers | Text: widths, ratios, timings |
| Owner's words | Quoted verbatim |

If the artifact has no rendered candidate or no reference, that is the first finding. Report it as a gap and stop asking visual questions until both exist.

## Use `jev_transport`, not `grill-jev.py`

`scripts/grill-jev.py` evaluates a text battery. For a visual battery, write the questions yourself and call `jev_transport.evaluate`. Keep the images in `state` so the request bills them once.

```python
from jev_images import JevImage
import jev_transport

state = {"candidate": JevImage("cand.png"), "reference": JevImage("ref.png"),
         "reference_rating": "owner: reference is 9 of 10", "measured": {"arm_px": 18}}
questions = {
    "like_reference": {"type": "score", "instructions": "How close is `candidate` to `reference`?", "criteria": LADDER},
    "readable": {"type": "noul", "instructions": "Can every label in `candidate` be read at this size?"},
    "worse": {"type": "noul", "instructions": "Does `candidate` show anything broken, clipped, or missing that `reference` has?"},
}
answers = jev_transport.evaluate(state, questions, timeout=90)["answers"]
```

- One trait per question, with a separate "anything worse" Noul.
- A Noul in 0.4-0.6 means the question or the picture is wrong. Crop to the area in doubt and ask again.
- Two images at 800 x 600 cost about 2,600 tokens. Stay within the per-request budget in `jev-production-lessons.md`.
