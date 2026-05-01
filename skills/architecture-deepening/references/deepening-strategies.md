# Deepening Strategies

> **Scope**: Dependency categorization, safe deepening execution patterns, and testing strategies. Loaded during Phase 2-3 when planning how to implement a deepening safely.

---

## Dependency Categorization

Before deepening a module, categorize its dependencies to understand what moves
behind the interface and what risks that introduces.

### Dependency Types

| Type | Description | Risk When Absorbed |
|------|-------------|-------------------|
| **Pure logic** | Computation with no side effects. String formatting, math, data transformation. | Low. Easy to test, no external state. |
| **Configuration** | Values that control behavior. Timeouts, retry counts, feature flags. | Low-Medium. Sensible defaults reduce risk. Test default and override paths. |
| **State management** | Lifecycle, initialization order, connection pools, caches. | Medium. Sequencing bugs become internal rather than caller-visible. Test lifecycle edge cases. |
| **I/O** | Network calls, file operations, database queries. | Medium-High. Failures are now internal. Module must handle retries, timeouts, and fallbacks that callers previously managed. |
| **Cross-cutting** | Auth, logging, metrics, tracing. | Medium. Absorbing these can create hidden coupling. Ensure the module does not make decisions callers should make (e.g., which metrics to emit). |

### Absorption Safety Rule

Absorb dependencies in order of risk: pure logic first, then configuration,
then state management, then I/O. Each level adds failure modes the module must
handle. Do not absorb I/O dependencies until the module's error handling for
lower-risk dependencies is solid.

---

## Incremental Migration Strategies

Deepening should never be an all-or-nothing migration. Callers adopt the new
interface incrementally.

### Strategy 1: New Function Alongside Old

Add the deep interface as a new function. Keep the shallow function available
but mark it for eventual removal.

```go
// Existing shallow interface -- still works
func NewClient(config Config) *Client { ... }

// New deep interface -- callers migrate to this
func Connect(endpoint string, opts ...Option) *Client { ... }
```

**When to use**: When the new interface has a different signature. Callers
migrate one at a time. Remove the old function when the last caller migrates.

**Risk**: Two interfaces coexist indefinitely. Set a deadline or automated
reminder to complete migration.

### Strategy 2: Default Parameters

Change the existing function to accept optional parameters, making the common
case simpler without breaking existing callers.

```python
# Before: all callers must specify format
def export(data, format, compression=None, encoding='utf-8'):

# After: format defaults to the common case
def export(data, format='json', compression=None, encoding='utf-8'):
```

**When to use**: When the language supports default parameters and the common
case is clear from caller analysis.

**Risk**: Changing a required parameter to optional can mask bugs where callers
intended to pass a specific value. Review each caller during migration.

### Strategy 3: Wrapper Module

Create a new module that wraps the shallow one, providing the deep interface.
Internal callers migrate to the wrapper. The shallow module becomes internal.

```
callers --> deep_wrapper --> shallow_module (internal)
```

**When to use**: When the shallow module is stable and well-tested but its
interface leaks. The wrapper absorbs complexity without risking the tested
implementation.

**Risk**: The wrapper can become a pass-through layer if it does not absorb
meaningful complexity. Apply the deletion test to the wrapper itself -- if
callers of the wrapper have the same complexity as callers of the original,
the wrapper is not earning its place.

---

## Testing Strategies for Deepened Modules

Deepened modules absorb complexity that was previously in callers. That
complexity still needs testing -- it just moves from caller tests to module
tests.

### Test Migration Checklist

When deepening a module:

1. **Identify caller tests that test absorbed behavior.** These tests belong
   in the module's test suite now, not in the caller's.

2. **Add module-level tests for absorbed edge cases.** Callers may have been
   handling edge cases individually. The module must handle all of them.

3. **Simplify caller tests.** After migration, caller tests should test caller
   logic only, not the module's internal behavior. If caller tests still set
   up extensive mocks of the module's internals, the interface is still leaky.

4. **Test the escape hatch.** If the deep interface provides options for
   unusual callers, test that the override mechanism works correctly.

### Testing Absorbed Sequencing

When a module absorbs lifecycle management (init, migrate, ready, close):

- Test the happy path: create, use, close
- Test early close: close before ready
- Test double close: close twice
- Test use-after-close: call methods after close
- Test concurrent lifecycle: multiple goroutines/threads calling lifecycle
  methods simultaneously

These tests previously did not exist because callers managed the sequence. Now
that the module owns sequencing, it must handle misuse gracefully.

### Testing Absorbed Error Translation

When a module absorbs error translation:

- Test that each internal error type maps to the correct public error
- Test that error context is preserved (callers can still diagnose issues)
- Test that new internal error types (added in future) do not leak as raw errors
- Test that wrapped errors support `errors.Is` and `errors.As` correctly

### Testing Absorbed Configuration

When a module absorbs configuration defaults:

- Test the default path: create with no options, verify sensible behavior
- Test each override: create with one option changed, verify it takes effect
- Test option composition: create with multiple options, verify they compose
- Test invalid options: verify clear error messages for bad configuration

---

## Measuring Deepening Success

After a deepening ships, measure these outcomes:

| Metric | How to Measure | Good Signal |
|--------|---------------|-------------|
| Caller code reduction | `git diff --stat` on caller files | Net line deletion across callers |
| Caller test simplification | Test file diff | Fewer mocks, shorter setup, simpler assertions |
| New contributor ease | Time for a new contributor to write a caller | Shorter onboarding, fewer "how do I use this?" questions |
| Bug locality | Where bugs are filed after the change | Bugs move from callers to the module (consolidated, not scattered) |
| API question frequency | Support channel / issue tracker | Fewer questions about how to use the module |

A deepening that increases total code or test volume without reducing caller
complexity has moved complexity sideways rather than absorbing it. Revisit the
interface design.

---

## When Not to Deepen

Deepening is not always the right move. Do not deepen when:

1. **The shallowness is intentional.** Some modules expose internals
   deliberately for performance, debugging, or extensibility. Ask the
   maintainer before assuming shallowness is a defect.

2. **The module is deprecated.** Investing in interface design for a module
   that will be replaced is wasted effort.

3. **Callers are diverse by design.** If each caller genuinely needs different
   behavior and the "common case" is an illusion, the shallow interface may be
   correct. Deepening would hide the diversity behind false simplicity.

4. **The migration cost exceeds the benefit.** If the deletion test shows
   minimal caller simplification but the migration touches many files, the
   disruption is not worth the gain.

5. **The module boundary is wrong.** Sometimes shallowness is a symptom of
   the wrong abstraction boundary. The fix is not to deepen the current module
   but to redraw the boundary -- split, merge, or restructure modules. If
   this is the case, document it as a finding and suggest a boundary redesign
   rather than an interface deepening.
