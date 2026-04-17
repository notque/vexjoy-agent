# Biome Rules Reference

> **Scope**: Common Biome rule categories, violation patterns, detection commands, and fixes for JavaScript and TypeScript code. Covers the rules most commonly triggered in real projects — not every rule in the full catalog.
> **Version range**: Biome 1.0+ (replaces Rome); config in `biome.json`
> **Generated**: 2026-04-16 — verify rule names against current Biome release notes

---

## Overview

Biome is a fast JavaScript/TypeScript linter and formatter replacing ESLint and Prettier. Rules are grouped into four categories: `correctness` (code that is likely wrong), `suspicious` (code that may be wrong), `style` (code that could be written more idiomatically), and `complexity` (code that is unnecessarily complex). The `check` command runs both lint and format checks together; `format` runs only formatting. `--write` applies fixes in place.

---

## Rule Category Table

| Category | What it catches | Auto-fixable |
|----------|----------------|-------------|
| `correctness` | Code that is definitely wrong | Some |
| `suspicious` | Code that might be wrong | Some |
| `style` | Idiomatic code improvements | Yes (most) |
| `complexity` | Unnecessary complexity | Some |
| `a11y` | Accessibility violations in JSX | No |
| `security` | Security anti-patterns | No |

**Common rules by category**:

| Rule | Category | Description |
|------|----------|-------------|
| `noDoubleEquals` | suspicious | Use `===` instead of `==` |
| `noVar` | style | Use `let`/`const` instead of `var` |
| `useConst` | style | Use `const` for never-reassigned variables |
| `noUnusedVariables` | correctness | Variable declared but never used |
| `noUnreachableCode` | correctness | Code after `return`/`throw`/`break` |
| `useTemplate` | style | Use template literals instead of string concatenation |
| `noConsole` | suspicious | `console.*` calls left in production code |
| `noExplicitAny` | suspicious | TypeScript `any` type annotation |
| `useOptionalChain` | complexity | Replace `&&` chains with `?.` optional chaining |
| `noArrayIndexKey` | suspicious | Array index used as React key prop |

---

## Correct Patterns

### Running check and format together

```bash
# Check everything (lint + format) — no changes
npx @biomejs/biome check src/

# Apply all safe fixes
npx @biomejs/biome check --write src/

# Format only (no lint)
npx @biomejs/biome format --write src/

# Check single file
npx @biomejs/biome check src/components/Button.tsx
```

**Why**: `biome check` covers both lint and format in one pass. Use `--write` instead of separate lint-fix and format steps.

---

### Disabling a rule for one line

```typescript
// biome-ignore lint/suspicious/noDoubleEquals: legacy API returns string
if (response.code == expectedCode) {
```

```typescript
// biome-ignore lint/correctness/noUnusedVariables: used in template
const _debug = process.env.DEBUG;
```

**Why**: Line-level suppression with a comment explaining the exception is auditable. File-level overrides in biome.json are harder to track.

---

### Per-file rule overrides in biome.json

```json
{
  "overrides": [
    {
      "include": ["**/*.test.ts", "**/*.spec.ts"],
      "linter": {
        "rules": {
          "suspicious": {
            "noConsole": "off"
          }
        }
      }
    },
    {
      "include": ["src/generated/**"],
      "linter": {
        "enabled": false
      }
    }
  ]
}
```

**Why**: Test files use `console.log` for debugging. Generated files should not be linted at all.

---

## Pattern Catalog

### ❌ Using `==` instead of `===` (noDoubleEquals)

**Detection**:
```bash
grep -rn '[^=!]==[^=]' --include="*.ts" --include="*.tsx" --include="*.js"
rg '[^=!]==[^=]' --type ts --type js
```

**What it looks like**:
```typescript
if (value == null) { }     // catches undefined too, but not obvious
if (count == "0") { }      // type coercion happens silently
if (response.status == 200) { }
```

**Why wrong**: `==` performs type coercion. `"0" == 0` is `true`. `null == undefined` is `true`. The behavior is defined but consistently surprises developers and makes code hard to reason about.

**Fix**:
```typescript
if (value === null || value === undefined) { }  // explicit
if (count === "0") { }
if (response.status === 200) { }
```

**Version note**: Exception: `value == null` (catches both null and undefined) is sometimes intentional. Use `// biome-ignore` with an explanation if this is deliberate.

---

### ❌ Using `var` instead of `let`/`const` (noVar)

**Detection**:
```bash
grep -rn '^\s*var ' --include="*.ts" --include="*.tsx" --include="*.js"
rg '^\s+var ' --type ts --type js
```

**What it looks like**:
```javascript
var count = 0;
var items = [];
for (var i = 0; i < items.length; i++) { }
```

**Why wrong**: `var` is function-scoped and hoisted. Loop variables bleed out of the loop body. Common source of closures capturing wrong values and use-before-declaration bugs.

**Fix**:
```typescript
const count = 0;        // never reassigned
let items: string[] = [];  // reassigned
for (let i = 0; i < items.length; i++) { }
```

---

### ❌ Using `let` when `const` suffices (useConst)

**Detection**:
```bash
ruff check --select UP .  # Python only — for JS/TS use Biome directly
npx @biomejs/biome check --reporter=json src/ | python3 -c "
import json,sys; data=json.load(sys.stdin)
[print(d['location']['path']['file'], d['rule_name']) for d in data.get('diagnostics',[]) if 'useConst' in d.get('rule_name','')]
"
```

**What it looks like**:
```typescript
let name = "Alice";   // never reassigned below
let config = { debug: false };  // object reference never changes
```

**Why wrong**: `let` signals intent to reassign. Using it for constants confuses readers about whether the value will change. Biome (useConst) and TypeScript compiler both flag this.

