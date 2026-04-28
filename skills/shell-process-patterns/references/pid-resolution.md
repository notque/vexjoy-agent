---
name: pid-resolution
description: Reliably resolve the real PID of a started process, because $! can lie.
---

# PID Resolution

`$!` is the PID of the most recently backgrounded command — as the shell understands it. The shell does not know whether that command exec-replaces itself, daemonizes, double-forks, or wraps a child. When any of those happen, `$!` points to a PID that is either the wrong one or a zombie by the time you use it.

This file catalogs the reliable alternatives.

## When `$!` is trustworthy

`$!` is fine when:
- The backgrounded command is a simple exec of a binary that does not fork (`sleep 10 &`, `cat /dev/urandom > /dev/null &`)
- The backgrounded command is wrapped by `exec` inside a subshell: `( exec python3 server.py ) &` — the subshell is replaced by Python, so the subshell PID == Python PID
- You do not care which PID you kill, only that the process tree dies (then use process groups)

`$!` is suspect when:
- You used `nohup`, `setsid`, or any other wrapper binary
- The command daemonizes itself (forks a child and exits)
- The command is a shell script that backgrounds its own work
- You will later look up the process by its owned resource (port, PID file, socket)

## Recipe 1: Resolve via owned port (`ss`)

Best for network services.

```bash
nohup my_server --port 8080 > log 2>&1 &

# Wait up to 10s for port to bind
for _ in $(seq 1 100); do
  ss -tln | grep -q ':8080\b' && break
  sleep 0.1
done

# Resolve owner PID
PID=$(ss -tlnp 2>/dev/null | awk '/:8080\b/ {print $NF}' | grep -oP 'pid=\K[0-9]+' | head -1)

[[ -n "$PID" ]] || { echo "ERROR: could not resolve PID for :8080"; exit 1; }
```

`ss -tlnp` requires root or CAP_NET_ADMIN to see the owner on some kernels; if empty, fall back to `lsof -i :8080 -t`.

## Recipe 2: Resolve via `lsof`

Works for ports, Unix sockets, and open files.

```bash
# By TCP port
PID=$(lsof -nP -iTCP:8080 -sTCP:LISTEN -t | head -1)

# By Unix socket path
PID=$(lsof -t /var/run/myapp.sock | head -1)

# By open file (e.g. the log file the daemon writes)
PID=$(lsof -t /var/log/myapp.log | head -1)
```

`lsof` is slower than `ss` but more widely available and can match by file or socket path.

## Recipe 3: Resolve via `pgrep` and process attributes

Use when the process has a distinctive command line.

```bash
# Match by exact binary name (strict)
PID=$(pgrep -x python3 | head -1)  # too broad if you have many python3 procs

# Match by full command line (better)
PID=$(pgrep -f 'python3 -m http.server 8080' | head -1)

# Match by parent (reliable when you know the wrapper's PID)
WRAPPER_PID=$!
PID=$(pgrep -P "$WRAPPER_PID" | head -1)
```

The `-P` parent-match trick is the cleanest way to recover the real child when `$!` captured a wrapper:

```bash
nohup my_server > log 2>&1 &
WRAPPER=$!
sleep 0.1  # give nohup time to fork
CHILD=$(pgrep -P "$WRAPPER" | head -1)
PID=${CHILD:-$WRAPPER}  # fall back to wrapper if nohup exec-replaced itself
```

## Recipe 4: Have the process write its own PID file

The most robust pattern when you control the binary.

```bash
# Program writes its own pid to a known path
my_server --pidfile /var/run/my_server.pid &

# Wait for pidfile
for _ in $(seq 1 50); do
  [[ -s /var/run/my_server.pid ]] && break
  sleep 0.1
done

PID=$(< /var/run/my_server.pid)
```

When the program does not support `--pidfile`, write it yourself after resolving:

```bash
nohup my_server > log 2>&1 &
sleep 0.2
PID=$(pgrep -f 'my_server' | head -1)
echo "$PID" > /var/run/my_server.pid
```

Pidfile caveats:
- Pidfile can go stale if the process crashes. Always validate `kill -0 "$PID"` before trusting it.
- PID recycling: kernel reuses PIDs. Pair the pidfile with a start-time or cmdline match on older systems; on modern Linux prefer `/proc/$PID/cmdline` verification.

## Recipe 5: Use `exec` to make `$!` truthful

Eliminate the wrapper so `$!` is correct by construction.

```bash
# Replace the subshell with the target, then background the subshell
( exec python3 -m http.server 8080 > log 2>&1 ) &
PID=$!  # This is the python process
```

Works for any command that is itself a well-behaved foreground process. Does not work if the command daemonizes itself (Python's http.server does not; many real daemons do).

## Verifying a resolved PID

Once you have a candidate PID, verify it before acting on it.

```bash
verify_pid() {
  local pid=$1
  local expected_cmdline=$2

  # 1. Is it alive?
  kill -0 "$pid" 2>/dev/null || return 1

  # 2. Does its cmdline match what we expect?
  if [[ -r "/proc/$pid/cmdline" ]]; then
    local actual
    actual=$(tr '\0' ' ' < "/proc/$pid/cmdline")
    [[ "$actual" == *"$expected_cmdline"* ]] || return 2
  fi

  return 0
}

verify_pid "$PID" "http.server 8080" \
  || { echo "ERROR: PID $PID does not match expected process"; exit 1; }
```

This catches PID recycling and misresolution.

## Resolving on macOS

`ss` is Linux-only. On macOS:

```bash
PID=$(lsof -nP -iTCP:8080 -sTCP:LISTEN -t | head -1)
# or
PID=$(pgrep -f 'http.server 8080' | head -1)
```

`/proc` does not exist; use `ps -o command= -p "$PID"` for cmdline verification.

## Resolving inside containers

Inside a minimal container without `ss`, `lsof`, or `pgrep`:

```bash
# Parse /proc directly
for d in /proc/[0-9]*; do
  pid=${d##*/}
  cmdline=$(tr '\0' ' ' < "$d/cmdline" 2>/dev/null)
  [[ "$cmdline" == *"http.server 8080"* ]] && { echo "$pid"; break; }
done
```

Or install `procps`/`iproute2` at image build time.

<!-- no-pair-required: This section is a pointer index into anti-patterns.md; each referenced AP has its own paired "Do instead" block in that file. -->

## Patterns to Detect and Fix

These come from the anti-patterns reference:
- `$!` after `nohup` or any wrapper binary — see AP-1 in `anti-patterns.md`
- `kill $!` without verification that the port/resource is actually freed — see AP-4
- `sleep N; kill $!` with a fixed sleep in hopes the wrapper has forked by then — races, use `pgrep -P` or poll

## Cross-references

- For starting-process idioms this file assumes: `starting-processes.md`
- For signal delivery after PID resolution: `signals-and-traps.md`
- For verification after kill: `cleanup-verification.md`
- For the concrete failure mode: `anti-patterns.md` AP-1
