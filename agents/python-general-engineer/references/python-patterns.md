# Python Code Patterns and Best Practices

> Reference file for python-general-engineer agent. Loaded as context during Python development tasks.

## Type Hints Everywhere

Use type hints on all function signatures, class attributes, and module-level variables. Modern Python (3.12+) supports cleaner syntax.

```python
# Use builtin generics (3.9+) — no need for typing.List, typing.Dict
def process(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# Union with | operator (3.10+)
def find(key: str) -> str | None:
    ...

# Type parameter syntax (3.12+)
type Vector[T] = list[T]

def first[T](items: list[T]) -> T:
    return items[0]
```

## Dataclasses vs NamedTuple vs TypedDict

Each serves a different purpose. Choose based on mutability and usage context.

```python
from dataclasses import dataclass, field
from typing import NamedTuple, TypedDict

# Dataclass — mutable structured data, methods, defaults, validation
@dataclass
class User:
    name: str
    email: str
    roles: list[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

# NamedTuple — immutable record, works as dict key, unpacking
class Coordinate(NamedTuple):
    lat: float
    lon: float

point = Coordinate(40.7, -74.0)
lat, lon = point  # unpacking works

# TypedDict — typed dict for JSON-like data, API responses
class APIResponse(TypedDict):
    status: int
    data: list[dict[str, str]]
    error: str | None

# When to use:
# - Dataclass: domain objects, mutable state, methods needed
# - NamedTuple: immutable records, used as keys, lightweight
# - TypedDict: JSON payloads, external API shapes, config dicts
```

## Protocol Classes for Structural Typing

Protocols define interfaces without inheritance. Objects satisfy a Protocol if they have the right methods — duck typing with type safety.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Renderable(Protocol):
    def render(self) -> str: ...

class HTMLWidget:
    def render(self) -> str:
        return "<div>widget</div>"

class MarkdownDoc:
    def render(self) -> str:
        return "# Document"

# Both satisfy Renderable without inheriting from it
def display(item: Renderable) -> None:
    print(item.render())

display(HTMLWidget())    # works
display(MarkdownDoc())   # works

# runtime_checkable allows isinstance checks
assert isinstance(HTMLWidget(), Renderable)
```

## Context Managers with @contextmanager

The `@contextmanager` decorator turns a generator function into a context manager. Simpler than writing `__enter__`/`__exit__`.

```python
from contextlib import contextmanager
import time

@contextmanager
def timer(label: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed:.3f}s")

with timer("database query"):
    results = db.execute(query)

# Async version
from contextlib import asynccontextmanager

@asynccontextmanager
async def managed_connection(url: str):
    conn = await connect(url)
    try:
        yield conn
    finally:
        await conn.close()
```

## Dependency Injection Patterns

Pass dependencies in so code stays testable and configurable.

```python
from dataclasses import dataclass, field
from typing import Protocol

class EmailSender(Protocol):
    def send(self, to: str, body: str) -> None: ...

class SMTPSender:
    def send(self, to: str, body: str) -> None:
        # real SMTP logic
        ...

class FakeSender:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send(self, to: str, body: str) -> None:
        self.sent.append((to, body))

@dataclass
class NotificationService:
    sender: EmailSender  # injected, not hard-coded

    def notify_user(self, user_email: str, message: str) -> None:
        self.sender.send(user_email, message)

# Production
service = NotificationService(sender=SMTPSender())

# Testing
fake = FakeSender()
service = NotificationService(sender=fake)
service.notify_user("a@b.com", "hello")
assert len(fake.sent) == 1
```

## functools: lru_cache, singledispatch, wraps

The `functools` module provides powerful function composition tools.

```python
from functools import lru_cache, singledispatch, wraps

# lru_cache — memoize expensive pure functions
@lru_cache(maxsize=512)
def fibonacci(n: int) -> int:
    if n < 2:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

# singledispatch — function overloading by first argument type
@singledispatch
def serialize(obj) -> str:
    raise TypeError(f"Cannot serialize {type(obj)}")

