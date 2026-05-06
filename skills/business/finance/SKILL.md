---
name: finance
description: Finance and accounting workflows — journal entries, reconciliation, variance analysis, financial statements, audit support, month-end close, SOX testing. Use when preparing journal entries, reconciling accounts, analyzing variances, generating statements, or supporting audits.
routing:
  triggers:
    - "finance"
    - "journal entry"
    - "reconciliation"
    - "variance analysis"
    - "financial statements"
    - "audit"
    - "month-end close"
    - "SOX"
  category: business
  force_route: false
  pairs_with: []
user-invocable: true
---

# Finance & Accounting

Umbrella skill for finance and accounting workflows. Detects the domain from the user's request, loads the right reference files, and executes. All output is working material for qualified professionals — not financial advice.

**Scope**: Journal entries, reconciliation, variance analysis, financial statements, audit/SOX support, month-end close. Use csuite for strategic finance decisions, data-analysis for ad-hoc analytics.

---

## Mode Detection

Classify into exactly one mode before proceeding.

| Mode | Signal Phrases | Reference to Load |
|------|---------------|-------------------|
| **JOURNAL ENTRY** | book, accrue, accrual, depreciation, prepaid, payroll entry, revenue recognition, deferred revenue, journal entry | `references/journal-entries.md` |
| **RECONCILIATION** | reconcile, bank rec, subledger, GL-to-sub, intercompany, reconciling items, aging | `references/reconciliation.md` |
| **VARIANCE** | variance, flux, budget vs actual, period-over-period, price/volume, waterfall, bridge | `references/variance-analysis.md` |
| **STATEMENTS** | P&L, income statement, balance sheet, cash flow, financial statements, GAAP presentation | `references/financial-statements.md` |
| **AUDIT/SOX** | SOX, control testing, sample selection, workpaper, deficiency, material weakness, ITGC, audit | `references/journal-entries.md` + `references/reconciliation.md` |
| **CLOSE** | month-end close, close calendar, close checklist, close day, hard close, soft close | `references/reconciliation.md` + `references/journal-entries.md` |

Always load `references/llm-finance-failure-modes.md` as a guard rail regardless of mode.

---

## Workflow

### Phase 1: CLASSIFY

1. Detect mode from user request
2. Load the corresponding reference file(s)
3. Load `references/llm-finance-failure-modes.md`
4. Confirm scope with user if ambiguous

### Phase 2: GATHER

Collect the data needed for the task:

| Mode | Required Inputs |
|------|----------------|
| JOURNAL ENTRY | Entry type, period, account codes, amounts or source data |
| RECONCILIATION | GL balance, comparison source (bank statement, subledger, counterparty), period |
| VARIANCE | Current period data, comparison period data, materiality thresholds |
| STATEMENTS | Trial balance or financial data, comparison periods, presentation preferences |
| AUDIT/SOX | Control area, testing period, population data, prior results |
| CLOSE | Close calendar dates, task ownership, current status |

If the user provides partial data, ask for the minimum additional data needed. Do not fabricate account codes, balances, or transaction details.

### Phase 3: EXECUTE

Follow the mode-specific workflow from the loaded reference file. Key constraints apply across all modes:

**Debit/Credit Rules (always enforce):**

| Account Type | Normal Balance | To Increase | To Decrease |
|-------------|---------------|-------------|-------------|
| Asset | Debit | Debit | Credit |
| Liability | Credit | Credit | Debit |
| Equity | Credit | Credit | Debit |
| Revenue | Credit | Credit | Debit |
| Expense | Debit | Debit | Credit |
| Contra Asset | Credit | Credit | Debit |
| Contra Revenue | Debit | Debit | Credit |

**Verification gates (every journal entry):**
- Debits = Credits (balanced entry, no exceptions)
- Account codes come from user data, never invented
- Amounts traced to source calculations
- Period is explicit and correct
- Reversal flag set for accruals

**Verification gates (every reconciliation):**
- Both sides reconcile to the same adjusted balance
- Every reconciling item is categorized (timing, adjustment, investigation)
- Items aged >60 days flagged for escalation

**Verification gates (every variance):**
- Decomposition components sum to total variance (verify arithmetic)
- Materiality threshold applied before narrative generation
- Narratives are causal (why), not circular ("revenue was higher due to higher revenue")

### Phase 4: VALIDATE

Before presenting output:

1. **Arithmetic check**: Verify all calculations. Re-derive totals from components. Because LLMs miscalculate, re-check every sum, difference, and percentage (see failure modes reference).
2. **Completeness check**: All required sections present per the reference file template
3. **Anti-hallucination check**: No fabricated account numbers, GAAP citations, or standards references. If uncertain about a specific GAAP rule, say so.
4. **Consistency check**: Treatment matches prior period (if prior period data provided)

