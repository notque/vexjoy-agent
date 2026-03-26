---
name: x-api
description: |
  Post tweets, build threads, upload media, and read timelines via the X API.
  Use when user wants to publish content to X/Twitter, post a thread, upload
  media with a tweet, read a timeline, or search X. Pairs with content-engine
  (generate content) and crosspost (distribute to multiple platforms).
  Do NOT use for Instagram, LinkedIn, or other social platforms.
version: 1.0.0
user-invocable: false
agent: python-general-engineer
model: sonnet
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
    - crosspost
  complexity: Medium
  category: content-publishing
---

# X API Skill

## Operator Context

This skill operates as an operator for X/Twitter API interactions, configuring behavior for OAuth-authenticated, rate-limit-aware API calls via a deterministic Python script. It implements a 4-phase pipeline: VALIDATE -> CONFIRM -> POST -> REPORT.

The confirm gate (Phase 2) is mechanically enforced. The script refuses all write operations without --confirmed. The skill only passes --confirmed after receiving explicit user approval in the conversation -- it never passes the flag pre-emptively.

### Hardcoded Behaviors (Always Apply)

- **VALIDATE First**: Always run Phase 1 credential and content checks before any network call
- **CONFIRM Gate is Mandatory**: Never pass --confirmed without explicit user approval in Phase 2
- **OAuth Mode is Automatic**: Read ops use Bearer token only; write ops require full OAuth 1.0a -- operator never configures this
- **Credential Source**: Credentials come from environment variables only -- never from files, arguments, or conversation context
- **Rate Limit Respect**: Surface [rate-limit-warning] output immediately; do not proceed if remaining < 10 without user acknowledgment
- **No Direct HTTP**: The skill never constructs HTTP requests -- all network calls go through scripts/x-api-poster.py

### Default Behaviors (ON unless disabled)

