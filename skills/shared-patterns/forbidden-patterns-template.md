# FORBIDDEN Patterns Template

Template for adding domain-specific forbidden patterns to agents. These are hard gates that cause automatic rejection.

## Purpose

FORBIDDEN patterns are anti-patterns so problematic that code containing them should be rejected during review. They represent:
- Security vulnerabilities
- Reliability risks
- Maintainability nightmares
- Violations of core principles

## Template for Agents

Add this section to domain-specific agents:

```markdown
## FORBIDDEN Patterns (HARD GATE)

Before writing or reviewing code, check for these patterns. If found:
1. STOP - Do not proceed with implementation
2. REPORT - Flag to user with explanation
3. FIX - Remove the pattern before continuing

| Pattern | Why FORBIDDEN | Correct Alternative |
|---------|---------------|---------------------|
| [anti-pattern code] | [consequence] | [correct approach] |
| [anti-pattern code] | [consequence] | [correct approach] |

### Detection

When reviewing code, grep for these patterns:
- `pattern1` - [what it indicates]
- `pattern2` - [what it indicates]

### Exceptions

The ONLY acceptable exceptions:
- [Exception 1]: [when and why]
- [Exception 2]: [when and why]

If no exception applies, the pattern is FORBIDDEN. No rationalization.
```

## Example: Go Agent

```markdown
## FORBIDDEN Patterns (HARD GATE)

| Pattern | Why FORBIDDEN | Correct Alternative |
|---------|---------------|---------------------|
| `fmt.Println()` | No structure, unsearchable logs | Structured logger |
| `log.Fatal()` | Exits without cleanup, breaks graceful shutdown | Return error, let main handle |
| `panic()` in business logic | Crashes entire service | Return error |
| `_, _ = fn()` (ignored errors) | Silent failures, data corruption | Handle or explicitly document why safe |
| `// TODO: fix later` | Technical debt that compounds | Fix now or create tracked issue |

### Detection
```bash
grep -rn "fmt.Print\|log.Fatal\|panic(" --include="*.go" | grep -v "_test.go"
```

### Exceptions
- `panic()` in `init()` functions for unrecoverable startup failures
- `fmt.Print` in CLI tools (not services)
```

## Example: Python Agent

```markdown
## FORBIDDEN Patterns (HARD GATE)

| Pattern | Why FORBIDDEN | Correct Alternative |
|---------|---------------|---------------------|
| `except:` (bare except) | Catches SystemExit, KeyboardInterrupt | `except Exception:` |
| `eval(user_input)` | Code injection vulnerability | Parse safely |
| `pickle.loads(untrusted)` | Arbitrary code execution | Use JSON |
| `# type: ignore` without comment | Hides real type errors | Fix the type or document why |
| `assert` for validation | Disabled in production (-O) | Raise ValueError |
```

## Example: Security Agent

```markdown
## FORBIDDEN Patterns (HARD GATE)

| Pattern | Why FORBIDDEN | Correct Alternative |
|---------|---------------|---------------------|
| SQL string concatenation | SQL injection | Parameterized queries |
| `dangerouslySetInnerHTML` | XSS vulnerability | Sanitize or use text content |
| Hardcoded secrets | Credential exposure | Environment variables / secrets manager |
| `http://` in production | Man-in-the-middle | Always HTTPS |
| `*` CORS origin | Cross-origin attacks | Specific allowed origins |
```

## Integration with Agent Creator

When creating agents, include:

1. **Domain-specific FORBIDDEN patterns** (3-10 patterns)
2. **Detection commands** (grep patterns to find violations)
3. **Clear exceptions** (when pattern is acceptable)
4. **Hard gate enforcement** (STOP, REPORT, FIX workflow)

## Relationship to Anti-Rationalization

FORBIDDEN patterns complement anti-rationalization:

- **Anti-rationalization**: Prevents skipping verification steps
- **FORBIDDEN patterns**: Prevents specific code patterns

Both are hard gates. Neither can be rationalized away.
