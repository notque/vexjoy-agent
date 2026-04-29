# Python Preferred Patterns

Common Python patterns to follow. See `python-preferred-patterns.md` for full catalog.

### Use Virtual Environments for All Installs
**Signal**: Running `pip3 install` without a virtual environment, hitting version mismatches between Python and pip
**Why this matters**: System pip may resolve to a different Python version (e.g., Python 3.14 but pip from 3.9), causing install failures or packages installed to wrong site-packages
**Preferred action**: Always use pyenv + virtual environments. Create venv first: `python -m venv .venv && source .venv/bin/activate`. Never install packages with system pip.

### Start Concrete, Abstract Later
**Signal**: Creating abstract base classes before you have multiple implementations
**Why this matters**: Adds complexity without proven benefit, makes code harder to navigate, violates YAGNI
**Preferred action**: Start with concrete class, add abstraction when you have 2+ implementations, use Protocols for structural typing

### Use Async Only for I/O Concurrency
**Signal**: Converting CPU-bound operations to async without I/O benefit
**Why this matters**: Adds async overhead for no performance gain, async is for I/O concurrency not CPU parallelism
**Preferred action**: Keep synchronous for CPU operations, only use async for actual I/O (network, disk, database)

### Fix Types Instead of Ignoring Them
**Signal**: Silencing type checker with `# type: ignore` instead of fixing types
**Why this matters**: Loses type safety, hides bugs, makes refactoring dangerous
**Preferred action**: Use proper type hints (TypedDict for dicts, correct Union types), fix the root cause

### Use str.join for String Assembly
**Signal**: `result = ""; for item in items: result += str(item)`
**Why this matters**: Strings are immutable, creates new string each iteration, O(n²) time complexity
**Preferred action**: Use `"".join(str(item) for item in items)` - O(n) time

### Catch Specific Exception Types
**Signal**: `except:` without specifying exception type
**Why this matters**: Catches SystemExit and KeyboardInterrupt, prevents debugging
**Preferred action**: `except Exception:` at minimum, or specific exception types

### Validate All Input on New CLI Handlers
**Signal**: New subcommand handler accepts subreddit/path from stdin JSON or env var without validating format
**Why this matters**: Every OTHER handler validates input (e.g., `_resolve_subreddit`), new handler bypasses the pattern. Creates path traversal via crafted stdin JSON.
**Preferred action**: Use the same validation function as existing handlers. If input comes from a new source (stdin JSON), validate BEFORE any file path construction.

### Surface All Computed Data in LLM Prompts
**Signal**: Calculating `repeat_offender_count` but not including it in the prompt string
**Why this matters**: The LLM can only use data that appears in the prompt. Computed-but-invisible data is dead computation.
**Preferred action**: Every signal computed for classification MUST appear in the rendered prompt. Test: "is this value in the prompt string?"

### Define Every New Category
**Signal**: Adding `BAN_RECOMMENDED` to a classification list without explaining when to use it
**Why this matters**: LLM has no guidance to distinguish it from existing categories, making it dead code
**Preferred action**: Each new category needs a definition, usage criteria, and auto-mode behavior in the prompt
