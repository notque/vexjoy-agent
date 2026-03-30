# Common Task Patterns

This document describes common task patterns and their verification strategies. Use these patterns when breaking down work into executable tasks.

**Note**: Examples reference various frameworks (Django, Flask, React, etc.). Adapt commands to match your project's tech stack.

## Pattern Categories

1. **File Creation Patterns** - Creating new files and resources
2. **File Modification Patterns** - Updating existing files
3. **Database Patterns** - Schema changes and migrations
4. **Testing Patterns** - Adding and running tests
5. **Configuration Patterns** - Updating system configuration
6. **Build & Deploy Patterns** - Compilation and deployment tasks
7. **Validation Patterns** - Verification and checking tasks

---

## 1. File Creation Patterns

### Pattern: Create Python Module

**When to use**: Creating new Python file with class or functions

**Task Structure**:
```json
{
  "task_id": "T1",
  "title": "Create [module_name] module",
  "estimated_duration": "3 minutes",
  "files": ["/absolute/path/to/module_name.py"],
  "operations": [
    "Create module_name.py file",
    "Add module docstring",
    "Define [Class/Function] with type hints",
    "Add basic error handling"
  ],
  "verification": {
    "command": "python3 -c 'import module_name; print(dir(module_name))'",
    "expected_output": "['ClassName', 'function_name']",
    "success_criteria": "Module imports successfully and exports expected names"
  }
}
```

**Verification Alternatives**:
- Type checking: `mypy /path/to/module_name.py`
- Linting: `pylint /path/to/module_name.py`
- Import test: `python3 -c 'import module_name'`

### Pattern: Create React Component

**When to use**: Creating new React/TypeScript component

**Task Structure**:
```json
{
  "task_id": "T1",
  "title": "Create [ComponentName] component",
  "estimated_duration": "4 minutes",
  "files": ["/absolute/path/to/ComponentName.tsx"],
  "operations": [
    "Create ComponentName.tsx file",
    "Define TypeScript props interface",
    "Implement functional component",
    "Export component"
  ],
  "verification": {
    "command": "npx tsc --noEmit --project /path/to/tsconfig.json",
    "expected_output": "No errors",
    "success_criteria": "TypeScript compiles without errors"
  }
}
```

**Verification Alternatives**:
- ESLint: `npx eslint /path/to/ComponentName.tsx`
- Import test: `node -e "require('./ComponentName')"`
- Build test: `npm run build`

### Pattern: Create Configuration File

**When to use**: Adding new YAML, JSON, or INI configuration

**Task Structure**:
```json
{
  "task_id": "T1",
  "title": "Create [config_name] configuration",
  "estimated_duration": "2 minutes",
  "files": ["/absolute/path/to/config.yaml"],
  "operations": [
    "Create config.yaml file",
    "Define required configuration keys",
    "Add default values",
    "Add comments explaining options"
  ],
  "verification": {
    "command": "python3 -c 'import yaml; yaml.safe_load(open(\"/path/to/config.yaml\"))'",
    "expected_output": "No exceptions",
    "success_criteria": "YAML file is valid and parseable"
  }
}
```

**Verification Alternatives**:
- JSON: `python3 -m json.tool < config.json`
- YAML: `yamllint config.yaml`
- INI: `python3 -c 'import configparser; c = configparser.ConfigParser(); c.read("config.ini")'`

### Pattern: Create Database Migration

**When to use**: Adding new database schema change

**Task Structure**:
```json
{
  "task_id": "T1",
  "title": "Create migration for [table_name]",
  "estimated_duration": "3 minutes",
  "files": ["/absolute/path/to/migrations/0001_create_table.py"],
  "operations": [
    "Create migration file with timestamp",
    "Define up migration (create table/add column)",
    "Define down migration (rollback logic)",
    "Add migration dependencies"
  ],
  "verification": {
    "command": "python manage.py migrate --plan",
    "expected_output": "0001_create_table",
    "success_criteria": "Migration appears in plan without errors"
  }
}
```

