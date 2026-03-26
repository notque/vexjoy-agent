# Modern Python Features by Version

> Reference file for python-general-engineer agent. Loaded as context during Python development tasks.

## Python 3.9

### Dict Union Operators (`|` and `|=`)

```python
# Old — copy and update
merged = {**defaults, **overrides}

# New — union operator
merged = defaults | overrides

# In-place merge
config = {"debug": False, "verbose": False}
config |= {"debug": True}
# {"debug": True, "verbose": False}
```

### str.removeprefix() and str.removesuffix()

```python
# Old — error-prone slicing
filename = "test_utils.py"
if filename.startswith("test_"):
    name = filename[5:]  # magic number

# New — explicit and safe
name = filename.removeprefix("test_")   # "utils.py"
path = "archive.tar.gz".removesuffix(".gz")  # "archive.tar"
```

### Generic Builtins in Type Hints

```python
# Old — import from typing
from typing import List, Dict, Tuple, Set

def process(items: List[str]) -> Dict[str, int]:
    ...

# New — use builtins directly (3.9+)
def process(items: list[str]) -> dict[str, int]:
    ...
```

## Python 3.10

### Structural Pattern Matching (match/case)

```python
# Old — if/elif chains
def handle(event):
    if event["type"] == "click":
        return handle_click(event["x"], event["y"])
    elif event["type"] == "key" and event["key"] == "Enter":
        return handle_enter()
    else:
        return handle_unknown(event)

# New — pattern matching with destructuring
def handle(event):
    match event:
        case {"type": "click", "x": x, "y": y}:
            return handle_click(x, y)
        case {"type": "key", "key": "Enter"}:
            return handle_enter()
        case _:
            return handle_unknown(event)
```

### Better Error Messages

Python 3.10 significantly improved error messages with suggestions and precise locations.

```python
# Before: SyntaxError: invalid syntax
# After:  SyntaxError: did you forget a comma between 'a' and 'b'?

# Before: NameError: name 'respone' is not defined
# After:  NameError: name 'respone' is not defined. Did you mean: 'response'?
```

### TypeAlias and ParamSpec

```python
from typing import TypeAlias, ParamSpec, Callable
import functools

# TypeAlias — explicit alias declaration
UserID: TypeAlias = int
Matrix: TypeAlias = list[list[float]]

# ParamSpec — preserve function signatures in decorators
P = ParamSpec("P")

def logged(func: Callable[P, T]) -> Callable[P, T]:
    @functools.wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        print(f"Calling {func.__name__}")
        return func(*args, **kwargs)
    return wrapper
```

### Union Type with `|`

```python
# Old
from typing import Union, Optional
def parse(data: Union[str, bytes]) -> Optional[dict]:
    ...

# New — | operator (3.10+)
def parse(data: str | bytes) -> dict | None:
    ...
```

## Python 3.11

### ExceptionGroup and except*

Handle multiple simultaneous exceptions from concurrent operations.

```python
# Raising multiple exceptions
raise ExceptionGroup("validation errors", [
    ValueError("name is required"),
    TypeError("age must be int"),
])

# Catching specific exceptions from a group
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(risky_a())
        tg.create_task(risky_b())
except* ValueError as eg:
    for exc in eg.exceptions:
        print(f"Value error: {exc}")
except* TypeError as eg:
    for exc in eg.exceptions:
        print(f"Type error: {exc}")
```

### TaskGroup — Structured Concurrency

```python
# Old — gather doesn't cancel on first failure
results = await asyncio.gather(task_a(), task_b(), task_c())

# New — TaskGroup cancels remaining tasks on failure
async with asyncio.TaskGroup() as tg:
    t1 = tg.create_task(fetch_users())
    t2 = tg.create_task(fetch_orders())
    t3 = tg.create_task(fetch_products())
# All tasks completed here (or all cancelled if one failed)
users, orders, products = t1.result(), t2.result(), t3.result()
```

### tomllib — Built-in TOML Parser

```python
# Old — third-party dependency
import toml  # pip install toml
config = toml.load("pyproject.toml")

# New — stdlib (read-only)
import tomllib
with open("pyproject.toml", "rb") as f:
    config = tomllib.load(f)
```

### Self Type

```python
from typing import Self

class Builder:
    def __init__(self):
        self._name: str = ""
        self._value: int = 0

    def name(self, name: str) -> Self:
        self._name = name
        return self

    def value(self, value: int) -> Self:
        self._value = value
        return self

# Works correctly with subclasses too
class SpecialBuilder(Builder):
    def special(self) -> Self:  # returns SpecialBuilder, not Builder
        return self
```

### Performance Improvements

Python 3.11 is 10-60% faster than 3.10 thanks to the Faster CPython project (PEP 659 — adaptive specializing interpreter).

## Python 3.12

### F-String Improvements

F-strings now support any valid Python expression, including nested quotes and backslashes.

```python
# Old — couldn't nest quotes or use backslashes
items = ["a", "b", "c"]
# msg = f"items: {'\n'.join(items)}"  # SyntaxError in <3.12

# New — all expressions allowed in 3.12+
msg = f"items: {'\n'.join(items)}"
msg = f"{'hello' if True else 'bye'}"
msg = f"{f'{x:.2f}':>10}"  # nested f-strings with formatting
```

### Type Parameter Syntax (PEP 695)

```python
# Old — verbose TypeVar declarations
from typing import TypeVar
T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")

def first(items: list[T]) -> T:
    return items[0]

class Map(Generic[K, V]):
    ...

# New — inline type parameters (3.12+)
def first[T](items: list[T]) -> T:
    return items[0]

class Map[K, V]:
    def get(self, key: K) -> V | None:
        ...

# Type aliases with the type statement
type Point = tuple[float, float]
type Matrix[T] = list[list[T]]
```

### @override Decorator

```python
from typing import override

class Base:
    def process(self) -> None:
        ...

class Child(Base):
    @override  # type checker verifies Base.process exists
    def process(self) -> None:
        ...

    @override  # ERROR — Base has no 'handle' method
    def handle(self) -> None:
        ...
```

## Python 3.13

### Improved Interactive REPL

The new REPL supports multi-line editing, syntax highlighting, and better paste handling. It is based on PyREPL and provides a more modern editing experience similar to IPython.

### Experimental JIT Compiler (PEP 744)

```bash
# Build with JIT enabled (experimental, copy-and-patch JIT)
./configure --enable-experimental-jit
# Provides targeted speedups for hot loops and numeric code
# Not yet a default — opt-in for benchmarking
```

### Free-Threaded CPython (PEP 703)

```bash
# Build without the GIL (experimental)
./configure --disable-gil

# At runtime, check if GIL is disabled
import sys
print(sys._is_gil_enabled())  # False when free-threaded
```

```python
# With free-threading, true parallel threads become possible
import threading

# This can now use multiple CPU cores simultaneously
threads = [
    threading.Thread(target=cpu_bound_work, args=(chunk,))
    for chunk in data_chunks
]
for t in threads:
    t.start()
for t in threads:
    t.join()

# Note: many C extensions need updates to be thread-safe
# Use the experimental build for testing, not production (yet)
```

### Deprecations and Removals

```python
# Many long-deprecated modules removed in 3.13:
# - aifc, audioop, cgi, cgitb, chunk, crypt, imghdr, mailcap,
#   msilib, nis, nntplib, ossaudiodev, pipes, sndhdr, spwd,
#   sunau, telnetlib, uu, xdrlib

# Migrate away from deprecated patterns:
# Old: import cgi; cgi.parse_qs(...)
# New: from urllib.parse import parse_qs
```
