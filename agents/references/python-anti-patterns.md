# Python Anti-Patterns

> Reference file for python-general-engineer agent. Loaded as context during Python development tasks.

## Mutable Default Arguments

Default mutable objects are shared across all calls to the function. The default is evaluated once at function definition time, not at each call.

```python
# Bad — the list is shared across calls
def append_to(item, target=[]):
    target.append(item)
    return target

append_to(1)  # [1]
append_to(2)  # [1, 2] — not [2]!

# Good — use None sentinel
def append_to(item, target=None):
    if target is None:
        target = []
    target.append(item)
    return target
```

## Bare except / Swallowing Exceptions

Catching all exceptions hides bugs. `except Exception` still catches too broadly if the body silences it.

```python
# Bad — catches KeyboardInterrupt, SystemExit, everything
try:
    process()
except:
    pass

# Bad — silently swallows real errors
try:
    process()
except Exception:
    pass

# Good — catch specific exceptions, log or re-raise
try:
    process()
except ValueError as e:
    logger.warning("Invalid input: %s", e)
except ConnectionError:
    logger.error("Service unavailable, retrying")
    raise
```

## import * (Namespace Pollution)

Wildcard imports dump unknown names into the local namespace, causing shadowing and making it impossible to trace where a name comes from.

```python
# Bad — which module defined 'connect'?
from database import *
from network import *
connect()  # ambiguous

# Good — explicit imports
from database import DatabaseConnection
from network import HttpClient

# Good — import the module, use qualified names
import database
database.connect()
```

## os.path Instead of pathlib.Path

`os.path` is stringly-typed and verbose. `pathlib.Path` provides an object-oriented interface that is clearer and less error-prone.

```python
# Bad — string manipulation for paths
import os
config_path = os.path.join(os.path.expanduser("~"), ".config", "app.toml")
if os.path.exists(config_path):
    with open(config_path) as f:
        data = f.read()

# Good — pathlib is expressive and chainable
from pathlib import Path
config_path = Path.home() / ".config" / "app.toml"
if config_path.exists():
    data = config_path.read_text()
```

## type() Checks Instead of isinstance()

`type()` does not respect inheritance. `isinstance()` handles subclasses and supports tuples of types.

```python
# Bad — fails for subclasses
if type(obj) == dict:
    ...

# Good — respects inheritance
if isinstance(obj, dict):
    ...

# Good — check multiple types
if isinstance(obj, (int, float)):
    ...

# Best — use Protocol for structural typing (duck typing)
from typing import Protocol

class Mappable(Protocol):
    def __getitem__(self, key: str) -> object: ...

def process(data: Mappable) -> None:
    ...
```

## String Concatenation in Loops

Repeated `+` on strings creates a new string object each time, leading to O(n^2) behavior.

```python
# Bad — quadratic string building
result = ""
for item in large_list:
    result += str(item) + ", "

# Good — join is O(n)
result = ", ".join(str(item) for item in large_list)

# Good — f-strings for small, fixed concatenations
name = f"{first} {last}"
```

## Not Using Context Managers for Resources

Forgetting to close files, connections, or locks leads to resource leaks. Context managers guarantee cleanup even when exceptions occur.

```python
# Bad — file may never be closed on exception
f = open("data.txt")
data = f.read()
f.close()

# Good — with statement guarantees close
with open("data.txt") as f:
    data = f.read()

# Good — works for locks, database connections, temp files
import threading
lock = threading.Lock()

with lock:
    shared_state.update(new_data)

# Good — custom context manager
from contextlib import contextmanager

@contextmanager
def temporary_env(key, value):
    old = os.environ.get(key)
    os.environ[key] = value
    try:
        yield
    finally:
        if old is None:
            del os.environ[key]
        else:
            os.environ[key] = old
```

## Global Mutable State

Module-level mutable variables create hidden coupling, make testing difficult, and cause unpredictable behavior in concurrent code.

```python
# Bad — global mutable state
_cache = {}

def get_user(user_id):
    if user_id not in _cache:
        _cache[user_id] = db.fetch(user_id)
    return _cache[user_id]

# Good — encapsulate state in a class
class UserCache:
    def __init__(self):
        self._cache: dict[int, User] = {}

    def get(self, user_id: int) -> User:
        if user_id not in self._cache:
            self._cache[user_id] = db.fetch(user_id)
        return self._cache[user_id]

# Good — use functools.lru_cache for simple memoization
from functools import lru_cache

@lru_cache(maxsize=256)
def get_user(user_id: int) -> User:
    return db.fetch(user_id)
```

## map/filter Instead of Comprehensions

In Python, list comprehensions are more readable and idiomatic than `map()` and `filter()` with lambdas.

```python
# Bad — lambda noise
squares = list(map(lambda x: x ** 2, numbers))
evens = list(filter(lambda x: x % 2 == 0, numbers))

# Good — comprehensions are clearer
squares = [x ** 2 for x in numbers]
evens = [x for x in numbers if x % 2 == 0]

# Good — generator expression for lazy evaluation
total = sum(x ** 2 for x in numbers)
```

## Late Binding Closures in Loops

Closures capture variables by reference, not by value. All closures in a loop share the same variable, which ends up with the final loop value.

```python
# Bad — all functions return 4 (the last value of i)
functions = []
for i in range(5):
    functions.append(lambda: i)
print([f() for f in functions])  # [4, 4, 4, 4, 4]

# Good — capture by default argument (binds at definition time)
functions = []
for i in range(5):
    functions.append(lambda i=i: i)
print([f() for f in functions])  # [0, 1, 2, 3, 4]

# Good — use functools.partial
from functools import partial

def make_value(x):
    return x

functions = [partial(make_value, i) for i in range(5)]
```

## Not Using __slots__ for Data-Heavy Classes

Without `__slots__`, every instance carries a `__dict__` which costs ~100 bytes overhead per object. For millions of instances, this adds up.

```python
# Bad — each instance has a __dict__
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

# Good — __slots__ eliminates per-instance dict
class Point:
    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y

# Good — for most cases, just use a dataclass with slots
from dataclasses import dataclass

@dataclass(slots=True)
class Point:
    x: float
    y: float
```
