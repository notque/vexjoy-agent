# PHP Quality Review Process

## Phase 1: ASSESS

Determine what kind of PHP quality review is needed:

| Request type | Load references | Action |
|-------------|----------------|--------|
| Code review | All quality refs | Full quality pass |
| Type system question | `modern-php-features.md` | Feature-specific guidance |
| Framework patterns | `framework-idioms.md` | Idiomatic pattern review |
| Tooling setup | `quality-tools.md` | Config and CI guidance |

**Gate**: Request classified and relevant references loaded.

## Phase 2: REVIEW

Apply loaded reference knowledge to the user's code or question. Every review checks:
1. `declare(strict_types=1)` present
2. PSR-12 compliance
3. Modern PHP features used where appropriate (from references)
4. Framework idioms followed (if applicable)
5. Quality tooling configured (if applicable)

**Gate**: Specific, reference-backed feedback provided.
