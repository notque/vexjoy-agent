# Brief writing

A good brief makes Jev's picks easy. Each requirement names one job the screen does, and its capabilities narrow the catalog to a few real options.

## Procedure

1. **Classify the surface.** Is it a landing page (sells or explains) or an app screen (users work in it)? Put the answer in the first sentence of `brief`.
2. **Name the audience and the task.** Who uses it, how often, and on what device: "Support agents triage 200+ cases a day on desktop."
3. **List the jobs.** Walk the screen top to bottom. Each thing a user reads, compares, enters, or triggers is a candidate requirement. Merge jobs that one component clearly does. Keep eight at most. Leave pure layout (header, grid, footer) out: you compose it in phase 3.
4. **Write each role as a verb plus an object:** "Filter open cases by status", not "Filters".
5. **Pick one to three capabilities per requirement** from `--list-capabilities`. Pick only the capabilities the job needs. Every extra one removes candidates. If the receipt shows `truncated` for a requirement, add one more specific capability.
6. **Pick two to four style traits** that describe tone and density: `dense`, `calm`, `playful`, `premium`.
7. **Set `primitives`** only when the project already uses Radix, Base UI, or React Aria. Conversation components (`bubble`, `message`, `marker`, `message-scroller`, `attachment`) exist only in Aria.

## Mapping common asks to capabilities

| The user says | Capabilities |
|---|---|
| "a table I can sort and filter" | `tabular-data`, `sort`, `filter` |
| "edit details in a side panel" | `overlay`, `secondary-task` |
| "are you sure?" before delete | `confirmation`, `modal` |
| "pick a country" (long list) | `single-choice`, `large-option-set` |
| "toggle notifications" | `binary-toggle` |
| "success message after save" | `notification` |
| "nothing here yet" | `empty-state` |
| "chat with the assistant" | `conversation`, `scroll-region` |
| "app navigation" | `navigation`, `app-shell` |
| "sign-up wizard" | `multi-step` |
| "show a trend" | `visualization` |

## Worked example

User: "Build a settings page for our team plan: members, billing, notifications. Make it look trustworthy."

```json
{"brief":"App screen. Team admins manage a paid workspace a few times a month on desktop and mobile; trustworthy, clear.",
 "style_traits":["trustworthy","professional","clear"],
 "requirements":[
  {"id":"sections","role":"Switch between members, billing, and notifications","capabilities":["section-switching","peer-views"]},
  {"id":"members","role":"Review members and change one member's role","capabilities":["list-items","actions"]},
  {"id":"remove","role":"Confirm removing a member","capabilities":["confirmation","modal"]},
  {"id":"notify","role":"Turn each email notification on or off","capabilities":["binary-toggle"]},
  {"id":"saved","role":"Confirm a change was saved","capabilities":["notification"]}
]}
```

Kept for phase 3, not the brief: page title "Team settings", billing shown as a summary card, the destructive action in red at the end of each row.

## Ambiguity

- Unknown surface type or audience: ask one question that names both options.
- Unknown device: assume both mobile and desktop, and say so.
- Unknown brand: let the recipe decide, and tell the user which one was picked and why it can change.
