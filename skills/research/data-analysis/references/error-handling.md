# Data Analysis — Error Handling Reference

Error conditions, recovery procedures, and retry limits for the data-analysis skill.

---

## Error: "No decision context provided"

**Cause**: User provides data without stating what decision it supports ("just analyze this CSV").

**Solution**: Ask "What will you do differently based on this analysis?" If truly exploratory, switch to Exploratory Mode: apply rigor gates but label all findings as exploratory with no causal claims.

---

## Error: "Data file cannot be parsed"

**Cause**: Malformed CSV, unexpected encoding, mixed delimiters, or binary file.

**Solution**:
1. Try common encodings: utf-8, latin-1, utf-8-sig
2. Detect delimiter: comma, tab, semicolon, pipe
3. If JSON: validate structure, identify if it's array-of-objects or nested
4. If still failing: ask user for format details.
5. Maximum 3 parse attempts before asking the user for format help.

---

## Error: "Insufficient data for planned segments"

**Cause**: Metric definitions specify segments (by region, by tier) but some segments have <30 observations.

**Solution**:
1. Report which segments are below minimum
2. Options: merge small segments into "Other", remove segmentation, or accept reduced confidence with disclosure
3. Return to Phase 2 to adjust definitions if needed, documenting the change

---

## Error: "Metrics changed after seeing data"

**Cause**: Analyst realizes original definitions prove unworkable after loading data (column doesn't exist, wrong granularity).

**Solution**: This is expected and acceptable IF handled properly:
1. Return explicitly to Phase 2
2. Document what changed and why
3. Save updated metric-definitions.md with change log
4. Make every adjustment visible -- the change must appear in the artifact trail
5. Maximum 2 definition revisions before flagging scope concern.

---

## Death Loop Prevention

If the analysis is cycling (returning to Phase 2 repeatedly, growing artifact count without convergence, same error recurring), simplify: drop segments, reduce metrics to the single most important one, narrow the time window. A tightly framed decision in Phase 1 produces fewer metrics and faster convergence.

Maximum retry limits:
- 3 attempts to parse a data file
- 2 definition revisions in Phase 2
- 3 rigor gate remediation attempts before documenting as limitation

---

## Blocker Criteria

Stop and ask the user when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| No decision context and user resists framing | Analysis without purpose wastes effort | "Help me understand: what will change based on this analysis?" |
| Data format unclear | Parsing errors corrupt analysis | "What format is this data in? What do the columns represent?" |
| Critical columns have >50% missing values | Analysis on mostly-missing data is unreliable | "Column X is 60% missing. Should we exclude it or is there another data source?" |
| Metric definitions contradict each other | Conflicting definitions produce conflicting results | "Metric A and B use different definitions of 'active user'. Which should we standardize on?" |
| Results are ambiguous (CI spans zero for primary metric) | User needs to know the data is inconclusive | State clearly: "The data does not support a confident decision. Here are options for getting more data." |

Ask the user about column semantics, population definitions, business thresholds, or causal claims (correlation is not causation).
