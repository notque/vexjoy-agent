# Rust Version Idioms and Gates

Version-pinned idiom table, hard gates, and error-message-to-version map. Check `Cargo.toml` before applying any row: writing a 1.75+ idiom on a project with `rust-version = "1.65"` fails the MSRV check. For how to write each idiom in context (with before/after code), load [rust-modern-code.md](rust-modern-code.md).

```bash
grep -E '^edition|^rust-version' Cargo.toml
# "rust-version = "1.85"" means 1.85 features are available; lower versions: see table below
```

The `rust-version` field in `Cargo.toml`, not the installed toolchain, decides what compiles during `cargo check --all`. A 1.85 toolchain building a crate with `rust-version = "1.75"` rejects 1.76+ language features.

## Idiom Replacement Table (Rust 1.56–1.85)

The most common AI-generated Rust failure mode is old idioms where modern ones exist:

| Outdated Pattern | Modern Replacement | Since |
|-----------------|-------------------|-------|
| `Box<dyn std::error::Error>` as library return | `thiserror`-derived error type | stable |
| `impl From<E> for MyError` by hand | `#[from]` attribute in `thiserror` | stable |
| `if let Some(x) = opt { return Err(...); }` | `let Some(x) = opt else { return Err(...); }` (let-else) | 1.65 |
| `match result { Ok(v) => v, Err(e) => return Err(e) }` | `?` operator | 1.13 |
| Custom iterator struct with `Iterator` impl | `gen { yield item; }` block | 1.85 (2024 edition) |
| `async fn` in trait via `async-trait` macro | `async fn` in trait (stable) | 1.75 |
| `Box<dyn Future<Output = T> + Send>` return from trait | `-> impl Future<Output = T>` in impl (RPITIT) | 1.75 |
| `dyn Error + Send + Sync + 'static` box | `anyhow::Error` in application code | stable |
| `eprintln!("{}", e); process::exit(1)` in main | `fn main() -> anyhow::Result<()>` | stable |
| `serde_json::from_str(s).unwrap()` | `serde_json::from_str(s).context("parse foo")?` | stable |
| `String` parameter in public API | `impl AsRef<str>` or `&str` | stable |
| `Vec<T>` parameter that is only iterated | `impl IntoIterator<Item = T>` or `&[T]` | stable |
| `Arc<Mutex<T>>` in async code | `Arc<tokio::sync::Mutex<T>>` | tokio stable |
| `thread::sleep` in async tests | `tokio::time::pause()` + `tokio::time::advance(d)` | tokio stable |
| `for i in 0..items.len() { let item = &items[i]; }` | `for item in &items { }` | stable |
| Manual `sort_by_key` with allocation | `.sort_by(|a, b| a.key.cmp(&b.key))` | stable |
| `unwrap_or_else(|_| default)` for infallible | `unwrap_or(default)` | stable |
| `if x.is_some() { x.unwrap() }` | `if let Some(v) = x { v }` or `x?` in Result context | stable |
| `HashMap::new()` + manual inserts in tests | `HashMap::from([("k", "v")])` | 1.56 |
| Derive `Clone` + manual `new` for builder | `bon` or `derive_builder` crate | stable |
| `futures::future::join_all(vec)` | `tokio::task::JoinSet` | tokio 1.x |
| `tokio::spawn` drop (fire-and-forget) | Store `JoinHandle`, call `.await` on shutdown | stable |

Notes on the newest rows:
- `let-else` (1.65): the else branch must diverge (return, break, continue, panic, or loop).
- `async fn` in traits (1.75): stable without `async-trait` macro. Dyn dispatch still requires `#[async_trait]` or explicit `Box<dyn Future>` return.
- RPITIT (1.75): `impl Trait` in trait return positions without boxing.
- `gen` blocks (1.85, 2024 edition only): zero-cost iterator authoring in push style. Not available in 2021 edition crates.
- `tokio::time::pause` requires the `test-util` feature: `tokio = { version = "1", features = ["full", "test-util"] }`.

