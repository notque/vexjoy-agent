# Banned Commit Message Patterns

List of prohibited phrases in commit messages, with explanations and alternatives.

## Default Banned Patterns (Always Enforced)

These patterns are ALWAYS banned regardless of repository CLAUDE.md settings:

### 1. "Generated with Claude Code"

**Why banned**:
- Adds noise without value
- Focus should be on WHAT changed and WHY, not HOW
- Commits should be professional and tool-agnostic

**Examples of violations**:
```
feat: add new feature

Generated with Claude Code
```

**Correct version**:
```
feat: add new feature

Implements XYZ functionality using ABC approach.
```

### 2. "Co-Authored-By: Claude"

**Why banned**:
- Claude is a tool, not a code author
- Attribution should be to human developers
- Legal/IP considerations (unclear ownership)

**Examples of violations**:
```
feat: add authentication

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Correct version**:
```
feat: add authentication

Implements OAuth2-based authentication flow.
```

### 3. "🤖 Generated"

**Why banned**:
- Emoji in professional commits (unless repository style requires)
- Implies automated/untrusted code
- Shifts responsibility away from committer

**Examples of violations**:
```
fix: resolve bug

🤖 Generated automatically by AI assistant
```

**Correct version**:
```
fix: resolve bug in authentication timeout

Increases timeout from 5s to 30s to handle slow connections.
```

### 4. "AI-generated"

**Why banned**:
- Similar to "Generated with Claude Code"
- Code ownership ambiguity
- Professional commit messages don't mention tools

**Examples of violations**:
```
refactor: improve error handling

AI-generated refactoring based on best practices.
```

**Correct version**:
```
refactor: improve error handling

Adds try/catch blocks around network operations and provides
specific error messages for common failure modes.
```

### 5. "Automated commit by AI"

**Why banned**:
- Implies lack of human review
- Reduces trust in commit quality
- Automated commits should still have meaningful messages

**Examples of violations**:
```
chore: update dependencies

Automated commit by AI - dependencies updated to latest versions
```

**Correct version**:
```
chore: update dependencies

Updates npm packages to latest stable versions:
- lodash: 4.17.19 → 4.17.21 (security fix)
- express: 4.17.1 → 4.18.0 (performance)
```

## Repository-Specific Banned Patterns

These are extracted from repository CLAUDE.md files and enforced in addition to defaults.

### Pattern Detection

The git-commit-flow skill automatically loads banned patterns from:
1. Repository CLAUDE.md (in git root)
2. Global ~/.claude/CLAUDE.md

**Example CLAUDE.md section**:
```markdown
## Git Commit Style

When creating git commits:
- Do NOT add "Generated with Claude Code" or similar attribution
- Do NOT add "Co-Authored-By: Claude" lines
- Write clean, professional commit messages focused on WHAT changed and WHY
```

From this section, the skill extracts:
- "Generated with Claude Code" (already in defaults)
- "Co-Authored-By: Claude" (already in defaults)

## Why Commit Message Quality Matters

### 1. Code Archeology

Developers spend significant time understanding WHY code exists:
```
❌ Bad: "update function"
   → No context, unclear intent

✅ Good: "fix: prevent race condition in cache invalidation"
   → Clear problem, searchable, specific
```

### 2. Git Blame / Git Log

Good commit messages make `git blame` and `git log` useful:
```bash
git log --grep="authentication"  # Find all auth-related commits
git log --since="2 weeks ago"    # Recent changes
git blame file.py                # Who changed this line and why?
```

### 3. Automated Changelog Generation

Tools like `conventional-changelog` parse commit messages:
```
feat: add user authentication  → Appears in "Features" section
fix: resolve login bug         → Appears in "Bug Fixes" section
docs: update README            → Skipped (documentation only)
```

### 4. Semantic Versioning

Conventional commits enable automatic version bumps:
```
fix: → 1.0.0 → 1.0.1 (PATCH)
feat: → 1.0.0 → 1.1.0 (MINOR)
BREAKING CHANGE: → 1.0.0 → 2.0.0 (MAJOR)
```

### 5. Code Review

Pull request reviewers rely on commit messages to understand changes:
```
❌ Bad: "update files" (15 files changed)
   → Reviewer has to inspect every file

✅ Good: "refactor: extract validation logic to separate module"
   → Reviewer understands intent immediately
```

## Attribution Alternatives

Instead of tool attribution, provide meaningful context:

### Alternative 1: Describe Approach
```
❌ Generated with Claude Code

✅ Uses dependency injection pattern to improve testability
```

### Alternative 2: Reference Standards
```
❌ AI-generated based on best practices

✅ Follows SOLID principles and Clean Architecture guidelines
```

### Alternative 3: Cite Sources
```
❌ Automated commit by AI

✅ Implementation based on Go effective patterns:
   https://go.dev/doc/effective_go
```

### Alternative 4: Explain Reasoning
```
❌ 🤖 Generated automatically

✅ Refactors for better error handling after analyzing common
   failure modes in production logs
