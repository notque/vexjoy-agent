---
name: shell-process-patterns
description: "Safely start, supervise, and terminate shell processes: background jobs, PID capture, signals, traps, cleanup verification."
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
    - "background process"
    - "nohup"
    - "kill process"
    - "pid lookup"
    - "shell cleanup"
    - "trap handler"
    - "signal handling"
    - "set -e"
    - "bash process"
  pairs_with:
    - condition-based-waiting
    - service-health-check
    - cron-job-auditor
  category: process
---

# Shell Process Patterns

Start, supervise, and terminate shell processes safely. The dominant failure mode is silent state: a process that looks killed but holds a port, a trap that never fired on the child, a `set -e` script that kept running because `|| true` swallowed the error.

| Pattern | Use When | Key Safety Bound |
|---------|----------|------------------|
| Background start | Ad-hoc long-running child in a script or session | Redirect fd 0/1/2, capture real PID, disown if parent exits |
| Daemonization | Process must survive terminal close | `setsid` + fd redirect + PID file atomically |
| PID resolution | Need to kill/inspect the actual worker | Re-query with `ss`/`pgrep`/`lsof`; `$!` is advisory |
| Signal discipline | Graceful shutdown of supervisor + children | SIGTERM first with timeout, SIGKILL last, propagate to group |
| Trap + cleanup | Script must leave no orphans, lock files, or temp dirs | `trap ... EXIT` + verification (file gone, port free, PID dead) |
| Strict-mode scripts | Any non-trivial bash script | `set -euo pipefail` with understood `||` and `if !` escape hatches |

## Scope

**In scope:** Background processes (`&`, `nohup`, `disown`, `setsid`, daemonization); PID capture and reconciliation; signal handling (SIGTERM vs SIGKILL, `exec`, process groups, subshell inheritance); trap discipline (`EXIT` vs signal traps, ordering, inheritance); cleanup verification (kill-and-check); `set -e`/`-u`/`-o pipefail` interactions; `wait` semantics and race conditions.

**Out of scope:** Cron scripts (`cron-job-auditor`). Polling/retry/backoff (`condition-based-waiting`). Service health reporting (`service-health-check`). Fish shell (`fish-shell-config`). Shell features unrelated to process lifecycle.

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| starting a background process, `&`, `nohup`, `disown`, `setsid`, daemonize | `starting-processes.md` | Launch-time patterns and fd/session rules |
| capturing the child PID, `$!` lies, port still listening after kill | `pid-resolution.md` | Real PID capture and state reconciliation |
| trap ordering, SIGTERM/SIGKILL, subshell signal inheritance, `exec` | `signals-and-traps.md` | Signal and trap discipline |
| verifying a process is actually gone, lock file still present, port still bound | `cleanup-verification.md` | Kill-and-check pattern |
| implementation patterns, detection commands, fix snippets, `set -e` + `||` | `preferred-patterns.md` | Gotcha catalog with `rg`/`grep` detection and fixes |

## Instructions

Before implementing, search the codebase for existing process-management patterns. Consistency with existing scripts beats local optimization.

### Step 1: Pick the pattern

One pattern per task. Do not pre-emptively wrap a background process in a daemon or add a trap for a 50ms script.

```
1. Starting a new process?
   YES -> Parent exits before child?
          YES -> Daemonization (Step 3, load references/starting-processes.md)
          NO  -> Background start (Step 2, load references/starting-processes.md)
   NO  -> Continue

2. Need to kill or inspect a process?
   YES -> PID resolution (Step 4, load references/pid-resolution.md)
   NO  -> Continue

3. Writing a supervisor (script managing children)?
   YES -> Signal + trap discipline (Step 5, load references/signals-and-traps.md)
   NO  -> Continue

4. Finishing a destructive operation (kill, rm, release)?
   YES -> Cleanup verification (Step 6, load references/cleanup-verification.md)
   NO  -> Task may not belong in this skill.
```

### Step 2: Start a background process

In-session, parent stays alive. Load `references/starting-processes.md`.

1. **Redirect all three fds.** `cmd > log 2>&1 < /dev/null &` -- un-redirected background processes inherit the terminal; stray stdin reads block forever.
2. **Capture PID defensively.** `$!` is the shell-level PID. If wrapped in `nohup`, you get the nohup PID, not the child. Re-query before acting (Step 4).
3. **`disown` if needed.** Removes job from shell's table so SIGHUP isn't sent on shell exit.

Minimal correct pattern:
```bash
cmd > /tmp/cmd.log 2>&1 < /dev/null &
pid=$!
kill -0 "$pid" 2>/dev/null || { echo "failed to start" >&2; exit 1; }
```

Never use `cmd &` with no redirection in a non-interactive script.

Gate: `kill -0 $pid` before treating PID as valid -- `$!` may name a process that died in the first millisecond.

### Step 3: Daemonize a process

Child must outlive parent session. Load `references/starting-processes.md`.

- Need session leader (independent of TTY)? -> `setsid cmd > log 2>&1 < /dev/null &`
- Just survive SIGHUP? -> `nohup cmd > log 2>&1 < /dev/null &`

Redirect all three fds explicitly -- `nohup` prints to `nohup.out` if you don't, creating sprawl.

### Step 4: Resolve the real PID

