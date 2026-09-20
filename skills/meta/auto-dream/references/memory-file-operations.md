# Auto-Dream memory operations

Memory files use YAML frontmatter; `type` is required by scan grouping. A synthesized insight also records `created` and `synthesized_from`. A merged memory inherits the newer source's frontmatter and adds `merged_from`.

A stale classification requires all three local signals: age over 30 days, no topic evidence in 20 recent commits, and no topic evidence in seven days of session summaries. Duplicates must be interchangeable without information loss. Contradictions are reported and left unchanged.

Archive instead of delete. Rewrite `MEMORY.md` through `MEMORY.md.tmp` plus rename, then verify every index target exists. Keep the injected index concise; the consumer truncates `MEMORY.md` after 200 lines.

```bash
wc -l "$DREAM_MEMORY_DIR/MEMORY.md"
rg -n '^type:|^merged_from:|^synthesized_from:' "$DREAM_MEMORY_DIR"
find "$DREAM_MEMORY_DIR" -maxdepth 1 -name '*.tmp'
```
