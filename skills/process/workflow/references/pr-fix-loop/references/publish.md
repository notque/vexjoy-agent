# PR Fix Loop: Publish Commands

Load in Phase 4, only on the owner's go for this PR. Run from the PR's worktree. Every step that changes GitHub needs that go; a new round after red CI or a Copilot fix needs a new go.

## 0. Resolve the PR

Use the full PR URL so every `gh pr` command targets the right host and repo.

```bash
PR=<full PR URL>
LEASE=<head SHA the owner last saw: the Phase 2 State line, or the last pushed head you reported>
HOST=$(echo "$PR" | cut -d/ -f3)
REPO=$(echo "$PR" | cut -d/ -f4-5)          # base repo, owner/name
NUM=$(echo "$PR" | cut -d/ -f7)
# One field per call: branch names from a foreign repo never pass through eval.
HEAD_OWNER=$(gh pr view "$PR" --json headRepositoryOwner -q .headRepositoryOwner.login)
HEAD_NAME=$(gh pr view "$PR" --json headRepository -q .headRepository.name)
BRANCH=$(gh pr view "$PR" --json headRefName -q .headRefName)
BASE=$(gh pr view "$PR" --json baseRefName -q .baseRefName)
CROSS=$(gh pr view "$PR" --json isCrossRepository -q .isCrossRepository)
HEAD_URL="https://$HOST/$HEAD_OWNER/$HEAD_NAME.git"   # where the PR branch lives (a fork when CROSS=true)
BASE_URL="https://$HOST/$REPO.git"
git fetch "$BASE_URL" "refs/heads/$BASE"
BASE_SHA=$(git rev-parse FETCH_HEAD)
```

## 1. Squash to one commit

```bash
REVIEWED=$(git rev-parse HEAD)               # the SHA /pr-review recorded in Phase 3
git reset --soft "$(git merge-base "$BASE_SHA" HEAD)"
git commit -s -m "<one line>"                # drop -s when the repo has no DCO
git log --oneline "$BASE_SHA"..HEAD          # must print exactly one line
git diff --quiet "$REVIEWED" HEAD && echo "tree unchanged: the squash only needs a fresh record"
```

## 2. Review the squashed commit

The `pretool-review-before-push-gate.py` hook blocks `git push`, `gh pr create`, and `gh pr edit --base` until a review record exists for the commit. It does not gate `gh pr ready` or a body-only `gh pr edit`; the owner's go still covers both.

A record covers one SHA, so the squash needs its own review, even when the tree is unchanged. Run `/pr-review` with no PR argument (local-branch mode) on the squashed commit. When no Critical or Important finding is open, Phase 6b writes `/tmp/pr-review-<sha12>.md` and runs `review-record.py mark --sha "$REVIEWED_SHA" --findings-file ...`. A review of the PR number or URL writes no record.

```bash
# exit 0: record exists for HEAD; 1: no record, review first; 2: usage or git error
python3 ~/.claude/scripts/review-record.py check --sha "$(git rev-parse HEAD)" --repo-dir .
```

## 3. Check the lease, then push

```bash
REMOTE_HEAD=$(git ls-remote "$HEAD_URL" "refs/heads/$BRANCH" | cut -f1)
if [ "$REMOTE_HEAD" != "$LEASE" ]; then
  echo "STOP: $BRANCH is at $REMOTE_HEAD, the owner saw $LEASE"   # report; do not push
else
  git push --force-with-lease="refs/heads/$BRANCH:$LEASE" "$HEAD_URL" "HEAD:refs/heads/$BRANCH"
fi
```

A rejected lease or a different remote head means someone else pushed. Stop and report; never retry with plain `--force`. After a push, the pushed SHA is the next round's `LEASE` once you have reported it.

## 4. Update the body and confirm it

```bash
gh pr edit "$PR" --body-file "pr-$NUM-body.md"
gh pr view "$PR" --json body -q .body > "pr-$NUM-body.posted.md"
python3 -c 'import sys; n=lambda p: open(p, encoding="utf-8").read().replace("\r", "").rstrip("\n"); sys.exit(n(sys.argv[1]) != n(sys.argv[2]))' \
  "pr-$NUM-body.md" "pr-$NUM-body.posted.md" && echo "body matches" || echo "body MISMATCH"
```

## 5. Request a Copilot review and verify it

Skip this step on a GitHub Enterprise Server host (`HOST` is not `github.com`): `@copilot` is not supported there. Report "Copilot: not available on this host".

```bash
gh pr edit "$PR" --add-reviewer @copilot
gh pr view "$PR" --json reviewRequests,latestReviews | grep -qi copilot && echo "registered" || echo "NOT registered"
```

The check string is case-insensitive `copilot`: the bot appears as `Copilot` in requests and `copilot-pull-request-reviewer[bot]` in reviews.

## 6. Wait with a deadline

```bash
SHA=$(git rev-parse HEAD)
COPILOT=1; [ "$HOST" = "github.com" ] || COPILOT=0
checks_done() {
  out=$(gh pr checks "$PR" --json bucket 2>/dev/null)
  python3 -c 'import json, sys; c = json.loads(sys.argv[1] or "[]"); sys.exit(0 if c and all(x["bucket"] != "pending" for x in c) else 1)' "$out"
}
copilot_done() {
  [ "$COPILOT" = 0 ] && return 0
  gh api --paginate "repos/$REPO/pulls/$NUM/reviews" --jq ".[] | select(.commit_id==\"$SHA\") | .user.login" 2>/dev/null | grep -qi copilot
}
sleep 60                                     # grace period: checks register after the push
deadline=$((SECONDS + 1800))
until checks_done && copilot_done; do
  if [ "$SECONDS" -ge "$deadline" ]; then echo "TIMEOUT after 30 min"; break; fi
  sleep 30
done
gh pr checks "$PR" --json name,bucket
```

`checks_done` needs at least one check, so "no checks reported" right after a push keeps waiting. Run the block in the background. On `TIMEOUT`, report the pending checks and the Copilot state to the owner; do not re-push.

## 7. Results

| Result | Action |
|--------|--------|
| A check in bucket `fail` | `gh run view <run-id> --log-failed`, fix locally, `/pr-review` the fix delta, re-squash, report; repeat steps 1-6 only on the owner's go |
| Valid Copilot comment | Same as a failed check |
| Invalid Copilot comment | Write the comment and your reasoning to `pr-$NUM-copilot-invalid.md`. Never reply on GitHub. |
| Round 4 would start | Stop and escalate to the owner: at most 3 CI/Copilot rounds per PR |