Load `references/pid-resolution.md`. Most-frequent failure class.

`$!` often returns a wrapper PID (`nohup`, `time`, `sh -c`), not the worker. Resolve via observable state:

| Goal | Command | Returns |
|------|---------|---------|
| TCP port owner | `ss -tlnp "sport = :N"` | PID, command |
| UDP port owner | `ss -ulnp "sport = :N"` | PID, command |
| Find by name | `pgrep -fa 'pattern'` | PID(s) + command line |
| Find by file | `lsof -t /path/to/file` | PID(s) |
| Children of parent | `pgrep -P $parent_pid` | Child PIDs |

Killing a wrapper PID orphans the child (re-parents to PID 1, keeps running). Always re-query after a kill.

Gate: before declaring killed, run the discovery query again and confirm empty -- see Step 6.

### Step 5: Signal and trap discipline

Load `references/signals-and-traps.md`.

1. **SIGTERM first, SIGKILL last.** SIGTERM allows cleanup. SIGKILL leaves lock files. Send SIGTERM, wait bounded interval (10s), escalate.
2. **Signal the process group** for the whole tree: `kill -TERM -$pgid`. Or launch with `setsid` so group ID = child PID.
3. **Subshells need their own traps.** Parent traps don't fire inside `$(...)` or `(...)`.
4. **`exec cmd` replaces the shell.** All traps gone. If you need traps, run as child and `wait`.
5. **`trap ... EXIT`** fires on normal exit, `set -e` exit, and most signals -- not SIGKILL. Design on-disk state to survive hard kill.

Traps calling `exit` mask the real exit code. Use `trap 'rc=$?; cleanup; exit $rc' EXIT`.

### Step 6: Verify cleanup

Load `references/cleanup-verification.md`. Every destructive operation ends with verification: "is it really gone?"

```bash
kill -TERM "$pid" 2>/dev/null || true

for _ in {1..10}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
done

if kill -0 "$pid" 2>/dev/null; then
    kill -KILL "$pid" 2>/dev/null || true
    sleep 1
fi

if kill -0 "$pid" 2>/dev/null; then
    echo "FATAL: $pid still alive after SIGKILL" >&2
    exit 1
fi
# Also check resource: ss -tlnp "sport = :8080" | grep -q . && echo "port still bound"
```

Check must target the resource (port, lock file), not just PID -- a re-spawned process under a different PID can re-bind immediately.

Gate: if resource still held, do not proceed. Surface the state. Do not auto-escalate beyond SIGKILL -- reboot/`fuser -k` requires human decision.

### Step 7: Strict-mode scripts

Default header:
```bash
#!/usr/bin/env bash
set -euo pipefail

cleanup() {
    local rc=$?
    [[ -n "${child_pid:-}" ]] && kill -TERM "$child_pid" 2>/dev/null || true
    rm -f "${lock_file:-/dev/null}"
    exit "$rc"
}
trap cleanup EXIT
trap 'echo "ERROR: line $LINENO exit $?" >&2' ERR
```

`|| something` masks exit codes -- `set -e` won't fire. Use `|| true` only when failure is genuinely harmless. Prefer `if ! cmd; then handle; fi`.

### Step 8: Verify

After implementing any pattern:
- **Success path**: child started, PID captured, trap fires on normal exit
- **Failure path**: child fails -> clear error, no orphan, no stale lock
- **Kill path**: SIGTERM -> clean exit; SIGKILL -> no lock/PID file remains (or next run tolerates leftovers)
- **Verification**: port/lock/PID file genuinely released, re-checked with `ss`/`ls`/`kill -0`

## Error Handling

### "kill: (1234): No such process" but port still bound
Cause: `$!` captured wrapper PID, not real child. Wrapper killed; child re-parented to init.
Solution: Re-query with `ss -tlnp "sport = :PORT"` for real PID. Fix start-time code to capture real PID. See `references/pid-resolution.md`.

### Trap handler never fires
Cause: (a) Trap set inside already-exited subshell, (b) script replaced by `exec`, (c) SIGKILL received, (d) trap overwritten by later `trap ... EXIT`.
Solution: Move trap into the shell owning the state. Don't `exec` if traps needed. Accept SIGKILL bypasses traps.

### Script hangs forever in `wait`
Cause: Waiting on reaped PID, wrong process group, or SIGCHLD trap never returns.
Solution: Use `wait -n` (bash 4.3+) or bounded loop with `kill -0`. Audit SIGCHLD traps.

### `set -e` script "succeeds" but didn't do work
Cause: `|| true` swallowed failure, or failing command on pipeline left side without `pipefail`.
Solution: Remove `|| true` unless failure genuinely harmless. Add `set -o pipefail`. See `references/preferred-patterns.md`.

## References

### Reference Files

- `references/starting-processes.md` -- `&`, `nohup`, `disown`, `setsid`, daemonization, fd redirection
- `references/pid-resolution.md` -- why `$!` lies, reliable PID capture, `ss`/`pgrep`/`lsof` recipes
- `references/signals-and-traps.md` -- SIGTERM/SIGKILL, trap ordering, subshell inheritance, `exec`, process groups
- `references/cleanup-verification.md` -- kill-and-check pattern, state re-query after destructive ops
- `references/preferred-patterns.md` -- gotchas with `rg` detection and paired fixes
