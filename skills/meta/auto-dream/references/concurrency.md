# Auto-Dream concurrency

The shipped wrapper must acquire a non-blocking `flock`; overlap is a skipped run, not a wait. Memory index and injection writes use a temporary file in the destination directory followed by rename, preserving same-filesystem atomicity.

An orphaned `.tmp` is evidence of interruption. Compare it with the destination and the pre-execution report; complete or discard it deliberately. Never treat its existence as permission to skip all future cycles.

Checks:

```bash
rg -n 'flock' scripts/auto-dream-cron.sh
find ~/.claude -name '*.tmp' -path '*dream*' -o -name 'MEMORY.md.tmp'
pgrep -af 'auto-dream|dream-prompt'
```
