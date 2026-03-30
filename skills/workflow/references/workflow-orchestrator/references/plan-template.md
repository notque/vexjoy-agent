# Workflow Plan Templates

This document provides example plans for common development scenarios. Use these as templates when creating your own plans.

## Template 1: Database Schema Change

**Scenario**: Add new table to existing database with proper migration.

```json
{
  "plan_id": "PLAN_DB_001",
  "description": "Add user_preferences table with migration",
  "approach": "Django-style migration with backward compatibility",
  "estimated_total_time": "14 minutes",
  "tasks": [
    {
      "task_id": "T1",
      "title": "Create database migration file",
      "estimated_duration": "3 minutes",
      "dependencies": [],
      "files": [
        "/path/to/your/project/migrations/0005_user_preferences.py"
      ],
      "operations": [
        "Create new migration file using timestamp",
        "Define UserPreferences model with schema",
        "Add indexes for user_id and preference_key"
      ],
      "verification": {
        "command": "python manage.py makemigrations --dry-run --check",
        "expected_output": "No changes detected",
        "success_criteria": "Exit code 0, no new migrations needed"
      },
      "rollback": {
        "description": "Delete migration file",
        "commands": [
          "rm /path/to/your/project/migrations/0005_user_preferences.py"
        ]
      }
    },
    {
      "task_id": "T2",
      "title": "Update database models",
      "estimated_duration": "4 minutes",
      "dependencies": ["T1"],
      "files": [
        "/path/to/your/project/models/user_preferences.py"
      ],
      "operations": [
        "Create UserPreferences model class",
        "Add user foreign key relationship",
        "Add preference_key and preference_value fields",
        "Add created_at and updated_at timestamps"
      ],
      "verification": {
        "command": "python manage.py check",
        "expected_output": "System check identified no issues",
        "success_criteria": "Exit code 0 and no model errors"
      },
      "rollback": {
        "description": "Remove model file",
        "commands": [
          "rm /path/to/your/project/models/user_preferences.py"
        ]
      }
    },
    {
      "task_id": "T3",
      "title": "Run migration and verify schema",
      "estimated_duration": "3 minutes",
      "dependencies": ["T2"],
      "files": [],
      "operations": [
        "Apply migration to database",
        "Verify table exists in schema",
        "Verify indexes created"
      ],
      "verification": {
        "command": "python manage.py migrate && python manage.py dbshell -c '\\dt user_preferences'",
        "expected_output": "Table user_preferences exists",
        "success_criteria": "Migration applied successfully and table created"
      },
      "rollback": {
        "description": "Revert migration",
        "commands": [
          "python manage.py migrate app_name 0004_previous_migration"
        ]
      }
    },
    {
      "task_id": "T4",
      "title": "Add model tests",
      "estimated_duration": "4 minutes",
      "dependencies": ["T3"],
      "files": [
        "/path/to/your/project/tests/test_user_preferences.py"
      ],
      "operations": [
        "Create test file for UserPreferences model",
        "Add test for creating preference",
        "Add test for updating preference",
        "Add test for preference uniqueness constraint"
      ],
      "verification": {
        "command": "python manage.py test tests.test_user_preferences",
        "expected_output": "OK",
        "success_criteria": "All tests pass, exit code 0"
      },
      "rollback": {
        "description": "Remove test file",
        "commands": [
          "rm /path/to/your/project/tests/test_user_preferences.py"
        ]
      }
    }
  ],
  "dependencies": {
    "T2": ["T1"],
    "T3": ["T2"],
    "T4": ["T3"]
  }
}
```

**Dependency Graph**:
```
T1 → T2 → T3 → T4
```

---

## Template 2: API Endpoint Addition

**Scenario**: Add new REST API endpoint with authentication.

