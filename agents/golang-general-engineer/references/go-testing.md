# Go Testing Patterns

## Table-Driven Tests with t.Run

Standard pattern for multiple scenarios. Each subtest runs individually.

```go
func TestParseSize(t *testing.T) {
    tests := []struct {
        name    string
        input   string
        want    int64
        wantErr bool
    }{
        {name: "bytes", input: "100B", want: 100},
        {name: "kilobytes", input: "2KB", want: 2048},
        {name: "megabytes", input: "1MB", want: 1_048_576},
        {name: "empty string", input: "", wantErr: true},
        {name: "invalid unit", input: "5XB", wantErr: true},
        {name: "negative", input: "-1KB", wantErr: true},
    }

    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := ParseSize(tt.input)
            if tt.wantErr {
                if err == nil {
                    t.Fatalf("ParseSize(%q) expected error, got %d", tt.input, got)
                }
                return
            }
            if err != nil {
                t.Fatalf("ParseSize(%q) unexpected error: %v", tt.input, err)
            }
            if got != tt.want {
                t.Errorf("ParseSize(%q) = %d, want %d", tt.input, got, tt.want)
            }
        })
    }
}
```

Run a single subtest: `go test -run TestParseSize/kilobytes`.

## t.Helper() for Test Helpers

Failure messages report caller's line, not helper's.

```go
func assertStatusCode(t *testing.T, resp *http.Response, want int) {
    t.Helper()
    if resp.StatusCode != want {
        t.Errorf("status = %d, want %d", resp.StatusCode, want)
    }
}

func mustParseJSON[T any](t *testing.T, data []byte) T {
    t.Helper()
    var v T
    if err := json.Unmarshal(data, &v); err != nil {
        t.Fatalf("parse JSON: %v\ninput: %s", err, data)
    }
    return v
}
```

## t.Cleanup() for Teardown

Prefer over `defer` in helpers. Runs after test+subtests, even after `t.Fatal`.

```go
func setupTestDB(t *testing.T) *sql.DB {
    t.Helper()
    db, err := sql.Open("sqlite3", ":memory:")
    if err != nil {
        t.Fatalf("open db: %v", err)
    }
    t.Cleanup(func() {
        db.Close()
    })

    _, err = db.Exec(schema)
    if err != nil {
        t.Fatalf("apply schema: %v", err)
    }
    return db
}

func TestUserRepo(t *testing.T) {
    db := setupTestDB(t) // cleanup happens automatically after test
    repo := NewUserRepo(db)
    // ... test logic
}
```

## Testing with Interfaces (Dependency Injection)

Define small interfaces at point of use. Test with fakes.

```go
// In your production code: define a narrow interface
type EmailSender interface {
    Send(ctx context.Context, to, subject, body string) error
}

type OrderService struct {
    email EmailSender
}

func (s *OrderService) PlaceOrder(ctx context.Context, order Order) error {
    // ... process order ...
    return s.email.Send(ctx, order.CustomerEmail, "Order Confirmed", body)
}

// In your test file: provide a fake
type fakeEmailSender struct {
    sent []string
}

func (f *fakeEmailSender) Send(_ context.Context, to, subject, body string) error {
    f.sent = append(f.sent, to)
    return nil
}

func TestPlaceOrder(t *testing.T) {
    sender := &fakeEmailSender{}
    svc := &OrderService{email: sender}

    err := svc.PlaceOrder(context.Background(), Order{CustomerEmail: "user@test.com"})
    if err != nil {
        t.Fatalf("PlaceOrder: %v", err)
    }
    if len(sender.sent) != 1 || sender.sent[0] != "user@test.com" {
        t.Errorf("expected email to user@test.com, sent: %v", sender.sent)
    }
}
```

## httptest.NewServer for HTTP Testing

Point clients at a local test server.

```go
func TestFetchUser(t *testing.T) {
    server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        if r.URL.Path != "/users/42" {
            http.NotFound(w, r)
            return
        }
        w.Header().Set("Content-Type", "application/json")
        fmt.Fprint(w, `{"id": 42, "name": "Alice"}`)
    }))
    t.Cleanup(server.Close)

    client := NewAPIClient(server.URL) // point client at test server
    user, err := client.FetchUser(context.Background(), 42)
    if err != nil {
        t.Fatalf("FetchUser: %v", err)
    }
    if user.Name != "Alice" {
        t.Errorf("Name = %q, want Alice", user.Name)
    }
}
```

Handler testing without a server:
```go
func TestHealthHandler(t *testing.T) {
    req := httptest.NewRequest(http.MethodGet, "/health", nil)
    rec := httptest.NewRecorder()

    healthHandler(rec, req)

    if rec.Code != http.StatusOK {
        t.Errorf("status = %d, want 200", rec.Code)
    }
    if body := rec.Body.String(); body != "ok" {
        t.Errorf("body = %q, want ok", body)
    }
}
```

