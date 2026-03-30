---
name: perses-project-manage
user-invocable: false
description: "Perses project lifecycle: create, list, switch, configure, RBAC."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-dashboard-engineer
version: 2.0.0
routing:
  triggers:
    - "manage Perses project"
    - "Perses RBAC"
  category: perses
---

# Perses Project Management

Create and manage Perses projects with RBAC configuration. A Project is an organizational container grouping dashboards, datasources, variables, and other resources. When running via Perses Operator on Kubernetes, each project maps to a K8s namespace.

---

## Instructions

### Phase 1: CREATE PROJECT

**Goal**: Create a new Perses project.

**Use MCP when available** (because MCP is the primary tool choice, faster than CLI):
```
perses_create_project(project="<project-name>")
```

**Or use percli CLI as fallback**:
```bash
percli apply -f - <<EOF
kind: Project
metadata:
  name: <project-name>
spec: {}
EOF

# Set as active project
percli project <project-name>
```

**Constraints**:
- Use **lowercase alphanumeric names with hyphens only** (e.g., `my-project`), because Perses follows DNS label conventions and rejects uppercase/spaces/special chars
- **Always verify creation** with `percli get project` or `perses_list_projects()` before reporting success, because MCP tools may return cached responses or partial creates on network errors
- **Set the active project immediately after creation**, because wrong context silently applies resources to the wrong project later
- **Stop and ask if project name conflicts**, because user must decide whether to reuse or rename
- **Stop and ask if target environment is ambiguous** (dev vs production), because production requires RBAC setup while dev may use defaults

**Gate**: Project created, verified, and set as active context. Proceed to Phase 2 if RBAC is needed, otherwise task complete.

### Phase 2: CONFIGURE RBAC (optional)

**Goal**: Set up roles and role bindings for access control when requested or for production projects.

**Step 1: Create a role**

Roles define what actions are allowed on which resource types within a project:

```bash
percli apply -f - <<EOF
kind: Role
metadata:
  name: dashboard-editor
  project: <project-name>
spec:
  permissions:
    - actions: [read, create, update]
      scopes: [Dashboard, Datasource, Variable]
EOF
```

**Available actions**: read, create, update, delete

**Available scopes** (resource types): Dashboard, Datasource, EphemeralDashboard, Folder, Role, RoleBinding, Secret, Variable

**Use project-scoped Role for project-specific permissions**, because it enforces least privilege. **Reserve GlobalRole for org-wide needs only**, because global roles grant access across every project:

```bash
percli apply -f - <<EOF
kind: GlobalRole
metadata:
  name: org-viewer
spec:
  permissions:
    - actions: [read]
      scopes: ["*"]
EOF
```

**Constraints**:
- **Never use wildcard scopes without explicit user approval**, because wildcard grants access to every resource type across every project
- **Set up RBAC immediately in production**, because any authenticated user has full access during the gap between creation and RBAC setup

**Step 2: Create a role binding**

Role bindings assign users or groups to roles. **Stop and ask about auth provider type** (User vs Group) because the `kind` field depends on whether auth is Native, OIDC, or OAuth:

```bash
percli apply -f - <<EOF
kind: RoleBinding
metadata:
  name: team-editors
  project: <project-name>
spec:
  role: dashboard-editor
  subjects:
    - kind: User
      name: user@example.com
EOF
```

**Never hardcode real email addresses**, because identity should come from the user. Use placeholder format and let user supply real identities:

```bash
percli apply -f - <<EOF
kind: RoleBinding
metadata:
  name: team-editors
  project: <project-name>
spec:
  role: dashboard-editor
  subjects:
    - kind: User
      name: <user-email>
EOF
```

For global role bindings:

```bash
percli apply -f - <<EOF
kind: GlobalRoleBinding
metadata:
  name: org-viewers
spec:
  role: org-viewer
  subjects:
    - kind: User
      name: <viewer-email>
EOF
```

