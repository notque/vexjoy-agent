# Source Verification

`--check-urls` enables HTTP HEAD verification of registry source URLs. The verification
step is best-effort and degrades gracefully — it never blocks the audit.

## Behavior

| Outcome | HTTP signal | Recorded as | Affects exit code? |
|---|---|---|---|
| Reachable | 200 / 301 / 302 / 403 / 405 | `reachable: true` | No |
| Definitively unreachable | 4xx (except 403/405), 5xx | `reachable: false` | Yes (exit 2 if any) |
| Network error | timeout, DNS failure, TLS failure | `reachable: null` (WARN) | No |

403 and 405 are treated as reachable: many security feed pages reject HEAD with
"Method Not Allowed" or block bots, but the URL still resolves and serves content
to a browser.

## Why HEAD instead of GET

- HEAD avoids downloading large advisory archives.
- Most servers honor HEAD with the same routing as GET.
- Failures are still informative: a 404 from HEAD is a 404 from GET.

## Timeout

5 seconds per URL. Each URL is checked at most once per run (results cached on the
URL string). For a registry of ~22 entries with 2–3 sources each, the worst case is
under 4 minutes; the typical case is under 30 seconds.

## When `--check-urls` is appropriate

| Situation | Run with `--check-urls`? |
|---|---|
| CI / scheduled audit | Yes — catches link rot early. |
| Offline laptop / no network | No. The audit works fully offline without the flag. |
| Restricted egress (corporate proxy) | Set `HTTPS_PROXY` env var; or omit the flag. |
| One-shot audit during PR review | Optional. Skip if network is flaky. |

## Reading the report

In Markdown, each source cell shows `[ok]`, `[DOWN]`, or `[—]`:

- `[ok]` — server responded with a reachable status.
- `[DOWN]` — server responded with a clear error status. Investigate.
- `[—]` — network error or check skipped. No conclusion drawn.

In JSON, the same information is in each source's `reachable` field as
`true` / `false` / `null`.

## Failure handling

A single unreachable URL does not abort the run. The script continues, records the
state, and surfaces the count in the summary. Exit code 2 is set only when at least
one source returned a definitive failure AND `--check-urls` was passed.
