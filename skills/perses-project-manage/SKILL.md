---
name: perses-project-manage
user-invocable: false
description: |
  Perses project lifecycle management: create, list, switch, and configure projects.
  Manage RBAC with roles and role bindings per project. Uses MCP tools when available,
  percli CLI as fallback. Use for "perses project", "create project", "perses rbac",
  "perses roles", "perses permissions". Do NOT use for dashboard creation
  (use perses-dashboard-create).
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
agent: perses-dashboard-engineer
version: 2.0.0
---

# Perses Project Management

Create and manage projects with RBAC configuration.

## Operator Context

This skill operates as the lifecycle manager for Perses projects and their RBAC configuration, handling project creation, role definitions, and role bindings. A Project in Perses is an organizational container that groups dashboards, datasources, variables, and other resources. When running via the Perses Operator on Kubernetes, each project maps to a K8s namespace.

### Hardcoded Behaviors (Always Apply)
- **MCP-first**: Use Perses MCP tools when available, percli as fallback
- **RBAC awareness**: When creating projects in production, always set up roles and bindings — an unprotected project allows any authenticated user full access
- **Project context**: Always verify/set active project with `percli project` before operating on project-scoped resources — wrong project context silently applies resources to the wrong project
- **Verify before declare**: After creating any resource (project, role, binding), verify it exists with a list or describe command before reporting success

### Default Behaviors (ON unless disabled)
- **Simple create**: Create project with default settings unless RBAC is requested
- **Set active**: After creating a project, set it as the active project context

### Optional Behaviors (OFF unless enabled)
- **RBAC setup**: Create roles and role bindings alongside project creation
- **Multi-project**: Create multiple projects in batch for team onboarding

## What This Skill CAN Do
- Create, list, describe, and delete projects
- Set up roles with granular permissions (read/create/update/delete on specific resource types)
- Create role bindings to assign users or groups to roles
- Switch active project context
- Manage global roles and global role bindings

## What This Skill CANNOT Do
- Manage user accounts (that's Perses server admin configuration)
- Configure authentication providers (use perses-deploy)
- Create dashboards or datasources (use perses-dashboard-create, perses-datasource-manage)

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

## Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|--------------|-------------|------------------|
| **Creating projects without RBAC in production** — skipping role and binding setup | Any authenticated user gets full read/write/delete access to the project's resources | Always create at least a viewer role and an admin role with bindings for production projects |
| **Not setting active project before applying resources** — relying on "whatever was last set" | Resources silently apply to the wrong project; no error is raised | Run `percli project <name>` immediately before every `percli apply` for project-scoped resources |
| **Using GlobalRole for project-scoped permissions** — granting org-wide access when project-level suffices | Violates principle of least privilege; users get access to all projects instead of just one | Use project-scoped Role for project-specific permissions; reserve GlobalRole for truly organization-wide needs |
| **Creating RoleBindings without verifying the role exists** — assuming role was created in a prior step | Binding references a non-existent role; no permissions are granted; no error may surface until access is denied | Always verify role existence with `percli get role --project <name>` before creating bindings |
| **Deleting a project without checking for active dashboards** — removing a project that contains resources | All dashboards, datasources, variables, and other resources in the project are permanently deleted | List project contents with `percli get dashboard --project <name>` before deletion; confirm with user |

---

## Anti-Rationalization

| Rationalization | Why It's Wrong | Required Action |
|-----------------|---------------|-----------------|
| "The project was just created, RBAC can wait" | In the gap between creation and RBAC setup, any authenticated user has full access to the project | **Set up RBAC immediately** after project creation for production environments |
| "I already set the project context earlier" | Context may have changed if other commands ran between setting it and applying resources | **Re-run `percli project <name>`** before every apply — it costs nothing and prevents silent misapplication |
| "The role name looks right, skip the verify step" | Typos in role names fail silently in RoleBindings — the binding is created but grants nothing | **Run `percli get role --project <name>`** and confirm the exact role name before creating bindings |
| "GlobalRole is simpler than per-project roles" | Simpler setup, but violates least-privilege and gives access across every project | **Use project-scoped Roles** unless the permission genuinely needs to span all projects |
| "MCP created it so it must exist" | MCP tool may return success on a stale or cached response; network issues can cause partial creates | **Verify with a list or describe command** after every create operation |

---

## FORBIDDEN Patterns

- **NEVER** apply project-scoped resources without first confirming the active project context — silent wrong-project application is the most common error
- **NEVER** create production projects without at least one Role and RoleBinding — unprotected projects are open to all authenticated users
- **NEVER** use wildcard (`"*"`) in GlobalRole scopes without explicit user approval — this grants access to every resource type across every project
- **NEVER** hardcode user email addresses or identities in skill output — always use placeholder values and let the user supply real identities
- **NEVER** delete projects without listing their contents first and confirming with the user

---

## Blocker Criteria

Stop and ask the user before proceeding if:
- Auth provider type is unknown — role binding subject `kind` (User vs Group) depends on auth configuration
- Target environment (dev vs production) is ambiguous — determines whether RBAC setup is required
- Project name conflicts with an existing project — user must decide: reuse existing or rename
- User wants GlobalRole with wildcard scopes — requires explicit confirmation due to security implications
- MCP server is in read-only mode — cannot create projects or roles; user must change server config

---

## Instructions

### Phase 1: CREATE PROJECT

**Goal**: Create a new Perses project.

**Via percli**:
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

**Via MCP** (preferred):
```
perses_create_project(project="<project-name>")
```

**Gate**: Project created and set as active context. Proceed to Phase 2 if RBAC is needed, otherwise task complete.

### Phase 2: CONFIGURE RBAC (optional)

**Goal**: Set up roles and role bindings for access control.

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

For organization-wide roles, use GlobalRole:
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

**Step 2: Create a role binding**

Role bindings assign users or groups to roles:

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
      name: viewer@example.com
EOF
```

**Gate**: Roles and bindings created. Proceed to Phase 3.

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

**Gate**: Project listed, roles and bindings confirmed. Task complete.

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
