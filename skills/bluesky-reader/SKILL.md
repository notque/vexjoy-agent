---
name: bluesky-reader
description: "Read public Bluesky feeds via AT Protocol API."
version: 1.0.0
user-invocable: false
agent: python-general-engineer
allowed-tools:
  - Bash
  - Read
routing:
  triggers:
    - "read Bluesky"
    - "fetch Bluesky posts"
    - "AT Protocol"
    - "Bluesky feed"
    - "bsky"
  category: research
---

# Bluesky Reader Skill

Read public Bluesky profiles via the AT Protocol public API. No auth needed.

## Commands

```bash
# Fetch recent posts
python3 ~/.claude/scripts/bluesky_reader.py feed --handle HANDLE --limit 20

# Search posts by keyword (fetches feed, filters locally)
python3 ~/.claude/scripts/bluesky_reader.py search --handle HANDLE --query "search terms"

# JSON output for pipeline consumption
python3 ~/.claude/scripts/bluesky_reader.py feed --handle HANDLE --json

# Pagination
python3 ~/.claude/scripts/bluesky_reader.py feed --handle HANDLE --cursor CURSOR_STRING
```

## API Details

- **Endpoint**: `https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed`
- **Auth**: None (public endpoint)
- **Limit**: 1-100 posts per request
- **Search**: Local keyword filter -- all query words must appear (case-insensitive)

## When to Use

- Gathering recent Bluesky posts from a specific person for research
- Searching a profile's posts for mentions of a topic
- Feeding Bluesky content into a news or content pipeline

## Exit Codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 1    | Error (network failure, invalid handle, no posts found) |
