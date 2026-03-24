---
name: service-health-check
description: |
  Deterministic 3-phase service health monitoring: Discover, Check, Report.
  Use when user asks about service status, process health, uptime, or
  whether services are running. Use for "health check", "is service up",
  "service status", "what's running", or "check if alive". Do NOT use for
  HTTP endpoint validation, performance profiling, or log analysis without
  a specific health concern.
version: 2.0.0
user-invocable: false
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
routing:
  triggers:
    - "service status"
    - "process health"
    - "uptime check"
    - "is service running"
    - "check health"
  category: infrastructure
---

# Service Health Check Skill

## Operator Context

This skill operates as an operator for service health monitoring workflows, configuring Claude's behavior for structured, read-only health assessment. It implements the **Discover-Check-Report** pattern — find services, gather health signals, produce actionable output — with deterministic process and health file evaluation.

### Hardcoded Behaviors (Always Apply)
- **Read-Only**: NEVER restart, stop, or modify services — report only
- **CLAUDE.md Compliance**: Read and follow repository CLAUDE.md before checking
- **No Side Effects**: Only read process tables, health files, and ports — no writes
- **Structured Output**: Always produce machine-parseable health report
- **Evidence-Based Status**: Every status determination requires at least one concrete signal (process check, health file, or port probe)

### Default Behaviors (ON unless disabled)
- **Process Verification**: Check process existence via pgrep/ps before anything else
- **Staleness Detection**: Flag health files older than configured threshold (default 300s)
- **Port Listening Check**: Verify expected ports are bound when port is configured
- **Actionable Recommendations**: Provide specific commands to resolve issues
- **Staleness Threshold Enforcement**: Default 300s, configurable per service

### Optional Behaviors (OFF unless enabled)
- **Auto-Restart Execution**: Run restart commands (requires explicit user flag)
- **Metrics Collection**: Gather detailed performance metrics from health files
- **Alert Integration**: Format output for monitoring system ingestion
- **Historical Comparison**: Compare against previous health snapshots

## What This Skill CAN Do
- Check if processes are running via pgrep/ps
- Parse JSON health files for status, connection state, and metrics
- Detect stale health data based on configurable thresholds
- Verify ports are listening with ss/netstat
- Produce structured health reports with actionable restart recommendations
- Evaluate service degradation (disconnected, reconnecting states)

## What This Skill CANNOT Do
- Restart, stop, or modify services (report-only by design)
- Perform deep log analysis (use systematic-debugging instead)
- Probe remote health endpoints over HTTP (use endpoint-validator instead)
- Inspect container internals (basic host-level process checks only)
- Authenticate against secured health endpoints
- Skip the Discover phase — services must be identified before checking

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Identify all services to check before running any health probes.

**Step 1: Locate service definitions**

Search for service configuration in this order:
1. `services.json` in project root
2. Docker/docker-compose files for service definitions
3. systemd unit files or process manager configs
4. User-provided service specification

**Step 2: Build service manifest**

For each service, establish:

```markdown
## Service Manifest
| Service | Process Pattern | Health File | Port | Stale Threshold |
|---------|----------------|-------------|------|-----------------|
| api-server | gunicorn.*app:app | /tmp/api_health.json | 8000 | 300s |
| worker | celery.*worker | /tmp/worker_health.json | - | 300s |
| cache | redis-server | - | 6379 | - |
```

**Step 3: Validate manifest**
- Confirm each process pattern is specific enough to avoid false matches
- Verify health file paths are absolute
- Ensure port numbers are within valid range (1-65535)

**Gate**: Service manifest complete with at least one service. Proceed only when gate passes.

### Phase 2: CHECK

**Goal**: Gather health signals for every service in the manifest.

**Step 1: Check process status**

For each service, run process check:
```bash
pgrep -f "<process_pattern>"
```
Record: running (true/false), PIDs, process count.

**Step 2: Parse health files (if configured)**

Read and parse JSON health files. Evaluate:
- Does the file exist?
- Does it parse as valid JSON?
- How old is the timestamp (staleness)?
- What status does the service self-report?
- What is the connection state?

**Step 3: Probe ports (if configured)**

Check if expected ports are listening:
```bash
ss -tlnp "sport = :<port>"
```
Flag processes that are running but not listening on expected ports.

**Step 4: Evaluate health per service**

Apply this decision tree:
1. Process not running → **DOWN**
2. Process running + health file missing → **WARNING**
3. Process running + health file stale → **WARNING** (restart recommended)
4. Process running + status=error → **ERROR** (restart recommended)
5. Process running + disconnected > 30min → **WARNING** (restart recommended)
6. Process running + disconnected < 30min → **DEGRADED** (allow reconnection)
7. Process running + healthy → **HEALTHY**
8. Process running + no health file configured → **RUNNING** (limited visibility)

