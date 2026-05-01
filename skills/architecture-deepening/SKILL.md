---
name: architecture-deepening
description: "Proactive architecture improvement: find shallow modules, propose deepening opportunities, design conversation."
user-invocable: true
command: architecture-deepening
context: fork
allowed-tools:
  - Agent
  - Bash
  - Read
  - Glob
  - Grep
routing:
  triggers:
    - deepen architecture
    - find shallow modules
    - architecture improvement
    - module depth analysis
    - deepening opportunities
    - improve module interfaces
    - reduce complexity
    - architecture deepening
  pairs_with:
    - full-repo-review
    - adr-consultation
    - codebase-overview
  complexity: Medium
  category: analysis
---

# Architecture Deepening

Proactive workflow for finding shallow modules and proposing deepening
opportunities. This is not a code review -- it does not find bugs or style
violations. It finds modules where the interface is too close to the
implementation, where users must understand internals to use the API, and
where small interface changes would absorb disproportionate complexity.

**When to use**: After onboarding to a codebase, before a major feature push,
when new contributors report confusion, or when the same "how do I use this?"
question keeps appearing.

**How it differs from full-repo-review**: Full-repo-review finds defects.
This skill finds structural improvement opportunities -- places where the
architecture could absorb more complexity so users of the module do less work.
The two pair well: run full-repo-review first to fix defects, then
architecture-deepening to raise the bar.

---

## Reference Loading Table

| Signal | Load These Files | Why |
|---|---|---|
| Phase 1, module analysis, vocabulary terms | `vocabulary.md` | Shared architecture vocabulary: module, depth, seam, leverage, locality, deletion test |
| Phase 2, interface alternatives, parallel exploration | `interface-design.md` | Parallel sub-agent pattern for exploring alternative interfaces |
| Phase 2-3, dependency analysis, testing strategy | `deepening-strategies.md` | Dependency categorization, safe deepening patterns, testing strategies |

## Instructions

Execute all three phases in order. Each phase has a gate that must pass before
advancing. The user is a collaborator throughout -- present findings, get
input, refine together.

This skill is language-agnostic. The vocabulary and strategies apply equally to
Go packages, Python modules, TypeScript libraries, or any codebase with module
boundaries.

### Phase 1: EXPLORE

**Goal**: Identify shallow modules -- places where the interface exposes too
much implementation detail, forcing users to understand internals.

**Step 1: Scope the codebase**

Determine what to analyze. If the user specified a directory or package, start
there. Otherwise, scan the full codebase for module boundaries.

```bash
# Find module boundaries by language
find . -name "go.mod" -o -name "package.json" -o -name "pyproject.toml" -o -name "__init__.py" -o -name "index.ts" -o -name "mod.rs" 2>/dev/null | head -50

# Count exported symbols per package (Go example)
grep -rn "^func [A-Z]" --include="*.go" | cut -d: -f1 | sort | uniq -c | sort -rn | head -20

# Count public exports (TypeScript example)
grep -rn "^export " --include="*.ts" --include="*.tsx" | cut -d: -f1 | sort | uniq -c | sort -rn | head -20
```

**Step 2: Apply shallowness signals**

Read `references/vocabulary.md` for the full vocabulary. For each module,
check these signals -- a module is shallow when:

- Its interface is nearly as complex as its implementation (high surface-area-to-depth ratio)
- Users must read source code to understand how to call it correctly
- Configuration or setup requires knowledge of internal state
- Error messages expose implementation details rather than guiding the caller
- Multiple modules must be coordinated to accomplish a single logical operation

Score each candidate module: **HIGH** (clear shallowness, high leverage fix),
**MEDIUM** (some shallowness, moderate leverage), **LOW** (minor, low impact).

**Step 3: Identify seams**

For each HIGH-scored module, identify seams -- natural boundaries where the
module could absorb more responsibility. Read `references/vocabulary.md` for
seam types (data seams, protocol seams, temporal seams).

**Gate**: At least 3 candidate modules identified with shallowness scores and
seam analysis. If fewer than 3 candidates exist, document why (the codebase
may already be well-structured) and proceed to Phase 2 with what you have.

---

### Phase 2: PRESENT CANDIDATES

**Goal**: Show the user what you found using the shared vocabulary, then
explore interface alternatives for the top candidates.

**Step 1: Present findings table**

Present each candidate using vocabulary from `references/vocabulary.md`:

