---
name: security-threat-model
description: |
  Phase-gated security threat model skill. Scans the active toolkit installation
  for attack surface exposure, generates a deny-list config, audits installed
  skills and hooks for supply-chain injection patterns, checks the learning DB
  for poisoned entries, and synthesizes findings into an actionable threat model
  document. Produces concrete artifacts in security/ at each phase. Use when
  assessing security posture of the toolkit installation, onboarding to security
  review, or running a point-in-time supply-chain audit.
  Triggers: threat model, security audit, supply chain scan, deny list,
  learning db sanitize, security posture, injection scan, surface scan.
version: 1.0.0
user-invocable: false
model: opus
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
routing:
  triggers:
    - threat model
    - security audit
    - supply chain scan
    - deny list
    - learning db sanitize
    - security posture
    - injection scan
    - surface scan
    - audit hooks
    - audit skills
  pairs_with:
    - python-general-engineer
  complexity: Complex
  category: security
---

# Security Threat Model Skill

## Operator Context

This skill configures Claude as a security-focused analyst executing a structured,
phase-gated threat model workflow. It follows the toolkit's four-layer architecture:
**deterministic scripts execute checks; LLM interprets findings and generates mitigations**.
Phase 5 (synthesis) is the only LLM step. All earlier phases are deterministic Python
scripts that produce JSON artifacts.

### Hardcoded Behaviors (Always Apply)

- **Artifacts over memory**: Every phase writes output to `security/` before proceeding
- **Gate enforcement**: Each phase gate must pass before the next phase starts
- **Dry-run by default**: No mutations to the learning DB without explicit `--purge` flag
- **No automated settings mutation**: deny-list is produced for human review; never merged automatically
- **Human approval required**: Phase 2 gate blocks until deny-list is reviewed and approved
- **CRITICAL findings block Phase 4**: Any CRITICAL supply-chain finding halts forward progress

### Default Behaviors (ON unless disabled)

- **security/ directory creation**: Created at Phase 1 start if not present
- **JSON validation**: All artifact JSON is validated before phase gate passes
- **Timestamped run ID**: All artifacts include a shared `run_id` for correlation
- **Summary to stderr**: Each script prints a one-line summary to stderr on completion

### Optional Behaviors (OFF unless enabled)

- **--purge**: Actually delete flagged learning DB rows (dry-run by default)
- **--include-user-claude**: Extend scans to `~/.claude/` paths in addition to local repo
- **--ci-mode**: Suppress interactive approval gates; CRITICAL findings exit non-zero

## Available Scripts

- **`scripts/scan-threat-surface.py`** -- Enumerate hooks, MCP servers, skills, and env vars. Output: `security/surface-report.json`
- **`scripts/generate-deny-list.py`** -- Produce deny-list config from surface scan findings. Output: `security/deny-list.json`
- **`scripts/scan-supply-chain.py`** -- Scan hooks/skills/agents for injection patterns, hidden chars, outbound commands. Output: `security/supply-chain-findings.json`
- **`scripts/sanitize-learning-db.py`** -- Inspect learning DB for poisoned entries. Output: `security/learning-db-report.json`
- **`scripts/validate-threat-model.py`** -- Verify required sections exist in `security/threat-model.md`

## What This Skill CAN Do

- Enumerate the active attack surface of the current toolkit installation
- Generate a ready-to-merge deny-list config for `settings.json`
- Detect zero-width Unicode, instruction-override phrases, and outbound commands in installed artifacts
- Flag learning DB entries with external origins or injection content
- Synthesize all findings into a structured threat model document with ranked mitigations

## What This Skill CANNOT Do

- Provide real-time hook monitoring (point-in-time audit only)
- Automatically purge learning DB rows (requires `--purge` flag and human review)
- Automatically merge deny-list into `settings.json` (human review required)
- Replace network-level egress controls (Docker no-egress is out of scope)

---

## Instructions

### Phase 1: SURFACE SCAN

**Goal**: Enumerate the active attack surface of the current installation.

**Step 1: Ensure output directory exists**

```bash
mkdir -p security
```

**Step 2: Run the surface scan script**

```bash
python3 scripts/scan-threat-surface.py --output security/surface-report.json
```

This script enumerates:
- Registered hooks (from `~/.claude/settings.json`) with file paths and event types
- Installed MCP servers (from `~/.claude/mcp.json` and `.mcp.json`)
- Installed skills (from `skills/`) with `allowed-tools` entries
- Any file in `hooks/`, `skills/`, or `agents/` containing `ANTHROPIC_BASE_URL`

**Step 3: Verify output**

```bash
python3 -c "import json; d=json.load(open('security/surface-report.json')); print('hooks:', len(d.get('hooks',[])), '| skills:', len(d.get('skills',[])), '| mcp_servers:', len(d.get('mcp_servers',[])))"
```

**Gate**: `security/surface-report.json` must exist and parse as valid JSON with `hooks`, `skills`, and `mcp_servers` keys. Do not proceed to Phase 2 until this passes.