**Verification Alternatives**:
- Django: `python manage.py sqlmigrate app_name 0001`
- Alembic: `alembic upgrade --sql head`
- Flyway: `flyway validate`

---

## 2. File Modification Patterns

### Pattern: Add Function to Existing Module

**When to use**: Extending existing Python module with new function

**Task Structure**:
```json
{
  "task_id": "T2",
  "title": "Add [function_name] to [module]",
  "estimated_duration": "3 minutes",
  "files": ["/absolute/path/to/existing_module.py"],
  "operations": [
    "Add function_name with type hints",
    "Add docstring with examples",
    "Implement function logic",
    "Add to __all__ export list"
  ],
  "verification": {
    "command": "python3 -c 'from module import function_name; print(function_name.__doc__)'",
    "expected_output": "Function docstring appears",
    "success_criteria": "Function is importable and has documentation"
  }
}
```

**Verification Alternatives**:
- Test existing functions: `python3 -m pytest tests/test_module.py`
- Check exports: `python3 -c 'import module; print(module.__all__)'`
- Type check: `mypy module.py`

### Pattern: Update API Route

**When to use**: Modifying existing API endpoint behavior

**Task Structure**:
```json
{
  "task_id": "T2",
  "title": "Update [endpoint] to support [feature]",
  "estimated_duration": "4 minutes",
  "files": ["/absolute/path/to/routes/endpoint.py"],
  "operations": [
    "Add new parameter to route function",
    "Add validation for new parameter",
    "Update response format",
    "Maintain backward compatibility"
  ],
  "verification": {
    "command": "curl -X GET http://localhost:5000/api/endpoint?new_param=test",
    "expected_output": "200 OK",
    "success_criteria": "Endpoint accepts new parameter and returns success"
  }
}
```

**Verification Alternatives**:
- Integration test: `python3 -m pytest tests/test_endpoint.py`
- OpenAPI validation: `swagger-cli validate openapi.yaml`
- Manual test: `curl -v http://endpoint`

### Pattern: Refactor Class

**When to use**: Restructuring existing class without changing interface

**Task Structure**:
```json
{
  "task_id": "T2",
  "title": "Refactor [ClassName] for [reason]",
  "estimated_duration": "5 minutes",
  "files": ["/absolute/path/to/class_module.py"],
  "operations": [
    "Extract helper methods",
    "Simplify complex logic",
    "Add type hints",
    "Preserve public interface"
  ],
  "verification": {
    "command": "python3 -m pytest tests/test_class_module.py -v",
    "expected_output": "All tests pass",
    "success_criteria": "All existing tests pass without modification"
  }
}
```

**Verification Alternatives**:
- Coverage: `pytest --cov=module --cov-report=term-missing`
- Type check: `mypy class_module.py`
- Import test: `python3 -c 'from module import ClassName'`

---

## 3. Database Patterns

### Pattern: Add Database Column

**When to use**: Adding new field to existing table

**Task Structure**:
```json
{
  "task_id": "T3",
  "title": "Add [column_name] to [table_name]",
  "estimated_duration": "3 minutes",
  "files": ["/absolute/path/to/migrations/000X_add_column.py"],
  "operations": [
    "Create migration adding column",
    "Set column type and constraints",
    "Add default value for existing rows",
    "Add index if needed for queries"
  ],
  "verification": {
    "command": "python manage.py migrate && python manage.py dbshell -c '\\d table_name'",
    "expected_output": "column_name appears in schema",
    "success_criteria": "Column exists with correct type and constraints"
  }
}
```

**Verification Alternatives**:
- SQL check: `SELECT column_name FROM information_schema.columns WHERE table_name='table_name'`
- ORM check: `python3 -c 'from models import Model; print(Model._meta.fields)'`
- Data check: `SELECT column_name FROM table_name LIMIT 1`

### Pattern: Create Database Index

**When to use**: Adding index to improve query performance

