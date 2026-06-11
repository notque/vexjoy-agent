# Changelog Curation

Curate user-facing changes since the last release into the `## Unreleased` section of `CHANGELOG.md`. A changelog answers "what changed for the user", so curation filters commits — it copies none of them verbatim.

## Workflow

1. **Pick the baseline.** Use the version the user names; otherwise the latest tag:
   ```bash
   git describe --tags --abbrev=0
   ```
2. **Collect commits since baseline.**
   ```bash
   git log <tag>..HEAD --oneline --reverse
   ```
   Skim diffs when a one-liner leaves user impact unclear.
3. **Curate entries** using the include/exclude table below; order by impact: breaking → features → fixes → misc.
4. **Edit `CHANGELOG.md`.** Ensure `## Unreleased` exists at the top (create it if missing), append bullets in the file's existing style, code in backticks. Add PR/issue numbers when known (`#123`); when working commit-only, keep the bullet concise and skip raw hashes.
5. **Sanity check.** Markdown renders, entries unique, wording concise.

## Include / Exclude

| Include | Exclude |
|---|---|
| Shipped features | Internal refactors |
| Bug fixes users can observe | Typo-only edits |
| Breaking changes | Dependency bumps without user impact |
| Notable UX or behavior tweaks | Features added then removed in the same window |

## Unreleased lifecycle

- `## Unreleased` collects entries between releases.
- At release time, move the curated bullets under the new version heading; keep the Unreleased block separate from versioned sections.
- After a release ships, open a fresh empty `## Unreleased` section so the next patch cycle has a home.
- The release body reuses the changelog bullets verbatim — write them once, well.

## Format example

```markdown
## Unreleased
- Added configurable status probe refresh interval. #123
- Fixed menu bar icon dimming on sleep/wake. #128
```
