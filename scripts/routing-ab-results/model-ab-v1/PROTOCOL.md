# model-ab-v1 — Blind A/B: fable solo-build vs fable-coordinate / opus-build

One real task, two execution arms, blind fable graders, one PR merges on merit.
Design only until the orchestrator executes this checklist. Pre-register: freeze
this file BEFORE step 1; any edit after a dispatch invalidates the run
(precedent: router-ab-runbook gates rule).

**Arms.**
- **Arm A**: one fable agent authors its workflow, then implements end-to-end.
- **Arm B**: fable authors the workflow and reviews; opus implements and fixes
  review findings; fable approves.

**Blindness gate (hard).** Nothing in commits, branch names, PR title/body, code
comments, or file paths may reveal an experiment or which arm made what. All
experiment artifacts live in `/tmp/model-ab-v1/` (local, non-served, non-repo)
until verdict, then publish to `scripts/routing-ab-results/model-ab-v1/`
(precedent: `self-route-v1`). Neither arm is told it is compared. Graders see
anonymized X/Y packets only.

---

## 1. Task selection

**Picked: fix the runtime-index replace-semantics bug in
`hooks/sync-to-user-claude.py`** (lines ~373-381, `_sync_skills_flat_symlinks`).

The bug: when `skills/INDEX.local.json` exists, the hook points the runtime
`~/.claude/skills/INDEX.json` symlink **wholesale** at the local file. A stale
local index then hides newly added tracked skills from everything reading the
runtime index — the exact replace-semantics failure merged PR #778 fixed in
`scripts/routing-manifest.py`, `scripts/pre-route.py`, `scripts/index-router.py`
(tracked-first merge; local overlay adds, never hides). The hook is the
remaining un-fixed instance. Verified in source at HEAD.

Why it differentiates two strong arms:

| Property | Evidence |
|---|---|
| Real design choice | A symlink cannot express a merge. The fix must pick: materialize a merged gitignored runtime file (when regenerated? staleness window?), write-through strategy, or another shape — while keeping the leak-prevention invariant (harness in-place writes must never reach the tracked `INDEX.json`). |
| Multi-path reasoning | Symlink mode AND copy mode behave differently today (copy mode never sees local entries; symlink mode hides tracked ones). A complete fix covers both. Stale-cleanup loop and `expected_names` interactions are traps. |
| Test surface | `hooks/tests/test_sync_to_user_claude.py` exists with symlink-policy tests that must be updated, plus new stale-local and leak-invariant tests. |
| Objective gold standard | PR #778 defines correct merge semantics; graders can check closure against stated invariants, not taste. |
| Merges on merit | Known live bug, same class as a merged fix; needed regardless of experiment. |

Alternates rejected (live-verified 2026-06-10):

- **(a) typescript-debugging-engineer phantom refs + reviewer EMPTY_SECTION
  templates.** 2 missing refs confirmed (`validate-references.py`), but
  `grep -rln EMPTY_SECTION` over the repo returns **nothing** — that half of
  the evidence is stale. What remains is mechanical path fixing; both arms ace
  it; no signal.
- **(b) Hook shelf-ware triage.** 11 unregistered hooks confirmed;
  `agent-grade-on-change.py` present, `evals/harness.py` confirmed missing.
  But output is triage decisions, not code: weak objective grading, no test
  surface, and registering hooks changes live session behavior — blast radius
  too big for a both-arms-build-it experiment.
- **(c) index-router CLI test order-dependence.** Test-hygiene fix, small,
  single-path; both arms ace it; no signal.

Single task serves both arms without contamination because arms run in isolated
worktrees and only one PR ever exists (§3).

## 2. Arm definitions

Controls held constant: same agent type (`hook-development-engineer`) writes
all implementation code in both arms; the core task statement (`TASK.md`) is
byte-identical in both arms; same repo base commit; same deliverable and
constraint text. Variables: model on the implementation dispatch, and the
coordinate/review structure.

**Shared task statement — write once to `/tmp/model-ab-v1/TASK.md`, splice
verbatim into both arms:**

