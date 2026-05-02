# Python Preferred Patterns

See `python-preferred-patterns.md` for full catalog.

### Use Virtual Environments for All Installs
**Signal**: `pip3 install` without venv, version mismatches
**Preferred action**: `python -m venv .venv && source .venv/bin/activate`. Never use system pip.

### Start Concrete, Abstract Later
**Signal**: ABCs before multiple implementations
**Preferred action**: Concrete class first, add Protocol when 2+ implementations exist.

### Use Async Only for I/O Concurrency
**Signal**: CPU-bound operations converted to async
**Preferred action**: Keep synchronous for CPU ops, async only for I/O (network, disk, database).

### Fix Types Instead of Ignoring Them
**Signal**: `# type: ignore` instead of fixing types
**Preferred action**: TypedDict for dicts, correct Union types, fix root cause.

### Use str.join for String Assembly
**Signal**: `result += str(item)` in loop
**Preferred action**: `"".join(str(item) for item in items)` — O(n) vs O(n^2).

### Catch Specific Exception Types
**Signal**: `except:` without type
**Preferred action**: `except Exception:` at minimum, or specific types.

### Validate All Input on New CLI Handlers
**Signal**: New handler accepts stdin JSON/env var without validating format
**Preferred action**: Same validation function as existing handlers. Validate BEFORE file path construction.

### Surface All Computed Data in LLM Prompts
**Signal**: Computing `repeat_offender_count` but not including in prompt
**Preferred action**: Every computed signal MUST appear in the rendered prompt.

### Define Every New Category
**Signal**: Adding `BAN_RECOMMENDED` without definition
**Preferred action**: Each new category needs definition, usage criteria, and auto-mode behavior.
