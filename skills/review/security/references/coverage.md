# Security Review Coverage Reference

The LLM-depth review taxonomy ported from Anthropic's `security-guidance` plugin
(`llm.py` + `review_api.py`). The session agent reviewing the diff applies this
to reach detection parity with the plugin's reviewer — without an SDK or API
key. The deterministic scanner (`scripts/security-review-scan.py`) handles the
syntactic patterns; this file covers what regex cannot: data flow, authorization,
and missing-control reasoning.

Load this when running Phase 3 (LLM-depth review) of `SKILL.md`.

---

## 1. Vulnerability classes (40)

Review every changed file against each class. Surface a finding only with a
concrete path from untrusted input to a dangerous sink. Each entry: **what + fix**.

### Injection & code execution
1. **Command injection** — user input reaching `exec.Command("sh","-c",...)`, `os.system`, `subprocess(..., shell=True)`, backticks. Fix: argv list, no shell; validate input format.
2. **Command injection via shell wrappers & indirect sources** — custom `sudo()`/`shell()`/`run()` helpers whose body runs a shell are the same sink. Taint sources include manifests, lockfiles, image labels, tarball entries, S3/GCS keys. `basename`/prefix-checks preserve `$(…)`/`;`/`|`. Fix: `shlex.quote()` each segment or argv list.
3. **Argument injection (argv flag smuggling)** — a value starting with `-` becomes a flag even with no shell (`rg --pre=`, `git --upload-pack=`, `tar --checkpoint-action=exec=`, `curl -o`, `ssh -oProxyCommand=`). Fix: insert `--` before untrusted value; reject `/^-/`.
4. **Dynamic code evaluation** — ANY string interpolated into `eval`/`new Function`/`Function()`/`exec`. Source need not be HTTP — DB column names, config, file paths qualify. Fix: safe property access / expression parser.
5. **SQL injection** — user input concatenated/f-string/`%`/`.format` into SQL. Fix: parameterized queries.
6. **Environment variable injection into subprocess** — untrusted map spread into `env` of spawn/exec is RCE via `LD_PRELOAD`, `NODE_OPTIONS`, `PYTHONPATH`, `BASH_ENV`, `GIT_SSH_COMMAND`, `IFS`, `PATH`. Incomplete denylists bypassable. Fix: `env_clear()` + explicit allowlist.
7. **Orchestrator template injection (Airflow/Argo/Tekton)** — `{{ dag_run.conf[...] }}`, `{{workflow.parameters.*}}`, `$(params.*)` rendered into a shell string are user-settable via trigger API. Fix: pass as separate argv/env. Do not flag scheduler-only macros (`{{ ds }}`).

### Deserialization & parsing
8. **Unsafe deserialization** — untrusted bytes to `pickle.load(s)`, `torch.load` w/o `weights_only=True`, `yaml.load` w/o `SafeLoader`, `joblib.load`, `cloudpickle`, `marshal.loads`, PHP `unserialize`, Java `ObjectInputStream`. Fix: JSON/msgspec or schema-validated deserializer.
9. **XXE / XML entity expansion** — untrusted XML (uploaded docx/xlsx/svg, SOAP/SAML, feeds) to stdlib `xml.etree.ElementTree`, `minidom`, `xml.sax`, Java `DocumentBuilderFactory`, lxml `resolve_entities=True`. Fix: `defusedxml`; disable DTD/external entities.

### XSS family
10. **XSS — autoescape off / wrong escaper** — `jinja2.Environment()` w/o `autoescape`, Go `text/template` to HTTP, Handlebars `{{{triple}}}`, React `dangerouslySetInnerHTML`; escapers that omit `"`/`'` and feed an attribute. Fix: enable autoescape / context-aware escaper.
11. **XSS via manual HTML/markdown building** — string-formatting HTML (`f"<div>{val}</div>"`, `fmt.Fprintf(w,"<span>%s</span>",v)`). Audit each `{var}` individually; one nearby `escape()` is not proof. Markdown via `rehypeRaw` w/o `rehypeSanitize`, `marked()` to `dangerouslySetInnerHTML` w/o DOMPurify. File-serve with stored `text/html` Content-Type, no CSP. Fix: escape each interpolation; sanitize markdown.
12. **Sibling validator/sanitizer asymmetry** — one field gets a refinement/sanitizer while a sibling field of the same role reaching the same sink does not. The `+` line adding the refinement to one place is the cue — check every sibling.

