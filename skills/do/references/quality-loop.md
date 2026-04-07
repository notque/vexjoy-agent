# Quality Loop Pipeline

Default pipeline for Medium+ code modification requests. Loaded by `/do` Phase 4 when the request involves code changes at Medium or Complex complexity.

## When This Applies

- Code modification requests at Medium+ complexity (implementation, bug fix, feature addition, refactoring)
- Does NOT apply to: Trivial (direct), Simple (quick/fast), reviews (parallel-code-review), research (research-pipeline), content creation (voice-writer)
- Force-route skills still take precedence (go-patterns, pr-workflow, feature-lifecycle, etc.)

## Pipeline Phases

### PHASE 1 — IMPLEMENT

Dispatch the selected domain agent with worktree isolation.

- Create feature branch in worktree
- Agent implements the change following its domain expertise
- Agent commits on the feature branch
- Inject worktree-agent skill rules into agent prompt
- Include "commit your changes on the branch" in agent prompt

**Gate:** Agent commits exist on feature branch. If agent failed to commit, halt pipeline and report which step to resume from.

### PHASE 2 — TEST

Run deterministic test suite. Language auto-detected from changed files.

Detection and commands:
- Go files changed: `go test ./...` (from repo root), `go vet ./...`
- TypeScript files changed: `tsc --noEmit`, then `npx vitest run` if vitest config exists
- Python files changed: `ruff check . --config pyproject.toml`, `ruff format --check . --config pyproject.toml`, `python -m pytest` if pytest config exists
- If Playwright config exists: `npx playwright test`
- If Makefile has `check` target: `make check`

Run ALL applicable test suites — a change may touch multiple languages.

Capture: exit codes, failure output, test counts.

**Gate:** Record results. If tests fail, continue to PHASE 3 anyway — review may find the root cause. Mark test failures as CRITICAL findings for PHASE 4.

### PHASE 3 — REVIEW

Dispatch 3 parallel review agents against the diff (feature branch vs main):

1. **Security reviewer** (reviewer-system) — injection vectors, auth issues, secret exposure, input validation
2. **Business logic reviewer** (reviewer-domain) — correctness, edge cases, domain rules, error handling
3. **Architecture reviewer** (reviewer-perspectives) — design patterns, coupling, API contracts, performance

Each reviewer produces findings as:
- CRITICAL: Must fix before merge
- IMPROVEMENT: Should fix, not blocking
- POSITIVE: Good patterns to reinforce

#### Intent Verification (mandatory)

After the 3 reviewers complete, dispatch one additional adversarial verifier agent (read-only) that compares the original user request against the actual diff. The verifier answers:

1. Does the diff accomplish what the user requested?
2. Are there aspects of the request that the implementation missed?
3. Are there changes in the diff that go beyond what was requested?

Any gap between request and implementation is a CRITICAL finding — because passing tests don't prove the code does what the user actually asked for. This implements the verifier pattern from PHILOSOPHY.md: "planner (read-only), executor (full access), verifier (read-only, adversarial intent)."

#### Live Validation (web projects only)

When the project has a dev server (detected by: `package.json` with `dev` or `start` script, Hugo config, or `docker-compose.yml` with web service), optionally spin up the dev server and use Playwright to visit changed routes/pages. This catches rendering regressions, broken layouts, and 404s that tests don't cover.

- Only run when Playwright is installed AND a dev server config exists
- Timeout: 60 seconds for server startup, 30 seconds per page
- If dev server fails to start, skip with a warning (not a CRITICAL)
- Uses the `e2e-testing` or `wordpress-live-validation` skill methodology

**Gate:** Collect all findings. If any CRITICAL findings (from PHASE 2 tests, PHASE 3 review, OR intent verification), proceed to PHASE 4. If no CRITICALs, skip to PHASE 6.

### PHASE 4 — FIX

For each CRITICAL finding, dispatch a fresh domain agent to fix it.

- Each fix is a separate commit with a message referencing the finding
- Use the same domain agent type as PHASE 1
- Fresh agent context — not the same agent that made the mistake — because the original agent has anchoring bias toward its own implementation
- Include the specific CRITICAL finding text in the agent prompt

**Gate:** All CRITICAL findings addressed with commits. Proceed to PHASE 5.

### PHASE 5 — RETEST

Run the same test suite as PHASE 2.

- If all tests pass AND no new issues: proceed to PHASE 6
- If tests fail: loop back to PHASE 4

**Loop counter:** Maximum 3 FIX→RETEST iterations. After 3 loops:
- Create PR anyway with remaining findings in the body
- Add "[needs-attention]" prefix to PR title
- Log the loop exhaustion to learning.db:

```bash
python3 ~/.claude/scripts/learning-db.py learn --skill do "quality-loop: max loops exhausted on [task summary]"
```

### PHASE 6 — PR

Push branch and create PR via pr-workflow skill.

PR body includes:
- Summary of the change
- Review findings (all CRITICAL, IMPROVEMENT, POSITIVE)
- Test results (pass/fail counts)
- Fix iterations (how many FIX→RETEST loops were needed)

Only fires when PHASE 5 passes clean (or max loops exhausted).

## Learning Integration

Each phase logs to learning.db:

```bash
python3 ~/.claude/scripts/learning-db.py learn --skill do "quality-loop PHASE_N: [outcome summary]"
```

## Worktree Isolation

- Phases 1–5 run in the same worktree
- Phase 6 (PR) runs pr-workflow from the main checkout using the feature branch