**Task Structure**:
```json
{
  "task_id": "T3",
  "title": "Add index on [column] for [table]",
  "estimated_duration": "2 minutes",
  "files": ["/absolute/path/to/migrations/000X_add_index.py"],
  "operations": [
    "Create migration adding index",
    "Specify index type (btree, hash, etc.)",
    "Add concurrent creation flag if needed",
    "Document query being optimized"
  ],
  "verification": {
    "command": "python manage.py dbshell -c '\\di table_name_*'",
    "expected_output": "index_name appears in list",
    "success_criteria": "Index exists on specified column"
  }
}
```

**Verification Alternatives**:
- Query plan: `EXPLAIN SELECT * FROM table WHERE column = 'value'`
- Index list: `SELECT indexname FROM pg_indexes WHERE tablename = 'table_name'`
- Performance: `SELECT * FROM table WHERE column = 'value'` (should use index)

### Pattern: Seed Database Data

**When to use**: Adding initial or test data to database

**Task Structure**:
```json
{
  "task_id": "T3",
  "title": "Seed [data_type] data",
  "estimated_duration": "3 minutes",
  "files": ["/absolute/path/to/fixtures/seed_data.json"],
  "operations": [
    "Create fixture file with seed data",
    "Define data in correct format",
    "Add data for all required tables",
    "Ensure data is idempotent (can run multiple times)"
  ],
  "verification": {
    "command": "python manage.py loaddata fixtures/seed_data.json && python manage.py dbshell -c 'SELECT COUNT(*) FROM table_name'",
    "expected_output": "Expected row count",
    "success_criteria": "Data loaded successfully and appears in database"
  }
}
```

**Verification Alternatives**:
- ORM query: `python3 -c 'from models import Model; print(Model.objects.count())'`
- Direct query: `SELECT * FROM table_name WHERE id = 'known_id'`
- Fixture validation: `python3 -m json.tool fixtures/seed_data.json`

---

## 4. Testing Patterns

### Pattern: Add Unit Test

**When to use**: Creating test for individual function or class

**Task Structure**:
```json
{
  "task_id": "T4",
  "title": "Add unit test for [function_name]",
  "estimated_duration": "4 minutes",
  "files": ["/absolute/path/to/tests/test_module.py"],
  "operations": [
    "Create/update test file",
    "Add test function with descriptive name",
    "Test happy path",
    "Test edge cases and error handling"
  ],
  "verification": {
    "command": "python3 -m pytest tests/test_module.py::test_function_name -v",
    "expected_output": "1 passed",
    "success_criteria": "New test passes"
  }
}
```

**Verification Alternatives**:
- All tests: `pytest tests/test_module.py -v`
- Coverage: `pytest tests/test_module.py --cov=module --cov-report=term`
- Specific test: `pytest -k test_function_name`

### Pattern: Add Integration Test

**When to use**: Testing interaction between multiple components

**Task Structure**:
```json
{
  "task_id": "T4",
  "title": "Add integration test for [workflow]",
  "estimated_duration": "5 minutes",
  "files": ["/absolute/path/to/tests/integration/test_workflow.py"],
  "operations": [
    "Create integration test file",
    "Set up test database/fixtures",
    "Test end-to-end workflow",
    "Assert expected outcomes",
    "Clean up test data"
  ],
  "verification": {
    "command": "python3 -m pytest tests/integration/test_workflow.py -v",
    "expected_output": "1 passed",
    "success_criteria": "Integration test passes with real database"
  }
}
```

**Verification Alternatives**:
- With fixtures: `pytest tests/integration/test_workflow.py --fixtures`
- Verbose: `pytest tests/integration/test_workflow.py -vv`
- Stop on failure: `pytest tests/integration/test_workflow.py -x`

### Pattern: Add Regression Test for Bug

**When to use**: Testing that specific bug is fixed

