# Wait/Retry Anti-Patterns

> **Scope**: Common mistakes in polling, retry, and backoff code — detection commands and fixes.
> **Version range**: Python 3.8+, Bash (any POSIX)
> **Generated**: 2026-04-16

---

## Overview

Retry and wait code fails silently more than almost any other category: a loop that should timeout hangs forever, a "retry" that doesn't back off hammers a downed service, a test that passed locally flakes in CI because it depended on timing. The patterns below are the most frequent offenders found across real codebases.

---

## Anti-Pattern Catalog

### ❌ Hardcoded `time.sleep()` Without Condition Check

**Detection**:
```bash
grep -rn 'time\.sleep(' --include="*.py" | grep -v 'poll_interval\|wait_for\|retry\|backoff'
rg 'time\.sleep\(\d' --type py
```

**What it looks like**:
```python
def wait_for_db():
    time.sleep(5)  # Hope the DB is ready by now
    return connect()
```

**Why wrong**: The sleep duration is a guess. If the DB starts in 1s you wasted 4s; if it takes 6s you got a connection error. There is no feedback — the code never checks whether the condition became true.

**Fix**:
```python
wait_for(
    lambda: try_connect() is not None,
    "database connection",
    timeout_seconds=30,
    poll_interval_seconds=0.5,
)
```

---

### ❌ Infinite Loop Without Timeout

**Detection**:
```bash
grep -rn 'while True' --include="*.py" | grep -v 'timeout\|deadline\|monotonic'
rg 'while True:' --type py -A 5 | grep -v 'break\|timeout\|deadline'
```

**What it looks like**:
```python
while True:
    if service_ready():
        break
    time.sleep(1)
# Hangs forever if service never becomes ready
```

**Why wrong**: A downed service turns this into an infinite loop that blocks the process, pegs a thread, and never gives the caller an error to act on.

**Fix**:
```python
start = time.monotonic()
deadline = start + timeout_seconds
while time.monotonic() < deadline:
    if service_ready():
        return
    time.sleep(1)
raise TimeoutError(f"Service not ready after {timeout_seconds}s")
```

---

### ❌ Using `time.time()` for Elapsed Time Measurement

**Detection**:
```bash
rg 'start\s*=\s*time\.time\(\)' --type py
grep -rn 'time\.time()' --include="*.py" | grep -E 'deadline|elapsed|timeout'
```

**What it looks like**:
```python
start = time.time()
deadline = start + timeout
while time.time() < deadline:
    ...
```

**Why wrong**: `time.time()` is wall-clock time and jumps backward on NTP sync or DST changes. A 1-second backward jump can cause the loop to run `timeout` extra seconds past the intended deadline. `time.monotonic()` never goes backward.

**Fix**:
```python
start = time.monotonic()
deadline = start + timeout
while time.monotonic() < deadline:
    ...
```

**Version note**: `time.monotonic()` available since Python 3.3.

---

### ❌ Retry Without Jitter (Thundering Herd)

**Detection**:
```bash
grep -rn 'sleep.*delay\|sleep.*backoff' --include="*.py" | grep -v 'jitter\|random\|uniform'
rg 'time\.sleep\(delay\)' --type py
```

**What it looks like**:
```python
for attempt in range(max_retries):
    try:
        return call_api()
    except RequestException:
        time.sleep(delay)
        delay *= 2  # No jitter — all clients wake up simultaneously
```

**Why wrong**: After an outage, all clients waiting with the same deterministic delay retry at exactly the same instant. This creates a load spike that can re-trigger the very failure they were recovering from.

**Fix**:
```python
jitter = 1.0 + random.uniform(-0.5, 0.5)
time.sleep(min(delay * jitter, max_delay))
delay = min(delay * backoff_factor, max_delay)
```

---

### ❌ Retrying Non-Retryable Errors

**Detection**:
```bash
grep -rn 'except Exception' --include="*.py" -B2 | grep -E 'retry|attempt|backoff'
rg 'retryable_exceptions.*=.*Exception\b' --type py
```

**What it looks like**:
```python
for attempt in range(5):
    try:
        return api_call()
    except Exception:  # Retries 401, 404, validation errors too
        time.sleep(delay)
```

