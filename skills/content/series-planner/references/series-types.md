# Series Types Reference

Complete templates for each series type with examples and selection criteria.

---

## Type Selection Matrix

| Topic Signal | Best Type | Example |
|--------------|-----------|---------|
| "learn", "master", "deep dive" | Progressive Depth | "Mastering Go Concurrency" |
| "build", "create", "project" | Chronological Build | "Building a REST API" |
| "why we chose", "migration" | Problem Exploration | "From Monolith to Microservices" |
| "vs", "comparison" | Problem Exploration | "SQL vs NoSQL for Our Use Case" |
| "tutorial", "guide", "how to" | Chronological Build | "Setting Up Kubernetes" |
| "internals", "how X works" | Progressive Depth | "Linux Process Scheduling" |

---

## Progressive Depth

### Template

```
Part 1: Basics [800-1000 words]
  Scope: Surface-level understanding, get started quickly
  Audience: Complete beginners
  Outcome: Reader can use the basic form

Part 2: Intermediate [1000-1200 words]
  Scope: Common use cases, real-world patterns
  Audience: Has basics, wants practical application
  Outcome: Reader handles 80% of cases

Part 3: Advanced [1000-1200 words]
  Scope: Edge cases, optimization, debugging
  Audience: Intermediate users hitting limits
  Outcome: Reader handles complex scenarios

Part 4 (optional): Expert [800-1000 words]
  Scope: Internals, architecture, extension points
  Audience: Power users, contributors
  Outcome: Reader understands the "why" deeply
```

### Standalone Value Pattern

- Part 1: Complete for basic use
- Part 2: Complete for everyday use (may reference Part 1 concepts briefly)
- Part 3: Complete for troubleshooting (assumes competence, not Part 1-2 reading)
- Part 4: Complete for deep understanding (stands alone as architecture doc)

### Example: "Hugo from Scratch"

```
Part 1: Your First Site [900 words]
  - Install Hugo
  - Create new site
  - Add first post
  - Local preview
  STANDALONE: Working Hugo site on localhost

Part 2: Themes and Templates [1100 words]
  - Installing a theme
  - Override layouts
  - Create partials
  - Custom CSS
  STANDALONE: Themed, styled Hugo site

Part 3: Content Types and Taxonomies [1100 words]
  - Archetypes
  - Content sections
  - Categories and tags
  - Custom taxonomies
  STANDALONE: Organized content architecture

Part 4: Deployment and Automation [900 words]
  - Build process
  - Cloudflare Pages setup
  - GitHub Actions
  - Cache and performance
  STANDALONE: Production deployment guide
```

---

## Chronological Build

### Template

```
Part 1: Setup [700-900 words]
  Scope: Environment, dependencies, project structure
  Milestone: Project scaffolding complete
  Output: Runnable (even if minimal) artifact

Part 2: Core [1000-1300 words]
  Scope: Primary functionality implementation
  Milestone: Main feature working
  Output: Functional (if rough) product

Part 3: Enhancement [900-1100 words]
  Scope: Polish, secondary features, UX
  Milestone: Product feels complete
  Output: Polished, usable product

Part 4: Production [800-1000 words]
  Scope: Deployment, monitoring, maintenance
  Milestone: Live in production
  Output: Deployed, observable product
```

### Standalone Value Pattern

Each part produces working output. Reader can stop at any milestone with something functional.

- Part 1: Scaffold is valid, builds, runs (even if it does nothing)
- Part 2: Core feature works end-to-end
- Part 3: Product is "complete enough" for real use
- Part 4: Production concerns addressed

### Example: "Building a CLI Tool in Go"

```
Part 1: Project Setup [800 words]
  - go mod init
  - Directory structure
  - Basic main.go
  - First command working
  MILESTONE: `mycli --help` works

Part 2: Core Commands [1200 words]
  - Command structure
  - Flags and arguments
  - Subcommands
  - Error handling
  MILESTONE: Core functionality complete

Part 3: Configuration [1000 words]
  - Config file support
  - Environment variables
  - State persistence
  - User preferences
  MILESTONE: Tool is polished for daily use

Part 4: Distribution [900 words]
  - Cross-compilation
  - Release workflow
  - Homebrew formula
  - Documentation
  MILESTONE: Others can install and use
```

