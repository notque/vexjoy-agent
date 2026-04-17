# Agent Comparison — Error Handling

## Error: "Agent Type Not Found"

Cause: Agent not registered or name misspelled

Solution: Verify agent file exists in agents/ directory. Restart Claude Code client to pick up new definitions.

---

## Error: "Tests Fail with Race Condition"

Cause: Concurrent code has data races

Solution: This is a real quality difference. Record as a finding in the grade. Record as a finding for the agent being tested.

---

## Error: "Different Test Counts Between Agents"

Cause: Agents wrote different test suites

Solution: Valid data point. Grade on test coverage and quality, not raw count. More tests is not always better.

---

## Error: "Timeout During Agent Execution"

Cause: Complex task taking too long or agent stuck in retry loop

Solution: Note the timeout and number of retries attempted. Record as incomplete with partial metrics. Increase timeout limit if warranted, but excessive retries are a quality signal — an agent that needs many retries is less efficient regardless of final outcome.
