---
description: "Fix, implement, or address review on PRs in repos you don't own: review locally, discuss, fix locally, publish only on the owner's go."
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
  - Agent
  - Edit
  - Write
  - Skill
routing:
  triggers:
    - pr fix loop
    - upstream PR
    - upstream pull request
    - repo I don't own
    - repo we don't own
    - someone else's repo
  pairs_with:
    - pr-workflow
    - review
  complexity: Complex
  category: devops
---

# PR Fix Loop

Use this pipeline to fix, implement, or address review on one or more pull requests in a repo you don't own (upstream, OSS, another team's org). Every phase exists because skipping it once caused a public mistake.

| Phase | Name | Public effect |
|-------|------|---------------|
| 0 | GROUND RULES | none |
| 1 | REVIEW | none |
| 2 | DISCUSS | none |
| 3 | FIX | none (local commits only) |
| 4 | PUBLISH | push, body, review request, each on the owner's go for that PR |
| 5 | TRACK | none |

**Domain overlays.** A domain overlay, such as a private org-specific skill, can add domain edge cases and ground rules. When one is installed for the target repo or org, load it in Phase 0 and apply its rules in every phase. Overlay rules add to this pipeline; they never relax it.

---

### Phase 0: GROUND RULES (always on)

**Check ownership first.** The `pretool-review-before-push-gate.py` hook treats every repo that is not a non-fork `github.com/notque` repo as one you don't own. Check the PR's base repo: `gh repo view <owner>/<repo> --json isFork,owner`. If it is a non-fork `notque` repo, stop and hand the work back to `pr-workflow`.

Apply these rules for the whole run, in every agent brief:

1. **Nothing public without the owner's approval.** That covers pushes, new PRs, body edits, comments, review replies, draft/ready toggles, and closes. Agents commit locally and report the SHA.
2. **PR text belongs to the owner.** The agent may draft the PR body to a local file for the owner to approve or edit; it is posted only on the owner's go. PR comments, review replies, and upstream discussion text are written by the owner alone. The agent never drafts or posts them unless asked.
3. **Prod is read-only, at low load.** Never send profile, explain, or other diagnostic options to production systems.
4. **Paused data paths count as live.** Rate every issue on a paused path as current. Never write "doesn't hit us today", "safety net", or "not live".
5. **No internal names in public repos:** not in code, comments, regexes, commit messages, or PR bodies.
6. **Alert severity changes need the owner's approval.** Never raise or lower a severity, or add a paging alert, without the owner's go.
7. **Every report that mentions a PR gives its full URL.**
8. **No Claude Artifacts.** Pages are local HTML files opened in the browser. Metric dashboards go in the team's dashboard tool, not a page.
9. **Load the domain overlay** for the target repo or org when one is installed.

**Gate**: ownership checked (foreign repo confirmed); ground rules in every agent brief; overlay loaded or confirmed absent.

---

### Phase 1: REVIEW (local, read-only)

1. **Collect every comment** into one local file per PR: bot overview and inline comments, plus human comments, each with the commit it was made on. Commands: `pr-fix-loop/references/review-checklist.md`.
2. **Run the real review.** Call the Skill tool with `pr-review` on the PR number or URL. A custom reviewer prompt does not count. A review of a PR number or URL writes no review record; only the local-commit review in Phase 3 does.
3. **Run an independent domain re-review** that re-verifies each claim on live data, read-only, with paused-path data as the baseline.
4. **Check user-visible output as it renders.** For dashboards, alerts, or metrics, use the observability checks; for anything else, run the changed output as users see it. Details: `pr-fix-loop/references/review-checklist.md`.
5. **Work the edge-case checklist** in `pr-fix-loop/references/review-checklist.md`: the generic list always, the observability list when the PR changes dashboards, alerts, or metrics. Test each item or mark it N/A with a reason. Add the overlay's domain edge cases.

**Gate**: per PR, a comment file, a `/pr-review` result, a domain re-review, a render check, and every applicable checklist item tested or N/A with reason.

---

### Phase 2: DISCUSS (one PR at a time, in merge order)

Present each PR to the owner in the fixed format in `pr-fix-loop/references/message-formats.md`: state, what and why, what's right, problems table, one-commit plan, confidence, and numbered decisions with a recommendation each.

The owner decides. State every default you picked so the owner can override it. Record the head SHA from the State line: it is the push lease baseline in Phase 4.

**Gate**: the owner has answered every numbered decision for this PR; the Phase 2 head SHA is recorded.

---

### Phase 3: FIX (local only, one agent per PR)

Run independent PRs in parallel, one agent each.

