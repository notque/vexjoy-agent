# Ansible Security Reference

> **Scope**: Vault encryption, secret management, privilege escalation, and credential hygiene in Ansible automation
> **Version range**: Ansible 2.9+ / ansible-core 2.12+
> **Generated**: 2026-04-04 — verify against current Ansible Vault and Collections documentation

---

## Overview

Ansible security failures typically come from three sources: secrets stored in plaintext (in playbooks, vars files, or git history), privilege escalation misconfiguration, and SSH key management errors. The Ansible Vault subsystem handles encryption at rest; the challenge is ensuring everything sensitive is encrypted before it ever reaches a file.

---

## Pattern Table

| Pattern | Version | Use When | Avoid When |
|---------|---------|----------|------------|
| `ansible-vault encrypt_string` | 2.4+ | Encrypting individual variable values inline | Encrypting entire files (use `encrypt` instead) |
| `ansible-vault encrypt` | all | Encrypting entire vars files or secrets files | Single-variable secrets in large playbooks |
| `--vault-id label@prompt` | 2.4+ | Multiple vault passwords / per-environment keys | Single-password setups (use `--ask-vault-pass`) |
| `no_log: true` | all | Tasks that print sensitive output (passwords, tokens) | Debug tasks where output is needed |
| `become: true` + `become_user` | all | Scoped privilege escalation to specific tasks | Playbook-level `become` on non-privileged tasks |

---

## Correct Patterns

### Encrypt Secrets at Variable Level

Encrypt only the secret value, not the entire vars file, so non-secret variables remain readable.

```yaml
# group_vars/production/vault.yml — encrypt the VALUE, not the key
db_password: !vault |
  $ANSIBLE_VAULT;1.1;AES256
  38626637...

# group_vars/production/main.yml — plaintext, readable in git
db_host: db.prod.example.com
db_port: 5432
db_name: myapp
db_password: "{{ vault_db_password }}"
```

**Why**: Whole-file encryption makes diffs unreadable and forces decryption to see what changed. Per-variable encryption keeps history readable while protecting secrets.

---

### Use `no_log` on Tasks That Handle Credentials

```yaml
- name: Set database password
  community.mysql.mysql_user:
    name: appuser
    password: "{{ db_password }}"
    priv: "myapp.*:ALL"
  no_log: true  # Prevents password from appearing in output/logs

- name: Create API token
  uri:
    url: https://api.example.com/tokens
    method: POST
    body_format: json
    body:
      username: "{{ api_user }}"
      password: "{{ api_password }}"
  no_log: true
  register: api_token_response
```

**Why**: Without `no_log: true`, Ansible prints full task arguments to stdout, log files, and Tower/AWX. Any observer with log access sees plaintext credentials.

---

### Scope `become` to Tasks That Need It

```yaml
# Bad: Entire play runs as root
- hosts: webservers
  become: true  # Everything runs as root

  tasks:
    - name: Read config file
      slurp:
        src: /etc/app/config.yml  # Does not need root

# Good: become scoped to tasks requiring elevated privileges
- hosts: webservers
  tasks:
    - name: Read config file
      slurp:
        src: /etc/app/config.yml

    - name: Install nginx
      apt:
        name: nginx
        state: present
      become: true  # Only this task runs as root
```

**Why**: Playbook-level `become` runs all tasks — including read operations and non-privileged commands — as root. Task-level `become` limits the blast radius of a privilege escalation misconfiguration.

---

## Anti-Pattern Catalog

### ❌ Plaintext Secrets in Playbooks or Vars Files

**Detection**:
```bash
# Scan for hardcoded passwords/tokens (not vault-encrypted)
grep -rn "password:\|api_key:\|secret:\|token:" group_vars/ host_vars/ playbooks/ \
  | grep -v "!vault" | grep -v "^#" | grep -v "vault_"

# Find variables that LOOK like secrets but aren't encrypted
grep -rn "password:" playbooks/ roles/ \
  | grep -v "!vault" | grep -v "_password:" | grep -v "#"
```

**What it looks like**:
```yaml
# vars/main.yml — NEVER DO THIS
db_password: MyS3cr3tP@ssword!
aws_access_key: AKIAIOSFODNN7EXAMPLE
aws_secret_key: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**Why wrong**: Plaintext secrets in any file will eventually reach git history. Git history is permanent — even after deletion, the secret exists in every clone and every CI artifact that ran during that period. Rotation requires assuming full compromise.

**Fix**:
```bash
# Encrypt inline
ansible-vault encrypt_string 'MyS3cr3tP@ssword!' --name 'db_password'