**Task Structure**:
```json
{
  "task_id": "T4",
  "title": "Add regression test for bug #[issue_number]",
  "estimated_duration": "3 minutes",
  "files": ["/absolute/path/to/tests/test_regressions.py"],
  "operations": [
    "Create test that reproduces bug",
    "Test should fail before fix (confirming bug)",
    "Add clear comment linking to issue",
    "Test will pass after bug fix"
  ],
  "verification": {
    "command": "python3 -m pytest tests/test_regressions.py::test_issue_123 -v",
    "expected_output": "1 failed (initially) or 1 passed (after fix)",
    "success_criteria": "Test fails initially, passes after fix applied"
  }
}
```

**Verification Alternatives**:
- Run before fix: Should fail
- Run after fix: Should pass
- Mark as xfail: `pytest.mark.xfail` until fixed

---

## 5. Configuration Patterns

### Pattern: Update Environment Variables

**When to use**: Adding new configuration to .env file

**Task Structure**:
```json
{
  "task_id": "T5",
  "title": "Add [VAR_NAME] environment variable",
  "estimated_duration": "2 minutes",
  "files": ["/absolute/path/to/.env", "/absolute/path/to/.env.example"],
  "operations": [
    "Add VAR_NAME to .env with value",
    "Add VAR_NAME to .env.example with placeholder",
    "Update documentation if needed",
    "Add validation in application startup"
  ],
  "verification": {
    "command": "grep -q 'VAR_NAME' /path/to/.env && echo 'Found'",
    "expected_output": "Found",
    "success_criteria": "Variable exists in both .env and .env.example"
  }
}
```

**Verification Alternatives**:
- Load test: `python3 -c 'import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv("VAR_NAME"))'`
- Validation: `python3 -c 'from config import settings; print(settings.VAR_NAME)'`
- Example check: `diff <(sort .env) <(sort .env.example)`

### Pattern: Update Nginx Configuration

**When to use**: Modifying web server configuration

**Task Structure**:
```json
{
  "task_id": "T5",
  "title": "Update nginx config for [change]",
  "estimated_duration": "3 minutes",
  "files": ["/etc/nginx/sites-available/myapp.conf"],
  "operations": [
    "Backup current config",
    "Add/modify location block",
    "Update proxy settings",
    "Test configuration syntax"
  ],
  "verification": {
    "command": "nginx -t",
    "expected_output": "syntax is ok",
    "success_criteria": "Configuration is syntactically valid"
  }
}
```

**Verification Alternatives**:
- Reload: `systemctl reload nginx && systemctl is-active nginx`
- Check endpoint: `curl -I http://localhost/endpoint`
- View logs: `tail -f /var/log/nginx/error.log`

### Pattern: Update Package Dependencies

**When to use**: Adding or updating package in requirements/package.json

**Task Structure**:
```json
{
  "task_id": "T5",
  "title": "Add [package_name] dependency",
  "estimated_duration": "2 minutes",
  "files": ["/absolute/path/to/requirements.txt"],
  "operations": [
    "Add package_name==version to requirements.txt",
    "Pin to specific version for reproducibility",
    "Add comment explaining why needed",
    "Update requirements-dev.txt if needed"
  ],
  "verification": {
    "command": "pip install -r requirements.txt && python3 -c 'import package_name; print(package_name.__version__)'",
    "expected_output": "version",
    "success_criteria": "Package installs successfully and imports"
  }
}
```

**Verification Alternatives**:
- NPM: `npm install && npm list package_name`
- Poetry: `poetry add package_name && poetry show package_name`
- Check conflicts: `pip check`

---

## 6. Build & Deploy Patterns

### Pattern: Build Docker Image

**When to use**: Creating or updating Docker container image

**Task Structure**:
```json
{
  "task_id": "T6",
  "title": "Build Docker image for [service]",
  "estimated_duration": "4 minutes",
  "files": ["/absolute/path/to/Dockerfile"],
  "operations": [
    "Update Dockerfile with changes",
    "Build image with appropriate tag",
    "Verify image size is reasonable",
    "Test image locally"
  ],
  "verification": {
    "command": "docker build -t myapp:latest . && docker images myapp:latest",
    "expected_output": "Image appears in list",
    "success_criteria": "Image builds successfully and appears in docker images"
  }
}
```

