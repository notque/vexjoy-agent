# Python General Engineer - Preferred Patterns

Action-first patterns for correct Python code. Each leads with what to do, followed by detection commands.

## Start With Concrete Classes, Add Abstraction When Needed

Write a plain class first. Introduce `Protocol` when you have 2+ implementations. Protocols use structural subtyping — matching methods satisfy the protocol without inheritance.

```python
class UserRepository:
    def get(self, id: int) -> User:
        return query_db(id)
    def save(self, user: User) -> None:
        insert_db(user)

# When you need abstraction, use Protocol
from typing import Protocol

class UserRepository(Protocol):
    def get(self, id: int) -> User: ...
    def save(self, user: User) -> None: ...
```

**When ABCs are appropriate**: 2+ implementations exist, framework extension points, method sharing via inheritance.

**Detection**: `grep -rn 'class.*ABC' --include="*.py" | grep -v 'test'`

---

## Keep CPU-Bound Code Synchronous

`async/await` only for I/O. Pure computation gains nothing from async. Use `asyncio.TaskGroup` for concurrent I/O.

```python
# Sync for computation
def calculate_total(items: list[Item]) -> float:
    return sum(item.price * item.quantity for item in items)

# Async only for I/O
async def fetch_and_calculate(user_id: int) -> float:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/users/{user_id}/items")
        items = [Item(**item) for item in response.json()]
    return calculate_total(items)

# TaskGroup for concurrent I/O (3.11+)
async def fetch_multiple_users(user_ids: list[int]) -> list[float]:
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_and_calculate(uid)) for uid in user_ids]
    return [task.result() for task in tasks]
```

**Detection**: `grep -rn 'async def' --include="*.py" | xargs grep -L 'await'`

---

## Fix Type Errors Instead of Suppressing Them

Define proper types with `TypedDict` or Pydantic. Each `# type: ignore` is a suppressed bug report.

```python
from typing import TypedDict

class UserDict(TypedDict):
    id: int
    name: str

class ResponseData(TypedDict):
    users: list[UserDict]

def process_data(data: ResponseData) -> list[User]:
    return [User(id=item["id"], name=item["name"]) for item in data["users"]]
```

**When `# type: ignore` is acceptable**: `# type: ignore[specific-error]  # Reason: explanation`, third-party stub bugs, untyped C extensions.

**Detection**: `grep -rn 'type: ignore' --include="*.py" | grep -v 'type: ignore\[' `

---

## Use None as Default for Mutable Arguments

Never use `[]`, `{}`, `set()` as defaults. Python creates defaults once — all calls share the same object.

```python
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items

# For dataclasses
@dataclass
class Cart:
    items: list[str] = field(default_factory=list)
```

**Detection**: `ruff check . --select B006`

---

## Build Strings With join(), Not Loop Concatenation

`join()` allocates once — O(n). Loop `+=` copies the entire string each iteration — O(n^2).

```python
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

**Detection**: `grep -rn '+= .*f"' --include="*.py"` and `grep -rn '+= "' --include="*.py"`

---

## Catch Specific Exceptions, Never Bare except

`except Exception` as broadest catch-all — excludes `SystemExit`, `KeyboardInterrupt`, `GeneratorExit`.

```python
try:
    process_data()
except ValueError as e:
    log.error(f"Invalid data: {e}")
except ConnectionError as e:
    log.error(f"Network error: {e}")

# 3.11+ exception groups
try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(task1())
        tg.create_task(task2())
except* ValueError as eg:
    for exc in eg.exceptions:
        log.error(f"Validation error: {exc}")
```

**Detection**: `grep -rn 'except:' --include="*.py"`

---

## Use Structured Logging, Not print()

`logging.getLogger(__name__)` provides severity levels, timestamps, structured metadata, and routing.

```python
import logging

logger = logging.getLogger(__name__)

def process_order(order_id: int):
    logger.info("Processing order", extra={"order_id": order_id})
    order = get_order(order_id)
    logger.debug("Order retrieved", extra={"order_id": order_id, "status": order.status})
```

**When print() is acceptable**: CLI output, debug scripts, development only.

**Detection**: `grep -rn 'print(' --include="*.py" | grep -v '_test.py\|test_\|cli\|__main__'`

---

## Use Context Managers for Resource Cleanup

`with` guarantees cleanup even on exceptions.

```python
def process_file(path: str):
    with open(path) as f:
        data = f.read()
    return process(data)

# Custom with transaction semantics
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
```

**Always use for**: files, database connections, locks, network sockets.

**Detection**: `grep -rn 'open(' --include="*.py" | grep -v 'with \|mock\|test'`

---

## Import Specific Names, Never Star Imports

```python
from module import User, Order, Product

# Or import the module
import module
user = module.User()

# Type-only imports to avoid circular deps
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from services import UserService
```

**Acceptable**: In `__init__.py` with `__all__` explicitly defined.

**Detection**: `grep -rn 'from .* import \*' --include="*.py" | grep -v '__init__'`

---

## Use Truthiness Directly, Not == True/False

```python
if value:
    do_something()
if value is None:
    handle_none()
```

**Exception — Peewee ORM**: `User.select().where(User.active == True)` required for SQL generation.

**Detection**: `ruff check . --select E712`

---

## Limit Decorator Stacking to 1-2 Decorators

For complex behavior, use a class with explicit configuration or inline the logic.

```python
# Clean: one decorator
@timer
def fetch_user(user_id: int) -> User:
    return api.get(f"/users/{user_id}")

# For complex behavior
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
```

**When decorators are appropriate**: `@property`, `@staticmethod`, framework requirements (`@app.route`, `@pytest.fixture`).

**Detection**: Functions preceded by 3+ `@` lines warrant review.
