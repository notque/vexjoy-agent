# Objective-loop specification

Freeze before iteration: one objective, deterministic done criteria (rubric only
when mechanics cannot decide), iteration budget, and NOT-DONE-YET guardrails.
Each iteration chooses the smallest next action through `/do`, records its
receipt, and independently reruns every criterion. Workers never grant DONE.
Criteria cannot be edited mid-loop or satisfied by weakening a test, hook, gate,
or safety control. Stop on all-pass, exhausted budget, or guardrail conflict.
