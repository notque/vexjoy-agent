# Architecture Deepening Vocabulary

> **Scope**: Shared terms for discussing module depth, shallowness, and deepening opportunities. These terms are used throughout the architecture-deepening skill and should be used consistently in all findings and design conversations.
> **Source**: Rebuilt from Ousterhout's "A Philosophy of Software Design" principles, adapted to this toolkit's vocabulary.

---

## Core Terms

### Module

A unit of code with an interface and an implementation. The interface is what
callers see and use. The implementation is what happens behind the interface.
A module can be a Go package, a Python class, a TypeScript module, a Rust
crate, or any grouping where there is a clear boundary between "what you call"
and "how it works."

The size of a module does not determine its quality. A 50-line module with a
clean interface is deeper than a 500-line module where callers must understand
the implementation.

### Interface

The contract a module presents to its callers: function signatures, types,
configuration options, error types, and documented behavior. The interface
includes everything a caller must know to use the module correctly.

A good interface is smaller than its implementation. It hides decisions that
callers do not need to make. A bad interface forces callers to understand and
manage implementation details.

### Depth

The ratio of functionality provided to interface complexity. A deep module
provides significant functionality behind a simple interface. A shallow module
provides little functionality relative to its interface complexity.

```
Deep module:           Shallow module:

+------------------+   +------------------+
|    interface     |   |    interface     |
+------------------+   |                  |
|                  |   |                  |
|                  |   +------------------+
|  implementation  |   |  implementation  |
|                  |   +------------------+
|                  |
+------------------+
```

Depth is not about line count. A module with 10 functions and 1,000 lines of
implementation is deep if each function hides significant complexity. A module
with 10 functions and 50 lines of implementation is shallow -- the interface
is almost as complex as the implementation, and callers gain little by using
the module instead of doing the work directly.

### Shallowness Signals

A module is shallow when one or more of these are true:

1. **Pass-through methods**: Functions that do little more than delegate to
   another function with the same or similar signature. The caller could have
   called the underlying function directly.

2. **Configuration explosion**: The module requires extensive setup or
   configuration that mirrors its internal structure. Callers must understand
   the implementation to configure it correctly.

3. **Leaking abstractions**: Error messages, types, or behaviors that expose
   implementation details. Callers must catch implementation-specific errors
   or handle internal state transitions.

4. **Forced coordination**: Multiple modules must be called in a specific
   sequence to accomplish a single logical operation. The sequencing knowledge
   belongs behind an interface.

5. **Documentation that describes internals**: If the public documentation
   must explain how the module works (not just how to use it) for callers to
   use it correctly, the interface is too thin.

---

## Structural Terms

### Seam

A natural boundary in the code where responsibility could be redistributed.
Seams are where deepening happens -- they are the lines along which you can
move implementation details behind an interface.

**Data seam**: Where data is transformed between representations. If callers
must understand the internal data format to construct inputs or interpret
outputs, the seam is exposed. Deepening means the module handles the
transformation internally.

**Protocol seam**: Where a communication protocol (HTTP, gRPC, database wire
protocol) is visible to callers. If callers must construct protocol-specific
messages or handle protocol-specific errors, the seam is exposed. Deepening
means the module handles protocol details internally.

**Temporal seam**: Where ordering or timing requirements are visible to
callers. If callers must call functions in a specific order, manage lifecycle
states, or coordinate timing between operations, the seam is exposed.
Deepening means the module manages sequencing internally.

**Error seam**: Where implementation-specific failure modes are visible to
callers. If callers must distinguish between internal error types to decide
what to do, the seam is exposed. Deepening means the module translates
internal errors into caller-meaningful categories.

### Leverage

How many callers benefit from deepening a module. A module called from 20
places has higher leverage than one called from 2 -- the same interface
improvement removes complexity in more locations.

Leverage is not just caller count. A module used by 3 callers in
safety-critical paths has higher effective leverage than one used by 20 callers
in logging paths. Weight by impact, not just frequency.

### Locality

The principle that related code should be close together. Deepening should
increase locality: if a change to behavior X requires touching files A, B,
and C today, a good deepening puts A, B, and C behind a single interface so
future changes to X touch one place.

A deepening that decreases locality -- scattering related logic across more
modules -- is likely moving complexity sideways rather than absorbing it.

### Deletion Test

The most concrete measure of a deepening's value: after the interface change,
how much caller code can be deleted?

Deleted code is the strongest signal because it represents complexity that
callers were forced to manage that now lives behind the interface. A deepening
that enables no caller deletion may still be valuable (better naming, clearer
error messages), but the highest-value deepenings always delete caller code.

Run the deletion test for every proposed interface change:

1. Write the new interface signature
2. For each caller, identify lines that become unnecessary
3. Count the total deletable lines across all callers
4. If the count is zero, question whether this is a deepening or a rename

---

## Evaluation Framework

### Depth Score

Rate each module on a 3-level scale:

| Score | Meaning | Action |
|-------|---------|--------|
| **HIGH** | Interface nearly as complex as implementation. Multiple shallowness signals. Many callers affected. | Top candidate for deepening |
| **MEDIUM** | Some leaking abstractions or pass-through methods. Moderate caller impact. | Worth exploring if high-leverage candidates are done |
| **LOW** | Minor interface improvements possible. Few callers affected. | Note for future; not worth dedicated deepening effort |

### Deepening Priority Matrix

| Factor | Weight | Why |
|--------|--------|-----|
| Caller count (leverage) | High | More callers = more deleted complexity |
| Shallowness severity | High | Severe shallowness = more improvement possible |
| Change risk | Medium | High-risk changes need more testing investment |
| Contributor friction | Medium | Frequently confused modules are high-priority |
| Deletion test result | High | More deletable caller code = higher concrete value |

Prioritize candidates that score high on leverage AND shallowness severity.
A module with many callers but mild shallowness is lower priority than one
with fewer callers but severe shallowness -- the latter causes more pain per
interaction.
