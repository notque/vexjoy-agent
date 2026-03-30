# Skill Creator Anti-Patterns

Common mistakes when designing skills and their corrections.

## ❌ Anti-Pattern: Description Without Triggers

**What it looks like**:
```yaml
description: |
  A comprehensive workflow automation tool for deployment pipelines.
```

**Why wrong**:
- /do router can't determine when to invoke skill
- Users can't discover when skill applies
- Undertriggers on relevant requests

**✅ Correct approach**:
```yaml
description: |
  Deploy applications to Kubernetes via Helm with validation gates. Use when
  user says "deploy", "release", "push to prod", or "helm upgrade". Do NOT
  use for Docker-only deploys (use docker-deploy skill).
```

**When to use**: Every skill - triggers are mandatory for discovery

---

## ❌ Anti-Pattern: Phases Without Gates

**What it looks like**:
```markdown
### Phase 1: Analyze
- Read configuration
- Validate inputs

### Phase 2: Execute
- Run deployment
- Update status
```

**Why wrong**:
- Phase 2 executes even if Phase 1 validation failed
- No clear failure points
- Cascading errors difficult to debug

**✅ Correct approach**:
```markdown
### Phase 1: Analyze
- Read configuration
- Validate inputs
- **GATE**: Configuration valid and all inputs verified

If gate fails:
- STOP execution
- Report validation errors
- Provide remediation steps

### Phase 2: Execute
- Run deployment
- Update status
- **GATE**: Deployment succeeded
```

**When to use**: All Medium+ complexity skills with multiple phases

---

## ❌ Anti-Pattern: Everything in Main File

**What it looks like**:
```
.claude/skills/my-complex-skill/
└── SKILL.md (4500 lines)
    - Frontmatter (100 lines)
    - Instructions (500 lines)
    - Error catalog (1500 lines)
    - Code examples (1200 lines)
    - Anti-patterns (800 lines)
    - Workflows (400 lines)
```

**Why wrong**:
- Bloats context with Level 3 details
- Violates progressive disclosure
- Makes skill hard to navigate
- Slower loading times

**✅ Correct approach**:
```
.claude/skills/my-complex-skill/
├── SKILL.md (1200 lines)
│   - Frontmatter (50 lines)
│   - Instructions (400 lines)
│   - Top 5 errors (200 lines)
│   - Top 5 anti-patterns (200 lines)
│   - Workflow summaries (200 lines)
│   - References section (150 lines)
└── references/
    ├── error-catalog.md (1200 lines)
    ├── code-examples.md (800 lines)
    ├── anti-patterns.md (600 lines)
    └── workflows.md (400 lines)
```

**When to use**: All Complex+ skills - anything approaching 2000+ lines needs references/

---

## ❌ Anti-Pattern: Vague What+When Formula

**What it looks like**:
```yaml
name: data-processor
description: |
  Processes various types of data files efficiently.
```

**Why wrong**:
- Doesn't state WHAT it actually does
- Doesn't state WHEN to use it
- Missing trigger phrases
- Will undertrigger

**✅ Correct approach**:
```yaml
name: csv-statistical-analyzer
description: |
  Advanced statistical analysis for CSV files: regression, clustering,
  time series forecasting. Use for "analyze data", "csv statistics",
  "regression analysis", "clustering". Do NOT use for simple data
  exploration (use data-viz skill instead).
```

**When to use**: Every skill - What+When is mandatory for all descriptions

---

## ❌ Anti-Pattern: Over-Engineering Simple Workflows

**What it looks like**:
Simple skill (pr-workflow (cleanup)) with:
- 6 phases with complex gates
- 15 error cases with detailed recovery
- 8 anti-patterns
- references/ directory with 4 files
- 2500 lines total

**Why wrong**:
- Simple workflow doesn't justify complexity
- Violates Over-Engineering Prevention
- Creates maintenance burden
- Confuses users

**✅ Correct approach**:
Simple skill (pr-workflow (cleanup)) with:
- 4 phases with basic gates
- 3-5 common errors inline
- 2-3 anti-patterns inline
- No references/ directory
- 300-600 lines total

**When to use**: Match complexity to workflow needs - don't add features "for completeness"

---

## ❌ Anti-Pattern: Missing Complexity Tier

**What it looks like**:
```yaml
routing:
  triggers:
    - deploy
  pairs_with:
    - verification-before-completion
  # Missing complexity field
  category: infrastructure
```

**Why wrong**:
- /do can't prioritize skill appropriately
- Skill evaluation can't assess if size matches tier
- Makes maintenance harder

**✅ Correct approach**:
```yaml
routing:
  triggers:
    - deploy
  pairs_with:
    - verification-before-completion
  complexity: Medium  # Add this
  category: infrastructure
```

**When to use**: Every skill - complexity is mandatory routing metadata

---

## ❌ Anti-Pattern: Infinite Retry Loops

**What it looks like**:
```markdown
### Phase 2: Refine
- Run quality check
- If fails: Go back to Phase 2
```

**Why wrong**:
- No exit condition
- Can loop indefinitely
- High token usage
- Session hangs

**✅ Correct approach**:
```markdown
### Phase 2: Refine (max 3 iterations)
- Run quality check
- If fails AND iterations < 3: Retry Phase 2
- If fails AND iterations = 3:
  - STOP execution
  - Report all failures
  - Suggest manual intervention
```

**When to use**: All iterative workflows - always include max iterations

---

## ❌ Anti-Pattern: Hardcoded Secrets

**What it looks like**:
```python
# scripts/deploy.py
API_KEY = "sk-1234567890abcdef"
DB_PASSWORD = "password123"

def deploy():
    connect(api_key=API_KEY, password=DB_PASSWORD)
```

