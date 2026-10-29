# Writing Modern Rust (Rust 2024 Edition)

Load this file before you write or edit any Rust code. Each rule below fixes a failure measured in generated code: code that compiled and passed its tests but used outdated or weak idioms. Rules marked with a version need that version or later in `Cargo.toml`; check the `edition` and `rust-version` lines first.

```bash
grep -E '^edition|^rust-version' Cargo.toml
# "edition = "2024"" unlocks every rule here; lower editions: see rust-version-idioms.md
```

## 1. Doc comments on every public item

Every public type, function, method, constant, and module gets a doc comment that starts with a verb or noun phrase describing what the item does (not just repeating its name). Every `lib.rs` and `mod.rs` starts with a `//!` crate or module doc comment. Measured: 9 of 12 unguided outputs skipped doc comments; 5 of 14 guided outputs still skipped the module comment.

```rust
// BAD
pub struct UserRepo {
    pool: sqlx::PgPool,
}

impl UserRepo {
    pub fn new(pool: sqlx::PgPool) -> Self {
        Self { pool }
    }
}

// GOOD
//! User repository backed by PostgreSQL via sqlx.

/// Stores users in PostgreSQL. Safe for concurrent use via internal connection pooling.
pub struct UserRepo {
    pool: sqlx::PgPool,
}

impl UserRepo {
    /// Creates a `UserRepo` using the given connection pool. The caller owns and closes the pool.
    pub fn new(pool: sqlx::PgPool) -> Self {
        Self { pool }
    }
}
```

State thread-safety, ownership, and zero-value/default behavior when they matter.

## 2. Error handling

| Do | Not | Since |
|----|-----|-------|
| `thiserror` for library error types | `Box<dyn Error>` or `String` as error return in library code | stable |
| `anyhow::Result` / `.context("...")` for application code | `.unwrap()` or `.expect("")` outside tests | stable |
| `err.downcast_ref::<ConcreteError>()` / `err.is::<E>()` (anyhow) | String matching: `err.to_string().contains("not found")` | stable |
| Named variants: `Error::NotFound { id }` | `Error::NotFound(String)` with formatted text as data | stable |
| `.context("create user {email:?}")` to add call-site context | Empty wrappers: `anyhow!("error: {e}")` that repeat the message | stable |
| Driver typed errors via `sqlx::Error::Database` downcast | Magic codes or string matching on SQLSTATE | stable |

Library errors with `thiserror`:

```rust
// BAD
pub fn get_user(id: Uuid) -> Result<User, Box<dyn std::error::Error>> { ... }

// GOOD
use thiserror::Error;

#[derive(Debug, Error)]
pub enum UserError {
    #[error("user {id} not found")]
    NotFound { id: Uuid },
    #[error("database error")]
    Database(#[from] sqlx::Error),
}

pub async fn get_user(id: Uuid, pool: &PgPool) -> Result<User, UserError> { ... }
```

Application code with `anyhow`:

```rust
// BAD
fn load_config(path: &str) -> Result<Config, Box<dyn Error>> {
    let s = std::fs::read_to_string(path)?;
    Ok(toml::from_str(&s)?)
}

// GOOD
use anyhow::{Context, Result};

fn load_config(path: &str) -> Result<Config> {
    let s = std::fs::read_to_string(path)
        .with_context(|| format!("read config from {path:?}"))?;
    toml::from_str(&s).context("parse config")
}
```

Driver errors — find the typed error in the crate source, then match it:

```rust
fn is_unique_violation(err: &sqlx::Error) -> bool {
    if let sqlx::Error::Database(db_err) = err {
        db_err.is_unique_violation()
    } else {
        false
    }
}
```

## 3. Async and task lifecycle

- Use `#[tokio::test]` for all async tests. Never `tokio::runtime::Runtime::new().unwrap().block_on(...)` in tests.
- Never `std::thread::sleep` in async tests — use `tokio::time::pause()` + `tokio::time::advance(d)`. Measured: 7 of 12 unguided outputs used `thread::sleep`.
- Every `tokio::spawn` call stores the `JoinHandle` or awaits it. Fire-and-forget spawns that drop `JoinHandle` silently discard panics and make shutdown impossible.
- Cancellation-safe async: hold no locks across `.await` points; use `tokio::sync::Mutex` not `std::sync::Mutex` in async code.
- Signal handling: `tokio::signal::ctrl_c()` for Ctrl-C; `signal::unix::signal(SignalKind::terminate())` for SIGTERM.

```rust
// BAD: fire-and-forget, panic lost, no shutdown path
fn start_background_task() {
    tokio::spawn(async { do_work().await });
}

// GOOD: tracked handle, can be awaited on shutdown
pub struct Worker {
    handle: tokio::task::JoinHandle<()>,
}

impl Worker {
    pub fn start() -> Self {
        Self {
            handle: tokio::spawn(async { do_work().await }),
        }
    }

    pub async fn shutdown(self) {
        self.handle.await.expect("worker panicked");
    }
}
```

