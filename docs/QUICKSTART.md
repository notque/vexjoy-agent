---
summary: "30-second start: install, verify, and request an outcome."
read_when:
  - "first-time setup"
---

# Quick Start

Install the toolkit from its repository:

```bash
cd ~/vexjoy-agent
./install.sh
```

Verify the installation:

```bash
python3 ~/.claude/scripts/install-doctor.py check
```

Open a project and describe the outcome you want:

```text
/do debug this failing test
/do review this change before I ship it
/do research current WebAssembly adoption
```

Use `/do` in Claude Code, Factory, and Reasonix. Use `$do` in Codex. The router selects the relevant agent, skill, and checks; you do not need to know their names.

For prerequisites, optional runtimes, installation choices, and troubleshooting, continue to [Start Here](start-here.md). Developers extending the toolkit should use [For Developers](for-developers.md).
