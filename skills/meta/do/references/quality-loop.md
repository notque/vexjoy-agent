# Routed quality loop

For Medium+ code modification, preserve this outer lifecycle:

`ADR/plan when required -> implement -> test -> intent verify -> review -> fix
-> retest -> delivery checks -> reconcile decision records -> report`

Implementation and review need distinct evidence. Review findings return to the
implementation owner; changed inputs invalidate earlier checks. Protected git
and security actions continue through their force-routed skills. If a workflow
pipeline is also selected, run it inside implementation rather than duplicating
the outer lifecycle.

Run read-only reviewers from the repository root against the candidate diff;
do not allocate them separate checkouts.

Skip this loop for read-only, trivial, and non-code work unless the user asked
for it. Completion requires the task spec's acceptance evidence or an explicit
blocker, not ceremonial phase output.
