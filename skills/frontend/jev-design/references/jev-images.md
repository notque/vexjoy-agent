# Review renders with Jev images

Send screenshots to Jev for phase 4 review instead of describing the page in text. Jev reads the picture and your question together. Shared API, limits, token cost, and routing: [images.md](../../../meta/building-with-jev/references/images.md). Image judgments steer review rounds. They never replace the `visual-review.md` checks or a measured number, and they are never the only gate.

## Capture

| Image | Size | Why |
|---|---|---|
| Desktop, light | 1280 x 800 viewport, scrolled to the area under review | About 2,700 tokens. |
| Mobile, light | 375 x 812 viewport | About 810 tokens. |
| Dark variant | Same sizes, only when a dark finding is open | Skip otherwise. |
| Reference | A rated screen in the same size and mode | Anchors "good" to something real. |

- Capture viewports or section crops. A full-page capture taller than 1,568 px is shrunk until text is unreadable.
- Scroll to the bottom first so scroll-reveal content has rendered.
- Keep every side 280-1568 px. `JevImage` fixes small deviations.

## Where each image goes

| Image | Place | Reason |
|---|---|---|
| Desktop and mobile candidate | `state`, once | All questions in the request share it, so it is billed once. |
| Reference screen | `state`, with the owner's rating in text beside it | Every trait question compares against it. |
| Example of a failure (clipped button, low contrast) | The `criteria` of the Noul it defines (`true.examples`) | Only that question pays for it. |

## Question set

One Noul per trait, plus a separate "anything worse" Noul. The measured numbers (control heights, contrast ratios, horizontal scroll) go in state as text next to the images.

```python
from jev_images import JevImage
import jev_transport

state = {
    "desktop": JevImage("desktop.png"),   # candidate, 1280 px
    "mobile": JevImage("mobile.png"),     # candidate, 375 px
    "reference": JevImage("ref.png"),     # owner-rated screen
    "reference_rating": "owner rates the reference 9 of 10",
    "measured": {"primary_buttons_in_footer": 1, "horizontal_scroll_375": False},
}
questions = {
    "primary_clear": {"type": "noul", "instructions": "Is the single primary action in `desktop` obvious within five seconds?"},
    "mobile_primary_visible": {"type": "noul", "instructions": "Is the primary action in `mobile` visible without scrolling?"},
    "hierarchy": {"type": "noul", "instructions": "Does `desktop` show a clear heading, section and body hierarchy like `reference`?"},
    "worse": {"type": "noul", "instructions": "Does `mobile` show clipped, overlapping, or unreadable elements?"},
    "gap": {"type": "score", "instructions": "How far is `desktop` from `reference`?", "criteria": LADDER},
}
answers = jev_transport.evaluate(state, questions, timeout=90)["answers"]
```

- `LADDER` is a Score ladder with `summary` and observable `signals` (sizes, alignment, what is visible).
- Budget: two candidate images plus a reference come to about 6,300 tokens. Read `usage.input_tokens` for the real number.
- Report each answer as a finding with a location and width, as `visual-review.md` requires. A Noul in 0.4-0.6 is not an answer: crop to the area in doubt and ask again.
