---
name: deploy
description: "Deploy and infrastructure: web deploy, dev branches, cron, package install, shell configuration."
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Bash
  - Grep
  - Glob
  - Edit
  - Agent
routing:
  force_route: true
  not_for: "Kubernetes or Helm (use kubernetes skill), Ansible (agents handle directly), code review (use review), security scanning (use security)"
  triggers:
    - "deploy website"
    - "deploy site"
    - "go live"
    - "public site"
    - "public website"
    - "static site"
    - "landing page"
    - "make it public"
    - "make public"
    - "set up https"
    - "nginx public site"
    - "host a website"
    - "use my domain"
    - "website online"
    - "put online"
    - "put this online"
    - "put site online"
    - "serve this website"
    - "point my domain"
    - "dev branch"
    - "deploy to dev"
    - "dev lane"
    - "create cron job"
    - "scheduled task"
    - "cron safety"
    - "background automation"
    - "fish shell"
    - "config.fish"
    - "zsh"
    - ".zshrc"
    - "shell cleanup"
    - "background process"
    - "nohup"
    - "trap handler"
  category: infrastructure
  pairs_with:
    - assessment
    - kubernetes
    - pr-workflow
---

# Deploy Skill

Six modes. Match the request to a section.

| Signal | Section |
|--------|---------|
| Deploy site, HTTPS, nginx, go live, public site | A. Public Web Deploy |
| Dev branch, Concourse dev lane, hermes/maia | B. Dev-Branch Deploy |
| Cron job, scheduled task, audit cron script | C. Cron Automation |
| Headless agent, wrapper script, recurring Claude task | D. Headless Cron Creator |
| Install toolkit, verify setup, health check | E. Toolkit Install |
| Fish shell, Zsh, shell config, migration | F. Shell Configuration |
| Background process, nohup, trap, PID, signals | G. Process Management |

When the request spans modes, compose the relevant sections.

---

## A. Public Web Deploy

Serve public sites through nginx/Caddy/Apache -- never a raw dev server. Local preview binds `127.0.0.1`; public sites require HTTPS + hardened nginx.

**5-phase workflow**: DNS -> Web Server -> HTTPS -> Hardening -> Verify.

1. **DNS**: Create A/AAAA record. Verify: `dig +short A <fqdn>`. Gate: resolves to intended IP.
2. **Web Server**: nginx server block with explicit docroot. Backend proxied to `127.0.0.1`. Test: `nginx -t && systemctl reload nginx`.
3. **HTTPS**: `certbot --nginx -d <fqdn>`. Verify renewal: `certbot renew --dry-run`. Verify redirect: `curl -sI http://<fqdn> | grep -iE '301|308'`.
4. **Hardening**: Firewall (ufw allow 80/443/SSH only), nginx deny rules (`location ~ /\. { deny all; }`), security headers (HSTS, X-Content-Type-Options, CSP in Report-Only), rate limiting (`limit_req`), fail2ban.
5. **Verify**: Run the 13-item security checklist. Spot-check: `curl -s https://<fqdn>/.env -w '%{http_code}\n'` (expect 403/404), `ss -tlnp` (no app ports public).

Load `references/public-web-deploy.md` for the full 13-item checklist, nginx config blocks, and error handling.

---

## B. Dev-Branch Deploy

Test Hermes or Maia stack changes in a live lab region before merging to master via Concourse `dev` lane.

1. **Preflight**: Verify dev branch on both repos + pipeline wired.
2. **Merge feature into dev branch**: `git checkout <stack>-dev-branch && git merge --no-ff origin/<feature> && git push`. Never force-push.
3. **Validate**: Dev lane green. `fly -t <target> watch -j <stack>/deploy-to-dev-<region>`.
4. **Merge to master** via PR after dev validation.

Load `references/dev-branch-deploy.md` for stack parameters, preflight commands, and pipeline regeneration.

---

## C. Cron Automation

Static analysis of cron scripts against a 9-point reliability checklist. Read-only -- never execute scripts.

1. **DISCOVER**: Locate scripts in `scripts/*.sh`, `cron/*.sh`, `jobs/*.sh`. Verify shell shebang.
2. **AUDIT**: Run all 9 checks via regex (verify matches not in comments):

| # | Check | Severity | Key patterns |
|---|-------|----------|-------------|
| 1 | Error handling | CRITICAL | `set -e`, `set -o errexit` |
| 2 | Exit code checking | HIGH | `$?`, `if [ $? -eq` |
| 3 | Logging with timestamps | HIGH | `>> *.log`, `$(date)` |
| 4 | Log rotation | MEDIUM | `find -mtime -delete`, `logrotate` |
| 5 | Working directory | HIGH | `cd "$(dirname"`, `SCRIPT_DIR=` |
| 6 | PATH environment | MEDIUM | `PATH=`, `export PATH` |
| 7 | Lock file / concurrency | HIGH | `.lock`, `flock`, `.pid` |
| 8 | Cleanup on exit | MEDIUM | `trap ... EXIT` |
| 9 | Failure notification | LOW | `mail -s`, `curl *webhook` |

3. **REPORT**: Per-script scores with paste-ready fixes for every FAIL/WARN. Aggregate summary for multi-script audits.

Load `references/cron-automation.md` for the best-practices reference script.

---

## D. Headless Cron Creator

Create headless Claude Code cron jobs. All crontab mutations go through `crontab-manager.py`.

