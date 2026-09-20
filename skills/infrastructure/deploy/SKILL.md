---
name: deploy
description: "Repository deployment operations: public web release, Hermes/Maia dev lanes, cron automation, toolkit installation, and safe local process handling."
user-invocable: true
allowed-tools: [Read, Write, Bash, Grep, Glob, Edit, Agent]
routing:
  force_route: true
  not_for: "Kubernetes/Helm, code review, or security scanning."
  triggers: [deploy website, deploy site, go live, public site, public website, static site, landing page, make it public, make public, set up https, nginx public site, host a website, use my domain, website online, put online, put this online, put site online, serve this website, point my domain, dev branch, deploy to dev, dev lane, create cron job, scheduled task, cron safety, background automation, install toolkit, fish shell, config.fish, zsh, .zshrc, shell cleanup, background process, nohup, trap handler]
  pairs_with: [assessment, kubernetes, pr-workflow]
  category: infrastructure
---

# Deploy

Load only the reference matching the request:

| Request | Reference / action |
|---|---|
| Public site, nginx, TLS | `references/public-web-deploy.md` |
| Hermes/Maia dev lane | `references/dev-branch-deploy.md` |
| Audit an existing cron job | `references/cron-automation.md` |
| Create a headless Claude cron job | use the promoted `headless-cron-creator` skill |
| Toolkit install/repair | `references/install.md` |
| CVE source coverage | use the promoted `cve-source-check` skill |
| Endpoint smoke validation | use the promoted `endpoint-validator` skill |

Handle ordinary Fish, Zsh, systemd, and shell/process questions from current model knowledge; they do not need bundled tutorials. Preserve the following local safety boundaries:

- Public services go behind nginx/Caddy/Apache with HTTPS; previews bind loopback. Never expose a raw development server.
- Treat DNS, certificate issuance, service restart, and crontab installation as external mutations. Inspect first and obtain any authorization the active workflow requires immediately before mutation.
- For a destructive process action, resolve the actual target and verify the observable resource afterward (port, socket, lock, or service state), not merely the signal exit code.
- Detached local processes must redirect stdin/stdout/stderr. Do not trust `$!` when a wrapper may fork; resolve the owner from the resource or service manager.
- Never pipe generated text directly into `crontab -`; repository cron entries go through `~/.claude/scripts/crontab-manager.py`, which preserves backups and owned tags.

After deployment, verify from the client side: expected URL/status/content, TLS where public, and that forbidden files or direct backend ports are not exposed. Report the deployed surface and verification evidence.
