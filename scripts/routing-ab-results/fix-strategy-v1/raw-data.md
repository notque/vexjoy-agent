# Raw per-trial data (mirror of gitignored JSON artifacts)

JSON files (`experiment.json`, `findings.json`, `trial-data.json`, `judge-*.json`, `uid-map.json`, `scoreboard.json`) are excluded by `.gitignore:80` (repo policy for routing-ab-results). This file mirrors their content for version history.

## Per-trial results

| Trial | Arm | Test pass | Exit | Collateral | Lines changed | Tool calls |
|---|---|---|---|---|---|---|
| T01 | fresh | True | 0 | False | 6 | ~3-4 (self-report) |
| T02 | fresh | True | 0 | False | 10 | ~3-4 (self-report) |
| T03 | fresh | True | 0 | False | 3 | ~3-4 (self-report) |
| T04 | fresh | True | 0 | False | 6 | ~3-4 (self-report) |
| T05 | fresh | True | 0 | False | 6 | ~3-4 (self-report) |
| T06 | fresh | True | 0 | False | 5 | ~3-4 (self-report) |
| T07 | fresh | True | 0 | False | 5 | ~3-4 (self-report) |
| T08 | fresh | True | 0 | False | 5 | ~3-4 (self-report) |
| T01 | same-ctx | True | 0 | False | 3 | ~3-4 (self-report) |
| T02 | same-ctx | True | 0 | False | 11 | ~3-4 (self-report) |
| T03 | same-ctx | True | 0 | False | 3 | ~3-4 (self-report) |
| T04 | same-ctx | True | 0 | False | 8 | ~3-4 (self-report) |
| T05 | same-ctx | True | 0 | False | 4 | ~3-4 (self-report) |
| T06 | same-ctx | True | 0 | False | 5 | 3 |
| T07 | same-ctx | True | 0 | False | 2 | 3 |
| T08 | same-ctx | True | 0 | False | 3 | 3 |

## Blind judge verdicts (rejoined with uid-map)

| Trial | X was | Y was | Judge picked | Winner | Reason |
|---|---|---|---|---|---|
| T01 | fresh | same-ctx | Y | same-ctx | Both use correct ceiling-division idioms, but Y is more minimal (no unrelated docstring edit) and the (n+d-1)//d form is more immediately readable than the double-negation trick. |
| T02 | fresh | same-ctx | tie | tie | Functionally identical fixes; Y's comment explaining the ordering rationale (escape after strip so regex sees raw tags) is marginally better, but X is marginally more minimal -- net wash. |
| T03 | same-ctx | fresh | tie | tie | The diffs are character-for-character identical. |
| T04 | fresh | same-ctx | X | fresh | Both apply the same correct fix (split with maxsplit=1), but X is more minimal -- it only touches the bug site, while Y also edits the module docstring. |
| T05 | same-ctx | fresh | X | same-ctx | Identical core fix (expiration check + eviction), but X is more minimal -- Y adds an unrelated module docstring edit. |
| T06 | fresh | same-ctx | X | fresh | Identical core fix (multiplier default 0.0 to 2.0), but X is more minimal -- Y also edits the module docstring. |
| T07 | same-ctx | fresh | X | same-ctx | X applies the single missing assignment with surgical precision; Y adds two unrelated edits (module docstring and init comment removal) that expand the diff beyond the bug fix. |
| T08 | same-ctx | fresh | X | same-ctx | Identical core fix (extend with remainders), but X is more minimal -- Y also edits the module docstring. |

Totals: fresh 2, same-ctx 4, tie 2.
