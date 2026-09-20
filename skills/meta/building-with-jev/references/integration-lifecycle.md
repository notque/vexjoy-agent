# Integration lifecycle

Every integration has five explicit parts: evidence reader, bounded state builder, Jev call, deterministic policy/action, and persisted receipt. Persist model/question/policy versions, source IDs, payload hash, attempts, timing, usage, raw answers, failure, and whether the answer changed action.

Choose the hook point that sees the evidence: pre-action gates cannot verify unseen output. Reusable earlier judgments travel as labeled `prior_results`; later LLMs act on them rather than silently re-grading them.

Unavailable, timeout, malformed, or partial responses become `unknown`. Define whether each gate fails open, fails to warn, or fails to block; none may turn failure into permission. Retry only transient failures, with a cap and one accounting record per send.

Ship an on-demand command first. Promote one hook at a time in shadow mode after labels show accuracy, answers are non-constant, deterministic rules already handle obvious cases, and the answer changes a useful action. Monitor distribution, action-change rate, errors, p50/p95, and cost after promotion.