## Hard Gates (STOP / REPORT / FIX)

Framework: `skills/shared-patterns/forbidden-patterns-template.md`.

| Pattern | Why blocked | Fix |
|---------|-------------|-----|
| `.unwrap()` in library code | Panics with no recovery path for the caller | Return `Err(...)` or `.ok_or_else(...)` |
| `.expect("")` (empty string message) | Panic with no diagnostic context | `.expect("user id must be set at this point")` |
| `.clone()` to satisfy the borrow checker | Hides a design flaw; costs allocation | Restructure ownership or use `Arc` / `Rc` explicitly |
| `let _ = result;` / `let _ = tx.send(...)` | Silently discards errors | `result?` or `result.ok()` with explicit intent |
| `err.to_string().contains("...")` | Breaks when messages change | `downcast_ref::<ConcreteError>()` or `matches!(err, MyError::Variant)` |
| `std::thread::sleep` in async code | Blocks the executor thread | `tokio::time::sleep(d).await` |
| `std::sync::Mutex` held across `.await` | Deadlocks under async | `tokio::sync::Mutex` |
| Fire-and-forget `tokio::spawn` (dropped `JoinHandle`) | Panics lost; no shutdown path | Store `JoinHandle`; await on shutdown |
| `Box<dyn std::error::Error>` in library API | Erases error type; callers cannot match variants | `thiserror`-derived enum |

```bash
grep -rn "\.unwrap()" --include="*.rs" | grep -v "_test\|#\[test\]\|mod tests"
grep -rn '\.expect("")' --include="*.rs"
grep -rn 'let _ = ' --include="*.rs"
grep -rn 'to_string().*contains\|contains.*to_string()' --include="*.rs"
grep -rn 'std::thread::sleep' --include="*.rs"
```

Sanctioned exceptions:
- `.unwrap()` in `#[test]` functions where the invariant is obvious and documented.
- `.clone()` when cloning `Arc<T>` — that is the intended use; flag only `.clone()` on large owned types.
- `let _ = handle` when the `JoinHandle` is stored in a shutdown list, not dropped.

## Error Message → Version Map

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `error[E0658]: let chains are experimental` | Rust < 1.88 | Use nested `if let` or upgrade MSRV |
| `error[E0658]: use of unstable library feature 'let_else'` | Rust < 1.65 | Upgrade to 1.65+ |
| `error[E0277]: the trait bound ... is not satisfied` on async trait | Rust < 1.75 without `async-trait` | Add `#[async_trait]` or upgrade to 1.75 |
| `error[E0562]: 'impl Trait' only allowed in ... not in return type of trait methods` | Rust < 1.75 (RPITIT) | Upgrade to 1.75 or use `Box<dyn Future>` |
| `error: gen blocks are not stable` | Rust < 1.85 or edition < 2024 | Add `edition = "2024"` and `rust-version = "1.85"` |
| `error[E0106]: missing lifetime specifier` on `&str` field | Struct needs explicit `'a` lifetime | Add `struct Foo<'a> { name: &'a str }` or use `String` |
| `cannot borrow ... as mutable because it is also borrowed as immutable` | Simultaneous mutable and immutable borrows | Restructure: end the immutable borrow before the mutable one |
| `future cannot be sent between threads safely` | `!Send` type held across `.await` | Drop the non-Send value before `.await`, or use `tokio::task::LocalSet` |
| `the trait object ... cannot be made into an object` (object-unsafe trait) | Trait has generic methods or `Self` in signature | Remove generics from the trait or use `Box<dyn AnyTrait>` via `dyn_clone` |
| `error[E0507]: cannot move out of ...` | Move out of borrowed context | `.clone()` (with intent), or restructure to avoid the borrow |
| `overflow evaluating the requirement` (recursive type) | Recursive type without indirection | Wrap in `Box<T>` at one point in the cycle |
