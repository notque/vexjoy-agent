# Verification Examples: Good vs Bad

This document shows real-world examples of good and bad verification practices to illustrate the defense-in-depth approach.

## Example 1: Python Bug Fix

### ❌ BAD Verification

**User**: Fix the login bug where passwords aren't being validated

**Assistant**: I've fixed the password validation in auth.py. The bug was that we weren't checking password length. Should be working now!

**Problems**:
- No tests run
- No code shown
- No verification of the fix
- Says "should be working" without evidence
- User has no confidence the fix works

---

### ✅ GOOD Verification

**User**: Fix the login bug where passwords aren't being validated

**Assistant**: I'll fix the password validation issue. Let me identify the problem and verify the fix.

**Step 1: Review the code**
```bash
$ cat -n /home/project/auth.py
    15  def validate_password(password):
    16      # TODO: Add validation
    17      return True
```

**Issue found**: Password validation always returns True

**Step 2: Implement fix**
```python
def validate_password(password):
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    return True
```

**Step 3: Run tests**
```bash
$ pytest tests/test_auth.py -v
============================= test session starts ==============================
platform linux -- Python 3.11.5, pytest-7.4.0
collected 5 tests

tests/test_auth.py::test_password_too_short PASSED                       [ 20%]
tests/test_auth.py::test_password_no_uppercase PASSED                    [ 40%]
tests/test_auth.py::test_password_no_digit PASSED                        [ 60%]
tests/test_auth.py::test_password_valid PASSED                           [ 80%]
tests/test_auth.py::test_login_with_invalid_password PASSED             [100%]

============================== 5 passed in 0.23s ==============================
```

**Step 4: Verify syntax**
```bash
$ python -m py_compile auth.py
$ echo $?
0
```

**Step 5: Check for unintended changes**
```bash
$ git diff auth.py
--- a/auth.py
+++ b/auth.py
@@ -14,7 +14,12 @@

 def validate_password(password):
-    # TODO: Add validation
-    return True
+    if len(password) < 8:
+        return False
+    if not any(c.isupper() for c in password):
+        return False
+    if not any(c.isdigit() for c in password):
+        return False
+    return True
```

**Verification Complete**:
- ✅ Tests pass (5/5)
- ✅ Syntax valid
- ✅ Only intended changes
- ✅ Password validation now enforces: min 8 chars, uppercase, digit

Test if this addresses the issue.

**Why this is better**:
- Shows actual test output (5 specific tests)
- Verifies syntax
- Shows git diff to prove only intended changes
- User can see exactly what was fixed
- No ambiguous "should work" language

---

## Example 2: Go Refactoring

### ❌ BAD Verification

**User**: Refactor the user service to use the new database package

**Assistant**: Done! I've refactored user.go to use the new db package. All the imports are updated and it should compile fine.

**Problems**:
- No build verification
- No test execution
- "Should compile" is speculation
- No evidence provided

---

### ✅ GOOD Verification

**User**: Refactor the user service to use the new database package

**Assistant**: I'll refactor the user service to use the new database package and verify everything still works.

**Step 1: Review changes**
```bash
$ git diff --name-only
internal/user/service.go
internal/user/repository.go
```

**Step 2: Run tests**
```bash
$ go test ./internal/user/... -v
=== RUN   TestUserService_Create
--- PASS: TestUserService_Create (0.01s)
=== RUN   TestUserService_Get
--- PASS: TestUserService_Get (0.01s)
=== RUN   TestUserService_Update
--- PASS: TestUserService_Update (0.01s)
=== RUN   TestUserService_Delete
--- PASS: TestUserService_Delete (0.01s)
=== RUN   TestUserRepository_FindByEmail
--- PASS: TestUserRepository_FindByEmail (0.02s)
PASS
ok      github.com/example/internal/user        0.156s
```

**Step 3: Run race detector**
```bash
$ go test -race ./internal/user/...
PASS
ok      github.com/example/internal/user        0.312s
```

**Step 4: Verify build**
```bash
$ go build ./...
$ echo $?
0
```

**Step 5: Check imports**
```bash
$ head -20 internal/user/service.go
package user

import (
    "context"
    "github.com/example/internal/db"  // New import
    "github.com/example/internal/models"
)
```

**Step 6: Verify no print statements**
```bash
$ grep -r "fmt.Println" internal/user/
$ echo $?
1
```
(Exit code 1 means no matches found - good!)

**Verification Complete**:
- ✅ Tests pass (5/5) with race detector
- ✅ Build succeeds
- ✅ New db package imported correctly
- ✅ No debug print statements
- ✅ Files reviewed: service.go, repository.go

Test if this addresses the issue.

---

## Example 3: JavaScript Feature Addition

### ❌ BAD Verification

**User**: Add a "Clear All" button to the dashboard

**Assistant**: I've added the Clear All button to Dashboard.jsx. It's wired up to call clearAllItems(). Everything looks good!

