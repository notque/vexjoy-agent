# Ansible Testing Reference

> **Scope**: Molecule test scenarios, ansible-lint rules, idempotency validation, check-mode patterns
> **Version range**: Molecule 6.0+ / ansible-lint 6.0+ / ansible-core 2.14+

Three testing layers: ansible-lint (quality/style before execution), check mode (preview changes), Molecule (integration with real containers). Automating all three catches 90% of issues before production.

## Pattern Table

| Tool | Version | Use When | What It Catches |
|------|---------|----------|-----------------|
| `ansible-lint` | 6.0+ | Pre-commit, CI/CD | Style, deprecated syntax, security patterns |
| `--check` mode | all | Pre-production run | Which tasks would change (no side effects) |
| `--diff` mode | all | With `--check` | Exact file/template changes |
| Molecule `verify` | 6.0+ | Post-convergence | State assertions on converged instance |
| `idempotency` scenario | 6.0+ | Full role testing | Tasks that always report `changed` |

---

## Correct Patterns

### Run ansible-lint in CI with Explicit Rules

```yaml
# .github/workflows/lint.yml
- name: Run ansible-lint
  uses: ansible/ansible-lint-action@v6
  with:
    args: "--profile production"

# .ansible-lint — project-level config
profile: production
exclude_paths:
  - molecule/
warn_list:
  - yaml[truthy]
skip_list:
  - 'no-changed-when'  # Only if you've deliberately handled changed_when
```

`production` profile enforces stricter rules. Without it, CI may pass despite security issues.

### Molecule Scenario Structure for Role Testing

```
roles/myrole/
└── molecule/
    └── default/
        ├── molecule.yml       # Platform/driver config
        ├── converge.yml       # The playbook to test
        ├── verify.yml         # State assertions
        └── prepare.yml        # Pre-test setup (optional)
```

```yaml
# molecule/default/molecule.yml
---
driver:
  name: docker
platforms:
  - name: instance
    image: geerlingguy/docker-ubuntu2204-ansible:latest
    pre_build_image: true

provisioner:
  name: ansible
  lint:
    name: ansible-lint

verifier:
  name: ansible
```

```yaml
# molecule/default/verify.yml — assert actual state, not just "it ran"
---
- name: Verify
  hosts: all
  tasks:
    - name: Check nginx is running
      service_facts:

    - name: Assert nginx service is active
      assert:
        that:
          - "'nginx' in services"
          - "services['nginx'].state == 'running'"
        fail_msg: "nginx service is not running"

    - name: Check config file exists and has correct content
      stat:
        path: /etc/nginx/sites-enabled/default
      register: nginx_conf

    - name: Assert config file exists
      assert:
        that: nginx_conf.stat.exists
```

Assert actual state (service running, file exists, port listening), not just "did the task run."

### Idempotency Test Pattern

```yaml
# molecule/default/molecule.yml — add idempotency check
provisioner:
  name: ansible
  playbooks:
    converge: converge.yml
  lint:
    name: ansible-lint

# Or run manually:
# molecule converge && molecule idempotency
```

```bash
# Manual idempotency check — second run should report 0 changed tasks
ansible-playbook site.yml --check 2>&1 | grep -E "changed=|failed="
# Expected: changed=0 failed=0
```

A role reporting `changed` every run breaks pipeline assumptions and indicates state corruption on repeated runs.

## Pattern Catalog

### Set changed_when on All command/shell Tasks
**Detection**:
```bash
# Find command/shell tasks missing changed_when
grep -rn -A5 "^\s*\(command\|shell\):" roles/ playbooks/ \
  | grep -v "changed_when\|register\|when:"

# Or with ripgrep
rg -t yaml '^\s+(command|shell):' roles/ playbooks/ -A5 \
  | grep -B3 -v "changed_when"
```

**Signal**:
```yaml
- name: Check disk usage
  command: df -h
  register: disk_result
  # Missing: changed_when: false
```

