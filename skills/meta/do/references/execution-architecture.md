# Execution Architecture

**Router → Agent → Skill → Script**

1. **Router** (`/do` or `/d`) classifies request, selects agent + skill + pipeline
2. **Agent** (domain expert) executes with skill methodology:
   - **Claude Code**: `Agent` tool (`subagent_type`, `isolation: "worktree"`) or JS `Workflow` tool (`fan-out-workflow.js`).
   - **Antigravity CLI (`agy`) / Google AI (`gemini-4-argon`)**: In-thread persona adoption for Simple/Medium tasks (with `read_file` skill loading); `/teamwork` subagent primitives (`define_subagent`, `invoke_subagent(..., Workspace="branch"|"share"|"inherit")`, `send_message`, `manage_subagents`) or Python `run_workflow` tool (`fan-out-workflow.py`) for Complex/Fan-out tasks, paired with `/goal` completion verification (`antigravity-execution.md`).
3. **Skill** (process) guides workflow, invokes deterministic scripts
4. **Script** (Python CLI) performs mechanical operations

**LLMs orchestrate. Programs execute.** When validation is needed, call a script. When state must persist, write a file.
