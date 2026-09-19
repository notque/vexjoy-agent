# Trigger Phrase Extraction Patterns

## Explicit Trigger Phrases

**Pattern:** Look for quoted phrases in description
```regex
"([^"]+)"
```

**Example:**
```yaml
description: Use when "lint code", "check style", or "format files"
```
**Extracted:** `["lint code", "check style", "format files"]`

## "Use when" Clauses

**Pattern:** Extract content after "Use when" keyword
```regex
(?:Use when|Trigger on|Invoke for)\s+(.+?)(?:\.|$)
```

**Example:**
```yaml
description: Automate testing. Use when running unit tests or integration tests.
```
**Extracted:** `["running unit tests", "integration tests"]`

## Action Verbs + Domain

**Pattern:** Match action verb + domain noun
```regex
(debug|fix|test|review|analyze|generate|create)\s+(\w+)
```

**Example:**
```yaml
description: Debug Go applications with systematic approach
```
**Extracted:** `["debug Go", "debug applications"]`

## Skill Purpose Keywords

**Common Keywords Map:**
- "lint", "format" → code quality checking
- "test", "TDD" → testing workflows
- "review", "audit" → code review
- "debug", "fix" → troubleshooting
- "refactor", "restructure" → code improvement
- "generate", "create" → code generation

**Example:**
```yaml
description: Lint Python code with ruff and mypy
```
**Extracted:** `["lint", "lint Python", "ruff", "mypy"]`

## Domain Keywords (Agents)

**Pattern:** Extract technology names
```regex
(Go|Python|TypeScript|React|Kubernetes|Docker|PostgreSQL|etc)
```

**Example:**
```yaml
description: Deep expertise in Go development, architecture, debugging
```
**Extracted:** `["Go", "Go development", "Go architecture", "Go debugging"]`

## Complexity Inference

**Simple:** Single action, tool wrapper, formatting
**Medium:** Multi-step, requires configuration, domain-specific
**Complex:** Orchestration, multi-tool, requires planning

**Keywords:**
- Simple: "quick", "simple", "check", "run"
- Medium: "comprehensive", "systematic", "analyze"
- Complex: "orchestrate", "coordinate", "plan"

## Fallback Strategy

If no explicit patterns found:
1. Use first sentence of description
2. Extract noun phrases
3. Default to skill/agent name as pattern
4. Mark complexity as Medium (conservative default)