### Authorization & data exposure
13. **Authorization (IDOR / scoping / visibility)** — `findById(id)`/`objects.get(id=id)` without ownership check; `objects.all()` for non-admin; FK ID from request body unchecked; an interaction endpoint skipping the read endpoint's visibility check; route under `/{tenant_id}/` whose handler never reads that param. The check's ABSENCE on a scoped resource is the vuln.
14. **Unfiltered serialization / nested data exposure** — `to_dict`/`to_json`/schema including related records must filter by the VIEWING user's permissions, not the parent's. Lives in the model layer, not the route.
15. **Unfiltered entity choices in forms** — select fields choosing related entities must restrict to authorized ones (Symfony `query_builder`/`choices`). Server-side validation of submitted values required.
16. **Secrets/PII in logs, URLs, or errors** — logger/print emitting token/secret/password/PII or user content; bearer tokens in URL query strings; `str(exc)`/`traceback` returned in HTTP responses; telemetry `before_send` omitting `event['request']`. Fix: redact; keep credentials out of sinks observers read.
17. **Spoofable-field auth bypass** — auth decision keyed on client-settable `X-Forwarded-For`, `Host`, `Origin`, `X-User-*`, or body `is_admin`/`role` without trusted-infra verification. Flag only when it GRANTS access AND no upstream proxy strips the header.

### Network & transport
18. **SSRF** — user-influenceable URL/host reaching `requests`/`httpx`/`fetch`/`axios`/`http.Get`, OAuth/OIDC discovery fields, webhooks, storage clients. Taint sources include project config (`.mcp.json`, `package.json`), manifests. A validator checking only scheme/format is not a defense — must reject loopback/RFC1918/link-local AFTER DNS of ALL `getaddrinfo` results, with `host.rstrip('.').lower()`. Redirects re-introduce SSRF. Fix: `redirect:'manual'` + re-validate each hop.
19. **SSRF URL-allowlist bypass** — (a) userinfo: compare only `hostname`, not `netloc`; (b) base-resolution: `new URL(userPath, base)` doesn't pin host; (c) string-suffix `endswith('.trusted.com')` on interpolated host; (d) missing `.lower().rstrip('.')`; (e) redirect-following.
20. **Substring/unanchored allowlist bypass** — gate matching by substring (`allowed in value`, `strings.Contains`, unanchored `re.search`) or unanchored prefix/suffix; denylist alias bypass (`=0`/`=no`, `JaVaScRiPt:`); case-sensitive compare where consumer is case-insensitive. Fix: parse structured field, `==` against allowlist, anchor regex both ends.
21. **TLS verification disabled / plaintext transport** — `verify=False`, `InsecureSkipVerify:true`, `rejectUnauthorized:false`, `NODE_TLS_REJECT_UNAUTHORIZED=0`, `grpc.insecure_channel`, `sslmode=disable`. Do NOT flag `localhost`/`127.0.0.1`/unix-socket/test fixtures.
22. **Open redirect** — `redirect(request.args.get('next'))` without validation. Fix: require relative path (`/` not `//`) or framework safe-redirect. Skip URL shorteners/proxies where redirect IS the feature.

### Crypto & secrets
23. **Insecure password hashing** — MD5/SHA1/SHA256/fast-unsalted for passwords. Fix: bcrypt/scrypt/argon2/PBKDF2.
24. **Weak cryptographic primitives** — `random`/`Math.random()`/`math/rand` for tokens/session IDs/nonces; entropy < 128 bits for access-gating values (< 64 for weaker). Fix: `secrets`/`crypto.randomBytes`/`crypto/rand` + adequate size. Also: AES-ECB, `createCipher` (no IV).
25. **Hardcoded secrets** — passwords/API keys/private keys/credential connection strings in source/config.
26. **Hardcoded framework secrets** — Flask/Django `SECRET_KEY`, Express session `secret`, `spring.datasource.password`, `DEBUG=True` with static value. Fix: read from env.
27. **Nonstandard credential prefix** — generated token using a custom prefix instead of `sk-`/`ghp_`/`AKIA` defeats secret scanners. Flag only at a token-generation site for a real credential.

