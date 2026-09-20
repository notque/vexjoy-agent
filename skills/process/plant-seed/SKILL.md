---
name: plant-seed
description: "Capture a deferred idea with an observable trigger in the repository-local personal seed store."
user-invocable: false
argument-hint: "<idea description>"
command: /plant-seed
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit]
routing:
  triggers: [plant seed, save idea for later, defer this idea, remember this for when, seed this, plant-seed]
  pairs_with: [workflow]
  complexity: Simple
  category: process
---

# Plant Seed

Use seeds only for deferred work. Immediate work belongs in the current task or an issue.

## Capture contract

Before writing, establish:

- `action`: what to do;
- `trigger`: a specific observable condition, not “someday”;
- `scope`: `Small`, `Medium`, or `Large`;
- `rationale`: the insight that will still explain the idea later;
- `breadcrumbs`: up to 10 related repository paths found now with 2–3 search terms; empty is valid.

ID: `seed-YYYY-MM-DD-<3-5-word-kebab-slug>`. Append `-2`, `-3`, etc. on collision. Show the complete record and obtain approval before persisting it.

## Storage contract

Seeds are personal and untracked. Store them in gitignored `.seeds/`, never in the shared repository. `.seeds/index.json` has this shape:

```json
{"seeds":[{"id":"seed-YYYY-MM-DD-slug","status":"dormant","planted":"YYYY-MM-DD","trigger":"observable condition","scope":"Small|Medium|Large","rationale":"why","action":"what","breadcrumbs":["path"]}]}
```

Create `.seeds/archived/` when needed. Preserve every existing record when updating the index. If JSON is malformed, make `index.json.bak`, warn the user, and do not silently discard records.

## Review and lifecycle

For list/review requests, show dormant seeds with ID, scope, trigger, and planted date.

- `activate`: change the indexed seed to `active` when its trigger has fired.
- `harvest` / `dismiss`: remove it from the index, set the corresponding status, and write `.seeds/archived/<id>.json`.

Do not archive, activate, or edit a seed without the requested lifecycle action.