```
Fix a known bug in hooks/sync-to-user-claude.py.

Bug: the runtime-index policy in _sync_skills_flat_symlinks (lines ~373-381)
points ~/.claude/skills/INDEX.json wholesale at skills/INDEX.local.json
whenever the local file exists. A stale INDEX.local.json then hides newly
added tracked skills from everything that reads the runtime index — the same
replace-semantics failure PR #778 fixed in scripts/routing-manifest.py,
scripts/pre-route.py, and scripts/index-router.py (tracked-first merge:
local entries overlay/add per-name, never hide tracked ones). Read that fix
first: git log --grep="local-override" --oneline; git show d4eea119.

Required invariants after the fix:
1. The runtime index contains every entry of the tracked skills/INDEX.json;
   INDEX.local.json entries overlay/add per-name.
2. In-place writes to ~/.claude/skills/INDEX.json never reach the tracked
   skills/INDEX.json in the repo (keep the leak-prevention property).
3. Both install modes correct: symlink and copy.
4. Scope: hooks/sync-to-user-claude.py and hooks/tests/ only, unless you
   justify otherwise.

Deliverables:
- The fix.
- Tests in hooks/tests/test_sync_to_user_claude.py covering: stale local
  index no longer hides tracked entries; leak-prevention invariant holds;
  both install modes.
- Green: python3 -m pytest hooks/tests/test_sync_to_user_claude.py -q
- Green: ruff check . --config pyproject.toml && ruff format --check . --config pyproject.toml
- One local commit, message style "fix(sync): <what changed>". Do NOT push.
  Do NOT open a PR.

Safety:
- Never execute hooks/sync-to-user-claude.py against the real ~/.claude.
  Exercise it only through pytest tmp_path fixtures.
```

**Arm A dispatch (one Task call):**

```
Agent(
  subagent_type="hook-development-engineer",
  model="fable",
  prompt="Work in /tmp/<WT_A>/ (a git worktree on its own branch; commit there).
First author your workflow: numbered steps, files to touch, test plan,
acceptance checks — as the opening section of your reply, not a committed
file. Then execute it end-to-end.

<TASK.md verbatim>"
)
```

