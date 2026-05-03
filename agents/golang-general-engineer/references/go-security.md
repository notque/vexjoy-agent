# Go Secure Implementation Patterns

Secure-by-default patterns for Go applications. Each section shows what correct code looks like and why it matters. Load this reference when the task involves security, auth, injection, XSS, CSRF, SSRF, path traversal, or any vulnerability-related code.

---

## Use exec.Command With Explicit Arguments

Pass command arguments as separate strings to `exec.Command`. Never concatenate user input into a shell string.

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

**Why this matters**: `exec.Command("sh", "-c", "git clone "+userURL)` passes the string through a shell where metacharacters (`;`, `|`, `&`, `$()`) are interpreted. `exec.Command` with separate arguments bypasses the shell entirely, sending each argument as a single argv entry. CVE-2021-22205 (GitLab ExifTool, CVSS 10.0) demonstrated command injection through shelled invocation.

**Detection**:
```bash
rg -n 'exec\.Command\("sh"|exec\.Command\("bash"|exec\.Command\("/bin/sh"' . --type go
rg -n 'exec\.Command.*\+.*' . --type go
```

---

## Validate Paths With filepath.Clean and Containment Checks

When serving or reading files based on user input, resolve the path and verify it stays within the intended base directory.

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

**Why this matters**: `filepath.Join("/base", userInput)` does not prevent traversal. If `userInput` is `../../etc/passwd`, the result escapes the base directory. `filepath.Clean` normalizes the path, and the `HasPrefix` check ensures containment. CVE-2007-4559 (Python tarfile) and CVE-2023-26111 (node-static) are canonical path traversal incidents applicable to any language.

**Detection**:
```bash
rg -n 'filepath\.Join.*r\.(URL|Form|PostForm)' . --type go
rg -n 'http\.ServeFile|os\.Open.*r\.' . --type go
rg -n 'strings\.HasPrefix.*filepath' . --type go
```

---

## Use Parameterized Queries for All Database Access

Pass user input as parameters, never interpolate into SQL strings with `fmt.Sprintf` or string concatenation.

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

**Why this matters**: `fmt.Sprintf("SELECT * FROM users WHERE name = '%s'", name)` allows SQL injection through string interpolation. Parameterized queries separate SQL structure from data, preventing injection regardless of input content.

**Detection**:
```bash
rg -n 'fmt\.Sprintf.*SELECT|fmt\.Sprintf.*INSERT|fmt\.Sprintf.*UPDATE|fmt\.Sprintf.*DELETE' . --type go
rg -n 'fmt\.Sprintf.*WHERE' . --type go
```

---

## Use html/template for Web Output

Use `html/template` (not `text/template`) for any output that reaches a web browser. `html/template` auto-escapes values based on context (HTML, JavaScript, URL, CSS).

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

**Why this matters**: `text/template` performs no escaping. If user input contains `<script>alert(1)</script>`, it reaches the browser verbatim as executable JavaScript. `html/template` applies context-aware escaping: HTML-entity-encodes in element content, JS-encodes in script contexts, URL-encodes in href attributes.

**Detection**:
```bash
rg -n '"text/template"' . --type go
rg -n 'template\.HTML\(' . --type go
```

---

## Use crypto/subtle for Timing-Safe Comparisons

Compare secrets, tokens, HMAC digests, and API keys using `crypto/subtle.ConstantTimeCompare`. Never use `==` or `bytes.Equal` for security-critical comparisons.

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

**Why this matters**: `==` short-circuits on the first mismatched byte. An attacker can measure response time differences to determine how many leading bytes of a token match, reducing a brute-force attack from exponential to linear time.

**Detection**:
```bash
rg -n 'token\s*==\s*|apiKey\s*==\s*|secret\s*==\s*' . --type go
rg -n 'subtle\.ConstantTimeCompare|hmac\.Equal' . --type go
```

---

## Configure TLS With Secure Defaults

Set minimum TLS version to 1.2 and use secure cipher suites when configuring TLS servers or clients.

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

**Why this matters**: TLS 1.0 and 1.1 have known vulnerabilities (BEAST, POODLE). Go's default `tls.Config` already uses TLS 1.2 minimum since Go 1.18, but explicit configuration documents the intent and prevents regressions when custom configs are needed.

**Detection**:
```bash
rg -n 'tls\.Config' . --type go
rg -n 'MinVersion|VersionTLS10|VersionTLS11' . --type go
rg -n 'InsecureSkipVerify:\s*true' . --type go
```

---

## Validate Outbound URLs to Prevent SSRF

When making HTTP requests to user-supplied URLs, resolve the hostname to IP addresses and validate against private/internal ranges. Disable redirect following or re-validate on each hop.

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

**Why this matters**: The Capital One breach (2019) exploited SSRF to steal IAM credentials from the EC2 metadata service. String-based blocklists fail against DNS rebinding, IP encoding tricks (`0xa9fea9fe`, `[::ffff:169.254.169.254]`), and redirects.

**Detection**:
```bash
rg -n 'http\.(Get|Post|Do)\(.*r\.(URL|Form)' . --type go
rg -n 'http\.NewRequest.*r\.' . --type go
```

---

## Return Generic Error Messages in HTTP Responses

Return generic error messages to clients. Log detailed error information server-side with structured logging.

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

**Why this matters**: `http.Error(w, err.Error(), 500)` often leaks SQL query fragments, internal file paths, stack traces, database schema details, and configuration values. These details help attackers map internal architecture and craft targeted attacks.

**Detection**:
```bash
rg -n 'err\.Error\(\)' . --type go | rg -i 'http\.Error|json\.|w\.Write'
rg -n 'fmt\.Fprintf.*err' . --type go
```

---

## Propagate Context for Auth and Authorization Decisions

Carry authentication and authorization state through `context.Context`. Extract the authenticated user from context at every decision point rather than trusting headers or parameters.

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

**Why this matters**: Storing auth state in context ensures every handler receives verified identity from middleware, not from raw request headers an attacker could forge. Context propagation also carries cancellation and deadline signals, preventing orphaned goroutines from outliving their request.

**Detection**:
```bash
rg -n 'r\.Header\.Get\("X-User' . --type go
rg -n 'context\.WithValue.*user|context\.Value.*user' . --type go
```

---

## Scope HTTP Header Validation

Validate and sanitize HTTP headers before use. Set security headers on all responses.

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

**Why this matters**: Trusting the `Host` header for URL construction enables Host-header poisoning attacks, where password-reset emails contain attacker-controlled URLs. Security headers prevent XSS, clickjacking, and MIME-type confusion.

**Detection**:
```bash
rg -n 'r\.Host|r\.Header\.Get\("Host"\)' . --type go
rg -n 'X-Content-Type-Options|X-Frame-Options|Content-Security-Policy' . --type go
```
