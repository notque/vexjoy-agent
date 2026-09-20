# Auto-Dream cron contract

`scripts/auto-dream-cron.sh` must retain: non-blocking `flock`; `--permission-mode auto`; `--max-budget-usd 3.00`; `--no-session-persistence`; `envsubst` of the five `DREAM_*` values; dry-run unless `--execute`; timestamped `tee`; and exit propagation through `PIPESTATUS[0]`.

Register it through `~/.claude/scripts/crontab-manager.py` under tag `auto-dream`, using the repository's off-minute schedule. Do not use `crontab -e` or `--dangerously-skip-permissions`.

Audit:

```bash
rg -n 'flock|permission-mode|max-budget|session-persistence|envsubst|PIPESTATUS' scripts/auto-dream-cron.sh
python3 ~/.claude/scripts/crontab-manager.py verify --tag auto-dream
```
