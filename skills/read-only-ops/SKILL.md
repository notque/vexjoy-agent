---
name: read-only-ops
description: "Read-only exploration, inspection, and reporting without modifications."
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
    - "browse code"
    - "inspect only"
  category: process
  pairs_with:
    - codebase-overview
---

# Read-Only Operations Skill

Core principle: **Observation Only**. Gather evidence. Report facts. Keep all state unchanged.

---

## Instructions

### Phase 1: SCOPE

**Step 1: Parse the request**

Determine: what information is needed, target scope (file, directory, service, system-wide), implicit constraints (time range, file type, component).

**Step 2: Confirm scope if ambiguous**

If the request could match dozens of results or span the entire filesystem, clarify before proceeding.

**Gate**: Scope understood. Target locations identified.

---

### Phase 2: GATHER

Collect evidence using read-only tools only.

**Step 1: Execute read-only operations**

**Allowed commands:**
```
ls, find, wc, du, df, file, stat
ps, top -bn1, uptime, free, pgrep
git status, git log, git diff, git show, git branch
sqlite3 ... "SELECT ..."
curl -s (GET only)
date, timedatectl, env
```

**Forbidden commands:**
```
mkdir, rm, mv, cp, touch, chmod, chown
git add, git commit, git push, git checkout, git reset
echo >, cat >, tee (file writes)
INSERT, UPDATE, DELETE, DROP, ALTER SQL
npm install, pip install, apt install
pkill, kill, systemctl restart/stop
```

Even "harmless" state changes violate the boundary. Use read-only equivalents (e.g., `ls -la` not `mkdir -p`, `git status` not `git add`, `SELECT` not `INSERT`).

**Step 2: Record raw output**

Show complete output, truncating only when output exceeds reasonable display length (show representative samples with counts). User must be able to verify claims from shown evidence.

**Gate**: All data gathered with read-only commands. No state modified.

---

### Phase 3: REPORT

**Step 1: Summarize key findings at the top**

Answer the question first, then supporting details.

**Step 2: Show evidence**

Include command output, file contents, or search results supporting the summary. Show raw data.

**Step 3: List files examined**

```markdown
### Files Examined
- `/path/to/file1` - why it was read
- `/path/to/file2` - why it was read
```

**Gate**: Report answers user's question with verifiable evidence. All claims supported by shown output.

---

## Error Handling

### Error: "Attempted to use Write or Edit tool"
**Cause**: Skill boundary violation.
**Solution**: Only Read, Grep, Glob, and read-only Bash permitted. Report findings verbally; write to files only with explicit user permission.

### Error: "Bash command would modify state"
**Cause**: Attempted state-changing command.
**Solution**: Use read-only equivalents: `ls -la` not `mkdir -p`, `git status` not `git add`, `SELECT` not `INSERT`, `stat` not `mkdir -p /tmp/test`.

### Error: "Scope too broad, results overwhelming"
**Cause**: Search returned hundreds of unfiltered matches.
**Solution**: Return to Phase 1. Narrow by file type, directory, or pattern.

### Preferred Patterns

**Investigating Everything**: User asks about API status; you audit all services. Wrong: wastes tokens, buries the answer. Do instead: answer the specific question, offer to investigate further.

**Summarizing Away Evidence**: "3 modified files and is clean" without `git status` output. Wrong: user cannot verify. Do instead: show complete command output.

**Exploring Before Scoping**: User says "find config files"; you search entire filesystem. Wrong: hundreds of irrelevant results. Do instead: confirm scope first, then search targeted locations.
