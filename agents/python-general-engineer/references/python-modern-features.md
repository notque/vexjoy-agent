# Python Modern Features (3.11+)

## Python 3.11+ Features

### Structural Pattern Matching (3.10+)

```python
def process_command(command: dict) -> str:
    match command:
        case {"action": "create", "type": "user", "data": user_data}:
            return create_user(user_data)
        case {"action": "delete", "type": "user", "id": user_id}:
            return delete_user(user_id)
        case {"action": action, **rest}:
            return f"Unknown action: {action}"
        case _:
            return "Invalid command"

def classify_age(age: int) -> str:
    match age:
        case n if n < 0: return "Invalid"
        case n if n < 18: return "Minor"
        case n if n < 65: return "Adult"
        case _: return "Senior"
```

### Exception Groups (3.11+)

```python
async def fetch_all():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(fetch_users())
        tg.create_task(fetch_orders())

try:
    async with asyncio.TaskGroup() as tg:
        tg.create_task(task1())
        tg.create_task(task2())
except* ValueError as eg:
    print(f"Got {len(eg.exceptions)} ValueError exceptions")
except* TypeError as eg:
    print(f"Got {len(eg.exceptions)} TypeError exceptions")
```

### Self Type (3.11+)

```python
from typing import Self

class Builder:
    def __init__(self) -> None:
        self.value = 0

    def add(self, n: int) -> Self:
        self.value += n
        return self
```

### NotRequired in TypedDict (3.11+)

```python
from typing import TypedDict, NotRequired

class UserDict(TypedDict):
    id: int
    name: str
    email: str
    age: NotRequired[int]
```

## Python 3.12+ Features

### PEP 695 Type Parameter Syntax

```python
# New syntax (3.12+)
class Container[T]:
    def __init__(self, value: T) -> None:
        self.value = value

def first[T](items: list[T]) -> T | None:
    return items[0] if items else None

type Point = tuple[float, float]
type Vector[T] = list[T]
```

## asyncio.TaskGroup Patterns

```python
import asyncio

async def fetch_all_data() -> dict:
    results = {}
    async with asyncio.TaskGroup() as tg:
        users_task = tg.create_task(fetch_users(), name="users")
        orders_task = tg.create_task(fetch_orders(), name="orders")
    results["users"] = users_task.result()
    results["orders"] = orders_task.result()
    return results

# With timeout
async def fetch_with_timeout() -> dict:
    try:
        async with asyncio.timeout(30):
            async with asyncio.TaskGroup() as tg:
                users_task = tg.create_task(fetch_users())
                orders_task = tg.create_task(fetch_orders())
            return {"users": users_task.result(), "orders": orders_task.result()}
    except TimeoutError:
        return {"error": "Request timed out"}
```

## Pydantic v2 Patterns

```python
from pydantic import BaseModel, Field, ConfigDict, field_validator, computed_field

class User(BaseModel):
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    id: int
    username: str = Field(min_length=3, max_length=50)
    email: str = Field(pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
    age: int = Field(ge=0, le=150)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower()

    @computed_field
    @property
    def display_name(self) -> str:
        return f"{self.username} ({self.email})"
```

## Modern Package Management with uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv init my-project
cd my-project
uv add fastapi uvicorn pydantic
uv add --dev pytest ruff mypy
uv run pytest
uv sync
```

## Ruff Configuration

```toml
# pyproject.toml
[tool.ruff]
target-version = "py311"
line-length = 88

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "SIM", "RUF"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
```

## FastAPI Modern Patterns

```python
from fastapi import FastAPI, Depends
from contextlib import asynccontextmanager
from typing import Annotated

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db = await create_db_pool()
    yield
    await app.state.db.close()

app = FastAPI(lifespan=lifespan)

async def get_db():
    async with app.state.db.acquire() as conn:
        yield conn

DB = Annotated[Connection, Depends(get_db)]

@app.get("/users/{user_id}")
async def get_user(user_id: int, db: DB) -> User:
    user = await db.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
    if not user:
        raise HTTPException(404, "User not found")
    return User(**user)
```
