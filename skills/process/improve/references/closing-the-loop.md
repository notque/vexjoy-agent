# Closing the loop: execute, reconcile, issues

Three follow-through flows: dispatch an executor and review its work
(`execute`), keep the backlog current (`reconcile`), and publish plans where
work gets picked up (`--issues`).

The first rule holds throughout: **the advisor never edits source code.** In
`execute`, a separate executor edits code in an isolated worktree. The advisor
dispatches, reviews, and gives a verdict.

---

## `execute <plan> [model]`

### Preconditions

Check all before dispatch. On a failure, stop and say which one.

| Check | Command |
|---|---|
| The repo is a git repository | `git rev-parse --show-toplevel` |
| The plan exists and its dependencies are DONE | Read `plans/README.md` |
| The plan has not drifted | The plan's own drift-check command. If in-scope files changed, reconcile the plan first |
| The disk has room for a checkout | Rule 10 in `skills/meta/do/references/worktree-rules.md` |
| The plan has steps the executor can run | A plan with only OWNER-GATED steps goes to the owner, not an executor |

### Dispatch

Dispatch one agent with `isolation: "worktree"`. Pick the domain agent for the
plan's language (`python-general-engineer`, `golang-general-engineer`,
`typescript-frontend-engineer`); use `general-purpose` only when none fits.
Model: `opus` at `medium`, or the model the user named for this run. Mark the
plan IN PROGRESS in the index.

The prompt holds three parts:

1. **The full plan text, inlined.** A worktree holds committed files only. An
   uncommitted `plans/` directory is not there. Always inline.
2. The executor preamble:

> You are the executor for the implementation plan below. Follow it step by
> step. Run every verification command and confirm the expected result before
> the next step. Modify only the files listed as in scope. If a STOP condition
> occurs, stop at once and report. Do not improvise around obstacles.
>
> Limits that no plan step overrides: work only inside your worktree. Do not
> push, open a pull request, merge, tag, or deploy. Do not read credential or
> env files. Do not start a server on a public interface. Do not create a
> scheduled job, service, or other persistent process. Do not delete or
> migrate data outside the worktree. Do not send repository content to a third
> party. Skip any step marked OWNER-GATED and list it as pending. Stop every
> process you start before you report.
>
> Read `skills/meta/do/references/worktree-rules.md` first and follow it. Commit in the worktree
> as the plan's git workflow section says. Skip the plan's instruction to
> update `plans/README.md`; your reviewer maintains the index. Before you
> report, check every claim against a tool result from this session. If a
> verification failed or was skipped, say so. Reply in exactly the report
> format below.

3. The report format:

```
STATUS: COMPLETE | STOPPED
STEPS: per step: done or skipped, plus the verification command's result
STOPPED BECAUSE: (only if STOPPED) which STOP condition and what you observed
OWNER-GATED PENDING: steps skipped for owner approval, or "none"
FILES CHANGED: list
NOTES: deviations, surprises, judgment calls
```

### Review

A fresh worktree shares git history but not installed dependencies or build
output. The executor installs first, and a check may need one build that the
plan's command table did not list. That is expected, not a deviation.

Review as a tech lead reviews a pull request against its spec. Fix nothing
yourself.

1. **Re-run every done criterion** in the worktree. Do not trust the report.
2. **Check scope**: `git -C <worktree> diff --stat <base>..HEAD` against the
   in-scope list. A file outside scope fails review.
3. **Read the whole diff.** Every hunk traces to a plan step. Judge it against
   "Why this matters" and the conventions the plan names.
4. **Read the new tests.** A test that asserts nothing passes the suite and
   proves nothing.
5. **Check the limits.** The diff adds no secret, public bind, scheduled job,
   or outbound call the plan did not specify.

### Verdict

Judge a documented deviation on its merits. An executor that hits a real
obstacle, adapts minimally, stays in scope, and explains it in NOTES did the
right thing. An undocumented deviation fails review.

| Verdict | When | Action |
|---|---|---|
| **APPROVE** | Criteria pass, scope is clean, quality holds | Mark DONE in the index. Report the diff summary, worktree path, branch, pending OWNER-GATED steps, and NOTES. Merging is the owner's decision. Keep the worktree until the owner decides |
| **REVISE** | Gaps the executor can fix | Send the same executor specific feedback ("criterion 3 fails: X; `api.ts:90` discards the error, use the Result pattern as the plan says"). At most 2 rounds, then BLOCK |
| **BLOCK** | A STOP condition, an unrecoverable scope violation, or revisions used up | Mark BLOCKED in the index with the reason. Rewrite the plan with what you learned. Remove the worktree. Report what happened and what changed in the plan |

### Cleanup

You own every worktree you dispatched.

- On BLOCK: remove it now (`git worktree remove <path>`, then delete its branch
  if it has no commits worth keeping).
- On APPROVE: keep it for the owner. List its path and branch in the report.
  Remove it once the owner has merged or declined.
- Before you report: run `git worktree list`, `ps -eo pid,etime,args`, and
  `ss -ltnp`. Stop what you or the executor started. Report anything that
  belongs to another session; do not stop it.

---

## `reconcile`

Read `plans/README.md` and every plan file. Then act by status:

| Status | Action |
|---|---|
| DONE | Re-run the cheap done criteria on HEAD. Mark verified. Keep the plan file as the record |
| BLOCKED | Read the reason. Investigate the obstacle in the code. Rewrite the plan around it (a new number when the approach changes), or mark REJECTED with one line |
| IN PROGRESS | An executor probably died. Check `git worktree list` for its worktree and report it to the owner |
| TODO | Run the drift check. If drifted, confirm the finding still exists, then refresh the "Current state" excerpts and the "Planned at" SHA. If the finding is gone, mark REJECTED ("fixed independently") |
| STALE | Leave it. Confirm the superseding plan exists |

Also list executor worktrees still on disk and whether each can go.

End with a short report: verified done, refreshed, rejected, blocked with
reasons, and what is executable now.

---

## `--issues`

A modifier on any planning run. It sends repository content to GitHub, so it is
third-party egress: run it only when the owner asked for it in this request.
Under the host policy, that request states the destination repo.

1. Preflight: `gh auth status` succeeds and the repo has a GitHub remote. If
   either fails, write the plan files as usual and say why you skipped issues.
2. Visibility: `gh repo view --json visibility`. On a public repo, do not
   publish a plan that describes a security weakness or a credential location.
   Report those plans as held back and why.
3. Show the titles about to become issues. Confirm once when a user is present.
4. Per plan: `gh issue create --title "<plan title>" --body-file <plan file>`.
   Add the `improve` label and the category label only when they already
   exist. Skip labels; never fail on them.
5. Record each URL in the plan's Status block and in the index.

The plan file stays the source of truth. The issue is distribution.
