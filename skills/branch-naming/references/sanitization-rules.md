# Text Sanitization Rules for Branch Names

Rules for converting text descriptions to valid kebab-case branch names.

## Sanitization Pipeline

### Step 1: Lowercase
Convert entire string to lowercase.

```
Input:  "Add User Authentication"
Output: "add user authentication"
```

### Step 2: Strip Whitespace
Remove leading/trailing whitespace.

```
Input:  "  add user auth  "
Output: "add user auth"
```

### Step 3: Replace Spaces with Hyphens
Convert all whitespace (spaces, tabs) to hyphens.

```
Input:  "add user auth"
Output: "add-user-auth"
```

### Step 4: Replace Underscores with Hyphens
Convert underscores to hyphens (normalize to kebab-case).

```
Input:  "add_user_auth"
Output: "add-user-auth"
```

### Step 5: Remove Special Characters
Keep only a-z, 0-9, hyphens. Remove everything else.

```
Input:  "add-user-auth!!!"
Output: "add-user-auth"

Input:  "add-oauth2-login"
Output: "add-oauth2-login"  (numbers preserved)
```

### Step 6: Collapse Multiple Hyphens
Replace sequences of hyphens with single hyphen.

```
Input:  "add---user---auth"
Output: "add-user-auth"
```

### Step 7: Remove Leading/Trailing Hyphens
Strip hyphens from start and end.

```
Input:  "-add-user-auth-"
Output: "add-user-auth"
```

## Complete Examples

### Example 1: Standard Text
```
Input:    "Add User Authentication"
Step 1:   "add user authentication"      (lowercase)
Step 2:   "add user authentication"      (strip whitespace)
Step 3:   "add-user-authentication"      (spaces → hyphens)
Step 4:   "add-user-authentication"      (no underscores)
Step 5:   "add-user-authentication"      (no special chars)
Step 6:   "add-user-authentication"      (no multiple hyphens)
Step 7:   "add-user-authentication"      (no leading/trailing)
Output:   "add-user-authentication"
```

### Example 2: Mixed Case with Underscores
```
Input:    "Fix_Login_Timeout_Error"
Step 1:   "fix_login_timeout_error"
Step 2:   "fix_login_timeout_error"
Step 3:   "fix_login_timeout_error"
Step 4:   "fix-login-timeout-error"      (underscores → hyphens)
Step 5:   "fix-login-timeout-error"
Step 6:   "fix-login-timeout-error"
Step 7:   "fix-login-timeout-error"
Output:   "fix-login-timeout-error"
```

### Example 3: Special Characters
```
Input:    "Add OAuth2 Login!!!"
Step 1:   "add oauth2 login!!!"
Step 2:   "add oauth2 login!!!"
Step 3:   "add-oauth2-login!!!"
Step 4:   "add-oauth2-login!!!"
Step 5:   "add-oauth2-login"             (removed !!!)
Step 6:   "add-oauth2-login"
Step 7:   "add-oauth2-login"
Output:   "add-oauth2-login"
```

### Example 4: Extra Whitespace and Hyphens
```
Input:    "  Update   API---Documentation  "
Step 1:   "  update   api---documentation  "
Step 2:   "update   api---documentation"
Step 3:   "update---api---documentation"  (multiple spaces → hyphens)
Step 4:   "update---api---documentation"
Step 5:   "update---api---documentation"
Step 6:   "update-api-documentation"      (collapsed hyphens)
Step 7:   "update-api-documentation"
Output:   "update-api-documentation"
```

## Intelligent Truncation

When sanitized text exceeds length limit, apply intelligent truncation.

### Strategy 1: Remove Filler Words

Filler words to remove:
```
the, a, an, and, or, but, with, for, to, from, in, on, at,
by, of, as, is, was, are, were, be, been, being
```

Example:
```
Input:  "add-the-user-authentication-with-oauth2-and-jwt"
Remove: "the", "with", "and"
Output: "add-user-authentication-oauth2-jwt"
```

### Strategy 2: Apply Abbreviations

Common abbreviations:
```
authentication → auth
authorization  → authz
configuration  → config
development    → dev
environment    → env
production     → prod
repository     → repo
application    → app
database       → db
implementation → impl
documentation  → docs
```

Example:
```
Input:  "add-user-authentication-configuration"
Apply:  auth, config
Output: "add-user-auth-config"
```

### Strategy 3: Truncate at Word Boundaries

Preserve complete words, don't cut mid-word.

Example (max 30 chars):
```
Input:  "add-comprehensive-user-authentication-system"  (45 chars)
Truncate: Keep words until limit
Output: "add-comprehensive-user-auth"  (27 chars)
```

## Edge Cases

### Empty After Sanitization
```
Input:  "@#$%^&*()"
Output: ""  (ERROR: empty after sanitization)
```

**Recovery**: Prompt user for valid description with letters/numbers.

### Only Numbers
```
Input:  "123456"
Output: "123456"  ✓ (valid - numbers allowed)
```

### Leading Number
```
Input:  "2fa authentication"
Output: "2fa-authentication"  ✓ (valid)
```

### All Hyphens Removed
```
Input:  "---"
Output: ""  (ERROR: empty after sanitization)
```

### Unicode/Emoji
```
Input:  "add feature 🚀"
Output: "add-feature"  (emoji removed)
```

### Path-like Input
```
Input:  "auth/login/oauth2"
Output: "authloginoauth2"  (slashes removed except prefix)
```

## Validation After Sanitization

After sanitization, validate result:

1. **Non-empty**: Must have at least 1 character
2. **Valid characters**: Only a-z, 0-9, hyphens
3. **No leading/trailing hyphens**: Trimmed
4. **No multiple hyphens**: Collapsed
5. **Length limit**: ≤ available length after prefix

## Testing Sanitization

Test cases for validation:

```python
# Valid sanitizations
assert sanitize("Add User Auth") == "add-user-auth"
assert sanitize("Fix_Login_Bug") == "fix-login-bug"
assert sanitize("Update   Docs  ") == "update-docs"
assert sanitize("OAuth2-Login!!!") == "oauth2-login"

# Edge cases
assert sanitize("---test---") == "test"
assert sanitize("  ") == ""  # Empty after sanitization
assert sanitize("123-test") == "123-test"  # Numbers OK
```

## See Also

- [Naming Conventions](naming-conventions.md) - Full branch naming rules
- [Type Mapping](type-mapping.md) - Prefix determination
- [Examples](examples.md) - Real-world sanitization examples