**Verification Alternatives**:
- Run container: `docker run --rm myapp:latest --version`
- Inspect: `docker inspect myapp:latest`
- Size check: `docker images myapp:latest --format "{{.Size}}"`

### Pattern: Run Build Process

**When to use**: Compiling or bundling application

**Task Structure**:
```json
{
  "task_id": "T6",
  "title": "Build [application] for production",
  "estimated_duration": "3 minutes",
  "files": [],
  "operations": [
    "Run build command",
    "Verify build output directory",
    "Check for build warnings/errors",
    "Verify all expected files generated"
  ],
  "verification": {
    "command": "npm run build && test -d dist && echo 'Build successful'",
    "expected_output": "Build successful",
    "success_criteria": "Build completes and output directory exists"
  }
}
```

**Verification Alternatives**:
- Size check: `du -sh dist/`
- File count: `find dist/ -type f | wc -l`
- Serve locally: `npx serve dist`

### Pattern: Deploy to Environment

**When to use**: Deploying application to staging/production

**Task Structure**:
```json
{
  "task_id": "T6",
  "title": "Deploy to [environment]",
  "estimated_duration": "5 minutes",
  "files": [],
  "operations": [
    "Build deployment artifact",
    "Upload to target environment",
    "Run database migrations if needed",
    "Restart application services",
    "Verify deployment health"
  ],
  "verification": {
    "command": "curl -f https://myapp.com/health && echo 'Deployed'",
    "expected_output": "Deployed",
    "success_criteria": "Health check endpoint returns 200 OK"
  }
}
```

**Verification Alternatives**:
- Kubernetes: `kubectl rollout status deployment/myapp`
- Heroku: `heroku ps:scale web=1 && heroku logs --tail`
- SSH: `ssh server 'systemctl is-active myapp'`

---

## 7. Validation Patterns

### Pattern: Validate Code Quality

**When to use**: Running linters, formatters, type checkers

**Task Structure**:
```json
{
  "task_id": "T7",
  "title": "Validate code quality for [module]",
  "estimated_duration": "2 minutes",
  "files": [],
  "operations": [
    "Run linter on changed files",
    "Run type checker",
    "Run code formatter in check mode",
    "Verify no violations found"
  ],
  "verification": {
    "command": "pylint module.py && mypy module.py && black --check module.py",
    "expected_output": "No errors",
    "success_criteria": "All quality checks pass"
  }
}
```

**Verification Alternatives**:
- ESLint: `npx eslint src/`
- Prettier: `npx prettier --check src/`
- Go: `gofmt -l . && go vet ./...`

### Pattern: Validate Security

**When to use**: Running security scans on dependencies

**Task Structure**:
```json
{
  "task_id": "T7",
  "title": "Run security audit",
  "estimated_duration": "3 minutes",
  "files": [],
  "operations": [
    "Run dependency vulnerability scan",
    "Check for known CVEs",
    "Verify no critical issues",
    "Document any warnings"
  ],
  "verification": {
    "command": "pip-audit --desc && echo 'No critical issues'",
    "expected_output": "No critical issues",
    "success_criteria": "No high or critical severity vulnerabilities found"
  }
}
```

**Verification Alternatives**:
- NPM: `npm audit --audit-level=high`
- Snyk: `snyk test`
- Safety: `safety check`

### Pattern: Validate API Compliance

**When to use**: Checking API matches OpenAPI/Swagger spec

**Task Structure**:
```json
{
  "task_id": "T7",
  "title": "Validate API against OpenAPI spec",
  "estimated_duration": "2 minutes",
  "files": [],
  "operations": [
    "Start application server",
    "Run OpenAPI validation tool",
    "Check for spec violations",
    "Verify all endpoints documented"
  ],
  "verification": {
    "command": "swagger-cli validate openapi.yaml && echo 'Valid'",
    "expected_output": "Valid",
    "success_criteria": "OpenAPI spec is valid and matches implementation"
  }
}
```