### OAuth / OIDC
28. **OAuth/OIDC state forgery** — `state` decoded as plain base64 JSON without HMAC verify / session-cookie compare / server nonce — attacker-forgeable. Comparing a field from forged state is a no-op. Flag even when the diff is "adding the comparison as a CSRF fix".
29. **Unauthenticated token minting** — handler returning `access_token`/`sessionId`/`apiKey` that reads only `req.query`/`req.body`, never `req.user`/`req.auth`/middleware.

### IaC / CI / agents
30. **GitHub Actions injection** — `github.event.*` (issue/PR title/body, comment, client_payload) into `run:`/`ref:`. Fix: env var + quoting; validate `pr_number` `^[0-9]+$`. Skip `inputs.*` on `workflow_dispatch`.
31. **GitHub Actions third-party unpinned** — `uses:` a third-party action by mutable tag/branch (not 40-char SHA) when workflow has write perms or passes secrets. Skip first-party `actions/*`.
32. **Agent/subprocess permission bypass** — spawning Claude/subagent with `--dangerously-skip-permissions`/`bypassPermissions` or unrestricted Bash without an isolation boundary or command classifier.
33. **Overly permissive IAM/RBAC** — binding beyond stated purpose: write where read suffices, project/bucket-wide where one resource needed, primitive role (Owner/Editor), OIDC trust `sub` ending `:*`.
34. **Insecure file permissions on credential writes** — token/secret/lockfile written world-readable: no mode (umask 0o644), explicit 0o666/0o644, or write-then-chmod race. On multi-user hosts → disclosure → privesc.

### Logic & state
35. **Fail-open gates** — a new security-gate param is safe only if enforced unconditionally OR denies when its enabling condition is False. Execution continuing past an unchecked gate = fail-open; broad-except→pass, `unwrap_or({})`, missing-finally, stale validator maps, boundary-value-permissive.
36. **CSRF disabled** — CSRF protection explicitly turned off in framework config.
37. **Boolean type coercion (Python)** — `bool("false")` is True; `request.form.get('is_public', True)` insecure. Fix: explicit `value.lower() in ('true','1','yes')`.
38. **Arbitrary file access from client parameters** — `file_get_contents($params['viewFile'])` / path from HTTP request without allowlist. Fix: `realpath()`, restrict dirs, reject `..`.
39. **Path traversal** — user input into file paths; `filepath.Join`/`os.path.join`/`Paths.resolve` do NOT prevent `..`. `path.resolve()`/`Clean()` is lexical — symlink-bypassable. Fix: `realpath`/`EvalSymlinks` FIRST, then `startsWith(realpath(baseDir))`.
40. **Data flow to pre-existing dangerous sinks** — new code routing user data to an existing `eval`/`exec`/shell/SQL sink IS a new vuln even though the sink is unchanged. Cite both the new flow and the pre-existing sink.

---

## 2. Severity rubric (4-tier; surface medium+)

| Severity | Definition |
|----------|------------|
| **critical** | Actively exploitable RCE, auth bypass, data breach |
| **high** | Significant vuln: IDOR, SQLi, XSS, SSRF, unsafe deserialization |
| **medium** | Defense-in-depth: CSRF, missing headers, lower-severity SSRF (path-only) |
| **low** | Best-practice improvement |

Surface **medium and above**. Drop low (too many false positives). Keep scanning
after the first finding — a file can have multiple independent issues.

---

## 3. False-positive exclusions (do NOT flag)