Budget: 1 dispatch + 1 retry (retry prompt = same prompt + "Your previous
attempt left failing checks: <pytest/ruff tail>. Fix and complete.").

**Arm B dispatches:**

B0 — workflow authoring. The orchestrator (fable) writes
`/tmp/model-ab-v1/workflow-b.md` itself before dispatching: numbered steps,
files to touch, test plan, acceptance checks — same headings Arm A is asked
for. No model call needed; the orchestrator is the fable coordinator.

B1 — builder:

```
Agent(
  subagent_type="hook-development-engineer",
  model="opus",
  prompt="Work in /tmp/<WT_B>/ (a git worktree on its own branch; commit there).
Follow this workflow:

<workflow-b.md verbatim>

<TASK.md verbatim>"
)
```

B2 — review (fable):

```
Agent(
  subagent_type="reviewer-code",
  model="fable",
  prompt="Review the change in /tmp/<WT_B>/ (run: git diff main) against this
task statement. Output numbered findings only — each: BLOCKING or
NON-BLOCKING, file:line, what is wrong, why it matters. No fixes. If nothing
blocks, say APPROVED.

<TASK.md verbatim>"
)
```

B3 — fixer (opus), only when B2 returned blocking findings:

```
Agent(
  subagent_type="hook-development-engineer",
  model="opus",
  prompt="In /tmp/<WT_B>/, address these review findings on your earlier
change. Re-run the test and lint commands from the task. Commit the fix
(normal fix message).

Findings:
<B2 findings verbatim>

<TASK.md verbatim>"
)
```

B4 — re-review: repeat B2. Approval = APPROVED or zero BLOCKING findings.
Budget: max 2 review rounds (B2→B3→B4); if blocking findings remain after
round 2, Arm B is DNF.

**Isolation.** Separate worktrees, separate local branches, no shared files,
no arm sees the other's worktree, report, or findings. Neither prompt mentions
comparison, experiment, models, arms, or `/tmp/model-ab-v1/`. Worktree paths
are neutral (`/tmp/<WT_A>`, `/tmp/<WT_B>` — names from §6 step 1) so an
agent's cwd reveals nothing.

## 3. Contamination controls

- **Same task, isolated worktrees.** Both branch from the same recorded main
  SHA. Arms launch in the same orchestrator turn (parallel start — fair
  timing, no cross-visibility). The orchestrator never pastes Arm A output
  into Arm B prompts or vice versa; all prompts are the frozen templates
  above, splice-points only TASK.md, workflow-b.md, findings, retry tails.
- **One PR ever.** Both branches stay local-only until the verdict. Winner's
  branch is pushed and gets a PR with a normal fix title/body (template §6
  step 9). Loser's branch is deleted without ever being pushed. No double-PR
  leakage; CI runs once, on what looks like an ordinary bug fix.
- **Commit hygiene.** Arms are instructed to write normal `fix(sync): ...`
  messages. Before push, the orchestrator greps the winner's commits and diff
  for experiment terms (gate G7, §6). Branch names are ordinary fix names
  carrying no arm marker.
- **Artifact containment.** Everything experiment-shaped (this file, TASK.md,
  workflow-b.md, assignments, packets, metrics, report) lives only in
  `/tmp/model-ab-v1/` until post-merge publication.
- **Orchestrator knowledge.** The orchestrator necessarily sees both arms; the
  blindness that matters is downstream: graders, CI, repo history, PR readers.

## 4. Grading

**Graders: N=3 fable agents** (`subagent_type="general-purpose"`,
`model="fable"`), dispatched in parallel, each grading BOTH anonymized work
products.

**Packet per grader** (`/tmp/model-ab-v1/packets/g{1,2,3}/`): `TASK.md`,
`RUBRIC.md`, `X.diff`, `Y.diff`, `X-tests.txt`, `Y-tests.txt`. Nothing else —
no branch names, no commit messages, no PR URLs, no model names, no token
counts.

**Anonymization.** Per grader, an independent coin flip maps {A,B}→{X,Y};
record all three flips in `/tmp/model-ab-v1/assignments.json` BEFORE building
packets. Diffs: `git -C <wt> diff <BASE_SHA> --no-color` (no commit metadata).
Test outputs: pytest+ruff output with worktree path rewritten to `REPO` via
sed. Blindness check before dispatch (gate G4):
`grep -riE 'opus|fable|claude-|arm[ -]?[ab]|model-ab|experiment|worktree' packets/` → must be empty.

**Rubric (frozen now; weights sum 1.0).** Each criterion 1-5 per diff.

| Criterion | Weight | 5 means |
|---|---|---|
| Correctness | 0.30 | Invariants 1-3 hold; tests green; no new failure mode introduced |
| Completeness | 0.20 | Both install modes, staleness, and cleanup interactions handled; no TODO gaps |
| Test quality | 0.20 | New tests fail on the old code, cover stale-local, leak, both modes |
| Code quality | 0.15 | Minimal, idiomatic, matches file's existing patterns and comment standard |
| Issue closure | 0.15 | The stated bug is fully closed, including edge paths; nothing reopens PR #778's class |

Plus a **forced choice**: "Which diff would you merge? X or Y. One sentence
why." Required JSON output:
`{"X": {"correctness": n, "completeness": n, "test_quality": n, "code_quality": n, "issue_closure": n}, "Y": {...}, "choice": "X"|"Y", "reason": "..."}`

**Grader prompt template:**

```
Agent(
  subagent_type="general-purpose",
  model="fable",
  prompt="Two candidate fixes exist for the task in
/tmp/model-ab-v1/packets/g<N>/TASK.md. Read TASK.md and RUBRIC.md, then grade
diff X (X.diff, X-tests.txt) and diff Y (Y.diff, Y-tests.txt) on the rubric,
1-5 per criterion. Judge only the packet contents. Finish with the forced
choice and emit exactly the JSON shape in RUBRIC.md as your final block."
)
```

**Aggregation.** Per grader, weighted score W = Σ wᵢ·sᵢ (max 5), rejoined to
arms via assignments.json by the orchestrator only. Winner = majority of the 3
forced choices (N odd → no tie). Mean delta Δ = mean(W_winner − W_loser).
**No-signal rule:** if all three graders show |W_X−W_Y| < 0.2, declare
NO-SIGNAL — still merge the majority-choice diff, report says task too easy,
replicate on a harder task.

**Secondary metrics** (orchestrator-recorded in `metrics.json`, never shown to
graders): per-arm total tokens (from Task results), wall-clock (dispatch
timestamps), dispatch count (A: 1-2; B: 3-5).

## 5. Verdict & publication

**Decision rule (pre-registered).** "Fable coordinate+review / opus build is
worth adopting" only when ALL hold:

1. Arm B wins the forced-choice majority (≥2 of 3 graders).
2. Mean weighted delta Δ ≥ 0.3 (of 5) — B must beat A by more than noise,
   because B costs more dispatches and tokens.
3. Every grader scores B's correctness ≥ 4.
4. The report states B's measured cost multiple (tokens, wall-clock,
   dispatches vs A); adoption recommendation carries it (precedent:
   self-route-v1 published 11x honestly).

