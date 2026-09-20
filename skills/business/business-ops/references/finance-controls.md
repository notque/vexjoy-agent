# Finance controls

Load for journal entries, reconciliations, statements, close, audit support, or variance analysis.

## Accounting invariants

- A journal entry must balance: total debits equal total credits. Use the user's chart of accounts; never infer account codes. Include date, currency, entity, description, source support, preparer/reviewer, and reversal treatment when relevant.
- Preserve `assets = liabilities + equity`. Net income closes into equity; cash-flow movements reconcile opening to closing cash; ending balance-sheet cash agrees to it.
- State the reporting basis (GAAP, IFRS, tax basis, or management reporting). Do not silently mix recognition rules or periods.
- A reconciliation ties a ledger balance to an independent source at the same cutoff. Show book balance, source balance, every reconciling item, adjusted balances, difference, owner, age, support, and disposition. Never plug an unexplained difference.
- Separate timing differences from errors. Long-aged or recurring items remain control signals even when balances agree.
- Keep an audit trail from each reported number to source evidence. Missing support is an exception, not zero.

## Variance decomposition

Define sign convention first. For revenue with quantity `Q` and price `P`:

- Volume: `(Actual Q - Budget Q) * Budget P`
- Price: `Actual Q * (Actual P - Budget P)`

These sum to total variance under this convention. For multiple products, isolate mix; do not attribute all quantity movement to volume. Separate currency effects when rates differ. Label favorable/unfavorable from the business perspective—a positive sign is not inherently favorable.

## Action-changing checks

- Bank: stale checks, deposits in transit, duplicates, fees, cutoff, unauthorized items.
- Receivables: subledger-to-control-account tie, credits and unapplied cash, disputes and aging.
- Payables: duplicate invoices, unmatched receipts, vendor-statement differences, post-cutoff liabilities.
- Intercompany: both entities, currency/rate, identifiers, reciprocal balances, bilateral owner.
- Estimates/accruals: method, source population, cutoff, reversal, sensitivity. Prior-period actuals are evidence, not automatic current amounts.
- SOX/audit: distinguish control design from operating effectiveness; name population, sample, evidence, exception, compensating control, and remediation owner. Document review alone provides no assurance.

Real filings, tax positions, and booked entries require qualified review before execution.
