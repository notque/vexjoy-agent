# Antigravity CLI (`agy`) & Google AI (Argon) Execution Reference for `/do`

Use this reference when running `/do` (or `/d`) inside the Antigravity CLI (`agy`) or with Google AI models (`gemini-4-argon`, `gemini-3.8-flash`). It maps every phase of VexJoy's `/do` router to Antigravity's native multi-agent primitives (`/teamwork`, `run_workflow`), autonomous deep-work loop (`/goal`), slash commands, brain artifacts, and hook translation layer.

---

## 1. Runtime Detection & `build-dispatch.py` Contract

Detect the active harness before Phase 4 dispatch:

```bash
python3 "$SDIR/detect-workflow-capability.py"
# -> {"harness": "antigravity", "workflow_capable": true}
```

When `harness == "antigravity"` (or `ANTIGRAVITY_AGENT=1`):
1. Pass `"provider": "google"` (or `"antigravity"`) in the `build-dispatch.py` JSON payload.
2. Select models from the **Google AI Model Selection Table** below instead of Claude model names.
3. Dispatch workers using Antigravity's native subagent tools (`define_subagent`, `invoke_subagent`, `send_message`, `manage_subagents`) or Python `run_workflow` tool when present in your live tool list.

---

## 2. Google AI (Argon & Flash) Model Selection

Select `model` (and optional `model_effort` or `model_policy`) in `build-dispatch.py` based on task risk and complexity, and map it to the `Model` parameter of `invoke_subagent` / `run_workflow`:

### 2.1 Automatic Policy Tiers (`model_policy` with `provider="google"`)

| `model_policy` | `build-dispatch.py` Emitted Marker | CLI Model Variant | `invoke_subagent` `Model` Arg | When to Select |
|---|---|---|---|---|
| `low-risk` | `model=gemini-3.8-flash effort=low` | `gemini-3.8-flash-low` | `"flash"` or `"flash_lite"` | Mechanical edits, file lookups, formatting, comment/doc fixes, read-only scouting |
| `standard` | `model=gemini-4-argon effort=medium` | `gemini-4-argon-medium` | `"inherit"` (or `"pro"`) | Feature implementation in existing patterns, standard debugging, unit/integration tests |
| `high-risk` | `model=gemini-4-argon-high effort=high` | `gemini-4-argon-high` | `"pro"` or `"inherit"` | Multi-file refactors, concurrency, security-sensitive paths, complex architecture |
| `max-power` | `model=gemini-4-argon-high effort=max` | `gemini-4-argon-high` (`--effort max`) | `"pro"` | Escalation tier after a miss, deep root-cause debugging, adversarial security audit (requires `manual_model_override: true`) |

### 2.2 Task-Type Routing Table for Google AI

| Task Type | `build-dispatch.py` `model` | `model_effort` | `invoke_subagent` `Model` | Escalation Path on Verification Miss |
|---|---|---|---|---|
| Locate, lookup, cite lines, inventory | `gemini-3.8-flash` | `low` | `flash` (on `research` subagent) | `gemini-4-argon` (`medium`) |
| Mechanical edit (rename, config, boilerplate) | `gemini-3.8-flash` | `medium` | `flash` | `gemini-4-argon` (`medium`) |
| Code review / planted-bug scan | `gemini-4-argon` | `medium` | `inherit` | `gemini-4-argon-high` (`high`) |
| Debug: root cause + regression test | `gemini-4-argon` | `medium` | `inherit` | `gemini-4-argon-high` (`high`) |
| Feature implementation (multi-file) | `gemini-4-argon` | `medium` | `inherit` | `gemini-4-argon-high` (`high`) |
| Complex architecture / security / migration | `gemini-4-argon-high` | `high` | `pro` | `gemini-4-argon-high` (`max`, `manual_model_override: true`) |

---

## 3. Multi-Agent Teamwork (`/teamwork` Engine for Complex Tasks)

When Phase 1 classifies a request as `Complex` (or Phase 2 selects multiple `agents` for parallel fan-out), execute using Antigravity's `/teamwork` architecture:

```mermaid
flowchart LR
    Coord["/do Orchestrator (Argon)"] -->|1. define_subagent| Def["Register Domain Specialists from agents/*.md"]
    Def -->|2. invoke_subagent Workspace='branch'| W1["Worker 1 (Isolated Branch)"]
    Def -->|2. invoke_subagent Workspace='branch'| W2["Worker 2 (Isolated Branch)"]
    Def -->|2. invoke_subagent Workspace='inherit'| R1["Research Scout (Read-Only)"]
    W1 -->|Reactive Wakeup| Coord
    W2 -->|Reactive Wakeup| Coord
    R1 -->|Reactive Wakeup| Coord
    Coord -->|3. send_message| W1
    Coord -->|4. Synthesize + Self-Review| Out["Final Verified Delivery"]
```