```

## Common Attribution Questions

### Q: Should I mention I used Claude Code?

**A: No, in commit messages.**

Commit messages should focus on WHAT changed and WHY, not the tools used.

**Exception**: Internal documentation, learning logs, or team notes (not commits).

### Q: How do I give credit to Claude?

**A: You don't, in commits.**

Claude is a tool like your IDE or linter. You don't write:
- "feat: add feature (written in VS Code)"
- "fix: bug (debugged with Chrome DevTools)"

The committer takes responsibility for all committed code.

### Q: What about pair programming attribution?

**A: Use Co-Authored-By for HUMANS only.**

```
✅ Co-Authored-By: Alice Developer <alice@example.com>
✅ Co-Authored-By: Bob Engineer <bob@example.com>
❌ Co-Authored-By: Claude <noreply@anthropic.com>
```

### Q: Legal/IP concerns about AI-generated code?

**A: Consult your organization's legal team.**

Commit messages should still follow best practices regardless. Maintain separate documentation for IP tracking if required by your organization.

## Detection and Enforcement

### How Patterns Are Detected

The intended `validate_message.py` script (not yet implemented) would check each line:

```python
for pattern in banned_patterns:
    for i, line in enumerate(lines, start=1):
        if pattern.lower() in line.lower():
            # Issue detected at line i
```

**Case-insensitive matching**:
- "Generated with Claude Code" matches
- "generated with claude code" matches
- "GENERATED WITH CLAUDE CODE" matches

### Severity Levels

All banned pattern violations are **CRITICAL** severity:
- Commit will be blocked
- Must fix before proceeding
- No bypass (unless `--skip-validation` flag)

### Bypass (Not Recommended)

```bash
# Emergency bypass (use with caution)
git commit --no-verify -m "message"

# Or with git-commit-flow (commit.py not yet implemented)
# git commit --no-verify -m "message"
```

**Only bypass when**:
- Emergency hotfix (seconds matter)
- Repository doesn't use git-commit-flow
- Testing/experimentation (non-production)

**NEVER bypass for**:
- Production commits
- Public repositories
- Team collaboration
- Permanent changes

## Examples: Good vs Bad

### Example 1: New Feature

```
❌ BAD:
feat: add user authentication

Generated with Claude Code using best practices for OAuth2
implementation.

✅ GOOD:
feat: add user authentication

Implements OAuth2-based authentication with:
- Login/logout endpoints
- JWT token management
- Role-based access control (RBAC)

Chose OAuth2 for compatibility with external identity providers
(Google, GitHub, etc.).
```

### Example 2: Bug Fix

```
❌ BAD:
fix: authentication bug

🤖 Generated fix for timeout issue

✅ GOOD:
fix: resolve authentication timeout

Increases connection timeout from 5s to 30s to handle slow
networks. Adds retry logic (3 attempts with exponential backoff)
for transient failures.

Fixes #123
```

### Example 3: Refactoring

```
❌ BAD:
refactor: improve code

AI-generated refactoring based on SOLID principles

Co-Authored-By: Claude <noreply@anthropic.com>

✅ GOOD:
refactor: extract validation logic to separate module

Moves validation functions from main.py to validation.py to:
- Improve testability (isolated unit tests)
- Enable reuse across multiple scripts
- Reduce main.py complexity (SRP)
```

### Example 4: Documentation

```
❌ BAD:
docs: update README

Automated commit by AI - documentation improvements

✅ GOOD:
docs: add installation instructions to README

Adds step-by-step installation guide including:
- Prerequisites (Python 3.9+, npm)
- Setup commands
- Common troubleshooting steps

Addresses issue #45 (new users struggling with setup)
```

## Validation Script Usage

### Check for Banned Patterns

```bash
# TODO: scripts/validate_message.py not yet implemented
# Manual alternative: grep for banned patterns in commit message
echo "feat: add feature

Generated with Claude Code" | grep -inE 'Generated with Claude Code|Co-Authored-By: Claude'

# Expected output for banned pattern detected:
# 3:Generated with Claude Code
```

### Suggest Fixes

```bash
# TODO: scripts/validate_message.py not yet implemented
# Manual alternative: review message and remove banned patterns

# Output includes:
REMOVE BANNED PATTERNS:
  - Remove: Generated with Claude Code

Suggested revised message:
────────────────────────────────────────────────────────────────
feat: add feature

Implements XYZ functionality.
────────────────────────────────────────────────────────────────
```

## Adding Custom Banned Patterns

### Repository-Specific Patterns

Update repository CLAUDE.md:

```markdown
## Git Commit Style

When creating git commits:
- Do NOT add "WIP" in commit messages
- Do NOT use emoji (except 🔥 for hotfixes)
- Do NOT include ticket numbers in subject line
```

The skill will automatically detect and enforce these.

### Script-Level Patterns

When `scripts/validate_message.py` is implemented, custom patterns would be added as:

```python
DEFAULT_BANNED_PATTERNS = [
    "Generated with Claude Code",
    "Co-Authored-By: Claude",
    "🤖 Generated",
    "AI-generated",
    "Automated commit by AI",
    # Add custom patterns here:
    "WIP",
    "TODO: fix later",
]
```

## References

- [Conventional Commits](https://www.conventionalcommits.org/)
- [How to Write a Git Commit Message](https://chris.beams.io/posts/git-commit/)
- [Angular Commit Guidelines](https://github.com/angular/angular/blob/master/CONTRIBUTING.md#commit)
- Repository CLAUDE.md (project-specific rules)
