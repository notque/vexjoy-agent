# Python General Engineer - Preferred Patterns

Action-first patterns for correct Python code. Each section leads with what to do and why, followed by detection commands for finding violations.

## Start With Concrete Classes, Add Abstraction When Needed

Write a plain class first. Introduce `Protocol` (not ABC) when you have two or more implementations that need a shared interface. Protocols use structural subtyping -- any class with matching methods satisfies the protocol without inheritance.

```python
# Simple concrete class -- add abstraction later if needed
class UserRepository:
    def get(self, id: int) -> User:
        return query_db(id)

    def save(self, user: User) -> None:
        insert_db(user)

# When you need interface abstraction, use Protocol (structural subtyping)
from typing import Protocol

class UserRepository(Protocol):
    def get(self, id: int) -> User: ...
    def save(self, user: User) -> None: ...

# Any class with these methods satisfies the protocol
# No inheritance needed!
```

**When ABCs are appropriate**:
- You have 2+ implementations already
- You're building a framework with extension points
- You need method implementation sharing via inheritance

**Why this matters**: ABCs before a second implementation add a layer of indirection with no proven benefit. Code becomes harder to navigate, and the abstraction often gets the interface wrong because it was designed without knowing the second consumer's needs.

**Detection**: `grep -rn 'class.*ABC' --include="*.py" | grep -v 'test'` finds ABC usage to audit for premature abstraction.

---

## Keep CPU-Bound Code Synchronous

Use `async/await` only for I/O-bound operations (network, database, file). Pure computation gains nothing from async -- it adds overhead and complexity without concurrency benefit. Use `asyncio.TaskGroup` to fan out concurrent I/O calls.

```python
# Synchronous for pure computation -- no async overhead
def calculate_total(items: list[Item]) -> float:
    return sum(item.price * item.quantity for item in items)

# Async only when doing actual I/O
async def fetch_and_calculate(user_id: int) -> float:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/users/{user_id}/items")
        items = [Item(**item) for item in response.json()]
    return calculate_total(items)  # Sync calculation -- no await needed

# Use TaskGroup for concurrent I/O (Python 3.11+)
async def fetch_multiple_users(user_ids: list[int]) -> list[float]:
    async with asyncio.TaskGroup() as tg:
        tasks = [
            tg.create_task(fetch_and_calculate(uid))
            for uid in user_ids
        ]
    return [task.result() for task in tasks]
```

**When to use async**:
- Network requests (HTTP, WebSocket)
- Database queries
- File I/O with aiofiles
- Multiple concurrent I/O operations

**Why this matters**: `async def` on a CPU-bound function adds the overhead of coroutine scheduling with zero concurrency benefit. Callers must now use `await`, propagating async through the call stack for no gain.

**Detection**: `grep -rn 'async def' --include="*.py" | xargs grep -L 'await'` finds async functions that never await -- likely CPU-bound code wrapped in async unnecessarily.

---

## Fix Type Errors Instead of Suppressing Them

Define proper types for your data structures using `TypedDict` or Pydantic models. Each `# type: ignore` is a suppressed bug report -- fix the underlying type mismatch instead.

```python
from typing import TypedDict

class UserDict(TypedDict):
    id: int
    name: str

class ResponseData(TypedDict):
    users: list[UserDict]

def process_data(data: ResponseData) -> list[User]:
    return [User(id=item["id"], name=item["name"]) for item in data["users"]]

# Or use Pydantic for runtime validation
from pydantic import BaseModel

class UserData(BaseModel):
    id: int
    name: str

class Response(BaseModel):
    users: list[UserData]

def process_data(data: dict) -> list[User]:
    response = Response(**data)  # Validates at runtime
    return [User(id=u.id, name=u.name) for u in response.users]
```

**When `# type: ignore` is acceptable**:
- `# type: ignore[specific-error]  # Reason: explanation` with specific error code and justification
- Working around bugs in third-party type stubs
- Interfacing with genuinely untyped C extensions (rare)

**Why this matters**: Each `# type: ignore` disables the type checker at that line. Refactoring becomes dangerous -- the checker cannot warn about type mismatches in suppressed regions. Proper types catch bugs at check time instead of runtime.

**Detection**: `grep -rn 'type: ignore' --include="*.py" | grep -v 'type: ignore\[' ` finds blanket suppressions without specific error codes.

---

## Use None as Default for Mutable Arguments

Never use mutable objects (`[]`, `{}`, `set()`) as default parameter values. Python creates defaults once at function definition -- all calls share the same object. Use `None` and create a new instance inside the function body.

