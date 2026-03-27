# Sample Collection Guide

Detailed reference for Step 1: COLLECT of the create-voice pipeline.

---

## Where to Find Samples

| Source | What to Look For | File Naming |
|--------|-----------------|-------------|
| Reddit history | Comments, posts, replies | `reddit-samples-YYYY-MM-DD.md` |
| Hacker News | Comments, Ask HN answers | `hn-samples-YYYY-MM-DD.md` |
| Blog posts | Published articles | `blog-samples.md` |
| Forum posts | Any discussion forum | `forum-samples-YYYY-MM-DD.md` |
| Emails | Professional and casual | `email-samples.md` |
| Chat logs | Slack, Discord, iMessage | `chat-samples.md` |
| Social media | Twitter/X threads | `social-samples.md` |

---

## Sample Quality Guidelines

- **Mix of lengths**: Very short (1 sentence), short (2-3 sentences), medium (paragraph), long (multi-paragraph). The distribution matters because most people write short responses most of the time.
- **Mix of contexts**: Technical, casual, disagreement, agreement, teaching, joking, emotional. Different contexts reveal different facets of voice.
- **Mix of topics**: Not all about the same subject. Topic diversity reveals stable voice patterns vs topic-specific patterns.
- **DO NOT clean up samples**: Typos, run-on sentences, fragments, loose punctuation ARE the voice, because cleaning destroys authenticity markers. This is the wabi-sabi principle (natural imperfections are features, not bugs) in action at the very first step.
- **DO NOT cherry-pick**: Include mediocre posts alongside great ones, because the mundane reveals default patterns.

---

## Directory Setup

```bash
mkdir -p skills/voice-{name}/references/samples/
```

Place all sample files in `skills/voice-{name}/references/samples/`. Each file should contain multiple samples, separated by `---` or clear headers.

---

## Sample File Format

Each sample file should preserve the original writing exactly:

```markdown
# Reddit Samples - 2025-12-30

## r/subreddit - Thread Title
[Exact text of comment, typos and all]

---

## r/subreddit - Another Thread
[Exact text]

---
```
