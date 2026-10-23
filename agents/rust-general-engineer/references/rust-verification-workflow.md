# Rust Verification Workflow

Toolkit-specific verification: rust-analyzer ordering, crate-source checks, rebuilt-binary and render-time verification, dead-code analysis. Load for any Rust edit, review, or cleanup task.

## rust-analyzer Tool Order

Available when rust-analyzer is configured in the editor or via LSP.

| Tool | When (mandatory ordering) |
|------|---------------------------|
| Confirm compilation baseline | First action of every Rust session: run `cargo check --workspace` |
| Check crate metadata | After reading `Cargo.toml`: note `edition`, `rust-version`, workspace members |
| go-to-definition / find-references | Before modifying any public item |
| `cargo check` | After every code edit; surfaces type errors before the full test suite |
| `cargo clippy --workspace --all-targets -- -D warnings` | After `cargo check` passes; re-run after applying fixes |
| `cargo test --workspace` | After clippy passes; paste full output |
| `cargo +nightly udeps --workspace` | During cleanup or refactoring tasks to find unused dependencies (requires nightly; use `cargo machete` as the stable alternative) |

Fallback without rust-analyzer: `Grep` for symbols, `cargo check` / `cargo clippy` / `cargo test` for diagnostics. rust-analyzer understands types and trait bounds where grep sees text — check references before renaming any public item.

## Verify the Crate, Not the Protocol

**What it looks like**: "sqlx will automatically roll back the transaction if you drop it, so this is safe."
**Why wrong**: Protocol-level behavior and crate-level behavior are not the same. LLMs reason from training data about protocols, not from reading the specific crate version in `Cargo.lock`.
**Do instead**: Read the crate source in `~/.cargo/registry/src/`. The question is not "how does PostgreSQL work?" but "how does THIS `sqlx` version implement `Transaction::drop`?"

```bash
# Find the crate source path
ls ~/.cargo/registry/src/
# Read a specific file
cat ~/.cargo/registry/src/index.crates.io-*/sqlx-core-0.8.*/src/transaction.rs
```

## Rebuilt Binary Check

When testing a fix to a CLI binary, confirm the binary you're running matches the fix. Check the modification time of `target/debug/<bin>` vs the fix time:

```bash
# macOS
stat -f "%m %Sm" target/debug/my-binary

# Linux
stat -c "%Y %n" target/debug/my-binary

# Or compare version output against what's in Cargo.toml
./target/debug/my-binary --version
grep '^version' Cargo.toml
```

A stale binary silently passes tests against the old (broken) code path.

## Render-Time Fixes Need Render-Time Verification

Bugs that manifest at output-render time (table layout, tracing output, template expansion) slip past compile + `cargo test`. Build a small standalone reproducer under `/tmp` with realistic fake data, run it, and compare before/after output.

```bash
cd /tmp
cargo new reproducer --edition 2024
cd reproducer
# Add the workspace crate as a path dependency in Cargo.toml:
# [dependencies]
# my-crate = { path = "/path/to/workspace/my-crate" }
cargo run
```

Use a path dependency to the workspace crate rather than copying source.

## Pre-Handoff Command Sequence

Run in this order on every Rust change; each must be clean before you report done. Paste the real output.

```bash
cargo fmt --check                                         # exit 0 = formatted; fix with cargo fmt
cargo check --workspace                                   # exit 0 = compiles
cargo clippy --workspace --all-targets -- -D warnings     # exit 0 = no warnings; fix each one
cargo test --workspace                                    # paste full output
```

Optional: add `--release` to `cargo clippy` and `cargo test` to catch optimisation-dependent issues.

A `cargo audit` run is recommended when `Cargo.lock` changes:

```bash
cargo install cargo-audit  # one-time
cargo audit
```

## Dead Code and Unused Dependency Analysis

`cargo-udeps` finds crates listed in `Cargo.toml` that are never `use`d in the final build. Run during cleanup, review, or refactoring tasks; skip when the question is only "does this build and pass tests?"

```bash
# Requires nightly for the unstable flag
cargo +nightly udeps --workspace

# For stable toolchain, use cargo-machete (no nightly needed):
cargo install cargo-machete
cargo machete
```

Known false positives:

| Finding | Cause | Fix |
|---------|-------|-----|
| Dev-dependency flagged | Used only in `#[test]` or `tests/` | Add to `[dev-dependencies]`, not `[dependencies]` |
| Feature-gated crate flagged | Crate only activated via a feature flag | Check `Cargo.toml` for `optional = true` and `#[cfg(feature = "...")]` in source |
| Proc-macro crate flagged | `cargo-udeps` cannot always track proc-macro usage | Verify manually: remove and see if the build still passes |

For dead code analysis at the function level, add `#[allow(dead_code)]` to intentionally unused items with a comment explaining why; do not suppress the warning globally.

```bash
# Find dead code that the compiler warns about
cargo check --workspace 2>&1 | grep "warning: .* is never used"

# More thorough: unused public items in library crates
cargo clippy --workspace -- -W clippy::unused_self -W clippy::unused_async
```

**Tooling decision**: rust-analyzer + `cargo check` + `grep` cover all Rust use cases for reference lookup, impact analysis, and code review. `cargo-udeps` / `cargo machete` add dependency hygiene on top. For call graph analysis before large refactors, use rust-analyzer's find-references rather than a static call graph tool — it handles trait dispatch and generics correctly.
