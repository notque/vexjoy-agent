---
name: cleanup-verification
description: Kill-and-check — never trust that a destructive operation succeeded, re-query state.
---

# Cleanup Verification

The core principle: **after any destructive operation on a process, re-query state to verify it actually worked.** `kill` returning 0 means the signal was delivered, not that the process is gone. `rm -f path` returning 0 means the unlink syscall succeeded; it does not tell you the process holding that file as open-fd has stopped writing.

The pattern name is **kill-and-check, not kill-and-assume.**

## Why `kill` exit status is insufficient

`kill` returns:
- `0` — signal was delivered (or was signal 0 and the target exists)
- `1` — permission denied, or target does not exist
- Other — error parsing arguments

What `kill` never tells you:
- Whether the target handled the signal
- Whether the target has finished shutting down
- Whether the target is still holding resources (ports, files, locks)

A process that ignores SIGTERM receives the signal, `kill` exits 0, and the process keeps running forever. A process that handles SIGTERM starts shutdown and may need seconds to finish. Either way, you cannot assume "dead" from `kill`'s exit code.

## The liveness check: `kill -0`

`kill -0 "$PID"` sends signal 0, which the kernel treats as "test whether the PID is valid and we could signal it." No actual signal is delivered.

```bash
if kill -0 "$PID" 2>/dev/null; then
  echo "still alive"
else
  echo "dead or unreachable"
fi
```

Caveats:
- Returns 1 when the PID belongs to another user (permission error) even if alive. Run as the same user or as root.
- Does not distinguish "dead" from "PID recycled by another process." Always verify cmdline or resource ownership when PID recycling matters.

## The standard kill-and-check loop

```bash
terminate_and_verify() {
  local pid=$1
  local grace=${2:-5}   # seconds to wait for graceful exit
  local resource=${3:-} # optional: port or file to re-verify

  # 1. Polite shutdown
  kill -TERM "$pid" 2>/dev/null || true

  # 2. Wait up to grace seconds for the process to exit
  for _ in $(seq 1 $((grace * 10))); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
  done

  # 3. Escalate if still alive
  if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid" 2>/dev/null || true
    sleep 0.2
  fi

  # 4. Final liveness check
  if kill -0 "$pid" 2>/dev/null; then
    echo "ERROR: PID $pid still alive after SIGKILL" >&2
    return 1
  fi

  # 5. Resource check (more important than PID check)
  if [[ -n "$resource" ]]; then
    case "$resource" in
      port:*)
        local port=${resource#port:}
        if ss -tln 2>/dev/null | grep -q ":${port}\b"; then
          echo "ERROR: port $port still bound after kill" >&2
          return 1
        fi
        ;;
      file:*)
        local f=${resource#file:}
        if lsof -t "$f" 2>/dev/null | read -r; then
          echo "ERROR: file $f still held by some process" >&2
          return 1
        fi
        ;;
    esac
  fi

  return 0
}

# Usage
terminate_and_verify "$PID" 5 port:8080
```

## Why resource verification beats PID verification

A process can exit while its child continues to hold the resource you cared about. A process can double-fork, leaving `$PID` dead but a grandchild alive and still listening on the port. A process can crash and systemd can restart it under a new PID before your verification runs.

Your user cares whether port 8080 is free, not whether a specific PID is gone. Verify the resource.

```bash
# Bad: only checks the one PID we knew about
kill "$PID"
sleep 1
kill -0 "$PID" 2>/dev/null && echo "still alive"

# Good: checks the resource the user cares about
kill "$PID"
sleep 1
if ss -tln | grep -q ':8080\b'; then
  echo "ERROR: port 8080 still bound"
  # escalate: find whatever is holding it now and kill that
  NEW_PID=$(ss -tlnp | awk '/:8080\b/ {print $NF}' | grep -oP 'pid=\K[0-9]+' | head -1)
  kill -KILL "$NEW_PID"
fi
```

## Common resources to verify

