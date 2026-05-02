# Python Code Patterns and Best Practices

> Reference file for python-general-engineer agent.

## Type Hints Everywhere

```python
# Builtin generics (3.9+)
def process(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# Union with | (3.10+)
def find(key: str) -> str | None: ...

# Type parameter syntax (3.12+)
type Vector[T] = list[T]
def first[T](items: list[T]) -> T:
    return items[0]
```

## Dataclasses vs NamedTuple vs TypedDict

```python
from dataclasses import dataclass, field
from typing import NamedTuple, TypedDict

# Dataclass — mutable, methods, defaults
@dataclass
class User:
    name: str
    email: str
    roles: list[str] = field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles

# NamedTuple — immutable, dict key, unpacking
class Coordinate(NamedTuple):
    lat: float
    lon: float

# TypedDict — typed dict for JSON/API shapes
class APIResponse(TypedDict):
    status: int
    data: list[dict[str, str]]
    error: str | None

# When to use:
# - Dataclass: domain objects, mutable state, methods
# - NamedTuple: immutable records, used as keys
# - TypedDict: JSON payloads, API shapes, config dicts
```

## Protocol Classes for Structural Typing

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class Renderable(Protocol):
    def render(self) -> str: ...

class HTMLWidget:
    def render(self) -> str:
        return "<div>widget</div>"

# Satisfies Renderable without inheriting from it
def display(item: Renderable) -> None:
    print(item.render())

assert isinstance(HTMLWidget(), Renderable)
```

## Context Managers with @contextmanager

```python
from contextlib import contextmanager

@contextmanager
def timer(label: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        print(f"{label}: {elapsed:.3f}s")

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

```python
from typing import Protocol

class EmailSender(Protocol):
    def send(self, to: str, body: str) -> None: ...

class SMTPSender:
    def send(self, to: str, body: str) -> None: ...

class FakeSender:
    def __init__(self):
        self.sent: list[tuple[str, str]] = []
    def send(self, to: str, body: str) -> None:
        self.sent.append((to, body))

@dataclass
class NotificationService:
    sender: EmailSender  # injected

    def notify_user(self, user_email: str, message: str) -> None:
        self.sender.send(user_email, message)

# Production
service = NotificationService(sender=SMTPSender())
# Testing
fake = FakeSender()
service = NotificationService(sender=fake)
```

## functools: lru_cache, singledispatch, wraps

```python
from functools import lru_cache, singledispatch, wraps

@lru_cache(maxsize=512)
def fibonacci(n: int) -> int:
    if n < 2: return n
    return fibonacci(n - 1) + fibonacci(n - 2)

@singledispatch
def serialize(obj) -> str:
    raise TypeError(f"Cannot serialize {type(obj)}")

@serialize.register
def _(obj: str) -> str: return f'"{obj}"'

@serialize.register
def _(obj: int) -> str: return str(obj)

@serialize.register
def _(obj: list) -> str:
    return "[" + ", ".join(serialize(x) for x in obj) + "]"

def retry(max_attempts: int = 3):
    def decorator(func):
        @wraps(func)
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

```python
from itertools import chain, groupby, islice, batched

all_items = list(chain(list_a, list_b, list_c))
flat = list(chain.from_iterable(nested))  # [[1,2],[3,4]] → [1,2,3,4]

# groupby (must be sorted first)
from operator import attrgetter
users_by_role = {
    role: list(group)
    for role, group in groupby(sorted(users, key=attrgetter("role")), key=attrgetter("role"))
}

first_ten = list(islice(infinite_generator(), 10))

# batched (3.12+)
for batch in batched(range(25), 10):
    process_batch(batch)
```

## Enum with auto() for State Machines

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
        case OrderStatus.PENDING: return OrderStatus.CONFIRMED
        case OrderStatus.CONFIRMED: return OrderStatus.SHIPPED
        case OrderStatus.SHIPPED: return OrderStatus.DELIVERED
        case OrderStatus.DELIVERED | OrderStatus.CANCELLED:
            raise ValueError(f"Cannot advance from {status.name}")
```

## Async Patterns: TaskGroup (3.11+), Async Generators

```python
import asyncio

async def fetch_all(urls: list[str]) -> list[Response]:
    results = []
    async with asyncio.TaskGroup() as tg:
        for url in urls:
            results.append(tg.create_task(fetch(url)))
    return [t.result() for t in results]

async def stream_results(query: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"/search?q={query}") as resp:
            async for line in resp.content:
                yield json.loads(line)

async def bounded_fetch(urls: list[str], max_concurrent: int = 10):
    semaphore = asyncio.Semaphore(max_concurrent)
    async def fetch_one(url: str) -> Response:
        async with semaphore:
            return await fetch(url)
    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(fetch_one(url)) for url in urls]
    return [t.result() for t in tasks]
```
