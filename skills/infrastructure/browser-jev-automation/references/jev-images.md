# Screenshots and Box in the browser harness

Use a screenshot when the page's meaning is in pixels, not DOM text: canvas or WebGL games, charts, icon-only buttons, images of text, or a layout whose visibility the DOM cannot report. Prefer the DOM table when labels, roles, and ids already identify the target. Shared API, limits, token cost, and routing: [images.md](../../../meta/building-with-jev/references/images.md). Image requests go to the direct API only (`TYPESAFE_API_KEY`); the Gateway cannot carry them. A screenshot judgment never replaces the harness's deterministic `--check-*` verifiers.

## Locate with Box

A Box question returns the target's edges as fractions of the image, so code converts them to a click point and `act` still works with coordinates, not model-written selectors.

| Step | Owner |
|---|---|
| Capture a viewport screenshot with the driver's `screenshot` command | Program |
| Ask `box` for the target, named in the instruction | Jev |
| Check `confidence`, then compute the center: x = (left + right) / 2 times viewport width | Program |
| Click, then re-observe and verify | Program |

```python
from jev_images import JevImage
import jev_transport

shot = JevImage("viewport.png")    # 1280 x 800 viewport, about 2,700 tokens
questions = {
    "target": {"type": "box", "instructions": "the round 'next turn' button in `page`"},
    "present": {"type": "noul", "instructions": "Is the 'next turn' button visible in `page`?"},
}
a = jev_transport.evaluate({"page": shot}, questions, timeout=90)["answers"]
if a["present"]["noul"] > 0.7 and a["target"]["confidence"] > 0.7:
    box = a["target"]["box"]       # top, bottom, left, right: 0 to 1
    x, y = (box["left"] + box["right"]) / 2 * 1280, (box["top"] + box["bottom"]) / 2 * 800
```

- Ask the `present` Noul beside every Box. A Box always returns edges, even when the target is absent.
- Capture at the viewport size you convert with. The driver's device scale factor must match, or scale the point.
- If the click does not change the page, the verify phase catches it. Do not retry the same box more than once.

## Other uses

- **Verify a visual goal:** put before and after screenshots in `state`, ask `goal_met` as a Noul, and keep the text and URL checks as the veto.
- **Pick among look-alike controls:** a Choice whose `criteria` options each carry an example picture of the control.
- **Budget:** each screenshot costs about 1 token per 390 pixels. Send one per decision cycle, not one per question, by putting it in `state`.
