# INDEX.json Conflict Resolution on Sequenced PRs

When two branches both regenerate `agents/INDEX.json` or `skills/INDEX.json`, the second PR to land hits a merge conflict. Naïve resolution corrupts the source-of-truth.

## The wrong move

Popping a stale stash on the second PR — it clobbers entries the first PR added.

Accepting either side of the conflict blindly — one side is always stale relative to the current `SKILL.md` / `agents/*.md` sources.

## The right sequence

1. `git rebase main` — take main's `INDEX.json` as the base (has PR #1's entries).
2. `git checkout stash@{0} -- <non-INDEX paths>` — apply your non-INDEX changes individually. Never restore the whole stash.
3. Regenerate `INDEX.json` from source of truth on the rebased branch:
   - Skills: `python3 scripts/generate-skill-index.py`
   - Agents: `python3 scripts/generate-agent-index.py`
4. Verify the regen contains BOTH PR #1's entries and your branch's entries.
5. Force-push with `--force-with-lease` — needs a prior `git fetch` on the contributor's branch to establish the lease ref, otherwise the lease check fails with an opaque error.

## Why this shape

`INDEX.json` is a generated artifact, not source. Merging it as text produces plausible-looking output that diverges from source. Regenerating after rebase is the only way to guarantee consistency with the actual `SKILL.md` / `*.md` files on the branch.

## Provenance

Pattern confirmed working on PRs #670 + #671 (2026-05-26). Rediscovered in gotcha `skill:pr-workflow/7fad9101` and `skill:do/f0f387436dc9`.
