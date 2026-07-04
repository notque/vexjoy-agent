# planning-unknowns-v2 — Pre-committed gates (written before any v2 result)

Design: 12 scenarios (v1's 6 + 6 new, same domain mix) × 2 independent sonnet
samples per arm = 48 generations. Judge: blind opus, pairwise per
(scenario, sample) = 24 judgments, random X/Y order, uid map withheld.

PROMOTE requires ALL of:
- (a) Two-sided sign test on discordant (non-tie) pairs, p < 0.05, favoring edited.
- (b) No judgment where the edited arm loses for a reason attributable to the
  edited text itself (Deviations, Blindspots, reference-implementations,
  volatile-first content causing bloat, confusion, or scope creep).
- (c) Collection failures 0; all 24 judgments parse.

Otherwise: INCONCLUSIVE (edited leads without significance) or DEMOTE
(full leads or gate (b) fails). No post-hoc gate changes.
