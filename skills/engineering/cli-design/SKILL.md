---
name: cli-design
description: "Design a Linux CLI contract: syntax, streams, machine output, safety, configuration, and exit behavior."
user_invocable: false
allowed-tools: [Read, Write, Grep, Glob, Bash]
routing:
  triggers: ["design a CLI", "CLI interface", "command line tool design", "CLI flags", "CLI spec", "argument parsing design", "exit codes"]
  category: engineering
  pairs_with: [testing, code-quality]
---

# CLI Design

Produce a Linux-only, language-neutral interface contract before implementation. Ask only about missing choices that alter it: purpose, audience, inputs, machine output, interactivity, destructive actions, and configuration.

Load `references/clig-checklist.md` while designing. Deliver a compact, language-neutral spec containing:

1. exact usage synopsis and subcommands, including mutation/idempotence;
2. argument/flag table: type, default, requirement, example;
3. stdin/stdout/stderr and stable machine-output schema;
4. exit-code map; add codes beyond 0/1/2 only when callers branch on them;
5. noninteractive/destructive behavior and config precedence;
6. examples for the main path, failure path, and a pipeline.

Before delivery, verify every example flag is declared and every described failure maps to an exit code. For a design-only request, stop at the spec. If design and implementation are requested together, use the spec as the implementation contract.