```python
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items

# Even better: don't mutate the input
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    items = items or []
    return [*items, item]

# For dataclasses, use field(default_factory=...)
from dataclasses import dataclass, field

@dataclass
class Cart:
    items: list[str] = field(default_factory=list)  # Correct!
    # items: list[str] = []  # Wrong! Shared across instances
```

**Why this matters**: Mutable default arguments are shared across all calls to the function. The first call mutates the default, and every subsequent call sees the mutation. This produces mysterious state leakage between unrelated callers.

**Detection**: Ruff flags this as `B006`. Run `ruff check . --select B006` to find all mutable default arguments.

---

## Build Strings With join(), Not Loop Concatenation

Use `"\n".join(items)` or a list-then-join pattern to assemble strings. String concatenation in a loop creates a new string object on every iteration because Python strings are immutable, giving O(n^2) time complexity.

```python
# Direct join for simple cases
def build_message(items: list[str]) -> str:
    return "\n".join(items)

# Join with formatting
def build_message(items: list[str]) -> str:
    return "\n".join(f"Item: {item}" for item in items)

# List-then-join for complex assembly
def build_html(items: list[str]) -> str:
    parts = ["<ul>"]
    for item in items:
        parts.append(f"  <li>{item}</li>")
    parts.append("</ul>")
    return "\n".join(parts)
```

**Why this matters**: `+=` on strings in a loop copies the entire accumulated string on every iteration. For 1000 items, that is 500,000 character copies. `join()` allocates once and copies each string exactly once -- O(n) instead of O(n^2).

**Detection**: `grep -rn '+= .*f"' --include="*.py"` and `grep -rn '+= "' --include="*.py"` find string concatenation patterns in loops.

---

## Catch Specific Exceptions, Never Bare except

Always specify the exception type in `except` clauses. Use `except Exception` as the broadest acceptable catch-all -- it excludes `SystemExit`, `KeyboardInterrupt`, and `GeneratorExit`, which must propagate for graceful shutdown.

```python
# Specific exceptions -- best practice
try:
    process_data()
except ValueError as e:
    log.error(f"Invalid data: {e}")
except ConnectionError as e:
    log.error(f"Network error: {e}")

# Exception as catch-all (doesn't catch system exceptions)
try:
    process_data()
except Exception as e:
    log.error(f"Error: {e}", exc_info=True)
    raise  # Re-raise if you can't handle it

# Python 3.11+ exception groups for concurrent error handling
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(task1())
        tg.create_task(task2())
except* ValueError as eg:
    for exc in eg.exceptions:
        log.error(f"Validation error: {exc}")
except* ConnectionError as eg:
    for exc in eg.exceptions:
        log.error(f"Network error: {exc}")
```

