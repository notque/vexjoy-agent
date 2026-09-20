---
name: frontend-slides
promoted_to: frontend
description: "Build, convert, or repair self-contained browser HTML slide decks using this repository's layouts, controllers, and validators. Not for creating a new PowerPoint file."
user-invocable: false
agent: typescript-frontend-engineer
routing:
  triggers: ["HTML slides", "browser presentation", "web deck", "convert PPTX to HTML", "kiosk presentation"]
  category: frontend
---

# Frontend Slides

This skill produces browser HTML. If “slides” does not identify HTML versus `.pptx`, ask which format. An existing PPTX may be converted to HTML; creating a new `.pptx` belongs elsewhere.

## Build contract

Resolve `${CLAUDE_SKILL_DIR}` to this skill directory.

1. New deck: assemble style, used layouts, and controllers. Existing deck: preserve its visual system unless redesign was requested. PPTX input: read `references/pptx-conversion.md`.
2. Use one `.slide` section per slide inside `#deck`. Keep the output self-contained.
3. Use repository assemblers rather than copying snippets:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/assemble-styles.py --list
python3 ${CLAUDE_SKILL_DIR}/scripts/assemble-styles.py --mood "MOTION"
python3 ${CLAUDE_SKILL_DIR}/scripts/assemble-layouts.py --layouts title,content,image
python3 ${CLAUDE_SKILL_DIR}/scripts/assemble-controllers.py --controllers slide-controller,indicator,speaker-notes
```

`base.css` is mandatory. Include only layouts/controllers actually used. Available names are defined by filenames under `templates/`; do not preserve a prose mirror of that inventory.

4. Read `references/runtime-contracts.md` before changing navigation, animation, notes, timers, or overflow behavior.
5. Validate and repair until clean:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/validate-slides.py deck.html
```

Also open at presentation dimensions when browser rendering is available. The validator catches structural and static overflow risks; it does not prove visual quality.

## Content decisions

Use the source material's hierarchy. Split crowded slides instead of shrinking body copy. A slide needs one communicative job; this is a decision rule, not a fixed element count. Never fabricate data, quotes, or screenshots to complete a layout.

Deliver the absolute HTML path and disclose skipped rendering or unavailable PPTX assets.
