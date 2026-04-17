# Review Detection Commands

> **Scope**: Concrete grep/rg commands for finding issues each perspective is responsible for flagging. Use these during the VERIFY phase before drafting findings.
> **Version range**: All languages (language-specific variants noted inline)
> **Generated**: 2026-04-14 — adapt file extensions to match the repository under review

---

## Overview

Each perspective has a natural class of defects it should find. The commands below turn perspective intuition into repeatable detection — run them before drafting findings so evidence comes from the actual codebase, not recall. Findings backed by grep output are harder to argue away than findings backed by "I noticed."

---

## Newcomer Perspective — Documentation & Clarity Gaps

Newcomers flag things that make the codebase harder to enter. These commands surface the most common entry barriers.

### Undocumented public exports

```bash
# Python: exported functions/classes missing docstrings
rg 'def [A-Z][a-z]|^class [A-Z]' --type py -l | xargs -I{} python3 -c "
import ast, sys
with open('{}') as f: tree = ast.parse(f.read())
for n in ast.walk(tree):
    if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and not ast.get_docstring(n):
        print(f'{}: {n.name}:{n.lineno}')
" 2>/dev/null

# Go: exported identifiers without doc comments
rg '^func [A-Z]|^type [A-Z]|^var [A-Z]|^const [A-Z]' --type go | rg -v '// '

# TypeScript/JS: exported functions without JSDoc
rg 'export (function|const|class|async function) ' --type ts | rg -v '/\*\*'
```

### Magic numbers (no symbolic name)

```bash
# Find numeric literals that aren't 0, 1, or -1
rg '[^0-9]\b([2-9][0-9]{2,}|[0-9]{4,})\b' --type py --type ts --type go -n
```

**Detection note**: Magic numbers above are candidates, not findings — confirm each one lacks a named constant before flagging.

### TODO/FIXME/HACK comments indicating unfinished work

```bash
rg 'TODO|FIXME|HACK|XXX|TEMP|KLUDGE' --type py --type ts --type go --type js -n
rg 'todo!|unimplemented!|todo_or_die' --type rs -n
```

### Long functions (complexity proxy)

```bash
# Functions over 50 lines (approximate — adjust threshold)
awk '/^def |^func |^function /{start=NR} start && NR-start==50{print FILENAME ":" start " (50+ lines)"}' **/*.py **/*.go **/*.ts 2>/dev/null

# Go: quick approximation
rg -c '^func ' --type go | sort -t: -k2 -rn | head -20
```

---

## Skeptical Senior Perspective — Production Readiness

Senior reviewers look for what fails silently in production. These commands find the most common silent killers.

### Missing error handling

```bash
# Go: errors discarded with _ (silent failures)
rg '\b_, err\b' --type go -n
rg 'if err != nil' --type go -c  # compare to _ usage above

# Python: bare except clauses (catches everything including SystemExit)
rg 'except\s*:' --type py -n

# TypeScript: promise chains without .catch()
rg '\.then\(' --type ts | rg -v '\.catch\('
```

### Missing timeouts on network calls

```bash
# Go: http.Get/http.Post without a timeout context
rg 'http\.Get\(|http\.Post\(' --type go -n

# Python: requests without timeout parameter
rg 'requests\.(get|post|put|delete|patch)\(' --type py | rg -v 'timeout='
```

### Check-then-act race conditions

```bash
# Python: os.path.exists followed by open (TOCTOU)
rg 'os\.path\.exists' --type py -n -A 3 | grep -A3 'exists' | grep 'open\('

# Go: sync/mutex missing on shared state (heuristic)
rg 'var\s+\w+\s+map\[' --type go | rg -v 'sync\.'
```

### N+1 query patterns

```bash
# Django ORM: queries inside loops
rg '\.objects\.(get|filter|all)\(' --type py -n -B 5 | grep -B5 'for '

# SQLAlchemy: session.query inside for
rg 'session\.query' --type py -B 5 | grep -B5 'for '

# Go/GORM: queries in loop
rg '\.Find\|\.First\|\.Where' --type go -B 3 | grep -B3 'for '
```

### Debug artifacts left in code

```bash
rg 'console\.log\(' --type ts --type js -n
rg 'fmt\.Println\|log\.Println' --type go -n | rg -v '_test\.go'
rg 'print\(|pprint\(' --type py -n | rg -v '# '
rg 'debugger;' --type ts --type js -n
rg 'binding\.pry|byebug|pp ' --type rb -n
```

