# Routing Table Updater — Skill Examples

### Example 1: New Skill Created

User creates `skills/api-integration-helper/SKILL.md` via skill-creator:

```yaml
---
name: api-integration-helper
description: Test API integrations with mock responses and validation. Use when "test API", "API integration", or "mock API".
---
```

Actions:
1. SCAN: Detect new file in skills/ directory
2. EXTRACT: Parse frontmatter, extract trigger patterns ["test API", "API integration", "mock API"], complexity Medium
3. GENERATE: Create entry for Intent Detection Patterns table
4. UPDATE: Backup do.md, insert entry alphabetically, validate markdown
5. VERIFY: Run validate.py, confirm no conflicts, all tables intact

Generated routing entry:
```
| "test API", "API integration", "mock API" | api-integration-helper skill | Medium | [AUTO-GENERATED]
```

Result: New skill is discoverable via /do command

---

### Example 2: Agent Description Updated

User updates golang-general-engineer description to add "concurrency" keyword.

Actions:
1. SCAN: Find modified agents/golang-general-engineer.md
2. EXTRACT: Parse updated domain keywords ["Go", "Golang", "gofmt", "Go concurrency"]
3. GENERATE: Update Domain-Specific routing entry with new keywords
4. UPDATE: Backup, replace existing auto-generated entry, preserve manual entries
5. VERIFY: Confirm no new conflicts, all references valid

Updated routing entry:
```diff
-| Go, Golang, gofmt | golang-general-engineer | Medium-Complex | [AUTO-GENERATED]
+| Go, Golang, gofmt, Go concurrency | golang-general-engineer | Medium-Complex | [AUTO-GENERATED]
```

Result: Domain routing expanded to cover new keyword

---

### Example 3: Conflict Detection

Two skills both match "test API" pattern.

Actions:
1. GENERATE phase detects overlap between api-testing-skill and integration-testing-skill
2. Conflict logged with severity assessment (low: both routes reasonable)
3. Resolution: longer pattern "test API integration" takes precedence for integration skill
4. Document conflict in output, apply specificity rule

Resolution applied:
```
| "test API integration" | integration-testing-skill | Medium | [AUTO-GENERATED]
| "test API" | api-testing-skill | Medium | [AUTO-GENERATED]
```

Result: Unambiguous routing with longest-match precedence

---

### Example 4: Manual Entry Preserved

Existing do.md has a hand-curated combination entry (no AUTO-GENERATED marker):
```
| "review Python", "Python quality" | python-general-engineer + python-quality-gate | Medium |
```

Auto-generation produces a simpler entry for "review Python". Because the existing entry lacks the `[AUTO-GENERATED]` marker, it is preserved as-is. The auto-generated entry is skipped for this pattern.

Result: Manual curation respected, no data loss
