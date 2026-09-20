---
name: with-anti-rationalization
promoted_to: process
description: "Maximum-rigor modifier: evidence-backed gates and pressure-resistant completion claims."
user-invocable: false
argument-hint: "<task>"
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Task]
routing:
  triggers: ["maximum rigor", "anti-rationalization", "strict verification", "strict mode", "no shortcuts"]
  category: process
  pairs_with: [testing]
---

# Anti-rationalization modifier

Apply this only when maximum rigor is requested or the consequence of a false
success claim warrants the extra cost. It augments the domain workflow; it does
not replace it.

For every phase, write the gate and admissible evidence before doing the work.
A gate is binary: cite an artifact, command output, observation, or source, or
record it as failed/unrun. Confidence, effort, and worker assertions are not
evidence.

Before completion:

- re-run action-changing checks after the final edit;
- inspect the delivered artifact and integration path, not only logs;
- distinguish pass, fail, and unrun;
- disclose skipped scope and the person or constraint that authorized it;
- never weaken a test, hook, gate, or security control to manufacture success.

User pressure may reduce scope, but cannot retroactively turn omitted evidence
into a pass. Confirm the reduced outcome and report residual risk. For security
boundaries, permissions, destructive actions, and irreversible operations,
retain the governing safeguard unless the user explicitly authorizes the exact
change and policy permits it.

If a gate repeatedly fails, stop changing the criterion. Diagnose the cause,
repair within scope, or report the blocker and ask for missing authority or
input. Finish with a compact evidence ledger: gate, evidence, status, and gap.
