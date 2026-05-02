# Source Quality Assessment

> **Scope**: Reliable vs unreliable sources, speculation/marketing detection, epistemic labels.
> **Version range**: all versions
> **Generated**: 2026-04-13

---

## Source Tier Classification

| Tier | Source Type | Weight | Example |
|------|-------------|--------|---------|
| 1 | Official docs, release notes, specs | High | docs.python.org, RFC, GitHub releases |
| 2 | Peer-reviewed, maintainer blog posts | High | arxiv.org, engineering blogs |
| 3 | Established publications with bylines | Medium | InfoQ, The New Stack, ACM |
| 4 | StackOverflow high-vote answers | Medium-Low | Verify against Tier 1 |
| 5 | Forums, Reddit, HackerNews | Low | Use only to identify questions |
| 6 | Aggregator listicles, vendor marketing | Discard | "Top 10 X for Y" |

---

## Correct Patterns

### Epistemic Labeling

Every factual claim labeled at first appearance:

```markdown
- FACT: Python 3.12.0 released October 2, 2023 [source: python.org/downloads]
- INFERENCE: GIL removal likely ships in 3.13 (based on PEP 703)
- SPECULATION: Some commenters expect adoption by Q4 2024 (no primary source)
```

Unlabeled inferences treated as facts corrupt coordinator synthesis.

---

### Detecting Outdated Sources

Check for: publication date, URL date path, "Last updated" footer, version number in title. No date found → treat as potentially outdated, note explicitly.

---

### Primary vs Aggregator Detection

```
Primary: official domain, named contributor, version/commit numbers, technical detail
Aggregator: "N best X for Y", equal-length summaries, "content writer" bio, no original analysis
```

---

## Pattern Catalog

### Find Primary Source Behind Aggregators

**Detection**: `grep -E "best-[0-9]|top-[0-9]|comparison" urls.txt`

"According to industry experts" cites no expert. Find the original study or docs.

---

### Label Forum Claims as Speculation

**Detection**: `grep -E "(reddit|ycombinator|stackoverflow)" source_list.txt`

HN comments are unverified. `SPECULATION: Community anticipates Rust rewrite [url] — no primary source found`

---

### Cite Sources for Every Precise Number

Numbers are most likely misremembered or context-dependent. Every numeric claim needs a URL.

```
FACT: K8s 1.28 ~23% pod startup reduction [source: kubernetes.io/blog/...]
```

---

### Extract Data, Discard Marketing

**Detection**: `grep -iE "(industry.leading|enterprise.grade|blazing.fast)" content.txt`

"Enterprise-grade" has no technical definition. Extract actual benchmarks or SLAs.

---

## Error-Fix Mappings

| Symptom | Root Cause | Fix |
|---------|------------|-----|
| "Can't verify claim" | Aggregator source | Re-research with primary source |
| "Conflicting data" | Different version contexts | Add version qualifier |
| Wrong number in report | Snippet misquoted | web_fetch full source |
| "Experts say" without name | Aggregator language | Remove or label SPECULATION |
| "Is this current?" | No date on source | Find dated version or add "verify" |

---

## Speculation Indicator Vocabulary

Flag for manual review:
```
"reportedly", "sources say", "is expected to", "plans to",
"according to rumors", "might/could/may", "industry observers", "it is believed"
```

---

## Detection Commands Reference

```bash
grep -E "(best-[0-9]|top-[0-9]|comparison)" sources.txt
grep -iE "(industry.leading|enterprise.grade|blazing.fast)" content.txt
grep -E "(reddit|hackernews|stackoverflow)" sources.txt
grep -E "^- (FACT|INFERENCE):" report.md | grep -v "\[source:"
```

---

## See Also

- `research-execution-patterns.md` — OODA cycle, budget, query optimization