| Resource | Verification |
|----------|--------------|
| TCP port | `ss -tln \| grep -q ':PORT\b'` or `lsof -i TCP:PORT` |
| UDP port | `ss -uln \| grep -q ':PORT\b'` |
| Unix socket | `[[ -S /path/to.sock ]]` (path exists) or `lsof /path/to.sock` |
| File lock (flock) | `flock -n /path/to.lockfile -c true` — success = lock is free |
| PID file | `[[ -f /var/run/app.pid ]] && kill -0 "$(<file)"` |
| Log file writer | `lsof -t /var/log/app.log` |
| Mount point | `findmnt /path` |
| Database session | Application-specific query |

## Cleanup on script exit

Combine EXIT trap with kill-and-check:

```bash
#!/usr/bin/env bash
set -euo pipefail

PIDS=()

start_worker() {
  "$@" &
  PIDS+=($!)
}

cleanup() {
  local rc=$?

  for pid in "${PIDS[@]}"; do
    kill -TERM "$pid" 2>/dev/null || true
  done

  # Grace period
  local deadline=$((SECONDS + 5))
  for pid in "${PIDS[@]}"; do
    while kill -0 "$pid" 2>/dev/null && (( SECONDS < deadline )); do
      sleep 0.1
    done
  done

  # Escalate survivors
  for pid in "${PIDS[@]}"; do
    kill -KILL "$pid" 2>/dev/null || true
  done

  exit "$rc"
}

trap cleanup EXIT

start_worker long_task_a
start_worker long_task_b

wait
```

## The "it died but the port is still held" case

This happens when the target process had a child that it failed to kill on its own way out. The parent's PID is gone; a grandchild owns the socket.

```bash
kill -TERM "$PARENT_PID"
# Parent exits, child survives, port stays bound.
```

Recovery: after the first kill, re-resolve the resource owner and kill whatever is holding it now.

```bash
kill_everything_holding_port() {
  local port=$1
  local max_iter=5

  for _ in $(seq 1 $max_iter); do
    local pids
    pids=$(ss -tlnp 2>/dev/null | awk -v p=":${port}" '$0 ~ p' \
           | grep -oP 'pid=\K[0-9]+')
    [[ -z "$pids" ]] && return 0

    while read -r pid; do
      [[ -n "$pid" ]] || continue
      kill -TERM "$pid" 2>/dev/null || true
    done <<< "$pids"

    sleep 0.5

    # Check if port is free now
    ss -tln | grep -q ":${port}\b" || return 0
  done

  # Still bound; escalate to SIGKILL on everything
  ss -tlnp 2>/dev/null | awk -v p=":${port}" '$0 ~ p' \
    | grep -oP 'pid=\K[0-9]+' \
    | while read -r pid; do kill -KILL "$pid" 2>/dev/null || true; done

  sleep 0.2
  ss -tln | grep -q ":${port}\b" && return 1 || return 0
}
```

## Verification in tests

If your test kills a server and then starts a new one, verify the port is free before starting. Otherwise the new server fails with "address already in use" and the test flakes.

```bash
# Teardown
kill -TERM "$SERVER_PID" 2>/dev/null || true
for _ in $(seq 1 30); do
  ss -tln | grep -q ':8080\b' || break
  sleep 0.1
done
ss -tln | grep -q ':8080\b' && { echo "FATAL: teardown incomplete"; exit 1; }

# Now safe to restart
start_server
```

<!-- no-pair-required: This section is a pointer index into anti-patterns.md; each referenced AP has its own paired "Do instead" block in that file. The body of THIS reference file (kill-and-check loop, resource verification, cleanup-on-exit) IS the "do instead" content for the referenced anti-patterns. -->

## Anti-patterns

- `kill "$PID" && echo done` — `kill` returning 0 is not "done"; see `anti-patterns.md` AP-4
- `kill -9` as the default — removes the process's chance to clean up; see AP-7
- `sleep 5; echo "should be dead now"` — races; poll the liveness check instead

## Cross-references

- For PID capture before kill: `pid-resolution.md`
- For signals and traps: `signals-and-traps.md`
- For anti-patterns: `anti-patterns.md` AP-4, AP-7
- For polling/backoff generalities: `skills/condition-based-waiting/SKILL.md`
