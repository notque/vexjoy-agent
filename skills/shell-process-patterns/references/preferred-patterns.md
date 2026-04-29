---
name: anti-patterns
description: Concrete shell-process anti-patterns with detection commands and paired fixes.
---

<!-- no-pair-required: this H1 is the file title; each AP-N section below contains its own "Do instead" block. -->

# Shell Process Patterns to Detect and Fix

Each entry pairs a detection command (runnable against a repo) with the broken pattern and a correct replacement. The detection commands are `rg`-first because ripgrep is available in the toolkit; fall back to `grep -rn` when `rg` is absent.

When you land here, you are probably reviewing a bash script or about to write one. Check your code against each entry below before shipping.

---

## AP-1: `nohup cmd &` captures the wrapper PID, not the child

### Symptom
You start a background daemon with `nohup`, capture `$!`, later run `kill $!`, and the service is still listening on its port. Your script reports success but the process is still alive.

### Why it happens
`nohup` is itself a wrapper process. When you write:

```bash
nohup python3 -m http.server 8080 > log 2>&1 &
PID=$!
```

`$!` holds the PID of the `nohup` wrapper, not the Python interpreter `nohup` forked. On many systems `nohup` exec-replaces itself with the child, so they end up identical; on others (including recent glibc/coreutils combinations) they do not. You cannot rely on them being the same.

Concrete failure (2026-04-21): Python `http.server` was started with `nohup python3 -m http.server 8080 --bind 0.0.0.0 > log 2>&1 &`. The captured `$!` was PID 1052107 (the `nohup` wrapper). The real listening process was 1052108. `kill 1052107` returned success. Port 8080 stayed `LISTEN`. The server was only killed after `ss -tlnp` was re-queried to find the real PID.

### Detection

```bash
# Find the pattern: nohup followed by & with $! capture
rg -n 'nohup.*&\s*$' --type sh --type bash
rg -n '^\s*PID=\$!' -A 0 --type sh --type bash

# Broader: any `&` + `$!` capture for binaries known to fork
rg -nU '^\s*nohup[^&]*&\s*\n\s*[A-Z_]+=\$!' --type sh --type bash
```

Any hit requires manual inspection: if the backgrounded command is a shell builtin or simple exec it may be safe; if it is anything that daemonizes, forks, or goes through `nohup`/`setsid`, the captured PID is suspect.

### Do instead

Capture the PID by querying the resource the process owns, not by trusting `$!`.

```bash
# Pattern: start, wait for the resource, resolve PID via ss/lsof/pgrep
nohup python3 -m http.server 8080 > log 2>&1 &

# Wait for port to bind
for _ in $(seq 1 30); do
  ss -tln | grep -q ':8080\b' && break
  sleep 0.1
done

# Resolve the real PID from the port owner
PID=$(ss -tlnp | awk '/:8080\b/ {print $NF}' | grep -oP 'pid=\K[0-9]+' | head -1)

if [[ -z "$PID" ]]; then
  echo "ERROR: server did not bind port 8080" >&2
  exit 1
fi

echo "real PID=$PID"
```

For the kill step, verify the port is free afterward, not just that `kill` returned 0. See `cleanup-verification.md`.

Alternative pattern when you really need `$!`: use `exec` inside a subshell to replace the wrapper with the target binary so `$!` points to the real child.

```bash
( exec python3 -m http.server 8080 > log 2>&1 ) &
PID=$!  # This is now the python process itself, not a wrapper
```

But `ss`/`lsof` resource-owner resolution remains more robust because it survives any daemonization pattern.

See `pid-resolution.md` for the full PID capture recipe catalog.

---

## AP-2: `set -e` silently bypassed by `|| true` and friends

### Symptom
A script has `set -e` at the top, a command in the middle fails, and the script continues anyway. Errors are swallowed; the script exits 0 despite real failures.

### Why it happens
`set -e` exits on the first command that returns non-zero. But `set -e` is disabled for any command that is part of:
- A logical operator chain: `cmd || fallback`, `cmd && next`
- A condition in `if`, `while`, `until`
- A pipeline's non-final members when `pipefail` is not set
- A function called in any of the above contexts

The `|| true` idiom is the most common offender. Developers add it to suppress a single expected failure, then the suppression spreads to wrap unrelated logic.

```bash
set -e
rm -rf /tmp/workdir || true  # Intended: tolerate missing dir
# ...100 lines later...
./deploy.sh || true           # Swallowed: deploy fails silently
```

Even worse, functions called under `||` disable `set -e` for their entire body:

```bash
set -e

deploy() {
  build_artifact    # Fails. set -e is DISABLED here because deploy was called under ||.
  upload_artifact   # Runs anyway. Corrupt artifact uploaded.
  restart_service   # Runs anyway. Service restarted with broken artifact.
  return 0
}

deploy || echo "deploy failed"  # Prints nothing. deploy returned 0.
```

### Detection

```bash
# Find `|| true` and `|| :` idioms
rg -n '\|\|\s*(true|:)\b' --type sh --type bash

# Find pipelines without `set -o pipefail`
rg -l 'set -e' --type sh --type bash | while read -r f; do
  if ! rg -q 'set -o pipefail|set -[a-zA-Z]*o[a-zA-Z]*' "$f"; then
    echo "$f: set -e without pipefail"
  fi
done

# Find function calls under || that mask set -e semantics
rg -n '^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*(\(\))?[^=]*\|\|' --type sh --type bash
```

### Do instead

**Always use `set -euo pipefail` together.** Each flag covers a different class of bug:

