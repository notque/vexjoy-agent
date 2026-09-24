# Writing Modern Python (3.12–3.14)

Load this file before you write or edit any Python code. Each rule fixes a failure measured in generated code that passed its tests but failed `ruff`, `mypy --strict`, packaging, or review. Examples use made-up domains (weather stations, parcels, telescopes, library loans, recipes, greenhouse sensors). Copy the pattern, never the names or wording.

Build everything the task asks for and nothing it doesn't: no extra endpoints, flags, dependencies, or files.

When you have no tools and must return files as text, every line inside a file block is code, comments, or data. Checks you would run become reading checks (section 14); you never narrate them. Measured: in 19 of 28 guided outputs across two rounds, a sentence about running checks ended up as the last line of a `.py` file, which is a syntax error.

## 1. Pick the Python version first

Read the version floor before writing code, and use only features at or below it.

```bash
grep -n 'requires-python' pyproject.toml   # the floor, e.g. ">=3.12"
python3 --version                          # the interpreter tests run on
```

- Existing project: its `requires-python` is the floor.
- New project with a stated runtime ("runs on 3.12"): set `requires-python = ">=3.12"` and stay at or below 3.12.
- New project with no stated runtime: use the local `python3 --version` as the floor. Current stable is 3.14 (3.15 is due October 2026).

| Feature | Version | Use |
|---|---|---|
| `asyncio.TaskGroup`, `asyncio.timeout()`, `except*`, `ExceptionGroup`, `typing.Self`, `datetime.UTC`, `tomllib`, `enum.StrEnum` | 3.11 | Default for new code |
| `class Box[T]:`, `def f[T](x: T) -> T:`, `type Alias = ...` (PEP 695), `typing.override`, `itertools.batched`, `Path.walk()`, tarfile `filter=` | 3.12 | Default when the floor is 3.12+ |
| `warnings.deprecated`, `copy.replace()`, `typing.TypeIs`, `typing.ReadOnly`, type-parameter defaults, `asyncio.Queue.shutdown()` | 3.13 | Only when the floor is 3.13+ |
| Deferred annotations (PEP 649), t-strings `t"..."`, `except A, B:` without brackets, `compression.zstd`, `Path.copy()`/`move()`, `uuid.uuid7()`, tarfile default filter `"data"` | 3.14 | Only when the floor is 3.14 |

Removed modules: `distutils`, `imp`, `asyncore`, `asynchat` (3.12); `cgi`, `telnetlib`, `crypt`, `pipes`, `imghdr` and the rest of PEP 594 (3.13). Deprecated: `datetime.utcnow()` and `utcfromtimestamp()` (3.12).

## 2. `pyproject.toml` that builds

Measured: 10 of 14 unguided projects declared a build backend that does not exist (`setuptools.backends._legacy:_Backend`, `hatchling.backends`), so `pip install .` failed. Copy one of these two backends exactly:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
# or: requires = ["setuptools>=77"] with build-backend = "setuptools.build_meta"
```

The rest of a new project's file (flat layout: package folder next to `pyproject.toml`, tests in `tests/`):

```toml
[project]
name = "shelfscan"
version = "0.1.0"
description = "Scan library shelves for overdue loans."
requires-python = ">=3.12"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=1.0", "mypy>=1.10", "ruff>=0.6"]

[tool.ruff]
line-length = 120
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP", "SIM", "RUF", "S", "ASYNC", "PTH", "PT", "C4", "DTZ", "RET", "FURB", "ANN"]

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "ANN"]

[tool.mypy]
strict = true
python_version = "3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"                          # only when pytest-asyncio is a dependency
asyncio_default_fixture_loop_scope = "function"
```

Keep `target-version` and `python_version` equal to the `requires-python` floor.

Write code the way `ruff format` would, or the format check fails. Measured: 6 of 14 round-1 outputs failed the format check, on line wrapping.

- A call, signature, or literal that fits on one line within `line-length` (120) stays on one line. Don't hand-wrap it at 80 or 88 columns; the formatter joins it back.
- When it doesn't fit, put one item per line and end with a trailing comma. The trailing comma tells the formatter to keep it exploded.

```python
# BAD at line-length 120: fits on one line, so ruff format joins it
rows = self._conn.execute(
    "SELECT id, book FROM loans WHERE id = ?", (loan_id,)
).fetchall()

# GOOD
rows = self._conn.execute("SELECT id, book FROM loans WHERE id = ?", (loan_id,)).fetchall()

