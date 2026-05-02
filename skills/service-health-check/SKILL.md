---
name: service-health-check
description: "Service health monitoring: Discover, Check, Report in 3 phases."
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
  pairs_with:
    - kubernetes-debugging
    - endpoint-validator
    - condition-based-waiting
---

# Service Health Check Skill

Deterministic service health monitoring via **Discover-Check-Report**. Finds services, gathers health signals from multiple sources (process table, health files, port binding), produces actionable reports.

Never report a service healthy without verifying process status independently of health file content. Never assume a running process is functional -- cross-check against health files and port binding.

---

## Instructions

### Phase 1: DISCOVER

**Goal**: Identify all services before running health probes.

**Step 1: Locate service definitions**

Search in order:
1. `services.json` in project root
2. Docker/docker-compose files
3. systemd unit files or process manager configs
4. User-provided specification

**Step 2: Build service manifest**

```markdown
## Service Manifest
| Service | Process Pattern | Health File | Port | Stale Threshold |
|---------|----------------|-------------|------|-----------------|
| api-server | gunicorn.*app:app | /tmp/api_health.json | 8000 | 300s |
| worker | celery.*worker | /tmp/worker_health.json | - | 300s |
| cache | redis-server | - | 6379 | - |
```

Constraints:
- Process patterns must be specific (not "python" -- use full paths or arguments)
- Health file paths must be absolute
- Port numbers 1-65535

**Step 3: Validate manifest**

If a pattern is too broad, use `ps aux | grep` to identify distinguishing arguments.

**Gate**: Manifest complete with at least one service.

### Phase 2: CHECK

**Goal**: Gather health signals for every service. Always check process status independently of health file content.

**Step 1: Check process status**

```bash
pgrep -f "<process_pattern>"
```
Record: running (true/false), PIDs, process count. A missing process always means DOWN.

**Step 2: Parse health files (if configured)**

Evaluate: file exists, parses as valid JSON, timestamp freshness (default stale threshold 300s), self-reported status, connection state.

Never trust health file alone -- file could be stale from before a crash. Always verify:
1. Process still running
2. Timestamp fresh (within threshold)
3. Status matches evidence

**Step 3: Probe ports (if configured)**

```bash
ss -tlnp "sport = :<port>"
```

A process can start but fail to bind its port -- that is effectively DOWN.

**Step 4: Evaluate health per service**

Decision tree:

1. **Process not running** -> **DOWN**
2. **Process running + health file missing** -> **WARNING**
3. **Process running + health file stale** (> threshold) -> **WARNING**
4. **Process running + status=error** -> **ERROR** (restart recommended)
5. **Process running + disconnected > 30 min** -> **WARNING** (stuck state)
6. **Process running + disconnected < 30 min** -> **DEGRADED** (allow reconnection)
7. **Process running + port not listening** -> **ERROR** (failed port bind)
8. **Process running + healthy** -> **HEALTHY**
9. **Process running + no health file configured** -> **RUNNING** (limited visibility)

**Gate**: All services evaluated with evidence-based status. No status without concrete signal.

### Phase 3: REPORT

**Goal**: Structured, actionable health report with remediation commands.

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
- All HEALTHY/RUNNING -> exit 0
- Any WARNING/DEGRADED/ERROR/DOWN -> exit 1

**Step 3: Present to user**
- Lead with summary (X/N healthy)
- Highlight services needing action
- Provide copy-pasteable remediation commands
- Never auto-restart without explicit user flag

**Gate**: Report delivered with actionable recommendations for all non-healthy services.

---

## Error Handling

### No Service Configuration Found
Cause: No services.json, docker-compose, or systemd units.
Solution: Ask user for service name and process pattern. Build minimal manifest. Proceed with manual config.

### Process Pattern Matches Too Many PIDs
Cause: Pattern too broad (e.g., "python").
Solution: Narrow with full command path or arguments. Use `ps aux | grep` to find distinguishing args. Update manifest.

### Health File Exists But Cannot Parse
Cause: Malformed JSON, permissions issue, or mid-write.
Solution: Check permissions with `ls -la`. Attempt raw read. If mid-write, retry after 2s delay. Report as WARNING.

---

## References

### Health File Format

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

### Key Constraints

| Constraint | Application |
|-----------|-------------|
| Process status verified independently of health file | Always check process before trusting health file |
| Health file staleness detected by timestamp | Check against 300s (configurable) threshold |
| Port binding verified when configured | Verify expected port listening |
| No auto-restart without explicit flag | Report first, let user decide |
| Narrow process patterns required | Use full paths or specific args |
| Evidence-based status only | No status without concrete signal |
