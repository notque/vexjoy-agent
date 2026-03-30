# Testing Patterns -- Detailed Reference

Comprehensive testing patterns from `sapcc/keppel`. Full examples for assert.HTTPRequest, easypg, test doubles, fixtures, and all test conventions.

---

## 1. Test File Organization

### Location and Package Naming

All test files live alongside the code they test. No separate `test/` directories for test files. Shared test utilities live in `internal/test/`.

**External test packages** (black-box testing) -- used for API-level integration tests:
```
internal/api/keppel/*_test.go    -> package keppelv1_test
internal/api/registry/*_test.go  -> package registryv2_test
internal/api/auth/*_test.go      -> package authapi_test
internal/api/peer/*_test.go      -> package peerv1_test
internal/client/*_test.go        -> package client_test
```

**Same-package tests** (white-box testing) -- used for unit tests and internal task tests:
```
internal/tasks/*_test.go         -> package tasks
internal/keppel/*_test.go        -> package keppel
internal/models/*_test.go        -> package models
internal/auth/*_test.go          -> package auth
internal/stringy/*_test.go       -> package stringy
internal/drivers/basic/*_test.go -> package basic
```

**Rule**: API packages use external test packages (`_test` suffix). Internal logic packages use same-package tests.

### shared_test.go Pattern

Each test directory that needs shared setup has a `shared_test.go` file containing:
- `TestMain(m *testing.M)` for database setup via `easypg.WithTestDB`
- Shared helper functions for that test suite
- Common variables and constants

---

## 2. Test Setup Architecture

### The `test.Setup` Struct

All integration tests use `test.NewSetup(t, ...options)` which returns everything needed:

```go
type Setup struct {
    Config       keppel.Configuration
    DB           *keppel.DB
    Clock        *mock.Clock
    SIDGenerator *StorageIDGenerator
    Auditor      *audittools.MockAuditor
    AD           *AuthDriver
    AMD          *basic.AccountManagementDriver
    FD           *FederationDriver
    SD           *trivial.StorageDriver
    ICD          *InboundCacheDriver
    Handler      http.Handler
    Ctx          context.Context
    Registry     *prometheus.Registry
    TrivyDouble  *TrivyDouble
    Accounts     []*models.Account
    Repos        []*models.Repository
}
```

### Functional Options Pattern

Setup is configured via functional options:

```go
s := test.NewSetup(t,
    test.WithKeppelAPI,
    test.WithPeerAPI,
    test.WithAnycast(true),
    test.WithAccount(models.Account{Name: "test1", AuthTenantID: "test1authtenant"}),
    test.WithRepo(models.Repository{AccountName: "test1", Name: "foo"}),
    test.WithQuotas,
    test.WithTrivyDouble,
    test.WithPreviousIssuerKey,
    test.WithoutCurrentIssuerKey,
    test.WithRateLimitEngine(rle),
    test.IsSecondaryTo(&s1),
)
```

### Complete Option Reference

| Option | Purpose |
|--------|---------|
| `WithKeppelAPI` | Enables the Keppel v1 API handler |
| `WithPeerAPI` | Enables the peer API handler |
| `WithAnycast(bool)` | Fills anycast configuration fields |
| `WithAccount(account)` | Inserts an account into the test DB |
| `WithRepo(repo)` | Inserts a repository into the test DB |
| `WithQuotas` | Sets up ample quotas for all accounts |
| `WithTrivyDouble` | Sets up a Trivy test double at trivy.example.org |
| `WithPreviousIssuerKey` | Adds the "previous" test issuer keys |
| `WithoutCurrentIssuerKey` | Omits the "current" test issuer keys |
| `WithRateLimitEngine(rle)` | Sets up Redis-backed rate limiting (uses miniredis) |
| `IsSecondaryTo(&s)` | Configures as a secondary registry peered with primary |

### Per-Package Setup Helpers

Each test package wraps `test.NewSetup` with its own convenience function:

```go
// internal/tasks/shared_test.go
func setup(t *testing.T, opts ...test.SetupOption) (*Janitor, test.Setup) {
    params := []test.SetupOption{
        test.WithKeppelAPI,
        test.WithPeerAPI,
        test.WithAccount(models.Account{Name: "test1", AuthTenantID: "test1authtenant"}),
        test.WithRepo(models.Repository{AccountName: "test1", Name: "foo"}),
        test.WithQuotas,
    }
    s := test.NewSetup(t, append(params, opts...)...)
    j := NewJanitor(s.Config, s.FD, s.SD, s.ICD, s.DB, s.AMD, s.Auditor).
        OverrideTimeNow(s.Clock.Now).
        OverrideGenerateStorageID(s.SIDGenerator.Next)
    j.DisableJitter()
    return j, s
}
```

### TestMain Pattern

Every package with database tests has exactly this:

```go
func TestMain(m *testing.M) {
    easypg.WithTestDB(m, func() int { return m.Run() })
}
```

This is the ONLY way `TestMain` is used. It wraps the test run with a test database lifecycle.

---

## 3. Assertion Library

### Primary: `github.com/sapcc/go-bits/assert`

All assertions come from `go-bits/assert`. There is NO use of testify or similar third-party assertion libraries.

### Core Assertion Functions

**`assert.Equal[V comparable](t, actual, expected)`** -- 3 args, uses `==`:
```go
assert.Equal(t, matches, tc.matches)
assert.Equal(t, len(events), 3)
assert.Equal(t, event.ID, "event-1")
```

**`assert.DeepEqual[V any](t, description, actual, expected)`** -- 4 args, uses `reflect.DeepEqual`:
```go
assert.DeepEqual(t, "token.Audience for "+requestInfo, token.Audience, c.Audience)
assert.DeepEqual(t, fmt.Sprintf("matches %q", tc.input), matches, tc.expected)
assert.DeepEqual(t, "CADF events", events, expectedEvents)
```

**Equal vs DeepEqual decision rule**: If the type supports `==` (int, string, bool, int64, float64), use `Equal` (3 args). If not (slices, maps, structs with non-comparable fields), use `DeepEqual` (4 args with label). Common mistake flagged in review: using `DeepEqual` for `int`/`string` comparisons -- it works but pulls in `reflect.DeepEqual` unnecessarily.

**`assert.ErrEqual(t, actualErr, expectedErr)`** -- flexible error comparison:
```go
assert.ErrEqual(t, sweepBlobsJob.ProcessOne(s.Ctx), nil)           // expect no error
assert.ErrEqual(t, sweepBlobsJob.ProcessOne(s.Ctx), sql.ErrNoRows) // expect "no work"
assert.ErrEqual(t, validateBlobJob.ProcessOne(s.Ctx), "expected digest sha256:..., but got sha256:...")
```

Can compare against `nil`, `sql.ErrNoRows`, or a string (matched against `err.Error()`).

**`must.SucceedT(t, err)`** -- abort immediately on error:
```go
must.SucceedT(t, s.DB.Insert(account))
must.SucceedT(t, s.DB.Db.Close())
must.SucceedT(t, json.Unmarshal(respBodyBytes, &respBody))
```

**`must.ReturnT(value, err)(t)`** -- curried form, extract value or fail:
```go
blob := must.ReturnT(keppel.FindBlobByRepositoryName(s.DB, ...))(t)
count := must.ReturnT(db.SelectInt(`SELECT COUNT(*) FROM blobs`))(t)
key := must.ReturnT(keppel.ParseIssuerKey(...))(t)
```

### Custom Assertion Types

**`test.ErrorCode(code)`** -- for Registry V2 error codes:
```go
ExpectBody: test.ErrorCode(keppel.ErrDenied)
```

**`test.ErrorCodeWithMessage{Code, Message}`** -- with message matching:
```go
ExpectBody: test.ErrorCodeWithMessage{
    Code:    keppel.ErrManifestUnknown,
    Message: "no such manifest",
}
```

**`jwtContents{}`** -- custom `assert.HTTPResponseBody` for JWT token validation in auth tests.

### Standard Library Assertions

Some tests use raw `t.Errorf`/`t.Error` for custom logic:
```go
if count > 0 {
    t.Errorf("expected 0 blobs in the DB, but found %d blobs", count)
}
```

### must vs assert: When to Use Which

The `must` and `assert` packages serve **different purposes** and are NOT interchangeable:

- **`assert.*`** calls `t.Errorf` -> **non-fatal**, test continues and reports ALL failures
- **`must.*`** calls `t.Fatal` -> **fatal**, test stops immediately