### Step 1: Register Domain Specialists (`define_subagent`)
Antigravity ships built-in `self` (full tool access), `research` (read-only sandbox), and `image-generator` subagents. To dispatch a specialized VexJoy agent (such as `python-general-engineer`, `golang-general-engineer`, `reviewer-system`):
1. Read `agents/<agent-name>.md` to extract its role description and system prompt.
2. Call `define_subagent`:
   - `Name`: `"<agent-name>"`
   - `Description`: Specialist domain summary from frontmatter.
   - `SystemPrompt`: Full agent instructions + `agents/base-instructions.md` reference.
   - `EnableWriteTools`: `true` for implementers; `false` for reviewers/scouts.
   - `EnableMCPTools`: `true` when MCP documentation or external tools are needed.
   - `EnableSubagentTools`: `true` only for coordinators (`project-coordinator-engineer`, `research-coordinator-engineer`).

### Step 2: Dispatch with Native Workspace Isolation (`invoke_subagent`)
1. Run `build-dispatch.py` **once per agent** so each worker receives its own `[do-route]` marker line, scoped `task_spec.files`, and `ownership` boundaries.
2. Call `invoke_subagent(TypeName, Role, Prompt, Model, Workspace)`:
   - **`Workspace="branch"`**: Creates an isolated workspace branched/cloned from the parent. **Mandatory** when 2+ parallel implementers edit files concurrently (replaces manual `git worktree` creation).
   - **`Workspace="share"`**: Shares the underlying repository metadata (worktree-style) for lightweight independent branching without duplicating storage.
   - **`Workspace="inherit"`**: Uses the parent workspace directly. Use for single-agent dispatches, read-only `research` scouts, or sequential phases with non-overlapping files.

### Step 3: Reactive Wakeup & Stateful Continuation (`send_message`)
- **Zero Polling Rule (HARD CONSTRAINT)**: `invoke_subagent` launches asynchronously. After invoking subagents, **do not poll in a loop or run shell `sleep` commands**. Either perform independent non-dependent work or stop calling tools to end your turn; Antigravity automatically wakes you when a subagent replies or completes.
- **Continue Existing Subagents via `send_message`**: When a worker needs a follow-up fix, test retry, or review correction, call `send_message(Recipient="<conversationId>", Message="...")` instead of calling `invoke_subagent` again. The existing subagent retains its full file context and reasoning trajectory.

### Step 4: Lifecycle & 3-Strike Circuit Breaker (`manage_subagents`)
- Use `manage_subagents(Action="list")` to inspect live subagent states when coordinating a large fan-out.
- If a subagent hits the 3-strike verification failure limit (`quality-loop.md` Phase 7) or enters a loop, call `manage_subagents(Action="kill", ConversationIds=["<conversationId>"])` to terminate it and clean up its branched workspace while preserving logs and artifacts.

---

## 4. Deterministic Python Workflows (`run_workflow` Tool)

When `run_workflow` is available in your active tool list and Phase 2 selected a multi-phase pipeline (or `Complex` fan-out), you can execute a deterministic Python orchestration script instead of manual turn-by-turn handoffs:

- **Reference Template**: `skills/process/workflow/references/fan-out-workflow.py`
- **Core Primitives**:
  - `phase("Phase Name")`: Declares a named workflow phase in the UI.
  - `await agent(prompt, schema=..., role=..., type_name=..., workspace="branch"|"share"|"inherit", model="inherit"|"flash"|"pro")`: Spawns a subagent and validates its structured output against `schema` (Pydantic `BaseModel` or JSON Schema).
  - `await parallel([agent(...), agent(...)])`: Runs independent workers concurrently and gathers results.
  - `await pipeline([step1, step2])`: Chains sequential stages where each stage consumes the prior output.
  - `trajectory(result)`: Inspects the subagent's execution trajectory (`steps`, `tool_calls`, `files_modified`) for deterministic quality-gate verification before advancing to the next phase.
- **Telemetry Preservation**: Include the `[do-route]` marker generated by `build-dispatch.py` at line start inside each worker `prompt` string in the Python workflow script; `hooks/agy-hook-adapter.py` maps `run_workflow` (`Script`) to `Workflow` (`script`) so `hooks/routing-decision-recorder.py` records every worker marker automatically.

---

## 5. Deep Autonomous Work (`/goal` Mode Integration)

When the user invokes `/do` alongside `/goal` (or requests `<afk-mode>`, "loop until done", or an objective with verifiable done-criteria):

1. **Checklist Grounding**: Create and maintain `<appDataDir>/brain/<conversation-id>/task.md` mapping every explicit deliverable to concrete verification evidence.
2. **Quality-Loop Enforcement**: Execute all applicable stages of `references/quality-loop.md` (`PLAN` → `IMPLEMENT` → `VERIFY` → `REVIEW` → `FIX` → `EVALUATE` → `LIVE-VALIDATE`).
3. **Stop Hook Continuation Protocol**:
   - In `/goal` mode, Antigravity's `Stop` hook blocks termination until every deliverable is verified with fresh execution output (test results, lint, build logs, `git status`).
   - **Never** emit `<!-- GOAL_COMPLETE -->` while any checklist item is unverified, while tests fail, or while only a plan exists for an implementation request.
   - Emit `<!-- GOAL_COMPLETE -->` at the end of your final response **only** after all deliverables and verification gates pass.
   - Emit `<!-- GOAL_CANCELLED -->` only if the user explicitly asks to cancel or stop the goal.