**Why this matters**: Bare `except:` catches `KeyboardInterrupt` (Ctrl+C won't work), `SystemExit` (process won't terminate), and `GeneratorExit` (generators can't clean up). It also hides programming errors during development by silently swallowing `TypeError`, `AttributeError`, and other bugs.

**Detection**: `grep -rn 'except:' --include="*.py"` finds bare except clauses. Also check for `except Exception` without `raise` -- swallowing errors silently.

---

## Use Structured Logging, Not print()

Replace `print()` with `logging.getLogger(__name__)` and structured log calls. Loggers provide severity levels, timestamps, structured metadata, and routing to different destinations. `print()` provides none of these.

```python
import logging

logger = logging.getLogger(__name__)

def process_order(order_id: int):
    logger.info("Processing order", extra={"order_id": order_id})
    order = get_order(order_id)
    logger.debug("Order retrieved", extra={"order_id": order_id, "status": order.status})
    process(order)
    logger.info("Order processed successfully", extra={"order_id": order_id})

# Structured logging with JSON formatter
import json

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ["name", "msg", "args", "created", "levelname", ...]:
                log_data[key] = value
        return json.dumps(log_data)
```

**When print() is acceptable**:
- CLI applications for user-facing output
- Debug scripts (not production services)
- Development/testing only

**Why this matters**: `print()` has no severity levels (cannot filter warnings from info), no timestamps, no structured metadata for log aggregation, and no way to route output to files, syslog, or monitoring systems. Sensitive data in `print()` goes straight to stdout with no redaction.

**Detection**: `grep -rn 'print(' --include="*.py" | grep -v '_test.py\|test_\|cli\|__main__'` finds print calls in non-test, non-CLI code.

---

## Use Context Managers for Resource Cleanup

Use `with` statements for any resource that needs cleanup: files, database connections, locks, network sockets. Context managers guarantee cleanup runs even when exceptions occur, eliminating resource leaks.

```python
# File operations
def process_file(path: str):
    with open(path) as f:
        data = f.read()
    return process(data)  # File automatically closed

# Multiple context managers on one line
def copy_file(src: str, dst: str):
    with open(src) as src_f, open(dst, "w") as dst_f:
        dst_f.write(src_f.read())

# Async context managers
async def fetch_data():
    async with get_async_connection() as conn:
        data = await conn.fetch()
        return data  # Connection automatically closed

# Custom context manager with transaction semantics
from contextlib import contextmanager

@contextmanager
def transaction(db):
    db.begin()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise

with transaction(db):
    db.execute("INSERT ...")
    db.execute("UPDATE ...")
```

**Always use context managers for**:
- File operations
- Database connections
- Locks (`threading.Lock`, `asyncio.Lock`)
- Network connections
- Any resource that needs cleanup

**Why this matters**: Manual cleanup with `try/finally` is verbose and easy to forget. A missing `finally` block means exceptions leak resources. Context managers make correct cleanup the default path.

**Detection**: `grep -rn 'open(' --include="*.py" | grep -v 'with \|mock\|test'` finds file opens that may lack context managers.

---

## Import Specific Names, Never Use Star Imports

Import specific names (`from module import User, Order`) or import the module itself (`import module`). Star imports (`from module import *`) pollute the namespace with unknown names, making it impossible to trace where a symbol originated.

```python
# Import specific names
from module import User, Order, Product

# Or import the module for namespaced access
import module
user = module.User()

# For many imports, use explicit parenthesized form
from typing import (
    Any, TypeVar, Protocol,
    Callable, Sequence, Mapping,
)

# Type-only imports to avoid circular dependencies
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services import UserService  # Only used in type annotations
```

**When star imports are acceptable**:
- In `__init__.py` for public API definition with `__all__` explicitly defined

**Why this matters**: Star imports make it impossible to know where a name came from without checking every imported module. Name conflicts between modules are silent -- the last import wins. IDE autocomplete and refactoring tools cannot trace symbol origins.

**Detection**: `grep -rn 'from .* import \*' --include="*.py" | grep -v '__init__'` finds star imports outside `__init__.py`.

---

## Use Truthiness Directly, Not == True/False

Test boolean values with `if value:` and `if not value:`. For `None` checks, use `is None` / `is not None` (identity, not equality). Avoid `== True` and `== False` comparisons.

```python
if value:
    do_something()

if not flag:
    do_other_thing()

# For None checks, use identity comparison
if value is None:
    handle_none()

if value is not None:
    handle_value()
```

**Exception -- Peewee ORM**:
```python
# Peewee ORM field comparisons require == True for SQL generation
query = User.select().where(User.active == True)
# E712 should be suppressed for this specific ORM pattern
```

**Why this matters**: `== True` has unexpected behavior with non-boolean truthy values: `1 == True` is `True` but `2 == True` is `False`, even though `bool(2)` is `True`. Direct truthiness testing is both more correct and more readable.

**Detection**: Ruff flags this as `E712`. Run `ruff check . --select E712` to find all `== True` / `== False` comparisons.

---

## Limit Decorator Stacking to 1-2 Decorators

Keep decorator usage to one or two per function. When behavior requires more cross-cutting concerns, extract them into a class with explicit configuration or inline the logic where it is needed.

```python
# Clean: one decorator for the primary cross-cutting concern
@timer
def fetch_user(user_id: int) -> User:
    return api.get(f"/users/{user_id}")

# For complex behavior, use a class with explicit configuration
class UserFetcher:
    def __init__(self, cache_ttl: int = 300):
        self.cache = Cache(ttl=cache_ttl)
        self.rate_limiter = RateLimiter(calls=10, period=1)

    def fetch(self, user_id: int) -> User:
        if cached := self.cache.get(user_id):
            return cached

        with self.rate_limiter:
            user = api.get(f"/users/{user_id}")

        self.cache.set(user_id, user)
        return user

# Or make retry logic explicit where needed
def fetch_user(user_id: int) -> User:
    for attempt in range(3):
        try:
            return api.get(f"/users/{user_id}")
        except APIError:
            if attempt == 2:
                raise
            time.sleep(1)
```

**When decorators are appropriate**:
- Single cross-cutting concern (`@property`, `@staticmethod`)
- Framework requirements (`@app.route`, `@pytest.fixture`)
- One or two simple decorators maximum

**Why this matters**: Decorator execution order is bottom-up (closest to the function runs first), but readers scan top-down. A stack of 5+ decorators makes the actual call path opaque, complicates debugging (stack traces include wrapper frames), and makes testing difficult since each decorator adds a layer of indirection.

**Detection**: `grep -B5 'def ' --include="*.py" -rn | grep -c '@'` gives a rough count of decorator usage. Functions preceded by 3+ `@` lines warrant review.
