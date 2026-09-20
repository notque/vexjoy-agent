# Automation boundary

CI may run the checker with `--strict --format json`. Auto-fix remains opt-in
and must not run in a read-only check. Preserve raw JSON and the process exit
code as build artifacts so parse failure can be distinguished from detected
drift.