---

## 6. Incorporating All Antigravity CLI Slash Commands & Capabilities

`/do` evaluates and incorporates every native Antigravity CLI slash command and tool into its 6-phase pipeline:

| Antigravity Command / Tool | `/do` Phase | How `/do` Incorporates or Recommends It |
|---|---|---|
| **`/teamwork`** (`define_subagent`, `invoke_subagent`, `send_message`, `manage_subagents`) | Phase 2 & Phase 4 (Complex / Fan-Out) | Directly executes parallel specialist fan-out with `Workspace="branch"\|"share"` isolation and `send_message` iterative handoffs. Recommend `/teamwork` when the user wants a persistent autonomous agent team across an entire project. |
| **`/goal`** (`<!-- GOAL_COMPLETE -->` + `Stop` hook loop) | Phase 3 & Phase 4.5 (Objective / Deep Work) | Couples VexJoy's `objective-loop` and `quality-loop.md` with `/goal` completion gates so long-running tasks never stop prematurely. Recommend `/goal` for overnight or multi-hour autonomous runs. |
| **`/plan`** (`implementation_plan.md` + `walkthrough.md` in `<appDataDir>/brain/<conversation-id>/`) | Phase 4 Step 1 & Phase 5 | Writes structured brain artifacts (`implementation_plan.md` with `ArtifactMetadata: {RequestFeedback: true, UserFacing: true}`) for user review before risky/complex changes, plus `task_plan.md` for repo-local checkpointing and `walkthrough.md` at completion. |
| **`/grill-me`** + **`ask_question`** tool | Phase 3 (Ambiguity Gate / Depth-First Interview) | Uses Antigravity's native `ask_question` tool (`questions` array, unnumbered `options`, `(Recommended)` prefix on first option, `is_multi_select`) to batch independent decision frontiers (`pl-depth-first-interview.md`). Recommend `/grill-me` when the user wants an exhaustive interactive design interview. |
| **`/boost`** (Deep Thinking + Multi-Perspective Verification + Scratch Prototyping) | Phase 3 & Phase 4.5 (`high-risk` / `max-power`) | Escalates to `gemini-4-argon-high` (`effort: "high"` or `"max"`), runs multi-perspective review fan-out (`reviewer-code`, `reviewer-system`, `reviewer-domain`, `reviewer-perspectives`), and builds empirical prototypes (`pl-empirical-prototype.md`) in `<appDataDir>/brain/<conversation-id>/scratch/`. |
| **`/browser`** | Phase 4.5 Stage 6 (`LIVE-VALIDATE`) | Validates web applications, UI components, and visual regressions in a live browser alongside `playwright-cli`. |
| **`/schedule`** (`schedule` tool) & **`/automation`** (Sidecars) | Phase 4 (Async Monitoring / Recurring Tasks) | Uses the native `schedule` tool (`DurationSeconds` or `CronExpression` + `TimerCondition`) instead of bash `sleep` polling; uses `~/.gemini/config/sidecars/<id>/sidecar.json` (`automation` skill) for standing background daemons. |
| **`/compact`** | Phase Boundaries (Context Hygiene) | When `suggest-compact.py` or context length signals pressure between phases, checkpoints state to `task_plan.md` and brain artifacts, then recommends `/compact`. |
| **`/learn`** | Phase 5 (Post-Task Learning & Rule Graduation) | Records routing and error learnings to `learning.db` (`rules-distill-trigger.py`) and graduates durable workflow corrections into `.agents/rules/*.md` or `GEMINI.md` (with `trigger: always_on`, `glob`, `manual`, or `model_decision`). |

---

## 7. Google AI (Argon) Best Practices & Sandbox Discipline

1. **Sandbox-First Command Execution (`run_command`)**:
   - Always run commands in Standard Sandbox Mode (`BypassSandbox: false`) first.
   - Keep command shapes prefix-matchable for auto-approval: invoke target binaries directly (`git`, `pytest`, `python3`), avoid unnecessary command substitutions `$(...)` or wrapper binaries (`env`, `eval`), and split unsandboxed network steps from local preparation/test steps.
2. **Exact Tool & Symbol Grounding**:
   - Format all file and symbol references as clickable Markdown links using `file://` (`[build-dispatch.py](file:///abs/path/scripts/build-dispatch.py#L1-L50)`).
   - Use `read_file`, `edit_file`, and `write_file` instead of shell `cat`/`sed`/`awk` for file operations so `PostToolUse` hooks (`edit_file|write_file`) and file backups trigger deterministically.
3. **Writing Style Precedence**:
   - Follow `CLAUDE.md` / `GEMINI.md` precedence: **Completeness floor** (never omit required technical facts or verification evidence) > **Google Developer Documentation Style** (active voice, second person, context-before-instruction) > **Dense-Complete conciseness**.