Arm A winning, NO-SIGNAL, or B winning narrowly (Δ < 0.3) → keep current
defaults; publish anyway.

**Either way, the winning PR merges on merit** — green tests, ruff, normal
review. The experiment never blocks or forces a merge.

**Publication** (only AFTER the winner PR merges and the loser branch is
deleted): copy `/tmp/model-ab-v1/{PROTOCOL.md, TASK.md, workflow-b.md,
assignments.json, packets/, grades/, metrics.json, REPORT.md}` →
`scripts/routing-ab-results/model-ab-v1/`; open a separate
`docs(experiments): publish model-ab-v1 results` PR. REPORT.md follows
`self-route-v1/VERDICT.md` shape: pre-registered rule verbatim, per-grader
scores, rejoined arms, cost table, mechanism read, verdict.

**If B wins (rule satisfied):** follow-up PR (post-publication, separate)
extends the /do verb-based model dispatch table
(`skills/meta/do/SKILL.md` ~line 407): add an implementation-verb row
(implement / fix / build / refactor on Complex tasks) → opus builder dispatch
+ fable review gate, marked "adopted from model-ab-v1, n=1 — replicate on a
second task class before widening". One run on one task is directional, not a
default-changer; the row ships scoped to this task class (hook/Python repo
fixes) until a replication run.

## 6. Step-by-step execution checklist

Abort conditions live at the end; check them at every gate.

**Step 0 — freeze & pre-flight.**
- `pwd`; `git -C /home/feedgen/vexjoy-agent status --short` must be clean.
- `BASE_SHA=$(git -C /home/feedgen/vexjoy-agent rev-parse main)` → record in
  `/tmp/model-ab-v1/assignments.json`.
- Write `TASK.md` (§2, verbatim) and this PROTOCOL.md to `/tmp/model-ab-v1/`.
- Three coin flips now, before any dispatch: arm→worktree assignment
  (A gets WT_1 or WT_2), and per-grader {A,B}→{X,Y} maps for g1,g2,g3. Record
  all in `assignments.json`.
- **Gate G0:** protocol + TASK.md + assignments.json written; no edits after
  this point.

**Step 1 — worktrees.**
```sh
git -C /home/feedgen/vexjoy-agent worktree add -b fix/sync-runtime-index-merge /tmp/wt-syncfix-1 main
git -C /home/feedgen/vexjoy-agent worktree add -b fix/sync-runtime-index-overlay /tmp/wt-syncfix-2 main
```
(Names are ordinary fix names; arm assignment per coin flip. The sync hook's
own worktree guard keeps these from touching ~/.claude.)
- **Gate G1:** both worktrees at BASE_SHA, clean.

**Step 2 — launch arms (same turn, parallel).** Record timestamps.
- Dispatch Arm A (template §2) into its worktree.
- Write `workflow-b.md` (orchestrator-authored, §2 B0), then dispatch Arm B
  builder B1 into the other worktree.
