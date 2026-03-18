# Checkpoint Examples

Real-world examples of checkpoints from various scenarios.

## Example 1: Feature Implementation (Mid-Progress)

```markdown
# Context Checkpoint: Implementing user authentication flow

**Created**: 2025-12-29T10:30:00
**Session ID**: N/A
**Trigger**: manual
**Branch**: feature/auth-flow
**Recent Commit**: abc1234 feat: add base auth module

## Task State

- **Current task**: Implementing JWT-based user authentication with login/logout
- **Progress**: 60% (implementing token refresh)
- **Blockers**: None

## Files Context

### Read Files

- `src/auth/types.ts` - Type definitions for User and Token interfaces
- `src/auth/middleware.ts` - Existing auth middleware pattern to follow
- `tests/auth/test_login.py` - Test patterns for auth flows
- `CLAUDE.md` - Commit style requirements (no attribution)

### Modified Files

- `src/auth/jwt.ts` - Added token generation and validation functions
- `src/auth/routes.ts` - Added /login and /logout endpoints
- `tests/auth/test_jwt.py` - Added unit tests for JWT functions

## Decisions Made

1. **Use RS256 for JWT signing**: More secure than HS256 for production, allows key rotation
2. **Store refresh tokens in Redis**: Better performance than database for high-frequency token checks
3. **15-minute access token expiry**: Balance between security and user experience

## Debugging State

- **Current error**: N/A (not debugging)
- **Hypotheses tested**: N/A
- **Current hypothesis**: N/A
- **Attempts made**: N/A

## Discovered Patterns

- **Error response format**: All API errors use `{error: string, code: number}` format
- **Test file naming**: Tests mirror source files with `test_` prefix
- **Middleware order**: Auth middleware must come after CORS in middleware stack

## Next Steps

1. Implement token refresh endpoint at `src/auth/routes.ts:refresh()`
2. Add integration tests for full auth flow in `tests/auth/test_integration.py`
3. Update API documentation at `docs/api/auth.md`
4. Run full test suite: `pytest tests/ -v`

## Raw Context (for LLM)

```
TASK: Implementing JWT-based user authentication with login/logout
PROGRESS: 60%
BRANCH: feature/auth-flow
CURRENT_ERROR: none
HYPOTHESIS: none

FILES_READ:
- src/auth/types.ts: User and Token type definitions
- src/auth/middleware.ts: Auth middleware pattern
- tests/auth/test_login.py: Test patterns
- CLAUDE.md: Commit style (no attribution)

FILES_MODIFIED:
- src/auth/jwt.ts: Token generation/validation
- src/auth/routes.ts: Login/logout endpoints
- tests/auth/test_jwt.py: JWT unit tests

DECISIONS:
- RS256 for JWT: More secure, allows key rotation
- Redis for refresh tokens: Better performance
- 15-min access expiry: Security/UX balance

PATTERNS:
- Error format: {error: string, code: number}
- Test naming: test_ prefix mirrors source
- Middleware order: CORS before auth

NEXT:
1. Implement token refresh at src/auth/routes.ts:refresh()
2. Add integration tests at tests/auth/test_integration.py
3. Update docs at docs/api/auth.md
4. Run pytest tests/ -v
```
```

## Example 2: Debugging Session (Active Investigation)