## Golden File Testing

Compare output against saved golden file. Update with `-update` flag.

```go
var update = flag.Bool("update", false, "update golden files")

func TestRenderTemplate(t *testing.T) {
    got := renderTemplate(sampleData)

    golden := filepath.Join("testdata", t.Name()+".golden")
    if *update {
        os.MkdirAll("testdata", 0o755)
        os.WriteFile(golden, []byte(got), 0o644)
        return
    }

    want, err := os.ReadFile(golden)
    if err != nil {
        t.Fatalf("read golden file: %v (run with -update to create)", err)
    }
    if diff := cmp.Diff(string(want), got); diff != "" {
        t.Errorf("output mismatch (-want +got):\n%s", diff)
    }
}
```

Update: `go test -run TestRenderTemplate -update`

## Benchmarks with b.ResetTimer

Exclude setup time from measurement.

```go
func BenchmarkSort(b *testing.B) {
    // Setup: generate test data (excluded from timing)
    data := make([]int, 10_000)
    for i := range data {
        data[i] = rand.IntN(100_000)
    }

    b.ResetTimer() // start timing here

    for range b.N {
        s := slices.Clone(data)
        slices.Sort(s)
    }
}

// Run: go test -bench BenchmarkSort -benchmem
// Output: BenchmarkSort-8  1234  890123 ns/op  80000 B/op  1 allocs/op
```

Use `b.ReportAllocs()` to always show allocation stats. Use `b.RunParallel` for concurrency benchmarks.

## Race Detection

```bash
go test -race ./...
```

Always enable in CI. 2-10x overhead — fine for tests, not production.

```go
// This test will fail with -race if the implementation has a data race
func TestConcurrentAccess(t *testing.T) {
    cache := NewCache()
    var wg sync.WaitGroup

    for range 100 {
        wg.Add(2)
        go func() {
            defer wg.Done()
            cache.Set("key", "value")
        }()
        go func() {
            defer wg.Done()
            _ = cache.Get("key")
        }()
    }
    wg.Wait()
}
```

## Fuzz Testing (Go 1.18+)

Random inputs to find unexpected edge cases.

```go
func FuzzParseSize(f *testing.F) {
    // Seed corpus: known inputs to start from
    f.Add("100B")
    f.Add("2KB")
    f.Add("1MB")
    f.Add("")
    f.Add("not-a-size")

    f.Fuzz(func(t *testing.T, input string) {
        size, err := ParseSize(input)
        if err != nil {
            return // invalid input is fine, just don't panic
        }
        // Property: valid sizes are non-negative
        if size < 0 {
            t.Errorf("ParseSize(%q) = %d, want non-negative", input, size)
        }
        // Property: roundtrip (if you have FormatSize)
        formatted := FormatSize(size)
        roundtrip, err := ParseSize(formatted)
        if err != nil {
            t.Errorf("roundtrip failed: ParseSize(%q) error: %v", formatted, err)
        }
        if roundtrip != size {
            t.Errorf("roundtrip: %d -> %q -> %d", size, formatted, roundtrip)
        }
    })
}
```

Run: `go test -fuzz FuzzParseSize -fuzztime 30s`

## testscript for CLI Testing

`github.com/rogpeppe/go-internal/testscript` — test CLI tools with script files.

```go
// In main_test.go
func TestMain(m *testing.M) {
    os.Exit(testscript.RunMain(m, map[string]func() int{
        "mycli": mainFunc, // register your CLI entry point
    }))
}

func TestCLI(t *testing.T) {
    testscript.Run(t, testscript.Params{
        Dir: "testdata/scripts",
    })
}
```

```
# testdata/scripts/basic.txtar
# Test basic usage
exec mycli --version
stdout 'mycli v1\.\d+\.\d+'

# Test with input file
exec mycli process input.txt
stdout 'processed 3 items'
! stderr .

-- input.txt --
line1
line2
line3
```

## Test Fixtures with t.TempDir

Auto-cleaned temporary directory.

```go
func TestWriteConfig(t *testing.T) {
    dir := t.TempDir() // auto-cleaned after test
    path := filepath.Join(dir, "config.yaml")

    err := WriteConfig(path, &Config{Port: 8080})
    if err != nil {
        t.Fatalf("WriteConfig: %v", err)
    }

    got, err := os.ReadFile(path)
    if err != nil {
        t.Fatalf("read written config: %v", err)
    }
    if !strings.Contains(string(got), "port: 8080") {
        t.Errorf("config missing port:\n%s", got)
    }
}
```
