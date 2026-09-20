# Requirement compliance reviewer contract

Review only whether the implementation matches the supplied task/ADR. Receive its complete requirements, expected paths/behavior, verification, and the implementation diff from the task’s base SHA.

Return a requirement table with evidence, unrequested extras with keep/remove rationale, and exactly one verdict: `COMPLIANT` or `NOT COMPLIANT`. List missing, extra, and behavior-mismatch items separately. Do not perform a general quality review.
