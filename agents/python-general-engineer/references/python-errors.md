# Python General Engineer - Error Catalog

Comprehensive Python error patterns and solutions.

## Category: Async/Await Errors

### Error: Async Deadlock or Hanging

**Symptoms**:
- Program hangs when running async code
- `asyncio.run()` never completes
- Tasks seem to start but never finish

**Cause**:
- Awaiting on non-awaitable object
- Missing `await` keyword before async function call
- Circular dependencies in async code
- Event loop blocking operations

**Solution**:
```python
# BAD - Missing await
async def fetch_data():
    result = async_api_call()  # Missing await!
    return result

# GOOD - Proper await
async def fetch_data():
    result = await async_api_call()
    return result

# BAD - Awaiting non-awaitable
async def process():
    data = await regular_function()  # Not async!

# GOOD - Don't await sync functions
async def process():
    data = regular_function()  # Sync call, no await

# Use TaskGroup for structured concurrency
async def fetch_multiple():
    async with asyncio.TaskGroup() as tg:
        task1 = tg.create_task(fetch_users(), name="users")
        task2 = tg.create_task(fetch_orders(), name="orders")

    return task1.result(), task2.result()
```

**Prevention**:
- Use type hints: `async def func() -> Awaitable[T]:`
- Run mypy to catch await/async mismatches
- Use `asyncio.create_task()` with task names for debugging
- Use TaskGroup instead of asyncio.gather for better error handling

---

### Error: Event Loop Already Running

**Symptoms**:
- `RuntimeError: This event loop is already running`
- Occurs in Jupyter notebooks or when nesting async calls

**Cause**:
- Calling `asyncio.run()` inside an already-running event loop
- Jupyter/IPython already has an event loop running

**Solution**:
```python
# In Jupyter or nested async context
import nest_asyncio
nest_asyncio.apply()

# Or use await directly instead of asyncio.run()
# BAD - in Jupyter
asyncio.run(my_async_function())

# GOOD - in Jupyter
await my_async_function()

# For scripts, use asyncio.run() at top level only
if __name__ == "__main__":
    asyncio.run(main())
```

**Prevention**:
- Only use `asyncio.run()` at the top level of scripts
- In notebooks, use `await` directly
- Don't nest `asyncio.run()` calls

---

## Category: Type Errors

### Error: Incompatible Type (mypy)

**Symptoms**:
- `error: Incompatible types in assignment`
- `error: Argument 1 has incompatible type`

**Cause**:
- Actual type mismatch indicating a bug
- Incorrect type hints
- Missing type narrowing

**Solution**:
```python
# BAD - Don't ignore, it's catching a real bug
def get_user(user_id: int) -> User:
    user = db.query(user_id)  # Returns User | None
    return user  # type: ignore  # Bug! Can return None

# GOOD - Fix the actual issue
def get_user(user_id: int) -> User:
    user = db.query(user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found")
    return user

# Or update return type if None is valid
def get_user(user_id: int) -> User | None:
    return db.query(user_id)

# Type narrowing for dicts
data: dict[str, Any] = get_json()

# BAD - mypy doesn't know types
name = data["name"]  # type is Any

# GOOD - Use TypedDict
class UserData(TypedDict):
    name: str
    email: str
    age: int

data: UserData = get_json()
name = data["name"]  # type is str
```

**Prevention**:
- Run `mypy --strict .` to catch issues early
- Use TypedDict for structured dictionary data
- Use type narrowing (isinstance checks)
- Fix the bug, don't silence the error

---

### Error: Missing Type Stubs

**Symptoms**:
- `error: Library stubs not installed for "package-name"`
- `note: Hint: "python3 -m pip install types-package-name"`

**Cause**:
- Third-party library doesn't have type hints
- Type stubs package not installed

**Solution**:
```bash
# Install type stubs
pip install types-requests
pip install types-redis
pip install types-PyYAML

# Or in pyproject.toml
[project.optional-dependencies]
dev = [
    "types-requests",
    "types-redis",
    "types-PyYAML",
]
```

**Prevention**:
- Install type stubs for all untyped dependencies
- Check typeshed for available stubs
- Contribute stubs for libraries you use

---

## Category: Linting Errors

### Error: B006 - Mutable Default Argument

**Symptoms**:
- `B006 Do not use mutable data structures for argument defaults`
- Unexpected shared state between function calls

**Cause**:
- Using list, dict, or set as default argument
- Default is created once at function definition time

**Solution**:
```python
# BAD - Mutable default
def add_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)
    return items

# All calls share same list!
add_item("a")  # ["a"]
add_item("b")  # ["a", "b"] - unexpected!

# GOOD - Use None
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items

# Or don't mutate, return new list
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    items = items or []
    return [*items, item]
```

**Prevention**:
- Always use `None` as default for mutable types
- Ruff will catch this automatically

---

### Error: UP035 - Deprecated Typing Import

**Symptoms**:
- `UP035 `typing.List` is deprecated, use `list` instead`
- Using `typing.Dict`, `typing.Tuple`, etc.

**Cause**:
- Using old-style typing imports (Python 3.8 style)
- Not using built-in generic types (Python 3.9+)

