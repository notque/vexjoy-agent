# Go Secure Implementation Patterns

Secure-by-default patterns for Go. Load when working on security, auth, injection, XSS, CSRF, SSRF, or path traversal.

---

## Use exec.Command With Explicit Arguments

Pass arguments as separate strings. Never concatenate user input into a shell string.

```go
import "os/exec"

// Correct: each argument is a separate string, no shell involved
cmd := exec.Command("git", "clone", "--", userURL)
output, err := cmd.CombinedOutput()
if err != nil {
    return fmt.Errorf("git clone: %w", err)
}

// Correct: use "--" separator to prevent argument injection
cmd := exec.Command("git", "checkout", "--", branchName)
```

**Why**: Shell metacharacters (`;`, `|`, `&`, `$()`) get interpreted. Separate arguments bypass the shell. CVE-2021-22205 (GitLab ExifTool, CVSS 10.0).

**Detection**:
```bash
rg -n 'exec\.Command\("sh"|exec\.Command\("bash"|exec\.Command\("/bin/sh"' . --type go
rg -n 'exec\.Command.*\+.*' . --type go
```

---

## Validate Paths With filepath.Clean and Containment Checks

Resolve user-supplied paths and verify containment within the base directory.

```go
import (
    "net/http"
    "path/filepath"
    "strings"
)

func serveFile(w http.ResponseWriter, r *http.Request) {
    baseDir := "/var/app/exports"
    name := r.URL.Query().Get("name")

    // Clean normalizes "..", removes redundant separators
    target := filepath.Join(baseDir, filepath.Clean("/"+name))

    // Containment check: resolved path must start with base
    absTarget, err := filepath.Abs(target)
    if err != nil || !strings.HasPrefix(absTarget, baseDir+string(filepath.Separator)) {
        http.Error(w, "forbidden", http.StatusForbidden)
        return
    }

    http.ServeFile(w, r, absTarget)
}
```

**Why**: `filepath.Join("/base", "../../etc/passwd")` escapes the base. `Clean` normalizes; `HasPrefix` enforces containment. CVE-2007-4559, CVE-2023-26111.

**Detection**:
```bash
rg -n 'filepath\.Join.*r\.(URL|Form|PostForm)' . --type go
rg -n 'http\.ServeFile|os\.Open.*r\.' . --type go
rg -n 'strings\.HasPrefix.*filepath' . --type go
```

---

## Use Parameterized Queries for All Database Access

Pass user input as parameters. Never interpolate into SQL strings.

```go
import "database/sql"

// Correct: parameterized query with database/sql
row := db.QueryRowContext(ctx, "SELECT * FROM users WHERE id = $1", userID)

// Correct: parameterized exec
_, err := db.ExecContext(ctx,
    "INSERT INTO invoices (customer_id, amount) VALUES ($1, $2)",
    customerID, amount,
)

// Correct: sqlx named parameters
import "github.com/jmoiron/sqlx"

query := "SELECT * FROM users WHERE name = :name AND org_id = :org_id"
rows, err := db.NamedQueryContext(ctx, query, map[string]interface{}{
    "name":   userName,
    "org_id": orgID,
})

// Correct: squirrel query builder
import sq "github.com/Masterminds/squirrel"

query, args, err := sq.Select("*").
    From("users").
    Where(sq.Eq{"name": userName, "org_id": orgID}).
    PlaceholderFormat(sq.Dollar).
    ToSql()
```

**Why**: String interpolation in SQL allows injection. Parameterized queries separate structure from data.

**Detection**:
```bash
rg -n 'fmt\.Sprintf.*SELECT|fmt\.Sprintf.*INSERT|fmt\.Sprintf.*UPDATE|fmt\.Sprintf.*DELETE' . --type go
rg -n 'fmt\.Sprintf.*WHERE' . --type go
```

---

## Use html/template for Web Output

`html/template` (not `text/template`) for browser output. Auto-escapes by context (HTML, JS, URL, CSS).