1. **Work in a new local worktree** on the PR branch. Never touch the main checkout.
2. **Apply the agreed fixes.** Include a related follow-up only when it can be validated; otherwise keep it separate.
3. **Draft the PR body** to a local file for the owner to approve or edit, in the target repo's style: read its last ~15 merged PRs. Say simply what the problem is, what changes, and how it was tested, for a reviewer who doesn't know your history.
4. **Docker-test on one harness:** "before" shows the bug, "after" shows the fix, a control shows nothing else changed. Use real inputs: rendered configs from the branch plus live-derived and paused-path samples.
5. **Run the repo's own checks:** template diff base vs head, lint, docs generators, license checks, config validation with the pinned image, and the language test suites.
6. **Review the local commit.** Call the Skill tool with `pr-review` with no PR argument (local-branch mode) on the committed branch. Fix what it finds, commit, and re-review the fix delta. Repeat until clean. When clean, `/pr-review` Phase 6b writes its findings to `/tmp/pr-review-<sha12>.md` and records the reviewed SHA with `scripts/review-record.py mark`.

**Gate**: Docker before/after/control table filled, repo checks pass, `/pr-review` clean on the final local SHA, body draft written. Report the SHA; do not push.

---

### Phase 4: PUBLISH (only on the owner's go for this PR)

Commands, the deadline wait loop, and the GHES rules: `pr-fix-loop/references/publish.md`.

1. **Resolve the PR's repos** with `gh pr view --json headRepositoryOwner,headRepository,headRefName,baseRefName,isCrossRepository`. Push to the head repo and branch, never an assumed `origin`. Fetch the base branch from `baseRefName`.
2. **Squash to one commit**: a one-line message, plus `Signed-off-by` (`git commit -s`) where the repo requires DCO.
3. **Review the squashed commit.** The `pretool-review-before-push-gate.py` hook blocks `git push`, `gh pr create`, and `gh pr edit --base` until a record exists for the commit; it does not gate `gh pr ready` or a body-only `gh pr edit`, and the owner's go still covers both. A record covers one SHA, so run `/pr-review` in local-branch mode on the squashed commit and confirm with `scripts/review-record.py check`. If `git diff --quiet <reviewed-sha> HEAD` passes, tell the owner the tree is unchanged and the squash only needs a fresh record.
4. **Check the lease.** The baseline is the head the owner last saw: the Phase 2 head SHA, or the last pushed head you reported. Fetch the remote head; if it differs, stop and report instead of pushing.
5. **Push** with `--force-with-lease=<branch>:<baseline>` to the head repo. Never push to the default branch.
6. **Update the body** from the owner-approved local file, then confirm the posted body matches.
7. **Request a Copilot review** and verify it registered. On a GitHub Enterprise Server host, skip this step and report "Copilot: not available on this host".
8. **Wait for CI and Copilot** with an until-loop that has a deadline in the command. On timeout, report what is still pending; do not re-push.
9. **Handle results.**
   - **Red CI:** read the failed logs, fix locally, re-review, re-squash, and report. Re-push only on the owner's go.
   - **Valid Copilot comment:** same path as red CI.
   - **Invalid Copilot comment:** write the reasoning to a local file. Never reply on GitHub; the owner replies.
   - **Round cap:** at most 3 CI/Copilot rounds per PR. Past that, stop and escalate to the owner.
10. **Report** in the fixed Phase 4 format in `pr-fix-loop/references/message-formats.md`, PR URL first.

**Gate**: one commit on the PR, review record for that SHA, CI green, Copilot finished or marked not available, every Copilot comment fixed or logged, report delivered.

---

### Phase 5: TRACK

1. **Version claims.** When several PRs bump versions in one file, keep a claims list. Versions must merge in ascending order.
2. **Status board.** Keep a local HTML board, opened in the browser, with each PR's URL, head SHA, phase, and blocker.
3. **Decisions log.** Record every owner decision with date and PR URL.
4. **Handover.** Hand anything outside your ownership to the owning session with full context: PR URL, SHA, evidence, open decisions.

**Gate**: board, log, and claims list match the current PR heads (`gh pr view <n> --json headRefOid`).

---

## Error handling

| Failure | Action |
|---------|--------|
| Push blocked by `pretool-review-before-push-gate.py` | Run `/pr-review` in local-branch mode on HEAD, fix findings, let Phase 6b record the SHA, then retry. Never bypass the gate. |
| Remote head differs from the lease baseline, or `--force-with-lease` rejected | Someone else pushed. Stop, fetch, show the owner the new commits, and wait. |
| Push refused for permission on a fork | Stop and report; the PR author may need to allow maintainer edits. |
| CI red | Fix locally, re-review, re-squash, report; re-push only on the owner's go. |
| Wait loop hit its deadline | Report the pending checks and Copilot state; do not re-push. |
| Copilot request did not register on github.com | Retry once, then report it as unverified. |
| More than 3 CI/Copilot rounds | Stop and escalate to the owner. |
| Docker "before" does not show the bug | The fix is unproven. Fix the harness before claiming the fix. |
| `/pr-review` still has findings after 3 loops | Stop and report. Do not ask to publish. |
