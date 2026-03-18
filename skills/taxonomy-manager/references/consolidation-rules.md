# Taxonomy Consolidation Rules

Guidelines for when and how to merge, rename, or remove taxonomy terms.

---

## When to Merge Tags

### Rule 1: Case Variations

**Condition**: Same word with different capitalization
**Action**: Merge to lowercase

| Source Tags | Target |
|-------------|--------|
| `Hugo`, `hugo`, `HUGO` | `hugo` |
| `CloudFlare`, `cloudflare` | `cloudflare` |
| `GitHub`, `github` | `github` |

**Priority**: High - breaks navigation and SEO

### Rule 2: Plural Variations

**Condition**: Singular and plural forms of same word
**Action**: Merge to singular (usually)

| Source Tags | Target |
|-------------|--------|
| `template`, `templates` | `template` |
| `tutorial`, `tutorials` | `tutorial` |
| `tool`, `tools` | `tool` |

**Exception**: Keep plural if it's the standard term (`analytics`, `kubernetes`)

**Priority**: Medium - dilutes SEO

### Rule 3: Synonym Pairs

**Condition**: Different words with identical meaning in context
**Action**: Merge to most common/searchable term

| Source Tags | Target | Reasoning |
|-------------|--------|-----------|
| `debugging`, `troubleshooting` | `debugging` | More search volume |
| `setup`, `installation` | `setup` | Shorter, common |
| `config`, `configuration` | `configuration` | More formal |
| `error`, `bug` | Keep separate | Different meanings |

**Priority**: Medium - depends on semantic overlap

### Rule 4: Abbreviation Pairs

**Condition**: Full term and abbreviation both exist
**Action**: Pick one based on audience familiarity

| Source Tags | Target | Reasoning |
|-------------|--------|-----------|
| `ci-cd`, `continuous-integration` | `cicd` | Well-known abbreviation |
| `k8s`, `kubernetes` | `kubernetes` | Full name more searchable |
| `js`, `javascript` | `javascript` | Full name preferred |
| `aws`, `amazon-web-services` | `aws` | Abbreviation is standard |

**Priority**: Low - user preference

### Rule 5: Hierarchical Overlap

**Condition**: Specific tag is subset of general tag
**Action**: Keep general, merge specific into it

| Source Tags | Target | Reasoning |
|-------------|--------|-----------|
| `git-submodules`, `git` | `git` | Submodules is too specific |
| `hugo-themes`, `hugo` | `hugo` + `themes` | Use two general tags |
| `docker-compose`, `docker` | Keep both | Compose is distinct enough |

**Decision Criteria**:
- Merge if specific tag has < 3 posts
- Keep if specific tag is a major sub-topic (5+ posts)
- Consider splitting into two general tags instead

**Priority**: Medium - prevents tag explosion

---

## When to Remove Tags

### Rule 1: Zero Usage

**Condition**: Tag exists in config but no posts use it
**Action**: Remove from configuration

### Rule 2: Single Usage (Orphan)

**Condition**: Tag used in only 1 post
**Action**: Either merge into broader tag OR remove entirely

**Decision Tree**:
```
Single-use tag detected
  |
  +-- Is the tag reusable for future content?
  |     |
  |     +-- YES: Keep it (you'll add more posts with this tag)
  |     +-- NO: Continue to next question
  |
  +-- Can it merge into an existing broader tag?
        |
        +-- YES: Merge (e.g., "toml-errors" -> "configuration")
        +-- NO: Remove (e.g., "first-post" - likely a mistake)
```

### Rule 3: Stale Tags

**Condition**: Tag not used in any post from last 12 months
**Action**: Evaluate for removal or consolidation

---

## When to Rename Tags

### Rule 1: Convention Violation

**Condition**: Tag doesn't follow `lowercase-with-hyphens`
**Action**: Rename to follow convention

| Source | Target |
|--------|--------|
| `HugoTemplates` | `hugo-templates` |
| `cloud_flare` | `cloudflare` |
| `CI CD` | `cicd` |

### Rule 2: Typos

**Condition**: Obvious spelling error
**Action**: Rename to correct spelling

| Source | Target |
|--------|--------|
| `debuging` | `debugging` |
| `tutoral` | `tutorial` |

### Rule 3: Outdated Terms

**Condition**: Technology name has changed
**Action**: Rename to current name

| Source | Target |
|--------|--------|
| `docker-machine` | (consider removing - deprecated tool) |
| `bower` | (consider removing - deprecated tool) |

---

## When to Add Tags

### Rule 1: Semantic Gap

**Condition**: Multiple posts share a concept but lack a unifying tag
**Action**: Add tag to all related posts

**Detection**:
```
3 posts mention "theme" in title/content
  -> None have "themes" tag
  -> Add "themes" tag to all 3
```

### Rule 2: Cross-Reference

**Condition**: Posts in different categories share a technology
**Action**: Add technology tag to create cross-category links

**Example**:
```
Post 1: Category=tutorials, Tags=[hugo, deployment]
Post 2: Category=technical-notes, Tags=[debugging]
Both posts discuss Cloudflare
  -> Add "cloudflare" tag to both
```

### Rule 3: Format Standardization

**Condition**: Blog adopts new format tags
**Action**: Retroactively add to matching posts

---

## Consolidation Priority Matrix

| Issue Type | Impact | Effort | Priority |
|------------|--------|--------|----------|
| Case inconsistency | High | Low | P1 - Do now |
| Synonym duplicates | Medium | Low | P2 - Soon |
| Orphan tags | Low | Low | P3 - Batch cleanup |
| Stale tags | Low | Low | P3 - Batch cleanup |
| Missing tags | Medium | Medium | P2 - When publishing |
| Hierarchical overlap | Medium | Medium | P3 - Quarterly |

---

## Consolidation Workflow

### Step 1: Audit

Run taxonomy audit to identify all issues:
```
/taxonomy audit
```

### Step 2: Prioritize

Address issues in priority order:
1. Case inconsistencies (breaks navigation)
2. Synonym duplicates (confuses users)
3. Orphan tags (clutter)

### Step 3: Preview

Always preview changes before applying:
```
/taxonomy merge "Hugo" into "hugo" --preview
```

### Step 4: Apply

Apply changes with explicit confirmation:
```
/taxonomy merge "Hugo" into "hugo" --apply
```

### Step 5: Verify

Confirm Hugo builds and changes are correct:
```
hugo --quiet
git diff content/
```

### Step 6: Commit

Commit with clear message:
```
git commit -m "taxonomy: standardize Hugo -> hugo across posts"
```

---

## Safe vs Risky Consolidations

### Safe Consolidations

These can be applied with high confidence:
- Case normalization (`Hugo` -> `hugo`)
- Obvious typos (`debuging` -> `debugging`)
- Exact synonyms in context (`setup` -> `installation`)

### Risky Consolidations

These require human judgment:
- Near-synonyms (`debugging` vs `troubleshooting`)
- Hierarchical merges (`docker-compose` into `docker`)
- Technology grouping (`react`, `vue`, `angular` into `frontend`)

**For risky consolidations**: Always ask for confirmation, explain tradeoffs.

---

## Rollback Strategy

If consolidation causes problems:

```bash
# Revert all taxonomy changes
git checkout content/

# Or revert specific file
git checkout content/posts/affected-post.md
```

Always run `hugo --quiet` after consolidation to verify build.
