---
name: starting-processes
description: Start background and detached shell processes reliably.
---

# Starting Processes

This file covers the idioms for launching shell processes that outlive or run alongside the parent script: `&`, `nohup`, `disown`, `setsid`, and full daemonization. It does not cover PID capture (see `pid-resolution.md`) or cleanup (see `cleanup-verification.md`).

## Decision Table

| Goal | Idiom | Why |
|------|-------|-----|
| Run a background job inside an interactive session, exit together | `cmd &` | Simplest. Job dies when shell exits unless `huponexit` is off. |
| Run a job that survives shell exit | `nohup cmd > log 2>&1 &` | Ignores SIGHUP. Redirects needed because `nohup` disables stdin and captures stdout to `nohup.out` otherwise. |
| Detach from job control but stay in session | `cmd & disown` | Removes from jobs table; still receives SIGHUP from controlling terminal loss. Use with `nohup` if terminal may close. |
| Fully detach — new session, new process group, no controlling terminal | `setsid cmd > log 2>&1 < /dev/null &` | Proper daemonization in one line. Survives parent exit, terminal loss, and signals to the parent session. |
| Run as a system daemon, managed by init | systemd unit file | Out of scope here. Use systemd if the host has it. |

## Pattern 1: Simple background job

```bash
long_running_task &
PID=$!  # OK for simple exec-replaced commands, suspect for wrappers — see pid-resolution.md
```

The job dies when the shell exits (unless `shopt -s huponexit` is off, which varies by distro). Fine for scripts whose lifetime matches the background job's.

## Pattern 2: Survive shell exit with `nohup`

```bash
nohup long_running_task > /var/log/task.log 2>&1 &
```

What `nohup` does:
- Ignores SIGHUP
- Redirects stdin from `/dev/null` (preventing reads from the terminal)
- If stdout is a terminal, redirects it to `./nohup.out` or `$HOME/nohup.out`

What `nohup` does NOT do:
- It does not create a new session (use `setsid` for that)
- It does not prevent SIGTERM or SIGINT — only SIGHUP
- It does not detach from the process group

Because `nohup` is a wrapper binary (not a builtin), `$!` captures the wrapper PID on some systems rather than the child. See `pid-resolution.md` and `anti-patterns.md` AP-1.

## Pattern 3: `disown`

```bash
long_running_task &
disown %1   # or: disown $!
```

`disown` removes the job from the shell's job table so the shell won't send SIGHUP when it exits. It does not modify the child's signal mask — if the controlling terminal closes, the child still gets SIGHUP from the kernel unless it is in a new session.

Use `nohup` + `disown` together for defense in depth, or prefer `setsid` for a cleaner single-step detachment.

## Pattern 4: Full daemonization with `setsid`

```bash
setsid long_running_task > /var/log/task.log 2>&1 < /dev/null &
```

`setsid` runs the command in a new session. The child has:
- No controlling terminal (terminal close no longer sends SIGHUP)
- New process group (its own job control target)
- Still parent = the shell; becomes orphan → reparented to init when shell exits

The shell redirects are critical. Without them, the child still inherits the shell's stdin/stdout/stderr; if the shell's terminal closes, writes to those fds will produce SIGPIPE or EIO.

Combine with `disown` if you want the shell's job table to forget it too:

```bash
setsid long_running_task > /var/log/task.log 2>&1 < /dev/null &
disown
```

## Pattern 5: The full double-fork daemon

When you need POSIX-canonical daemonization (new session, no controlling TTY possible, `/` as cwd, umask reset, stdio closed) and you cannot use systemd:

```bash
daemonize() {
  local cmd=("$@")

  # First fork: parent exits so child is not a process group leader
  if ! (
    # Second fork via setsid: child is session leader but exits,
    # grandchild can never reacquire a controlling TTY
    setsid "${cmd[@]}" \
      > /var/log/$(basename "$1").log 2>&1 \
      < /dev/null &
  ); then
    echo "ERROR: failed to daemonize ${cmd[*]}" >&2
    return 1
  fi
}

daemonize my_server --port 8080
```

Most scripts do not need this. `setsid cmd > log 2>&1 < /dev/null &` is good enough unless the child itself reopens a terminal. If you're writing a real daemon, use systemd.

## File descriptor redirections

All backgrounded processes should redirect all three stdio streams. Inheriting the parent's terminal fds is a source of flakiness.

```bash
# Minimum for any detached process:
cmd > /path/to/out.log 2>&1 < /dev/null &

# Shortcut using &> for stdout+stderr (bash only, not POSIX sh):
cmd &> /path/to/out.log < /dev/null &

# Discard all output:
cmd > /dev/null 2>&1 < /dev/null &
```

Order matters: `> out 2>&1` redirects stdout then points stderr at the (redirected) stdout. Writing `2>&1 > out` points stderr at the terminal's stdout and then redirects only stdout to the file. Almost always a bug.

## Process group launching

If you plan to send a signal to the whole group later:

```bash
set -m  # enable job control inside a non-interactive script (needed for setpgid)

cmd &
PGID=$!

# To signal the group:
kill -TERM -- -"$PGID"  # negative PID targets the group
```

Without `set -m`, non-interactive bash puts background jobs in the script's own process group, so `kill -- -$$` would target the script itself.

## Common failure modes

| Failure | Root cause | Fix |
|---------|-----------|-----|
| Process dies when terminal closes | No `nohup` or `setsid`; controlling TTY loss sends SIGHUP | Add `setsid ... < /dev/null &` |
| `nohup: ignoring input and appending output to 'nohup.out'` warning | Forgot to redirect stdout | Add `> log 2>&1` before `&` |
| Process holds terminal (CI job hangs) | Inherited stdin tries to read from closed TTY | Add `< /dev/null` |
| `$!` is wrong PID | `nohup`/wrapper issue | See `pid-resolution.md` |
| Background job fails silently in CI | No `pipefail`; output went to null; no exit-code check | Use `wait "$PID"; rc=$?` explicitly |

## Cross-references

- For PID capture after start: `pid-resolution.md`
- For signal handling of started children: `signals-and-traps.md`
- For cleanup after start: `cleanup-verification.md`
- For anti-patterns in starting (AP-1, AP-6): `anti-patterns.md`