# Or encrypt entire file
ansible-vault encrypt vars/secrets.yml
```

**Version note**: `encrypt_string` available since Ansible 2.3. For older versions, encrypt entire vars files.

---

### ❌ SSH Private Keys in Playbooks or Inventory

**Detection**:
```bash
grep -rn "ansible_ssh_private_key_file\|private_key_file" inventory/ group_vars/ \
  | grep -v "~/.ssh\|/home\|/root\|vault"

# Find PEM headers accidentally committed
grep -rn "BEGIN.*PRIVATE KEY\|BEGIN RSA" .
```

**What it looks like**:
```ini
# inventory/hosts.ini — NEVER DO THIS
[webservers]
web01 ansible_ssh_private_key_file=keys/deploy_key.pem
```

**Why wrong**: Private keys committed to a repository expose root access to every server in the inventory. Even with a gitignore rule added later, the key exists in git history.

**Fix**:
```yaml
# Use key file path outside repo, reference via variable
ansible_ssh_private_key_file: "{{ lookup('env', 'SSH_DEPLOY_KEY_PATH') }}"

# Or store path in vault-encrypted variable
ansible_ssh_private_key_file: "{{ vault_deploy_key_path }}"
```

---

### ❌ Storing Vault Password in Plaintext on Disk

**Detection**:
```bash
# Find .vault_pass files tracked by git
git ls-files | grep -i vault_pass

# Find vault password files referenced in ansible.cfg
grep -n "vault_password_file" ansible.cfg
```

**What it looks like**:
```ini
# ansible.cfg
[defaults]
vault_password_file = .vault_pass  # .vault_pass contains plaintext password
```

**Why wrong**: If `.vault_pass` is readable and stored with the repo, it defeats the purpose of encryption. Anyone with repo access can decrypt all vault values.

**Fix**:
```ini
# ansible.cfg — use a script that fetches from a secrets manager
[defaults]
vault_password_file = scripts/vault-password.sh
```

```bash
# scripts/vault-password.sh — fetches from AWS Secrets Manager
#!/bin/bash
aws secretsmanager get-secret-value \
  --secret-id ansible/vault-password \
  --query SecretString \
  --output text
```

---

## Error-Fix Mappings

| Error Message | Root Cause | Fix |
|---------------|------------|-----|
| `Decryption failed (no vault secrets would decrypt)` | Wrong vault password or vault ID mismatch | Run with `--ask-vault-pass` to confirm password; check `--vault-id` matches encryption label |
| `ERROR! Attempting to decrypt but no vault secrets found` | Missing `--vault-id` or `--ask-vault-pass` in command | Add `--vault-id @prompt` or configure `vault_password_file` in `ansible.cfg` |
| `sudo: no password supplied` | `become_pass` not set or `become_method` mismatch | Set `ansible_become_password: "{{ vault_become_password }}"` in group_vars |
| `Permission denied (publickey)` | SSH key not in `authorized_keys` or wrong key file | Verify with `ssh -i keyfile user@host`; check `ansible_ssh_private_key_file` points to correct key |
| `Missing sudo password` | Remote user requires password for sudo | Use `--ask-become-pass` flag or set `ansible_become_password` in vault |

---

## Detection Commands Reference

```bash
# Plaintext secrets not encrypted with vault
grep -rn "password:\|api_key:\|secret:\|token:" group_vars/ host_vars/ playbooks/ \
  | grep -v "!vault" | grep -v "^#"

# SSH private keys in repository
grep -rn "BEGIN.*PRIVATE KEY\|BEGIN RSA" .

# Vault password files tracked in git
git ls-files | grep -i vault_pass

# Tasks missing no_log on credential operations
grep -rn -A10 "password:\|secret:" roles/*/tasks/ playbooks/ \
  | grep -B5 "no_log" | grep -v "no_log"

# Unencrypted vault files (should start with $ANSIBLE_VAULT)
find . -name "vault.yml" -o -name "secrets.yml" | xargs grep -L "ANSIBLE_VAULT"
```

---

## See Also

- `testing.md` — Molecule and ansible-lint patterns including secret scanning
- [Ansible Vault documentation](https://docs.ansible.com/ansible/latest/vault_guide/index.html)
