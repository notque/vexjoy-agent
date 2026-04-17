# Runbook and Operational Documentation Patterns

> **Scope**: Runbook structure, troubleshooting guide patterns, incident response docs, and service integration guides. Does NOT cover API reference docs (see `documentation-standards.md`, `api-doc-anti-patterns.md`).
> **Version range**: All versions — structural patterns are version-independent
> **Generated**: 2026-04-15

---

## Overview

Runbooks fail when they describe how the system works instead of what to do when it breaks. A runbook is read under stress — at 2am when something is paging. The reader needs specific commands, not explanations of architecture. The most common failure mode: a runbook that says "check the logs" without specifying where the logs are, what to grep for, or what the output means.

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

**Why**: The 5-section structure ensures a new oncall engineer can triage without domain knowledge. "Root Causes" table maps observable symptoms to likely causes — no guesswork required.

---

### Diagnosis Section — Commands Before Explanation

Every diagnosis command must appear before the explanation of what it shows, not after.

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

**Why**: Under stress, readers skim. Command-first format means they can paste the command immediately. Explanation after the command is read only when the output is unexpected.

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

**Why**: Runbooks without prerequisites fail when a new oncall engineer doesn't have access. The verification command for each prerequisite converts "do you have X?" into a yes/no test.

---

## Pattern Catalog

<!-- no-pair-required: section header with no content -->

### ❌ Vague Symptoms Section

**Detection**:
```bash
grep -n "may\|might\|could\|possibly\|sometimes" runbooks/**/*.md | grep -i "symptom\|alert\|issue"
rg "(may|might|could) (be|indicate|suggest|mean)" --glob "runbooks/**/*.md"
```

**Do instead:** List each symptom as a concrete, named signal: the exact alert expression that fired, the observed user-facing failure, and a dashboard URL. Every symptom must be specific enough that the oncall engineer can confirm the diagnosis without guessing.

**What it looks like**:
```markdown
## Symptoms
<!-- no-pair-required: example code block fragment, not an individual anti-pattern block -->
The service may be experiencing issues. Performance might degrade under load.
Users could see errors.
```

**Why wrong**: "May be experiencing issues" is a description of the alert condition, not the symptom. The oncall engineer is reading this because they got paged — they already know something is wrong. They need to know what specific signal confirms the diagnosis.

**Do instead:** Write symptoms as concrete, observable signals: the exact alert name and threshold that fired, the user-visible behavior (specific action that fails), and a link to the relevant dashboard. The oncall engineer should be able to confirm they are looking at the right problem with a single glance.

**Fix**:
```markdown
## Symptoms
<!-- no-pair-required: example code block fragment, not an individual anti-pattern block -->
- Alert fires: `CheckoutService5xxRate > 1% for 3min` in PagerDuty
- Users report: orders stuck at "Processing Payment" with no confirmation email
- Metrics: https://grafana.internal/d/checkout — `checkout_order_total` flatlines
```

---

### ❌ Fix Steps Without Verification

**Detection**:
```bash
grep -n "kubectl\|curl\|systemctl\|service\b" runbooks/**/*.md \
  | grep -v "verify\|check\|confirm\|status"
# Lines with fix commands but no adjacent verify command (manual review needed)
<!-- no-pair-required: detection code fragment inside bash block, not an anti-pattern block -->

grep -A5 "^## Fix\|^## Resolution" runbooks/**/*.md | grep -c "verify\|confirm\|check"
```

**What it looks like**:
```markdown
## Fix
<!-- no-pair-required: example code block fragment, not an individual anti-pattern block -->

Restart the service:
```bash
kubectl rollout restart deploy/checkout -n prod
```
```
*(no verification step after)*

**Why wrong**: The restart command runs but the deployment might fail (OOMKilled, ImagePullError). The oncall engineer thinks they fixed it but the pods are crash-looping. The alert fires again in 2 minutes.

**Do instead:** Follow every fix command with a verification step that checks the expected outcome explicitly. The verification command must show what "success" looks like (e.g., `"successfully rolled out"`) so the engineer knows whether the fix worked before closing the incident.

**Fix**:
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

### ❌ Escalation Section Without Contact Details

**Detection**:
```bash
grep -n "escalate\|contact\|reach out\|ask" runbooks/**/*.md \
  | grep -v "#[a-z]\|@[a-z]\|pagerduty\|phone\|email"
rg "escalate to (the )?team|contact support" --glob "runbooks/**/*.md"
```

**Do instead:** Write escalation steps with named Slack channels, PagerDuty policy names, and time thresholds (e.g., "If not resolved in 15 minutes, post in `#oncall-platform`"). Every escalation path must be actionable without prior knowledge of the team structure.

**What it looks like**:
```markdown
## Escalation
<!-- no-pair-required: example code block fragment, not an individual anti-pattern block -->

If the issue persists, escalate to the platform team.
```

**Why wrong**: "The platform team" doesn't exist at 2am — specific people and channels do. Vague escalation paths cause delay while the oncall engineer asks "who is the platform team?"

**Do instead:** Name specific Slack channels, PagerDuty policies, and war room links with a time threshold for each escalation step. Include a brief summary of what information to include when escalating (alert link, pod state, what was tried), so the engineer doesn't have to improvise under stress.

**Fix**:
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

### ❌ Missing Rollback Procedure for Deploy Runbooks

**Detection**:
```bash
grep -rn "deploy\|release\|rollout" runbooks/**/*.md \
  | grep -v "rollback\|undo\|revert\|previous version"
# Deploy runbooks without rollback are a gap — flag manually
# no-pair-required: detection code fragment inside bash block, not an anti-pattern block
grep -l "deploy\|release" runbooks/**/*.md \
  | xargs grep -L "rollback\|undo\|revert"
```

**What it looks like**: A deploy runbook with steps to apply a new version, but no section on what to do if the deploy breaks production.

**Why wrong**: When a deploy causes a P0, the first question is "how do we roll back?" A missing rollback section means someone must figure this out under pressure without documentation.

**Do instead:** Add a `## Rollback` section to every deploy runbook with the exact rollback command, the verification step confirming the previous version is running, and the post-rollback action (e.g., file an incident review ticket). Rollback is not an afterthought — it is a required section.

**Fix**: Every deploy runbook needs:
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
- `api-doc-anti-patterns.md` — Verification patterns for API documentation accuracy
