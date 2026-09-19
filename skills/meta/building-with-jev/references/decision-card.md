# Decision card

Complete one card per gate or judgment before writing code. Each field
constrains the design; an empty field is a gap, not an option.

## Fields

1. **Desired behavior.** State the decision, the unit it applies to, and what
   happens when the system acts correctly. Name a non-Jev baseline (majority
   class, strongest single signal, existing rule) and its measured accuracy.
2. **Judgments.** List every Jev question, its primitive, and what each returned
   number means for this domain. Define "high," "low," and "ambiguous" with
   concrete examples.
3. **Evidence source.** Name the data the state draws from, its refresh rate,
   and any coverage gaps (missing labels, skewed slices, stale sources). State
   which gaps the design tolerates and which would invalidate it.
4. **Deterministic policy.** Write the pure function `policy(answers) -> action`
   with named thresholds. State which code path owns each action and who is
   accountable for the outcome.
5. **Batchable vs dependent steps.** Mark each question as batchable (runs in
   the same request, no data dependency) or dependent (needs a prior answer
   before it can be asked). Dependent steps add a second request; justify each.
6. **Failure and abstention.** Define behavior when Jev is unavailable, when
   confidence is below the gate, and when the response is malformed. State
   whether the gate fails open, fails to warn, or fails to block.
7. **Falsifying experiment.** Describe the smallest labeled test that could
   reject this design: the split, the metric, and the threshold below which
   the gate is not worth shipping.
8. **Versions.** Pin the Jev model id, the rubric version (date or hash), and
   the policy version. State what triggers re-evaluation: a model upgrade, a
   rubric edit, a data distribution shift, or a policy change.

## Usage

Fill the card in the ADR, design doc, or code comment before the first Jev
call ships. Review the card when any version field changes. A gate that ships
without a card has no defined failure behavior and no falsifying experiment
-- it cannot be evaluated or retired.