- **Gate G2:** both dispatches returned with a diff present
  (`git -C <wt> diff <BASE_SHA> --stat` non-empty). Apply retry budgets on
  empty/failed returns.

**Step 3 — Arm B review chain.** B2 review → if blocking, B3 fix → B4
re-review. Max 2 rounds. Record each dispatch's tokens/time.
- **Gate G3:** Arm B APPROVED, or DNF declared.

**Step 4 — independent verification (orchestrator, deterministic).** In each
worktree:
```sh
python3 -m pytest hooks/tests/test_sync_to_user_claude.py -q
ruff check . --config pyproject.toml && ruff format --check . --config pyproject.toml
```
Save outputs to `/tmp/model-ab-v1/verify-<wt>.txt`.
- **Gate G4a:** an arm with red checks gets its remaining retry budget (A: 1
  retry; B: counts as a review round); still red → DNF.

**Step 5 — build packets.** For each grader gN, per its X/Y map:
```sh
git -C <wt> diff <BASE_SHA> --no-color > packets/gN/<label>.diff
sed "s|/tmp/wt-syncfix-[12]|REPO|g" verify-<wt>.txt > packets/gN/<label>-tests.txt
cp TASK.md RUBRIC.md packets/gN/
```
- **Gate G4:** blindness grep (§4) over `packets/` is empty; packets contain
  exactly the six files.

**Step 6 — dispatch 3 graders in parallel** (template §4). Save each JSON to
`/tmp/model-ab-v1/grades/gN.json`.
- **Gate G5:** three valid JSONs, all criteria scored, forced choice present.
  Invalid → one re-dispatch of that grader with a fresh packet copy.

**Step 7 — aggregate & verdict.** Rejoin via assignments.json; compute
per-grader W, majority, Δ; apply §5 decision rule; write
`/tmp/model-ab-v1/REPORT.md` + `metrics.json`.
- **Gate G6:** verdict recorded before any push.

**Step 8 — hygiene check on winner.**
```sh
git -C <winner-wt> log <BASE_SHA>..HEAD --format='%B' | grep -riE 'opus|fable|arm|experiment|model-ab|a/b' || echo CLEAN
git -C <winner-wt> diff <BASE_SHA> | grep -riE 'opus|fable|arm[ -]?[ab]|experiment|model-ab' || echo CLEAN
```
Hits in commit messages → reword locally before push. Hits in code → fix as a
normal amend (content unchanged otherwise).
- **Gate G7:** both CLEAN.

**Step 9 — winner PR.** Push winner branch only; open PR titled
`fix(sync): merge INDEX.local.json over tracked index in runtime skills index`
(adjust to the actual change), body = summary/changes/notes like PR #778's —
no experiment mention. CI and review proceed normally; merge on merit.

**Step 10 — cleanup.** After merge:
```sh
git -C /home/feedgen/vexjoy-agent worktree remove --force /tmp/wt-syncfix-1 /tmp/wt-syncfix-2
git -C /home/feedgen/vexjoy-agent branch -D <loser-branch>
```
Loser branch was never pushed; nothing remote to delete.

**Step 11 — publish.** Copy artifacts to
`scripts/routing-ab-results/model-ab-v1/`; open the
`docs(experiments): publish model-ab-v1 results` PR. If B won per §5, open the
/do dispatch-table follow-up PR after publication.

**Abort / rollback conditions.**
- **Both arms DNF** → abort experiment; fix the bug as normal work; publish a
  short NULL-RUN note.
- **One arm DNF** → other arm wins by default; if both diffs exist, grade
  anyway for the record.
- **Blindness breach in a packet** → discard that grader, rebuild packet,
  re-flip its X/Y, dispatch a fresh grader.
- **An arm pushes or opens a PR despite instructions** → delete the remote
  branch immediately; if the PR drew any attention, abort, merge the best fix
  as normal work, publish a breach note.
- **Protocol edit needed after G0** → invalidates the run; re-register and
  restart from Step 0 with fresh worktrees.
- **Full rollback at any point:** remove both worktrees, delete both local
  branches, `rm -rf /tmp/model-ab-v1` — repo untouched.
