# Go Concurrency Patterns

> Reference file for golang-general-engineer agent. Loaded as context during Go development tasks.

## Worker Pool (with generics)

Distributes work across a fixed number of goroutines. Use when you have many independent tasks and want to bound resource usage.

```go
func WorkerPool[T any, R any](ctx context.Context, workers int, tasks []T, fn func(context.Context, T) (R, error)) ([]R, error) {
    var (
        taskCh   = make(chan T)
        resultCh = make(chan R, len(tasks))
        g, gctx  = errgroup.WithContext(ctx)
    )

    // Fan out: launch workers
    for range workers {
        g.Go(func() error {
            for task := range taskCh {
                result, err := fn(gctx, task)
                if err != nil {
                    return err
                }
                resultCh <- result
            }
            return nil
        })
    }

    // Feed tasks
    go func() {
        defer close(taskCh)
        for _, t := range tasks {
            select {
            case <-gctx.Done():
                return
            case taskCh <- t:
            }
        }
    }()

    // Wait for all workers, then close results
    err := g.Wait()
    close(resultCh)
    if err != nil {
        return nil, err
    }

    results := make([]R, 0, len(tasks))
    for r := range resultCh {
        results = append(results, r)
    }
    return results, nil
}
```

## Fan-out/Fan-in with errgroup

Launch multiple concurrent operations and collect results. `errgroup` cancels remaining work if any task fails.

```go
func fetchAll(ctx context.Context, urls []string) ([]Response, error) {
    g, gctx := errgroup.WithContext(ctx)
    responses := make([]Response, len(urls))

    for i, url := range urls {
        g.Go(func() error {
            resp, err := fetchURL(gctx, url)
            if err != nil {
                return fmt.Errorf("fetch %s: %w", url, err)
            }
            responses[i] = resp // safe: each goroutine writes to its own index
            return nil
        })
    }

    if err := g.Wait(); err != nil {
        return nil, err
    }
    return responses, nil
}
```

Use `errgroup.SetLimit(n)` to cap the number of concurrent goroutines.

## Context Propagation Rules

Contexts flow down the call chain. Never store contexts in structs; pass them as the first argument.

```go
// RULE 1: context is always the first parameter
func ProcessOrder(ctx context.Context, order Order) error { ... }

// RULE 2: derive child contexts, never replace parent
func handler(ctx context.Context) error {
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
    defer cancel() // always defer cancel to release resources
    return doWork(ctx)
}

// RULE 3: check ctx.Err() in long loops
func processItems(ctx context.Context, items []Item) error {
    for _, item := range items {
        if err := ctx.Err(); err != nil {
            return fmt.Errorf("processing interrupted: %w", err)
        }
        if err := process(ctx, item); err != nil {
            return err
        }
    }
    return nil
}

// RULE 4: use context.WithCancelCause for richer cancellation (Go 1.20+)
ctx, cancel := context.WithCancelCause(parentCtx)
cancel(fmt.Errorf("user requested shutdown"))
// later:
cause := context.Cause(ctx) // "user requested shutdown"
```

## Channel Ownership

The goroutine that creates a channel should close it. Receivers should never close channels.

```go
// GOOD: producer creates, writes, and closes
func produce(ctx context.Context) <-chan Event {
    ch := make(chan Event)
    go func() {
        defer close(ch) // producer closes
        for {
            event, err := pollEvent(ctx)
            if err != nil {
                return
            }
            select {
            case <-ctx.Done():
                return
            case ch <- event:
            }
        }
    }()
    return ch // return receive-only channel
}

// Consumer reads until channel is closed
func consume(events <-chan Event) {
    for event := range events {
        handle(event)
    }
}
```

## sync.Once for Lazy Initialization

Initialize expensive resources exactly once, safe for concurrent access.

