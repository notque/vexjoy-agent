---
name: frontend
description: "Build or assess coded frontend experiences, self-contained HTML artifacts, and Three.js scenes. Use for implementation-focused UI work; route browser slide decks and specialized card shaders to their dedicated skills."
user-invocable: true
routing:
  not_for: "game mechanics (use game-dev), backend work, or brand/logo design without code"
  triggers: ["frontend design", "HTML artifact", "self-contained HTML", "Three.js", "WebGL", "WebGPU", "react three fiber", "R3F", "GLTF", "card effects", "design critique"]
  category: frontend
  pairs_with: [typescript-frontend-engineer, ui-frontend-engineer, game-dev]
---

# Frontend

Choose one path. Load only the named local reference; rely on normal frontend knowledge for ordinary implementation, UX, accessibility, and design-system work.

## Distinctive coded UI

Use real product content and pick a macrostructure before styling. Read:

- `references/distinctive-frontend-design-refs/macrostructure-catalog.md` for the chosen `macro:*` entry only.
- `font-catalog.json` and `color-inspirations.json` when the project lacks brand inputs.
- `roll-text.md` only when that exact slot-roll behavior is requested.

Do not invent absent product screenshots, metrics, testimonials, or controls. Prefer an honest labeled placeholder over plausible fake UI. Treat the catalogs as prompts, not mandatory taste: existing brand and repository conventions win.

When this repo's anti-cliche contract applies, run:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts-distinctive-frontend-design/validate_design.py \
  --fonts "Display,Body" --palette palette.json --project NAME \
  --macrostructure macro:ID --animation --background --emitted-css generated.html
```

Fix reported failures and rerun. Score 80 is the local acceptance floor. The validator, not prose checklists, defines the current rules.

Specialized browser decks belong to `frontend-slides`; specialized holographic/card shaders belong to `webgl-card-effects`.

## Self-contained HTML artifact

Use the scripts as the workflow contract:

1. Check saved templates with `scripts-html-artifact/fill-template.py --list`; if one matches, fill its slots without restyling it.
2. Detect shape with `detect-shape.py --request "..."`. Low confidence becomes `report`.
3. Assemble with `assemble-template.py --shape SHAPE --title "..." --components ...`, then fill the result. Keep CSS and JS inline; no CDN/framework dependency; maximum 500 KB.
4. Validate with `validate-artifact.py FILE`; fix and rerun.
5. Export only when requested. Read `references/html-artifact-refs/export-contracts.md` first.

Available shapes are `spec`, `code-review`, `prototype`, `report`, `editor`, `data-viz`, `diagram`, and `deck`. Templates and components under `templates/` are the source of truth for markup and class names.

## Three.js

First preserve the repository's existing paradigm. Do not mix imperative Three.js and R3F lifecycle patterns.

- R3F: animation belongs in `useFrame`, never a second `requestAnimationFrame` loop.
- Imperative/WebGPU: prefer `renderer.setAnimationLoop()`.
- Never allocate geometry or materials inside the frame loop; dispose replaced resources.
- Cap DPR (`Math.min(devicePixelRatio, 2)`) unless the product has a measured reason not to.

Read `references/threejs-builder-refs/runtime-contracts.md` for GLTF cloning, camera-control ownership, bloom, WebGPU/TSL, and failure mappings. These are the non-obvious constraints retained from the former framework manuals.

## Delivery

Run the repository's tests/build plus the mode-specific validator. Report the artifact path and any intentional fallback or unsupported export; do not claim visual verification unless it was rendered and inspected.