---

## Problem Exploration

### Template

```
Part 1: Problem Space [800-1000 words]
  Scope: Symptoms, constraints, requirements
  Tone: "Here's what we were dealing with"
  Outcome: Reader understands the challenge

Part 2: First Approach [900-1100 words]
  Scope: Initial solution, implementation
  Tone: "Here's what we tried"
  Outcome: Reader learns from our attempt

Part 3: Hitting Walls [900-1100 words]
  Scope: Where it failed, what we learned
  Tone: "Here's where it broke down"
  Outcome: Reader avoids same mistakes

Part 4: Resolution [800-1000 words]
  Scope: Final solution, why it works
  Tone: "Here's what actually worked"
  Outcome: Reader has proven solution
```

### Standalone Value Pattern

Even failed approaches are instructive. Each part teaches something.

- Part 1: Problem analysis is valuable for anyone facing similar symptoms
- Part 2: First approach may work for simpler cases
- Part 3: Debugging insights apply broadly
- Part 4: Final solution stands as authoritative answer

### Example: "Why We Moved from Redis to PostgreSQL"

```
Part 1: The Caching Problem [900 words]
  - Application architecture
  - Performance requirements
  - Initial cache strategy
  - Why we chose Redis initially
  STANDALONE: Caching strategy analysis

Part 2: Redis Implementation [1000 words]
  - Redis setup
  - Caching patterns we used
  - What worked well
  - Early wins
  STANDALONE: Redis caching patterns

Part 3: Scaling Issues [1000 words]
  - Memory pressure at scale
  - Consistency problems
  - Operational complexity
  - Debugging the failures
  STANDALONE: Redis pitfalls and debugging

Part 4: PostgreSQL Solution [900 words]
  - Migration strategy
  - JSONB for flexibility
  - Performance results
  - Lessons learned
  STANDALONE: PostgreSQL as cache layer
```

---

## Hybrid Types

### Investigation Report (Problem-Solution + Technical Explainer)

For complex bugs requiring deep system understanding.

```
Part 1: The Symptom [700-900 words]
Part 2: Initial Hypotheses [900-1000 words]
Part 3: Deep Dive: [System] [1000-1200 words]
Part 4: Root Cause and Fix [900-1000 words]
```

### Tutorial with Context (Walkthrough + Why It Matters)

For when the "why" is as important as the "how."

```
Part 1: Why This Approach [800-1000 words]
Part 2: Foundation [900-1000 words]
Part 3: Implementation [1000-1200 words]
Part 4: Production Considerations [800-900 words]
```

---

## Type Selection Flowchart

```
What is the primary purpose?

Is it about learning/mastering?
  └── YES: Progressive Depth

Is it about building something?
  └── YES: Chronological Build

Is it about a journey (debugging, migration, decision)?
  └── YES: Problem Exploration

Does it combine elements?
  └── YES: Consider Hybrid

Still unclear?
  └── Default to Progressive Depth (most flexible)
```

---

## Part Count Guidelines

| Series Type | Minimum | Optimal | Maximum |
|-------------|---------|---------|---------|
| Progressive Depth | 3 | 4 | 5 |
| Chronological Build | 3 | 4 | 6 |
| Problem Exploration | 3 | 4 | 4 |
| Hybrid | 3 | 4 | 5 |

**Fewer than 3:** Probably not a series. Use single post.
**More than 6-7:** Consider splitting into multiple series.

---

## Word Count Targets by Type

| Series Type | Per Part | Total Series |
|-------------|----------|--------------|
| Progressive Depth | 900-1100 | 3,500-5,500 |
| Chronological Build | 900-1200 | 3,500-6,000 |
| Problem Exploration | 850-1000 | 3,400-4,000 |
| Hybrid | 900-1100 | 3,500-5,000 |

These targets assume a direct, technical style. Adjust for different voices.
