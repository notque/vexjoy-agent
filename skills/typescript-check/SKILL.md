---
name: typescript-check
description: "TypeScript type checking via tsc --noEmit with actionable error output."
user-invocable: false
allowed-tools:
  - Read
  - Bash
  - Grep
  - Glob
agent: typescript-frontend-engineer
routing:
  triggers:
    - "TypeScript check"
    - "tsc noEmit"
    - "type check TypeScript"
    - "tsc errors"
    - "TypeScript type validation"
  category: code-quality
  pairs_with:
    - vitest-runner
    - code-linting
---

# TypeScript Type Check Skill

Validates TypeScript code via `tsc --noEmit`, parsing errors into structured reports by file. Read-only validation (does not modify code). Linear workflow: locate config, execute compiler, parse output, present results.

Use for: validating before commits, after refactors, checking type regressions. Not for: linting, test execution, runtime errors, projects without tsconfig.json.

---

## Instructions

### Step 1: Verify TypeScript Project

Locate tsconfig.json. Never skip -- tsc without tsconfig falls back to defaults, missing project-specific paths, strict mode, and targets.

```bash
ls tsconfig.json 2>/dev/null || ls */tsconfig.json 2>/dev/null
```

If no tsconfig.json exists, stop and inform the user.

### Step 2: Run Type Check

```bash
npx tsc --noEmit 2>&1
```

- **Exit 0**: No type errors. Report PASS.
- **Exit 1+**: Errors detected. Continue to Step 3.

Do not install TypeScript or dependencies. If not installed, suggest `npm install typescript --save-dev`. This is read-only -- never modify package.json or run installation commands.

### Step 3: Parse Output

For each error line, extract:
- **File path**: .ts/.tsx file (absolute paths for navigation)
- **Line:Column**: Exact location
- **Error code**: TS#### identifier (e.g., TS2322, TS7006)
- **Message**: Human-readable description

Group by file, sort by line number.

### Step 4: Present Results

```
=== TypeScript Type Check ===

Status: PASS / FAIL (N errors)

Errors by File:
---------------

src/components/Button.tsx
  Line 15:3  TS2322  Type 'string' is not assignable to type 'number'
  Line 28:10 TS2339  Property 'foo' does not exist on type 'Props'

src/utils/helpers.ts
  Line 5:1   TS7006  Parameter 'x' implicitly has an 'any' type

Summary: N files, M errors
```

Never auto-fix without explicit user request. Type check is validation -- the user may want to review errors or have a different fix approach.

---

## Error Handling

### Error: "Cannot find tsconfig.json"
Cause: No TypeScript config in project root.
Solution: Search common locations (src/, app/, packages/). If found, re-run with `--project path/to/tsconfig.json`. If not found, inform user.

### Error: "Cannot find module 'typescript'"
Cause: TypeScript not installed.
Solution: Inform user. Suggest `npm install typescript --save-dev`. Do not install automatically.

### Error: "npx: command not found"
Cause: Node.js not installed or not in PATH.
Solution: Check `node --version`. If Node.js present but npx missing, try `npm exec tsc -- --noEmit`. If Node.js missing, inform user.

### Error: "Multiple tsconfig.json files found"
Cause: Monorepo or nested structure.
Solution: List all tsconfig.json files. Ask user which to use. Re-run with `--project path/to/specific/tsconfig.json`.

---

## References

### Common tsc Flags

| Flag | Purpose |
|------|---------|
| `--noEmit` | Type check only, no .js output |
| `--project path` | Use specific tsconfig.json |
| `--skipLibCheck` | Skip .d.ts checking (faster on large projects) |
| `--incremental` | Incremental compilation (faster repeats) |
| `--strict` | Enable all strict checks |

### Integration Points

- **Before pr-workflow commit**: Run type check before committing TypeScript changes
- **With vitest-runner**: Type check first, then tests
- **With code-linting**: Lint first, then type check

### Optional Behaviors (OFF unless enabled)

- **--strict mode**: Additional strict flags beyond tsconfig
- **--project path**: Specific tsconfig.json when multiple exist
- **--skipLibCheck**: Speed up large projects
- **Specific files**: Check named files instead of entire project