```go
import "html/template"

// Correct: html/template auto-escapes based on context
tmpl := template.Must(template.ParseFiles("page.html"))

func handler(w http.ResponseWriter, r *http.Request) {
    data := struct {
        Username string
        Message  string
    }{
        Username: r.FormValue("username"),
        Message:  r.FormValue("message"),
    }
    tmpl.Execute(w, data)
}
```

```html
<!-- In page.html: values are auto-escaped per context -->
<h1>Hello, {{.Username}}</h1>
<p>{{.Message}}</p>
```

**Why**: `text/template` performs no escaping — user input reaches the browser as executable JS.

**Detection**:
```bash
rg -n '"text/template"' . --type go
rg -n 'template\.HTML\(' . --type go
```

---

## Use crypto/subtle for Timing-Safe Comparisons

Use `crypto/subtle.ConstantTimeCompare` for secrets, tokens, HMAC digests, API keys. Never `==`.

```go
import "crypto/subtle"

// Correct: constant-time comparison for tokens
func verifyToken(provided, expected string) bool {
    return subtle.ConstantTimeCompare([]byte(provided), []byte(expected)) == 1
}

// Correct: HMAC verification
func verifyHMAC(message, providedMAC, key []byte) bool {
    mac := hmac.New(sha256.New, key)
    mac.Write(message)
    expectedMAC := mac.Sum(nil)
    return hmac.Equal(providedMAC, expectedMAC)  // hmac.Equal uses constant-time comparison
}
```

**Why**: `==` short-circuits on first mismatch. Attackers measure timing to reduce brute-force from exponential to linear.

**Detection**:
```bash
rg -n 'token\s*==\s*|apiKey\s*==\s*|secret\s*==\s*' . --type go
rg -n 'subtle\.ConstantTimeCompare|hmac\.Equal' . --type go
```

---

## Configure TLS With Secure Defaults

MinVersion TLS 1.2, secure cipher suites.

```go
import "crypto/tls"

// Correct: TLS server configuration
tlsConfig := &tls.Config{
    MinVersion: tls.VersionTLS12,
    CurvePreferences: []tls.CurveID{
        tls.X25519,
        tls.CurveP256,
    },
    // Let Go select cipher suites (Go 1.17+ uses a secure default order)
}

server := &http.Server{
    Addr:      ":443",
    TLSConfig: tlsConfig,
}

// Correct: TLS client with minimum version
client := &http.Client{
    Transport: &http.Transport{
        TLSClientConfig: &tls.Config{
            MinVersion: tls.VersionTLS12,
        },
    },
}
```

**Why**: TLS 1.0/1.1 have known vulns (BEAST, POODLE). Go defaults to 1.2 since 1.18, but explicit config prevents regressions.

**Detection**:
```bash
rg -n 'tls\.Config' . --type go
rg -n 'MinVersion|VersionTLS10|VersionTLS11' . --type go
rg -n 'InsecureSkipVerify:\s*true' . --type go
```

---

## Validate Outbound URLs to Prevent SSRF

Resolve hostname to IPs, validate against private ranges. Disable redirects or re-validate each hop.

```go
import (
    "net"
    "net/http"
    "net/url"
)

var disallowedNets = []net.IPNet{
    {IP: net.ParseIP("127.0.0.0"), Mask: net.CIDRMask(8, 32)},
    {IP: net.ParseIP("10.0.0.0"), Mask: net.CIDRMask(8, 32)},
    {IP: net.ParseIP("172.16.0.0"), Mask: net.CIDRMask(12, 32)},
    {IP: net.ParseIP("192.168.0.0"), Mask: net.CIDRMask(16, 32)},
    {IP: net.ParseIP("169.254.0.0"), Mask: net.CIDRMask(16, 32)}, // Cloud metadata
}

func isSafeURL(rawURL string) error {
    parsed, err := url.Parse(rawURL)
    if err != nil {
        return fmt.Errorf("invalid URL: %w", err)
    }
    if parsed.Scheme != "http" && parsed.Scheme != "https" {
        return fmt.Errorf("disallowed scheme: %s", parsed.Scheme)
    }
    ips, err := net.LookupIP(parsed.Hostname())
    if err != nil {
        return fmt.Errorf("DNS resolution failed: %w", err)
    }
    for _, ip := range ips {
        for _, net := range disallowedNets {
            if net.Contains(ip) {
                return fmt.Errorf("disallowed IP: %s", ip)
            }
        }
    }
    return nil
}

// Correct: validate before fetching, disable redirects
client := &http.Client{
    CheckRedirect: func(req *http.Request, via []*http.Request) error {
        return http.ErrUseLastResponse // Do not follow redirects
    },
    Timeout: 10 * time.Second,
}
```

