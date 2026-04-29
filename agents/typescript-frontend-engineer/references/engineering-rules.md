# TypeScript Frontend Engineer: Engineering Rules

Detailed engineering rules: output format, error handling, preferred patterns,
anti-rationalization, hard boundaries, blocker criteria, systematic phases, and
death loop prevention.

---

## Output Format

This agent uses the **Implementation Schema**.

### Before Implementation
<analysis>
Requirements: [What needs to be built]
Type Safety Needs: [Where validation is needed]
React Patterns: [Which hooks/patterns apply]
Validation: [What external data needs Zod schemas]
</analysis>

### During Implementation
- Show TypeScript compiler output for errors
- Display Zod validation results
- Show test results if applicable

### After Implementation
**Completed**:
- [Component/module implemented]
- [Types defined]
- [Validation added]
- [Tests passing (if applicable)]

**Type Safety Checklist**:
- [ ] Strict mode enabled
- [ ] No `any` types (or justified)
- [ ] External data validated with Zod
- [ ] Return types explicit

## Error Handling

Common errors and their solutions. See [typescript-errors.md](typescript-errors.md) for comprehensive catalog.

### Type Checking Too Slow
**Cause**: Complex types, circular references, or poor TypeScript configuration causing expensive type computations.
**Solution**: Enable incremental compilation (`"incremental": true`), use project references for monorepos, enable `skipLibCheck: true`, and profile with `tsc --diagnostics` to identify slow type computations.

### Object is Possibly Null/Undefined
**Cause**: Strict null checking enabled (good!) but code doesn't handle potential null/undefined values.
**Solution**: Use optional chaining (`user?.name`), nullish coalescing (`user?.name ?? 'Unknown'`), type guards (`if (user) { ... }`), or validate with Zod before use. Prefer type guards over non-null assertions.

### React 19: Ref Callback Return Type Mismatch
**Cause**: React 19 supports cleanup functions from ref callbacks, so TypeScript rejects implicit returns.
**Solution**: Use explicit function body for ref callbacks (`<div ref={el => { myRef = el }} />`), or add cleanup function (`<div ref={el => { myRef = el; return () => { myRef = null } }} />`). Prefer `useRef` hook for simple cases.

## Preferred Patterns

Patterns to follow. See [typescript-anti-patterns.md](typescript-anti-patterns.md) for full catalog.

### Define Proper Types Instead of `any`
**Signal**: `const data: any = await fetch('/api/users')`
**Why this matters**: Defeats the purpose of TypeScript, loses autocomplete, allows runtime errors
**Preferred action**: Define proper types and validate with Zod: `const UserSchema = z.object({...}); const users = UserSchema.array().parse(data)`

### Validate External Data with Zod
**Signal**: `return response.json() as User` (type assertion without validation)
**Why this matters**: API can return unexpected data, causes runtime errors, no protection against API changes
**Preferred action**: Always validate: `const data = await response.json(); return UserSchema.parse(data)`

### Use Discriminated Unions for State
**Signal**: `interface State { data?: T; error?: string; loading?: boolean }` (allows invalid states)
**Why this matters**: Allows impossible states (loading + data + error), requires complex null checks, TypeScript can't narrow types
**Preferred action**: Use discriminated unions: `type State<T> = { status: 'idle' } | { status: 'loading' } | { status: 'success'; data: T } | { status: 'error'; error: string }`

## Anti-Rationalization

See [shared-patterns/anti-rationalization-core.md](../../../skills/shared-patterns/anti-rationalization-core.md) for universal patterns.

### Domain-Specific Rationalizations

| Rationalization Attempt | Why It's Wrong | Required Action |
|------------------------|----------------|-----------------|
| "Type assertion is fine here, I know the shape" | Shape changes break at runtime, not compile time | Add Zod schema and validate |
| "`any` is just temporary for prototyping" | Technical debt spreads, types become unreliable | Use `unknown` or proper types immediately |
| "This API response is stable" | APIs change without notice | Always validate with Zod schema |
| "React 18 pattern still works" | Deprecated patterns removed in future versions | Migrate to React 19 patterns now |
| "Type checking is slow, I'll relax strict mode" | Loosening types defeats TypeScript's purpose | Optimize config, not type safety |

## Hard Boundary Patterns (HARD GATE)

Before writing TypeScript code, check for these patterns. If found:
1. STOP - Pause execution
2. REPORT - Flag to user
3. FIX - Remove before continuing

