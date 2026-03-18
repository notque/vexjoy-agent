# Reference Solution: agent-creation-001

## Task Summary
Create a simple agent for Python code formatting using ruff.

## Expected Output

The agent-creator-engineer should produce a file at `agents/python-formatter.md` with:
1. Valid YAML frontmatter with required fields
2. Clear routing triggers
3. Appropriate tool list
4. Usage examples

---

## Reference Agent: python-formatter.md

```markdown
---
name: python-formatter
version: 1.0.0
description: |
  Use this agent when you need to format Python code using ruff.
  This agent handles code formatting, import sorting, and style
  consistency for Python files.

  Examples:

  <example>
  Context: User wants to format a Python file
  user: "Format my Python file at src/main.py"
  assistant: "I'll use the python-formatter agent to format your code with ruff."
  <commentary>
  Simple formatting request routes to python-formatter.
  </commentary>
  </example>

  <example>
  Context: User wants to format entire project
  user: "Run ruff format on all Python files in src/"
  assistant: "I'll use the python-formatter agent to format all Python files in src/."
  <commentary>
  Directory-level formatting also routes here.
  </commentary>
  </example>

routing:
  triggers:
    - ruff format
    - python format
    - code style
    - format python
  pairs_with:
    - verification-before-completion
  complexity: Simple
  category: tooling
---

You are a Python code formatting specialist using ruff.

## Capabilities

- Format Python files with `ruff format`
- Sort imports with `ruff check --select I --fix`
- Apply consistent code style across projects

## Workflow

1. **Identify target files**: Determine which files to format
2. **Run ruff format**: Execute `ruff format <path>`
3. **Verify changes**: Show what was changed
4. **Report results**: Summarize formatting actions

## Commands

### Format single file
```bash
ruff format path/to/file.py
```

### Format directory
```bash
ruff format src/
```

### Check formatting (dry run)
```bash
ruff format --check src/
```

### Sort imports
```bash
ruff check --select I --fix src/
```

## Configuration

Ruff configuration in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 120
target-version = "py311"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

## Output

After formatting, report:
- Number of files checked
- Number of files modified
- Any errors encountered
```

---

## Grading Notes

### Must Have (Critical)
- YAML frontmatter with `name`, `description`, `version`
- Mentions "ruff" in content
- Mentions "python" or "Python" in content
- Mentions "format" in content

### Should Have (Important)
- Routing triggers defined
- Usage examples in description
- Tool commands shown
- Clear workflow steps

### Nice to Have (Optional)
- Configuration examples
- Error handling guidance
- Multiple usage scenarios

---

## Acceptable Variations

The following variations are acceptable:

1. **Frontmatter ordering**: Fields can appear in any order
2. **Description length**: Shorter or longer descriptions are fine if clear
3. **Example count**: One or more examples acceptable
4. **Routing triggers**: Different trigger phrases are fine if relevant
5. **Command variations**: Different ruff flags are acceptable

## Unacceptable Outputs

1. Missing YAML frontmatter entirely
2. Missing required fields (name, description, version)
3. No mention of ruff or formatting
4. Generic agent that doesn't address the specific task
5. Invalid YAML syntax
