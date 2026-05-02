---
name: plant-seed
description: "Capture forward-looking idea as a seed for future feature design."
user-invocable: false
argument-hint: "<idea description>"
command: /plant-seed
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - plant seed
    - save idea for later
    - defer this idea
    - remember this for when
    - seed this
    - plant-seed
  pairs_with:
    - feature-lifecycle
  complexity: Simple
  category: process
---

# Plant Seed Skill

Capture forward-looking ideas with trigger conditions so they resurface at the right time. Seeds carry WHY (rationale) and WHEN (trigger). Stored in `.seeds/` (gitignored), surfaced automatically during feature-lifecycle design phase.

For deferred ideas only. If work should happen now, suggest a task or issue instead.

---

## Instructions

### Phase 1: CAPTURE

**Goal**: Gather idea, trigger condition, scope, and rationale.

**Step 1: Understand the idea**

Extract:
- **What** (action): Specific thing to do when triggered
- **Why** (rationale): The insight motivating this idea
- **When** (trigger): Human-readable condition for when this becomes relevant

If any missing, ask:
- Missing **trigger**: "When should this resurface? e.g., 'when we add user accounts', 'when the API exceeds 10 endpoints'"
- Missing **scope**: "How big? Small (< 1hr), Medium (1-4hr), Large (4+hr)?"
- Missing **rationale**: "Why does this matter? What's the insight?"

**Step 2: Generate seed ID**

Format: `seed-YYYY-MM-DD-slug` (today's date, 3-5 word kebab-case slug). Duplicate same-day slugs get `-2`, `-3`.

**Step 3: Discover breadcrumbs**

Grep codebase with 2-3 key terms. Collect up to 10 related file paths. These preserve code references from capture time for re-orientation when the seed surfaces later. Empty breadcrumbs are acceptable.

**Gate**: All required fields captured (action, trigger, scope, rationale). Breadcrumbs discovered.

### Phase 2: CONFIRM

Present the seed for approval:

```
## Seed: seed-YYYY-MM-DD-slug [Scope]

Trigger: "human-readable trigger condition"
Rationale: Why this matters...
Action: What to do when triggered...
Breadcrumbs: file1.go, file2.py, ...

Plant this seed? [yes/no/edit]
```

- **yes**: Proceed to Write
- **no**: Discard
- **edit**: Update fields, re-confirm

**Gate**: User approved.

### Phase 3: WRITE

Persist seed to `.seeds/index.json` (gitignored -- seeds are personal, not shared via version control).

```bash
mkdir -p .seeds/archived
```

Read or initialize `.seeds/index.json`, append seed:

```json
{
  "id": "seed-YYYY-MM-DD-slug",
  "status": "dormant",
  "planted": "YYYY-MM-DD",
  "trigger": "human-readable trigger condition",
  "scope": "Small|Medium|Large",
  "rationale": "Why this matters...",
  "action": "What to do when triggered...",
  "breadcrumbs": ["path/to/file1.go", "path/to/file2.py"]
}
```

Confirm to user:

```
Seed planted: seed-YYYY-MM-DD-slug [Scope]
Trigger: "condition"
Status: dormant

Surfaces during /feature-lifecycle design phase. Review with: /plant-seed "list seeds"
```

**Gate**: Seed persisted. Workflow complete.

---

### Seed Review Mode

On "list seeds" / "review seeds" / "show my seeds":

1. Read `.seeds/index.json`
2. Display dormant seeds as table (ID, Scope, Trigger, Planted)
3. Offer: "Want to activate, dismiss, or edit any seed?"

### Seed Lifecycle Actions

- **Harvest**: Archive to `.seeds/archived/{seed-id}.json`, status `harvested`. Work incorporated.
- **Dismiss**: Archive to `.seeds/archived/{seed-id}.json`, status `dismissed`. No longer relevant.
- **Activate**: Change status to `active` in index.json. Trigger met, work not started.

To archive: remove from `index.json`, write standalone file to `.seeds/archived/`.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| `.seeds/` missing | First seed | `mkdir -p .seeds/archived` |
| `index.json` malformed | Corruption | Back up to `.bak`, reinitialize, warn user |
| Duplicate seed ID | Same day + slug | Append `-2`, `-3` |
| No breadcrumbs | Forward-looking, no code yet | Plant with empty breadcrumbs |
| Immediate work described | Not deferred | Suggest task/issue instead |
| Vague trigger ("someday") | Cannot match in feature-lifecycle | Ask for specific, observable condition |
| Missing rationale | Loses value when surfaced later | Capture the specific insight |

---

## References

- [Feature Lifecycle](../feature-lifecycle/SKILL.md) - Seeds surfaced during design phase (Phase 0)
