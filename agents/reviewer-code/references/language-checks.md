# Language-Specific Checks Catalog

Check catalogs for Go, Python, and TypeScript. Load after detecting language from file extensions.

## Go (when reviewing .go files)

**Modern stdlib (Go 1.21+, Go 1.22+)**:
- `slices.SortFunc` instead of `sort.Slice`
- `slices.Contains` instead of manual loop search
- `strings.CutPrefix`/`strings.CutSuffix` instead of `HasPrefix`+`TrimPrefix`
- `min`/`max` builtins instead of custom helpers (Go 1.21+)
- `for range N` loop syntax (Go 1.22+)
- Flag `v := v` inside `for range` loops — unnecessary since Go 1.22, LLM tell
- Flag `go func(x Type) { ... }(x)` capture patterns — per-iteration variables since Go 1.22
- `maps.Clone`, `maps.Keys` instead of manual map operations
- `log/slog` instead of `log.Printf` for structured logging

**Idioms**:
- Error wrapping `%w` with `errors.Is`/`errors.As`
- Receiver type consistency (all pointer or all value)
- Package naming: lowercase, single-word, no underscores
- Unexported types with exported constructors (`NewFoo()`)
- Blank identifier only with explicit justification

**Concurrency**:
- Goroutine leaks: goroutines without shutdown path
- Context cancellation: respect `context.Context`
- Mutex per resource, not per struct
- `sync.Once` for initialization, not `init()` with flags
- Channel direction in function signatures

**Resources**:
- `defer Close()` after error check on open call
- Connection pool sharing across requests
- `http.DefaultClient` reuse vs new clients
- File descriptor limits

**Anti-patterns**:
- Premature interface abstraction (one implementation)
- Over-engineered error types for simple errors
- Unnecessary channels when mutex suffices
- `init()` for non-trivial work (I/O, network)
- Returning concrete types but accepting interfaces at boundaries
- `MockXxx` types in production (non-test) files
- Separate `*sql.DB` pools when shared pool should be injected

**LLM tells**:
- Functional options on 2-3 field types (struct literal suffices)
- Table-driven tests for single-case scenarios
- Excessive interface segregation (one-method interfaces for everything)
- Config validation with reflection when `if` works
- Overly verbose error messages repeating function name
- Builder pattern for few-field structs
- `v := v` loop variable shadowing in Go 1.22+
- `defer rows.Close()` without checking `rows.Err()` after loop
- Verbose error wrapping when error already has good context

## Python (when reviewing .py files)

**Modern Python (3.10+, 3.11+, 3.12+)**:
- Walrus operator `:=` in conditions
- `match` for structural pattern matching (3.10+)
- `type` statement for type aliases (3.12+)
- `tomllib` for TOML parsing (3.11+)
- `TaskGroup` for structured concurrency (3.11+)
- `ExceptionGroup` and `except*` (3.11+)
- Generic syntax `def foo[T](x: T)` (3.12+)

**Idioms**:
- Comprehensions over `map`/`filter` with lambdas
- Context managers (`with`) for resources
- Generators for large dataset processing
- `pathlib.Path` over `os.path`
- `collections.defaultdict` over manual key checks
- F-strings over `format()` or `%`
- `dataclasses`/`attrs` over manual `__init__`

**Concurrency**:
- `asyncio`: proper `async with`, `async for`
- `TaskGroup` over `gather` with manual cancellation
- Cleanup in async context managers
- Thread safety mixing sync and async

**Resources**:
- Context managers for file handles, connections, locks
- `atexit` for global cleanup
- Signal handling for graceful shutdown
- `contextlib.suppress` over empty except

**Anti-patterns**:
- Mutable default arguments (`def foo(items=[])`)
- Bare `except:` or `except Exception:` without re-raise
- `import *`
- Global mutable state
- Monkey patching in production
- String concatenation in loops (use `join`)

**LLM tells**:
- Verbose type hints on obvious types (`x: int = 5`)
- Unnecessary docstrings on self-documenting functions
- Java-style getters/setters instead of properties
- Abstract base classes for single implementations
- `typing.Optional` when `| None` exists (3.10+)
- Over-engineered class hierarchies for simple transforms

## TypeScript (when reviewing .ts/.tsx files)

**Modern TypeScript (5.0+, 5.2+)**:
- `satisfies` for type checking without widening
- `const` type parameters for literal inference
- `using` declarations for resources (5.2+)
- Template literal types for string patterns
- `NoInfer<T>` utility type (5.4+)

**Idioms**:
- Discriminated unions over type casting
- `Zod` or similar for runtime validation
- Generic constraints (`extends`) over `any`
- Mapped types and conditional types
- `as const` for literal inference

**React (when reviewing .tsx)**:
- React 19: no `forwardRef` (ref is regular prop), `useActionState`, `useOptimistic`
- Proper hook dependency arrays (exhaustive deps)
- `memo` only with measured performance justification
- Server Components vs Client Components
- Framework data loading instead of `useEffect` for fetching

**Anti-patterns**:
- `any` overuse instead of `unknown`
- Type assertions (`as`) over type narrowing
- Barrel file bloat causing circular deps
- Circular dependencies
- Enum overuse when union types suffice
- `namespace` in modern code

**LLM tells**:
- Abstract factory patterns for simple object creation
- Class-based components in modern React
- Redundant null checks when strict mode already narrows
- Over-engineered DI frameworks
- Excessive abstraction layers (repository wrapping simple fetch)
- Generic utility types reimplementing built-ins
