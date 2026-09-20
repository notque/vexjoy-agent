---
name: security
description: "Review changed code for vulnerabilities or run this repository's threat-model and supply-chain audit workflow."
user-invocable: true
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task, Agent]
agent: reviewer-system
routing:
  force_route: true
  not_for: "general code review or non-security quality checks"
  triggers: [security review, review my changes for security, review for security, security scan, review for vulnerabilities, scan for vulnerabilities, check for security issues, security issues, audit for vulnerabilities, audit auth, threat model, security audit, supply chain scan, deny list, security posture, injection scan, surface scan, audit hooks, audit skills]
  category: security
  pairs_with: [review, reviewer-system]
---

# Security

Choose changed-code review or threat model. Load `references/coverage.md` for review invariants and `references/threat-model.md` for the local artifact workflow.

## Changed-code review

Scope to staged and working-tree changes:

```bash
git diff --name-only HEAD
python3 scripts/security-review-scan.py --files <changed-files> --format json
```

The scanner is the source of deterministic rules. Then read every changed file in full and trace new input/data flows to security-sensitive sinks, including unchanged sinks reached by new code. Apply project `claude-security-guidance.md` only as additive context. Merge findings by `file:line`, retaining the higher severity.

Report only concrete attacker, path, sink, victim/impact, and remediation. CRITICAL yields BLOCK; HIGH yields FIX; MEDIUM/LOW may APPROVE with suggestions. An incomplete scanner or semantic review cannot yield APPROVE; name the gap and use NEEDS-DISCUSSION. Intentional fixtures require contextual justification, not deletion of the built-in rule.

The commit hook scans staged files and blocks HIGH/CRITICAL. `VEXJOY_SECURITY_REVIEW_SKIP=1` is the documented one-off override; `VEXJOY_SECURITY_REVIEW_DISABLE=1` disables both hook events. Hook internal errors fail open. Custom `security-patterns.{yaml,json}` rules are additive, capped at 50, and invalid/ReDoS-prone entries are skipped with warnings; built-ins remain enabled.