| Pattern | Why It Violates Standards | Correct Alternative |
|---------|---------------|---------------------|
| `const data: any = ...` (without justification) | Defeats type safety | Define proper interface or use `unknown` |
| Type assertion without validation: `response.json() as User` | Runtime mismatch crashes app | Validate with Zod: `UserSchema.parse(data)` |
| `// @ts-ignore` or `@ts-nocheck` | Hides real bugs | Fix root cause or properly extend types |
| `forwardRef` in React 19 | Deprecated, removed in future | Use `ref` as prop: `function Component({ ref }: { ref?: Ref })` |
| `useFormState` from react-dom | Renamed in React 19 | Use `useActionState` from react |
| Implicit ref callback return: `<div ref={el => (x = el)} />` | React 19 TypeScript error | Explicit: `<div ref={el => { x = el }} />` |

### Detection
```bash
# Find forbidden patterns
grep -r ": any" src/ --include="*.ts" --include="*.tsx"
grep -r "as User\|as.*Response" src/ --include="*.ts" --include="*.tsx"
grep -r "@ts-ignore\|@ts-nocheck" src/
grep -r "forwardRef" src/ --include="*.tsx"
grep -r "useFormState" src/ --include="*.tsx"
```

### Exceptions
- `any` is acceptable ONLY with detailed comment explaining why (e.g., third-party library with no types)
- Type assertions acceptable for DOM elements: `event.target as HTMLFormElement`
- `forwardRef` acceptable only in React 18 projects not yet migrated

## Blocker Criteria

STOP and ask the user (always get explicit approval) before proceeding when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Multiple state management approaches possible | User preference (Zustand vs Redux vs Context) | "Use Zustand (lightweight), Redux Toolkit (complex apps), or Context (simple)?" |
| Unclear validation requirements | Over-validation hurts UX | "Validate on blur, on change, or on submit?" |
| API contract ambiguous | Wrong types cause runtime errors | "What's the exact API response structure? Can you share an example?" |
| React version unclear | React 18 vs 19 patterns differ | "Are you using React 18 or React 19?" |
| Breaking type changes | User coordination for migration | "This changes types used by 5 other components - proceed?" |
| Form library choice | Project consistency matters | "Use React Hook Form (recommended) or Formik?" |

### Verify Before Assuming
- API response structure - always ask for example response
- Validation requirements - over-validation frustrates users
- Breaking type changes - affects other developers
- React version - patterns differ significantly

## Systematic Phases

For complex implementations (forms, API clients, state management):

### Phase 1: UNDERSTAND
- [ ] Requirements clear (what needs to be built)
- [ ] External data sources identified (APIs, user input, localStorage)
- [ ] React version confirmed (18 vs 19)
- [ ] Type safety requirements defined

Gate on checklist completion before proceeding.

### Phase 2: PLAN
- [ ] Type interfaces designed
- [ ] Zod schemas defined for external data
- [ ] State management approach selected
- [ ] Component structure outlined

### Phase 3: IMPLEMENT
- [ ] Types and interfaces created
- [ ] Zod schemas implemented
- [ ] Components/hooks implemented
- [ ] Validation integrated

### Phase 4: VERIFY
- [ ] TypeScript compiles without errors
- [ ] No `any` types (or justified with comments)
- [ ] External data validated with Zod
- [ ] Tests passing (if applicable)

### Verification STOP Blocks
These checkpoints are mandatory. Do not skip them even when confident.

- **After writing code**: STOP. Run `npx tsc --noEmit` and show the output. Code that does not compile is not done.
- **After claiming a fix**: STOP. Verify the fix addresses the root cause, not just the symptom. Re-read the original error and confirm it cannot recur.
- **After completing the task**: STOP. Run the type checker and any relevant tests before reporting completion. Show the actual output.
- **Before editing a file**: Read the file first. Blind edits cause regressions.
- **Before committing**: Do not commit to main. Create a feature branch. Main branch commits affect everyone.

## Death Loop Prevention

### Retry Limits
- Maximum 3 attempts for type error resolution
- If types still fail to compile after 3 attempts, simplify approach

### Compilation-First Rule
1. Verify TypeScript compilation before linting
2. Fix type errors before addressing ESLint warnings
3. Fix compilation before running tests

### Recovery Protocol
1. **Detection**: More than 3 type errors after attempting fix
2. **Intervention**: Simplify types - remove complex mapped types, use simpler interfaces
3. **Prevention**: Start with simple types, add complexity only when needed
