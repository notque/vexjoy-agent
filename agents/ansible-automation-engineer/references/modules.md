# Ansible Modules Reference

> **Scope**: Module selection patterns, builtin vs command/shell decisions, collection modules, and version-specific module changes
> **Version range**: ansible-core 2.14+ / Ansible Collections (community.general 7.0+)
> **Generated**: 2026-04-04 — verify against current Ansible module documentation

---

## Overview

The most common Ansible anti-pattern is using `command` or `shell` when an idempotent module exists. Module selection determines whether playbooks are idempotent, properly report changes, and work across environments. The hierarchy is: builtin module > collection module > command/shell with explicit `changed_when`.

---

## Pattern Table: Module Selection by Task Type

| Task | Wrong Approach | Correct Module | Notes |
|------|---------------|----------------|-------|
| Install package (Debian) | `command: apt-get install nginx` | `ansible.builtin.apt` | Handles idempotency, state management |
| Install package (RHEL) | `command: yum install nginx` | `ansible.builtin.dnf` | `dnf` preferred over `yum` on RHEL 8+ |
| Install package (any OS) | `shell: {{pkg_mgr}} install` | `ansible.builtin.package` | Cross-platform, uses detected pkg manager |
| Manage service | `command: systemctl start nginx` | `ansible.builtin.systemd` | Reports enabled/started/stopped state |
| Copy file | `command: cp src dst` | `ansible.builtin.copy` | Detects changes by checksum |
| Template | `command: sed 's/VAR/val/g' > /etc/conf` | `ansible.builtin.template` | Jinja2, detects changes, `--diff` support |
| Create dir | `command: mkdir -p /path` | `ansible.builtin.file` | state=directory, handles permissions |
| Download file | `command: wget url -O dest` | `ansible.builtin.get_url` | Checksum validation, change detection |
| Run script once | `shell: /path/to/setup.sh` | `command` + `creates:` | `creates:` makes it idempotent |
| Git checkout | `command: git clone` | `ansible.builtin.git` | Version-aware, detects changes |
| Manage user | `command: useradd -m user` | `ansible.builtin.user` | Full lifecycle, idempotent |
| Manage cron | `command: crontab -e` | `ansible.builtin.cron` | Named entries, idempotent |

---

## Correct Patterns

### Package Installation Across OS Families

```yaml
# Use package module for cross-platform playbooks
- name: Install common packages
  ansible.builtin.package:
    name: "{{ item }}"
    state: present
  loop:
    - nginx
    - python3
    - curl

# Use platform-specific modules when you need platform features
- name: Install nginx with apt options (Debian/Ubuntu)
  ansible.builtin.apt:
    name: nginx
    state: present
    install_recommends: false  # apt-specific option
  when: ansible_os_family == "Debian"

- name: Install nginx with dnf options (RHEL 8+)
  ansible.builtin.dnf:
    name: nginx
    state: present
    enablerepo: epel  # dnf-specific option
  when: ansible_distribution_major_version | int >= 8 and ansible_os_family == "RedHat"
```

**Why**: `package` abstracts over OS differences. Use `apt`/`dnf` only when platform-specific options (repos, recommends, module streams) are needed.

---

### Service Management with systemd

```yaml
# Start and enable in one task
- name: Enable and start nginx
  ansible.builtin.systemd:
    name: nginx
    state: started
    enabled: true
    daemon_reload: true  # Required when unit files change

# Restart via handler (triggered by config change)
- name: Deploy nginx config
  ansible.builtin.template:
    src: nginx.conf.j2
    dest: /etc/nginx/nginx.conf
    mode: '0644'
  notify: Restart nginx

# handlers/main.yml
- name: Restart nginx
  ansible.builtin.systemd:
    name: nginx
    state: restarted
```

**Why**: Handlers ensure services restart only when the triggering resource actually changed. Using `state: restarted` directly in tasks causes restarts on every run.

---

### Making `command` Idempotent with `creates`

```yaml
# When no module exists, use command with creates/removes
- name: Run database migration
  ansible.builtin.command:
    cmd: /app/bin/migrate up
    chdir: /app
    creates: /app/.migrations-complete  # Skip if this file exists

# After migration, create the sentinel file
- name: Mark migrations complete
  ansible.builtin.file:
    path: /app/.migrations-complete
    state: touch
    mode: '0644'

# For scripts that can be re-run safely
- name: Check if cluster is initialized
  ansible.builtin.command: kubectl get nodes
  register: cluster_check
  changed_when: false
  failed_when: false

- name: Initialize cluster
  ansible.builtin.command: kubeadm init --config /etc/kubeadm/config.yml
  when: cluster_check.rc != 0
```

