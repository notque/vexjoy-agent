# Disprove Pass

A separate model call tries to refute each finding from the code, and refuted findings leave the report. Run it after findings are collected and before they are reported. Use it in Systematic (Phase 3.5) and Parallel (Step 3) modes. Skip it when there are no findings.

## Steps

1. Write the findings to `findings.json`, a list of `{"fid", "file", "line", "severity", "quote", "claim"}`. `fid` is optional (default `f1`, `f2`, ...).
2. Build the prompt. Pass the post-change diff and every touched file.

```bash
python3 scripts/disprove-findings.py prompt --findings findings.json --diff diff.patch --file path/a --file path/b --lang python > prompt.txt
```

3. Dispatch one agent with `model: opus`, a fresh context, and `prompt.txt` as its whole task. Tell it to answer only from the prompt and reply with JSON only. Send all findings of the review in this one call, not one call per finding.
4. Save the reply as `verdicts.txt` and apply it.

```bash
python3 scripts/disprove-findings.py apply --findings findings.json --verdicts verdicts.txt --diff diff.patch --file path/a --file path/b
```

5. Report the `kept` list. Name each `dropped` finding and its `refuted_by` reason in the Rationale so the owner can audit the drop. Dropped findings do not count toward the verdict.

## Drop rule

The script drops a finding only when its verdict is `refuted` and its reason quotes code, in backticks, that appears in the diff or a touched file. It keeps the finding in every other case: `stands`, a missing or malformed verdict, a reason with no quote, or a quote not found in the code.

Keep this fail-open behavior:

| Situation | Action |
|---|---|
| Agent times out, returns nothing, or returns non-JSON | Keep all findings and record the gap in the Rationale |
| Premise marked `open` | Keep the finding |
| Verdict `stands` | Keep the finding; do not re-ask or argue it |

## Model

Use opus. On 48 review units (323 findings), the refuter dropped 20 findings and none was valid by both judges or a planted bug. Recall held at 0.875. False positives per review fell from 0.500 to 0.229 on the primary label, 0.604 to 0.312 on opus labels, and 1.000 to 0.646 on GPT labels. A batched sonnet call missed the GPT-label bar (0.708 against a 0.700 limit). One opus call costs about $0.14 per review.
