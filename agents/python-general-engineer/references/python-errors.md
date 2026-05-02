# Python General Engineer - Error Catalog

## Category: Async/Await Errors

### Error: Async Deadlock or Hanging

**Symptoms**: Program hangs, `asyncio.run()` never completes, tasks start but don't finish.

**Solution**:
```python
# BAD - Missing await
async def fetch_data():
    result = async_api_call()  # Missing await!
    return result

# GOOD
async def fetch_data():
    result = await async_api_call()
    return result

# BAD - Awaiting non-awaitable
async def process():
    data = await regular_function()  # Not async!

# GOOD
async def process():
    data = regular_function()

# Use TaskGroup for structured concurrency
async def fetch_multiple():
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(fetch_users(), name="users")
        task2 = tg.create_task(fetch_orders(), name="orders")
    return task1.result(), task2.result()
```

**Prevention**: Type hints (`-> Awaitable[T]`), mypy, `asyncio.create_task()` with names, TaskGroup over gather.

---

### Error: Event Loop Already Running

**Symptoms**: `RuntimeError: This event loop is already running` (Jupyter/nested async).

**Solution**:
```python
# In Jupyter: use await directly, not asyncio.run()
await my_async_function()

# For scripts: asyncio.run() at top level only
if __name__ == "__main__":
    asyncio.run(main())
```

---

## Category: Type Errors

### Error: Incompatible Type (mypy)

**Solution**:
```python
# BAD - Suppressing a real bug
def get_user(user_id: int) -> User:
    user = db.query(user_id)  # Returns User | None
    return user  # type: ignore  # Bug!

# GOOD - Fix the actual issue
def get_user(user_id: int) -> User:
    user = db.query(user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user

# Use TypedDict for structured dicts
class UserData(TypedDict):
    name: str
    email: str
    age: int
```

**Prevention**: `mypy --strict`, TypedDict for dicts, type narrowing (isinstance), fix bugs not silence errors.

---

### Error: Missing Type Stubs

**Solution**:
```bash
pip install types-requests types-redis types-PyYAML

# Or in pyproject.toml
[project.optional-dependencies]
dev = ["types-requests", "types-redis", "types-PyYAML"]
```

---

## Category: Linting Errors

### Error: B006 - Mutable Default Argument

**Solution**:
```python
# BAD
def add_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

# GOOD
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

---

### Error: UP035 - Deprecated Typing Import

**Solution**:
```python
# BAD (3.8 style)
from typing import List, Dict, Tuple, Set

# GOOD (3.9+)
def process(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}
```

**Fix**: `ruff check --fix --select UP`

---

## Category: Import Errors

### Error: Circular Imports

**Solution**:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services import UserService  # Only for type checking

class User:
    def process(self, service: "UserService") -> None:
        service.handle(self)

# Alternative: from __future__ import annotations
```

**Prevention**: TYPE_CHECKING for type-only imports, `from __future__ import annotations`, move shared types to separate module.

---

## Category: Test Errors

### Error: AttributeError on Mock

**Solution**:
```python
from unittest.mock import Mock, MagicMock

# Configure return_value
mock_client = Mock()
mock_client.get.return_value = {"users": []}

# Use spec to validate attributes
mock_client = Mock(spec=HTTPClient)
mock_client.invalid_method()  # AttributeError!

# For exceptions
mock_client.get.side_effect = ConnectionError("Network error")

# Multiple calls
mock_client.get.side_effect = [
    {"users": ["alice"]},
    {"users": ["bob"]},
    ConnectionError("Failed"),
]
```

---

### Error: pytest Async Test Not Running

**Solution**:
```bash
pip install pytest-asyncio
```

```python
@pytest.mark.asyncio
async def test_fetch_users():
    users = await fetch_users()
    assert len(users) > 0

# Or configure in pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

## Category: Dependency Errors

### Error: ModuleNotFoundError

**Solution**:
```bash
python -c "import sys; print(sys.prefix)"  # Check environment
source venv/bin/activate
pip install package-name

# Or use uv
uv add package-name
uv sync
```

---

## Category: Pydantic Validation Errors

### Error: ValidationError

**Solution**:
```python
from pydantic import BaseModel, Field, field_validator

class User(BaseModel):
    name: str = Field(min_length=1)
    email: str
    age: int = Field(ge=0, le=150)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        if "@" not in v:
            raise ValueError("Invalid email format")
        return v.lower()

# Handle errors
from pydantic import ValidationError

try:
    user = User(name="", email="invalid", age=200)
except ValidationError as e:
    print(e.errors())
```

**Prevention**: Field constraints, custom validators, handle ValidationError at API boundaries.
