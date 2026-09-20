# Routing telemetry

`scripts/build-dispatch.py` emits the sole routing marker consumed by the
routing recorder:

```
[do-route]
```

One dispatch produces one marker; fan-out produces one per agent. Do not pack
several markers into one manually constructed shell action.

When investigating a routing failure, preserve the user request, selected
agent/skill/pipeline, manifest version/hash when available, guard output,
fallback reason, and observed outcome. Derive quoted rates from the current
learning database/query and include numerator, denominator, time window, and
query provenance. Never retain prose percentages after their evidence expires.
