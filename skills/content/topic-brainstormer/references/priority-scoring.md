# Priority Scoring Reference

## The Priority Matrix

Every topic is scored on three dimensions:

```
Priority Score = Impact x Vex Level x Resolution

Maximum score: 5 x 5 x 5 = 125
Minimum score: 1 x 1 x 1 = 1
```

---

## Dimension 1: Impact

**Question:** How many people face this problem?

### Scoring Rubric

| Score | Description | Examples |
|-------|-------------|----------|
| **5** | Nearly everyone using the technology | "Git merge conflicts", "npm install fails" |
| **4** | Common scenario, many will encounter | "Hugo build fails on CI", "Docker networking issues" |
| **3** | Specific situation, some will encounter | "Hugo theme submodule update", "PaperMod search setup" |
| **2** | Niche scenario, few will encounter | "Hugo with custom CMS integration", "Specific cloud provider quirk" |
| **1** | Rare edge case, almost no one encounters | "Obscure OS + tool combination", "Legacy version issue" |

### Impact Assessment Questions

- Is this technology widely used?
- Is this scenario common in normal usage?
- Would this appear in search results often?
- Have you seen others hit this problem?

### Impact Indicators

**High impact signals (4-5):**
- Multiple Stack Overflow questions about this
- Appears in technology's FAQ or common issues
- You've seen colleagues hit the same problem
- Error message is commonly searched

**Low impact signals (1-2):**
- Can't find others with this issue
- Requires unusual configuration
- Only affects edge case workflows
- Technology is rarely used

---

## Dimension 2: Vex Level

**Question:** How frustrating is the problem?

### Scoring Rubric

| Score | Description | Time Lost | Emotional Response |
|-------|-------------|-----------|-------------------|
| **5** | Major blocker, significant time lost | Hours to days | "I almost quit" |
| **4** | Very frustrating, serious impediment | 2-4 hours | "This is ridiculous" |
| **3** | Annoying but manageable | 1-2 hours | "That was frustrating" |
| **2** | Minor inconvenience | 15-60 minutes | "A bit annoying" |
| **1** | Barely noticeable | < 15 minutes | "Mildly confusing" |

### Vex Level Assessment Questions

- How much time did you lose?
- How many failed attempts before success?
- How unclear was the error message or docs?
- Did this block other work?

### Vex Level Indicators

**High vex signals (4-5):**
- Multiple debugging sessions
- Had to step away and come back
- Involved multiple wrong turns
- Error messages were misleading
- Documentation was wrong or missing

**Low vex signals (1-2):**
- Figured it out quickly
- Error message was helpful
- First Google result had the answer
- Just needed to read the docs more carefully

---

## Dimension 3: Resolution

**Question:** How satisfying is the solution?

### Scoring Rubric

| Score | Description | Understanding Gained | Solution Quality |
|-------|-------------|---------------------|------------------|
| **5** | Elegant fix, deep understanding | "Now I truly get it" | Clean, permanent |
| **4** | Clean solution, good insight | "That makes sense" | Solid, maintainable |
| **3** | Workable fix, some insight | "I see what was wrong" | Functional |
| **2** | Hacky workaround, limited insight | "It works now" | Fragile |
| **1** | Partial fix, still confusing | "Not sure why this works" | Band-aid |

### Resolution Assessment Questions

- Do you understand why the problem happened?
- Is the fix elegant or hacky?
- Could you explain this to others?
- Would you feel confident hitting this again?

### Resolution Indicators

**High resolution signals (4-5):**
- Root cause fully understood
- Fix is simple and elegant
- Learned something transferable
- Can prevent this in the future
- Would feel good sharing this

**Low resolution signals (1-2):**
- Still not 100% sure why it works
- Fix feels fragile
- Couldn't explain to someone else
- Might break again in new context
- Copied the solution without understanding

---

## Score Interpretation

### Score Ranges

| Range | Priority | Action |
|-------|----------|--------|
| **60-125** | HIGH | Write this soon - strong YourBlog material |
| **30-59** | MEDIUM | Good candidate with the right angle |
| **15-29** | LOW | Needs more vex or broader impact |
| **1-14** | SKIP | Not enough value for readers |

### Score Distribution Examples

**HIGH PRIORITY (60+):**
```
"Hugo Build Fails Only on Cloudflare Pages"
Impact: 4 (common CI/CD scenario)
Vex: 4 (hours lost, misleading errors)
Resolution: 4 (version pinning, understanding why)
Score: 4 x 4 x 4 = 64
```

