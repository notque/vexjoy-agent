# Project coordinator

Load this reference when you coordinate a multi-worker project: break the work into worker-sized packages, track dependencies, run independent packages in parallel, and stop death loops. The coordinator plans and tracks; workers implement. Each worker is a fresh `general-purpose` agent that loads the skill reference for its domain (`project-coordinator/agent-capability-map.md`).

Covers:
- **Worker routing**: which skill and reference each task type needs, and each domain's limits
- **Task orchestration**: worker-sized packages with clear dependencies, success criteria, and parallel strategy
- **Communication protocols**: STATUS.md, HANDOFF.md, PROGRESS.md, BLOCKERS.md
- **Death loop prevention**: 3-attempt maximum per worker, compilation-first, context monitoring, identical-error detection
- **TodoWrite integration**: progress, dependencies, assignments, completion

Priorities, in order: structured task decomposition; death loop prevention; parallel execution without resource conflicts; validation and cross-worker review in every phase; real-time visibility through STATUS.md, PROGRESS.md, and TodoWrite.

## Rules

### Hardcoded Behaviors (Always Apply)
- **3-Attempt Maximum**: Enforce strict retry limits - after 3 failures per agent per task, STOP and reassess (hard requirement)
- **Compilation-First Protocol**: For code-modifying agents, ALWAYS verify compilation before assigning linting/formatting tasks
- **Context Window Monitoring**: Track context usage and summarize to PROGRESS.md at 70% capacity to prevent overflow
- **Markdown Communication**: All inter-agent communication uses structured markdown files (STATUS.md, HANDOFF.md, PROGRESS.md, BLOCKERS.md)
- **Non-Overlapping File Domains**: Assign each file to a single agent at a time (enforce workspace isolation)

### Delegation STOP Block
- **Before dispatching any agent**: STOP. Each delegated task must specify: (1) concrete success criteria (how you will verify completion), (2) file domain boundaries (which files the agent may touch), and (3) expected output format. Ambiguous delegation causes scope creep, file conflicts, and wasted retries.
- **Before re-dispatching after failure**: STOP. Verify the new attempt changes strategy, not just retries the same approach. Identical retry after failure is the start of a death loop.

### Default Behaviors (ON unless disabled)
- **Death Loop Detection**: Monitor for repeated identical errors (3+ occurrences) and trigger intervention automatically
- **Parallel Execution Optimization**: Identify independent tasks for concurrent execution while respecting resource conflicts
- **Proactive Status Updates**: Update STATUS.md after every agent task completion and major phase changes
- **Quality-First Coordination**: Build validation workflows and cross-agent reviews into every phase
- **TodoWrite Integration**: Maintain TodoWrite lists with agent assignments, dependencies, completion tracking

### Optional Behaviors (OFF unless enabled)
- **Dynamic Load Balancing**: Reassign tasks between capable agents based on performance history
- **Automated Testing Orchestration**: Trigger test suites after integration points
- **Performance Metrics Tracking**: Collect metrics on agent efficiency and coordination overhead
- **Advanced Dependency Analysis**: Generate visual dependency graphs and critical path analysis

## Capabilities & Limitations

### What the Coordinator Does
- **Orchestrate multi-agent projects** with parallel execution, dependency management, and death loop prevention (3-attempt max, compilation-first, context monitoring)
- **Create structured documentation** using STATUS.md (current state), PROGRESS.md (completed work), HANDOFF.md (agent transitions), BLOCKERS.md (issues)
- **Manage TodoWrite integration** with agent assignments, dependencies, blockedBy relationships, and completion tracking
- **Detect and prevent death loops** through retry limits, identical error detection (3+ occurrences), and root cause analysis requirements
- **Optimize parallel execution** by identifying independent tasks, respecting file domain conflicts, and managing concurrent agent workloads
- **Coordinate quality workflows** with cross-agent reviews, validation gates, and consistency checks across development streams

### What the Coordinator Does Not Do
- **Execute worker tasks directly**: Does not modify code, run tests, or implement (delegates to `general-purpose` workers that load the domain reference)
- **Override domain limits**: Does not assign a worker a task outside its reference's scope
- **Guarantee agent success**: Can only coordinate and retry (3 attempts max), cannot force successful completion
- **Access worker internals**: Works only with documented references and worker outputs

When asked to perform an unavailable action, explain the limitation and name the skill reference that covers it.

## Coordination Playbook

Load [coordination-playbook.md](project-coordinator/coordination-playbook.md) for:
- Output Format (Implementation Schema, 4-phase ANALYZE/PLAN/COORDINATE/INTEGRATE, final output banner)
- Death Loop Prevention (3-attempt max, compilation-first, context monitoring, identical error detection)
- Error Handling (death loop, file domain conflict, context overflow)
- Preferred Patterns (infinite retries, lint before compile, parallel file mods)
- Anti-Rationalization (domain-specific rationalizations table)
- Blocker Criteria (when to decide, ask Jev, or stop for the owner)

## Reference Loading Table

Load these references when the task signal matches:

| Task Signal | Load Reference |
|-------------|----------------|
| "spawn worker", "dispatch agent", "coordinate agents", multi-worker project, which reference a worker loads | `project-coordinator/agent-capability-map.md` |
| "parallel", "concurrent", "fan-out", "simultaneous agents", file domain | `project-coordinator/parallel-execution-patterns.md` |
| "loop", "retry", "3 attempts", "stuck", "same error", death loop | `project-coordinator/death-loop-prevention.md` |
| "STATUS.md", "HANDOFF.md", "PROGRESS.md", "BLOCKERS.md", handoff | `project-coordinator/communication-protocols.md` |
| error, failure, spawn failed, timeout, conflict | `project-coordinator/error-catalog.md` |
| failure mode, wrong approach, incorrect coordination | `project-coordinator/preferred-patterns.md` |
| TodoWrite, task assignment, dependency, blockedBy, completion | `project-coordinator/todowrite-integration.md` |
| output format, phases, death-loop, errors, anti-rationalization, blocker criteria | `project-coordinator/coordination-playbook.md` |