---

### Phase 2: DENY-LIST GENERATION

**Goal**: Produce a concrete deny-list config derived from Phase 1 findings.

**Step 1: Generate deny-list**

```bash
python3 scripts/generate-deny-list.py \
    --surface security/surface-report.json \
    --output security/deny-list.json
```

The script applies these mappings from surface findings to deny rules:
- Hook uses `curl` or `wget` -> append `"Bash(curl *)"` and `"Bash(wget *)"`
- Hook uses `ssh` or `scp` -> append `"Bash(ssh *)"` and `"Bash(scp *)"`
- Skill `allowed-tools` contains unscoped `Read(*)` or `Write(*)` -> add path-scoped deny entries
- Any file contains `ANTHROPIC_BASE_URL` override -> append `"Bash(* ANTHROPIC_BASE_URL=*)"`

Always includes the static baseline:
```json
["Read(~/.ssh/**)", "Read(~/.aws/**)", "Read(**/.env*)",
 "Write(~/.ssh/**)", "Write(~/.aws/**)",
 "Bash(curl * | bash)", "Bash(ssh *)", "Bash(scp *)", "Bash(nc *)",
 "Bash(* ANTHROPIC_BASE_URL=*)"]
```

**Step 2: Display diff for human review**

```bash
python3 -c "
import json
d = json.load(open('security/deny-list.json'))
print('Deny-list entries to add to settings.json:')
for rule in d['permissions']['deny']:
    print(' ', rule)
print()
print('Review security/deny-list.json before merging.')
"
```

**Gate (HUMAN APPROVAL REQUIRED)**: Display the deny-list diff and block until the operator confirms they have reviewed it. In `--ci-mode`, skip approval and proceed. Do not proceed to Phase 3 without this gate passing.

---

### Phase 3: SUPPLY-CHAIN AUDIT

**Goal**: Scan all installed hooks, skills, and agents for injection patterns and hidden characters.

**Step 1: Run supply-chain audit**

```bash
python3 scripts/scan-supply-chain.py \
    --scan-dirs hooks/ skills/ agents/ \
    --output security/supply-chain-findings.json
```

Detection patterns (see `scripts/scan-supply-chain.py` source for full regex details):
| Pattern Category | Severity |
|-----------------|----------|
| Zero-width + bidi Unicode characters | CRITICAL |
| HTML comments and hidden payload blocks | CRITICAL |
| `ANTHROPIC_BASE_URL` override in any file | CRITICAL |
| Outbound network commands in hooks/skills | WARNING |
| `enableAllProjectMcpServers` setting | WARNING |
| Broad permission grants without path scoping | WARNING |
| Instruction-override and role-hijacking phrases | CRITICAL |

**Step 2: Check for CRITICAL findings**

```bash
python3 -c "
import json, sys
d = json.load(open('security/supply-chain-findings.json'))
crits = [f for f in d.get('findings', []) if f.get('severity') == 'CRITICAL']
warns = [f for f in d.get('findings', []) if f.get('severity') == 'WARNING']
print(f'CRITICAL: {len(crits)}, WARNING: {len(warns)}')
if crits:
    for c in crits:
        print(f'  CRITICAL: {c[\"file\"]}:{c.get(\"line\",\"?\")} -- {c[\"pattern\"]}')
    sys.exit(1)
"
```

**Gate**: Any CRITICAL finding blocks Phase 4. All CRITICAL findings must be remediated or explicitly acknowledged before continuing. WARNING findings are logged but do not block.

---

### Phase 4: LEARNING DB SANITIZATION

**Goal**: Inspect the learning DB for entries that may contain injected content from external sources.

**Step 1: Run sanitization check (dry-run)**

```bash
python3 scripts/sanitize-learning-db.py \
    --output security/learning-db-report.json
```

Add `--purge` only if the operator explicitly requests it after reviewing the report.

Flags entries where:
- `key` or `value` fields contain known instruction-override or role-hijacking phrases
- `source` is `pr_review`, `url`, or `external` (high-risk origin)
- `value` contains zero-width Unicode or base64 blobs
- `first_seen` is older than 90 days and `source` indicates external origin

**Step 2: Review flagged entries**

```bash
python3 -c "
import json
d = json.load(open('security/learning-db-report.json'))
flagged = d.get('flagged_entries', [])
print(f'Total flagged: {len(flagged)}')
for e in flagged[:10]:
    print(f'  [{e[\"severity\"]}] id={e[\"id\"]} source={e.get(\"source\",\"?\")} action={e[\"action\"]}')
if len(flagged) > 10:
    print(f'  ... and {len(flagged)-10} more. See security/learning-db-report.json')
"
```

**Gate**: Report must be presented to the operator. If purge is desired, re-run with `--purge`. Proceed to Phase 5 when operator acknowledges the report (or when no entries are flagged).

---