```markdown
| Module | Depth Score | Shallowness Signal | Seam | Leverage |
|--------|------------|-------------------|------|----------|
| pkg/config | HIGH | Users must know YAML structure to use API | Data seam | High -- 12 callers |
| internal/auth | MEDIUM | Token refresh logic leaks to callers | Protocol seam | Medium -- 4 callers |
```

For each candidate, state:
- What the module does today
- Why it is shallow (cite specific interface elements)
- Where the seam is (what responsibility could move behind the interface)
- The leverage (how many callers benefit from deepening)

**Step 2: Get user input**

Ask the user which candidates to explore further. Do not proceed to interface
design without confirmation -- the user knows the codebase priorities better
than the model.

**Step 3: Explore interface alternatives**

For each selected candidate, read `references/interface-design.md` and
`references/deepening-strategies.md`. Then design 2-3 alternative interfaces
that would deepen the module:

For each alternative, document:
- The new interface signature (function names, parameters, return types)
- What moves behind the interface (what callers no longer need to know)
- The deletion test result: what code in callers can be deleted if this interface ships
- Trade-offs: what flexibility callers lose, what edge cases need escape hatches

**Gate**: At least 2 interface alternatives presented per selected candidate.
User has confirmed which candidates to explore. Each alternative includes a
deletion test result.

---

### Phase 3: DESIGN CONVERSATION

**Goal**: Grill the chosen approach until the best deepening emerges. This is
a collaborative design conversation, not a presentation.

**Step 1: Challenge each alternative**

For the user's preferred alternative(s), probe with these questions:

- **Locality**: Does this change keep related things together, or does it scatter
  responsibility across more files? Read `references/vocabulary.md` for the
  locality principle.
- **Escape hatches**: What happens when a caller needs the old flexibility? Is there
  a clean override path, or does the new interface force workarounds?
- **Migration**: Can callers adopt incrementally, or is this an all-or-nothing change?
- **Testing**: How do you test the deepened module? Read
  `references/deepening-strategies.md` for testing strategies.
- **Second-order effects**: Does deepening this module create new shallowness
  elsewhere (pushing complexity sideways instead of absorbing it)?

**Step 2: Iterate until convergence**

Continue the design conversation until either:
- The user and model agree on a specific deepening approach, OR
- The user decides the current structure is acceptable after examining alternatives

This is not a fixed number of rounds. Keep going until the design feels right
or the user says stop. Each round should narrow the design space -- if rounds
are not converging, surface that explicitly: "We have been going back and forth
on X -- should we pick one and try it, or is this a sign the deepening is not
worth the disruption?"

**Step 3: Document the decision**

Produce a summary of the chosen deepening:

```markdown
## Deepening Decision: {module name}

**Current interface**: {what callers see today}
**Proposed interface**: {what callers would see after deepening}
**What moves behind the interface**: {implementation details that callers no longer manage}
**Deletion test**: {what caller code can be removed}
**Migration path**: {how callers adopt incrementally}
**Trade-offs accepted**: {what flexibility was traded for simplicity}
**Next step**: {specific first action -- "create ADR", "prototype in branch", "discuss with team"}
```

If the user wants to formalize the decision, suggest pairing with
`adr-consultation` to create an Architecture Decision Record.

**Gate**: Design conversation completed. Decision documented with all fields
filled. Next step identified.

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| No shallow modules found | Codebase is well-structured or too small | Document the finding -- this is a valid outcome. Suggest running again after the next major feature addition. |
| Too many candidates | Large codebase with pervasive shallowness | Focus on the 5 highest-leverage candidates (most callers benefit). Suggest splitting into multiple sessions by subsystem. |
| User disagrees with shallowness assessment | Model misjudged module boundaries or caller patterns | Ask the user to explain the design intent. The model may be seeing complexity that is intentional (performance, backward compatibility). |
| Design conversation does not converge | Fundamental disagreement about trade-offs | Surface the disagreement explicitly. Suggest prototyping both approaches in separate branches and comparing. |

---

## References

- [Vocabulary](references/vocabulary.md) -- Shared architecture vocabulary: module, depth, seam, leverage, locality, deletion test
- [Interface Design](references/interface-design.md) -- Patterns for exploring alternative interfaces
- [Deepening Strategies](references/deepening-strategies.md) -- Dependency categorization and testing strategies for safe deepening
