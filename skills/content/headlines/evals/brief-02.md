# Brief 02 — Tech: CLI rewrite speedup

**Premise**: A developer rewrote an internal Python CLI in Go. Startup time dropped from 410ms to 38ms. The surprise: the win came almost entirely from removing import-time work, and a later Python refactor with lazy imports reached 95ms — the rewrite was mostly unnecessary.

**Key facts**: 410ms → 38ms (Go rewrite); 410ms → 95ms (Python lazy imports, done afterward); tool runs ~200 times/day per developer; team of 40.

**Audience**: working developers weighing rewrites.

**Formats requested**: article title, social post.