**Problems**:
- No build verification
- No tests run
- No visual confirmation
- "Looks good" is subjective

---

### ✅ GOOD Verification

**User**: Add a "Clear All" button to the dashboard

**Assistant**: I'll add the Clear All button and verify it works correctly.

**Step 1: Review changes**
```bash
$ git diff --name-only
src/components/Dashboard.jsx
src/components/Dashboard.test.jsx
```

**Step 2: Check syntax**
```bash
$ node -c src/components/Dashboard.jsx
$ echo $?
0
```

**Step 3: Run tests**
```bash
$ npm test -- Dashboard.test.jsx
 PASS  src/components/Dashboard.test.jsx
  Dashboard Component
    ✓ renders dashboard with items (45 ms)
    ✓ displays Clear All button (12 ms)
    ✓ calls clearAllItems when button clicked (23 ms)
    ✓ disables button when no items (8 ms)

Test Suites: 1 passed, 1 total
Tests:       4 passed, 4 total
Snapshots:   0 total
Time:        1.234 s
```

**Step 4: Build verification**
```bash
$ npm run build
> app@1.0.0 build
> react-scripts build

Creating an optimized production build...
Compiled successfully.

File sizes after gzip:

  52.3 kB  build/static/js/main.a1b2c3d4.js
  1.8 kB   build/static/css/main.e5f6g7h8.css

The build folder is ready to be deployed.
```

**Step 5: Check for console.log**
```bash
$ grep -n "console.log" src/components/Dashboard.jsx
$ echo $?
1
```
(No console.log statements found)

**Step 6: Review actual code**
```jsx
// Dashboard.jsx excerpt
<button
  className="btn btn-danger"
  onClick={clearAllItems}
  disabled={items.length === 0}
>
  Clear All
</button>
```

**Verification Complete**:
- ✅ Syntax valid
- ✅ Tests pass (4 new tests)
- ✅ Build succeeds (52.3 kB bundle)
- ✅ No console.log statements
- ✅ Button properly wired to clearAllItems()
- ✅ Button disabled when no items

Test if this addresses the issue.

---

## Example 4: Database Migration

### ❌ BAD Verification

**User**: Add an index on the email column in the users table

**Assistant**: Index added! I created the migration file and the index should improve query performance.

**Problems**:
- Migration not tested
- No verification it actually runs
- "Should improve" is speculation
- Doesn't check if index was created

---

### ✅ GOOD Verification

**User**: Add an index on the email column in the users table

**Assistant**: I'll create the migration and verify it works correctly.

**Step 1: Create migration**
```bash
$ ls migrations/
20250129_add_email_index.sql
```

**Step 2: Review migration content**
```sql
-- migrations/20250129_add_email_index.sql
-- Add index on users.email for faster lookups

BEGIN;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_email
ON users(email);

COMMIT;
```

**Step 3: Test migration on test database**
```bash
$ psql test_db -f migrations/20250129_add_email_index.sql
BEGIN
CREATE INDEX
COMMIT
```

**Step 4: Verify index exists**
```bash
$ psql test_db -c "\d users"
Table "public.users"
 Column |  Type   | Collation | Nullable | Default
--------+---------+-----------+----------+---------
 id     | integer |           | not null |
 email  | varchar |           |          |
Indexes:
    "users_pkey" PRIMARY KEY, btree (id)
    "idx_users_email" btree (email)  <--- NEW INDEX
```

**Step 5: Test query performance**
```bash
$ psql test_db -c "EXPLAIN SELECT * FROM users WHERE email = 'test@example.com';"
                                   QUERY PLAN
---------------------------------------------------------------------------------
 Index Scan using idx_users_email on users  (cost=0.42..8.44 rows=1 width=100)
   Index Cond: ((email)::text = 'test@example.com'::text)
```
(Using index scan - good!)

**Step 6: Test rollback**
```sql
-- migrations/20250129_add_email_index_down.sql
BEGIN;
DROP INDEX CONCURRENTLY IF EXISTS idx_users_email;
COMMIT;
```

```bash
$ psql test_db -f migrations/20250129_add_email_index_down.sql
BEGIN
DROP INDEX
COMMIT

$ psql test_db -c "\d users" | grep idx_users_email
$ echo $?
1
```
(Index successfully removed by rollback)

**Verification Complete**:
- ✅ Migration file created
- ✅ Migration runs successfully
- ✅ Index actually exists (verified with \d)
- ✅ Query uses index (verified with EXPLAIN)
- ✅ Rollback works correctly
- ✅ Uses CONCURRENTLY to avoid locks

Test if this addresses the issue.

---

## Example 5: Configuration Change

### ❌ BAD Verification

**User**: Update nginx config to add rate limiting

**Assistant**: Updated nginx.conf with rate limiting. The config should prevent abuse now.

**Problems**:
- Config not syntax-checked
- Not tested
- "Should prevent" is speculation
- No verification nginx accepts it

---

### ✅ GOOD Verification