@serialize.register
def _(obj: str) -> str:
    return f'"{obj}"'

@serialize.register
def _(obj: int) -> str:
    return str(obj)

@serialize.register
def _(obj: list) -> str:
    return "[" + ", ".join(serialize(x) for x in obj) + "]"

# wraps — preserve metadata on decorators
def retry(max_attempts: int = 3):
    def decorator(func):
        @wraps(func)  # preserves __name__, __doc__, etc.
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if attempt == max_attempts - 1:
                        raise
        return wrapper
    return decorator
```

## itertools Patterns

Standard library tools for efficient iteration.

```python
from itertools import chain, groupby, islice, batched

# chain — flatten multiple iterables
all_items = list(chain(list_a, list_b, list_c))

# chain.from_iterable — flatten list of lists
nested = [[1, 2], [3, 4], [5]]
flat = list(chain.from_iterable(nested))  # [1, 2, 3, 4, 5]

# groupby — group sorted items by key
from operator import attrgetter
users_by_role = {
    role: list(group)
    for role, group in groupby(
        sorted(users, key=attrgetter("role")),
        key=attrgetter("role"),
    )
}

# islice — lazy slicing of any iterable
first_ten = list(islice(infinite_generator(), 10))

# batched (3.12+) — chunk iterable into fixed-size groups
for batch in batched(range(25), 10):
    process_batch(batch)  # (0..9), (10..19), (20..24)
```

## Enum with auto() for State Machines

Enums provide type-safe named constants. Combine with `auto()` and `match/case` for state machines.

```python
from enum import Enum, auto

class OrderStatus(Enum):
    PENDING = auto()
    CONFIRMED = auto()
    SHIPPED = auto()
    DELIVERED = auto()
    CANCELLED = auto()

def advance(status: OrderStatus) -> OrderStatus:
    match status:
        case OrderStatus.PENDING:
            return OrderStatus.CONFIRMED
        case OrderStatus.CONFIRMED:
            return OrderStatus.SHIPPED
        case OrderStatus.SHIPPED:
            return OrderStatus.DELIVERED
        case OrderStatus.DELIVERED | OrderStatus.CANCELLED:
            raise ValueError(f"Cannot advance from {status.name}")
```

## match/case (Structural Pattern Matching, 3.10+)

Pattern matching with destructuring, guards, and type checks.

```python
# Match on structure, not just value
def handle_command(command: dict) -> str:
    match command:
        case {"action": "create", "name": str(name)}:
            return f"Creating {name}"
        case {"action": "delete", "id": int(id_)} if id_ > 0:
            return f"Deleting #{id_}"
        case {"action": str(action)}:
            return f"Unknown action: {action}"
        case _:
            return "Invalid command"

# Match on class instances
@dataclass
class Point:
    x: float
    y: float

def classify(point: Point) -> str:
    match point:
        case Point(x=0, y=0):
            return "origin"
        case Point(x=0, y=y):
            return f"y-axis at {y}"
        case Point(x=x, y=0):
            return f"x-axis at {x}"
        case Point(x=x, y=y) if x == y:
            return f"diagonal at {x}"
        case _:
            return "general"
```

## Async Patterns: TaskGroup (3.11+), Async Generators

Modern async patterns for concurrent work.

```python
import asyncio

# TaskGroup — structured concurrency (3.11+)
async def fetch_all(urls: list[str]) -> list[Response]:
    results = []
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            task = tg.create_task(fetch(url))
            results.append(task)
    return [t.result() for t in results]
    # If any task raises, all others are cancelled

# Async generator — stream results as they arrive
async def stream_results(query: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"/search?q={query}") as resp:
            async for line in resp.content:
                yield json.loads(line)

# Consuming async generators
async def process_stream():
    async for result in stream_results("python"):
        print(result)

# Semaphore for rate limiting
async def bounded_fetch(urls: list[str], max_concurrent: int = 10):
    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_one(url: str) -> Response:
        async with semaphore:
            return await fetch(url)

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_one(url)) for url in urls]
    return [t.result() for t in tasks]
```
