# Browser deck runtime contracts

The templates under `templates/controllers/` are executable source of truth. Preserve these behaviors when modifying or replacing them.

## Navigation

- Guard `go()` against re-entry for the full smooth-scroll transition.
- Debounce wheel bursts separately; a trackpad gesture emits many events and the navigation guard alone does not collapse the burst.
- Clamp indices. Keyboard support includes arrows plus Home/End; do not hijack keystrokes originating in editable controls.
- Touch/wheel listeners should remain passive unless cancellation is actually required.
- Keep the visible indicator synchronized and `aria-live="polite"`.

## Reveal and layout

Do not hide observed slides with `display:none`: they leave the layout/accessibility tree and IntersectionObserver cannot reveal them. Use opacity/transform, and make reduced-motion slides immediately visible with no transition.

A static overflow validator cannot see every font/rendering difference. Test at the target viewport. Split content before shrinking it. Code and tables need explicit overflow behavior; presentation controls must remain outside printable slide content.

## Optional controllers

- Only one module owns slide navigation.
- Speaker notes must not leak into the projected/printed surface.
- Countdown completion must not implicitly advance a slide unless requested.
- Clean up intervals, observers, and global listeners when embedding a deck in a longer-lived shell.

## Diagnostics

| Symptom | Likely cause |
|---|---|
| one wheel swipe skips slides | missing debounce or premature guard release |
| reveal never fires | `display:none` or wrong observed node |
| indicator drifts | index changed outside the controller |
| print/PDF includes controls | missing print rule |
| first/last slide scrolls past deck | unclamped index or browser-native scroll competing |