**User**: Update nginx config to add rate limiting

**Assistant**: I'll update the nginx configuration and verify it's valid.

**Step 1: Review changes**
```bash
$ git diff nginx.conf
@@ -10,6 +10,9 @@ http {
     include       mime.types;
     default_type  application/octet-stream;

+    # Rate limiting
+    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
+
     server {
         listen 80;
         server_name example.com;
@@ -18,6 +21,8 @@ http {
             proxy_pass http://localhost:8000;
             proxy_set_header Host $host;
             proxy_set_header X-Real-IP $remote_addr;
+
+            limit_req zone=api_limit burst=20 nodelay;
         }
     }
 }
```

**Step 2: Syntax validation**
```bash
$ nginx -t -c /etc/nginx/nginx.conf
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

**Step 3: Check rate limit zone**
```bash
$ grep -A 1 "limit_req_zone" nginx.conf
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;
```

**Step 4: Dry-run reload**
```bash
$ nginx -s reload
2025/11/29 10:30:00 [notice] signal process started
```
(No errors - successful reload)

**Step 5: Test rate limiting**
```bash
$ for i in {1..15}; do curl -w "%{http_code}\n" -o /dev/null -s http://localhost/api/test; done
200
200
200
200
200
200
200
200
200
200
503
503
503
503
503
```
(First 10 requests succeed, next 5 rate-limited with 503)

**Verification Complete**:
- ✅ Syntax valid (nginx -t passed)
- ✅ Configuration reload successful
- ✅ Rate limit zone created (10m size, 10r/s limit)
- ✅ Rate limiting actually works (tested with curl)
- ✅ Burst handling configured (burst=20)

Test if this addresses the issue.

---

## Key Patterns in Good Verification

### 1. Multiple Independent Checks
Good verification uses multiple different validation methods:
- Syntax checkers (py_compile, node -c, gofmt)
- Tests (pytest, go test, npm test)
- Build verification (go build, npm run build)
- Runtime checks (start server, query database)
- Manual inspection (Read tool, git diff)

### 2. Show Actual Output
Never summarize - always show:
- Complete test results with test names
- Full build output
- Actual command output
- Exit codes

### 3. Evidence-Based Claims
Replace speculation with evidence:
- ❌ "Should work now"
- ✅ "Tests pass: [show output]"
- ❌ "Looks good"
- ✅ "Syntax valid: [show command]"
- ❌ "Index improves performance"
- ✅ "EXPLAIN shows index scan: [show output]"

### 4. Check for Unintended Changes
Always verify:
```bash
git diff                    # Review all changes
grep "console.log"          # No debug code
grep "TODO"                 # No leftover TODOs
grep "password\|secret"     # No credentials
```

### 5. Domain-Appropriate Verification
Different domains need different checks:
- **Python**: pytest + syntax + imports
- **Go**: tests + race detector + build + gofmt
- **JavaScript**: tests + syntax + build + bundle size
- **Database**: migration test + rollback test + EXPLAIN
- **Config**: syntax check + dry-run + actual reload

### 6. User-Friendly Format
Good verification provides:
- Clear step numbers
- Actual commands with $ prefix
- Complete output (not summaries)
- Checklist summary at end
- "Test if this addresses the issue" invitation

---

## Red Flags in Bad Verification

Watch for these warning signs:

1. **Speculation Language**:
   - "Should work"
   - "Should fix"
   - "Should prevent"
   - "Looks good"
   - "Seems fine"

2. **Missing Evidence**:
   - "Tests pass" (without showing output)
   - "Build succeeds" (without showing command)
   - "No errors" (without showing what was checked)

3. **Skipped Verification**:
   - "Small change, no need to test"
   - "Just config, won't break anything"
   - "Only comments changed"

4. **Incomplete Checks**:
   - Only syntax check, no tests
   - Only read code, no execution
   - Only manual review, no automation

5. **No User Confidence**:
   - User must still test blind
   - No evidence changes work
   - No visibility into verification process

---

## Verification Mindset

**Bad Mindset**: "I changed the code, it should work"

**Good Mindset**: "I changed the code, let me prove it works through multiple independent verification layers"

**Defense-in-Depth Principle**:
- **Layer 1**: Syntax validation
- **Layer 2**: Unit tests
- **Layer 3**: Integration tests
- **Layer 4**: Build verification
- **Layer 5**: Manual code review
- **Layer 6**: Runtime verification

Each layer catches different types of errors. Never rely on just one layer.

---

## Final Checklist

Before saying "done":
- [ ] Tests run (output shown)
- [ ] Build successful (output shown)
- [ ] Syntax validated (command shown)
- [ ] Files reviewed (Read tool used)
- [ ] Diff checked (git diff shown)
- [ ] No debug code (grep verified)
- [ ] No speculation (only evidence-based statements)
- [ ] User invited to test ("Test if this addresses the issue")

**Remember**: The goal isn't to check boxes - it's to have genuine confidence the changes work correctly.
