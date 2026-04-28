---
name: signals-and-traps
description: Signals, traps, and how they interact with subshells, exec, and pipelines.
---

# Signals and Traps

This file covers what signals mean in practice, how `trap` works in bash, and the subtle cases where trap handlers don't do what a reader expects (subshells, `exec`, pipelines, `EXIT` ordering).

## Signal reference (the useful ones)

| Signal | Default | Use for | Ignorable? | Blockable? |
|--------|---------|---------|------------|------------|
| SIGTERM (15) | Terminate | Polite shutdown; process can catch and clean up | Yes | Yes |
| SIGINT (2) | Terminate | Ctrl+C from the terminal | Yes | Yes |
| SIGHUP (1) | Terminate | Controlling terminal closed; reload config by convention | Yes | Yes |
| SIGQUIT (3) | Core dump | Developer's "abort with state" | Yes | Yes |
| SIGKILL (9) | Terminate, immediate | Last resort — process cannot catch, block, or ignore | **No** | **No** |
| SIGSTOP (19) | Stop | Pause (Ctrl+Z sends SIGTSTP); cannot be caught | **No** | **No** |
| SIGUSR1 / SIGUSR2 | Terminate | Application-defined | Yes | Yes |
| SIGCHLD | Ignore | Child state changed; used internally by shell job control | Yes | Yes |
| SIGPIPE (13) | Terminate | Wrote to pipe with no reader (e.g. `producer \| head`) | Yes | Yes |

**Rule of thumb:** always send SIGTERM first. Escalate to SIGKILL only after a grace period with verification that SIGTERM was ignored. See `anti-patterns.md` AP-7.

## Sending signals

```bash
# By name (preferred — readable)
kill -TERM "$PID"
kill -HUP "$PID"
kill -KILL "$PID"

# By number (portable but cryptic)
kill -15 "$PID"

# To a process group (negative PID)
kill -TERM -- -"$PGID"

# To every process matching a pattern
pkill -TERM -f 'my_server --port 8080'

# Liveness check — sends signal 0, which is "test only, do not deliver"
kill -0 "$PID" 2>/dev/null && echo alive
```

## The `trap` builtin

```bash
# Run handler on specific signals
trap 'handler_fn' SIGTERM SIGINT SIGHUP

# Run handler on script exit (any cause: normal, signal, error)
trap 'cleanup' EXIT

# Run on error (with set -e)
trap 'echo "failed at line $LINENO" >&2' ERR

# Reset a trap to default
trap - SIGTERM

# Ignore a signal
trap '' SIGHUP
```

## EXIT trap: preserve `$?`

The single most common trap bug: clobbering the exit code inside the handler.

```bash
# Broken: final rm exits 0, script reports 0 even if command_that_fails failed
cleanup() {
  rm -rf "$TMPDIR"
}
trap cleanup EXIT

command_that_fails
# script exits with 0 because rm succeeded last
```

Fix: capture `$?` as the first statement and re-exit with it.

```bash
cleanup() {
  local rc=$?
  rm -rf "$TMPDIR"
  exit "$rc"
}
trap cleanup EXIT
```

## Trap ordering: EXIT runs last, always

When you trap both a signal and EXIT, receiving the signal runs the signal handler *and then* the EXIT handler. Don't register the same cleanup in both — you'll run it twice.

```bash
# Wrong — cleanup runs twice on SIGTERM
trap cleanup EXIT SIGTERM

# Right — signal handler delegates to EXIT
trap 'exit 143' SIGTERM   # 143 = 128 + 15 (SIGTERM)
trap cleanup EXIT
```

Bash's convention: exit codes 128+N indicate death by signal N. Preserving this lets parent scripts diagnose the cause.

## Subshell inheritance

Traps set in the parent apply only to the current shell. Each `(...)`, `$(...)`, and pipeline component runs in its own subshell, so re-register the trap where you need it.

