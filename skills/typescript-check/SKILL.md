---
name: typescript-check
description: |
  Run TypeScript type checking with tsc --noEmit and parse errors into
  actionable, file-grouped output. Use when validating TypeScript code before
  commits, after refactors, or when checking for type regressions. Use for
  "type check", "tsc", "TypeScript errors", "type validation", or pre-commit
  TypeScript verification. Do NOT use for linting, test execution, runtime
  errors, or JavaScript-only projects without tsconfig.json.
version: 2.0.0
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
  category: code-quality
---

# TypeScript Type Check Skill

## Operator Context

This skill operates as an operator for TypeScript type validation, configuring Claude's behavior for running `tsc --noEmit` and parsing output into structured, actionable error reports. It implements a **Linear Validation** pattern -- locate config, execute compiler, parse output, present results.

### Hardcoded Behaviors (Always Apply)

- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before running checks
- **Read-Only Validation**: Report errors only; never modify source code unless explicitly requested
- **Complete Output**: Always show full tsc output with file paths, line numbers, and error codes
- **Verify tsconfig.json First**: Confirm tsconfig.json exists before running tsc
- **No Dependency Installation**: Never run npm install, yarn add, or pnpm add

### Default Behaviors (ON unless disabled)

- **Parse Errors**: Convert raw tsc output into structured, file-grouped format
- **Absolute Paths**: Display absolute file paths for direct navigation
- **Group by File**: Organize errors by source file, sorted by line number
- **Exit Code Reporting**: Report PASS (exit 0) or FAIL (exit 1+) with error count
- **Error Code Inclusion**: Include TS#### codes for each error

### Optional Behaviors (OFF unless enabled)

- **--strict mode**: Run with additional strict flags beyond tsconfig settings
- **--project path**: Use a specific tsconfig.json when multiple exist
- **--skipLibCheck**: Add --skipLibCheck to speed up checking on large projects
- **Specific files**: Check only named files instead of entire project

## What This Skill CAN Do

- Run TypeScript type checking on any project with tsconfig.json
- Parse and format tsc error output into actionable, file-grouped reports
- Detect missing type dependencies, bad imports, and configuration issues
- Check specific files or the entire project
- Report pass/fail status with structured error summaries

## What This Skill CANNOT Do

- Auto-fix type errors (this is read-only validation)
- Install dependencies or modify package.json
- Modify tsconfig.json or any project configuration
- Run on projects without tsconfig.json
- Execute tests or perform linting

---

## Instructions

### Step 1: Verify TypeScript Project

Locate tsconfig.json in the project:

```bash
ls tsconfig.json 2>/dev/null || ls */tsconfig.json 2>/dev/null
```

If no tsconfig.json exists, stop and inform the user. Do not proceed without configuration.

### Step 2: Run Type Check

Execute the TypeScript compiler in type-check-only mode:

```bash
npx tsc --noEmit 2>&1
```

Capture the exit code:
- **Exit 0**: No type errors found
- **Exit 1+**: Type errors detected

### Step 3: Parse Output

For each error line in the tsc output, extract:
- **File path**: The .ts/.tsx file containing the error
- **Line:Column**: Exact location in the file
- **Error code**: TS#### identifier (e.g., TS2322, TS7006)
- **Message**: Human-readable error description

### Step 4: Present Results

Format output using this structure:

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

---

## Error Handling

### Error: "Cannot find tsconfig.json"

Cause: No TypeScript configuration in the project root or specified path.
Solution:
1. Search for tsconfig.json in common locations (src/, app/, packages/)
2. If found elsewhere, re-run with `--project path/to/tsconfig.json`
3. If not found anywhere, inform user this requires a TypeScript project

### Error: "Cannot find module 'typescript'"

Cause: TypeScript is not installed as a project dependency.
Solution:
1. Inform user that TypeScript must be installed first
2. Suggest `npm install typescript --save-dev`
3. Do not install it automatically (read-only skill)

### Error: "npx: command not found"

Cause: Node.js toolchain is not installed or not in PATH.
Solution:
1. Verify Node.js is installed: `node --version`
2. If Node.js is present but npx missing, try `npm exec tsc -- --noEmit`
3. If Node.js is missing, inform user to install Node.js

---

## Anti-Patterns

### Anti-Pattern 1: Running Without tsconfig.json

**What it looks like**: Executing `npx tsc --noEmit` in a directory without tsconfig.json
**Why wrong**: tsc falls back to default settings, missing project-specific configuration like paths, strict mode, and compiler targets
**Do instead**: Always verify tsconfig.json exists in Step 1 before running

### Anti-Pattern 2: Suppressing or Summarizing Output

**What it looks like**: Running `npx tsc --noEmit > /dev/null` or reporting only "5 errors found"
**Why wrong**: Users need actual error messages, file paths, and line numbers to fix issues
**Do instead**: Always show complete, structured error output

### Anti-Pattern 3: Auto-Fixing Without Explicit Request

**What it looks like**: Seeing a type error and immediately editing the source file
**Why wrong**: Type check is a read-only validation step; user may want to review errors, may disagree with the fix approach, or may have a different solution in mind
**Do instead**: Present errors clearly; only fix if user explicitly asks

### Anti-Pattern 4: Skipping Exit Code Check

**What it looks like**: Parsing output text without checking the tsc exit code
**Why wrong**: tsc may produce warnings that look like errors, or errors may be incomplete if the process was killed
**Do instead**: Always capture and report the exit code alongside parsed output

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Common tsc Flags

| Flag | Purpose |
|------|---------|
| `--noEmit` | Type check only, do not generate .js files |
| `--project path` | Use specific tsconfig.json |
| `--skipLibCheck` | Skip type checking .d.ts files (faster) |
| `--incremental` | Use incremental compilation (faster for repeat runs) |
| `--strict` | Enable all strict type checks |

### Integration Points

- **Before git-commit-flow**: Run type check before committing TypeScript changes
- **With vitest-runner**: Run type check first, then tests
- **With code-linting**: Run lint first, then type check
