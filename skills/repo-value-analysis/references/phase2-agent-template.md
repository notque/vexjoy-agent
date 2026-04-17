# Phase 2: DEEP-READ Agent Template

Dispatch 1 Agent per analysis zone (background). Each agent receives:
- The zone name and file list
- Instructions to read EVERY file (not sample, not skim) to avoid sampling bias
- A structured output template that captures what they have, not just what they are

**Agent instructions template** (replace ALL bracketed placeholders with actual values before dispatching):

```
You are analyzing the "[zone]" zone of repository [REPO_NAME].

Read EVERY file listed below. For each file, extract:
1. Purpose (1-2 sentences)
2. Key techniques or patterns used
3. Notable or unique approaches
4. Dependencies on other components

Files to read:
[file list]

After reading ALL files, produce a structured summary:

## Zone: [zone]
### Component Inventory
| File | Purpose | Key Pattern |
|------|---------|-------------|
| ... | ... | ... |

### Key Techniques
- [technique]: [which files use it, how]

### Notable Patterns
- [pattern]: [why it's notable]

### Potential Gaps They Fill
- [gap]: [what capability this provides that might be missing elsewhere]

Save your findings to /tmp/[REPO_NAME]-zone-[zone].md
```

Dispatch up to 8 agents in parallel for speed. If more than 8 zones exist, batch them (first 8, wait 5 minutes, then remaining) rather than serializing — parallel dispatch is default unless `--quick` flag requests otherwise.
