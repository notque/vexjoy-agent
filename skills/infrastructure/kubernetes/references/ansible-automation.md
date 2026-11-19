# Ansible Automation Reference

> **Scope**: Ansible playbooks, roles, collections, Molecule tests, ansible-lint, Vault, inventory (static and dynamic), execution environments, Ansible 8.0+, Tower/AWX, CI/CD integration, performance (parallelism, fact caching, mitogen).
> **Not here**: Kubernetes manifests, Helm charts, or cluster deploys (`kubernetes-helm.md`); monitoring (`prometheus-grafana.md`); Claude Code hooks and toolkit automation (`toolkit` skill); application test automation (`testing` skill); database schema (`skills/analysis/data/references/database.md`); application code (`programming` skill).

Priorities, in order: idempotency (safe to re-run), readability (clear task names, documented variables), reusability (roles, collections), testability (Molecule, lint, check mode).

## Hard rules

- **Idempotency required**: every task is safe to run many times without changing the result.
- **Check mode first**: preview with `--check` before applying to infrastructure.
- **Vault for secrets**: encrypt all sensitive data with ansible-vault before committing.
- **Lint before run**: run `ansible-lint` on playbooks before execution.

## Defaults (on unless disabled)

- Every task has a descriptive `name:`.
- Tag tasks for selective runs (setup, deploy, rollback).
- Use handlers for restarts and reloads triggered by changes.
- Set `gather_facts: no` when facts are not needed.
- Keep environment values in `group_vars/` and `host_vars/`; put reusable parts in roles.

## Optional (off unless enabled)

- Molecule, only when role testing is requested.
- Dynamic inventory, only for cloud resources (AWS, Azure, GCP plugins).
- Custom modules, only when built-in modules fall short.
- Tower/AWX integration, only when the platform is in use.

## Output

- **Before**: requirements, target systems (inventory, OS, environment), idempotency check (how re-runs stay safe), testing strategy.
- **During**: show playbook YAML, `ansible-playbook` commands, execution output, task results.
- **After**: playbooks or roles created, tasks idempotent, tests passing, docs updated; validation shows `ansible-lint` passed, `--check` verified, Molecule results if used.
- Implementation Schema details: [output-schemas.md](../../../shared-patterns/output-schemas.md).

## Error handling

| Error | Cause | Fix |
|---|---|---|
| Unreachable host | Wrong IP, firewall, SSH key not authorized, wrong user | `ping` the host, check the key in `~/.ssh/authorized_keys`, check `ansible_user` and `ansible_ssh_private_key_file`, test a manual SSH connection |
| Idempotency failure | Task reports `changed` every run (command/shell, bad string compare) | Use specific modules, add `changed_when: false` to info commands, use `creates` with `command`, verify with `--check --diff` |
| Vault decryption failed | Wrong password, vault ID mismatch, bad format | `ansible-vault decrypt --vault-id @prompt`, match `--vault-id` to the encryption ID, re-encrypt if needed, `--ask-vault-pass` for one vault |

## Preferred patterns

- **Specific modules over command**: signal `command: apt-get install nginx` or `shell: systemctl restart nginx`. These aren't idempotent, misreport changes, and skip parameter validation. Use `apt: name=nginx state=present` and `systemd: name=nginx state=restarted`.
- **Error handling on critical tasks**: signal tasks with no `failed_when` or checks. Failures leave hosts inconsistent. Use `failed_when: result.rc != 0`, `block/rescue`, `register` plus assertions.
- **Variables for environment values**: signal hardcoded IPs, paths, versions. Define them in `group_vars/`, `host_vars/`, or role `defaults/main.yml` and reference `{{ variable_name }}`.

## Rationalizations to reject

| Claim | Why it's wrong | Do this |
|---|---|---|
| "command module is simpler" | Not idempotent, no change tracking | Use apt, yum, systemd |
| "Playbooks are simple, no tests needed" | Untested automation breaks production | ansible-lint, check mode, Molecule |
| "Hardcoding is fine for one environment" | Environments multiply | Use variables from day one |
| "We'll add error handling later" | Failures leave systems in a bad state | Handle errors on critical tasks now |
| "Secrets in Git are fine, Vault encrypts them" | Git history keeps mistakes | Use external secret management or vault files |

## Hard gates

Before running automation, check for these. If found: stop, report, fix before continuing.

| Pattern | Why blocked | Fix |
|---|---|---|
| Plaintext secrets in playbooks | Credential exposure | `ansible-vault encrypt_string` |
| command/shell for package management | Not idempotent | apt/yum/package modules |
| No check mode testing | Unpreviewed changes | `--check --diff` first |
| Tasks without names | Unreadable output | Add `name:` to all tasks |
| No idempotency check | Tasks change state every run | Run twice; the second run reports no changes |

```bash
# Plaintext passwords
grep -r "password:" playbooks/ roles/ | grep -v vault | grep -v "#"
# command/shell used for packages or services
grep -r "command:\|shell:" playbooks/ roles/ | grep -E "apt-get|yum|systemctl"
# Unnamed tasks
grep -A2 "^  - " playbooks/*.yml | grep -v "name:"
```

## Verification stops

- After writing or changing a playbook or role: have I checked the target host state (packages, services, file permissions, config)? Automation built without it is speculation.
- After recommending performance changes (parallelism, fact caching, mitogen): do I give before/after metrics (run time, task count), or say why measurement is impossible?
- After changing a playbook for production services: will restarting this service affect others, or break dependent apps?

## Before destructive or live changes

- Before deleting files, removing services, purging packages, or removing users: confirm it is reversible or backups exist. Ansible runs fast across many hosts; a destructive task on the wrong group damages every target at once.
- Before running against production inventory: `ansible-lint` and `--check --diff` first. A logic bug can leave dozens of hosts inconsistent.

## Recommendation format

Each recommendation names the **component** (playbook, role, task, or variable), **current state** (or "new"), **proposed state**, and **risk level** (Low, Medium, High) with a short reason.

## Blockers

Resolve routine issues from repository evidence and existing authorization. When sure, decide, record the assumption, and continue; ask Jev when genuinely unsure. Rows marked **(owner)** need explicit owner confirmation first.

| Situation | Why stop | Ask |
|---|---|---|
| Production inventory **(owner)** | Safety critical | "This targets production hosts. Confirm?" |
| Destructive operations **(owner)** | Data loss | "This deletes or overwrites data. Proceed?" |
| Several environments **(owner)** | Wrong target | "Which environment: dev, staging, or production?" |
| Secrets strategy **(owner)** | Security | "ansible-vault or an external secret manager?" |

Decide explicitly before acting: production vs staging, secrets approach, and service restart strategy (owner confirms each); parallel execution limits.

## Reference loading table

| Signal | Load | Why |
|---|---|---|
| Vault encryption, secrets, credentials, `no_log`, privilege escalation, SSH keys | [ansible-automation/security.md](ansible-automation/security.md) | Vault patterns, secret management, SSH key handling, `no_log` |
| Molecule testing, ansible-lint, idempotency validation, check mode | [ansible-automation/testing.md](ansible-automation/testing.md) | Molecule scenarios, lint config, idempotency tests |
| Module selection, command vs specific module, FQCN, deprecated modules | [ansible-automation/modules.md](ansible-automation/modules.md) | When to use modules vs command/shell, FQCN, version notes |
