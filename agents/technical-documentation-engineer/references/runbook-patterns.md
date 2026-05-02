# Runbook and Operational Documentation Patterns

> **Scope**: Runbook structure, troubleshooting guide patterns, incident response docs, and service integration guides. Does NOT cover API reference docs (see `documentation-standards.md`, `api-doc-verification-failures.md`).
> **Version range**: All versions — structural patterns are version-independent
> **Generated**: 2026-04-15

---

## Overview

Runbooks are read at 2am under stress. Reader needs commands, not architecture explanations. Common failure: "check the logs" without specifying where, what to grep, or what output means.

---

## Pattern Table

| Section | Required | Placement | Anti-Pattern |
|---------|----------|-----------|--------------|
| Symptoms | Yes | First | "Service may be unhealthy" (too vague) |
| Verification command | Yes | Immediately after symptom | Describing what to look for without the command |
| Rollback procedure | Yes for deploy runbooks | After fix | Missing entirely |
| Escalation path | Yes | Last section | "Contact the team" without names/channels |
| Prerequisites | Yes | Before any steps | Buried in step 3 |

---

## Correct Patterns

### Runbook Structure — 5-Section Format

A complete runbook requires these five sections in this order:

```markdown
# Service Name: Issue Name

## Symptoms
- Alert fires: `ServiceHighLatencyP99 > 500ms for 5min`
- Users report: checkout fails with 504 Gateway Timeout
- Dashboard: https://grafana.internal/d/checkout-latency

## Diagnosis
```bash
# Verify service health
curl -s https://checkout.internal/health | jq '.status'

# Check recent error rate
kubectl logs -n prod deploy/checkout --since=5m | grep "ERROR" | tail -20

# Check database connection pool
kubectl exec -n prod deploy/checkout -- env | grep DB_POOL_MAX
```

Expected healthy output: `{"status": "ok", "db": "connected"}`

## Root Causes

| Symptom | Likely Cause | Check Command |
|---------|-------------|---------------|
| 504 on all requests | DB connection pool exhausted | `kubectl exec ... -- curl localhost:8080/metrics | grep db_pool` |
| 504 on POST only | Payment provider timeout | `kubectl logs ... | grep "payment.*timeout"` |
| 504 after deploy | New migration blocking table | Check migration log in deployment output |

## Fix

**Immediate mitigation** (stops the bleeding):
```bash
# Scale up to add capacity
kubectl scale deploy/checkout -n prod --replicas=5

# If DB pool: restart with increased pool size
kubectl set env deploy/checkout -n prod DB_POOL_MAX=20
kubectl rollout restart deploy/checkout -n prod
```

**Verify fix applied**:
```bash
kubectl rollout status deploy/checkout -n prod
curl -s https://checkout.internal/health | jq '.status'
```

## Rollback

If fix makes things worse:
```bash
kubectl rollout undo deploy/checkout -n prod
# Then: page #oncall-platform to investigate
```

## Escalation

If not resolved in 15 minutes:
- Slack: `#oncall-platform` with alert link and `kubectl describe pod` output
- PagerDuty: escalate to Platform team
- War room: https://meet.example.com/incident-response
```

**Why**: New oncall can triage without domain knowledge. Root Causes table maps symptoms to causes.

---

### Diagnosis Section — Commands Before Explanation

Command first, then interpretation. Never explanation before command.

```markdown
<!-- Good: command first, then interpretation -->
Check database connection pool saturation:
```bash
kubectl exec -n prod deploy/checkout -- curl -s localhost:8080/metrics \
  | grep db_pool_active
```
Output above 18/20 means pool is saturated. Proceed to fix section.

<!-- Bad: explanation before the command -->
The database connection pool can become saturated when there are many concurrent requests.
When this happens, you should check the metrics endpoint to see the current pool utilization.
The command for this is: ...
```

**Why**: Under stress, readers skim and paste. Explanation read only when output is unexpected.

---

### Prerequisites Section — Environment Assumptions Made Explicit

```markdown
## Prerequisites

Before running any commands in this runbook:

- `kubectl` configured and authenticated for the `prod` cluster
  - Verify: `kubectl get nodes --context=prod-us-east`
- PagerDuty access to escalate if needed
- Grafana access: https://grafana.internal (SSO login)
- This service's dependencies: PostgreSQL 14+, Redis 6+
  - Verify Redis: `redis-cli -h redis.internal ping`

If any prerequisite fails, escalate to `#oncall-platform` immediately.
```

**Why**: New oncall without access = runbook fails. Verification commands make each prereq a yes/no test.

---

## Pattern Catalog

<!-- no-pair-required: section header with no content -->

### List Concrete Observable Symptoms

**Detection**:
```bash
grep -n "may\|might\|could\|possibly\|sometimes" runbooks/**/*.md | grep -i "symptom\|alert\|issue"
rg "(may|might|could) (be|indicate|suggest|mean)" --glob "runbooks/**/*.md"
```

**Signal**:
```markdown
## Symptoms
<!-- no-pair-required: example code block fragment, not an individual anti-pattern block -->
The service may be experiencing issues. Performance might degrade under load.
Users could see errors.
```

**Why this matters**: "May be experiencing issues" is not a symptom. Oncall needs exact alert name, threshold, user-visible failure, and dashboard link.

**Preferred action**:
```markdown
## Symptoms
<!-- no-pair-required: example code block fragment, not an individual anti-pattern block -->
- Alert fires: `CheckoutService5xxRate > 1% for 3min` in PagerDuty
- Users report: orders stuck at "Processing Payment" with no confirmation email
- Metrics: https://grafana.internal/d/checkout — `checkout_order_total` flatlines
```

---

### Add Verification After Every Fix Step

**Detection**:
```bash
grep -n "kubectl\|curl\|systemctl\|service\b" runbooks/**/*.md \
  | grep -v "verify\|check\|confirm\|status"