# GOOD: too long for one line, so one item per line with a trailing comma
summary = summarize_loans(
    loans=active_loans,
    overdue_after=timedelta(days=21),
    include_labels=("reserve", "interlibrary"),
)
```

## 3. Typing

Measured: 6 of 14 unguided outputs imported `List`, `Optional`, `Sequence`, or `Callable` from `typing`; 7 of 14 failed `mypy --strict`, mostly on bare generics, `Any` returns, and unannotated special methods.

| Write | Never write |
|---|---|
| `list[int]`, `dict[str, float]`, `tuple[str, ...]` | `List[int]`, `Dict`, `Tuple` from `typing` |
| `X \| None`, `A \| B` | `Optional[X]`, `Union[A, B]` |
| `from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence, Awaitable` | the same names from `typing` |
| `class Shelf[T]:` and `def first[T](...)` (3.12+) | `T = TypeVar("T")` + `Generic[T]` |
| `type StationReadings = dict[str, list[float]]` (3.12+) | `StationReadings: TypeAlias = ...` |
| `dict[int, Recipe]`, `Shelf[str]` | bare `dict`, bare `Shelf` in any annotation |
| `datetime.UTC`, builtin `TimeoutError` | `timezone.utc`, `asyncio.TimeoutError` |

Rules:

- Annotate every parameter and return, including `-> None` on `__init__` and full `__exit__`/`__aexit__` signatures (section 6).
- `json.loads`, `response.json()`, `os.environ`, and untyped libraries return `Any`. Narrow with `isinstance` before returning a typed value; `mypy --strict` rejects `return data["x"]` from a function declared `-> float` (`no-any-return`).
- `# type: ignore[code]` only when `mypy` reports that exact code and no narrowing fixes it. An ignore that silences nothing fails strict mode (`unused-ignore`).
- `isinstance(x, int)` is true for `True`; exclude `bool` when you mean a number.

```python
class ReadingError(ValueError):
    """A station reading had the wrong shape."""


def parse_wind_speed(raw: str) -> float:
    """Parse `{"wind_kmh": 12.5}` and return the speed as a float."""
    data = json.loads(raw)  # Any
    if not isinstance(data, dict):
        raise ReadingError("expected a JSON object")
    speed = data.get("wind_kmh")
    if not isinstance(speed, int | float) or isinstance(speed, bool):
        raise ReadingError(f"wind_kmh must be a number, got {speed!r}")
    return float(speed)


class Shelf[T]:
    """A bounded shelf of items, oldest first."""

    def __init__(self, capacity: int) -> None:
        """Create an empty shelf that holds at most *capacity* items."""
        self._items: list[T] = []
        self._capacity = capacity
```

## 4. Docstrings on every public name

Measured: 14 of 14 unguided and 12 of 14 guided outputs left public functions, classes, or methods without docstrings. Every module, public class, public function, and public method (including `__enter__`/`__exit__` and FastAPI route handlers) gets a docstring. One line is enough when the signature says the rest; add Google-style `Args:`/`Returns:`/`Raises:` sections when behavior is not obvious. Private helpers (`_name`) may skip them.

## 5. Errors and validation

- Inside `except`, raise with `from err` so the cause survives (ruff `B904`). Measured: 6 hits in unguided outputs.
- Catch the narrowest exception that can happen: `FileNotFoundError`, `json.JSONDecodeError`, `httpx.TransportError`. `except Exception:` is only for a boundary that turns any failure into a result or log line, and never with a bare `pass`.
- Give a package one base exception and subclass it; callers catch the base.
- Never use `assert` for runtime checks in library code; `python -O` strips it (ruff `S101`). Use `if ...: raise`.
- `Decimal("NaN")` and `Decimal("Infinity")` parse without error. Measured: 4 of 4 outputs that parsed money accepted `NaN`. Check `is_finite()` after parsing.

```python
def parse_fee(text: str) -> Decimal:
    """Parse a fee such as ``"4.20"``; reject NaN, infinities, and junk."""
    try:
        fee = Decimal(text.strip())
    except InvalidOperation as err:
        raise ValueError(f"fee is not a number: {text!r}") from err
    if not fee.is_finite():
        raise ValueError(f"fee must be finite: {text!r}")
    return fee
```

- Money and exact quantities use `Decimal`, never `float`. Whole numbers are ints, fractions are strings (ruff `FURB157`), in tests too. Measured: 8 hits in one test file. Sum with `sum(values, start=Decimal(0))`.

```python
# BAD
Parcel(tracking_id="P-1", fee=Decimal("100"))
refund = Decimal("-5")
# GOOD
Parcel(tracking_id="P-1", fee=Decimal(100))
refund = Decimal(-5)
surcharge = Decimal("0.75")   # fractions stay strings; Decimal(0.75) would carry float error
```
- Records are `@dataclass(frozen=True, slots=True)`; use `NamedTuple` only when tuple unpacking is part of the API.