- Missing authentication on a service described **internal/VPN-only** — BUT internal-only does NOT excuse SSRF (internal services are the primary SSRF target; metadata endpoints always blocked).
- Missing HTTPS/TLS, rate limiting, input length validation.
- **DoS** concerns: missing timeouts, pagination, unbounded loops, memory exhaustion (best-practice, not exploitable). EXCEPTION: a code defect that defeats an existing resource cap.
- Pre-existing issues unrelated to the current change (when a diff is provided).
- Non-credential config: project IDs, dataset/table/service names, hostnames, ports, file paths, public-API URLs. Only flag ACTUAL secrets.
- Development fallback secrets (`os.environ.get('SECRET_KEY','dev-fallback')`).
- Framework secrets in dev/example/seed/test files (only flag in production config).
- Path traversal where the path is NOT user-controlled (hardcoded, config, CLI args, internal params — env vars and CLI args are trusted).
- XSS in code that doesn't handle HTTP/render HTML (CLI tools, backend, data scripts). React auto-escapes text — but flag `dangerouslySetInnerHTML` with user input.
- Open redirect / SSRF in code where URLs are not user-controlled.
- **ORM-safe SQL**: parameterized queries, ORMs, query builders.
- GitHub Actions injection where the only taint is `inputs.*` on `workflow_dispatch`, or value lands in `with:` not `run:`.
- Theoretical race/timing attacks; log spoofing; crashes from undefined vars/type errors (bugs, not vulns).
- **Telemetry/analytics keys** (Honeycomb, Datadog, Sentry) — designed to be client-side.
- Vulnerabilities in pre-existing starter/template code not written this session.

**Diff scope rule:** flag only vulnerabilities NEWLY INTRODUCED on `+` lines. A
pattern present in context (space-prefixed) or re-added from `-` lines is
pre-existing. EXCEPTION: `+` lines routing user data to a pre-existing sink.

**Distrust safety claims:** comments asserting "validated upstream"/"SSRF-safe"
are claims, not evidence. Verify the invariant holds in visible code.

---

## 4. Per-language guidance

| Language | Watch for |
|----------|-----------|
| **Go** | `exec.Command("sh",...)`; `filepath.Join` does not stop `..`; `text/template` vs `html/template` to `ResponseWriter`; `tls.Config{InsecureSkipVerify:true}` safe only with `VerifyConnection` checking chain+EKU+hostname; `db.Query("...$1", x)` for params; `math/rand` for security values. |
| **Python** | `pickle`/`yaml.load`/`torch.load` deserialization; stdlib XML → use `defusedxml`; `os.system`/`subprocess(shell=True)`; `bool("false")` coercion; `redirect(request.args['next'])`; MD5/SHA for passwords; `random` not `secrets`; f-string SQL. |
| **JS/TS** | `child_process.exec`/`execSync`; `new Function`; `.innerHTML`/`dangerouslySetInnerHTML`/`insertAdjacentHTML`; `crypto.createCipher`; `rejectUnauthorized:false`; `Math.random()` for tokens; prototype pollution; `eval`. |
| **Java** | `ObjectInputStream` deserialization; `DocumentBuilderFactory`/`SAXParserFactory` XXE (`disallow-doctype-decl`); all-trusting `TrustManager`/`HostnameVerifier`; `Paths.get().resolve()` traversal; `spring.datasource.password` hardcoded. |
| **PHP** | `unserialize()`; `simplexml_load_*` with `LIBXML_NOENT`; `file_get_contents($_GET[...])` file access; `eval()`; string-concat SQL. |
| **EJS** | `<%- variable %>` outputs UNESCAPED HTML (XSS); `<%= %>` escapes; only `<%- include(...) %>` is safe. |
| **Django** | `mark_safe()`/`|safe` on non-literal; `redirect(request.GET['next'])` open redirect; raw `SECRET_KEY`; use `url_has_allowed_host_and_scheme`. |
| **Jinja** | `jinja2.Environment()` defaults `autoescape=False` (Flask `render_template` enables it; raw `Environment()` does not); `{{var}}` lacking `|e` reaching an HTML sink. |

Note: `html.escape()` is NOT sufficient inside JS event-handler attributes
(`onclick`) — the browser HTML-decodes before executing. Use `json.dumps()`/
`JSON.stringify()` for JS contexts.

