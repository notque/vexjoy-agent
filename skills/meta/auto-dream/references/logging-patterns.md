# Auto-Dream artifacts

Per-run logs live under `cron-logs/auto-dream/`; structured state lives under `${DREAM_STATE_DIR}`. `last-dream.md` is the consumer-facing latest pointer, while the dated report is the audit copy.

A log mentioning one completed phase is not success. Confirm the final report date, planned-versus-actual results, injection path, and wrapper exit. Empty logs often mean lock contention or failure before `claude` started. Keep 30 days of timestamped logs; do not rotate state reports as if they were raw logs.
