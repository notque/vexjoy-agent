---
name: x-api
description: "Post tweets, build threads, upload media via the X API."
user-invocable: false
agent: python-general-engineer
allowed-tools:
  - Read
  - Write
  - Bash
  - Glob
routing:
  triggers:
    - post to X
    - post tweet
    - tweet this
    - build thread
    - post thread
    - twitter thread
    - x api
    - upload media to X
    - read timeline
    - search X
    - search twitter
    - publish to X
    - publish to twitter
  pairs_with:
    - content-engine
  complexity: Medium
  category: content-publishing
---

# X API Skill

## Overview

OAuth-authenticated, rate-limit-aware X/Twitter API interactions via `scripts/x-api-poster.py`. 4-phase pipeline with explicit confirmation gate (Phase 2) to prevent accidental public posts.

- Validate credentials and content before any network call
- Confirm gate is mechanically enforced (script refuses writes without `--confirmed`)
- Credentials flow from environment variables only
- Rate limits surfaced immediately if remaining capacity drops below 10

---

## Instructions

### Phase 1: VALIDATE

**Goal**: Confirm credentials, content, and dependencies before any network call.

**Step 1: Check credentials**

```bash
python3 $HOME/.claude/scripts/x-api-poster.py post --dry-run --text "ping"
```

Required env vars: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_SECRET`, `X_BEARER_TOKEN`.
- Read-only ops (timeline, search): only `X_BEARER_TOKEN`
- Write ops (post, thread): all five
- If missing, script exits with clear error; surface it and stop
- Never pass credentials as arguments or store in files

**Step 2: Validate content length**

```bash
python3 $HOME/.claude/scripts/x-api-poster.py post --dry-run --text "your tweet text here"
```

For threads:
```bash
python3 $HOME/.claude/scripts/x-api-poster.py thread --dry-run --texts "part 1" "part 2" "part 3"
```

If length error, ask user to shorten or approve auto-segmentation into thread.

**Gate**: Dry run exits 0, content validates, credentials confirmed.

---

### Phase 2: CONFIRM

**Goal**: Show exact content and require explicit approval before writing. X posts are public and irreversible.

```
CONTENT PREVIEW
================
Tweet 1/1:
  "Your tweet text here"
  Characters: 42/280

Action: POST single tweet

Approve? [yes/no]
```

For threads:
```
CONTENT PREVIEW
================
Tweet 1/3:
  "First part text"
Tweet 2/3:
  "Second part text"
Tweet 3/3:
  "Third part text"

Action: POST thread (3 tweets, chained replies)

Approve? [yes/no]
```

**Wait for explicit typed approval** ("yes", "approve", "go ahead", "post it"). Do not infer from context or prior turns. Do not pass `--confirmed` before approval.

**Gate**: User typed explicit approval in this conversation turn.

---

### Phase 3: POST

**Goal**: Execute write operation and capture tweet IDs.

**Single tweet:**
```bash
python3 $HOME/.claude/scripts/x-api-poster.py post \
  --confirmed \
  --text "your tweet text here"
```

**Thread:**
```bash
python3 $HOME/.claude/scripts/x-api-poster.py thread \
  --confirmed \
  --texts "part 1" "part 2" "part 3"
```

**With media:**
```bash
python3 $HOME/.claude/scripts/x-api-poster.py post \
  --confirmed \
  --text "your tweet text here" \
  --media /absolute/path/to/image.jpg
```

Media: images <= 5 MB (JPG, PNG, GIF); videos <= 512 MB (MP4). Two-step upload; no orphaned media on failure. Confirm file exists and format supported.

Watch output for:
- `[tweet-posted] id=... url=...` — success (canonical URL: https://x.com/i/web/status/{id})
- `[rate-limit-warning] remaining=N reset=EPOCH` — surface immediately
- `ERROR:` — surface verbatim and stop

OAuth mode is automatic: reads use Bearer token, writes use full OAuth 1.0a.

**Gate**: Script exits 0, at least one `[tweet-posted]` line.

---

### Phase 4: REPORT

**Goal**: Return tweet URLs, IDs, and engagement baseline.

1. Parse `[tweet-posted] id=... url=...` lines from Phase 3
2. Optionally read engagement baseline:
   ```bash
   python3 $HOME/.claude/scripts/x-api-poster.py read-timeline --user-id me --max-results 5
   ```
   Metrics have propagation delay; 0 impressions immediately after posting is expected.
3. Report: tweet URL(s), ID(s), thread structure if applicable, rate limit warnings, engagement baseline with async growth note.

---

## Error Handling

### "Missing required environment variable: X_API_KEY"
Verify all five variables exported. Read-only needs only `X_BEARER_TOKEN`; writes need all five. Never pass as arguments.

### "Tweet text exceeds 280 characters"
Shorten manually, or approve auto-segmentation into thread (splits on sentence boundaries).

### "Write operation requires --confirmed flag"
Return to Phase 2, present confirm gate, obtain explicit approval.

### "403 Forbidden" or "401 Unauthorized"
Verify app has Read+Write permissions. Regenerate tokens after permission changes. Confirm app attached to Project in developer portal.

### "429 Too Many Requests"
Check x-rate-limit-reset timestamp. Wait until reset epoch. Rate limits are per-15-minute window; N-tweet thread consumes N requests.

### "Media upload failed at step 1/2"
Confirm file exists, supported format (JPG, PNG, GIF, MP4), and size (images <= 5 MB, videos <= 512 MB). Re-run; no partial attachment on failure.

---

## References

- `$HOME/.claude/scripts/x-api-poster.py`: Backing script (exit codes: 0=success, 1=missing credentials, 2=content validation failed, 3=API error, 4=write without --confirmed)
- X API v2: https://developer.twitter.com/en/docs/twitter-api
- X media upload (v1.1): https://developer.twitter.com/en/docs/twitter-api/v1/media/upload-media/api-reference/post-media-upload