```json
{
  "plan_id": "PLAN_API_001",
  "description": "Add GET /api/v1/user/preferences endpoint",
  "approach": "Flask blueprint with JWT authentication",
  "estimated_total_time": "13 minutes",
  "tasks": [
    {
      "task_id": "T1",
      "title": "Create API route handler",
      "estimated_duration": "4 minutes",
      "dependencies": [],
      "files": [
        "/path/to/your/project/api/routes/preferences.py"
      ],
      "operations": [
        "Create preferences.py route file",
        "Add get_user_preferences function",
        "Add JWT authentication decorator",
        "Add response formatting with JSON"
      ],
      "verification": {
        "command": "python -c 'import api.routes.preferences; print(dir(api.routes.preferences))'",
        "expected_output": "['get_user_preferences']",
        "success_criteria": "Module imports successfully and function exists"
      },
      "rollback": {
        "description": "Remove route file",
        "commands": [
          "rm /path/to/your/project/api/routes/preferences.py"
        ]
      }
    },
    {
      "task_id": "T2",
      "title": "Register route in blueprint",
      "estimated_duration": "2 minutes",
      "dependencies": ["T1"],
      "files": [
        "/path/to/your/project/api/__init__.py"
      ],
      "operations": [
        "Import preferences route",
        "Register /user/preferences endpoint",
        "Add to blueprint"
      ],
      "verification": {
        "command": "python -c 'from api import bp; print([r.rule for r in bp.url_map.iter_rules()])'",
        "expected_output": "/api/v1/user/preferences",
        "success_criteria": "Route appears in blueprint routes"
      },
      "rollback": {
        "description": "Remove route registration",
        "commands": [
          "git checkout /path/to/your/project/api/__init__.py"
        ]
      }
    },
    {
      "task_id": "T3",
      "title": "Add integration test",
      "estimated_duration": "4 minutes",
      "dependencies": ["T2"],
      "files": [
        "/path/to/your/project/tests/api/test_preferences_endpoint.py"
      ],
      "operations": [
        "Create test file for preferences endpoint",
        "Add test for authenticated request",
        "Add test for unauthenticated request (should fail)",
        "Add test for invalid user ID"
      ],
      "verification": {
        "command": "python -m pytest tests/api/test_preferences_endpoint.py -v",
        "expected_output": "3 passed",
        "success_criteria": "All 3 tests pass"
      },
      "rollback": {
        "description": "Remove test file",
        "commands": [
          "rm /path/to/your/project/tests/api/test_preferences_endpoint.py"
        ]
      }
    },
    {
      "task_id": "T4",
      "title": "Update API documentation",
      "estimated_duration": "3 minutes",
      "dependencies": ["T3"],
      "files": [
        "/path/to/your/project/docs/api/endpoints.md"
      ],
      "operations": [
        "Add GET /user/preferences endpoint documentation",
        "Document authentication requirement",
        "Add example request and response",
        "Document error codes"
      ],
      "verification": {
        "command": "grep -q 'GET /user/preferences' /path/to/your/project/docs/api/endpoints.md && echo 'Found'",
        "expected_output": "Found",
        "success_criteria": "Documentation contains new endpoint"
      },
      "rollback": {
        "description": "Revert documentation changes",
        "commands": [
          "git checkout /path/to/your/project/docs/api/endpoints.md"
        ]
      }
    }
  ],
  "dependencies": {
    "T2": ["T1"],
    "T3": ["T2"],
    "T4": ["T3"]
  }
}
```

**Dependency Graph**:
```
T1 → T2 → T3 → T4
```

---

## Template 3: Frontend Component Addition

**Scenario**: Add new React component with tests and stories.

