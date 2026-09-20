---
name: content
description: "Operate this repository's editorial calendar, publishing wrappers, Bluesky reader, and Reddit moderation tooling. For prose/style use writing."
user-invocable: true
allowed-tools: [Read, Write, Edit, Bash, Grep, Glob, WebFetch]
routing:
  force_route: false
  not_for: "prose voice and style (use writing), code documentation (use docs-sync-checker)"
  triggers: ["editorial calendar", "content pipeline", "wordpress draft", "post to X", "Bluesky feed", "moderate Reddit", "modqueue", "audit links", "audit images", "batch edit posts"]
  category: content
  pairs_with: [writing, workflow]
---

# Content operations

Use normal model judgment for strategy, SEO, outlines, campaigns, and copy. This
skill supplies only local state and execution contracts.

## Editorial calendar

The source of truth is `content-calendar.md`; read it immediately before every
write and re-read it afterward. Its ordered stages are `Ideas -> Outlined ->
Drafted -> Editing -> Ready -> Published`, followed by month-keyed `Historical`
sections. Moves are forward-only, record an ISO `YYYY-MM-DD` transition date,
and require checked items in `Ready`/`Published`. Scheduling applies only to
`Ready` items and cannot use a past date. Archive published entries older than
the current month. Match requested titles case-insensitively; ask when a partial
match is ambiguous. Never reconstruct the file from remembered state.

## Mutating external systems

Show the exact mutation and obtain explicit confirmation immediately before a
social post, moderation action, WordPress publish, or destructive batch edit.
Draft creation and read-only queries do not imply permission to publish.

Load [references/local-operations.md](references/local-operations.md) for the
repository's wrapper commands, credentials, response shapes, and moderation
policy. Prefer those wrappers over raw API calls because they preserve local
conversion, authentication, and audit behavior.

## Local scripts

- `skills/content/content/scripts/publish/link_scanner.py`: link graph and external checks.
- `skills/content/content/scripts/publish/pagespeed.py`: PageSpeed capture.
- `skills/content/content/scripts/publish/wordpress-{upload,media-upload,edit-post}.py`: WordPress.
- `skills/content/content/scripts/reddit-moderate/reddit-mod.py`: Reddit reads and actions.

Inspect each script's `--help` before use; its live interface outranks prose.
