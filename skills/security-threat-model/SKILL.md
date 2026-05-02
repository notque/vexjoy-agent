---
name: security-threat-model
description: "Security threat model: scan toolkit for attack surface, supply-chain risks."
agent: python-general-engineer
effort: high
user-invocable: false
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

Phase-gated security threat model: deterministic Python scripts perform all checks (Phases 1-4) and produce JSON artifacts; Phase 5 (synthesis) is the only LLM step. Each phase gates on artifact validation. Outputs saved to `security/` with a shared `run_id`.

---

## Instructions

### Phase 1: SURFACE SCAN

Enumerate the active attack surface.

```bash
mkdir -p security
python3 scripts/scan-threat-surface.py --output security/surface-report.json
```

Enumerates: registered hooks (from `~/.claude/settings.json`), installed MCP servers (from `~/.claude/mcp.json` and `.mcp.json`), installed skills (from `skills/`) with `allowed-tools`, any file containing `ANTHROPIC_BASE_URL`.

**Validate**:
```bash
python3 -c "import json; d=json.load(open('security/surface-report.json')); print('hooks:', len(d.get('hooks',[])), '| skills:', len(d.get('skills',[])), '| mcp_servers:', len(d.get('mcp_servers',[])))"
```

**Gate**: `security/surface-report.json` must exist, parse as valid JSON, and contain `hooks`, `skills`, and `mcp_servers` keys. Missing directories produce empty arrays. Do not proceed until gate passes.

---

### Phase 2: DENY-LIST GENERATION

Produce a deny-list config from Phase 1 findings.

```bash
python3 scripts/generate-deny-list.py \
    --surface security/surface-report.json \
    --output security/deny-list.json
```

Mapping rules:
- Hook uses `curl`/`wget` -> deny `"Bash(curl *)"`, `"Bash(wget *)"`
- Hook uses `ssh`/`scp` -> deny `"Bash(ssh *)"`, `"Bash(scp *)"`
- Skill has unscoped `Read(*)`/`Write(*)` -> add path-scoped deny entries
- Any `ANTHROPIC_BASE_URL` override -> deny `"Bash(* ANTHROPIC_BASE_URL=*)"`

Static baseline always included:
```json
["Read(~/.ssh/**)", "Read(~/.aws/**)", "Read(**/.env*)",
 "Write(~/.ssh/**)", "Write(~/.aws/**)",
 "Bash(curl * | bash)", "Bash(ssh *)", "Bash(scp *)", "Bash(nc *)",
 "Bash(* ANTHROPIC_BASE_URL=*)"]
```

**Display for review**:
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

**Gate (HUMAN APPROVAL REQUIRED)**: Never merge automatically. Display diff and block until operator confirms. In `--ci-mode`, skip this gate.

---

### Phase 3: SUPPLY-CHAIN AUDIT

Scan hooks, skills, and agents for injection patterns and hidden characters.

```bash
python3 scripts/scan-supply-chain.py \
    --scan-dirs hooks/ skills/ agents/ \
    --output security/supply-chain-findings.json
```

| Pattern | Severity |
|---------|----------|
| Zero-width + bidi Unicode characters | CRITICAL |
| HTML comments and hidden payload blocks | CRITICAL |
| `ANTHROPIC_BASE_URL` override | CRITICAL |
| Instruction-override / role-hijacking phrases | CRITICAL |
| Outbound network commands in hooks/skills | WARNING |
| `enableAllProjectMcpServers` setting | WARNING |
| Broad permission grants without path scoping | WARNING |

**Check CRITICALs**:
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

**Gate (BLOCKING)**: Any CRITICAL halts progress. Remediate or explicitly acknowledge before Phase 4. WARNINGs logged under "Gaps and Recommended Next Controls" with acceptance rationale.

---

### Phase 4: LEARNING DB SANITIZATION

Inspect learning DB for injected content. Dry-run only (never mutates without `--purge`).

```bash
python3 scripts/sanitize-learning-db.py \
    --output security/learning-db-report.json
```

Flags entries where:
- `key`/`value` contain instruction-override or role-hijacking phrases
- `source` is `pr_review`, `url`, or `external`
- `value` contains zero-width Unicode or base64 blobs
- `first_seen` > 90 days with external origin

**Review**:
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

**Gate (DRY-RUN)**: No rows deleted without operator request and `--purge` flag. Missing learning DB produces empty report (`total_entries: 0`). Proceed when operator acknowledges or no entries flagged.

---

### Phase 5: THREAT MODEL SYNTHESIS

Synthesize Phases 1-4 into an actionable threat model. This is the only LLM-driven phase.

Load all artifacts:
- `security/surface-report.json`
- `security/deny-list.json`
- `security/supply-chain-findings.json`
- `security/learning-db-report.json`

Write `security/threat-model.md` with required sections (validator checks exact headings):

```markdown
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

Status is `fail` if any CRITICAL was not remediated or any phase gate did not pass.

**Validate**:
```bash
python3 scripts/validate-threat-model.py \
    --threat-model security/threat-model.md \
    --badge security/audit-badge.json
```

**Gate**: Must exit 0. If validation fails, add missing sections and re-run. Max 3 fix iterations before escalating.

---

## Error Handling

### Supply-chain CRITICAL blocks progress
**Cause**: Hook/skill/agent contains zero-width Unicode, ANTHROPIC_BASE_URL override, or injection phrase.
**Solution**: Open flagged file at reported line. If false positive (e.g., documentation about injection): add to `--exclude` and re-run. If genuine: remediate before Phase 4.

### Validation fails with missing sections
**Cause**: Phase 5 omitted a required heading.
**Solution**: Read validator output for exact missing section. Add it with content from phase artifacts. Re-run. Max 3 iterations.

### Missing configuration or databases
**Cause**: `~/.claude/settings.json` or learning DB missing.
**Solution**: Handled gracefully: missing settings -> empty hook arrays; missing DB -> `total_entries: 0`. Use `--verbose` for detail.

---

## References

- [ADR-102: Security Threat Model Skill](../../adr/ADR-102-security-threat-model.md)
- [pretool-prompt-injection-scanner.py](../../hooks/pretool-prompt-injection-scanner.py) -- session-time injection scanner (complements this skill)
- [learning_db_v2.py](../../hooks/lib/learning_db_v2.py) -- learning DB schema and connection interface
- OWASP MCP Top 10 (living document)
- Snyk ToxicSkills research: 36% of public skills contained injection patterns