| Context | Use | Why |
|---------|-----|-----|
| `mustXxx` helper function body | `must.SucceedT` / `must.ReturnT` | Function name says "must" -- it MUST succeed or test dies |
| Setup/precondition in test body | `must.SucceedT` / `must.ReturnT` | Next lines depend on this succeeding |
| Checking expected outcome of the tested operation | `assert.ErrEqual(t, err, nil)` | Non-fatal -- test continues, reports ALL failures |
| Need return value from a fallible call | `must.ReturnT` | No assert equivalent exists |

**Decision tree:**
1. Inside a `mustXxx` helper function? -> `must.SucceedT` or `must.ReturnT`
2. Does the next line need this result to not be meaningless? -> `must.SucceedT` / `must.ReturnT`
3. Checking the outcome of the thing being tested? -> `assert.ErrEqual(t, err, nil)`
4. Need a return value from a fallible call? -> `must.ReturnT`

```go
// HELPER -- must.SucceedT (fatal, precondition)
func mustWrite(t *testing.T, store *FileBackingStore, event cadf.Event) {
    t.Helper()
    must.SucceedT(t, store.Write(event))
}

// TEST ASSERTION -- assert.ErrEqual (non-fatal, report all failures)
func TestNewAuditor(t *testing.T) {
    auditor, err := newTestAuditor(t, opts)
    assert.ErrEqual(t, err, nil)       // assertion: did it work?
}

// SETUP in test body -- must.SucceedT (fatal, next lines depend on this)
func TestMetrics(t *testing.T) {
    must.SucceedT(t, store.UpdateMetrics())             // setup: must work
    families := must.ReturnT(registry.Gather())(t)      // setup: need the value
    assert.Equal(t, len(families), 3)                   // assertion: check result
}
```

**The rule: helper = must, assertion = assert.**

### Forbidden Libraries

NO testify, NO gomock, NO external assertion libraries -- only `go-bits/assert` and `go-bits/must`.

---

## 4. assert.HTTPRequest -- Complete Examples

### Full Pattern

```go
assert.HTTPRequest{
    Method:       "PUT",
    Path:         "/keppel/v1/accounts/first",
    Header:       map[string]string{"X-Test-Perms": "change:tenant1"},
    Body: assert.JSONObject{
        "account": assert.JSONObject{
            "auth_tenant_id": "tenant1",
        },
    },
    ExpectStatus: http.StatusOK,
    ExpectHeader: map[string]string{
        test.VersionHeaderKey: test.VersionHeaderValue,
    },
    ExpectBody: assert.JSONObject{
        "account": assert.JSONObject{
            "name":           "first",
            "auth_tenant_id": "tenant1",
        },
    },
}.Check(t, h)
```

### Body Assertion Types

| Type | Usage |
|------|-------|
| `assert.JSONObject{...}` | JSON object comparison (recursive) |
| `[]assert.JSONObject{...}` | JSON array of objects |
| `assert.StringData("text")` | Plain string body |
| `assert.ByteData(bytes)` | Raw byte body |
| `test.ErrorCode(code)` | Registry V2 error response |
| Custom implementations | Any type implementing `assert.HTTPResponseBody` |

### Authentication in Tests

**Keppel API tests** -- permissions via `X-Test-Perms` header:
```go
Header: map[string]string{"X-Test-Perms": "view:tenant1,change:tenant1"}
```

**Registry V2 API tests** -- real Bearer tokens via `s.GetToken()`:
```go
token := s.GetToken(t, "repository:test1/foo:pull,push")
Header: map[string]string{"Authorization": "Bearer " + token}
```

### RoundTripper Mock

Tests involving cross-service communication use `test.WithRoundTripper()`:
```go
test.WithRoundTripper(func(tt *test.RoundTripper) {
    // tt.Handlers["registry.example.org"] = handler
    // tests run here...
})
```

### Version Header

All Registry V2 responses must include the Docker Distribution API version header:
```go
ExpectHeader: test.VersionHeader  // {"Docker-Distribution-Api-Version": "registry/2.0"}
```

---

## 5. Database Testing with easypg

### Mode 1: Full DB Snapshot (`easypg.AssertDBContent`)

Compares the entire database state against a `.sql` fixture file:
```go
easypg.AssertDBContent(t, s.DB.Db, "fixtures/blob-sweep-001.sql")
```

