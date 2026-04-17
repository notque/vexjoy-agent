# Repo Value Analysis Error Handling

## Error: "Repository Clone Failed"
Cause: Invalid URL, private repo, network issue, or repo doesn't exist
Solution:
1. Verify the URL is correct and the repo is public
2. If private, check that git credentials are configured
3. If network issue, retry once after 5 seconds
4. If repo doesn't exist, report to user and abort pipeline

## Error: "Repository Too Large (10,000+ files)"
Cause: Monorepo or very large codebase
Solution:
1. Increase zone capping to split aggressively (sub-zones of ~50 files)
2. Prioritize zones most relevant to our toolkit (skills, agents, hooks, docs)
3. Deprioritize vendor, generated, and third-party code zones
4. Note incomplete coverage in the final report

## Error: "Agent Timed Out in Phase 2/5"
Cause: Zone too large, agent stuck on binary/generated files
Solution:
1. Proceed with results from completed agents (minimum 75% required)
2. Note which zones/audits were incomplete in the report
3. If below 75%, retry failed zones with smaller file batches

## Error: "No Gaps Found"
Cause: External repo covers the same ground or less than ours
Solution:
1. This is a valid outcome, not an error
2. Report confirms our toolkit already covers or exceeds the external repo
3. Note any interesting alternative approaches even if not gaps
4. Skip Phase 5 (no recommendations to audit)

## Error: "Self-Inventory Agent Failed"
Cause: Our own repo structure changed or agent timed out
Solution:
1. Fall back to reading `skills/INDEX.json` for skill counts
2. Use `ls agents/ hooks/ scripts/` for basic counts
3. Note that self-inventory is approximate in the report
