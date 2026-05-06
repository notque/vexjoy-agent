# Data Analysis — Worked Examples

Three end-to-end examples showing how each phase applies to realistic inputs.

---

## Example 1: A/B Test Evaluation

User says: "Evaluate this A/B test - here's the CSV of results"

Actions:
1. FRAME: "Should we ship variant B?" Options: ship B, keep A, extend test. Evidence: conversion lift >1% with 95% CI excluding zero.
2. DEFINE: Conversion = orders/visitors per variant. Time: test period. Segments: mobile/desktop.
3. EXTRACT: Load CSV, profile 45k rows, check group sizes balanced, verify no date gaps.
4. ANALYZE: Variant B conversion 4.2% vs A 3.9%. Difference 0.3% (CI: -0.1% to 0.7%). Fails practical significance -- CI includes zero.
5. CONCLUDE: "Data is inconclusive. The observed 0.3% lift has a confidence interval that includes zero. Recommend extending the test for 2 more weeks to reach adequate power."

---

## Example 2: Trend Analysis

User says: "What's happening with our monthly revenue? Here's 2 years of data."

Actions:
1. FRAME: "Is revenue growth slowing, and should we invest in acquisition?" Options: increase spend, maintain, cut.
2. DEFINE: Revenue = sum of invoice amounts per month. Growth = month-over-month %. Segments: new vs returning customers.
3. EXTRACT: Load 24 months, verify no missing months, check for outliers (December spike).
4. ANALYZE: Overall +2.1%/mo but returning customer revenue flat. All growth from new customers. Seasonality adjusted.
5. CONCLUDE: "Revenue growth is entirely acquisition-driven. Returning customer revenue has been flat for 8 months, suggesting a retention problem. Recommend investigating churn before increasing acquisition spend."

---

## Example 3: Distribution Profiling

User says: "Our API response times feel slow. Here's a week of latency data."

Actions:
1. FRAME: "Do we need to optimize the API?" Options: optimize, add caching, do nothing. Threshold: p99 >500ms warrants action.
2. DEFINE: Latency = request duration in ms. Segments: by endpoint, by hour. Key metrics: p50, p95, p99.
3. EXTRACT: Load 1.2M requests, check for timestamp gaps, identify endpoints.
4. ANALYZE: p50=45ms (fine), p99=890ms (exceeds threshold). /search endpoint contributes 73% of p99 violations. Peak hours 2x worse.
5. CONCLUDE: "p99 latency exceeds the 500ms threshold, concentrated in /search during peak hours. Recommend optimizing /search specifically rather than system-wide caching."