Fixture files contain sorted INSERT statements representing the expected full DB state.

### Mode 2: Change Tracking (`easypg.NewTracker` / `DBChanges`)

Tracks incremental changes from a baseline:

```go
tr, tr0 := easypg.NewTracker(t, s.DB.Db)
tr0.AssertEqualToFile("fixtures/manifest-sync-setup.sql")  // assert initial state
tr0.AssertEmpty()  // assert no data exists

// ... run some operation ...

tr.DBChanges().AssertEqualf(`
    UPDATE repos SET next_manifest_sync_at = %d WHERE id = 1 AND account_name = 'test1' AND name = 'foo';
`, s1.Clock.Now().Add(1*time.Hour).Unix())

tr.DBChanges().AssertEmpty()  // nothing else changed
```

### DBChanges Methods

| Method | Purpose |
|--------|---------|
| `.AssertEmpty()` | No changes since last check |
| `.AssertEqual(sql)` | Exact match of changes |
| `.AssertEqualf(fmt, args...)` | Formatted match of changes |
| `.AssertEqualToFile(path)` | Match against a fixture file |

### Test Database Setup

```go
// In TestMain
easypg.WithTestDB(m, func() int { return m.Run() })

// In NewSetup
easypg.ConnectForTest(t, keppel.DBConfiguration(), opts...)

// Secondary databases
easypg.OverrideDatabaseName(t.Name()+"_secondary")

// Table management between tests
easypg.ClearTables(...)
easypg.ClearContentsWith(...)
easypg.ResetPrimaryKeys(...)
```

### Direct SQL Execution

```go
test.MustExec(t, s.DB, `DELETE FROM blob_mounts WHERE blob_id IN ($1,$2,$3)`, id1, id2, id3)
test.MustExec(t, s.DB, `UPDATE accounts SET is_deleting = TRUE WHERE name = $1`, "test1")
```

### Time Control with mock.Clock

```go
s.Clock.StepBy(1 * time.Hour)
s.Clock.StepBy(8 * 24 * time.Hour)
s.Clock.Now()
```

Never use `time.Now()` or `time.Sleep()` in tests.

---

## 6. Fixture Patterns

### Fixture File Types

| Type | Count | Purpose |
|------|-------|---------|
| `.sql` | 39 | Database state snapshots (INSERT statements) |
| `.json` | 12 | API response fixtures, Trivy report fixtures |

### SQL Fixture Format

Pure INSERT statements, sorted alphabetically by table name, then by primary key:

```sql
INSERT INTO accounts (name, auth_tenant_id, next_blob_sweep_at) VALUES ('test1', 'test1authtenant', 7200);

INSERT INTO blob_mounts (blob_id, repo_id) VALUES (1, 1);
INSERT INTO blob_mounts (blob_id, repo_id) VALUES (2, 1);

INSERT INTO blobs (id, account_name, digest, size_bytes, storage_id, pushed_at, next_validation_at) VALUES (1, 'test1', 'sha256:...', 1048919, '6b86b...', 3600, 608400);
```

### Fixture Location

```
internal/tasks/fixtures/blob-sweep-001.sql
internal/tasks/fixtures/blob-sweep-002.sql
internal/api/registry/fixtures/imagemanifest-001-before-upload-blob.sql
internal/api/keppel/fixtures/before-delete-repo.sql
```

### Fixture Naming Convention

- Sequential numbering: `blob-sweep-001.sql`, `blob-sweep-002.sql`, `blob-sweep-003.sql`
- State descriptions: `before-delete-repo.sql`, `after-delete-manifest.sql`
- Combined: `imagemanifest-003-after-upload-manifest-by-tag.sql`
- Setup files: `manifest-sync-setup-on_first_use.sql`

### `.actual` / `.expected` Pattern

When `easypg.AssertDBContent` fails, it writes the actual state to a `.actual` file next to the expected file. Running `make copy-fixtures` promotes all `.actual` files:

```make
copy-fixtures:
	find -name '*.actual' | xargs -I{} bash -c 'mv {} $$(echo {} | sed "s/.actual//g")'
```

---

## 7. Test Doubles Implementation

### Driver-Based Doubles

Test doubles implement the same driver interfaces as production code, registered via `init()`:

```go
func init() {
    keppel.AuthDriverRegistry.Add(func() keppel.AuthDriver { return &AuthDriver{} })
}
```

