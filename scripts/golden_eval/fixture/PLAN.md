# Plan: move the sim database to Postgres

1. Replace the SQLite file with a managed Postgres instance.
2. Rewrite every query in the sim engine for Postgres.
3. Run the nightly season sims against Postgres from next week.

Reason: SQLite "feels slow". No measurements yet.