**Fix**:
```typescript
const name = "Alice";
const config = { debug: false };  // object contents can still mutate; reference is const
```

---

### ❌ TypeScript `any` type annotation (noExplicitAny)

**Detection**:
```bash
grep -rn ': any\b\|as any\b' --include="*.ts" --include="*.tsx"
rg ':\s*any\b|as any\b' --type ts
```

**What it looks like**:
```typescript
function process(data: any): any {
    return data.value;
}
const result = response as any;
```

**Why wrong**: `any` disables TypeScript's type checker for that value. Errors that TypeScript would catch at compile time become runtime crashes. Propagates through the codebase — one `any` can infect many downstream types.

**Fix**:
```typescript
function process(data: Record<string, unknown>): string {
    return String(data.value);
}

// When receiving from external API, use a type guard
interface ApiResponse { value: string; status: number; }
const result = response as ApiResponse;  // narrow with interface, not any
```

---

### ❌ String concatenation instead of template literals (useTemplate)

**Detection**:
```bash
grep -rn '".*" + \|+ ".*"' --include="*.ts" --include="*.tsx" --include="*.js"
rg '"[^"]*"\s*\+\s*\w+|\w+\s*\+\s*"[^"]*"' --type ts --type js
```

**What it looks like**:
```typescript
const message = "Hello " + name + "!";
const path = "/api/" + version + "/users/" + userId;
const sql = "SELECT * FROM " + table + " WHERE id = " + id;
```

**Why wrong**: String concatenation is verbose, harder to read, and error-prone when mixing numbers and strings. Template literals are clearer and prevent accidental type coercion in concatenation.

**Fix**:
```typescript
const message = `Hello ${name}!`;
const path = `/api/${version}/users/${userId}`;
const sql = `SELECT * FROM ${table} WHERE id = ${id}`;
```

---

### ❌ Optional chain avoidance (useOptionalChain)

**Detection**:
```bash
grep -rn '&& .*\.' --include="*.ts" --include="*.tsx"
rg '\w+\s*&&\s*\w+\.' --type ts
```

**What it looks like**:
```typescript
const city = user && user.address && user.address.city;
const len = arr && arr.length;
const name = response && response.data && response.data.user && response.data.user.name;
```

**Why wrong**: Manual null checks via `&&` chains are verbose and easy to get wrong (short-circuits at wrong level). TypeScript 3.7+ optional chaining is safer and more readable.

**Fix**:
```typescript
const city = user?.address?.city;
const len = arr?.length;
const name = response?.data?.user?.name;
```

**Version note**: Optional chaining (`?.`) available in TypeScript 3.7+, JavaScript ES2020. Biome's `useOptionalChain` rule was introduced in Biome 1.0.

---

## Error-Fix Mappings

| Error / Diagnostic | Root Cause | Fix |
|--------------------|------------|-----|
| `noDoubleEquals: Use === instead of ==` | Equality with type coercion | Replace `==` → `===`, `!=` → `!==` |
| `noVar: Use const or let instead of var` | Function-scoped variable | Replace `var` → `const` or `let` |
| `useConst: This let is never reassigned` | `let` used for immutable value | Replace `let` → `const` |
| `noUnusedVariables: 'X' is defined but never used` | Dead variable | Remove, or prefix with `_` for intentional unused params |
| `noExplicitAny: Unexpected any` | TypeScript type gap | Replace with specific type, `unknown`, or type guard |
| `useTemplate: Template literals are preferred` | String concatenation | Replace `"a" + b` → `` `a${b}` `` |
| `biome: command not found` | Not installed | `npm install --save-dev @biomejs/biome` |
| `Configuration file not found` | Missing biome.json | `npx @biomejs/biome init` to generate default config |
| `noConsole: Unexpected console statement` | Debug log left in | Remove or wrap in `if (process.env.NODE_ENV !== 'production')` |
| `organizeImports` formatter conflict | Biome reorders imports differently than ESLint | Disable ESLint organize-imports rule; let Biome own it |

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| Biome 1.0 | Initial stable release; replaces Rome | Config moves from `rome.json` → `biome.json` |
| Biome 1.2 | `--reporter=github` for CI annotations | Use in GitHub Actions for inline PR comments |
| Biome 1.5 | CSS formatter added | Biome can now format `.css` files alongside JS/TS |
| Biome 1.6 | GraphQL formatter added | `.graphql` files supported |
| Biome 1.8 | `biome migrate eslint` command | Migrate ESLint config to Biome rules automatically |

---

## Detection Commands Reference

```bash
# Run full check (lint + format), no changes
npx @biomejs/biome check src/

# Apply all auto-fixes
npx @biomejs/biome check --write src/

# Check only one rule category
npx @biomejs/biome check --only-rules lint/suspicious src/

# Find == (double-equals) in TypeScript
rg '[^=!]==[^=]' --type ts

# Find var declarations
rg '^\s+var ' --type ts --type js

# Find any type annotations
rg ':\s*any\b|as any\b' --type ts

# Find string concatenation patterns
rg '"[^"]*"\s*\+\s*\w+|\w+\s*\+\s*"[^"]*"' --type ts --type js

# Count violations by rule
npx @biomejs/biome check --reporter=json src/ 2>/dev/null | \
  python3 -c "import json,sys; [print(d.get('rule_name','?')) for d in json.load(sys.stdin).get('diagnostics',[])]" | \
  sort | uniq -c | sort -rn | head -20
```

---

## See Also

- `ruff-rules-reference.md` — Python linting with ruff
- [Biome documentation](https://biomejs.dev/)
- [Biome rules reference](https://biomejs.dev/linter/rules/)
