# Hill-climb specification

Freeze one metric and direction, deterministic measurement command, target,
pinned fixture and checksum/seed, correctness floors, sample count, variance
tolerance, iteration budget, and plateau count. Baseline under fixed conditions;
profile before editing. Each iteration states one hypothesis, makes one change,
runs floors, and repeats the same measurement. Revert a failed floor. Accept
only improvement beyond measured spread. Rubrics require frozen text and a
fresh-context grader. Stop on target, plateau, budget, or unstable harness.
