# Execution Architecture

**Router → Agent → Skill → Script**

1. **Router** (`/do`) classifies request, selects agent + skill
2. **Agent** (domain expert) executes with skill methodology
3. **Skill** (process) guides workflow, invokes deterministic scripts
4. **Script** (Python CLI) performs mechanical operations

**LLMs orchestrate. Programs execute.** When validation is needed, call a script. When state must persist, write a file.