**Verification Alternatives**:
- Dredd: `dredd openapi.yaml http://localhost:5000`
- Spectral: `spectral lint openapi.yaml`
- Postman: Import spec and run collection

---

## Task Duration Guidelines

### 2-minute tasks
- Add single environment variable
- Create simple configuration file
- Update single function parameter
- Add simple validation check
- Run single command verification

### 3-minute tasks
- Create database migration
- Add unit test for single function
- Update nginx configuration block
- Add single Python class/function
- Create simple React component

### 4-minute tasks
- Add API endpoint handler
- Implement integration test
- Add frontend component with styles
- Update database model with validation
- Build and verify Docker image

### 5-minute tasks
- Refactor complex class
- Add comprehensive integration test
- Update deployment configuration
- Implement bug fix with test
- Add component with multiple tests

**Anything longer than 5 minutes should be split into multiple tasks.**

## Verification Command Patterns

### Immediate Verification (fastest)
```bash
# File exists
test -f /path/to/file && echo "Exists"

# Directory exists
test -d /path/to/dir && echo "Exists"

# Content check
grep -q "expected_text" /path/to/file && echo "Found"

# JSON valid
python3 -m json.tool < file.json > /dev/null && echo "Valid"
```

### Import/Syntax Verification
```bash
# Python import
python3 -c 'import module_name'

# Python syntax
python3 -m py_compile file.py

# JavaScript syntax
node -c file.js

# TypeScript compile
npx tsc --noEmit
```

### Service Verification
```bash
# HTTP endpoint
curl -f http://localhost:5000/health

# Service status
systemctl is-active service_name

# Process running
pgrep -f process_name

# Port listening
netstat -tuln | grep :8000
```

### Test Execution
```bash
# Python unit test
python3 -m pytest tests/test_module.py::test_function -v

# Python all tests
python3 -m pytest tests/

# JavaScript tests
npm test -- ComponentName

# Go tests
go test ./...
```

### Build Verification
```bash
# Docker build
docker build -t app:latest . && docker images app:latest

# NPM build
npm run build && test -d dist

# Go build
go build -o bin/app ./cmd/app

# Python package
python3 setup.py sdist && ls dist/
```

## Common Verification Mistakes

### ❌ Too Vague
```json
{
  "verification": {
    "command": "ls file.py",
    "expected_output": "file.py",
    "success_criteria": "File exists"
  }
}
```
**Problem**: Only checks existence, not correctness

### ✅ Specific and Meaningful
```json
{
  "verification": {
    "command": "python3 -c 'import file; assert hasattr(file, \"main_function\")'",
    "expected_output": "No exceptions",
    "success_criteria": "Module imports and exports expected function"
  }
}
```

### ❌ No Actual Verification
```json
{
  "verification": {
    "command": "echo 'OK'",
    "expected_output": "OK",
    "success_criteria": "Command runs"
  }
}
```
**Problem**: Fake verification, always passes

### ✅ Real Verification
```json
{
  "verification": {
    "command": "python3 -m pytest tests/test_new_feature.py -v",
    "expected_output": "1 passed",
    "success_criteria": "New feature test passes"
  }
}
```

### ❌ Too Slow
```json
{
  "verification": {
    "command": "npm test",
    "expected_output": "All tests pass",
    "success_criteria": "Full test suite passes"
  }
}
```
**Problem**: May take >2 minutes for large test suites

### ✅ Targeted Verification
```json
{
  "verification": {
    "command": "npm test -- NewComponent.test.tsx",
    "expected_output": "PASS",
    "success_criteria": "Only new component tests pass"
  }
}
```

## Summary Checklist

When creating a task, verify:

- [ ] Task duration is 2-5 minutes
- [ ] All file paths are absolute
- [ ] Operations are specific and actionable
- [ ] Verification command actually tests the change
- [ ] Expected output is realistic and specific
- [ ] Success criteria are clear and measurable
- [ ] Rollback strategy is defined (if applicable)
- [ ] Dependencies are declared if task relies on others