```markdown
# Context Checkpoint: Debugging intermittent cache invalidation failure

**Created**: 2025-12-29T14:45:00
**Session ID**: N/A
**Trigger**: manual
**Branch**: fix/cache-race
**Recent Commit**: def5678 fix: add logging to cache module

## Task State

- **Current task**: Investigating race condition in cache invalidation that causes stale data
- **Progress**: 40% (isolated to cache module, testing hypothesis)
- **Blockers**: None (actively debugging)

## Files Context

### Read Files

- `src/cache/invalidate.ts` - Main invalidation logic, suspect area lines 45-80
- `src/cache/types.ts` - CacheEntry interface with TTL
- `tests/cache/test_invalidate.py` - Existing tests pass (don't cover concurrency)
- `logs/cache-error-20251229.log` - Error logs showing timing patterns

### Modified Files

- `src/cache/invalidate.ts` - Added debug logging at lines 50, 60, 70
- `tests/cache/test_concurrent.py` - New test for concurrent invalidation

## Decisions Made

1. **Add timing logs before fix**: Need evidence of race condition timing
2. **Create concurrent test first**: Reproduce before fixing

## Debugging State

- **Current error**: `StaleDataError: Cache returned expired entry after invalidation`
- **Hypotheses tested**:
  - Hypothesis 1: TTL calculation wrong - REFUTED (TTL values correct in logs)
  - Hypothesis 2: Invalidation message lost - REFUTED (Redis PUBLISH confirmed)
- **Current hypothesis**: Race between invalidation check and cache read - checking with timing logs
- **Attempts made**:
  - Added TTL logging - showed TTL values are correct
  - Checked Redis PUBLISH - messages are being sent
  - Added timing logs to narrow window - in progress

## Discovered Patterns

- **Cache key format**: `{prefix}:{entity}:{id}:{version}`
- **Invalidation pattern**: Publish to Redis channel, subscribers clear local cache
- **Timing pattern**: Errors cluster around cache warm-up period (first 30s after restart)

## Next Steps

1. Run concurrent test with timing logs: `pytest tests/cache/test_concurrent.py -v -s`
2. Analyze timing output to confirm race window
3. If confirmed, add mutex around invalidation check in `src/cache/invalidate.ts:checkAndInvalidate()`
4. Re-run concurrent tests to verify fix

## Raw Context (for LLM)

```
TASK: Debugging race condition in cache invalidation
PROGRESS: 40% (hypothesis testing)
BRANCH: fix/cache-race
CURRENT_ERROR: StaleDataError: Cache returned expired entry after invalidation
HYPOTHESIS: Race between invalidation check and cache read

FILES_READ:
- src/cache/invalidate.ts: Main logic, suspect lines 45-80
- src/cache/types.ts: CacheEntry interface
- tests/cache/test_invalidate.py: Existing tests (no concurrency coverage)
- logs/cache-error-20251229.log: Timing patterns in errors

FILES_MODIFIED:
- src/cache/invalidate.ts: Added debug logging
- tests/cache/test_concurrent.py: New concurrent test

DECISIONS:
- Add timing logs first: Need evidence before fix
- Create concurrent test: Reproduce before fixing

PATTERNS:
- Cache key: {prefix}:{entity}:{id}:{version}
- Invalidation: Redis PUBLISH, subscribers clear local
- Timing: Errors cluster in first 30s after restart

NEXT:
1. Run pytest tests/cache/test_concurrent.py -v -s
2. Analyze timing output
3. Add mutex in src/cache/invalidate.ts:checkAndInvalidate()
4. Re-run tests to verify
```
```

## Example 3: Pre-Compact Checkpoint (Automatic)

