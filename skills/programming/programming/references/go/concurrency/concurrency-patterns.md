# Go Concurrency Patterns Reference

## Worker Pool Pattern

The standard pattern for processing jobs concurrently with controlled parallelism.

```go
type Job struct {
    ID   string
    Data []byte
}

type Result struct {
    JobID string
    Value any
    Error error
}

func ProcessJobs(ctx context.Context, jobs <-chan Job, numWorkers int) <-chan Result {
    results := make(chan Result, numWorkers)

    var wg sync.WaitGroup
    wg.Add(numWorkers)

    for i := 0; i < numWorkers; i++ {
        go func(workerID int) {
            defer wg.Done()

            for {
                select {
                case job, ok := <-jobs:
                    if !ok {
                        return
                    }

                    value, err := processJob(ctx, job)
                    results <- Result{
                        JobID: job.ID,
                        Value: value,
                        Error: err,
                    }

                case <-ctx.Done():
                    return
                }
            }
        }(i)
    }

    go func() {
        wg.Wait()
        close(results)
    }()

    return results
}
```

## Rate Limiter Pattern

Token-bucket rate limiter with context-aware waiting.

```go
type RateLimiter struct {
    rate     int
    interval time.Duration
    tokens   chan struct{}
    stop     chan struct{}
}

func NewRateLimiter(rate int, interval time.Duration) *RateLimiter {
    rl := &RateLimiter{
        rate:     rate,
        interval: interval,
        tokens:   make(chan struct{}, rate),
        stop:     make(chan struct{}),
    }

    for i := 0; i < rate; i++ {
        rl.tokens <- struct{}{}
    }

    go rl.refill()
    return rl
}

func (rl *RateLimiter) refill() {
    ticker := time.NewTicker(rl.interval / time.Duration(rl.rate))
    defer ticker.Stop()

    for {
        select {
        case <-ticker.C:
            select {
            case rl.tokens <- struct{}{}:
            default: // Channel full, skip
            }
        case <-rl.stop:
            return
        }
    }
}

func (rl *RateLimiter) Wait(ctx context.Context) error {
    select {
    case <-rl.tokens:
        return nil
    case <-ctx.Done():
        return ctx.Err()
    }
}

func (rl *RateLimiter) Stop() {
    close(rl.stop)
}
```

## Fan-Out / Fan-In Pattern

```go
// Fan-out: distribute work to multiple goroutines
func fanOut(ctx context.Context, input <-chan Job, workers int) []<-chan Result {
    channels := make([]<-chan Result, workers)
    for i := 0; i < workers; i++ {
        channels[i] = worker(ctx, input)
    }
    return channels
}

// Fan-in: merge multiple channels into one
func fanIn(ctx context.Context, channels ...<-chan Result) <-chan Result {
    out := make(chan Result)
    var wg sync.WaitGroup

    for _, ch := range channels {
        wg.Add(1)
        go func() {  // Go 1.22+: ch captured correctly
            defer wg.Done()
            for result := range ch {
                select {
                case out <- result:
                case <-ctx.Done():
                    return
                }
            }
        }()
    }

    go func() {
        wg.Wait()
        close(out)
    }()

    return out
}
```

## Pipeline Pattern

```go
func pipeline(ctx context.Context, input <-chan int) <-chan int {
    out := make(chan int)
    go func() {
        defer close(out)
        for n := range input {
            select {
            case out <- n * 2:
            case <-ctx.Done():
                return
            }
        }
    }()
    return out
}
```

## Graceful Shutdown Patterns

### Background Worker Lifecycle

```go
type Worker struct {
    ctx    context.Context
    cancel context.CancelFunc
    done   chan struct{}
}

func NewWorker() *Worker {
    ctx, cancel := context.WithCancel(context.Background())
    w := &Worker{
        ctx:    ctx,
        cancel: cancel,
        done:   make(chan struct{}),
    }
    go w.run()
    return w
}

func (w *Worker) run() {
    defer close(w.done)

    ticker := time.NewTicker(time.Second)
    defer ticker.Stop()

    for {
        select {
        case <-ticker.C:
            w.doWork()
        case <-w.ctx.Done():
            return
        }
    }
}

func (w *Worker) Stop() {
    w.cancel()
    <-w.done // Wait for goroutine to finish
}
```

### Server Graceful Shutdown

```go
func runServer(ctx context.Context) error {
    srv := &http.Server{Addr: ":8080"}

    go func() {
        if err := srv.ListenAndServe(); err != http.ErrServerClosed {
            log.Printf("server error: %v", err)
        }
    }()

    <-ctx.Done()

    shutdownCtx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
    defer cancel()

    return srv.Shutdown(shutdownCtx)
}
```

## Container-Aware GOMAXPROCS (Go 1.25+)

Go 1.25 automatically adjusts GOMAXPROCS based on container CPU limits. No manual configuration needed.

```go
// Before Go 1.25 (no longer needed - can be removed)
import _ "go.uber.org/automaxprocs"

// Go 1.25+: Just works - no code needed!
// Runtime auto-detects: min(host CPUs, cgroup CPU limit)
```

Disabling if needed:

```bash
GODEBUG=containermaxprocs=0  # Disable container detection
GODEBUG=updatemaxprocs=0     # Disable dynamic updates
export GOMAXPROCS=4           # Explicit override
```

Platform support: Linux only (uses cgroups). Does not apply to Windows or macOS.