```bash
trap 'echo parent cleanup' EXIT

(
  # This subshell does NOT inherit the parent's EXIT trap.
  # It has its own (empty) trap table.
  echo "in subshell"
  exit 1
)

echo "after subshell"   # runs; parent EXIT trap will fire at script end
```

If you need a subshell to clean up on its own exit, re-register:

```bash
(
  trap 'echo subshell cleanup' EXIT
  risky_operation
)
```

Functions, by contrast, share the parent's traps (they run in the same shell). This is why `trap ... RETURN` exists — per-function cleanup without subshell overhead.

## `exec` replaces the process

`exec cmd` replaces the shell with `cmd`. The shell's traps are discarded because the shell no longer exists. `cmd` starts with the default disposition for every signal (unless the kernel marks SIGCHLD/SIGPIPE handlers as inherited, which is platform-specific).

```bash
trap 'echo cleanup' EXIT

exec python3 server.py
# Shell is gone. The EXIT trap never fires.
```

If you want traps that apply to the exec'd process, you must have the target set them — the shell cannot pass traps through exec.

## Pipeline components each run in a subshell

```bash
trap 'echo cleanup' EXIT

producer | consumer
# If producer dies from SIGPIPE, its subshell exits but the parent trap
# does not fire — because producer was a subshell. The parent script
# fires its EXIT trap only when the parent shell exits.
```

With `set -o pipefail`, the pipeline's overall exit code reflects any failure; without it, only the last stage's exit code matters.

## Signal forwarding to children

A shell script that receives SIGTERM does NOT automatically forward it to its children. Children keep running; the script exits and orphans them. If you want clean shutdown:

```bash
child_pids=()

spawn() {
  "$@" &
  child_pids+=($!)
}

on_term() {
  for pid in "${child_pids[@]}"; do
    kill -TERM "$pid" 2>/dev/null
  done

  # Wait for children to drain, up to 5s
  local deadline=$((SECONDS + 5))
  for pid in "${child_pids[@]}"; do
    while kill -0 "$pid" 2>/dev/null && (( SECONDS < deadline )); do
      sleep 0.1
    done
  done

  # Escalate survivors
  for pid in "${child_pids[@]}"; do
    kill -KILL "$pid" 2>/dev/null
  done

  exit 143
}

trap on_term SIGTERM SIGINT

spawn worker_a
spawn worker_b
wait
```

Alternatively, put all children in a process group and signal the group. See `starting-processes.md` "Process group launching".

## `set -e` and traps

`set -e` + `trap ... ERR` is the bash error-handling idiom:

```bash
set -euo pipefail

on_error() {
  echo "ERROR: line $LINENO: $BASH_COMMAND exited $?" >&2
}

trap on_error ERR
```

Gotcha: `ERR` traps have the same `set -e` blind spots — they don't fire for commands in `if`, `while`, `||`, or `&&` chains. If you need to catch every non-zero, check `$?` explicitly.

## `wait` and signal delivery

While a bash script is blocked inside `wait`, signal handlers run after `wait` returns. The OS delivers the signal; bash queues it; the handler runs after the current builtin completes.

This means SIGTERM sent to a script sitting in `wait` won't run the handler until the child exits on its own. Workaround: add a timeout.

```bash
# bash 4.3+: wait has -n (any child) but still blocks
# use a watchdog
(
  sleep 30
  kill -TERM 0   # kill whole process group, including parent
) &
WATCHDOG=$!

cmd &
wait $!
kill "$WATCHDOG" 2>/dev/null
```

Or: use `wait -n` in a loop with `read -t` for periodic handler dispatch (bash 4.3+).

## Debugging traps

```bash
# List current traps
trap -p

# List traps for a specific signal
trap -p SIGTERM

# Remove a trap (reset to default)
trap - SIGTERM
```

## Cross-references

- For the trap-clobbers-exit-code anti-pattern: `anti-patterns.md` AP-3
- For SIGKILL-first anti-pattern: `anti-patterns.md` AP-7
- For starting process groups: `starting-processes.md`
- For cleanup verification after signaling: `cleanup-verification.md`