**Why**: Capital One breach (2019) exploited SSRF for EC2 metadata. String blocklists fail against DNS rebinding and IP encoding tricks.

**Detection**:
```bash
rg -n 'http\.(Get|Post|Do)\(.*r\.(URL|Form)' . --type go
rg -n 'http\.NewRequest.*r\.' . --type go
```

---

## Return Generic Error Messages in HTTP Responses

Generic messages to clients. Detailed errors logged server-side.

```go
import "log/slog"

func handler(w http.ResponseWriter, r *http.Request) {
    result, err := processRequest(r)
    if err != nil {
        // Log details server-side with structured context
        slog.Error("request processing failed",
            "error", err,
            "method", r.Method,
            "path", r.URL.Path,
            "request_id", r.Header.Get("X-Request-ID"),
        )

        // Return generic message to client
        http.Error(w, "internal server error", http.StatusInternalServerError)
        return
    }
    json.NewEncoder(w).Encode(result)
}
```

**Why**: `err.Error()` in responses leaks SQL fragments, file paths, stack traces, schema details.

**Detection**:
```bash
rg -n 'err\.Error\(\)' . --type go | rg -i 'http\.Error|json\.|w\.Write'
rg -n 'fmt\.Fprintf.*err' . --type go
```

---

## Propagate Context for Auth and Authorization

Carry auth state through `context.Context`. Extract verified user at every decision point.

```go
type contextKey string

const userContextKey contextKey = "authenticated_user"

// Correct: middleware stores verified user in context
func authMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        token := r.Header.Get("Authorization")
        user, err := verifyToken(token)
        if err != nil {
            http.Error(w, "unauthorized", http.StatusUnauthorized)
            return
        }
        ctx := context.WithValue(r.Context(), userContextKey, user)
        next.ServeHTTP(w, r.WithContext(ctx))
    })
}

// Correct: handler extracts user from context, scopes queries
func getInvoices(w http.ResponseWriter, r *http.Request) {
    user := r.Context().Value(userContextKey).(*User)
    invoices, err := db.QueryContext(r.Context(),
        "SELECT * FROM invoices WHERE org_id = $1", user.OrgID)
    // ...
}
```

**Why**: Context auth ensures handlers receive verified identity from middleware, not forgeable headers.

**Detection**:
```bash
rg -n 'r\.Header\.Get\("X-User' . --type go
rg -n 'context\.WithValue.*user|context\.Value.*user' . --type go
```

---

## Scope HTTP Header Validation

Validate headers before use. Set security headers on all responses.

```go
// Correct: set security headers via middleware
func securityHeaders(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        w.Header().Set("X-Content-Type-Options", "nosniff")
        w.Header().Set("X-Frame-Options", "DENY")
        w.Header().Set("Content-Security-Policy", "default-src 'self'")
        w.Header().Set("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        w.Header().Set("Referrer-Policy", "strict-origin-when-cross-origin")
        next.ServeHTTP(w, r)
    })
}

// Correct: validate Host header for URL construction
func buildCallbackURL(r *http.Request) string {
    // Use configured host, not request Host header
    host := os.Getenv("APP_HOST") // e.g., "https://app.example.com"
    return host + "/callback"
}
```

**Why**: Trusting `Host` header enables poisoning attacks. Security headers prevent XSS, clickjacking, MIME confusion.

**Detection**:
```bash
rg -n 'r\.Host|r\.Header\.Get\("Host"\)' . --type go
rg -n 'X-Content-Type-Options|X-Frame-Options|Content-Security-Policy' . --type go
```