```go
type Client struct {
    initOnce sync.Once
    conn     *grpc.ClientConn
    connErr  error
}

func (c *Client) getConn() (*grpc.ClientConn, error) {
    c.initOnce.Do(func() {
        c.conn, c.connErr = grpc.Dial("server:443",
            grpc.WithTransportCredentials(credentials.NewTLS(nil)),
        )
    })
    return c.conn, c.connErr
}
```

For simple values, prefer `sync.OnceValue` (Go 1.21+):
```go
var loadConfig = sync.OnceValue(func() *Config {
    cfg, err := readConfigFile()
    if err != nil {
        slog.Error("failed to load config", "err", err)
        return &Config{} // return default
    }
    return cfg
})

// Usage: cfg := loadConfig()
```

## Rate Limiting with time.Ticker

Control the rate of operations (API calls, message sends, etc.).

```go
func rateLimitedProcess(ctx context.Context, items []Item, rps int) error {
    ticker := time.NewTicker(time.Second / time.Duration(rps))
    defer ticker.Stop()

    for _, item := range items {
        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-ticker.C:
            if err := process(ctx, item); err != nil {
                return fmt.Errorf("process item %s: %w", item.ID, err)
            }
        }
    }
    return nil
}
```

For bursty traffic, use a buffered semaphore channel:
```go
func boundedProcess(ctx context.Context, items []Item, maxConcurrent int) error {
    sem := make(chan struct{}, maxConcurrent)
    g, gctx := errgroup.WithContext(ctx)

    for _, item := range items {
        sem <- struct{}{} // acquire
        g.Go(func() error {
            defer func() { <-sem }() // release
            return process(gctx, item)
        })
    }
    return g.Wait()
}
```

## Mutex Scope Minimization

Hold locks for the shortest time possible. Never do I/O while holding a lock.

```go
// BAD: lock held during network call
func (s *Service) Update(id string) error {
    s.mu.Lock()
    defer s.mu.Unlock()
    data := s.cache[id]
    result, err := s.client.Fetch(data.URL) // network I/O under lock!
    if err != nil {
        return err
    }
    s.cache[id] = result
    return nil
}

// GOOD: minimize lock scope
func (s *Service) Update(id string) error {
    s.mu.RLock()
    data := s.cache[id]
    s.mu.RUnlock()

    result, err := s.client.Fetch(data.URL) // no lock held during I/O

    s.mu.Lock()
    s.cache[id] = result
    s.mu.Unlock()
    return err
}
```

## Select with Default (Non-blocking)

Use `select` with a `default` case to attempt a channel operation without blocking.

```go
// Non-blocking send: drop the event if the channel is full
func tryNotify(ch chan<- Event, event Event) bool {
    select {
    case ch <- event:
        return true
    default:
        return false // channel full, event dropped
    }
}

// Non-blocking receive: check if work is available
func tryReceive(ch <-chan Task) (Task, bool) {
    select {
    case task := <-ch:
        return task, true
    default:
        return Task{}, false
    }
}

// Timeout pattern: wait, but not forever
func receiveWithTimeout(ch <-chan Result, timeout time.Duration) (Result, error) {
    select {
    case r := <-ch:
        return r, nil
    case <-time.After(timeout):
        return Result{}, fmt.Errorf("receive timed out after %v", timeout)
    }
}
```

## Pipeline Pattern

Chain stages where each stage is a goroutine reading from one channel and writing to another.

```go
func pipeline(ctx context.Context, input <-chan int) <-chan string {
    doubled := stage(ctx, input, func(n int) int { return n * 2 })
    formatted := stage(ctx, doubled, func(n int) string { return fmt.Sprintf("value: %d", n) })
    return formatted
}

func stage[In, Out any](ctx context.Context, in <-chan In, fn func(In) Out) <-chan Out {
    out := make(chan Out)
    go func() {
        defer close(out)
        for v := range in {
            select {
            case <-ctx.Done():
                return
            case out <- fn(v):
            }
        }
    }()
    return out
}
```