```json
{
  "plan_id": "PLAN_FE_001",
  "description": "Add UserPreferencePanel component",
  "approach": "React functional component with hooks",
  "estimated_total_time": "16 minutes",
  "tasks": [
    {
      "task_id": "T1",
      "title": "Create component file",
      "estimated_duration": "5 minutes",
      "dependencies": [],
      "files": [
        "/path/to/your/project/src/components/UserPreferencePanel.tsx"
      ],
      "operations": [
        "Create UserPreferencePanel.tsx",
        "Add TypeScript interface for props",
        "Implement functional component with useState",
        "Add JSX structure for preference form"
      ],
      "verification": {
        "command": "npx tsc --noEmit --project /path/to/your/project/tsconfig.json",
        "expected_output": "No errors",
        "success_criteria": "TypeScript compiles without errors"
      },
      "rollback": {
        "description": "Remove component file",
        "commands": [
          "rm /path/to/your/project/src/components/UserPreferencePanel.tsx"
        ]
      }
    },
    {
      "task_id": "T2",
      "title": "Add component styles",
      "estimated_duration": "3 minutes",
      "dependencies": ["T1"],
      "files": [
        "/path/to/your/project/src/components/UserPreferencePanel.module.css"
      ],
      "operations": [
        "Create CSS module file",
        "Add styles for panel container",
        "Add styles for form elements",
        "Add responsive styles"
      ],
      "verification": {
        "command": "test -f /path/to/your/project/src/components/UserPreferencePanel.module.css && echo 'Exists'",
        "expected_output": "Exists",
        "success_criteria": "CSS file exists"
      },
      "rollback": {
        "description": "Remove CSS file",
        "commands": [
          "rm /path/to/your/project/src/components/UserPreferencePanel.module.css"
        ]
      }
    },
    {
      "task_id": "T3",
      "title": "Add unit tests",
      "estimated_duration": "4 minutes",
      "dependencies": ["T1"],
      "files": [
        "/path/to/your/project/src/components/__tests__/UserPreferencePanel.test.tsx"
      ],
      "operations": [
        "Create test file",
        "Add test for component rendering",
        "Add test for form submission",
        "Add test for validation"
      ],
      "verification": {
        "command": "npm test -- UserPreferencePanel.test.tsx",
        "expected_output": "PASS",
        "success_criteria": "All tests pass"
      },
      "rollback": {
        "description": "Remove test file",
        "commands": [
          "rm /path/to/your/project/src/components/__tests__/UserPreferencePanel.test.tsx"
        ]
      }
    },
    {
      "task_id": "T4",
      "title": "Add Storybook story",
      "estimated_duration": "4 minutes",
      "dependencies": ["T2"],
      "files": [
        "/path/to/your/project/src/components/UserPreferencePanel.stories.tsx"
      ],
      "operations": [
        "Create Storybook story file",
        "Add default story",
        "Add story with pre-filled data",
        "Add story with validation errors"
      ],
      "verification": {
        "command": "npx build-storybook --quiet && echo 'Built'",
        "expected_output": "Built",
        "success_criteria": "Storybook builds successfully"
      },
      "rollback": {
        "description": "Remove story file",
        "commands": [
          "rm /path/to/your/project/src/components/UserPreferencePanel.stories.tsx"
        ]
      }
    }
  ],
  "dependencies": {
    "T2": ["T1"],
    "T3": ["T1"],
    "T4": ["T2"]
  }
}
```

**Dependency Graph**:
```
     ↗ T2 → T4
T1 →
     ↘ T3
```

---

## Template 4: Bug Fix with Regression Test

**Scenario**: Fix bug where user preferences aren't saved on logout.

