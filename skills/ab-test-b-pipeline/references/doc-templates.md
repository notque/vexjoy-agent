# Documentation Templates by Module Type

Templates for structuring Python module documentation. Selected during Phase 3 (OUTLINE) based on module type classification from Phase 1 (EXTRACT).

---

## CLI Tool

For modules with `has_cli_entry: true` and `has_argparse: true`.

```markdown
# {Module Name}

## Overview
[One-paragraph purpose from module docstring. What problem it solves, who uses it.]

## Quick Start
[Most common invocation pattern -- the one command a new user needs first.]

## Usage

### Commands
[One subsection per argparse subcommand with description, arguments, and example.]

### Global Options
[Arguments that apply to all subcommands, if any.]

### Exit Codes
| Code | Meaning |
|------|---------|
| 0 | {description} |
| 1 | {description} |

## Examples
[One working example per subcommand, using REAL values from codebase research.]

## API Reference
[Public functions if the module is also imported as a library. Skip if CLI-only.]

### {function_name}({args})
[Description, parameters table, return value.]

## Architecture
[Internal data flow, key design decisions. Only for Medium+ complexity.]

## Dependencies
[Key imports, external tools, environment variables.]
```

---

## Utility Library

For modules with no CLI entry point and multiple public functions/classes.

```markdown
# {Module Name}

## Overview
[One-paragraph purpose. What abstractions it provides, where it fits in the system.]

## Key Concepts
[Core abstractions, terminology, or patterns the user needs to understand first.]

## API Reference

### Functions

#### {function_name}({args}) -> {return_type}
[Description from docstring, supplemented by source analysis.]

**Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| {name} | {type} | {description} |

**Returns:** {description of return value}

**Raises:** {exceptions, if any}

**Example:**
```python
{real usage from codebase research}
```

### Classes

#### class {ClassName}({bases})
[Description. Constructor parameters.]

##### {method_name}({args}) -> {return_type}
[Method description.]

### Constants
| Constant | Value | Description |
|----------|-------|-------------|
| {NAME} | {value or type} | {purpose} |

## Usage Patterns
[Common calling patterns discovered during research. How callers typically use this module.]

## Architecture
[Internal data flow, relationships to other modules. Only for Medium+ complexity.]

## Dependencies
[Key imports and their roles.]
```

---

## Hook

For modules in `hooks/` that use `hook_utils`.

```markdown
# {Hook Name}

## Overview
[What this hook detects, when it fires, what context it provides.]

## Event
- **Type**: {SessionStart | UserPromptSubmit | PostToolUse | PreToolUse | Stop | PreCompact}
- **Trigger**: {what condition activates the hook}
- **Output**: {what context is injected when triggered}

## Detection Logic
[How the hook determines whether to fire. Key conditions and thresholds.]

## Output Format
[Exact format of the context output when the hook fires.]

```
{example output}
```

## Configuration
| Variable | Default | Description |
|----------|---------|-------------|
| {ENV_VAR} | {default} | {what it controls} |

## API Reference
[Public functions and their roles in the detection pipeline.]

### {function_name}({args}) -> {return_type}
[Description.]

## Integration
[Which agents/skills consume this hook's output. How it fits in the pipeline.]

## Dependencies
[Key imports, database files, external state.]
```

---

## Data Layer

For modules primarily containing classes, dataclasses, ORM models, or data structures.

```markdown
# {Module Name}

## Overview
[What data this module manages. Schema purpose and system role.]

## Data Model

### class {ClassName}
[Purpose, relationship to other models.]

**Fields:**
| Field | Type | Description |
|-------|------|-------------|
| {name} | {type} | {purpose} |

**Properties:**
| Property | Returns | Description |
|----------|---------|-------------|
| {name} | {type} | {computed value} |

**Methods:**
#### {method_name}({args}) -> {return_type}
[Description.]

## Relationships
[How models relate to each other. Foreign keys, composition, inheritance.]

## Query Patterns
[Common queries against this data layer. Actual usage from callers.]

## Schema
[Database schema if applicable. Table definitions, indexes.]

## Migration Notes
[Version history, breaking changes, migration paths.]

## Dependencies
[ORM library, database driver, related modules.]
```

---

## Template Selection Logic

Used in Phase 1 Step 3 and Phase 3 Step 1:

```
IF has_cli_entry AND has_argparse:
    template = "CLI Tool"
ELIF located in hooks/ AND imports hook_utils:
    template = "Hook"
ELIF primarily classes (class count > function count):
    template = "Data Layer"
ELSE:
    template = "Utility Library"
```

Priority: CLI Tool > Hook > Data Layer > Utility Library. If multiple signals match, use the first match in priority order.
