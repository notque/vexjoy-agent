# Project Management

Create and manage Perses projects with RBAC configuration. A Project is an organizational container grouping dashboards, datasources, variables, and other resources. On Kubernetes with the Perses Operator, each project maps to a K8s namespace.

## Phase 1: CREATE PROJECT

**Goal**: Create a new Perses project.

**Via MCP** (preferred):
```
perses_create_project(project="<project-name>")
```

**Via percli CLI**:
```bash
percli apply -f - <<EOF
kind: Project
metadata:
  name: <project-name>
spec: {}
EOF
percli project <project-name>
```

**Constraints**:
- **Lowercase alphanumeric names with hyphens only** (DNS label conventions)
- **Always verify creation** with `percli get project` or `perses_list_projects()`
- **Set active project immediately** after creation
- **Stop and ask** if name conflicts or target environment is ambiguous

**Gate**: Project created, verified, and set as active. Proceed to Phase 2 if RBAC needed.

## Phase 2: CONFIGURE RBAC (optional)

**Goal**: Set up roles and role bindings for access control.

**Step 1: Create a role**

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

**Available scopes**: Dashboard, Datasource, EphemeralDashboard, Folder, Role, RoleBinding, Secret, Variable

For global roles:
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
- Never use wildcard scopes without explicit user approval
- Set up RBAC immediately in production

**Step 2: Create a role binding**

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

**Constraints**:
- Verify the role exists before creating bindings
- Ensure role and binding are in the same project

**Gate**: Roles and bindings created and verified. Proceed to Phase 3.

## Phase 3: VERIFY

```bash
percli get project
percli describe project <project-name>
percli get role --project <project-name>
percli get rolebinding --project <project-name>
percli get globalrole
percli get globalrolebinding
```

Or via MCP:
```
perses_list_projects()
perses_list_project_roles(project="<project-name>")
perses_list_project_role_bindings(project="<project-name>")
perses_list_global_roles()
```

**Gate**: Project listed and roles/bindings confirmed. Task complete.

## Error Handling

### Project creation fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| 409 Conflict | Name already taken | Use different name or operate on existing |
| 400 Bad Request | Invalid characters | Use lowercase alphanumeric with hyphens |
| 401 | Not authenticated | Run `percli login` |
| 403 | Lacks create permission | Needs GlobalRole with create on Project |

### Role and RoleBinding fails

| Symptom | Cause | Fix |
|---------|-------|-----|
| "role not found" | Role doesn't exist | Create Role first |
| Binding has no effect | User name doesn't match auth provider | Verify user identity |
| "project not found" | Project doesn't exist | Create project first |
| GlobalRole 403 | No admin permissions | Escalate to admin |

### Wrong project context

| Symptom | Cause | Fix |
|---------|-------|-----|
| Resources in wrong project | Wrong `percli project` context | Run `percli project <name>` before applying |
| "project not set" | No active context | Run `percli project <name>` |
| Permissions don't work | Cross-project role reference | Ensure same project |

## References

| Resource | URL |
|----------|-----|
| Project API docs | https://perses.dev/docs/api/project/ |
| RBAC documentation | https://perses.dev/docs/user-guides/security/rbac/ |
| Authentication docs | https://perses.dev/docs/user-guides/security/authentication/ |
| percli CLI | https://perses.dev/docs/user-guides/percli/ |
| Perses MCP server | https://github.com/perses/perses-mcp-server |
| Perses Operator | https://github.com/perses/perses-operator |
