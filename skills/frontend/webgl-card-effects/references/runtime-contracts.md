# WebGL card runtime contract

The effect family targets WebGL2 / GLSL 300 ES and a 5:7 card surface (canonical 400 × 560).

## Shared ownership

Browsers commonly enforce a small WebGL-context budget. A card grid must not create one WebGL context per card. Use one module-owned WebGL2 context rendering to an offscreen canvas, then blit into each card's 2D canvas. Register per-card state in a keyed map and run one RAF loop only while visible entries exist.

Feature-detect WebGL2 once and fail to CSS without repeated console noise. On context loss, stop rendering and retain the CSS surface; restoration may rebuild GPU programs and buffers. React cleanup must unregister the card, disconnect its observer, remove pointer handlers, and stop the shared RAF when the registry becomes empty.

## Uniform contract

All effects use bounded application values:

| Uniform | Meaning |
|---|---|
| `u_time` | elapsed seconds, wrapped before float precision becomes visible |
| `u_rarity` | common 0, uncommon 0.25, rare 0.5, legendary 1 |
| `u_hover` | eased 0–1, not a boolean jump |
| `u_mouse` | card-local 0–1; reset to (0.5, 0.5) at rest |
| `u_resolution` | actual drawing-buffer pixels |
| `u_upgraded` | 0 or 1 |

GLSL compilers remove unused uniforms. A null `getUniformLocation` can therefore mean optimization, not link failure; either use the uniform or stop setting it. Compile and link logs must be surfaced before falling back.

Aspect-correct isotropic operations with the real resolution (or the canonical 5:7 ratio); do not distort circles/noise by treating card UVs as square. Cap rendering DPR and reduce octave count/frame rate for mobile rather than spawning lower-quality contexts.

## Compositing and motion

The foil shader emits transparent dark regions and expects screen-like compositing over card art. Keep base opacity restrained; full opaque output hides the art. Mouse/tilt should drive hue more than time—fast full-spectrum cycling reads as an animated overlay, not physical foil. Reduced-motion mode freezes or replaces ambient animation but may retain direct pointer response if policy allows.

## Failure map

| Symptom | First check |
|---|---|
| `useProgram: program not valid` | compile/link logs and GLSL 300 syntax |
| canvas exists but is invisible | size, viewport, alpha/composite layer, non-null program |
| contexts are evicted | accidental per-card `getContext('webgl2')` |
| effect stretches on resize | drawing-buffer size and `u_resolution` |
| uniform appears ignored | compiler stripped it or wrong program is bound |
| React card leaks work | missing unregister/observer/listener cleanup |
