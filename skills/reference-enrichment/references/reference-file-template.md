# Reference File Template

Use this template when generating new reference files in Phase 3 COMPILE.
Replace `{{PLACEHOLDER}}` markers with actual content. Delete sections that don't apply
to the domain — a focused 80-line file beats a padded 300-line file.

---

# {{DOMAIN}} Reference

> **Scope**: {{ONE-SENTENCE description of what this file covers and what it doesn't}}
> **Version range**: {{e.g., "Go 1.18+", "Python 3.11+", "all versions"}}
> **Generated**: {{YYYY-MM-DD}} — verify version-specific content against current release notes

---

## Overview

{{2-4 sentences explaining the sub-domain: what problem it solves, why it matters for this
agent's work, and what the most common failure mode is. Be specific — mention the language,
framework, or tool by name.}}

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `{{function_or_construct}}` | `{{X.Y+}}` | {{condition}} | {{counter-condition}} |
| `{{function_or_construct}}` | `{{X.Y+}}` | {{condition}} | {{counter-condition}} |

*Delete this table if the domain has no version-specific API surface.*

---

## Correct Patterns

### {{Pattern Name}}

{{One sentence: what this pattern does and why it's correct.}}

```{{language}}
// {{comment explaining the key point}}
{{correct code example — copy-pasteable, not pseudocode}}
```

**Why**: {{Behavioral explanation — what breaks if you don't follow this.}}

---

### {{Pattern Name}}

```{{language}}
{{correct code example}}
```

**Why**: {{Explanation.}}

---

## Anti-Pattern Catalog

### ❌ {{Anti-Pattern Name}}

**Detection**:
```bash
grep -rn '{{pattern}}' --include="*.{{ext}}"
rg '{{pattern}}' --type {{lang}}
```

**What it looks like**:
```{{language}}
{{bad code example — should be something grep above would find}}
```

**Why wrong**: {{Behavioral consequence — what actually breaks, not just "it's bad practice".
Mention the specific failure mode: data loss, silent error, performance degradation, etc.}}

**Fix**:
```{{language}}
{{corrected code example}}
```

**Version note**: {{If behavior changed in a specific version, state it here. Otherwise delete.}}

---

### ❌ {{Anti-Pattern Name}}

**Detection**:
```bash
grep -rn '{{pattern}}' --include="*.{{ext}}"
```

**What it looks like**:
```{{language}}
{{bad code}}
```

**Why wrong**: {{Consequence.}}

**Fix**:
```{{language}}
{{fix}}
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `{{exact error text or regex}}` | {{why it occurs}} | {{what to change}} |
| `{{exact error text or regex}}` | {{why it occurs}} | {{what to change}} |

*Delete this table if the domain has no common error messages.*

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| `{{X.Y}}` | {{What changed}} | {{How it affects code using this pattern}} |
| `{{X.Y}}` | {{What changed}} | {{How it affects code using this pattern}} |

*Delete this table if no significant version changes exist for this domain.*

---

## Detection Commands Reference

Quick collection of all grep/rg commands from this file:

```bash
# {{Anti-pattern 1 name}}
grep -rn '{{pattern1}}' --include="*.{{ext}}"

# {{Anti-pattern 2 name}}
rg '{{pattern2}}' --type {{lang}}
```

---

## See Also

- `{{other-reference.md}}` — {{what it covers}}
- {{Official docs URL if applicable}}

---

## Template Usage Notes

**Minimum for Level 2**: Overview + one correct pattern with code block + one anti-pattern entry.

**Minimum for Level 3**: All of the above + at least one detection command per anti-pattern +
error-fix mappings table (if the domain has common errors) + version notes (if API changed).

**Line count target**: 80-200 lines for a focused sub-domain. If you need more than 300 lines,
split into two files covering narrower sub-domains.

**What NOT to include**:
- Generic advice ("follow best practices", "be careful with...")
- Patterns that apply to every language (not domain-specific)
- Content that duplicates what's already in the agent body
- Aspirational content ("in the future, consider...")
