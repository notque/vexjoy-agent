# Contributor PR landing contract

Required end state: GitHub reports `MERGED` (not merely `CLOSED`), local checkout is on an updated base branch, and temporary landing refs are removed.

Start with a clean tree and capture PR state, base/head repos and branches, head SHA, mergeability, and permissions. Create a temporary branch at a freshly fetched base tip; check out the PR head and rebase onto that pinned tip. Resolve conflicts narrowly and preserve contributor authorship.

Run repository-required quality gates after rebase. Commit only scoped fixes. For a fork, push to the PR’s actual head repository/branch with a lease tied to the fetched head SHA; if lease fails, fetch and reassess rather than force-overwriting new work.

Merge through GitHub only when current-head required checks and approvals pass. Verify state `MERGED`, record the merge SHA/evidence, return to the updated base, and remove temporary branch/remote. If checks, permission, conflicts, or lease block landing, preserve the branch and report the exact blocker.