### Hardcoded credentials or secrets

```bash
rg '(password|secret|api_key|token)\s*=\s*["'"'"'][^"'"'"']+["'"'"']' --type py --type ts --type go -in
rg 'Authorization.*Bearer [A-Za-z0-9+/]{20,}' -in
```

---

## Pedant Perspective — Spec Compliance & Terminology

Pedants verify technical correctness against specs. These commands find common spec violations.

### HTTP status code misuse (RFC 7231)

```bash
# 200 OK on error paths
rg '(status|StatusCode)\s*(=|:)\s*200' --type ts --type py --type go -n -A 2 | grep -A2 '200' | grep -i 'error\|fail\|err'

# Wrong method for mutation (GET with side effects)
rg 'router\.(get|GET)\(' --type ts | rg -v '#'  # review manually for mutations
```

### REST conventions

```bash
# POST endpoints returning 200 instead of 201
rg 'router\.(post|POST)\(' --type ts --type py -n -A 10 | grep -A10 'post' | grep '200'

# PUT used for partial update (should be PATCH)
rg 'router\.(put|PUT)\(' --type ts --type py -n
```

### JWT claim misuse (RFC 7519)

```bash
# Custom claims where standard claims exist (sub, iss, aud, exp, iat)
rg '"userId"|"user_id"|"userName"' --type ts --type py -n | rg -v 'sub'
```

### SemVer violations in package manifests

```bash
# Breaking changes in minor version bumps (heuristic — find removed exports)
git diff HEAD~1 HEAD -- '*.ts' '*.py' | grep '^-export ' | head -20
git diff HEAD~1 HEAD -- 'package.json' | grep '"version"'
```

---

## Contrarian Perspective — Unnecessary Complexity

Contrarians look for complexity that doesn't earn its keep.

### Abstraction layers with single implementations

```bash
# Interfaces implemented exactly once (Python protocol/ABC)
rg 'class \w+\(Protocol\)|class \w+\(ABC\)' --type py -l | while read f; do
  rg "class \w+\($(rg 'class (\w+)\(' "$f" | head -1 | sed 's/.*class \(\w\+\).*/\1/')\)" --type py -l | wc -l
done

# Go: interfaces with one implementor
rg 'type \w+ interface' --type go -n
```

### Copy-pasted code blocks (duplication without abstraction)

```bash
# Find 5-line blocks that appear more than twice
rg --count '(def |function |func )' --type py --type ts --type go | sort -t: -k2 -rn | head -20
```

### Unused flags, config keys, or feature toggles

```bash
rg 'feature_flag|FeatureFlag|feature_toggle' --type py --type ts --type go -n
rg 'os\.environ\.get\(' --type py -n | head -30  # audit for unchecked values
```

### Deep nesting (complexity indicator)

```bash
# Python: functions with 4+ levels of indentation
rg '^\s{16,}' --type py -n | rg 'if |for |while ' | head -20

# TypeScript: callback nesting
rg '^\s{12,}' --type ts -n | rg 'then\(' | head -20
```

---

## User Advocate Perspective — User-Facing Impact

User advocates flag changes that break users or increase their cognitive load.

### Breaking API changes (removed or renamed exports)

```bash
# Removed exports since last release
git diff main HEAD -- '*.ts' '*.py' | grep '^-export ' | grep -v '//'

# Renamed functions (old name referenced in tests or docs)
git log --oneline -20 -- '*.ts' '*.py'  # scan for "rename" in commits
```

### Missing user-facing error messages

```bash
# Generic internal errors exposed to users
rg '"Internal Server Error"|"Something went wrong"' --type ts --type py -n | grep -v 'test'

# Errors without user guidance (just a code, no message)
rg 'throw new Error\(|raise Exception\(' --type ts --type py -n | rg -v '[A-Z][a-z].*[a-z]{10}'
```

### Loading states and error boundaries missing

```bash
# React: async operations without loading state
rg 'useEffect' --type tsx --type jsx -n -A 5 | grep -A5 'fetch\|axios\|api' | rg -v 'loading\|isLoading\|pending'
```

### Non-obvious UX: empty states not handled

