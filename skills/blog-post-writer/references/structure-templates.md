# Structure Templates Reference

Three post structures for blog content. Choose based on content type.

---

## Structure 1: Problem-Solution

**Use when**: Documenting a specific bug fix, debugging session, or resolution.

**Core pattern**: State the vex, explain the solution, describe the implications.

### Template

```markdown
---
title: "[Brief description of what was fixed/solved]"
date: YYYY-MM-DD
draft: false
tags: ["debugging", "specific-tech"]
summary: "[One sentence: problem and solution]"
---

## The Problem

[2-3 paragraphs describing the symptom]
- What was observed
- When it happened
- Initial hypotheses (optional)

## Investigation

[2-4 paragraphs on the debugging process]
- What was checked first
- What was ruled out
- The breakthrough moment

## The Fix

[1-2 paragraphs with the actual solution]
- Code change or config change
- Why this fixed it

## Why It Worked

[1-2 paragraphs on root cause]
- Technical explanation
- Why the symptom appeared the way it did

## Preventing Future Occurrences

[Optional: 1-2 paragraphs]
- Monitoring added
- Tests written
- Process changes
```

### Example: Problem-Solution

```markdown
---
title: "Why Production Crashed Every Tuesday at 3 AM"
date: 2024-12-20
draft: false
tags: ["debugging", "kubernetes", "cron"]
summary: "A cron job and a deployment window collided. The fix took 3 months to find."
---

## The Problem

Production crashed every Tuesday at 3:02 AM UTC. CPU spiked to 100%. All pods restarted.

The crashes started in September. Before that, Tuesdays were fine. Nothing in the September deployment logs explained the change.

## Investigation

First theory: bad deployment on Monday. We checked every Monday deploy for 6 weeks. Nothing correlated.

Second theory: external traffic spike. Tuesday 3 AM UTC is Tuesday 11 PM EST. Prime time? Traffic logs showed nothing unusual.

The breakthrough came from a different team. "Did you know we added a weekly database maintenance job in September?"

## The Fix

The database maintenance job ran at 3:00 AM Tuesday. It locked tables for bulk updates.

Our health checks queried those tables. Locked tables meant health check timeouts. Timeouts meant pod restarts. Mass restarts meant CPU spike.

```yaml
# Before: 3:00 AM (conflict)
schedule: "0 3 * * 2"

# After: 4:00 AM (deploy window ends at 3:30)
schedule: "0 4 * * 2"
```

## Why It Worked

Health checks hit a specific table: `user_sessions`. The maintenance job vacuumed that table first. Moving the job past the deploy window meant no overlap.

## Preventing Future Occurrences

We added a shared cron calendar. All scheduled jobs go there. Conflicts get flagged before merge.

Health checks now use a dedicated read replica. Maintenance on primary no longer affects them.
```

---

## Structure 2: Technical Explainer

**Use when**: Teaching a concept, explaining how something works, or documenting a technology.

**Core pattern**: What changed, why it matters, how it works.

### Template

```markdown
---
title: "[What this explains]"
date: YYYY-MM-DD
draft: false
tags: ["concept", "specific-tech"]
summary: "[One sentence: what this is and why it matters]"
---

## What [Thing] Does

[1-2 paragraphs: direct explanation]
- Core function
- Primary use case

## Why It Matters

[1-2 paragraphs: practical implications]
- What problems it solves
- What happens without it

## How It Works

[2-4 paragraphs: technical breakdown]
- Step by step process
- Key components
- Interactions between parts

## Practical Example

[Code or configuration showing usage]
- Minimal working example
- Common variations

## Gotchas

[1-3 common mistakes or surprises]
- Each with explanation
- How to avoid or fix

## When to Use (and When Not To)

[1-2 paragraphs: appropriate use cases]
- Good fit scenarios
- Bad fit scenarios
```

### Example: Technical Explainer

```markdown
---
title: "PostgreSQL VACUUM: What It Does and When You Need It"
date: 2024-12-18
draft: false
tags: ["postgresql", "database", "performance"]
summary: "VACUUM removes dead tuples. Without it, your database grows forever and queries slow down."
---

## What VACUUM Does

PostgreSQL never deletes data in place. When you UPDATE or DELETE a row, the old version stays on disk. These old versions are called dead tuples.

VACUUM marks dead tuples as reusable space. Without it, your tables grow forever.

## Why It Matters

Dead tuples waste disk space. A table with 1 million rows might have 10 million dead tuples consuming 90% of its storage.

Dead tuples also slow queries. Sequential scans read every tuple, dead or alive. Index scans can point to dead tuples, requiring extra heap fetches.

## How It Works

VACUUM runs in three phases:

**Phase 1: Scan**
Read the table and identify dead tuples. Build a list of tuple IDs to remove.

**Phase 2: Remove**
Mark dead tuples as available for reuse. Update the visibility map. Update free space map.

**Phase 3: Cleanup**
Remove index entries pointing to dead tuples. Update statistics for the query planner.

## Practical Example

```sql
-- Basic vacuum
VACUUM my_table;

-- Vacuum with statistics update
VACUUM ANALYZE my_table;