---

## 5. High-miss reviewer checklist (12, from review_api.py)

Run as a final sweep — these are the classes the plugin's investigate stage
specifically targets because they are most often missed. Check ONLY `+` lines.

1. **Sensitive-to-observability** — a `+` line emits to log/trace/span/metric/exception; trace EVERY field (URLs, `.message`, f-string vars, `**kwargs`) to source; flag credentials/PII/customer content, especially on error branches.
2. **IaC omitted arg** — a `+` line instantiates a Terraform/Pulumi/CDK module omitting a security-relevant optional arg whose default is insecure.
3. **CI/CD trust** — `+` lines add `workflow_dispatch`/`repository_dispatch`/`pull_request_target` without `branches:` filter while the job reads secrets or has write perms.
4. **Allowlist semantic escape** — `+` adds a safe-command/endpoint/capability allowlist entry or a `||` disjunct to a permission matcher; verify no allowed entry achieves a denied effect via args/flags/scope mismatch (allowlist matches `argv[0]` but consumer reads full argv).
5. **Over-broad grant** — `+` adds a principal to a broad-scope permission when the same module exposes a narrower mechanism for the same need.
6. **Stale identity mapping** — `+` changes teardown/unregister of hostname/DNS/IP/route/lease/token where a window leaves it resolvable to the wrong tenant.
7. **Control regression** — `-` deletes a fail-closed validator (deny-by-default) and `+` replaces it with a single condition.
8. **Fail-open state drift** — a decision reads parsed/cached/callback state; verify error/cancel/TOCTOU/cache-skew/unhandled-variant paths don't default to allow. Exact-boundary-value permissive; retry overriding a stricter first decision.
9. **Security-registry fanout** — `+` adds an entity (field/enum/credential type/alias/port/scope); Grep unchanged files for every registry keyed on that class (sanitizer lists, redaction sets, revocation handlers, allowlists) and flag missing entries. Conversely, verify added registry entries match the consumer's key format.
10. **Gate/action field mismatch** — `+` adds/modifies an authz check; if the field(s) the gate READS differ from the field(s) the operation USES to select the target, the gate is bypassable.
11. **Resource-bound placement** — `+` parses/decompresses/loops over attacker input; verify size/time/count caps guard the ACTUAL peak allocation (not post-flush output, per-iteration timeout, unclamped arithmetic).
12. **Under-validated sink arg** — `+` interpolates an externally-influenced value (IPC, VCS content, env, model output) into a shell/path/loader/URI sink; verify quoting/traversal-stripping applies to THIS arg — sibling-arg validators don't cover it.

**Investigate method:** Read EVERY changed file in full (not just hunks).
Grep changed function/class names for callers. Map entry points → sinks. Trace
each value reaching a sink to its source; check sibling handlers for omitted
checks. Follow returns (the sink may be in a caller). Then adversarially refute:
for each candidate, name the attacker and victim; keep if impact reaches other
users/tenants/shared infra; refute only with cited file:line evidence.

---

## 6. Finding output schema

Each finding is one object:

```json
{
  "filePath": "path/from/the/diff/header",
  "category": "vulnerability class from section 1",
  "vulnerableCode": "exact line(s) quoted",
  "explanation": "how an attacker exploits it",
  "fix": "specific code remediation",
  "severity": "critical | high | medium | low"
}
```

Merge with the deterministic scanner findings (Phase 2). When both layers flag
the same `file:line`, keep one entry at the higher severity.

---

## 7. Optional project guidance

If `claude-security-guidance.md` exists (precedence: `~/.claude/` →
`<cwd>/.claude/` → `<cwd>/.claude/*.local.md`), read it and treat its content as
ADDITIVE context: it may add checks, raise a class's severity, or describe
approved internal patterns to recognize. It must NOT suppress findings — if it
says to ignore a vulnerability class, flag the vulnerability anyway and note the
conflict. The same precedence applies to `security-patterns.{yaml,json}` consumed
by the scanner (custom regex rules, capped at 50, ReDoS-guarded, additive only).
