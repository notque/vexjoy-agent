# Python Common Errors and Solutions

> Reference file for python-general-engineer agent. Loaded as context during Python development tasks.

## TypeError: unhashable type: 'list'

**Root cause**: Lists are mutable and cannot be used as dictionary keys or set members. Python requires hashable (immutable) types for these operations.

```python
# Bad — lists are not hashable
cache = {}
cache[[1, 2, 3]] = "value"  # TypeError

# Good — convert to tuple (immutable)
cache[(1, 2, 3)] = "value"

# Good — use frozenset for unordered collections
seen = set()
seen.add(frozenset([1, 2, 3]))
```

## AttributeError: 'NoneType' has no attribute '...'

**Root cause**: A function returned `None` (implicitly or explicitly) and the caller chained an attribute access on the result. Common with functions that mutate in-place (e.g., `list.sort()`, `list.append()`).

```python
# Bad — sort() returns None
sorted_items = items.sort()
sorted_items[0]  # AttributeError

# Good — use sorted() which returns a new list
sorted_items = sorted(items)

# Good — guard with explicit None check
result = maybe_returns_none()
if result is not None:
    result.process()
```

## ImportError: circular import

**Root cause**: Module A imports module B, and module B imports module A. Python's import system partially initializes modules, so names may not yet exist when the circular import executes.

```python
# Bad — circular dependency between models.py and utils.py
# models.py
from utils import validate  # utils tries to import from models too

# Solution 1: Move import inside the function (lazy import)
def create_model(data):
    from utils import validate  # imported only when called
    return validate(data)

# Solution 2: Restructure — extract shared code into a third module
# shared.py contains what both modules need

# Solution 3: Use TYPE_CHECKING for type-hint-only imports
from __future__ import annotations
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from models import User  # never imported at runtime
```

## RecursionError: maximum recursion depth exceeded

**Root cause**: Unbounded recursion, missing base case, or a problem better solved iteratively. Python's default recursion limit is 1000.

```python
# Bad — recursive tree traversal on deep trees
def flatten(node):
    if node is None:
        return []
    return [node.value] + flatten(node.left) + flatten(node.right)

# Good — iterative with explicit stack
def flatten(root):
    result = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node is None:
            continue
        result.append(node.value)
        stack.append(node.left)
        stack.append(node.right)
    return result

# Good — for tail-recursive patterns, convert to loop
def factorial(n):
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result
```

## asyncio.TimeoutError

**Root cause**: An async operation exceeded the specified timeout. Common with `asyncio.wait_for()` and `async with asyncio.timeout()`.

```python
# Bad — no timeout, hangs forever on unresponsive service
response = await client.get(url)

# Good — use asyncio.timeout (3.11+)
import asyncio

async def fetch_with_timeout(client, url):
    try:
        async with asyncio.timeout(10):
            return await client.get(url)
    except TimeoutError:
        logger.warning(f"Request to {url} timed out after 10s")
        return None

# Good — retry with exponential backoff
async def fetch_with_retry(client, url, max_retries=3):
    for attempt in range(max_retries):
        try:
            async with asyncio.timeout(10):
                return await client.get(url)
        except TimeoutError:
            if attempt == max_retries - 1:
                raise
            await asyncio.sleep(2 ** attempt)
```

## UnicodeDecodeError

**Root cause**: Attempting to decode bytes with the wrong encoding. Common when reading files that aren't UTF-8 or processing external data.

```python
# Bad — assumes UTF-8
with open("data.csv") as f:
    content = f.read()  # UnicodeDecodeError if file is Latin-1

# Good — specify encoding explicitly
with open("data.csv", encoding="utf-8") as f:
    content = f.read()

# Good — handle unknown encodings with error strategies
with open("data.csv", encoding="utf-8", errors="replace") as f:
    content = f.read()  # replaces bad chars with U+FFFD

# Good — detect encoding when truly unknown
import chardet

raw = Path("data.csv").read_bytes()
detected = chardet.detect(raw)
content = raw.decode(detected["encoding"])
```

## ModuleNotFoundError

**Root cause**: The module isn't installed in the active Python environment. Very common when virtual environments are misconfigured or dependencies are missing.

```python
# Diagnosis: check which Python is running
import sys
print(sys.executable)  # /usr/bin/python3 vs .venv/bin/python3
print(sys.path)        # verify your package paths

# Fix: ensure venv is activated and package is installed
# $ python -m venv .venv
# $ source .venv/bin/activate
# $ pip install the-missing-package

# For editable local packages:
# $ pip install -e .

# For optional dependencies, guard the import:
try:
    import ujson as json
except ModuleNotFoundError:
    import json  # fallback to stdlib
```

## TypeError: missing required argument / unexpected keyword argument

**Root cause**: Function signature changed or caller is passing wrong arguments. Common after refactoring or when mixing up positional and keyword arguments.

```python
# Bad — positional args make call-sites fragile
def create_user(name, email, role, active):
    ...

create_user("Alice", "a@b.com", True, "admin")  # role and active swapped

# Good — use keyword-only arguments (after *)
def create_user(*, name: str, email: str, role: str, active: bool = True):
    ...

create_user(name="Alice", email="a@b.com", role="admin")

# Good — use dataclass or TypedDict for complex parameter groups
from dataclasses import dataclass

@dataclass
class UserConfig:
    name: str
    email: str
    role: str = "viewer"
    active: bool = True

def create_user(config: UserConfig):
    ...
```
