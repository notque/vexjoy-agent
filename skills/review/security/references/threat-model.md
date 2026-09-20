# Repository threat-model workflow

Programs produce four JSON artifacts under `security/`; synthesis is the only generative phase. Keep one run ID across artifacts.

1. Surface: `python3 scripts/scan-threat-surface.py --output security/surface-report.json`. Require parseable `hooks`, `skills`, and `mcp_servers` keys.
2. Deny list: `python3 scripts/generate-deny-list.py --surface security/surface-report.json --output security/deny-list.json`. Display it for human review. It is never merged automatically; CI may continue without the interactive acknowledgment.
3. Supply chain: `python3 scripts/scan-supply-chain.py --scan-dirs hooks/ skills/ agents/ --output security/supply-chain-findings.json`. Unacknowledged CRITICAL findings (hidden/bidi characters, payload blocks, base-URL overrides, instruction hijacking) stop the run; warnings remain in the final gaps.
4. Learning DB: `python3 scripts/sanitize-learning-db.py --output security/learning-db-report.json`. Default is dry-run. Deletion requires an explicit operator request and `--purge`; a missing DB produces a valid empty report.
5. Synthesize `security/threat-model.md` and `security/audit-badge.json`, then run `python3 scripts/validate-threat-model.py --threat-model security/threat-model.md --badge security/audit-badge.json`.

The threat model must contain exact headings: Run Metadata, Attack Surface Inventory, Active Threats, Mitigations In Place, Gaps and Recommended Next Controls, Deny-List Status, Supply-Chain Audit Summary, and Learning DB Sanitization Summary. Badge status fails when a CRITICAL remains or any phase gate failed. Retry validator-driven formatting fixes at most three times.

Never auto-merge the deny list or purge learning data. Missing configuration is recorded as an empty surface, not silently inferred as secure.