## 6. Resources

Every file, connection, client, and lock is opened in a `with`/`async with` block or owned by an object that is itself a context manager.

- Files: `path.open(encoding="utf-8")`, `path.read_text(encoding="utf-8")`; never bare `open()` (ruff `PTH123`) and never without `encoding`. CSV: `path.open(encoding="utf-8", newline="")`.
- Context manager signatures that pass `mypy --strict`:

```python
from types import TracebackType
from typing import Self


class LoanStore:
    def __enter__(self) -> Self:
        """Return the open store."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the connection."""
        self._conn.close()
```

For async, use `async def __aenter__(self) -> Self` and `async def __aexit__(...)` with the same parameters, and close the client there (`await self._client.aclose()` for httpx).

## 7. asyncio

Measured: 2 of 2 unguided concurrency outputs used `asyncio.gather` with hand-written cancel loops and `asyncio.wait_for`.

- Run a group of tasks with `async with asyncio.TaskGroup() as tg:`. It waits for every task, cancels the rest when one fails, and cancels all of them when the caller is cancelled. Don't hand-roll this with `gather` + `task.cancel()`.
- Per-operation deadlines use `async with asyncio.timeout(seconds):` and catch the builtin `TimeoutError`.
- Bound concurrency with `asyncio.Semaphore(n)` inside each task.
- Never swallow `asyncio.CancelledError`. Put cleanup in `finally`. If you must catch it, re-raise. Only the code that called `task.cancel()` may suppress it, around its own `await task`.
- Keep a reference to every `create_task` result (a TaskGroup does this). Never call `asyncio.get_event_loop()` or `ensure_future` in new code; use `asyncio.run(main())` at the entry point.
- Inject slow things (sleep, clock, transport) as parameters so tests run without real waiting.

```python
async def poll_stations(
    station_ids: list[str],
    read: Callable[[str], Awaitable[float]],
    *,
    limit: int,
    per_call_s: float,
) -> dict[str, float | str]:
    """Read every station, at most *limit* at a time; failures become messages."""
    gate = asyncio.Semaphore(limit)
    results: dict[str, float | str] = {}

    async def one(station_id: str) -> None:
        async with gate:
            try:
                async with asyncio.timeout(per_call_s):
                    results[station_id] = await read(station_id)
            except TimeoutError:
                results[station_id] = f"timeout after {per_call_s}s"
            except (OSError, ValueError) as err:
                results[station_id] = f"{type(err).__name__}: {err}"

    async with asyncio.TaskGroup() as tg:
        for sid in station_ids:
            tg.create_task(one(sid))
    return {sid: results[sid] for sid in station_ids}


async def stop(task: asyncio.Task[None]) -> None:
    """Cancel *task* and wait for it. Only the caller that cancelled may swallow the CancelledError."""
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
```

## 8. HTTP clients

- Pass an explicit timeout when you create the client: `httpx.AsyncClient(base_url=..., timeout=httpx.Timeout(10.0))`. `requests` has no default timeout at all.
- Create one client per object and close it in `__aexit__`/`close()`; never one client per request.
- Retry only what can succeed on retry: connection errors, timeouts, 429, and 5xx. Never retry other 4xx. Back off exponentially with jitter and a cap, and honor a numeric `Retry-After`.
- Tests use `httpx.MockTransport(handler)`, never the network.
- httpx does not follow redirects unless `follow_redirects=True`; `requests` does by default. Turn redirects off when the URL comes from a user (SSRF, see python-local-gates.md).

## 9. SQL with `sqlite3`

- Values go in `?` placeholders only. Never build SQL with f-strings, `%`, `+`, or `.format()`, even for "safe" values such as a string of `?` marks. For a variable-length `IN` list, pass one JSON array: `"... WHERE id IN (SELECT value FROM json_each(?))", (json.dumps(ids),)` (JSON functions are built in from SQLite 3.38; check `python3 -c 'import sqlite3; print(sqlite3.sqlite_version)'`, and on older builds join against a temporary table instead). Measured: an f-string `IN ({placeholders})` in 1 of 2 round-2 repositories.
- `LIKE` treats `%` and `_` as wildcards. Escape user text and add `ESCAPE '\'`.
- Run `PRAGMA foreign_keys = ON` on every new connection; SQLite defaults to off, so `ON DELETE CASCADE` silently does nothing.
- `with conn:` wraps a transaction: it commits on success and rolls back on an exception. It does not close the connection.
- Store timestamps as ISO strings from `datetime.now(UTC)`; the default sqlite3 datetime adapters are deprecated since 3.12.

