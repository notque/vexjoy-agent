# Screenshots and Box in the browser harness

Use a screenshot when the page's meaning is in pixels, not DOM text: canvas or WebGL games, charts, icon-only buttons, images of text, or a layout whose visibility the DOM cannot report. Prefer the DOM table when labels, roles, and ids already identify the target. Shared API, limits, token cost, and routing: [images.md](../../../meta/building-with-jev/references/images.md). Image requests go to the direct API only (`TYPESAFE_API_KEY`); the Gateway cannot carry them. A screenshot judgment never replaces the harness's deterministic `--check-*` verifiers.

## Locate with Box

A Box question returns the target's edges as fractions of the image, so code converts them to a click point and `act` still works with coordinates, not model-written selectors.

| Step | Owner |
|---|---|
| Capture a viewport screenshot with the driver's `screenshot` command | Program |
| Ask `box` for the target, named in the instruction | Jev |
| Check `needs_escalation`, then read the center: x = (left + right) / 2 times viewport width | Program |
| Click, then re-observe and verify | Program |

```python
import jev_box

res = jev_box.locate("viewport.png", "the round 'next turn' button", context=dom_facts)   # 1280 x 800 viewport
if res.needs_escalation:
    ...                                # not confident: read the screenshot with a stronger model
elif res.status == "found":
    x, y = res.center                  # click point in viewport pixels
```

`locate` sends the Box with a presence Noul and a count Choice in one request, then refines or checks edges when needed. Box is experimental: confirm the target against the DOM first when it can answer, and re-observe after the click. See [images.md](../../../meta/building-with-jev/references/images.md) for `tile_grid`, `reference`, and the measured numbers.

| Situation | Call |
|---|---|
| Small control in a large page | `locate(shot, target)`: a low-confidence first box gets a refine crop from the original. |
| Several look-alike controls | Describe the one you want. On `several`, pass `tile_grid=(rows, cols)` or narrow the text. |
| Icon you have a picture of | `locate(shot, "the matching icon", reference="icon.png")`. |
| Fast click, box is enough | `locate(shot, target, edge_check=False)` saves a request. |

- `locate` reads the presence Noul for you. Hand-built Box questions need one beside them, because a Box always returns edges.
- Capture at the viewport size you convert with. The driver's device scale factor must match, or scale the point.
- If the click does not change the page, the verify phase catches it. Do not retry the same box more than once.

## Other uses

- **Verify a visual goal:** put before and after screenshots in `state`, ask `goal_met` as a Noul, and keep the text and URL checks as the veto.
- **Pick among look-alike controls:** a Choice whose `criteria` options each carry an example picture of the control.
- **Budget:** each screenshot costs about 1 token per 390 pixels. Send one per decision cycle, not one per question, by putting it in `state`.