**Why**: `command`/`shell` always report `changed` unless told otherwise. Breaks idempotency checks, noisy `--check` output, triggers handlers incorrectly.

**Fix**:
```yaml
- name: Check disk usage
  command: df -h
  register: disk_result
  changed_when: false  # Read-only command, never changes state

- name: Run migration script
  command: /app/bin/migrate up
  register: migration_result
  changed_when: "'No migrations' not in migration_result.stdout"
  # Only reports changed when migrations actually ran
```

---

### Write Meaningful Assertions in verify.yml
**Detection**:
```bash
# Find verify.yml files without assert tasks
grep -rL "assert:" molecule/*/verify.yml

# Find verify.yml files with only ping/gather_facts
grep -rn "tasks:" molecule/*/verify.yml -A5 \
  | grep -v "assert\|stat\|uri\|service_facts\|command"
```

**Signal**:
```yaml
# molecule/default/verify.yml — provides zero value
---
- name: Verify
  hosts: all
  tasks:
    - name: Check connectivity
      ping:
```

**Why**: Ping passing means the container is alive, not that the role worked.

**Fix**:
```yaml
---
- name: Verify
  hosts: all
  gather_facts: false
  tasks:
    - name: Check nginx listening on port 80
      wait_for:
        port: 80
        timeout: 5

    - name: Check nginx config syntax
      command: nginx -t
      changed_when: false

    - name: Verify nginx config file deployed
      stat:
        path: /etc/nginx/sites-available/myapp.conf
      register: config_stat

    - name: Assert config file exists and has correct permissions
      assert:
        that:
          - config_stat.stat.exists
          - config_stat.stat.mode == "0644"
```

---

### Configure ansible-lint with Production Profile
**Detection**:
```bash
# Check if ansible-lint config exists
ls -la .ansible-lint .ansible-lint.yml ansible-lint.yml 2>/dev/null || echo "No ansible-lint config found"

# Run with verbose to see what rules are active
ansible-lint --list-rules 2>&1 | wc -l
```

**Signal**: No ansible-lint config defaults to "basic" profile, missing production-critical rules.

**Why**: Default profile skips security rules (plaintext passwords, deprecated syntax).

**Fix**:
```yaml
# .ansible-lint
profile: production
offline: false
exclude_paths:
  - .cache/
  - molecule/
mock_modules:
  - community.general.nmcli
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `[risky-file-permissions]` | File task missing explicit `mode:` | Add `mode: '0644'` (or appropriate) to all file/template tasks |
| `[no-changed-when]` | command/shell task missing `changed_when` | Add `changed_when: false` for read-only, or `changed_when: result.rc == 0` |
| `[yaml[truthy]]` | Using `yes/no/True/False` instead of `true/false` | Replace with lowercase boolean: `become: true` |
| `Idempotency test failed` | Task reports changed on second run | Add `changed_when: false` or use idempotent module instead of command |
| `FAILED! => module not found` | Module not installed in execution environment | Install collection: `ansible-galaxy collection install community.general` |
| `Permission denied during Molecule converge` | Docker image lacks sudo/become support | Use `geerlingguy/docker-*-ansible` images that include sudo |

---

## Detection Commands Reference

```bash
# Lint with production profile
ansible-lint --profile production

# Check mode preview (no changes applied)
ansible-playbook site.yml --check --diff

# Run Molecule full test suite
molecule test

# Run only idempotency check
molecule converge && molecule idempotency

# Find tasks missing changed_when on command/shell
rg -t yaml '^\s+(command|shell):' roles/ playbooks/ -A10 \
  | grep -B8 -v "changed_when"

# Check for plaintext passwords in playbooks
grep -rn "password:" roles/ playbooks/ group_vars/ \
  | grep -v "!vault\|_password\|#\|become_password"
```

## See Also

- `security.md` — Vault encryption and credential handling
- `modules.md` — Module selection vs command/shell