```json
{
  "plan_id": "PLAN_BUG_001",
  "description": "Fix user preference persistence on logout",
  "approach": "Add beforeunload event handler to save preferences",
  "estimated_total_time": "12 minutes",
  "tasks": [
    {
      "task_id": "T1",
      "title": "Add regression test for bug",
      "estimated_duration": "4 minutes",
      "dependencies": [],
      "files": [
        "/path/to/your/project/tests/test_preference_persistence.py"
      ],
      "operations": [
        "Create test file",
        "Add test that reproduces the bug",
        "Test should FAIL initially (confirming bug exists)",
        "Document expected vs actual behavior"
      ],
      "verification": {
        "command": "python -m pytest tests/test_preference_persistence.py -v",
        "expected_output": "1 failed",
        "success_criteria": "Test fails, confirming bug exists"
      },
      "rollback": {
        "description": "Keep test file for future use",
        "commands": []
      }
    },
    {
      "task_id": "T2",
      "title": "Implement bug fix",
      "estimated_duration": "5 minutes",
      "dependencies": ["T1"],
      "files": [
        "/path/to/your/project/src/hooks/usePreferences.ts"
      ],
      "operations": [
        "Add beforeunload event listener",
        "Call savePreferences on window unload",
        "Ensure cleanup on component unmount",
        "Add debounce to prevent excessive saves"
      ],
      "verification": {
        "command": "npx tsc --noEmit && echo 'TypeScript OK'",
        "expected_output": "TypeScript OK",
        "success_criteria": "TypeScript compiles without errors"
      },
      "rollback": {
        "description": "Revert changes to hook",
        "commands": [
          "git checkout /path/to/your/project/src/hooks/usePreferences.ts"
        ]
      }
    },
    {
      "task_id": "T3",
      "title": "Verify regression test now passes",
      "estimated_duration": "3 minutes",
      "dependencies": ["T2"],
      "files": [],
      "operations": [
        "Run the regression test again",
        "Test should PASS now (confirming fix works)",
        "Run full test suite to ensure no regressions"
      ],
      "verification": {
        "command": "python -m pytest tests/test_preference_persistence.py -v && npm test",
        "expected_output": "1 passed",
        "success_criteria": "Regression test passes and no other tests break"
      },
      "rollback": {
        "description": "N/A - verification step only",
        "commands": []
      }
    }
  ],
  "dependencies": {
    "T2": ["T1"],
    "T3": ["T2"]
  }
}
```

**Dependency Graph**:
```
T1 → T2 → T3
```

---

## Template 5: Configuration Change with Rollback

**Scenario**: Update production nginx configuration to add new API endpoint.

```json
{
  "plan_id": "PLAN_CONFIG_001",
  "description": "Add nginx route for /api/v2/preferences",
  "approach": "Update nginx config with backup and validation",
  "estimated_total_time": "9 minutes",
  "tasks": [
    {
      "task_id": "T1",
      "title": "Backup current nginx config",
      "estimated_duration": "1 minute",
      "dependencies": [],
      "files": [],
      "operations": [
        "Copy current nginx config to backup file",
        "Add timestamp to backup filename",
        "Verify backup was created"
      ],
      "verification": {
        "command": "test -f /etc/nginx/sites-available/myapp.conf.backup.$(date +%Y%m%d) && echo 'Backup exists'",
        "expected_output": "Backup exists",
        "success_criteria": "Backup file exists with today's date"
      },
      "rollback": {
        "description": "N/A - this is the backup step",
        "commands": []
      }
    },
    {
      "task_id": "T2",
      "title": "Update nginx configuration",
      "estimated_duration": "4 minutes",
      "dependencies": ["T1"],
      "files": [
        "/etc/nginx/sites-available/myapp.conf"
      ],
      "operations": [
        "Add location block for /api/v2/preferences",
        "Set proxy_pass to backend server",
        "Add necessary headers",
        "Set timeout values"
      ],
      "verification": {
        "command": "nginx -t",
        "expected_output": "syntax is ok",
        "success_criteria": "nginx -t passes without errors"
      },
      "rollback": {
        "description": "Restore from backup",
        "commands": [
          "cp /etc/nginx/sites-available/myapp.conf.backup.$(date +%Y%m%d) /etc/nginx/sites-available/myapp.conf"
        ]
      }
    },
    {
      "task_id": "T3",
      "title": "Reload nginx and verify",
      "estimated_duration": "2 minutes",
      "dependencies": ["T2"],
      "files": [],
      "operations": [
        "Reload nginx with new configuration",
        "Check nginx status",
        "Verify endpoint is accessible"
      ],
      "verification": {
        "command": "systemctl reload nginx && systemctl is-active nginx && curl -I http://localhost/api/v2/preferences",
        "expected_output": "active",
        "success_criteria": "nginx reloads successfully and endpoint responds"
      },
      "rollback": {
        "description": "Restore backup and reload nginx",
        "commands": [
          "cp /etc/nginx/sites-available/myapp.conf.backup.$(date +%Y%m%d) /etc/nginx/sites-available/myapp.conf",
          "systemctl reload nginx"
        ]
      }
    },
    {
      "task_id": "T4",
      "title": "Test endpoint with real request",
      "estimated_duration": "2 minutes",
      "dependencies": ["T3"],
      "files": [],
      "operations": [
        "Send test GET request to endpoint",
        "Verify response code",
        "Verify response format"
      ],
      "verification": {
        "command": "curl -s -w '%{http_code}' http://localhost/api/v2/preferences | grep 200",
        "expected_output": "200",
        "success_criteria": "Endpoint returns 200 status code"
      },
      "rollback": {
        "description": "N/A - verification only",
        "commands": []
      }
    }
  ],
  "dependencies": {
    "T2": ["T1"],
    "T3": ["T2"],
    "T4": ["T3"]
  }
}
```

