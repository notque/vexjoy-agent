# Routing Conflict Resolution

## Conflict Types

### Type 1: Exact Pattern Overlap
**Example:** "debug" matches both systematic-debugging skill AND programming skill (golang-general.md)

**Resolution Strategy:**
- More specific pattern takes precedence
- Context-dependent patterns noted in description
- General pattern as fallback

**Action:**
```
Pattern: "debug" → systematic-debugging skill (general)
Pattern: "debug Go" → programming skill (golang-general.md) (specific)
Pattern: "debug Python" → programming skill (python-general.md) (specific)
```

### Type 2: Subset Pattern Overlap
**Example:** "test" is subset of "test API", "test Go", etc.

**Resolution Strategy:**
- Longer pattern matches first
- Routing logic checks longest match
- Document substring relationships

**Action:**
```
Pattern: "test API" → api-testing-skill (specific)
Pattern: "test Go" → programming (golang-general.md) + test-driven-development (specific)
Pattern: "test" → test-driven-development skill (general fallback)
```

### Type 3: Synonym Conflicts
**Example:** "review" vs "audit" vs "check" all mean similar things

**Resolution Strategy:**
- Map synonyms to same route
- Use most common term as primary pattern
- List alternates as comma-separated triggers

**Action:**
```
Pattern: "review", "audit", "check quality" → systematic-code-review skill
```

### Type 4: Domain Ambiguity
**Example:** "API" could be REST API, GraphQL, or general API work

**Resolution Strategy:**
- Domain-specific routing takes precedence over task routing
- If domain context present, route to domain agent
- Otherwise route to task-specific skill

**Action:**
```
If request includes "Go" + "API" → programming skill, golang-general.md (domain)
If request includes "test" + "API" → api-testing-skill (task)
If request is just "API" → Ask clarifying question
```

## Priority Rules

**Rule 1: Specificity Wins**
- "debug Go code" beats "debug"
- Domain + task beats task alone

**Rule 2: Domain Routing > Intent Routing**
- If domain keyword detected, check Domain-Specific table first
- Intent patterns are fallback for cross-domain tasks

**Rule 3: Explicit > Inferred**
- Manual routing entries always win over auto-generated
- User can override conflicts by adding manual entry

**Rule 4: Alphabetical Tiebreaker**
- If equal specificity, alphabetically first route wins
- Document the tie in comments

## Conflict Severity Levels

**Low Severity:**
- Both routes would work reasonably well
- User can clarify if needed
- Example: "test" → TDD skill vs testing skill (testing-automation.md)

**Medium Severity:**
- Routes lead to different outcomes
- Requires pattern refinement
- Example: "review" → code review vs documentation review

**High Severity:**
- Routes are incompatible
- One will fail user's intent
- MUST resolve before deploying
- Example: "deploy" → docker-deployment vs kubernetes-deployment (completely different)

## Resolution Process

1. **Detect Conflict:**
   ```python
   if pattern in routing_table and new_route != existing_route:
       conflicts.append(Conflict(pattern, [existing, new]))
   ```

2. **Analyze Specificity:**
   ```python
   specificity_score = len(pattern.split()) + domain_bonus + task_bonus
   higher_score_wins()
   ```

3. **Apply Priority Rules:**
   - Check manual entry status (manual always wins)
   - Check domain context
   - Check pattern length
   - Check alphabetical order

4. **Document Decision:**
   ```markdown
   <!-- ROUTING NOTE: "debug" has multiple routes
        - General debugging → systematic-debugging skill
        - Go debugging → programming skill (golang-general.md)
        Resolution: Context-dependent, domain routing takes precedence
   -->
   ```

5. **Update Routing Tables:**
   - Keep most specific patterns
   - Document fallback behavior
   - Add clarifying examples to /do documentation