**Why wrong**:
- Security risk
- Credential leaks
- Can't share skill
- Audit failures

**✅ Correct approach**:
```python
# scripts/deploy.py
import os

def deploy():
    api_key = os.environ.get("API_KEY")
    db_password = os.environ.get("DB_PASSWORD")

    if not api_key or not db_password:
        raise ValueError(
            "Required environment variables: API_KEY, DB_PASSWORD\n"
            "See references/setup.md for configuration"
        )

    connect(api_key=api_key, password=db_password)
```

**When to use**: All skills with credentials - never hardcode secrets

---

## ❌ Anti-Pattern: No Error Handling

**What it looks like**:
```markdown
## Instructions

### Step 1: Analyze
Run: `python3 ~/.claude/scripts/analyze.py --input file.csv`

### Step 2: Process
Run: `python3 ~/.claude/scripts/process.py --output results.json`
```

**Why wrong**:
- No guidance when commands fail
- Users stuck without solutions
- No recovery path

**✅ Correct approach**:
```markdown
## Instructions

### Step 1: Analyze
Run: `python3 ~/.claude/scripts/analyze.py --input file.csv`

### Step 2: Process
Run: `python3 ~/.claude/scripts/process.py --output results.json`

## Error Handling

### Error: "FileNotFoundError: file.csv"
**Cause**: Input file not found
**Solution**: Verify file path and run from correct directory

### Error: "ValueError: Invalid CSV format"
**Cause**: CSV file has formatting issues
**Solution**: Check for:
- Consistent column count
- Proper quoting
- Valid encoding (UTF-8)

### Error: "PermissionError: results.json"
**Cause**: Cannot write to output directory
**Solution**: `chmod +w $(dirname results.json)`
```

**When to use**: All Simple+ skills - minimum 3-5 error cases

---

## ❌ Anti-Pattern: Verbose Frontmatter

**What it looks like**:
```yaml
description: |
  This skill provides comprehensive deployment automation for modern
  cloud-native applications. It begins by validating your local
  environment including Docker, Kubernetes, kubectl, Helm, and all
  necessary CLI tools. Next, it builds your Docker image with
  optimized caching, tags it appropriately, and pushes to your
  configured container registry. Following that, it updates your
  Helm values files with the new image tag, runs Helm lint to
  validate your charts, and then performs a Helm upgrade with
  appropriate flags... [continues for 2000 characters]
```

**Why wrong**:
- Frontmatter loaded on EVERY request (token cost)
- Exceeds 1024 character limit
- Violates progressive disclosure
- Details belong in SKILL.md body

**✅ Correct approach**:
```yaml
description: |
  Deploy applications to Kubernetes via Helm with validation gates.
  Use for "deploy", "release", "helm upgrade", "push to prod". Do NOT
  use for Docker-only deploys. See SKILL.md for detailed workflow.
```

**When to use**: Every skill - keep frontmatter under 700 characters

---

## ❌ Anti-Pattern: Skill Naming Violations

**What it looks like**:
- Folder: `.claude/skills/DeploymentWizard/`
- Name: `deployment_ninja`
- File: `skill.md`

**Why wrong**:
- Case mismatch (folder vs file)
- Fancy names (wizard, ninja) instead of plain function names
- SKILL.md must be exact case
- Underscore instead of kebab-case

**✅ Correct approach**:
- Folder: `.claude/skills/deployment-automation/`
- Name: `deployment-automation`
- File: `SKILL.md`

**Naming Rules**:
- Folder and name: `{action}-{domain}` in kebab-case
- File: `SKILL.md` (exact case)
- No fancy terms: wizard, guru, ninja, master, oracle

**When to use**: Every skill - naming is non-negotiable

---

## ❌ Anti-Pattern: Mandates Without Motivation

**What it looks like**:
```markdown
## Instructions
- ALWAYS use structured logging
- NEVER use fmt.Println for error output
- MUST validate all inputs
- ALWAYS check return values
```

**Why wrong**:
- LLMs follow instructions better when they understand the reasoning
- Bare imperatives can't generalize to edge cases the author didn't anticipate
- All-caps MUSTs without explanation read as arbitrary rules rather than principled guidance
- When the model encounters an ambiguous case, understanding intent helps it make the right call

**✅ Correct approach**:
```markdown
## Instructions
- Use structured logging (fmt.Println output isn't captured by the log aggregator
  and can't be filtered by severity in production)
- Validate all inputs at service boundaries (malformed data here propagates
  silently through downstream services and surfaces as confusing errors later)
- Check return values — Go's error model depends on callers inspecting errors;
  ignored errors cause silent failures that are hard to debug in production
```

**Principle**: Explain the why AND keep your gates. Motivation makes the model follow willingly; gates catch failures regardless.

**When to use**: All skills — review every MUST/ALWAYS/NEVER and ask "does the model know why?"

---

## ❌ Anti-Pattern: Missing Negative Triggers

**What it looks like**:
```yaml
description: |
  Analyzes code and provides quality recommendations. Use for "code review",
  "check code", "analyze quality".
```

**Why wrong**:
- Skill will overtrigger on all code review requests
- Can't distinguish from specialized reviewers (security, performance)
- Users will disable due to overtriggering

**✅ Correct approach**:
```yaml
description: |
  General code quality analysis: style, complexity, maintainability. Use for
  "code review", "check quality", "analyze code". Do NOT use for security
  audits (use reviewer-security), performance analysis (use performance-
  optimization-engineer), or language-specific reviews (use go-patterns,
  python-code-review).
```

**When to use**: Skills with broad domains that could conflict with specialized skills