**Solution**:
```python
# BAD - Deprecated typing imports
from typing import List, Dict, Tuple, Set

def process(items: List[str]) -> Dict[str, int]:
    return {item: len(item) for item in items}

# GOOD - Built-in generics (Python 3.9+)
def process(items: list[str]) -> dict[str, int]:
    return {item: len(item) for item in items}

# Correct imports for modern Python
from typing import (
    Any, TypeVar, Protocol,
    Callable, Literal, TypedDict,
    Self,  # 3.11+
)
```

**Prevention**:
- Use built-in `list`, `dict`, `tuple`, `set` for type hints
- Run `ruff check --select UP` to find deprecated imports
- Use `ruff check --fix` to auto-fix

---

## Category: Import Errors

### Error: Circular Imports

**Symptoms**:
- `ImportError: cannot import name 'X' from partially initialized module`
- Import works in some contexts but not others

**Cause**:
- Module A imports module B, and module B imports module A
- Usually happens with type hints

**Solution**:
```python
# file: models.py
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services import UserService  # Only imported for type checking

class User:
    def process(self, service: "UserService") -> None:  # String annotation
        service.handle(self)

# file: services.py
from models import User  # No circular import at runtime

class UserService:
    def handle(self, user: User) -> None:
        pass

# Alternative: Use forward references
from __future__ import annotations  # Top of file

class User:
    def process(self, service: UserService) -> None:  # No quotes needed
        service.handle(self)
```

**Prevention**:
- Use `TYPE_CHECKING` for type-only imports
- Use `from __future__ import annotations` (PEP 563)
- Reorganize code to reduce circular dependencies
- Move shared types to separate module

---

## Category: Test Errors

### Error: AttributeError on Mock

**Symptoms**:
- `AttributeError: Mock object has no attribute 'foo'`
- Mock methods not callable

**Cause**:
- Mock not configured properly
- Missing return_value or side_effect
- Accessing attribute not set on mock

**Solution**:
```python
from unittest.mock import Mock, MagicMock

# BAD - Mock not configured
mock_client = Mock()
result = mock_client.get("/users")  # Returns <Mock ...>, not what you want

# GOOD - Configure return_value
mock_client = Mock()
mock_client.get.return_value = {"users": []}
result = mock_client.get("/users")  # Returns {"users": []}

# Use spec to validate attributes
mock_client = Mock(spec=HTTPClient)
mock_client.get.return_value = {"users": []}
mock_client.invalid_method()  # AttributeError! Method doesn't exist on spec

# For exceptions
mock_client.get.side_effect = ConnectionError("Network error")

# For multiple calls with different results
mock_client.get.side_effect = [
    {"users": ["alice"]},
    {"users": ["bob"]},
    ConnectionError("Failed"),
]
```

**Prevention**:
- Always configure `return_value` or `side_effect`
- Use `spec=` parameter to validate mock usage
- Use `MagicMock` for magic methods (`__enter__`, `__exit__`)

---

## Category: Async Test Errors

### Error: pytest Async Test Not Running

**Symptoms**:
- `async def test_foo()` passes without running
- Async code not executed in tests

**Cause**:
- Missing `pytest-asyncio` plugin
- Missing `@pytest.mark.asyncio` decorator

**Solution**:
```bash
# Install pytest-asyncio
pip install pytest-asyncio
```

```python
# Add decorator to async tests
import pytest

@pytest.mark.asyncio
async def test_fetch_users():
    users = await fetch_users()
    assert len(users) > 0

# Or configure in pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"  # Automatically detect async tests

# Then no decorator needed
async def test_fetch_users():  # Automatically recognized
    users = await fetch_users()
    assert len(users) > 0
```

**Prevention**:
- Install `pytest-asyncio` in dev dependencies
- Configure `asyncio_mode = "auto"` in pyproject.toml
- Use async fixtures for setup/teardown

---

## Category: Dependency Errors

### Error: ModuleNotFoundError

**Symptoms**:
- `ModuleNotFoundError: No module named 'package'`
- Import works locally but fails in CI

**Cause**:
- Package not installed in virtual environment
- Wrong virtual environment activated
- Package not in requirements.txt

**Solution**:
```bash
# Check current environment
python -c "import sys; print(sys.prefix)"

# Activate correct venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install missing package
pip install package-name

# Freeze dependencies
pip freeze > requirements.txt

# Or use uv (modern alternative)
uv add package-name  # Adds to pyproject.toml and installs
uv sync  # Sync environment with lockfile
```

**Prevention**:
- Always use virtual environments
- Keep requirements.txt or pyproject.toml up to date
- Use `uv` for dependency management (faster, better locking)
- Document setup steps in README

---

## Category: Pydantic Validation Errors

### Error: ValidationError

**Symptoms**:
- `pydantic.ValidationError: 1 validation error for User`
- Data doesn't match model schema

**Cause**:
- Input data type mismatch
- Missing required fields
- Failed custom validators

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

# Handle validation errors
from pydantic import ValidationError

try:
    user = User(name="", email="invalid", age=200)
except ValidationError as e:
    print(e.errors())
    # [
    #     {'loc': ('name',), 'msg': 'ensure this value has at least 1 characters', ...},
    #     {'loc': ('email',), 'msg': 'Invalid email format', ...},
    #     {'loc': ('age',), 'msg': 'ensure this value is less than or equal to 150', ...},
    # ]
```

**Prevention**:
- Use Field constraints for validation
- Add custom validators for complex rules
- Handle ValidationError at API boundaries
- Return clear error messages to users