### Complete Double Inventory

| Double | Real Interface | Purpose |
|--------|---------------|---------|
| `test.AuthDriver` | `keppel.AuthDriver` | Permission checking, user auth |
| `test.FederationDriver` | `keppel.FederationDriver` | Account claiming, peering |
| `test.InboundCacheDriver` | `keppel.InboundCacheDriver` | Caching replicated content |
| `trivial.StorageDriver` | `keppel.StorageDriver` | In-memory blob/manifest storage |
| `test.TrivyDouble` | HTTP handler | Trivy vulnerability scanner |

### Mock Components from go-bits

| Component | Type | Purpose |
|-----------|------|---------|
| `mock.Clock` | `*mock.Clock` | Deterministic time control (starts at Unix epoch, only advances via `StepBy`) |
| `audittools.MockAuditor` | `*audittools.MockAuditor` | Capture and assert audit events |

### Storage ID Generator

Deterministic, SHA-256-based generator for reproducible tests:
```go
type StorageIDGenerator struct{ n uint64 }
func (g *StorageIDGenerator) Next() string {
    g.n++
    hashBytes := sha256.Sum256([]byte(strconv.FormatUint(g.n, 10)))
    return hex.EncodeToString(hashBytes[:])
}
```

### Override Methods Pattern

Production code exposes `.Override*()` methods for test injection:
```go
j := NewJanitor(s.Config, ...).
    OverrideTimeNow(s.Clock.Now).
    OverrideGenerateStorageID(s.SIDGenerator.Next)
j.DisableJitter()
```

---

## 8. Table-Driven Test Patterns

### Classic Struct Slice

```go
var durationTestCases = []struct {
    Value        time.Duration
    ExpectedJSON string
}{
    {90 * time.Second, `{"value":90,"unit":"s"}`},
    {120 * time.Second, `{"value":2,"unit":"m"}`},
    // ...
}

func TestDurationMarshalling(t *testing.T) {
    for _, c := range durationTestCases {
        // test logic...
    }
}
```

### Named Type for Complex Cases

```go
type TestCase struct {
    Scope          string
    AnonymousLogin bool
    CannotPush     bool
    CannotPull     bool
    CannotDelete   bool
    RBACPolicy     *keppel.RBACPolicy
    GrantedActions   string
    AdditionalScopes []string
}

var testCases = []TestCase{
    {Scope: "repository:test1/foo:pull", GrantedActions: "pull"},
    // ...
}
```

### Logging Index in Loops

When iterating over test cases, the current index is logged:
```go
for idx, c := range testCases {
    t.Logf("----- testcase %d/%d -----\n", idx+1, len(testCases))
    // ...
}
```

**Note**: `t.Run` subtests are RARE -- only 1 occurrence in the entire codebase. The project strongly prefers logging test case indices over using subtests.

---

## 9. Content Generation Helpers

### Deterministic Image Generation

```go
layer1 := test.GenerateExampleLayer(1)        // 1 MiB gzipped blob from seed 1
layer2 := test.GenerateExampleLayerSize(2, 5)  // 5 MiB gzipped blob from seed 2
image := test.GenerateImage(layer1, layer2)    // Docker manifest + config
imageList := test.GenerateImageList(img1, img2) // Multi-arch manifest list
ociImage := test.GenerateOCIImage(ociArgs, layers...) // OCI image
```

Results are memoized for commonly used seeds (0-9).

### MustUpload Helpers

Upload content through the actual API and fail on error:
```go
blob := layer.MustUpload(t, s, repoRef)           // returns models.Blob
manifest := image.MustUpload(t, s, repoRef, "tag") // returns models.Manifest
manifest := imageList.MustUpload(t, s, repoRef, "")
```

These helpers also verify the upload succeeded by checking the database and storage.

---

## 10. Integration Test Patterns

### Scenario Wrapper Functions

Complex test scenarios use wrapper functions for multiple configurations:

```go
func testWithPrimary(t *testing.T, setupOptions []test.SetupOption, action func(test.Setup)) {
    test.WithRoundTripper(func(tt *test.RoundTripper) {
        for _, withAnycast := range []bool{false, true} {
            opts := append(slices.Clone(setupOptions),
                test.WithAnycast(withAnycast),
                test.WithAccount(...),
            )
            s := test.NewSetup(t, opts...)
            action(s)
            must.SucceedT(t, s.DB.Db.Close())
        }
    })
}
```