```bash
#!/usr/bin/env bash
set -euo pipefail

# -e: exit on first unchecked failure
# -u: exit on unset variable reference
# -o pipefail: pipeline fails if any stage fails, not just the last
```

**Handle expected failures explicitly, with scoped checks, not blanket `|| true`.**

```bash
# Wrong
rm -rf /tmp/workdir || true

# Right: test the precondition explicitly
if [[ -d /tmp/workdir ]]; then
  rm -rf /tmp/workdir
fi

# Also right: scope the tolerance to the one command
rm -rf /tmp/workdir 2>/dev/null || [[ ! -d /tmp/workdir ]]
```

**Check exit status inside `if`, not with `||` chains that cascade:**

```bash
# Wrong
build || notify_failure
deploy  # runs even if build failed

# Right
if ! build; then
  notify_failure
  exit 1
fi
deploy
```

**When `|| true` is genuinely needed (e.g. tolerating SIGPIPE from `head`), comment the reason:**

```bash
# head closes stdin on line 10; producer gets SIGPIPE. Tolerated.
producer | head -10 || true
```

---

## AP-3: Trap handler loses the original exit code

### Symptom
Your script has a `trap cleanup EXIT`; when the script fails, `cleanup` runs but the final exit code is the cleanup function's exit code, not the original failure's.

### Detection

```bash
# Traps that run non-trivial logic without preserving $?
rg -nU 'trap\s+[^ ]+\s+EXIT' --type sh --type bash -A 3
```

### Do instead

Capture `$?` as the first line of the trap handler, before any other command can overwrite it.

```bash
cleanup() {
  local rc=$?
  rm -rf "$TMPDIR"
  exit "$rc"
}
trap cleanup EXIT
```

See `signals-and-traps.md` for the full ordering discussion.

---

## AP-4: Kill without verification

### Symptom
`kill "$PID"` returns 0, script proceeds assuming the process is dead, but the process ignored SIGTERM or is still shutting down.

### Detection

```bash
# kill with no follow-up verification
rg -nU 'kill\s+(-[0-9]+\s+)?\$?[A-Z_]+\s*\n' --type sh --type bash -A 2
```

### Do instead

Always re-query state after a destructive action. `kill -0 "$PID"` is the cheapest liveness check.

```bash
kill -TERM "$PID"

# Give it up to 5s to shut down cleanly
for _ in $(seq 1 50); do
  kill -0 "$PID" 2>/dev/null || break
  sleep 0.1
done

# Escalate if still alive
if kill -0 "$PID" 2>/dev/null; then
  kill -KILL "$PID"
  sleep 0.2
fi

# Verify the resource, not just the PID (process could have double-forked)
if ss -tln | grep -q ':8080\b'; then
  echo "ERROR: port 8080 still bound after kill" >&2
  exit 1
fi
```

See `cleanup-verification.md` for patterns that survive double-forking and orphan children.

---

## AP-5: `wait` with no PID kills the script's error handling

### Symptom
`wait` without arguments waits for all background jobs and always returns 0 even if one failed. Subsequent `set -e` logic thinks everything succeeded.

### Detection

```bash
rg -n '^\s*wait\s*

 --type sh --type bash
```

### Do instead

Wait on specific PIDs and check each exit code.

```bash
cmd_a & PID_A=$!
cmd_b & PID_B=$!

wait "$PID_A"
RC_A=$?
wait "$PID_B"
RC_B=$?

if (( RC_A != 0 || RC_B != 0 )); then
  echo "ERROR: one or more background jobs failed (a=$RC_A b=$RC_B)" >&2
  exit 1
fi
```

---

## AP-6: Race between background start and resource readiness

### Symptom
You start a server in the background, then immediately run a client against it. The client fails with "connection refused" because the server has not yet bound the port. Adding `sleep 1` makes it work on your laptop but flakes on CI.

### Detection

```bash
# sleep immediately after background launch is almost always a race hack
rg -nU '&\s*\n\s*sleep\s+[0-9.]+' --type sh --type bash
```

### Do instead

Poll for the resource, not the clock. See the `condition-based-waiting` skill for the full polling/backoff catalog; for simple port-ready checks:

```bash
start_server &

# Poll up to 10s for port to bind
for _ in $(seq 1 100); do
  ss -tln | grep -q ':8080\b' && break
  sleep 0.1
done

ss -tln | grep -q ':8080\b' || { echo "ERROR: server failed to bind"; exit 1; }
```

---

## AP-7: `SIGKILL` as the default

### Symptom
Scripts start with `kill -9` instead of `kill -TERM`. Processes have no chance to flush buffers, close files, or release locks. Corruption follows.

### Detection

```bash
rg -n 'kill\s+-9\b|kill\s+-(KILL|SIGKILL)\b' --type sh --type bash
```

### Do instead

Default to SIGTERM. Escalate to SIGKILL only after a grace period. See AP-4 above for the escalation pattern.

The only valid first-reach SIGKILL is when you have prior evidence the process ignores SIGTERM (document this in a comment), or when the process is known-unresponsive and holding a critical lock.

---

## Cross-references

- For the PID resolution recipes (AP-1): `pid-resolution.md`
- For the full signals and traps discussion (AP-3): `signals-and-traps.md`
- For verification patterns (AP-4, AP-7): `cleanup-verification.md`
- For starting-process idioms (AP-6): `starting-processes.md`
- For polling/backoff (AP-6): `skills/condition-based-waiting/SKILL.md`
