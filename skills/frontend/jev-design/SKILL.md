---
name: jev-design
description: Design React interfaces with the full shadcn/ui catalog. The agent writes a brief, Jev picks components and a style recipe from bounded catalogs, then the agent implements, renders, and reviews against concrete checks.
user-invocable: true
routing:
  triggers: ["jev design", "design with jev", "shadcn component plan", "choose shadcn components", "shadcn ui design", "component style recipe", "which shadcn component", "shadcn theme recipe", "pick shadcn components", "design a shadcn screen"]
  category: frontend
  pairs_with: [frontend, building-with-jev]
---

# Jev design

Each part of the work goes to whoever does it best:

| Phase | Who | Output |
|---|---|---|
| 1. Brief | the agent running the skill | `brief.json` |
| 2. Pick | Jev, through `scripts/plan.py` | a component per requirement, a style recipe, install commands, and CSS |
| 3. Compose and build | the agent, with the `frontend` skill | layout, hierarchy, copy, custom parts, and working code |
| 4. Review | the agent, with any screenshot tool | concrete findings, then fixes or a revised brief |

Jev only picks from lists: a component from the catalog's candidates and a recipe from its styles. It does not write layout, copy, or code. The agent does all open-ended work. Everything below is a default. Override any step when you have a stated reason, and write the reason in your summary.

## 1. Brief

Turn the user's request into `brief.json`. Read [references/brief-writing.md](references/brief-writing.md) for the procedure and a worked example.

```json
{"brief":"Support agents triage 200+ cases a day on desktop; calm, dense, keyboard-first.",
 "style_traits":["dense","calm","professional"],
 "requirements":[
  {"id":"results","role":"Compare, filter, and act on open cases","capabilities":["tabular-data","filter","row-actions"]},
  {"id":"details","role":"Inspect one case without leaving the list","capabilities":["overlay","details"]}
]}
```

- List capabilities, style traits, recipes, and limits with `--list-capabilities`. Use only listed names.
- Keep the brief to audience, task, and tone, 1,500 characters at most. Layout and copy notes stay with you for phase 3.
- Add `"primitives": "radix" | "base" | "aria"` when the project already uses one primitive set.
- Ask the user only when the surface type (landing page or app) or the audience is unknown. Otherwise decide, and record the assumption.

## 2. Pick

```bash
python3 skills/frontend/jev-design/scripts/plan.py \
  --input brief.json --output /tmp/design-plan.json \
  --receipt /tmp/jev-design-receipt.json --css /tmp/design-theme.css
```

The planner filters the catalog by capability in code: each requirement gets at most six candidates, tightest fit first. It packs requests to 3,500 tokens or fewer and refuses to send any request over 4,500. It sends through the selectable Jev transport (Vercel AI Gateway when configured), which retries 429, 503, and 529 with jittered backoff. It validates every answer and accepts a pick only when its fitness is 0.62 or higher. It never installs anything or edits code.

When the plan is selected, `implementation` holds:
- `install`: the exact `npx shadcn@latest add ...` command, plus `npm` for extra dependencies.
- `css`: paste-ready `@theme inline`, `:root`, and `.dark` blocks.
- `fonts`: the families to load.
- `layout_tokens`: radius, density classes, and shadow.
- `contrast`: every checked WCAG pair and its ratio.

When the plan abstains, the output still holds `baseline` and `candidates`:

| Reason | Do |
|---|---|
| `no_compatible_component` | Fix the listed capabilities, or split the requirement. |
| `low_fitness`, `none_or_out_of_catalog` | Rewrite that requirement's role as a verb plus an object, and rerun. If it abstains again, build that part as a custom component (phase 3). |
| `low_style_fitness` | Add or change `style_traits`, and rerun. If it abstains again, pick from `--list-capabilities` styles yourself. |
| `jev_unavailable`, `malformed_response` | Use the baseline, check it against each candidate's `use_when`, and say in your summary that Jev did not pick. |
| `request_too_large`, `invalid_request` | Shorten the brief or roles as the message says. |

Run the planner at most three times per screen.

## 3. Compose and build

Use the `frontend` skill. Follow this order:

1. Run `init` (if needed), `install`, and `npm` exactly as the plan gives them.
2. Paste `css` into the app's global stylesheet, replacing the existing theme variables. Load `fonts`.
3. Write the layout. Apply `layout_tokens` everywhere: the same control height, row height, gap, and section spacing on every part of the screen.
4. Write real copy: a headline that names the task, labels as nouns, buttons as verbs with objects ("Assign case", not "Submit").
5. When no catalog component fits, compose from catalog parts first (`item` + `dropdown-menu`, `card` + `chart`). Write new markup only when that fails, and reuse the recipe's variables.

## 4. Review

Build with [UI design judgment](../../shared-patterns/ui-design-judgment.md) and its [recipes](../../shared-patterns/ui-design-recipes.md). Render the screen and review it with [references/visual-review.md](references/visual-review.md). Use the harness's screenshot tool (Playwright or chrome-devtools MCP). Capture 375, 768, and 1280 px widths in light and dark mode.

- Report each finding as a fact with a location: "Primary button in the dialog footer is below the fold at 375 px", not "spacing feels off".
- Fix code-level findings in code. Put requirement-level findings (a wrong component, the wrong tone) back into `brief.json`, and rerun phase 2.
- Stop after three review rounds. Report what remains.
- If the harness has no screenshot tool, say so. Give the user the checklist from `visual-review.md` to check by eye, and do not claim visual quality.

## Rules for changing the planner

Apply the [Jev production rules](../../shared-patterns/jev-production-lessons.md) to any change in how requests are built or sent. They cover request size, retries by status, and budget checks. Keep the worst-case size test passing: too much context is the most common failure. Read [references/decision-card.md](references/decision-card.md) before you change the model, catalog, rubric, threshold, bounds, failure policy, or promotion status. `references/catalog-v1.json` is kept for reference only.