### Replication Testing Pattern

Primary/secondary setups for testing replication:
```go
func testWithAllReplicaTypes(t *testing.T, s1 test.Setup, action func(strategy string, firstPass bool, s test.Setup)) {
    for _, strategy := range []string{"on_first_use", "from_external_on_first_use"} {
        testWithReplica(t, s1, strategy, func(firstPass bool, s2 test.Setup) {
            action(strategy, firstPass, s2)
        })
    }
}
```

The `firstPass` parameter indicates whether the primary is reachable (first pass) or the network is severed (second pass).

### Job Processing Pattern

Background jobs are tested by calling `ProcessOne` repeatedly:
```go
assert.ErrEqual(t, job.ProcessOne(s.Ctx), nil)           // processed one item
assert.ErrEqual(t, job.ProcessOne(s.Ctx), nil)           // processed another
assert.ErrEqual(t, job.ProcessOne(s.Ctx), sql.ErrNoRows) // nothing left
easypg.AssertDBContent(t, s.DB.Db, "fixtures/expected-state.sql")
```

The pattern of checking `sql.ErrNoRows` confirms the job queue is drained.

---

## 11. Audit Event Testing

```go
s.Auditor.ExpectEvents(t, cadf.Event{
    RequestPath: "/keppel/v1/accounts/first",
    Action:      cadf.CreateAction,
    Outcome:     "success",
    Reason:      test.CADFReasonOK,
    Target: cadf.Resource{
        TypeURI:   "docker-registry/account",
        ID:        "first",
        ProjectID: "tenant1",
    },
})

// Expect no events:
s.Auditor.ExpectEvents(t)
```

---

## 12. Test Execution Configuration

### Makefile Command

```
go test -shuffle=on -p 1 -coverprofile=build/coverprofile.out -covermode=count -coverpkg=<internal-packages> ./...
```

### Flags Explained

| Flag | Value | Purpose |
|------|-------|---------|
| `-shuffle=on` | Randomize test order within packages |
| `-p 1` | Run packages sequentially (shared test database) |
| `-covermode=count` | Count-based coverage (not just boolean hit/miss) |
| `-coverpkg=...` | Coverage for `internal/` packages excluding `drivers` and `test/util` |
| `-mod vendor` | Use vendored dependencies |

No race detection (`-race`) is included -- tests share a real PostgreSQL database and race detection would produce false positives from concurrent DB access.

---

## 13. Complete Rules Summary

1. **Use `test.NewSetup(t, ...options)` for all integration tests** -- never construct Setup manually
2. **Use `easypg.WithTestDB` in `TestMain`** for every package that touches the database
3. **Use `assert.HTTPRequest{}.Check(t, h)` for all HTTP tests** -- never use `httptest.NewRecorder` directly
4. **Use `assert.ErrEqual` for error comparison**, not `if err != nil` patterns
5. **Use `must.SucceedT` / `must.ReturnT` to abort early** on setup failures
6. **Use `easypg.AssertDBContent` for full state snapshots**, `easypg.NewTracker` for incremental changes
7. **SQL fixtures are the source of truth** for expected database state; update via `make copy-fixtures`
8. **Use `test.MustExec` for direct DB manipulation** in test setup
9. **Control time with `s.Clock.StepBy()`** -- never use `time.Now()` or `time.Sleep()` in tests
10. **Use `test.GenerateExampleLayer` / `test.GenerateImage`** for deterministic test content
11. **Use `MustUpload` helpers** to upload content through the real API stack
12. **External test packages for API tests**, same-package for internal logic
13. **Log test case index** with `t.Logf("----- testcase %d/%d -----")` rather than using `t.Run`
14. **Close DB connections** in loops that create multiple setups to avoid "too many clients" errors
15. **Tests run sequentially** across packages (`-p 1`) due to shared database
16. **Test order is shuffled** within packages (`-shuffle=on`)
17. **Driver interfaces are tested via registered test doubles**, not mock libraries
18. **Production code provides `Override*` methods** for injecting test clocks and ID generators
19. **No testify, no gomock, no external assertion libraries** -- only `go-bits/assert` and `go-bits/must`
20. **Fixture files use sorted INSERT statements** with all non-default column values spelled out