1. **PARSE**: Extract name (kebab-case), prompt, schedule, workdir, budget ($2.00 default).
2. **GENERATE**: `python3 ~/.claude/scripts/crontab-manager.py generate-wrapper --name <name> ...`. Verify: `flock`, `--permission-mode auto`, `--max-budget-usd`, `tee` logging, dry-run default.
3. **VALIDATE**: `bash -n scripts/<name>-cron.sh`. Run 9-point cron checklist.
4. **INSTALL**: Dry-run first (`--dry-run`), ask user confirmation, then install.
5. **REPORT**: Script path, schedule, log dir, budget, management commands.

Load `references/headless-cron-creator.md` for the full methodology and schedule conversion table.

---

## E. Toolkit Install

1. Run `python3 ~/.claude/scripts/install-doctor.py check` and `python3 ~/.claude/scripts/toolkit-health.py --json`.
2. If issues: guide user to `./install.sh --symlink`. Fix permissions and deps as needed.
3. Show inventory: `python3 ~/.claude/scripts/install-doctor.py inventory`.
4. Show MCP status: `python3 ~/.claude/scripts/mcp-registry.py list`.
5. Orient: `/do`, `/comprehensive-review`, `/install` commands.

Load `references/install.md` for full diagnostic steps and error handling.

---

## F. Shell Configuration

Detect target shell first. Fish and Zsh have incompatible syntax.

| Concept | Fish | Zsh |
|---------|------|-----|
| Variable assignment | `set -gx VAR value` | `export VAR=value` |
| PATH management | `fish_add_path` | `typeset -U path; path=(...)` |
| Completions | `completions/` directory | `compinit` + `fpath` |
| Conditionals | `test`, not `[[ ]]` | `[[ ]]` preferred |
| Interactive guard | `status is-interactive` | `[[ -o interactive ]]` |

Load the shell-specific reference matching the task:

| Task | Fish | Zsh |
|------|------|-----|
| Full config | `references/fish-shell-config.md` | `references/zsh-shell-config.md` |
| Migration from Bash | `references/fish-bash-migration.md` | `references/zsh-bash-migration.md` |
| Variables, special vars | `references/fish-quick-reference.md` | `references/zsh-quick-reference.md` |
| Error audit, failure modes | `references/fish-preferred-patterns.md` | `references/zsh-preferred-patterns.md` |
| Dev tool integration | `references/fish-tool-integrations.md` | `references/zsh-tool-integrations.md` |

---

## G. Process Management

Match the need to the pattern:

| Goal | Command |
|------|---------|
| Background job, exits with shell | `cmd &` |
| Survive shell exit | `nohup cmd > log 2>&1 &` |
| Detach from job control | `cmd & disown` |
| Full detach, new session | `setsid cmd > log 2>&1 < /dev/null &` |
| System daemon | systemd unit file |

All backgrounded processes must redirect stdio: `> out 2>&1 < /dev/null &`. Order matters: `> out 2>&1` is correct; `2>&1 > out` is almost always a bug.

Key rule: verify the observable state (port free, PID dead) after every kill -- do not assume `kill` succeeded.

Load deep references for specific tasks:

| Task | Reference |
|------|-----------|
| Process lifecycle patterns | `references/shell-process-patterns.md`, `references/starting-processes.md` |
| PID capture and resolution | `references/pid-resolution.md` |
| Signal and trap discipline | `references/signals-and-traps.md` |
| Kill verification, stale PID | `references/cleanup-verification.md` |
| Shell gotchas (`set -e`, `|| true`) | `references/preferred-patterns.md` |

---

## Deep References

All references below are >100 lines of domain-specific content. Load as directed by the sections above.

| Reference | Lines | Domain |
|-----------|-------|--------|
| `references/public-web-deploy.md` | 259 | Full public deploy workflow + security checklist |
| `references/dev-branch-deploy.md` | 156 | Concourse dev-branch workflow |
| `references/cron-automation.md` | 194 | 9-point cron audit checklist |
| `references/headless-cron-creator.md` | 150 | Headless cron job creation |
| `references/install.md` | 195 | Toolkit install and health check |
| `references/shell-error-handling.md` | 226 | Shell error handling patterns |
| `references/concurrency-and-locks.md` | 219 | Concurrency and locking |
| `references/logging-and-rotation.md` | 231 | Logging and rotation |
| `references/starting-processes.md` | 152 | Process start patterns |
| `references/shell-process-patterns.md` | 247 | Process lifecycle patterns |
| `references/pid-resolution.md` | 200 | PID capture and resolution |
| `references/signals-and-traps.md` | 259 | Signal and trap discipline |
| `references/cleanup-verification.md` | 253 | Kill-and-check verification |
| `references/preferred-patterns.md` | 354 | Shell gotchas and fixes |
| `references/fish-shell-config.md` | 247 | Fish shell configuration |
| `references/fish-bash-migration.md` | 149 | Bash-to-Fish migration |
| `references/fish-quick-reference.md` | 229 | Fish variable scope guide |
| `references/fish-preferred-patterns.md` | 240 | Fish failure modes |
| `references/fish-tool-integrations.md` | 318 | Fish dev tool patterns |
| `references/zsh-shell-config.md` | 310 | Zsh shell configuration |
| `references/zsh-bash-migration.md` | 248 | Bash-to-Zsh migration |
| `references/zsh-quick-reference.md` | 332 | Zsh parameter expansion |
| `references/zsh-preferred-patterns.md` | 290 | Zsh failure modes |
| `references/zsh-tool-integrations.md` | 368 | Zsh dev tool patterns |
