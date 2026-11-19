---
description: "General Rust development: features, debugging, code review, performance. Rust 2024 edition (1.85+) rules, rust-analyzer order, five-phase workflow."
type: reference
---

# General Rust Development

Rules and workflow for idiomatic, production-ready Rust (Rust 2024 edition,
Rust 1.85+). Covers features, debugging, code review, and performance.

Not for: "rust" as an adjective (rust-colored, rusty); C++ ownership patterns;
WebAssembly-only tasks without Rust source.

## Hard rules

- **Write modern Rust.** Before you write or edit Rust code, load
  [rust-modern-code.md](rust-general/rust-modern-code.md) and follow it. Code
  that builds and passes tests still fails review when it uses the old idioms
  listed there. The rules most often missed:
  - A `//!` module-level doc comment in every module file and a doc comment on
    every public item, starting with a noun or verb phrase (not repeating the
    item name mechanically).
  - `main` delegates to `run() -> anyhow::Result<()>` (or equivalent); errors
    propagate via `?` rather than `.unwrap()` in `main`.
  - Tests: `#[tokio::test]` for async; never `std::thread::sleep` in async
    tests. Use `tokio::time::pause()` + `tokio::time::advance(d)`.
  - Prefer `tokio::spawn` with a tracked `JoinHandle` over fire-and-forget
    spawns.
  - `thiserror` for library errors; `anyhow` for application errors. Never
    string-match on `anyhow` messages.
  - Use the `uuid` crate (`Uuid::new_v4()` / `Uuid::now_v7()`), never
    hand-rolled UUIDs.
  - `Iterator` combinators over manual loops when intent is clear; `rayon` for
    data-parallel workloads.
  - Never `.unwrap()` in library code; never `.expect()` without a message;
    never `.clone()` only to silence the borrow checker.
- **Format with `cargo fmt`.** Non-negotiable: run it on every edited `.rs` file.
- **After a clean `cargo build`, run `cargo clippy`** to catch subtle issues.
- **Errors carry useful context.** Return `Err(e)` unchanged when it is already
  clear. Add context with `.context("...")` (`anyhow`) or a wrapping error
  variant (`thiserror`). Propagate with `?`; `.unwrap()` only in tests where the
  invariant is obvious.
- **`&str`, not `String`, for parameters.** Accept `impl AsRef<str>` or `&str` at
  API boundaries unless ownership is required.
- **Pre-handoff checklist.** Before you report done, run the command sequence
  and tick the checklist in rust-modern-code.md section 12. Without tools, check
  the code against each checklist line.
- **Show complete command output.** Paste actual `cargo test` output instead of
  "tests pass".
- **Table-driven tests** with `rstest` parametrize for data-driven cases; keep
  distinct scenarios in separate tests when that is clearer.
- **Edition-aware code.** Detect the edition from `Cargo.toml` and use only
  features available in it. The 2024 edition enables `gen` blocks and tighter
  `let` chains. `async fn` in traits stabilized in 1.75 (independent of
  edition).
- **Verify crate behavior from source.** When a change depends on specific crate
  behavior (retry logic, connection lifecycle, error types), read the crate
  source in `~/.cargo/registry/src/` or use `cargo doc --open`. Never reason
  from protocol-level knowledge alone. The question is not "how does PostgreSQL
  work?" but "how does `sqlx` v0.8 implement this method?"
- **rust-analyzer first.** Use LSP tools in this order when available:
  1. Confirm the workspace compiles before any edit, to set a baseline.
  2. Use go-to-definition / find-references before modifying any public item.
  3. Run `cargo check` after each edit to surface type errors early.
  4. Run `cargo clippy --workspace --all-targets -- -D warnings` after
     `cargo check` passes.

  Fall back to grep / Glob only when rust-analyzer is not configured.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| cargo check, cargo clippy, rust-analyzer, crate source, stale binary, dead code, refactoring prep | [rust-verification-workflow.md](rust-general/rust-verification-workflow.md) | rust-analyzer ordering, crate-source verification, rebuilt-binary check, dead-code analysis with cargo-udeps |