```bash
# Array renders without empty-state fallback
rg '\.map\(' --type tsx --type jsx -n -B 2 | grep -B2 '\.map\(' | rg -v 'length|empty|fallback|\?\.'
```

---

## Meta-Process Perspective — Structural Health

Meta-process reviewers map structural fragility that no single file reveals.

### Single points of failure: high fan-in modules

```bash
# Files imported by many others (fan-in)
rg 'from \.\./\.\.' --type ts --type py | awk -F'from' '{print $2}' | sort | uniq -c | sort -rn | head -10

# Go: packages with high import count
rg '"github\.com/[^"]+/([^"]+)"' --type go --only-matching | sort | uniq -c | sort -rn | head -10
```

### Authority concentration: single config owners

```bash
# Single config file controlling broad behavior
find . -name 'config.*' -o -name '*.config.*' | xargs wc -l 2>/dev/null | sort -rn | head -5

# Catch-all routing that silences failures
rg 'catch.*\{\s*\}|except:\s*pass' --type py --type ts -n
```

### Reversibility: schema migrations without rollback

```bash
# Migration files without down() or rollback
rg 'def up\|async up\|exports\.up' --include='*migration*' -l | while read f; do
  grep -L 'def down\|async down\|exports\.down' "$f" 2>/dev/null && echo "NO ROLLBACK: $f"
done

# ALTER TABLE without corresponding rollback
grep -r 'ALTER TABLE\|DROP COLUMN\|DROP TABLE' migrations/ 2>/dev/null
```

### Hidden global state

```bash
# Python: module-level mutable state
rg '^[a-z_]+ = \[\]|^[a-z_]+ = \{\}|^[a-z_]+ = 0' --type py -n | rg -v '^#|test'

# Go: package-level vars (mutable globals)
rg '^var [a-z]' --type go -n | rg -v '_test\.go'

# TypeScript: module-level mutable state
rg '^let [a-z]|^var [a-z]' --type ts -n | rg -v 'export '
```

---

## Detection Commands Reference

Quick reference — copy and run before drafting any perspective's findings:

```bash
# === NEWCOMER ===
rg 'TODO|FIXME|HACK|XXX' --type py --type ts --type go -n
rg 'def [A-Z][a-z]|^class [A-Z]' --type py -n  # then check docstrings

# === SKEPTICAL SENIOR ===
rg '\b_, err\b' --type go -n
rg 'except\s*:' --type py -n
rg 'console\.log\(' --type ts -n
rg '(password|secret|api_key)\s*=\s*["'"'"']' -in

# === PEDANT ===
git diff HEAD~1 HEAD -- '*.ts' '*.py' | grep '^-export '
rg '(status|StatusCode)\s*(=|:)\s*200' -n -A2 | grep 'error\|err'

# === CONTRARIAN ===
rg 'type \w+ interface' --type go -n
rg '^[a-z_]+ = \[\]|^[a-z_]+ = \{\}' --type py -n

# === USER ADVOCATE ===
git diff main HEAD -- '*.ts' '*.py' | grep '^-export '
rg '"Internal Server Error"' --type ts --type py -n

# === META-PROCESS ===
rg 'catch.*\{\s*\}|except:\s*pass' --type py --type ts -n
grep -r 'ALTER TABLE\|DROP TABLE' migrations/ 2>/dev/null
```

---

## Anti-Pattern: Running Perspective Without Detection Pass

**Detection**:
```bash
# Check if the review output cites file:line evidence
grep -c 'File:\|Where:\|:\d\+:' review_output.md 2>/dev/null || echo "No line references found"
```

**What it looks like**: A review with findings like "the code seems complex" or "error handling may be insufficient" — no file reference, no line number, no grep evidence.

**Why wrong**: Vague findings are unfalsifiable. The author cannot verify them, cannot rebut them, and cannot be sure what to fix. Evidence-free reviews waste everyone's time.

**Do instead:** Before writing any finding, run the relevant detection command above. If the finding cannot be grounded in a file:line reference, it does not meet the `Evidence-Based Critique` hardcoded behavior.

---

## See Also

- `contrarian.md` — Premise validation, alternative discovery, YAGNI analysis
- `skeptical-senior.md` — Production readiness checklist, edge case taxonomy
- `pedant.md` — Spec references (RFC 7231, RFC 7519, SemVer)
- `meta-process.md` — Five-lens framework for structural health