```
"Git Submodule Detached HEAD Breaks Theme Updates"
Impact: 4 (everyone using submodule themes)
Vex: 5 (confusing state, silent failures)
Resolution: 4 (proper update workflow)
Score: 4 x 5 x 4 = 80
```

**MEDIUM PRIORITY (30-59):**
```
"PaperMod Search Feature Setup"
Impact: 3 (PaperMod users wanting search)
Vex: 3 (config not obvious)
Resolution: 4 (clean setup, understanding config)
Score: 3 x 3 x 4 = 36
```

```
"Hugo Partial Caching in Dev Mode"
Impact: 3 (Hugo devs who use partials)
Vex: 4 (confusing behavior)
Resolution: 3 (cache-busting, but feels like workaround)
Score: 3 x 4 x 3 = 36
```

**LOW PRIORITY (15-29):**
```
"Hugo Taxonomy URL Customization"
Impact: 2 (specific SEO need)
Vex: 3 (config spread across files)
Resolution: 3 (works, but verbose)
Score: 2 x 3 x 3 = 18
```

**SKIP (1-14):**
```
"Hugo Server Port Already in Use"
Impact: 3 (common enough)
Vex: 1 (obvious fix: change port)
Resolution: 2 (no insight gained)
Score: 3 x 1 x 2 = 6
```

---

## Tie-Breaking Rules

When topics have equal scores, prefer:

1. **Gap fillers over new topics**
   - Completing existing cross-references builds site coherence
   - Readers may already be looking for this content

2. **Complements recent posts**
   - Related topics create content clusters
   - Readers may follow the thread

3. **Uses covered technologies**
   - Lower research overhead
   - Consistent voice and depth

4. **Clearer narrative structure**
   - Easier to write well
   - Better chance of high-quality result

5. **Stronger vex (if Impact x Resolution tied)**
   - YourBlog identity is about frustration
   - Readers connect with struggle stories

---

## Scoring Calibration

### Common Mistakes

**Over-scoring Impact:**
- "Everyone who uses X" - but how many use X?
- Consider: Is X a mainstream technology?

**Under-scoring Vex:**
- Forgetting how frustrated you were after solving it
- Consider: Would past-you have appreciated this post?

**Over-scoring Resolution:**
- "It works now" != elegant solution
- Consider: Do you truly understand why?

### Calibration Checks

Before finalizing scores, ask:

- **Impact:** Would you share this on HN/Reddit? Would people care?
- **Vex:** Would past-you have been grateful for this post?
- **Resolution:** Could you teach this to a colleague tomorrow?

---

## Quick Reference Card

```
IMPACT (1-5): How many face this?
  5 = Universal    4 = Common    3 = Specific
  2 = Niche        1 = Rare

VEX (1-5): How frustrating?
  5 = Hours/days   4 = 2-4 hours   3 = 1-2 hours
  2 = < 1 hour     1 = < 15 min

RESOLUTION (1-5): How satisfying?
  5 = Elegant      4 = Clean       3 = Workable
  2 = Hacky        1 = Partial

PRIORITY = Impact x Vex x Resolution
  60+  = HIGH      Write soon
  30-59 = MEDIUM   Good with angle
  15-29 = LOW      Needs work
  <15  = SKIP      Not enough value
```

---

## Example Scoring Session

```
TOPIC: "Cloudflare Pages Environment Variables Aren't Available at Build Time"

IMPACT ASSESSMENT:
- Cloudflare Pages is popular for static sites
- Anyone using build-time env vars hits this
- Common enough, but not universal
- Score: 4

VEX ASSESSMENT:
- Error is not obvious (variable just empty)
- Difference between build-time and runtime confusing
- Spent 2 hours figuring this out
- Docs exist but easy to miss
- Score: 3

RESOLUTION ASSESSMENT:
- Understand the runtime vs build-time model now
- Solution is clean (use wrangler.toml or build command)
- Can explain to others confidently
- Not the most elegant (wish it just worked)
- Score: 4

FINAL SCORE: 4 x 3 x 4 = 48 (MEDIUM PRIORITY)

NOTES:
- Good topic but vex could be higher
- Consider framing around the confusion, not just the fix
- Pairs well with other Cloudflare deployment topics
```