**Gate**: All services evaluated with evidence-based status. Proceed only when gate passes.

### Phase 3: REPORT

**Goal**: Produce structured, actionable health report.

**Step 1: Generate summary**

```
SERVICE HEALTH REPORT
=====================
Checked: N services
Healthy: X/N

RESULTS:
  service-name         [OK  ] HEALTHY     PID 12345, uptime 2d 4h
  background-worker    [WARN] WARNING     Health file stale (15 min)
  cache-service        [DOWN] DOWN        Process not found

RECOMMENDATIONS:
  background-worker: Restart recommended - health file not updated in 900s
  cache-service: Start service - process not running

SUGGESTED ACTIONS:
  systemctl restart background-worker
  systemctl start cache-service
```

**Step 2: Set exit status**
- All HEALTHY/RUNNING → exit 0
- Any WARNING/DEGRADED/ERROR/DOWN → exit 1

**Step 3: Present to user**
- Lead with the summary line (X/N healthy)
- Highlight any services needing action
- Provide copy-pasteable commands for remediation
- If user has auto-restart enabled, confirm before executing

**Gate**: Report delivered with actionable recommendations for all non-healthy services.

---

## Examples

### Example 1: Routine Health Check
User says: "Are all services up?"
Actions:
1. Locate services.json, build manifest (DISCOVER)
2. Check each process, parse health files, probe ports (CHECK)
3. Output structured report showing 3/3 healthy (REPORT)
Result: Clean report, no action needed

### Example 2: Stale Worker Detection
User says: "The background worker seems stuck"
Actions:
1. Identify worker service from config (DISCOVER)
2. Find process running but health file 20 minutes stale (CHECK)
3. Report WARNING with restart recommendation (REPORT)
Result: Specific diagnosis with actionable command

---

## Error Handling

### Error: "No Service Configuration Found"
Cause: No services.json, docker-compose, or systemd units discovered
Solution:
1. Ask user for service name and process pattern
2. Build minimal manifest from user input
3. Proceed with manual configuration

### Error: "Process Pattern Matches Too Many PIDs"
Cause: Pattern too broad (e.g., "python" matches all Python processes)
Solution:
1. Narrow pattern with full command path or arguments
2. Use `ps aux | grep` to identify distinguishing arguments
3. Update manifest with more specific pattern

### Error: "Health File Exists But Cannot Parse"
Cause: Malformed JSON, permissions issue, or file being written during read
Solution:
1. Check file permissions with `ls -la`
2. Attempt raw read to inspect content
3. If mid-write, retry after 2-second delay
4. Report as WARNING with parse error details

---

## Anti-Patterns

### Anti-Pattern 1: Restarting Without Diagnosing
**What it looks like**: Service shows WARNING, immediately run `systemctl restart`
**Why wrong**: Masks root cause. Service may crash again immediately.
**Do instead**: Report finding, let user decide. Never auto-restart without explicit flag.

### Anti-Pattern 2: Trusting Health File Alone
**What it looks like**: Health file says "healthy" so skip process check
**Why wrong**: Process could be zombie, health file could be stale from before crash.
**Do instead**: Always check process status independently of health file content.

### Anti-Pattern 3: Ignoring Port Mismatch
**What it looks like**: Process running, skip port check, report HEALTHY
**Why wrong**: Process may have started but failed to bind port — effectively down.
**Do instead**: When port is configured, always verify it is listening.

### Anti-Pattern 4: Broad Process Patterns
**What it looks like**: Using "python" as process pattern for a Flask app
**Why wrong**: Matches every Python process on the system, giving false positives.
**Do instead**: Use specific patterns like `gunicorn.*myapp:app` or full command paths.

---

## References

This skill uses these shared patterns:
- [Anti-Rationalization](../shared-patterns/anti-rationalization-core.md) - Prevents shortcut rationalizations
- [Verification Checklist](../shared-patterns/verification-checklist.md) - Pre-completion checks

### Domain-Specific Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "Process is running, must be healthy" | Running ≠ functional | Check health file and port |
| "Health file looks fine" | File could be stale from before crash | Verify timestamp freshness |
| "Just restart it" | Restart masks root cause | Report first, restart only if flagged |
| "No config, skip the check" | User still needs an answer | Ask user for service details |

### Health File Format Reference

Services should write health files as:
```json
{
    "timestamp": "ISO8601, updated every 30-60s",
    "status": "healthy|degraded|error",
    "connection": "connected|disconnected|reconnecting",
    "last_activity": "ISO8601 of last meaningful action",
    "running": true,
    "uptime_seconds": 12345,
    "metrics": {}
}
```
