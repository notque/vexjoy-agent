---
name: jev-design
description: Plan React interfaces with shadcn components and style recipes selected from bounded catalogs by live Jev. Use before frontend implementation; it does not install components or visually inspect renders.
user-invocable: true
routing:
  triggers: ["jev design", "design with jev", "shadcn component plan", "choose shadcn components", "shadcn ui design", "component style recipe"]
  category: frontend
  pairs_with: [frontend, building-with-jev]
---

# Jev design

Create `brief.json` with a screen brief and one or more named requirements:

```json
{"brief":"Dense, calm support workspace","requirements":[
  {"id":"results","role":"Show cases","capabilities":["tabular-data","filter","row-actions"]},
  {"id":"details","role":"Inspect a case","capabilities":["overlay","details"]}
]}
```

Then create an advisory component and style plan:

```bash
python3 skills/frontend/jev-design/scripts/plan.py \
  --input brief.json --output /tmp/design-plan.json \
  --receipt /tmp/jev-design-receipt.json
```

List capabilities with `--list-capabilities`. The planner filters its versioned
catalog before calling pinned Jev, validates the response, and abstains on weak,
malformed, unavailable, or out-of-catalog results. It never installs components
or edits application code.

Revise the brief with concrete feedback and compare complete style recipes;
stop after three attempts. Use `frontend` to implement a returned plan, then
render and inspect behavior, accessibility, and appearance. Jev's text judgment
is not visual verification.

Read `references/decision-card.md` when changing its model, catalog, rubric,
threshold, failure policy, or promotion status.
