# Brief 01 — Tech: silent backup failure

**Premise**: A team discovered their nightly Postgres backups had been unrestorable for 11 months. The cron job exited 0 every night; pg_dump wrote zero-byte files because a password rotation broke auth and stderr went to /dev/null. A routine disaster-recovery drill caught it.

**Key facts**: 11 months of zero-byte backups; exit code 0 throughout; discovered in a DR drill, not an incident; fix was a restore-test job that loads each backup into a scratch database weekly.

**Audience**: backend engineers and SREs.

**Formats requested**: article title, email subject line.