- **Dry Run Preview**: Run --dry-run before any write to confirm content length and credentials
- **Thread Segmentation**: Auto-segment content exceeding 280 chars into thread parts
- **Tweet URL Reporting**: Return canonical tweet URL (https://x.com/i/web/status/{id}) after each post
- **Engagement Baseline**: Read public_metrics after post to establish initial engagement snapshot

### Optional Behaviors (OFF unless enabled)

- **Media Upload**: Attach image/video to tweet with --media /path/to/file
- **Schedule Awareness**: User may ask to post at a specific time -- note the script posts immediately; scheduling requires external orchestration
- **Search**: Read-only timeline/search operations with read-timeline or search commands

---

## What This Skill CAN Do

- Post a single tweet and return its ID and URL
- Build a thread by chaining replies from a list of tweet texts
- Upload media (image/video) and attach it to a tweet
- Read a user home timeline (read-only, Bearer token)
- Search recent tweets by keyword or hashtag
- Validate content length and credential presence without posting (--dry-run)
- Warn when rate limit headroom is low (remaining < 10)

## What This Skill CANNOT Do

- Post to platforms other than X/Twitter
- Schedule posts for future delivery (posts immediately)
- Edit or delete existing tweets
- Access Twitter API v1.1 for anything except media upload (as required by the platform)
- Generate content -- use content-engine for that
- Operate without environment variables set

---

## Instructions

### Phase 1: VALIDATE

**Goal**: Confirm credentials, content, and dependencies before any network call.

**Step 1: Check credentials**

```bash
python3 $HOME/.claude/scripts/x-api-poster.py post --dry-run --text "ping"
```

A clean dry-run output confirms all required env vars are present (X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, X_BEARER_TOKEN). If any are missing, the script exits with a clear error -- surface it to the user and stop.

**Step 2: Validate content length**

For a single tweet:
```bash
python3 $HOME/.claude/scripts/x-api-poster.py post --dry-run --text "your tweet text here"
```

For a thread:
```bash
python3 $HOME/.claude/scripts/x-api-poster.py thread --dry-run --texts "part 1" "part 2" "part 3"
```

The script enforces 280-character limit per tweet. If --dry-run reports a length error, ask the user to shorten the text or approve auto-segmentation into a thread.

**Gate**: Dry run exits 0, content length validates, credentials confirmed present. Proceed only when gate passes.

---

### Phase 2: CONFIRM

**Goal**: Show the user exactly what will be posted and require explicit approval before writing.

Present the content preview in this format:

```
CONTENT PREVIEW
================
Tweet 1/1:
  "Your tweet text here"
  Characters: 42/280

Action: POST single tweet

Approve? [yes/no]
```

For a thread:
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

**Wait for explicit user approval.** The words "yes", "approve", "go ahead", "post it", or equivalent constitute approval. Do not infer approval from context or prior conversation turns.

**Gate**: User has typed an explicit approval in this conversation turn. Proceed only when gate passes. Do NOT pass --confirmed before the user approves.

---

### Phase 3: POST

**Goal**: Execute the write operation and capture tweet IDs.

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

**Tweet with media:**
```bash
python3 $HOME/.claude/scripts/x-api-poster.py post \
  --confirmed \
  --text "your tweet text here" \
  --media /absolute/path/to/image.jpg
```

Watch output for:
- [tweet-posted] id=... url=... -- success line per tweet
- [rate-limit-warning] remaining=N reset=EPOCH -- surface to user immediately if present
- Any ERROR: line -- surface verbatim and stop

**Gate**: Script exits 0, at least one [tweet-posted] line in output. Proceed only when gate passes.

---

### Phase 4: REPORT

**Goal**: Return tweet URLs, IDs, and engagement baseline to the user.

**Step 1: Collect tweet IDs from Phase 3 output**

Parse all [tweet-posted] id=... url=... lines.

**Step 2: Read engagement baseline (optional, read-only)**

For each posted tweet, you may read initial public_metrics via:
```bash
python3 $HOME/.claude/scripts/x-api-poster.py read-timeline --user-id me --max-results 5
```

**Step 3: Report to user**

Provide:
- Tweet URL(s) as clickable links
- Tweet ID(s) for reference
- Thread structure if applicable (N tweets, root ID)
- Any rate limit warnings encountered
- Engagement baseline if collected (impressions, likes, retweets at T+0)

---

## Error Handling

### Error: "Missing required environment variable: X_API_KEY"
Cause: One or more credential env vars not set in the shell
Solution:
1. Verify all five variables are exported: X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET, X_BEARER_TOKEN
2. For read-only operations, only X_BEARER_TOKEN is required
3. For write operations, all five are required
4. Never pass credentials as command arguments or store in files

### Error: "Tweet text exceeds 280 characters"
Cause: A single tweet segment is too long
Solution:
1. Shorten the text manually
2. Or approve auto-segmentation into a thread -- the skill will split on sentence boundaries

### Error: "Write operation requires --confirmed flag"
Cause: Script invoked without confirmation (should not happen if Phase 2 gate was followed)
Solution: Return to Phase 2, present the confirm gate, and obtain explicit user approval

### Error: "403 Forbidden" or "401 Unauthorized"
Cause: Credentials are invalid, expired, or lack the required permissions
Solution:
1. Verify the X developer app has Read and Write permissions enabled
2. Regenerate access tokens after changing app permissions
3. Confirm the app is attached to a Project in the X developer portal

### Error: "429 Too Many Requests" or rate limit exhaustion
Cause: API rate limit window exhausted
Solution:
1. Check x-rate-limit-reset timestamp in the warning output
2. Wait until the reset epoch before retrying
3. X API rate limits are per-15-minute window -- a thread of N tweets consumes N requests

### Error: "Media upload failed at step 1" or "Media upload failed at step 2"
Cause: Media upload is a two-step process; failure at either step leaves no orphaned media
Solution:
1. Confirm media file exists and is a supported format (JPG, PNG, GIF, MP4)
2. Check file size: images <= 5 MB, videos <= 512 MB
3. Re-run the post command; the script does not partially attach media on failure

---

## Anti-Patterns

### Anti-Pattern 1: Pre-emptively passing --confirmed
**What it looks like**: Agent passes --confirmed before the user approves in Phase 2
**Why wrong**: Bypasses the only hard gate on irreversible public actions
**Do instead**: Present the content preview, wait for explicit typed approval, then pass --confirmed

### Anti-Pattern 2: Skipping --dry-run in Phase 1
**What it looks like**: Running post --confirmed directly without a dry-run validation pass
**Why wrong**: Posts content that fails length checks or uses missing credentials -- publicly, irreversibly
**Do instead**: Always run --dry-run in Phase 1 before any write attempt

### Anti-Pattern 3: Constructing HTTP requests directly
**What it looks like**: Agent using requests or curl to call api.x.com directly
**Why wrong**: Bypasses credential handling, rate limit inspection, and error normalization in the script
**Do instead**: All X API calls go through scripts/x-api-poster.py

### Anti-Pattern 4: Treating engagement metrics as real-time
**What it looks like**: Reading public_metrics immediately after posting and reporting 0 impressions as failure
**Why wrong**: X API metrics have propagation delay; 0 impressions at T+0 is normal
**Do instead**: Report metrics as baseline at post time and note they will grow asynchronously

### Anti-Pattern 5: Using OAuth 1.0a for read operations
**What it looks like**: Passing all four OAuth 1.0a credentials for a timeline read
**Why wrong**: Unnecessarily exposes write-capable credentials; read ops only need Bearer token
**Do instead**: The script selects auth mode automatically based on operation type -- do not override it

---

## References

- `$HOME/.claude/scripts/x-api-poster.py`: Backing script (exit codes: 0=success, 1=missing credentials, 2=content validation failed, 3=API error, 4=write attempted without --confirmed)
- X API v2 documentation: https://developer.twitter.com/en/docs/twitter-api
- X media upload (v1.1): https://developer.twitter.com/en/docs/twitter-api/v1/media/upload-media/api-reference/post-media-upload