```python
def like_pattern(text: str) -> str:
    r"""Return a LIKE pattern that matches *text* literally (use with ESCAPE '\')."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def borrow(self, book: str, labels: Iterable[str] = ()) -> int:
    """Record a loan and its labels in one transaction; return its id."""
    now = datetime.now(UTC)
    with self._conn:  # commits on success, rolls back on any exception
        cur = self._conn.execute("INSERT INTO loans (book, borrowed_at) VALUES (?, ?)", (book, now.isoformat()))
        loan_id = cur.lastrowid
        if loan_id is None:
            raise RuntimeError("insert returned no row id")
        self._conn.executemany(
            "INSERT INTO loan_labels (loan_id, label) VALUES (?, ?)", [(loan_id, lb) for lb in set(labels)]
        )
    return loan_id
```

Query with `"... WHERE book LIKE ? ESCAPE '\\' ORDER BY id", (like_pattern(text),)`.

## 10. HTTP services (FastAPI and Pydantic v2)

- Put validation in the model, not in the handler: `Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]`, `Field(ge=0)`. Measured: guided outputs re-checked lengths by hand after stripping.
- Reject unknown fields with `model_config = ConfigDict(extra="forbid")` on request models.
- Store model instances (`dict[int, Recipe]`), not raw `dict`s. Partial updates use `stored.model_copy(update=patch.model_dump(exclude_unset=True))`.
- Query bounds: `limit: Annotated[int, Query(ge=1, le=100)] = 20`.
- Keep all state inside the `create_app()` factory, never at module level, so two apps (and two tests) never share data.
- Declare codes on the decorator: `status_code=status.HTTP_201_CREATED`; a 204 handler returns `Response(status_code=204)`.
- Annotate each handler's return type with a response model; never return internal dicts with extra keys.

```python
def create_app() -> FastAPI:
    """Build an app with its own empty store."""
    app = FastAPI()
    recipes: dict[int, Recipe] = {}
    next_id = 1

    def lookup(recipe_id: int) -> Recipe:
        recipe = recipes.get(recipe_id)
        if recipe is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="recipe not found")
        return recipe

    @app.post("/recipes", status_code=status.HTTP_201_CREATED)
    def create(body: RecipeIn) -> Recipe:
        """Create a recipe."""
        nonlocal next_id
        recipe = Recipe(id=next_id, **body.model_dump())
        recipes[recipe.id] = recipe
        next_id += 1
        return recipe

    @app.patch("/recipes/{recipe_id}")
    def update(recipe_id: int, body: RecipePatch) -> Recipe:
        """Change the fields the client sent."""
        updated = lookup(recipe_id).model_copy(update=body.model_dump(exclude_unset=True))
        recipes[recipe_id] = updated
        return updated

    return app
```

## 11. CLIs and logging

- `def main(argv: Sequence[str] | None = None) -> int` parses, runs, and returns the exit code; `__main__.py` is `raise SystemExit(main())`.
- Exit codes: 0 success, 1 runtime failure (one line on stderr, no traceback), 2 usage error (argparse does this).
- Every module logs through `logger = logging.getLogger(__name__)`. Configure handlers only inside `main()`, never at import time.
- Logs and diagnostics go to stderr; program output goes to stdout.
- Structured logs: subclass `logging.Formatter`, mark `format` with `@override`, and emit one `json.dumps` object per line.

```python
class JsonLineFormatter(logging.Formatter):
    """Format each record as one JSON object per line."""

    @override
    def format(self, record: logging.LogRecord) -> str:
        payload = {"level": record.levelname, "logger": record.name, "message": record.getMessage()}
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload)
```

## 12. Tests

Test files meet the same `ruff` and `mypy` bar as package code. Measured: after round 1, every remaining lint failure was in `tests/`.

