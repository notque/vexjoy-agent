# /do Routing Table Format Specification

## Table Structure

All routing tables in commands/do.md follow markdown pipe table format:

```
| Column 1 Header | Column 2 Header | Column 3 Header | Column 4 (Optional) |
|-----------------|-----------------|-----------------|---------------------|
| Entry 1         | Entry 2         | Entry 3         | Entry 4             |
```

## Intent Detection Patterns Table

**Header:**
```
| User Says | Route To | Complexity |
|-----------|----------|------------|
```

**Entry Format:**
```
| "trigger phrase", "alternate phrase" | tool-name type | Level | [AUTO-GENERATED] |
```

**Example:**
```
| "lint", "format", "style check" | code-linting skill via /lint | Simple | [AUTO-GENERATED]
```

**Rules:**
- Multiple trigger phrases separated by commas in quotes
- Route target includes type (skill/agent/command)
- Complexity: Trivial, Simple, Medium, Complex
- AUTO-GENERATED marker in 4th column for automated entries
- Alphabetical order by first trigger phrase

## Domain-Specific Routing Table

**Header:**
```
| Domain Mentioned | Agent | Typical Complexity |
|-----------------|-------|-------------------|
```

**Entry Format:**
```
| Keyword1, Keyword2 | agent-name | Level | [AUTO-GENERATED] |
```

**Example:**
```
| Go, Golang, gofmt | golang-general-engineer | Medium-Complex | [AUTO-GENERATED]
```

**Rules:**
- Domain keywords comma-separated
- Agent name only (no "agent" suffix in cell)
- Complexity can be ranges: Medium-Complex
- AUTO-GENERATED marker in 4th column
- Alphabetical order by primary domain keyword

## Task Type Routing Table

**Header:**
```
| Task Type | Route To Agent | Complexity |
|-----------|----------------|------------|
```

**Entry Format:**
```
| "action phrase", "alternate phrase" | agent-name agent | Level | [AUTO-GENERATED] |
```

**Example:**
```
| "create agent", "new agent", "design agent" | skill-creator | Complex | [AUTO-GENERATED]
```

## Combination Routing Table

**Header:**
```
| Task Type | Combination | Complexity |
|-----------|-------------|------------|
```

**Entry Format:**
```
| "task description" | primary-tool + secondary-tool | Level | [AUTO-GENERATED] |
```

**Example:**
```
| "Add feature with tests" | workflow-orchestrator + test-driven-development | Complex | [AUTO-GENERATED]
```

## Auto-Generated Marker

**Purpose:** Distinguish automated entries from manual entries

**Format:** `[AUTO-GENERATED]` in 4th column (or 3rd if table has 3 columns)

**Detection Rule:**
```python
is_auto_generated = "[AUTO-GENERATED]" in row
```

**Preservation Rule:** Only update rows with AUTO-GENERATED marker, preserve all others

## Ordering Rules

**Within Tables:**
- Alphabetical by primary pattern/keyword
- Case-insensitive sorting
- Special characters after alphanumeric

**Exception:** Manual entries maintain their original position if not auto-generated
