# Routing Table Update Examples

## Example 1: New Skill Added

**Skill Created:**
```yaml
# skills/database-migration-helper/SKILL.md
---
name: database-migration-helper
description: Generate and validate database migrations. Use when "migrate database", "create migration", or "schema change"
version: 1.0.0
---
```

**Extracted Metadata:**
```json
{
  "type": "skill",
  "name": "database-migration-helper",
  "trigger_patterns": ["migrate database", "create migration", "schema change"],
  "complexity": "Medium",
  "routing_table": "Intent Detection Patterns"
}
```

**Generated Routing Entry:**
```markdown
| "migrate database", "create migration", "schema change" | database-migration-helper skill | Medium | [AUTO-GENERATED]
```

**Diff in do.md:**
```diff
 | "lint", "format", "style check" | code-linting skill via /lint | Simple |
+| "migrate database", "create migration", "schema change" | database-migration-helper skill | Medium | [AUTO-GENERATED]
 | "verify", "make sure", "check before" | verification-before-completion skill | Simple |
```

---

## Example 2: Agent Description Updated

**Original Agent:**
```yaml
# agents/golang-general-engineer.md
---
name: golang-general-engineer
description: Deep expertise in Go development
version: 2.3.0
---
```

**Updated Agent:**
```yaml
# agents/golang-general-engineer.md
---
name: golang-general-engineer
description: Deep expertise in Go development, architecture, debugging, concurrency
version: 2.4.0
---
```

**Changed Domain Keywords:**
```diff
-["Go", "Go development"]
+["Go", "Go development", "Go architecture", "Go debugging", "Go concurrency"]
```

**Updated Routing Entry:**
```diff
-| Go, Golang, gofmt | golang-general-engineer | Medium-Complex |
+| Go, Golang, gofmt, Go architecture, Go debugging, Go concurrency | golang-general-engineer | Medium-Complex | [AUTO-GENERATED]
```

---

## Example 3: Conflict Detection

**Scenario:** Two skills with overlapping patterns

**Skill 1:**
```yaml
name: api-testing-skill
description: Test REST APIs. Use when "test API"
```

**Skill 2:**
```yaml
name: integration-testing-skill
description: Run integration tests. Use when "test integration", "test API integration"
```

**Conflict Detected:**
```json
{
  "pattern": "test API",
  "routes": [
    "api-testing-skill",
    "integration-testing-skill (as substring of 'test API integration')"
  ],
  "severity": "low",
  "resolution": "Longer pattern 'test API integration' takes precedence"
}
```

**Resolution Applied:**
```markdown
| "test API integration" | integration-testing-skill | Medium | [AUTO-GENERATED]
| "test API" | api-testing-skill | Medium | [AUTO-GENERATED]
```

**Note:** Pattern matching checks longest match first, so "test API integration" will match integration-testing-skill.

---

## Example 4: Manual Entry Preserved

**do.md Before:**
```markdown
| "review Python", "Python quality" | python-general-engineer + python-quality-gate | Medium |
| "review code" | systematic-code-review skill | Medium |
```

**Auto-Generated Entry:**
```markdown
| "review Python" | python-general-engineer | Medium | [AUTO-GENERATED]
```

**Merge Result:**
```markdown
| "review Python", "Python quality" | python-general-engineer + python-quality-gate | Medium |  <!-- Manual entry preserved -->
| "review code" | systematic-code-review skill | Medium | [AUTO-GENERATED]
```

**Explanation:** First entry has no `[AUTO-GENERATED]` marker, so it's preserved as manual. Second entry is auto-generated and was updated.

---

## Example 5: Multiple Table Updates

**New Agent:**
```yaml
# agents/graphql-api-engineer.md
---
name: graphql-api-engineer
description: GraphQL API development and schema design. Expert in Apollo, federation, and performance optimization.
version: 1.0.0
---
```

**Routing Entries Generated:**

**Domain-Specific Routing:**
```markdown
| GraphQL, Apollo, federation | graphql-api-engineer | Medium-Complex | [AUTO-GENERATED]
```

**Task Type Routing:**
```markdown
| "GraphQL schema", "API design", "federation setup" | graphql-api-engineer agent | Medium | [AUTO-GENERATED]
```

**Updates Applied:**
```
✓ Domain-Specific Routing: 1 new entry
✓ Task Type Routing: 1 new entry
Total routing changes: 2 tables updated
```

---

## Example 6: Complexity Change

**Skill Updated:**
```diff
 ---
 name: workflow-orchestrator
-description: Plan complex work
+description: Orchestrate complex multi-step tasks with brainstorming, planning, execution. Use for "orchestrate", "complex task", "multi-step project"
-version: 1.0.0
+version: 1.1.0
 ---
```

**Routing Entry Updated:**
```diff
-| "complex task" | workflow-orchestrator skill | Medium | [AUTO-GENERATED]
+| "orchestrate", "complex task", "multi-step project" | workflow-orchestrator skill | Complex | [AUTO-GENERATED]
```

**Changes:**
- More trigger patterns added
- Complexity escalated from Medium to Complex (reflects expanded scope)