### Phase 5: DELIVER

Present output in the format specified by the reference file for the mode. Include:
- The working artifact (entry, reconciliation, analysis, statement)
- Supporting calculations
- Items flagged for professional review
- Suggested next steps

---

## LLM Failure Modes in Finance

These are the ways LLMs most commonly fail in finance work. Internalize these before executing any mode.

### Calculation Errors

LLMs perform arithmetic unreliably. Every number in the output must be verified.

| Failure | Example | Mitigation |
|---------|---------|------------|
| Wrong sums | Three line items of $127K, $89K, $214K totaled as $420K (actual: $430K) | Re-derive every total from components |
| Percentage errors | $28K variance on $500K base reported as "4.6%" (actual: 5.6%) | Recompute: variance / base x 100 |
| Sign errors | Favorable variance presented as unfavorable | Confirm: actual > budget for revenue = favorable; actual > budget for expense = unfavorable |
| Rounding cascade | Individual items rounded then summed, producing different total than sum-then-round | Round at the final step, not intermediate steps |
| Debit/credit imbalance | Entry with $150K debit and $145K credit presented as "balanced" | Verify sum(debits) == sum(credits) explicitly |

### Fabricated Standards and Rules

LLMs confidently cite nonexistent GAAP/IFRS standards.

| Failure | Example | Mitigation |
|---------|---------|------------|
| Invented ASC numbers | "Per ASC 842-30-55-12" when no such paragraph exists | Only cite ASC/IFRS at topic level. When uncertain: "Consult the relevant ASC guidance" |
| Misapplied rules | Applying lease accounting rules to a service contract | State the standard being applied and let the professional verify applicability |
| Conflated GAAP/IFRS | Mixing US GAAP and IFRS rules without distinguishing | Default to US GAAP. State which framework. Never blend silently |
| Outdated standards | Referencing superseded guidance (e.g., pre-ASC 606 revenue rules) | Flag when a standard has been superseded and note the replacement |

### Misapplied Materiality

| Failure | Example | Mitigation |
|---------|---------|------------|
| No threshold applied | Investigating a $500 variance on a $50M revenue line | Apply materiality thresholds before investigating |
| Wrong benchmark | Using net income as materiality base for a balance sheet item | Match benchmark to the financial statement element |
| Inconsistent application | Investigating 3% variance on one line, ignoring 8% on another | Apply thresholds uniformly across all line items |

### Period and Cut-off Errors

| Failure | Example | Mitigation |
|---------|---------|------------|
| Wrong period allocation | Booking December expense in January | Expense belongs in the period the service was received or goods delivered |
| Ignoring accrual basis | Recording expense only when cash is paid | Accrue when the obligation is incurred, not when cash moves |
| Partial period errors | Full month depreciation on asset placed in service mid-month | Apply the entity's convention (half-month, mid-quarter, exact days) |

### Account Code Fabrication

LLMs will generate plausible-looking account codes (e.g., "4100 — Revenue") when none are provided.

**Rule**: Use codes from the user's chart of accounts. Use descriptive placeholders when codes are unavailable: `[Revenue Account]`, `[Accrued Liabilities Account]`.

---

## Failure Modes by Mode

### Journal Entry Failure Modes

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| Unbalanced entry presented as complete | Violates fundamental accounting equation |
| Missing reversal flag on accruals | Creates double-counting in the next period |
| Round-number estimates without calculation basis | Signals fabrication, fails audit |
| Booking to "Miscellaneous Expense" | Lacks specificity for variance analysis and audit trail |
| Same person prepares and approves | Violates segregation of duties |

### Reconciliation Failure Modes

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| Forcing the rec to balance by plugging a number | Hides real differences that may indicate errors or fraud |
| Carrying items forward indefinitely without investigation | Stale items may represent losses or control failures |
| Reconciling to an unverified source | Both sides must come from authoritative sources |
| Skipping intercompany for "immaterial" entities | Intercompany must eliminate to zero in consolidation |

### Variance Analysis Failure Modes

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| Circular narrative ("revenue is higher because revenue increased") | No causal explanation |
| "Timing" without specifying what shifted and when it normalizes | Uninvestigable claim |
| "Various small items" for a material variance | Must decompose until below materiality |
| Ignoring offsetting variances | Net favorable can hide serious unfavorable components |
| Missing outlook (one-time vs recurring) | Variance without context is useless for forecasting |

### Financial Statement Failure Modes

| Anti-Pattern | Why It Fails |
|-------------|-------------|
| Assets not equal to liabilities + equity | Balance sheet does not balance |
| Mixing functional and nature expense classification | GAAP requires consistency within a statement |
| Omitting non-cash items in cash flow reconciliation | Indirect method requires all non-cash adjustments |
| Current/non-current misclassification | Debt maturing within 12 months must be current |