**Constraints**:
- **Verify the role exists before creating bindings**, because typos in role names fail silently and the binding grants nothing
- **Ensure role and binding are in the same project**, because cross-project references don't work
- Run `percli get role --project <name>` before binding creation to confirm exact role name

**Gate**: Roles and bindings created and verified. Proceed to Phase 3.

### Phase 3: VERIFY

**Goal**: Confirm project, roles, and bindings are correctly configured.

```bash
# List projects
percli get project

# Describe project
percli describe project <project-name>

# List roles in project
percli get role --project <project-name>

# List role bindings in project
percli get rolebinding --project <project-name>

# List global roles
percli get globalrole

# List global role bindings
percli get globalrolebinding
```

Or via MCP:
```
perses_list_projects()
perses_list_project_roles(project="<project-name>")
perses_list_project_role_bindings(project="<project-name>")
perses_list_global_roles()
```

**Constraints**:
- **Always verify before declaring success**, because MCP tools may report cached responses
- **Re-run `percli project <name>`** before applying project-scoped resources in subsequent phases, because context may have changed since initial setup

**Gate**: Project listed and roles/bindings confirmed. Task complete.

---

## Error Handling

### Project creation fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| "already exists" / 409 Conflict | Project name is already taken | List existing projects with `percli get project` or `perses_list_projects()` and use a different name, or operate on the existing project |
| "invalid name" / 400 Bad Request | Project name contains invalid characters (uppercase, spaces, special chars) | Use lowercase alphanumeric names with hyphens only (e.g., `my-project`). Perses follows DNS label conventions |
| "unauthorized" / 401 | Not authenticated or session token expired | Run `percli login` first, or verify MCP server auth config has valid credentials |
| "forbidden" / 403 | Authenticated user lacks permission to create projects | User needs a GlobalRole with `create` action on Project scope, or admin access |

### Role and RoleBinding creation fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| "role not found" in RoleBinding apply | The role referenced in `spec.role` does not exist | Create the Role first, then create the RoleBinding. Verify role exists with `percli get role --project <name>` |
| "subject not found" / binding has no effect | User or group name in subjects does not match any identity in the auth provider | Verify user identity with the configured auth provider (Native, OIDC, OAuth). For native auth, the username is the login name |
| "project not found" in role metadata | The project specified in `metadata.project` does not exist | Create the project first, or fix the project name in the role definition |
| GlobalRole apply returns 403 | User does not have cluster-level admin permissions | GlobalRole and GlobalRoleBinding require admin-level access; escalate to a Perses admin |

### Wrong project context

| Symptom | Cause | Fix |
|---------|-------|-----|
| Resources appear in wrong project | `percli project` was set to a different project than intended | Always run `percli project <name>` immediately before applying project-scoped resources |
| "project not set" error | No active project context configured | Run `percli project <name>` to set the active project |
| Role/binding created but permissions don't work | RoleBinding references a role from a different project | Ensure role and binding are in the same project; check `metadata.project` on both |

### MCP tool failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `perses_create_project` returns read-only error | Perses server has `security.readonly: true` in config | Ask user to disable read-only mode, or switch to a writable instance |
| MCP tool returns connection refused | MCP server cannot reach Perses API | Check MCP server config URL and ensure Perses server is running at that address |
| MCP list returns empty but projects exist | MCP auth credentials lack read permission | Verify MCP server auth config; the configured user needs at least read access |

---

## References

| Resource | URL |
|----------|-----|
| Perses Project API docs | https://perses.dev/docs/api/project/ |
| Perses RBAC documentation | https://perses.dev/docs/user-guides/security/rbac/ |
| Perses Authentication docs | https://perses.dev/docs/user-guides/security/authentication/ |
| percli CLI reference | https://perses.dev/docs/user-guides/percli/ |
| Perses MCP server | https://github.com/perses/perses-mcp-server |
| Perses Operator (project-to-namespace mapping) | https://github.com/perses/perses-operator |