-- Aggressive vacuum (reclaims more space, takes longer)
VACUUM FULL my_table;  -- Warning: locks table exclusively
```

Check dead tuple count:

```sql
SELECT relname, n_dead_tup, n_live_tup,
       round(n_dead_tup::numeric / nullif(n_live_tup, 0) * 100, 2) as dead_ratio
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC;
```

## Gotchas

**Gotcha 1: VACUUM FULL locks the table**

Regular VACUUM runs concurrently. VACUUM FULL requires exclusive lock. Use VACUUM FULL only during maintenance windows.

**Gotcha 2: Autovacuum might not keep up**

High-churn tables can generate dead tuples faster than autovacuum cleans them. Monitor `n_dead_tup` and tune autovacuum thresholds.

**Gotcha 3: Long-running transactions block VACUUM**

VACUUM can't remove tuples visible to active transactions. A query running for 6 hours prevents cleanup of anything changed in those 6 hours.

## When to Use (and When Not To)

**Use regular VACUUM when:**
- Autovacuum is disabled (not recommended)
- You need immediate cleanup after bulk deletes
- Dead tuple ratio exceeds 20%

**Use VACUUM FULL when:**
- Table has excessive bloat (dead tuples > 50% of live)
- You can afford exclusive lock
- Regular VACUUM isn't reclaiming space

**Don't use VACUUM FULL when:**
- Table is actively queried
- Autovacuum is keeping up
- Downtime isn't acceptable
```

---

## Structure 3: Walkthrough

**Use when**: Providing step-by-step instructions for a specific task.

**Core pattern**: Goal, steps, gotchas, result.

### Template

```markdown
---
title: "[Action]: [Specific Goal]"
date: YYYY-MM-DD
draft: false
tags: ["tutorial", "specific-tech"]
summary: "[What you'll accomplish by the end]"
---

## Goal

[1 paragraph: what this walkthrough accomplishes]
- End state
- Why you'd want this

## Prerequisites

[Bulleted list]
- Required software/versions
- Required access/permissions
- Starting assumptions

## Steps

### Step 1: [Action]

[1-2 paragraphs of context]

```bash
# Command or code
```

[What to expect / how to verify]

### Step 2: [Action]

[Continue pattern...]

### Step N: Verify

[How to confirm success]
- Expected output
- Tests to run

## Gotchas

[Numbered list of common problems]
1. [Problem]: [Solution]
2. [Problem]: [Solution]

## Result

[1-2 paragraphs]
- What you now have
- Next steps (optional)
```

### Example: Walkthrough

```markdown
---
title: "Setting Up GitHub Actions for Go Projects"
date: 2024-12-15
draft: false
tags: ["tutorial", "go", "github-actions", "ci"]
summary: "A working CI pipeline for Go in 15 minutes. Tests, linting, and build verification."
---

## Goal

Create a GitHub Actions workflow that runs on every push. The workflow tests, lints, and builds a Go project. Failed checks block merges.

## Prerequisites

- Go 1.21 or later
- GitHub repository with Go code
- `go.mod` file in repository root

## Steps

### Step 1: Create the workflow file

GitHub Actions workflows live in `.github/workflows/`. Create the directory and file.

```bash
mkdir -p .github/workflows
touch .github/workflows/ci.yml
```

### Step 2: Add the workflow configuration

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.21'

      - name: Test
        run: go test -v ./...

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.21'

      - name: golangci-lint
        uses: golangci/golangci-lint-action@v4
        with:
          version: latest

  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Go
        uses: actions/setup-go@v5
        with:
          go-version: '1.21'

      - name: Build
        run: go build -v ./...
```

### Step 3: Commit and push

```bash
git add .github/workflows/ci.yml
git commit -m "Add CI workflow"
git push origin main
```

### Step 4: Verify the workflow runs

Go to your repository on GitHub. Click the "Actions" tab. You should see your workflow running.

Green checkmark: success. Red X: check the logs for failures.

### Step 5: Enable branch protection

Go to Settings > Branches > Add rule.

- Branch name pattern: `main`
- Check "Require status checks to pass before merging"
- Select: `test`, `lint`, `build`
- Save changes

## Gotchas

1. **golangci-lint fails on first run**: The action downloads the linter. If your code has lint errors, it fails. Run `golangci-lint run` locally first to fix issues.

2. **Tests pass locally but fail in CI**: Check for environment-specific code. CI runs on Ubuntu. Local might be macOS. Path separators and file permissions differ.

3. **Workflow doesn't trigger**: Check the branch name. `main` vs `master`. Check the `on:` triggers match your workflow.

4. **Build takes too long**: Add caching. The `setup-go` action caches by default in v5. If using v4, add explicit cache step.

## Result

Every push to `main` and every pull request now runs tests, linting, and build verification. Broken code can't reach main.

Total setup time: 10-15 minutes. Time saved per broken deploy: hours.
```

---

## Choosing a Structure

| If the content is... | Use... |
|---------------------|--------|
| A bug you fixed | Problem-Solution |
| A concept to teach | Technical Explainer |
| Steps to follow | Walkthrough |
| An opinion with evidence | Technical Explainer (adapted) |
| A comparison | Technical Explainer (adapted) |

When in doubt, use Problem-Solution. Technical blogs about solving frustrating problems fit this structure naturally.

---

## Combining Structures

Sometimes posts need multiple structures. Common combinations:

**Technical Explainer + Walkthrough**
- First half explains the concept
- Second half shows how to use it

**Problem-Solution + Technical Explainer**
- Describe the bug and fix
- Then explain why it worked (deeper dive)

**Walkthrough + Problem-Solution**
- Show the steps
- Include a "Troubleshooting" section for common failures

Keep transitions clean. Use clear headings to signal structure shifts.