- All imports at the top of the test file, and each one used. Write the test functions first, then write the import block from the names that appear in them. Measured leftovers across 14 outputs: `json`, `asyncio`, `time`, `datetime`, `UTC`, `Callable`, `AsyncMock`, and the package's own result classes, all imported and never called. A type used only in an annotation still counts as used. Never import inside a test function: a local `from x import Name` makes `Name` local to the whole function, so an earlier use raises `UnboundLocalError`.
- Never `pytest.raises(Exception)` (ruff `B017`, `PT011`). Name the exact type the code raises and add `match=`: `pytest.raises(sqlite3.ProgrammingError, match="closed")`. To test rollback, make the failing input raise a known type (for example a non-string tag raises `TypeError` before insert) and assert that type.
- Keep a reference to every task a test creates: `task = asyncio.create_task(...)`, then `await` or cancel it (ruff `RUF006`).
- Test every edge case the task names (empty input, invalid values, duplicates, cancellation, timeouts), not just the happy path.
- `pytest.raises(ValueError, match="fee")`: always pass `match=` (ruff `PT011`).
- `@pytest.fixture` without parentheses (ruff `PT001`); fixtures that open resources `yield` inside a `with` block.
- Use `@pytest.mark.parametrize` for cases that share one body.
- Use `tmp_path` for files and databases, `capsys` for stdout/stderr, and `httpx.MockTransport` or a fake callable for network code. Never use the real network or `sleep` longer than about 0.1 s.
- Async tests: `async def test_...` with `asyncio_mode = "auto"` configured (section 2), or `asyncio.run(...)` inside a sync test.
- Prefix unused unpacked names with `_` (`_status, body = ...`, ruff `RUF059`).
- Annotate test functions `-> None` and fixtures with their return type so `mypy --strict` can check the tests too.
- Work out each expected value from the code you wrote, not from what the name suggests. Measured: a test expected `None` for a JSON `null` body that the client rejects as invalid.

## 13. Lint-clean by construction

Measured: 14 of 14 outputs in both arms failed a strict `ruff check`. The codes seen most, with the fix:

| Code | Fix |
|---|---|
| `I001` | Imports in three groups (stdlib, third-party, local), each sorted, one blank line between groups |
| `F401` | Delete unused imports; re-exports go in a sorted `__all__` (`RUF022`) |
| `UP035`, `UP006`, `UP007` | Section 3 table |
| `UP017`, `UP041` | `datetime.UTC`; builtin `TimeoutError` |
| `B904` | `raise ... from err` inside `except` |
| `FURB157` | `Decimal(0)`, `Decimal(-5)`, not `Decimal("0")` or `Decimal("-5")`, in tests too; keep strings for fractions |
| `PT011`, `B017`, `PT001` | Exact exception type plus `match=` on `pytest.raises`, never `Exception`; `@pytest.fixture` without `()` |
| `RUF059` | `_`-prefix unused unpacked variables |
| `S101` | `if ...: raise` instead of `assert` outside tests |
| `PTH123` | `path.open(...)` instead of `open(path)` |
| `ANN204` | `-> None` on `__init__` and other special methods |
| `E402`, `F821` | Imports at the top of the file, never inside a function or after code |
| `RUF006` | Keep the `asyncio.create_task` result in a variable |

## 14. Pre-handoff checklist

With a shell, run these from the project root and fix every finding before you report done. Show the real output.

```bash
ruff check --fix . && ruff format .
ruff check . && ruff format --check .
mypy --strict <package>          # or: mypy . with [tool.mypy] strict = true
python -m pytest -q
python -m pip wheel --no-deps -w /tmp/wheel-check .   # proves the build backend exists
```

With no shell, skip the commands and don't mention them. The last line of your last file is code. Answer each line below yes by reading your code:

- [ ] `requires-python`, ruff `target-version`, and mypy `python_version` agree, and no feature is newer than the floor (section 1).
- [ ] `build-backend` is exactly `hatchling.build` or `setuptools.build_meta`.
- [ ] No `typing.List/Dict/Optional/Union/Callable/Sequence`, no bare generic in any annotation, no `TypeVar` + `Generic` on 3.12+.
- [ ] Every public module, class, function, and method has a docstring.
- [ ] Every value from `json`, headers, or environment is narrowed before it is returned as a typed value.
- [ ] Every `raise` inside `except` has `from err`; no `assert` outside tests; no `except Exception: pass`.
- [ ] Decimal inputs are checked with `is_finite()`.
- [ ] Every file, connection, and client is closed by a `with` block or a context manager's exit.
- [ ] Async code uses `TaskGroup` and `asyncio.timeout`, never swallows `CancelledError`, never calls `get_event_loop`.
- [ ] SQL uses `?` placeholders only; `LIKE` input is escaped; `PRAGMA foreign_keys = ON` is set.
- [ ] In every file, including tests: imports at the top, grouped, sorted, and each one used.
- [ ] Nothing is wrapped that fits in 120 columns; every wrapped call ends with a trailing comma.
- [ ] Tests cover each edge case in the task, name the exact exception with `match=` (never `Exception`), and never touch the network.
- [ ] The files contain only code: no summary or prose after the last line of the last file.