| Any task that writes or edits Rust code: new crate, handler, CLI, worker, iterator, repository, tests | [rust-modern-code.md](rust-general/rust-modern-code.md) | Measured failure patterns with before/after code: doc comments, errors, lifetimes, async, bounded concurrency, HTTP serve/shutdown, UUID, CLI flags, iterators, test patterns, database access, pre-handoff checklist |
| unwrap, expect, clone, lifetime, 2021 vs 2024, impl Trait, async fn in trait, let-else, gen blocks, MSRV errors | [rust-version-idioms.md](rust-general/rust-version-idioms.md) | Rust 1.56–1.85 idiom replacement table, hard gates with fixes, error-message-to-version map |
| Hard-gate framework | [forbidden-patterns-template.md](../../../shared-patterns/forbidden-patterns-template.md) | Shared gate format |

## Workflow

Follow these phases for every Rust task. Skipping phases is the dominant cause
of regressions and death-loop debugging.

### Phase 1: Discover

Run `cargo metadata --no-deps --format-version 1` first to get the workspace
layout, edition, and MSRV. Read `Cargo.toml` for every affected crate before
editing, because feature flags and edition-specific syntax differ per crate.

**Gate:** workspace structure known; edition and MSRV identified.

### Phase 2: Plan

Check `Cargo.toml` for `edition` and `rust-version` (MSRV): `let-else` on a
project targeting Rust 1.56 breaks the build, and `gen` blocks on a project
targeting 1.82 fail with a syntax error. Identify the failing test or
compilation error before implementing.

**Gate:** reproduction steps or failing test captured.

### Phase 3: Implement

Apply minimum-viable edits; over-engineering beyond the request is the most
common Rust review rejection. Propagate errors with `?`, add `.context("...")`
when a message loses information crossing a boundary, and return typed errors
from library functions with `thiserror`. Never `.unwrap()` in library code;
reserve it for tests with an obvious invariant.

**Gate:** `cargo check --workspace` returns zero errors for edited files.

### Phase 4: Verify

- Run `cargo fmt --check` on every edited file; unformatted Rust fails CI before
  any logic review runs.
- Run `cargo clippy --workspace --all-targets -- -D warnings` and fix all
  findings; clippy catches subtle bugs of the same class as `go vet`.
- Run `cargo test --workspace` and paste the actual output.
- For cleanup, review, or refactoring tasks, run
  `cargo +nightly udeps --workspace` to find unused dependencies (needs
  nightly; `cargo machete` is the stable alternative). See
  [rust-verification-workflow.md](rust-general/rust-verification-workflow.md).

**Render-time fixes need render-time verification.** Bugs that show at output
render time (formatting, template output, tracing output) are not caught by
compile + `cargo test`. Build a small standalone reproducer under `/tmp` with
realistic fake data, run it, and compare before/after output. Use a local
`Cargo.toml` that points to the workspace crate rather than copying source.

**Rebuilt binary check.** When testing a fix to a CLI binary, confirm the binary
matches the fix. Compare the modification time of `target/debug/<bin>` against
the fix time, or compare the version from `cargo pkgid` against the binary's
`--version`. A stale binary silently passes tests against the old code path.

**Gate:** `cargo test --workspace` output shown in full;
`cargo clippy --workspace -- -D warnings` clean.

### Phase 5: Report

Report exit status with real command output. No "should work": either the gates
passed or they didn't.

**Gate:** the completion report includes command output, not summaries.

## Preferred patterns

See [rust-version-idioms.md](rust-general/rust-version-idioms.md) for the modern
idiom replacement table, hard gates with fixes, and the error-message-to-version
map.

## Error handling

Standard Rust failure modes (borrow checker violations, lifetime errors, async
executor starvation, trait bound mismatches) are base-model knowledge: diagnose
with `cargo check`, `cargo clippy`, and rust-analyzer. Verification workflows
and rust-analyzer fallback guidance live in
[rust-verification-workflow.md](rust-general/rust-verification-workflow.md).
