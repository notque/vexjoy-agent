# Architecture Reviewer — Smell Baseline

Adapted from [mattpocock/skills#394](https://github.com/mattpocock/skills/pull/394) (Martin Fowler's "Bad Smells in Code", *Refactoring* ch.3) with three vexjoy modifications established by A/B test:

1. **Named language-idiom counter-examples come first** (per-language Go/TS/Python list of patterns that are NOT smells, even though the smell taxonomy might suggest they are).
2. **Severity cap.** Baseline smells default to LOW, may rise to MEDIUM if compounded with a real defect, **never** HIGH/CRITICAL from a smell alone.
3. **Lower-signal OO smells demoted** with language caveats (Middle Man, Refused Bequest, Feature Envy, Message Chains).

A/B context: the verbatim PR #394 baseline produced 7 trap false positives and 24 invented findings across 6 setups; this modified version produced 3 trap false positives and 11 invented findings on the same setups (B′ won 6/6). Setup-level results: `/tmp/ab394/` artifacts; full transcript at `tasks/w609k70v1.output`.

---

## The brief (pass verbatim to the Architecture reviewer)

> Smell baseline (always-on, language-idiom-overridden). On top of your language's idiomatic standards, carry this curated Fowler-smell baseline. It applies even when nothing else flags the diff.
>
> **Two binding rules — read these BEFORE applying any smell:**
>
> ### Rule 1: Language idioms override. Always check the counter-examples first.
>
> A smell label is **suppressed** when the code matches an idiomatic pattern. The following counter-examples are NOT smells — flagging them is a review defect:
>
> **Go:**
> - `switch v := x.(type)` (type switch on an interface) — NOT *Repeated Switches*. This is the idiomatic Go dispatch mechanism. Suppress.
> - Single interface in a package with one current implementation — NOT *Speculative Generality* if there's a test double, a mock, or a second impl is announced. Otherwise flag at LOW.
> - `default:` case that logs/skips on unknown type — NOT a "silent failure." This is the standard defensive `%T` pattern.
>
> **TypeScript:**
> - `switch` on a discriminated-union `kind` field — NOT *Repeated Switches*. This is idiomatic TS exhaustiveness. Suppress.
> - Chained `.map().filter().reduce()` on arrays — NOT *Message Chains*. This is functional composition, not navigation. Suppress.
> - `string` literal union types (`'card' | 'bank' | 'wallet'`) — NOT *Primitive Obsession*. The compiler enforces the domain. Suppress.
>
> **Python:**
> - `if/elif` on enum members at a single call site — NOT *Repeated Switches*. The smell needs the same cascade **at two or more sites**. Suppress when there's exactly one site.
> - ABCs (`abc.ABC`) with one concrete implementation and one current caller — NOT *Speculative Generality*. Suppress.
> - `dict[str, Any]` for genuinely heterogeneous payloads (event buses, plugin metadata) — NOT *Primitive Obsession* by default. Flag only at LOW if a clearer type is obvious.
>
> When in doubt about whether the code matches an idiom, **err toward suppression and don't flag the smell at all**. A missed smell is recoverable; a false-positive smell teaches the reader to ignore the reviewer.
>
> ### Rule 2: Severity cap. Baseline smells default to LOW. They may rise to MEDIUM only when they compound with an idiomatic or correctness violation. Never HIGH or CRITICAL from a smell alone.
>
> A real bug found while reading a smelly area gets HIGH/CRITICAL on its own merits as a normal Architecture finding — not as a smell.
>
> ---
>
> ## The 12 smells (each: *what it is* → *how to fix*)
>
> **High-signal (apply first):**
>
> - **Mysterious Name** — a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
> - **Duplicated Code** — the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
> - **Data Clumps** — the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
> - **Primitive Obsession** — a primitive standing in for a domain concept that deserves its own type. → give the concept its own small type. *(See Rule 1 for TS union-type and Python `dict[str, Any]` exceptions.)*
> - **Repeated Switches** — the same `switch`/`if`-cascade on the same type recurs at **two or more sites** in the diff. → replace with polymorphism, or one map both sites share. *(See Rule 1 for Go type-switch, TS discriminated-union, and Python single-site exceptions.)*
> - **Speculative Generality** — abstraction, parameters, or hooks added for needs the spec doesn't have **and no current caller uses**. → delete it; inline back until a real need shows.
> - **Shotgun Surgery** — one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
> - **Divergent Change** — one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
>
> **Lower-signal (apply only when very confident; OO-heavy):**
>
> - **Feature Envy** — a method that reaches into another object's data more than its own. → move the method onto the data it envies.
> - **Message Chains** — long `a.b.c.d` *property navigation* through nested data (NOT method chains on collections). → hide the walk behind one method on the first object.
> - **Middle Man** — a class or function that mostly just delegates onward with no added behavior. → cut it, call the real target direct. *(Lower priority in Go: thin wrappers for interface satisfaction are idiomatic.)*
> - **Refused Bequest** — a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition. *(Lower priority in Go: no inheritance.)*
>
> ---
>
> ## Output format (for Architecture findings)
>
> - `[Architecture] <one-line description> — file:line`
> - If a baseline smell, prefix with the label: `[Architecture] possible <Smell Name>: <one-line> — file:line`
> - Severity: CRITICAL / HIGH / MEDIUM / LOW (baseline smells default to LOW, MEDIUM if compounded — never HIGH/CRITICAL from a smell alone)
>
> ## Rules
>
> - Read-only — observe and report, never modify.
> - Skip anything tooling (linter, formatter, type-checker) already enforces.
> - Distinguish hard violations from judgement calls. Baseline smells are always judgement calls.
> - Cite `file:line` for every finding.
>
> **Re-read Rule 1 before reporting any smell-labeled finding.**

---

## Maintenance

When adding a new language-idiom counter-example: state the exact pattern, name the smell it would have triggered, and end with "Suppress." (or, for borderline cases, "Flag at LOW only when..."). Vague guidance ("be careful with…") is not a suppression rule and will not change the model's behavior — the A/B showed that named, code-shaped counter-examples did the work.
