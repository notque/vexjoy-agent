# Security review invariants

Review only newly introduced vulnerabilities in a diff, except when new code routes attacker-controlled data to an existing sink. Comments claiming upstream validation are not evidence.

Require an end-to-end path for injection, authorization, disclosure, SSRF, traversal, unsafe parsing, XSS, crypto/secret, OAuth state, CI/IaC, permission, and fail-open findings. In particular:

- argv avoids shell injection but not flag smuggling; insert `--` or reject leading options where the target CLI supports it.
- path normalization is not containment; resolve symlinks/real paths before proving the target remains below the allowed root.
- SSRF validation covers every resolved address and every redirect, with normalized hostname and userinfo-safe parsing.
- authorization checks the same object/tenant fields that the operation later uses; sibling endpoints and serializers need equivalent scoping.
- environment passed to a subprocess is an execution surface (`LD_PRELOAD`, `NODE_OPTIONS`, `PYTHONPATH`, `BASH_ENV`, `GIT_SSH_COMMAND`, `PATH`); prefer a cleared allowlist.
- security registries fan out: adding a credential/entity/alias may require sanitizer, redaction, revocation, and allowlist updates.
- gates stay fail-closed through parse errors, cancellation, retries, cache skew, unhandled variants, and exact boundary values.

Exclude generic hardening without an exploit path: ordinary timeouts/pagination/DoS, internal-only authentication, non-secret IDs/URLs, telemetry keys, trusted CLI/env-only paths, ORM-parameterized SQL, framework-escaped text, and pre-existing issues outside the diff. Internal-only does not excuse SSRF. Surface medium and above by default.

Each finding records `filePath`, category, exact vulnerable code/location, attacker path and impact, specific fix, and `critical | high | medium | low`. Read full changed files, find callers, inspect sibling handlers, and try to refute each candidate with cited guards before keeping it.
