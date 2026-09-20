# Operational controls

Load for support, runbooks, incidents, changes, migrations, process controls, or vendor operations.

## Support and incidents

Priority follows impact, scope, urgency, workaround, and safety/compliance exposure—not customer emotion alone. Use the local severity/SLA definition; otherwise explain the evidence and mark priority provisional.

Never invent reproduction steps, ticket history, root cause, resolution, quotes, entitlement, or ETA. An escalation preserves: exact symptom and expected behavior; affected users/tenants; start time, frequency, environment, impact; logs/error IDs; changes near onset; attempted steps and results; workaround and limits; owner, next update, dependencies, and explicit question.

A knowledge-base article requires a verified resolution. Separate symptom, scope/prerequisites, diagnosis, procedure, validation, rollback, and escalation. Never publish a hypothesis as a fix.

## Runbooks and change

Runbooks need executable preconditions, permissions, local commands or observations, expected results, stop conditions, rollback, escalation, validation, and evidence capture. A procedure without a failure branch is incomplete.

For changes and migrations:

1. Capture baseline and success measures before mutation.
2. Establish dependencies, owners, access, capacity, data classification, and compatibility.
3. Test restore where data can be lost; a backup existing does not prove recoverability.
4. Give rollback a trigger, decision owner, point of no return, and time budget. If impossible, state the roll-forward plan.
5. Limit blast radius with pilot/canary scope; validate business outcomes and system health.
6. Reconcile completeness and correctness after movement; matching row counts alone is insufficient.

Separate hazard, cause, consequence, control, residual risk, trigger, and owner. Probability × impact ranks risk but cannot override mandatory controls or hide catastrophic low-probability outcomes.

## Vendors

Apply hard eliminators (security, residency, integration, legal, continuity) before scores. Verify sales claims through a representative proof of concept and contractual evidence. A roadmap promise is not a capability without an enforceable remedy.

Evaluate exit before entry: usable export, deletion proof, transition help, dependencies, credential revocation, retention, switching cost, concentration risk, and vendor failure or ownership change.