### Phase 5: THREAT MODEL SYNTHESIS

**Goal**: Synthesize Phases 1-4 into an actionable threat model document.

**Step 1: Load all phase artifacts**

Read and internalize:
- `security/surface-report.json`
- `security/deny-list.json`
- `security/supply-chain-findings.json`
- `security/learning-db-report.json`

**Step 2: Write threat-model.md**

Write `security/threat-model.md` containing these required sections (the validator checks for these exact headings):

```
# Threat Model

## Run Metadata

## Attack Surface Inventory

## Active Threats

## Mitigations In Place

## Gaps and Recommended Next Controls

## Deny-List Status

## Supply-Chain Audit Summary

## Learning DB Sanitization Summary
```

**Step 3: Write audit-badge.json**

Write `security/audit-badge.json`:
```json
{
  "status": "pass",
  "timestamp": "2026-01-01T00:00:00Z",
  "run_id": "from-surface-report",
  "critical_count": 0,
  "warning_count": 0,
  "phases_completed": 5
}
```

Status is `fail` if `critical_count > 0` or if any phase gate did not pass.

**Step 4: Validate outputs**

```bash
python3 scripts/validate-threat-model.py \
    --threat-model security/threat-model.md \
    --badge security/audit-badge.json
```

**Gate**: `validate-threat-model.py` must exit 0. If it reports missing sections, add them and re-run. Maximum 3 fix iterations before escalating to operator.

---

## Error Handling

### Error: `surface-report.json` missing required keys
**Cause**: Script ran against a directory without Claude Code config.
**Solution**: `~/.claude/settings.json` absence is handled gracefully -- surface-report produces empty arrays. Re-run with `--verbose` for detail.

### Error: Supply-chain audit CRITICAL finding blocks progress
**Cause**: A hook, skill, or agent contains zero-width Unicode, an ANTHROPIC_BASE_URL override, or a known injection phrase.
**Solution**:
1. Open the flagged file at the reported line
2. Determine if it is a legitimate false positive (e.g., a security doc discussing injection patterns)
3. If false positive: add the file to `--exclude` and re-run
4. If genuine: remediate the file before continuing

### Error: Learning DB not found
**Cause**: No sessions have run or the DB path has been moved.
**Solution**: Script handles this gracefully -- produces a report with `total_entries: 0` and `flagged_entries: []`. Not an error condition.

### Error: `validate-threat-model.py` reports missing sections
**Cause**: Phase 5 synthesis omitted a required section.
**Solution**: Read the validator output for the exact missing section name. Add the section to `security/threat-model.md` and re-run validation.

---

## Anti-Patterns

### Anti-Pattern 1: Skipping Phase Gates
**What it looks like**: Moving to Phase 3 before deny-list is reviewed.
**Why wrong**: The gate exists because deny-list review is the highest-ROI control. Skip it and the entire audit is advisory-only.
**Do instead**: Always surface the diff and wait for acknowledgment before Phase 3.

### Anti-Pattern 2: Running `--purge` without reviewing the report
**What it looks like**: `python3 scripts/sanitize-learning-db.py --purge` as a one-liner.
**Why wrong**: Bulk-deleting learning DB rows without review can erase legitimate session context.
**Do instead**: Dry-run first, review `learning-db-report.json`, then re-run with `--purge` only for rows you intend to delete.

### Anti-Pattern 3: Treating this skill as a real-time monitor
**What it looks like**: Running the skill on every commit or session start.
**Why wrong**: This is a point-in-time installation audit. Use `pretool-prompt-injection-scanner.py` for session-time scanning.
**Do instead**: Run on onboarding, after batch PR merges to hooks/ or skills/, or on a scheduled cadence.

### Anti-Pattern 4: Dismissing WARNING findings
**What it looks like**: Noting warnings but not logging them anywhere.
**Why wrong**: Warnings accumulate. An outbound network call in a hook may be legitimate today and exploitable after a patch.
**Do instead**: Log all WARNING findings in `security/threat-model.md` under "Gaps and Recommended Next Controls" with acceptance rationale.

### Anti-Pattern 5: Auto-committing security/ artifacts
**What it looks like**: Adding `security/` to the commit in the same step as running the skill.
**Why wrong**: `security/learning-db-report.json` may contain sensitive entry values from the learning DB.
**Do instead**: Review all `security/` artifacts before committing. Only `security/threat-model.md` and `security/audit-badge.json` are commit candidates.

---

## References

- [ADR-102: Security Threat Model Skill](../../adr/ADR-102-security-threat-model.md)
- [pretool-prompt-injection-scanner.py](../../hooks/pretool-prompt-injection-scanner.py) -- session-time injection scanner (complements, does not replace this skill)
- [learning_db_v2.py](../../hooks/lib/learning_db_v2.py) -- learning DB schema and connection interface
- OWASP MCP Top 10 (living document)
- Snyk ToxicSkills research: 36% of public skills contained injection patterns