---

## Anti-Pattern Catalog

### ❌ Using `shell` for Package Management

**Detection**:
```bash
# Find shell/command used for package installation
grep -rn "command:\|shell:" playbooks/ roles/ \
  | grep -E "apt-get|yum|dnf|pip install|npm install"

rg -t yaml '(command|shell):.*\b(apt-get|yum|dnf|pip)\b' roles/ playbooks/
```

**What it looks like**:
```yaml
- name: Install nginx
  shell: apt-get install -y nginx

- name: Update packages
  command: yum update -y
```

**Why wrong**: `shell`/`command` always report `changed` regardless of whether nginx was already installed. Running twice installs twice (or errors). No change tracking. Breaks `--check` mode (would show false changes).

**Fix**:
```yaml
- name: Install nginx
  ansible.builtin.apt:
    name: nginx
    state: present
    update_cache: true
    cache_valid_time: 3600  # Only update cache if older than 1 hour
```

---

### ❌ Using `command: systemctl` Instead of `systemd` Module

**Detection**:
```bash
grep -rn "command:\|shell:" roles/ playbooks/ \
  | grep "systemctl"

rg -t yaml '(command|shell):.*systemctl' roles/ playbooks/
```

**What it looks like**:
```yaml
- name: Start nginx
  command: systemctl start nginx

- name: Enable nginx on boot
  shell: systemctl enable nginx
```

**Why wrong**: Doesn't report the service state as a change properly. Can't use `--check` mode (would actually run `systemctl`). Doesn't integrate with handlers. Two tasks when one suffices.

**Fix**:
```yaml
- name: Start and enable nginx
  ansible.builtin.systemd:
    name: nginx
    state: started
    enabled: true
```

---

### ❌ Using `copy` for Templated Content

**Detection**:
```bash
# Find copy tasks that use variables in src
grep -rn -A5 "ansible.builtin.copy:\|^  copy:" roles/ playbooks/ \
  | grep "content:.*{{" 

# Find hardcoded config files that should be templates
grep -rn "copy:" roles/ playbooks/ -A3 \
  | grep "src:.*\.conf\|src:.*\.cfg\|src:.*\.ini"
```

**What it looks like**:
```yaml
- name: Copy nginx config
  ansible.builtin.copy:
    src: files/nginx.conf  # Static file, no variable substitution
    dest: /etc/nginx/nginx.conf
    # But the file contains: listen {{ nginx_port }};  ← variable!
```

**Why wrong**: `copy` sends the file verbatim — Jinja2 variables are NOT evaluated. The destination file will contain literal `{{ nginx_port }}` text, causing nginx to fail to parse it.

**Fix**:
```yaml
- name: Deploy nginx config
  ansible.builtin.template:
    src: templates/nginx.conf.j2  # .j2 extension by convention
    dest: /etc/nginx/nginx.conf
    mode: '0644'
    owner: root
    group: root
  notify: Reload nginx
```

---

## Version-Specific Notes

| Version | Change | Impact |
|---------|--------|--------|
| ansible-core 2.12 | FQCN (Fully Qualified Collection Names) required by default in lint | Replace `copy:` with `ansible.builtin.copy:` in new playbooks |
| ansible-core 2.14 | `yum` module deprecated, use `dnf` | Replace `ansible.builtin.yum` with `ansible.builtin.dnf` for RHEL 8+ |
| ansible-core 2.8 | `include` deprecated, split into `import_tasks`/`include_tasks` | `import_tasks`: static (preprocessed), `include_tasks`: dynamic (runtime) |
| collections 3.0+ | `community.general` modules split into sub-namespaces | Some modules moved; verify FQCN against current collection docs |

---

## Detection Commands Reference

```bash
# Find command/shell that should use specific modules
grep -rn "command:\|shell:" roles/ playbooks/ \
  | grep -E "apt-get|yum|dnf|systemctl|useradd|mkdir|wget|curl -o"

# Find deprecated module names (non-FQCN)
ansible-lint --profile production --show-relpath

# Find 'include' instead of import_tasks/include_tasks
grep -rn "^\s*- include:" playbooks/ roles/

# Audit for copy vs template confusion
grep -rn -B2 "^.*copy:" roles/ playbooks/ \
  | grep "src:.*\.conf\|src:.*\.cfg"
```

---

## See Also

- `testing.md` — Molecule and ansible-lint patterns to validate module correctness
- `security.md` — Vault encryption for module credentials
