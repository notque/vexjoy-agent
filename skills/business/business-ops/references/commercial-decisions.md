# Commercial decisions

Load for strategy, investment, build/buy, vendor comparison, sales pipeline, or product metrics.

## Decision economics

Apply non-negotiable constraints before scores. Compare feasible options in base, upside, and downside cases.

- `ROI = (benefit - cost) / cost`
- `NPV = sum(cash_flow_t / (1 + discount_rate)^t) - initial_investment`
- Payback is when cumulative net cash flow first becomes non-negative; it ignores later value and, unless discounted, time value.
- LTV:CAC requires consistent cohort, gross margin, retention/churn model, attribution, and horizon.

Do not treat ordinal weighted scores as money. Use scores for preferences, financial models for economics, and sensitivity analysis to find assumptions that reverse the answer.

## Build, buy, migrate

Use the same horizon and usage scenarios. Include implementation, migration, integration, training, support, security/compliance, incidents, maintenance, growth pricing, lock-in, exit, and opportunity cost. Internal engineering is not free. Use local maintenance history or expose the assumption; do not impose a universal percentage.

Assess reversibility separately from expected value. A slightly lower-value option may win when it preserves learning and limits irreversible loss.

## Sales pipeline

Tie stages to buyer evidence, not seller activity. A sent proposal does not prove buyer-confirmed process, budget, authority, need, or timing. Preserve deal provenance when aggregating.

- Weighted pipeline: `sum(deal amount * stage probability)`; calibrate probabilities from historical conversion.
- Coverage: `open qualified pipeline / remaining quota`; coverage is diagnostic, not a forecast.
- Forecast categories need mutually exclusive entry/exit criteria and a date. Separate commit, best case, pipeline, closed, slipped, and lost.
- Decompose movement into new, advanced, regressed, expanded, contracted, won, lost, and slipped. A stable total can conceal deterioration.

Never invent competitor claims, buyer intent, history, pricing, or close dates. Separate sourced intelligence from salesperson inference.

## Product metrics

Define entity, event, eligibility, window, timezone, exclusions, and denominator. Never compare metrics whose definitions changed.

- Activation represents experienced value, not signup completion.
- Retention uses fixed cohorts and a named return event/window; report sample size and maturation.
- Funnels require consistent eligibility and ordering; exclude users without opportunity from the denominator.
- Experiments require assignment unit, primary metric, guardrails, exposure, power assumptions, and stopping rule. Post-result segment hunting is exploratory.
- Roadmaps preserve dependencies, mandatory work, risk reduction, and strategic constraints outside the score. Confidence means evidence quality, not enthusiasm.

## Market evidence

Separate direct evidence (behavior, contracts, switching, cohort economics) from proxies (search, funding, attention, analyst coverage). Trend claims need dated sources and independent signal types. A feature list is not positioning; relate alternatives to the customer's job, switching barrier, and willingness to pay.