`main` delegates to `run`:

```rust
// BAD: unwrap in main, no graceful error display
#[tokio::main]
async fn main() {
    run().await.unwrap();
}

// GOOD
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    run().await
}

async fn run() -> anyhow::Result<()> {
    let config = load_config("config.toml")?;
    // ... defers and signal setup here
    Ok(())
}
```

## 4. Bounded concurrency

Use `tokio::task::JoinSet` for a bounded pool that collects results. Results go back in completion order; use a preallocated `Vec` indexed by task ID when order matters.

```rust
/// Map calls fn for every item with at most `workers` tasks in flight.
/// Returns results in the order tasks complete, not input order.
pub async fn map_concurrent<T, R, F, Fut>(
    items: Vec<T>,
    workers: usize,
    f: F,
) -> anyhow::Result<Vec<R>>
where
    T: Send + 'static,
    R: Send + 'static,
    F: Fn(T) -> Fut + Clone + Send + 'static,
    Fut: Future<Output = anyhow::Result<R>> + Send,
{
    use tokio::task::JoinSet;
    let semaphore = Arc::new(tokio::sync::Semaphore::new(workers));
    let mut set = JoinSet::new();

    for item in items {
        let sem = semaphore.clone();
        let f = f.clone();
        set.spawn(async move {
            let _permit = sem.acquire().await?;
            f(item).await
        });
    }

    let mut results = Vec::new();
    while let Some(res) = set.join_next().await {
        results.push(res??);
    }
    Ok(results)
}
```

For CPU-bound parallel work, use `rayon`:

```rust
use rayon::prelude::*;

let results: Vec<_> = items.par_iter().map(|item| process(item)).collect();
```

## 5. HTTP servers with axum

Use `axum` for HTTP servers. Let the router return 405 automatically — axum does this when a path matches but the method does not.

```rust
use axum::{Router, routing::{get, post}};

let app = Router::new()
    .route("/items", post(create_item))
    .route("/items/{id}", get(get_item))
    .route("/healthz", get(health));
```

Graceful shutdown: bind a `CancellationToken` to the server so it shuts down when the token is cancelled.

```rust
use tokio_util::sync::CancellationToken;

pub async fn serve(addr: SocketAddr, app: Router, token: CancellationToken) -> anyhow::Result<()> {
    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app)
        .with_graceful_shutdown(async move { token.cancelled().await })
        .await
        .context("axum serve")
}
```

Request body validation: use `axum::extract::Json` with `serde`; reject unknown fields via `#[serde(deny_unknown_fields)]`.

```rust
#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct CreateItem {
    name: String,
    quantity: u32,
}

async fn create_item(Json(body): Json<CreateItem>) -> impl IntoResponse { ... }
```

Bind development servers to `127.0.0.1`, never `0.0.0.0` or bare `:port`.

## 6. Serialization (serde)

- `#[serde(deny_unknown_fields)]` on all API input structs to reject extra fields.
- `#[serde(rename_all = "camelCase")]` when the API contract uses camelCase JSON.
- `#[serde(skip_serializing_if = "Option::is_none")]` to omit `null` fields; use `#[serde(default)]` to accept missing fields on input.
- `chrono::DateTime<Utc>` serializes to ISO 8601 with the `chrono` serde feature.
- Never implement `Serialize` / `Deserialize` by hand unless the generated code is wrong.

## 7. CLIs with clap

Shape: `fn run(args: Args) -> anyhow::Result<()>` and `main` is three lines.

```rust
use clap::Parser;

/// Count word frequencies in a text file.
#[derive(Parser, Debug)]
#[command(version, about)]
struct Args {
    /// Input file path ("-" for stdin).
    #[arg(short, long)]
    input: String,

    /// Number of top words to print.
    #[arg(short, long, default_value_t = 10)]
    top: usize,
}

fn main() -> anyhow::Result<()> {
    let args = Args::parse();
    run(args)
}

fn run(args: Args) -> anyhow::Result<()> {
    // no process::exit, no eprintln! for errors — use ?
    let text = read_input(&args.input)?;
    print_top_words(&text, args.top);
    Ok(())
}
```

Never call `process::exit` inside `run`; return `Err` and let `main` display it.

## 8. Iterators

- Return `impl Iterator<Item = T>` from functions that produce sequences lazily.
- Use `.filter_map`, `.flat_map`, `.chain`, `.take_while` over manual loops.
- Avoid `.collect::<Vec<_>>()` in the middle of a chain when the result feeds another iterator immediately.
- For `gen` blocks (2024 edition, Rust 1.85+): use `gen { yield item; }` to write push-style iterators as pull-style:

