# Changelog Curation

Build the `## Unreleased` section of `CHANGELOG.md` by filtering recent commits down to what a user would notice. Curation summarizes; it never pastes commit subjects in.

## Workflow

1. **Find the baseline.** Use the version the user gives; otherwise take the newest tag with `git describe --tags --abbrev=0`.
2. **List candidate commits.** `git log <baseline>..HEAD --oneline --reverse`. Open the diff for any commit whose user impact the subject line does not make obvious.
3. **Filter and rank.** Keep only entries that pass the table below. Sort: breaking changes first, then new behavior, then fixes, then anything else.
4. **Write the bullets.** Put them under `## Unreleased` at the top of `CHANGELOG.md` (add the heading if absent). Match the file's existing bullet style, wrap identifiers in backticks, and cite PRs or issues as `#NNN` when you know them. Without PR numbers, leave the bullet bare — never paste commit hashes.
5. **Verify.** Render the markdown, check for duplicate bullets, trim wordy entries.

## What earns a bullet

| Keep | Drop |
|---|---|
| New capability a user can invoke | Refactor with identical behavior |
| Fix for a defect a user could hit | Spelling or comment-only change |
| Anything that breaks existing usage | Dependency bump with no visible effect |
| Changed defaults or output a user will see | Work added and reverted before release |

## Unreleased lifecycle

- Bullets accumulate under `## Unreleased` between releases.
- When tagging a release, move those bullets under the new version heading, then recreate an empty `## Unreleased` for the next cycle.
- Release notes lift these bullets unchanged, so write them release-ready.

## Format example

```markdown
## Unreleased
- Added `--strict` mode to `scripts/validate-references.py` that fails on missing frontmatter. #791
- Fixed systemd journal tailing in the service-health-check skill when the unit name contains a dash. #794
```
