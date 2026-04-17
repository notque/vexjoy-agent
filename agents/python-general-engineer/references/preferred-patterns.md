# Python Preferred Patterns

Common Python patterns to follow. See `python-anti-patterns.md` for full catalog.

### ❌ System Python/pip Mismatch
**What it looks like**: Running `pip3 install` without a virtual environment, hitting version mismatches between Python and pip
**Why wrong**: System pip may resolve to a different Python version (e.g., Python 3.14 but pip from 3.9), causing install failures or packages installed to wrong site-packages
**✅ Do instead**: Always use pyenv + virtual environments. Create venv first: `python -m venv .venv && source .venv/bin/activate`. Never install packages with system pip.

### ❌ Over-Engineering with ABCs
**What it looks like**: Creating abstract base classes before you have multiple implementations
**Why wrong**: Adds complexity without proven benefit, makes code harder to navigate, violates YAGNI
**✅ Do instead**: Start with concrete class, add abstraction when you have 2+ implementations, use Protocols for structural typing

### ❌ Premature Async Conversion
**What it looks like**: Converting CPU-bound operations to async without I/O benefit
**Why wrong**: Adds async overhead for no performance gain, async is for I/O concurrency not CPU parallelism
**✅ Do instead**: Keep synchronous for CPU operations, only use async for actual I/O (network, disk, database)

### ❌ Type: Ignore Instead of Fixing
**What it looks like**: Silencing type checker with `# type: ignore` instead of fixing types
**Why wrong**: Loses type safety, hides bugs, makes refactoring dangerous
**✅ Do instead**: Use proper type hints (TypedDict for dicts, correct Union types), fix the root cause

### ❌ String Concatenation in Loops
**What it looks like**: `result = ""; for item in items: result += str(item)`
**Why wrong**: Strings are immutable, creates new string each iteration, O(n²) time complexity
**✅ Do instead**: Use `"".join(str(item) for item in items)` - O(n) time

### ❌ Bare Except Clauses
**What it looks like**: `except:` without specifying exception type
**Why wrong**: Catches SystemExit and KeyboardInterrupt, prevents debugging
**✅ Do instead**: `except Exception:` at minimum, or specific exception types

### ❌ Skipping Input Validation on New CLI Handlers
**What it looks like**: New subcommand handler accepts subreddit/path from stdin JSON or env var without validating format
**Why wrong**: Every OTHER handler validates input (e.g., `_resolve_subreddit`), new handler bypasses the pattern. Creates path traversal via crafted stdin JSON.
**✅ Do instead**: Use the same validation function as existing handlers. If input comes from a new source (stdin JSON), validate BEFORE any file path construction.

### ❌ Computing Data Without Surfacing It in LLM Prompts
**What it looks like**: Calculating `repeat_offender_count` but not including it in the prompt string
**Why wrong**: The LLM can only use data that appears in the prompt. Computed-but-invisible data is dead computation.
**✅ Do instead**: Every signal computed for classification MUST appear in the rendered prompt. Test: "is this value in the prompt string?"

### ❌ Adding Categories Without Definitions
**What it looks like**: Adding `BAN_RECOMMENDED` to a classification list without explaining when to use it
**Why wrong**: LLM has no guidance to distinguish it from existing categories, making it dead code
**✅ Do instead**: Each new category needs a definition, usage criteria, and auto-mode behavior in the prompt
