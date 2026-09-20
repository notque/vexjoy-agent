# PR status contract

Fetch before comparing refs. Report separately:

- local: branch, dirty paths, upstream, ahead/behind counts, unpushed commits;
- PR: number/URL/state, head/base, draft/mergeability, requested reviewers and decisions;
- CI: checks for the PR’s current head SHA, including pending/failing/absent states;
- review: unresolved threads or review requests, distinguishing bots from humans.

Readiness requires current-head CI green, no blocking review state, and mergeability—not merely an open PR. If `gh pr view` says no PR exists, still report local/remote branch state. Authentication/network failure is unknown status, not “no PR” or “green.”
