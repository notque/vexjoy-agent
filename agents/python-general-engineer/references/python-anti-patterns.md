# Python General Engineer - Preferred Patterns

Common Python mistakes, preferred fixes, and why they matter.

## Pattern: Over-Engineering with Abstract Base Classes

**Signal**:
```python
from abc import ABC, abstractmethod

# Creating ABCs before you have multiple implementations
class UserRepository(ABC):
    @abstractmethod
    def get(self, id: int) -> User: ...

    @abstractmethod
    def save(self, user: User) -> None: ...

class DatabaseUserRepository(UserRepository):
    def get(self, id: int) -> User:
        return query_db(id)

    def save(self, user: User) -> None:
        insert_db(user)
```

**Why it matters**:
- Adding abstraction layer before you have a second implementation
- Increases complexity without proven benefit
- Makes code harder to navigate and understand
- Violates YAGNI (You Aren't Gonna Need It)

**Preferred action**:
```python
# Simple concrete class - add abstraction later if needed
class UserRepository:
    def get(self, id: int) -> User:
        return query_db(id)

    def save(self, user: User) -> None:
        insert_db(user)

# When you need interface abstraction, use Protocol
from typing import Protocol

class UserRepository(Protocol):
    def get(self, id: int) -> User: ...
    def save(self, user: User) -> None: ...

# Any class with these methods satisfies the protocol
# No inheritance needed!
```

**Use ABCs when**:
- You have 2+ implementations already
- You're building a framework with extension points
- You need method implementation sharing via inheritance

---

## Pattern: Premature Async Conversion

**Signal**:
```python
# Converting synchronous code to async without I/O benefit
async def calculate_total(items: list[Item]) -> float:
    total = 0.0
    for item in items:
        total += await calculate_price(item)  # CPU-bound work
    return total

async def calculate_price(item: Item) -> float:
    return item.price * item.quantity  # Just math, no I/O
```

**Why it matters**:
- Adding async overhead for CPU-bound operations
- No concurrent I/O operations to benefit from
- Makes code more complex with no performance gain
- async/await is for I/O concurrency, not CPU parallelism

**Preferred action**:
```python
# Synchronous for pure computation
def calculate_total(items: list[Item]) -> float:
    return sum(item.price * item.quantity for item in items)

# Async only when doing I/O
async def fetch_and_calculate(user_id: int) -> float:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/users/{user_id}/items")
        items = [Item(**item) for item in response.json()]
    return calculate_total(items)  # Sync calculation

# Use TaskGroup for concurrent I/O
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
- File I/O with aiof files
- Multiple concurrent I/O operations

---

## Pattern: Type: Ignore Instead of Fixing Types

**Signal**:
```python
def process_data(data: dict) -> list[User]:
    users = []
    for item in data["users"]:  # type: ignore
        user = User(
            id=item["id"],  # type: ignore
            name=item["name"],  # type: ignore
        )
        users.append(user)  # type: ignore
    return users
```

**Why it matters**:
- Silencing type checker instead of fixing the underlying issue
- Loses type safety benefits
- Hides potential bugs that mypy would catch
- Makes refactoring dangerous

**Preferred action**:
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

**When type: ignore is acceptable**:
- `# type: ignore[specific-error]  # Reason: explanation` with specific error code and explanation
- Working around bugs in type stubs
- Interfacing with truly untyped code (rare)

---

## Pattern: Mutable Default Arguments

**Signal**:
```python
def add_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

# This creates shared state across calls!
result1 = add_item("a")  # ["a"]
result2 = add_item("b")  # ["a", "b"] - unexpected!
```

**Why it matters**:
- Default mutable arguments are created once at function definition
- All calls share the same mutable object
- Causes unexpected state sharing between function calls
- Classic Python gotcha that leads to hard-to-debug issues

**Preferred action**:
```python
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items

# Or better: don't mutate the input
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

**Detection**:
- Ruff will flag this as B006 error
- Run `ruff check .` to find all instances

---

## Pattern: String Concatenation in Loops

**Signal**:
```python
def build_message(items: list[str]) -> str:
    message = ""
    for item in items:
        message += f"{item}\n"  # Creates new string each iteration
    return message
```

**Why it matters**:
- Strings are immutable in Python
- Each concatenation creates a new string object
- O(n²) time complexity for n items
- Significant performance impact for large lists

**Preferred action**:
```python
def build_message(items: list[str]) -> str:
    return "\n".join(items)

# Or with formatting
def build_message(items: list[str]) -> str:
    return "\n".join(f"Item: {item}" for item in items)

# For complex building, use list then join
def build_html(items: list[str]) -> str:
    parts = ["<ul>"]
    for item in items:
        parts.append(f"  <li>{item}</li>")
    parts.append("</ul>")
    return "\n".join(parts)
```

**Performance comparison**:
```python
# BAD: O(n²)
result = ""
for i in range(1000):
    result += str(i)

# GOOD: O(n)
result = "".join(str(i) for i in range(1000))
```

---

## Pattern: Catching Bare Exceptions

**Signal**:
```python
try:
    process_data()
except:  # Catches EVERYTHING including SystemExit, KeyboardInterrupt
    log.error("Error occurred")
```

**Why it matters**:
- Catches `SystemExit`, `KeyboardInterrupt`, `GeneratorExit`
- Prevents graceful shutdown (Ctrl+C won't work)
- Hides programming errors during development
- Makes debugging very difficult

**Preferred action**:
```python
# Specific exceptions
try:
    process_data()
except ValueError as e:
    log.error(f"Invalid data: {e}")
except ConnectionError as e:
    log.error(f"Network error: {e}")

# Or Exception as catch-all (doesn't catch system exceptions)
try:
    process_data()
except Exception as e:
    log.error(f"Error: {e}", exc_info=True)
    # Re-raise if you can't handle it
    raise

# Python 3.11+ exception groups
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

**Required checks**:
- `except:` without type (use `except Exception:`)
- Catching without logging or re-raising
- Silencing errors with `pass`

---

## Pattern: print() in Production Code

**Signal**:
```python
def process_order(order_id: int):
    print(f"Processing order {order_id}")  # No log levels
    order = get_order(order_id)
    print(f"Order data: {order}")  # Might contain sensitive data
    process(order)
    print("Done")  # No timestamp, no structure
```

**Why it matters**:
- No log levels (can't filter by severity)
- No timestamps or structured metadata
- Can't route to different destinations
- Sensitive data might be logged
- No correlation IDs for distributed systems

**Preferred action**:
```python
import logging

logger = logging.getLogger(__name__)

def process_order(order_id: int):
    logger.info("Processing order", extra={"order_id": order_id})
    order = get_order(order_id)
    logger.debug("Order retrieved", extra={"order_id": order_id, "status": order.status})
    process(order)
    logger.info("Order processed successfully", extra={"order_id": order_id})

# Structured logging with JSON
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
- CLI applications for user output
- Debug scripts (not production services)
- Development/testing only

---

## Pattern: Not Using Context Managers

**Signal**:
```python
def process_file(path: str):
    f = open(path)
    data = f.read()
    # Forgot to close! Resource leak
    return process(data)

# Or manual cleanup
def fetch_data():
    conn = get_connection()
    try:
        data = conn.fetch()
        return data
    finally:
        conn.close()  # Manual cleanup
```

**Why it matters**:
- Easy to forget cleanup
- Exception handling becomes verbose
- Resource leaks if cleanup is missed
- Python has built-in context managers for this

**Preferred action**:
```python
# Use with statement
def process_file(path: str):
    with open(path) as f:
        data = f.read()
    return process(data)  # File automatically closed

# Multiple context managers
def copy_file(src: str, dst: str):
    with open(src) as src_f, open(dst, "w") as dst_f:
        dst_f.write(src_f.read())

# Async context managers
async def fetch_data():
    async with get_async_connection() as conn:
        data = await conn.fetch()
        return data  # Connection automatically closed

# Custom context manager
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
- Locks (threading.Lock, asyncio.Lock)
- Network connections
- Any resource that needs cleanup

---

## Pattern: Importing * (Star Imports)

**Signal**:
```python
from module import *

# Now you have dozens of names in namespace
# Where did `User` come from? No idea!
user = User()
```

**Why it matters**:
- Pollutes namespace with unknown names
- Makes it impossible to know where names come from
- Can cause name conflicts
- Makes refactoring dangerous
- IDE autocomplete becomes useless

**Preferred action**:
```python
# Import specific names
from module import User, Order, Product

# Or import module
import module
user = module.User()

# For many imports, be explicit
from typing import (
    Any, TypeVar, Protocol,
    Callable, Sequence, Mapping,
)

# Type-only imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services import UserService  # Only for type hints
```

**Ruff check**:
- `from module import *` in production code
- Only acceptable in `__init__.py` for public API definition with `__all__`

---

## Pattern: Using == for True/False Comparisons

**Signal**:
```python
if value == True:
    do_something()

if flag == False:
    do_other_thing()
```

**Why it matters**:
- Redundant and verbose
- Can have unexpected behavior with truthy/falsy values
- Violates PEP 8 style guide
- Ruff will flag as E712 error

**Preferred action**:
```python
if value:
    do_something()

if not flag:
    do_other_thing()

# For None checks, use `is`
if value is None:
    handle_none()

if value is not None:
    handle_value()
```

**Exception: Peewee ORM**:
```python
# This is OK for Peewee ORM field comparisons
query = User.select().where(User.active == True)
# E712 should be ignored for this specific ORM pattern
```

---

## Pattern: Complex Decorator Chains

**Signal**:
```python
@timer
@retry(max_attempts=3)
@cache(ttl=300)
@rate_limit(calls=10, period=1)
@validate_input
@log_calls
def fetch_user(user_id: int) -> User:
    return api.get(f"/users/{user_id}")
```

**Why it matters**:
- Difficult to understand execution order
- Hard to debug when something goes wrong
- Obscures the actual function behavior
- Makes testing complicated
- Order of decorators matters but isn't obvious

**Preferred action**:
```python
# Keep decorator usage minimal (1-2 max)
@timer
def fetch_user(user_id: int) -> User:
    return api.get(f"/users/{user_id}")

# Or make behavior explicit
def fetch_user(user_id: int) -> User:
    # Explicit retry logic where needed
    for attempt in range(3):
        try:
            return api.get(f"/users/{user_id}")
        except APIError:
            if attempt == 2:
                raise
            time.sleep(1)

# Use classes for complex behavior
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

**When decorators are appropriate**:
- Single cross-cutting concern (`@property`, `@staticmethod`)
- Framework requirements (`@app.route`, `@pytest.fixture`)
- One or two simple decorators maximum