```rust
// 2024 edition: gen block
fn fibonacci() -> impl Iterator<Item = u64> {
    gen {
        let (mut a, mut b) = (0u64, 1u64);
        loop {
            yield a;
            (a, b) = (b, a + b);
        }
    }
}
```

- Streaming rows from a database as an iterator: use `sqlx::query_as::<_, T>(...).fetch(pool)` which returns a `Stream`; convert with `stream.next().await` or collect with `stream.try_collect().await`.

## 9. Standard-library and ecosystem helpers

| Need | Use | Notes |
|------|-----|-------|
| UUID | `uuid::Uuid::new_v4()` / `uuid::Uuid::now_v7()` | `uuid` crate, `v4`/`v7` feature |
| Async runtime | `tokio` | `tokio = { version = "1", features = ["full"] }` |
| HTTP server | `axum` | `axum = "0.8"` |
| HTTP client | `reqwest` | `reqwest = { version = "0.12", features = ["json"] }` |
| Structured logging | `tracing` + `tracing-subscriber` | `tracing::info!(key = val, "message")` |
| Config loading | `config` crate or `toml` + `serde` | |
| CLI parsing | `clap` | derive feature |
| Data-parallel | `rayon` | |
| Date/time | `chrono` with `serde` feature | |
| Database | `sqlx` with `postgres`/`sqlite` feature + `runtime-tokio` | |
| Error types | `thiserror` (libraries), `anyhow` (applications) | |
| Sorting with tie-break | `.sort_by(|a, b| a.count.cmp(&b.count).then(a.name.cmp(&b.name)))` | |

## 10. Tests

- `#[tokio::test]` for all async tests.
- `tokio::time::pause()` at the top of a test that exercises timeouts or delayed work; then `tokio::time::advance(d)` to move the clock. Measured: 0 of 12 unguided outputs used time control; 6 used `thread::sleep`.
- `tempfile::TempDir` for tests needing a filesystem; use the `tempfile` crate.
- Parametrize with `rstest`:

```rust
use rstest::rstest;

#[rstest]
#[case("hello world", 2)]
#[case("a b c d", 4)]
fn test_word_count(#[case] input: &str, #[case] expected: usize) {
    assert_eq!(count_words(input), expected);
}
```

- `assert_eq!(got, want)` — `got` first, `want` second. Measured: reversed order is the most common assertion mistake.
- Mock external services with `wiremock` for HTTP; `sqlx::test` macro with `TestPool` for database tests.
- Never leave `#[ignore]` without a comment explaining why and a tracking issue.

## 11. sqlx database access

- Every query uses `sqlx::query_as!` or `sqlx::query!` macros for compile-time checking when `DATABASE_URL` is set.
- Every query takes a `&PgPool` or `&mut PgTransaction`; never hold connections across non-db work.
- Map `sqlx::Error::RowNotFound` to your domain `NotFound` error.
- Transactions: `let mut tx = pool.begin().await?; /* queries using &mut tx */; tx.commit().await?;` — no manual rollback needed; `Drop` rolls back on error.
- UPDATE or DELETE on a missing row: check `result.rows_affected()` and return `NotFound` when 0.
- Enforce uniqueness with a UNIQUE constraint and map the `is_unique_violation()` check from the driver error; never check-then-insert.

## 12. Pre-handoff checklist

Run each command when you have tools. Without tools, read your code against each line before you answer.

```bash
cargo fmt --check                                          # must exit 0
cargo check --workspace                                    # must exit 0
cargo clippy --workspace --all-targets -- -D warnings      # must exit 0
cargo test --workspace                                     # paste the full output
```

- [ ] Every `lib.rs`, `mod.rs`, and `main.rs` has a `//!` crate or module doc comment; every public item has a `///` doc comment starting with a verb or noun phrase.
- [ ] No `.unwrap()` outside tests; no `.expect("")` (empty message); no `.clone()` added solely to silence the borrow checker.
- [ ] No `Box<dyn Error>` as a library return type; library errors use `thiserror`; application errors use `anyhow`.
- [ ] No `std::thread::sleep` in async tests; async tests use `tokio::time::pause` + `tokio::time::advance`.
- [ ] Every `tokio::spawn` stores or awaits its `JoinHandle`.
- [ ] No fire-and-forget channels (`let _ = tx.send(...)`); every send checks the result or uses `?`.
- [ ] No string matching on error messages; driver errors use typed downcast (`db_err.is_unique_violation()`).
- [ ] No hand-rolled UUIDs; use `uuid::Uuid::new_v4()` or `uuid::Uuid::now_v7()`.
- [ ] Every `async fn` that holds a `MutexGuard` across `.await` uses `tokio::sync::Mutex`, not `std::sync::Mutex`.
- [ ] Servers bind `127.0.0.1` by default and shut down via `CancellationToken` or signal handler.