**Why wrong**: A 401 Unauthorized will never succeed on retry — you're burning quota and delaying the inevitable. A 400 Bad Request means your payload is wrong, not that the server is overloaded.

**Fix**:
```python
RETRYABLE = (requests.Timeout, requests.ConnectionError)
NON_RETRYABLE_CODES = {400, 401, 403, 404, 422}

for attempt in range(max_retries):
    try:
        resp = requests.get(url)
        if resp.status_code in NON_RETRYABLE_CODES:
            resp.raise_for_status()  # Propagates immediately, no retry
        resp.raise_for_status()
        return resp
    except RETRYABLE as e:
        if attempt >= max_retries - 1:
            raise
        time.sleep(delay)
```

---

### ❌ Busy-Wait (No Sleep in Poll Loop)

**Detection**:
```bash
grep -rn -A 8 'while.*monotonic\(\)' --include="*.py" | grep -v 'sleep'
rg 'while time\.monotonic' --type py -A 6 | grep -c 'sleep'
```

**What it looks like**:
```python
while time.monotonic() < deadline:
    if condition():
        return True
# No sleep — spins at 100% CPU until timeout
```

**Why wrong**: A tight poll loop consumes 100% of one CPU core, starves other threads/processes, and triggers thermal throttling on laptops.

**Fix**:
```python
while time.monotonic() < deadline:
    if condition():
        return True
    time.sleep(poll_interval)  # min 0.01s in-process; 0.5s+ for external services
```

---

### ❌ Bash Loop Without Timeout

**Detection**:
```bash
grep -rn 'while.*sleep' --include="*.sh" | grep -v 'deadline\|SECONDS\|timeout\|end_time'
grep -rn 'while true' --include="*.sh" -i | grep -v 'deadline\|SECONDS'
```

**What it looks like**:
```bash
while ! pg_isready -h localhost; do
    sleep 2
done
# Hangs indefinitely if postgres never starts
```

**Why wrong**: No bound means this script hangs in CI until the job times out, with no diagnostic about what failed or how long it waited.

**Fix**:
```bash
deadline=$((SECONDS + 60))
while [ $SECONDS -lt $deadline ]; do
    if pg_isready -h localhost; then
        exit 0
    fi
    sleep 2
done
echo "Timeout: postgres not ready after 60s" >&2
exit 1
```

**Note**: `$SECONDS` is a bash built-in counting seconds since shell started — no `date` subprocess needed.

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `TimeoutError: Timeout waiting for: X. Waited 30.0s, last result: None` | Condition function always returns falsy | Add logging inside condition; verify the target actually changes state |
| `All retries exhausted` with 401/403 in logs | Retrying non-retryable auth errors | Add status-code check before retry; propagate 401/403 immediately |
| Test hangs in CI but passes locally | Hardcoded `sleep()` too short for CI machine | Replace with condition-based wait; or add env-var timeout override |
| High CPU during health check startup | Busy-wait with no sleep | Add `time.sleep(poll_interval)` inside the poll loop |
| Retry storm after outage recovery | No jitter — all instances retry simultaneously | Add `random.uniform(-0.5, 0.5)` jitter multiplier |

---

## Detection Commands Reference

```bash
# Hardcoded sleep without condition
grep -rn 'time\.sleep(' --include="*.py" | grep -v 'poll_interval\|wait_for\|retry'

# Infinite loop without timeout
grep -rn 'while True' --include="*.py" | grep -v 'deadline\|timeout\|monotonic'

# Wall-clock time for elapsed measurement
rg 'start\s*=\s*time\.time\(\)' --type py

# Retry without jitter
rg 'time\.sleep\(delay\)' --type py

# Broad exception catch in retry context
grep -rn 'except Exception' --include="*.py" -B2 | grep -E 'retry|attempt'

# Bash loop without timeout
grep -rn 'while.*sleep' --include="*.sh" | grep -v 'deadline\|SECONDS\|timeout'
```

---

## See Also

- `implementation-patterns.md` — complete Python/Bash implementations for all patterns
