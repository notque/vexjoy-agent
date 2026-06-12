# Staleness Windows

Freshness windows per claim type for Phase 2 Step 6. A claim whose evidence is older than its window needs a re-check before it can be Verified — facts carry timestamps, and a true-then figure can be a false-now figure.

Reviewed: 2026-06-12. These are defaults; the caller's domain can override them (e.g., a historical piece quotes period figures deliberately — then the window applies to "was X at time T" framing, not the figure itself).

| Claim type | Window | Reason | Re-check action |
|------------|--------|--------|-----------------|
| Prices, market figures, exchange rates | 1 day–1 week | Move continuously | Fetch current figure; report date with the figure |
| Counts that grow (users, downloads, deployments, casualties, case numbers) | 1–3 months | Newer official figure usually exists | Search the same origin for the latest figure |
| Titles, roles, employment ("CEO of X") | 3–6 months | People change jobs quietly | Confirm against the org's current page or latest filing |
| Event status (scheduled, ongoing, settled) | Until the event date passes | Schedules slip | Confirm status as of today, state the as-of date |
| Survey/poll results | 6–12 months | Opinion drifts; methodology ages | Cite fieldwork dates, not publication date; look for a newer wave |
| Scientific findings | 1–3 years | Replications and retractions accrue | Check for retractions, corrections, newer meta-analyses |
| Laws, regulations, policies | 6–12 months | Amended and superseded | Verify against the currently-in-force text |
| Records and superlatives ("largest", "first", "fastest") | Re-check every use | One newer event falsifies them | Search for a superseding event since the source date |
| Stable historical facts (past dates, completed events) | None | Settled | Verify once against a primary source |

## Applying a window

1. Date the evidence: when was the source's figure true? Fieldwork date and as-of date beat publication date — a 2026 article can carry a 2023 figure.
2. Compare to today. Inside the window: usable. Outside: re-check.
3. Re-check outcome drives the label:
   - Newer figure from the same origin contradicts the claim → **Disputed** (stale stat), report both figures with dates.
   - Newer figure confirms → **Verified**, cite the newer source.
   - No newer figure findable → **Unverifiable**, flagged stale, with the evidence date stated.

## Reporting rule

Every time-sensitive Verified claim carries its as-of date in the report ("12,000 deployments as of May 2026"). The date is part of the fact, and a report that drops it manufactures the next stale stat.
