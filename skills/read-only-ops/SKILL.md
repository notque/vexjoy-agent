---
name: read-only-ops
description: |
  Read-only exploration, status checks, and reporting without modifications.
  Use when user asks to check status, find files, search code, show state,
  or explicitly requests read-only investigation. Do NOT use when user wants
  changes, fixes, refactoring, or any write operation.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
routing:
  triggers:
    - "check status"
    - "explore code"
    - "read-only"
  category: process
---

# Read-Only Operations Skill

## Operator Context

This skill operates as an operator for safe exploration and reporting, configuring Claude's behavior to NEVER modify files or system state during investigation. It implements the **Observation Only** architectural pattern -- gather evidence, report facts, never alter state.

### Hardcoded Behaviors (Always Apply)
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md files before exploration
- **Over-Engineering Prevention**: Only explore what is directly requested. No speculative investigations or comprehensive audits unless explicitly asked
- **NEVER use Write or Edit tools**: Under no circumstances modify files
- **NEVER run destructive Bash commands**: No rm, mv, cp, mkdir, kill, touch, or write redirects (>, >>)
- **NEVER modify databases**: Only SELECT queries; never INSERT, UPDATE, DELETE, or DROP
- **NEVER modify git state**: No add, commit, push, checkout, or reset commands
- **Show complete output**: Display full command results; never summarize away details the user needs to verify

### Default Behaviors (ON unless disabled)
- **Structured reporting**: Lead with key findings summary, details below
- **List files examined**: Document which files were read for transparency
- **Include timestamps**: Show when status was captured for time-sensitive checks
- **Scope confirmation**: Confirm scope before broad searches to avoid wasting tokens
- **Temporary file cleanup**: Remove any temp files created during exploration at task end

### Optional Behaviors (OFF unless enabled)
- **Deep exploration**: Recursively examine nested directories and dependencies
- **Performance metrics**: Include timing information for operations
- **Diff comparison**: Compare current state against known baselines

## What This Skill CAN Do
- Read files, search codebases, and report findings
- Run read-only Bash commands (ls, ps, git status, git log, du, df, curl GET)
- Execute SELECT queries against databases
- Produce structured status reports with evidence

## What This Skill CANNOT Do
- Modify, create, or delete any files
- Run destructive or state-changing Bash commands
- Execute write operations against databases
- Install, remove, or update packages
- Alter git state in any way

---

## Instructions

### Phase 1: SCOPE

**Goal**: Understand exactly what the user wants to know before exploring.

**Step 1: Parse the request**
- What specific information is the user asking for?
- What is the target scope (specific file, directory, service, system-wide)?
- Are there implicit constraints (time range, file type, component)?

**Step 2: Confirm scope if ambiguous**

If the request could match dozens of results or span the entire filesystem, clarify before proceeding. If the scope is clear, proceed directly.

**Gate**: Scope is understood. Target locations are identified. Proceed only when gate passes.

### Phase 2: GATHER

**Goal**: Collect evidence using read-only tools.

**Step 1: Execute read-only operations**

Allowed commands:
```
ls, find, wc, du, df, file, stat
ps, top -bn1, uptime, free, pgrep
git status, git log, git diff, git show, git branch
sqlite3 ... "SELECT ..."
curl -s (GET only)
date, timedatectl, env
```

Forbidden commands:
```
mkdir, rm, mv, cp, touch, chmod, chown
git add, git commit, git push, git checkout, git reset
echo >, cat >, tee (file writes)
INSERT, UPDATE, DELETE, DROP, ALTER SQL
npm install, pip install, apt install
pkill, kill, systemctl restart/stop
```

**Step 2: Record raw output**

Show complete command output. Do not paraphrase or truncate unless output exceeds reasonable display length, in which case show representative samples with counts.

**Gate**: All requested data has been gathered with read-only commands. No state was modified. Proceed only when gate passes.

### Phase 3: REPORT

**Goal**: Present findings in a structured, verifiable format.

**Step 1: Summarize key findings at the top**

Lead with what the user asked about. Answer the question first, then provide supporting details.

**Step 2: Show evidence**

Include command output, file contents, or search results that support the summary. The user must be able to verify claims from the evidence shown.

**Step 3: List files examined**

```markdown
### Files Examined
- `/path/to/file1` - why it was read
- `/path/to/file2` - why it was read
```

**Gate**: Report answers the user's question with verifiable evidence. All claims are supported by shown output.

---

## Error Handling

### Error: "Attempted to use Write or Edit tool"
Cause: Skill boundary violation -- tried to modify a file
Solution: This skill only permits Read, Grep, Glob, and read-only Bash. Report findings verbally; do not write them to files unless the user explicitly grants permission.

### Error: "Bash command would modify state"
Cause: Attempted destructive or state-changing command
Solution: Use the read-only equivalent (e.g., `ls -la` instead of `mkdir -p`, `git status` instead of `git add`, `SELECT` instead of `INSERT`).

### Error: "Scope too broad, results overwhelming"
Cause: Search returned hundreds of matches without filtering
Solution: Return to Phase 1. Narrow scope by file type, directory, or pattern before re-executing.

---

## Anti-Patterns

### Anti-Pattern 1: Investigating Everything
**What it looks like**: User asks about API server status; Claude audits all services, configs, logs, and dependencies
**Why wrong**: Wastes tokens, buries the answer, scope was never that broad
**Do instead**: Answer the specific question. Offer to investigate further if needed.

### Anti-Pattern 2: Summarizing Away Evidence
**What it looks like**: "The repository has 3 modified files and is clean" instead of showing `git status` output
**Why wrong**: User cannot verify the claim. Missing details (which files? staged or unstaged?)
**Do instead**: Show complete command output. Let the user draw conclusions.

### Anti-Pattern 3: Modifying State "Just to Check"
**What it looks like**: Running `mkdir -p /tmp/test` to check if a path is writable
**Why wrong**: Creates state change. Violates read-only constraint absolutely.
**Do instead**: Use `ls -la`, `stat`, or `[ -d /path ] && echo exists` for read-only checks.

### Anti-Pattern 4: Exploring Before Scoping
**What it looks like**: User says "find config files"; Claude immediately searches entire filesystem
**Why wrong**: May return hundreds of irrelevant results. Wastes time without direction.
**Do instead**: Confirm scope (which config? where? what format?) then search targeted locations.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "I'll just quickly create a temp file to store results" | Any file creation violates read-only constraint | Report findings in response text only |
| "This git command is harmless" | Only explicitly allowed git commands are safe | Check against allowed list before running |
| "The user probably wants me to fix this too" | Read-only means observe and report, never act | Report findings, let user decide next steps |
| "I'll summarize to save space" | Summaries hide details the user needs to verify | Show complete output, summarize at top |
