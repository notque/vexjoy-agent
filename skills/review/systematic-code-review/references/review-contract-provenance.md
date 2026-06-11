# Review Contract and Provenance

Deep-review method for bug fixes and regressions: prove the root cause or name the missing evidence, trace where the bug came from with bounded git history, and judge whether the fix is the best one after reading adjacent code. Load when reviewing a bug fix, regression, or any PR whose verdict depends on "why did this break."

## Review Contract

Answer every line explicitly. "Unknown" with named missing evidence beats a guess.

| Question | Required answer |
|---|---|
| What bug or behavior is being fixed? | One or two sentences. |
| Is the root cause identified? | Yes: code path (`file:line`) plus why. No: name the missing evidence (repro, logs, upstream docs). |
| For regressions: what introduced it? | Commit/PR provenance via bounded history (below), or `unknown` — stated, not guessed. |
| Is this the best fix? | Judged only after reading adjacent code (below). |
| Would a larger refactor help? | Yes/no with the specific shape, or why the refactor widens risk without improving the bug class. |
| What proof exists? | Inventory: tests, live repro, CI checks, docs, dependency source, shipped behavior. |
| What stays risky? | Residual risk and test gaps, named. |

## Provenance Method

For bug and regression reviews, produce a compact `Provenance:` line when traceable. Bound the search — recent history first, widen only on a miss.

```bash
# Who introduced/removed the exact string:
git log -S '<exact code string>' --oneline --all -- <path>
# Who touched matching code by regex:
git log -G '<regex>' --oneline --all -- <path>
# Line-level authorship at the failing site:
git blame -L <start>,<end> <path>
```

Rules:

- Phrase the relation precisely: `introduced by`, `made visible by` (latent bug exposed by a later change), or `carried forward by` (copied/refactored from an older defect).
- Separate the commit author, the merger, and the current PR author when they differ.
- State confidence: `clear` (blame lands on the defect line), `likely` (history points there but the path is indirect), or `unknown`.
- For features, docs, refactors, or untraceable bugs, write `N/A` or name what evidence is missing.
- Link the introducing PR/issue when `git log` shows it; cite tests added alongside it as supporting evidence.

## Best Fix After Reading Adjacent Code

A fix verdict requires reading past the first touched file. Follow the real path:

- entrypoint → validation/parsing → dispatch → owner module → shared helper → persistence/network boundary
- config/schema/docs → runtime usage → migration/repair path
- tests around the touched surface plus adjacent regression tests

When behavior depends on a dependency, read its docs, types, or source before assuming. Prefer current source and executable proof over issue comments; treat stale comments and old CI as hints until rechecked.

Quality bar — a good fix usually:

- lives at the ownership boundary where the bug belongs
- preserves backward-compatible behavior unless retiring it is the point
- adds a regression test at the smallest meaningful seam
- keeps semantic sentinels, broad special cases, and hidden migrations out of generic code
- updates docs/changelog when user-visible behavior changes

Call out symptom-level fixes. Recommend a slightly larger refactor when it makes the invariant obvious and shrinks the bug class; say so when it only widens risk.

## Output Block

Add this block to the Phase 4 DOCUMENT output when this reference applies:

```text
Bug: <one or two sentences>
Cause: <code path file:line + confidence, or missing evidence named>
Provenance: <introduced / made visible / carried forward by commit/PR/date — confidence clear|likely|unknown, or N/A>
Best fix: <what should change and why, judged after adjacent-code reading>
Refactor: <yes/no, specific shape>
Proof: <tests | live repro | CI | source | dependency docs — what was actually checked>
Risk: <remaining uncertainty and test gaps>
```

Keep it short; carry every line. A blank line is a skipped decision.