```markdown
# Context Checkpoint: Refactoring agent routing system

**Created**: 2025-12-29T16:20:00
**Session ID**: N/A
**Trigger**: pre-compact
**Branch**: refactor/routing
**Recent Commit**: ghi9012 refactor: extract routing logic

## Task State

- **Current task**: Refactoring agent routing from monolithic to composable system
- **Progress**: 75% (core routing done, testing edge cases)
- **Blockers**: Need to verify backward compatibility with existing agents

## Files Context

### Read Files

- `agents/*.md` - All agent files to understand routing patterns
- `skills/skill-composer/SKILL.md` - Example of multi-skill routing
- `commands/do.md` - Main routing entry point

### Modified Files

- `lib/routing.py` - New routing engine with composable rules
- `lib/matcher.py` - Pattern matching for agent selection
- `tests/test_routing.py` - Comprehensive routing tests
- `agents/router-agent.md` - Updated to use new routing engine

## Decisions Made

1. **Keep backward compatibility**: Existing agent triggers must still work
2. **Composable rules**: Allow combining multiple routing criteria
3. **Explicit over implicit**: Prefer explicit routing over inference

## Debugging State

- **Current error**: N/A
- **Hypotheses tested**: N/A
- **Current hypothesis**: N/A
- **Attempts made**: N/A

## Discovered Patterns

- **Agent routing metadata**: YAML frontmatter with `routing:` section
- **Trigger keywords**: Listed in `routing.triggers` array
- **Complexity tiers**: Simple/Medium/Complex/Comprehensive affects routing priority

## Next Steps

1. Test edge case: ambiguous triggers matching multiple agents
2. Add fallback behavior for no-match scenarios
3. Update documentation in `docs/routing.md`
4. Run full test suite before merge: `pytest tests/ -v`

## Raw Context (for LLM)

```
TASK: Refactoring agent routing from monolithic to composable
PROGRESS: 75%
BRANCH: refactor/routing
CURRENT_ERROR: none
HYPOTHESIS: none

FILES_READ:
- agents/*.md: All agent routing patterns
- skills/skill-composer/SKILL.md: Multi-skill routing example
- commands/do.md: Main routing entry

FILES_MODIFIED:
- lib/routing.py: New composable routing engine
- lib/matcher.py: Pattern matching
- tests/test_routing.py: Comprehensive tests
- agents/router-agent.md: Updated for new engine

DECISIONS:
- Backward compat: Existing triggers must work
- Composable: Allow combining routing criteria
- Explicit: Prefer explicit routing over inference

PATTERNS:
- Routing metadata: YAML frontmatter routing: section
- Triggers: routing.triggers array
- Complexity: Affects routing priority

NEXT:
1. Test ambiguous trigger edge case
2. Add no-match fallback behavior
3. Update docs/routing.md
4. Run pytest tests/ -v
```
```

## Example 4: Minimal Checkpoint (Quick Save)

```markdown
# Context Checkpoint: Quick save before meeting

**Created**: 2025-12-29T09:55:00
**Session ID**: N/A
**Trigger**: manual
**Branch**: feature/api-v2
**Recent Commit**: jkl3456 wip: api endpoint scaffolding

## Task State

- **Current task**: Implementing API v2 endpoints
- **Progress**: 25% (scaffolding done, implementing first endpoint)
- **Blockers**: None

## Files Context

### Read Files

- `src/api/v1/routes.ts` - Reference for endpoint patterns

### Modified Files

- `src/api/v2/routes.ts` - New v2 endpoint scaffolding
- `src/api/v2/handlers/users.ts` - Started users endpoint

## Decisions Made

1. **Mirror v1 structure**: Keep v2 structure similar for easier migration

## Debugging State

- **Current error**: N/A
- **Hypotheses tested**: N/A
- **Current hypothesis**: N/A
- **Attempts made**: N/A

## Discovered Patterns

*No patterns recorded*

## Next Steps

1. Complete users endpoint in `src/api/v2/handlers/users.ts`
2. Add validation middleware

## Raw Context (for LLM)

```
TASK: Implementing API v2 endpoints
PROGRESS: 25%
BRANCH: feature/api-v2
CURRENT_ERROR: none
HYPOTHESIS: none

FILES_READ:
- src/api/v1/routes.ts: Endpoint patterns

FILES_MODIFIED:
- src/api/v2/routes.ts: v2 scaffolding
- src/api/v2/handlers/users.ts: Users endpoint WIP

DECISIONS:
- Mirror v1 structure: Easier migration

PATTERNS:
- none

NEXT:
1. Complete src/api/v2/handlers/users.ts
2. Add validation middleware
```
```

## Usage Notes

### When to Create Detailed vs Minimal Checkpoints

**Detailed checkpoint** (like Examples 1, 2, 3):
- Complex debugging sessions
- Multi-day implementations
- Before long breaks
- When patterns discovered are valuable

**Minimal checkpoint** (like Example 4):
- Quick break (meeting, lunch)
- Simple task with clear next step
- Context is mostly in git history

### What Makes a Good Checkpoint

1. **Actionable next steps**: Can resume immediately from checkpoint
2. **Key insights captured**: Don't need to re-read files to understand
3. **Decision rationale**: Why, not just what
4. **Specific file paths**: Not "update the config" but "update `src/config.ts:15-20`"