# Lines with fix commands but no adjacent verify command (manual review needed)
<!-- no-pair-required: detection code fragment inside bash block, not an anti-pattern block -->

grep -A5 "^## Fix\|^## Resolution" runbooks/**/*.md | grep -c "verify\|confirm\|check"
```

**Signal**:
```markdown
## Fix
<!-- no-pair-required: example code block fragment, not an individual anti-pattern block -->

Restart the service:
```bash
kubectl rollout restart deploy/checkout -n prod
```
```
*(no verification step after)*

**Why this matters**: Restart runs but deploy may fail (OOMKilled, ImagePullError). Without verification, oncall thinks it's fixed while pods crash-loop.

**Preferred action** — verify after every fix:
```markdown
Restart the service:
```bash
kubectl rollout restart deploy/checkout -n prod
```

Verify restart succeeded (wait up to 2 minutes):
```bash
kubectl rollout status deploy/checkout -n prod --timeout=120s
# Expect: "successfully rolled out"
```

If rollout fails, check pod status:
```bash
kubectl get pods -n prod -l app=checkout
kubectl describe pod -n prod -l app=checkout | tail -20
```
```

---

### Include Named Channels in Escalation

**Detection**:
```bash
grep -n "escalate\|contact\|reach out\|ask" runbooks/**/*.md \
  | grep -v "#[a-z]\|@[a-z]\|pagerduty\|phone\|email"
rg "escalate to (the )?team|contact support" --glob "runbooks/**/*.md"
```

**Signal**:
```markdown
## Escalation
<!-- no-pair-required: example code block fragment, not an individual anti-pattern block -->

If the issue persists, escalate to the platform team.
```

**Why this matters**: "The platform team" doesn't exist at 2am. Specific channels and policies do.

**Preferred action** — named channels, policies, time thresholds, info to include:
```markdown
## Escalation
<!-- no-pair-required: example code block fragment, not an individual anti-pattern block -->

If not resolved in 15 minutes:
1. Post in `#oncall-platform` with: alert link, output of `kubectl get pods -n prod`, and what you tried
2. PagerDuty: escalate to "Platform On-Call" policy
3. War room: https://meet.example.com/incident-2 (create if none exists)
4. If data loss suspected: immediately page `#sre-emergency` and halt all mitigation
```

---

### Include Rollback Section in Deploy Runbooks

**Detection**:
```bash
grep -rn "deploy\|release\|rollout" runbooks/**/*.md \
  | grep -v "rollback\|undo\|revert\|previous version"
# Deploy runbooks without rollback are a gap — flag manually
# no-pair-required: detection code fragment inside bash block, not an anti-pattern block
grep -l "deploy\|release" runbooks/**/*.md \
  | xargs grep -L "rollback\|undo\|revert"
```

**Signal**: A deploy runbook with steps to apply a new version, but no section on what to do if the deploy breaks production.

**Why this matters**: Deploy P0 without rollback docs = figuring it out under pressure.

**Preferred action**: Every deploy runbook needs:
```markdown
## Rollback

If the deployment causes increased error rates or alerts:

```bash
# Revert to previous version
kubectl rollout undo deploy/SERVICE -n prod

# Verify rollback
kubectl rollout status deploy/SERVICE -n prod
kubectl get pods -n prod -l app=SERVICE
```

Expected: previous version running, error rates returning to baseline within 2 minutes.

After rollback: open a post-incident review ticket in Linear with label `deploy-rollback`.
```

---

## Error-Fix Mappings

| Runbook Issue | Detection Signal | Fix |
|---------------|-----------------|-----|
| Verification command missing after fix | Fix section has no curl/kubectl/grep following the change command | Add `verify` step with expected output |
| Alert name not in symptoms | Symptoms describe behavior but not the alert that fires | Add exact PagerDuty/Grafana alert name |
| Command uses hardcoded values | Commands have literal IPs/hostnames that may differ by env | Replace with env variable references or document env assumptions |
| No "Expected output" for diagnosis commands | Reader doesn't know if what they see is normal or broken | Add `# Expected healthy output: ...` comment after each command |
| Runbook not linked from alert | Alert fires but runbook is not discoverable | Add runbook URL to alert annotation |

---

## Detection Commands Reference

```bash
# Vague symptoms (may/might/could)
rg "(may|might|could) (be|indicate|suggest)" --glob "runbooks/**/*.md"

# Fix steps without verification
grep -A10 "^## Fix\|^## Resolution" runbooks/**/*.md | grep -c "verify\|check\|confirm"

# Escalation without channel/contact
rg "escalate to (the )?team|contact support" --glob "runbooks/**/*.md"

# Deploy runbooks missing rollback
grep -l "deploy\|release" runbooks/**/*.md | xargs grep -L "rollback\|undo"

# Commands using placeholder hostnames
grep -n "example\.com\|YOUR_\|<hostname>" runbooks/**/*.md
```

---

## See Also

- `documentation-standards.md` — Style guide for API documentation tables and formatting
- `api-doc-verification-failures.md` — Verification patterns for API documentation accuracy