**Dependency Graph**:
```
T1 → T2 → T3 → T4
```

---

## Plan Structure Guidelines

### Essential Elements

Every plan must include:

1. **plan_id**: Unique identifier (format: `PLAN_[CATEGORY]_[NUMBER]`)
2. **description**: One-line summary of what the plan achieves
3. **approach**: High-level strategy selected during brainstorm phase
4. **estimated_total_time**: Sum of all task durations
5. **tasks**: Array of task objects (see task template)
6. **dependencies**: Object mapping dependent tasks to their prerequisites

### Task Object Requirements

Every task must have:

1. **task_id**: Unique identifier within plan (T1, T2, T3, etc.)
2. **title**: Short description of what the task does
3. **estimated_duration**: Time estimate in minutes (2-5 minute range)
4. **dependencies**: Array of task_ids that must complete first
5. **files**: Array of absolute file paths that will be modified
6. **operations**: Array of specific operations to perform
7. **verification**: Object with command, expected output, and success criteria
8. **rollback**: Object with description and commands to undo changes

### Verification Best Practices

Good verification commands:
- ✅ `python manage.py check` - Comprehensive Django check
- ✅ `npm test -- ComponentName` - Specific test file
- ✅ `nginx -t` - Configuration validation
- ✅ `curl -I http://endpoint` - Endpoint accessibility check
- ✅ `python -c 'import module; ...'` - Python import check

Bad verification commands:
- ❌ No verification command
- ❌ `ls file.py` - Only checks existence, not correctness
- ❌ `echo "OK"` - Fake verification
- ❌ Verification command that takes >2 minutes

### Rollback Best Practices

Good rollback strategies:
- ✅ `rm /path/to/new/file.py` - Remove newly created file
- ✅ `git checkout /path/to/file.py` - Restore from git
- ✅ `cp backup.conf original.conf` - Restore from backup
- ✅ `python manage.py migrate app 0004` - Revert migration

Bad rollback strategies:
- ❌ No rollback defined
- ❌ Destructive commands without backup
- ❌ Rollback that depends on external state

## Usage Tips

1. **Copy template**: Start with the template closest to your scenario
2. **Customize tasks**: Adapt operations to your specific requirements
3. **Verify paths**: Ensure all file paths are absolute and correct
4. **Test verification**: Make sure verification commands work in your environment
5. **Check dependencies**: Ensure dependency graph has no cycles
6. **Estimate time**: Be realistic about task durations (2-5 minutes each)
