# Local Overlay Directory

This directory contains **templates** for your private/organization-specific customizations.

## Quick Start

```bash
# One-time setup: Copy templates to .local/
cp -r .local.example/* .local/

# Edit files in .local/ with your real data
# .local/ is gitignored - your changes stay private
```

## How It Works

```
repo/
├── skills/vault-helper/...        ← Generic (public, tracked)
└── .local/skills/vault-helper/...     ← Yours (private, gitignored)
```

**Rule**: Files in `.local/` mirror the repo structure and contain your private data.

## What to Customize

| File | What to Add |
|------|-------------|
| `agents/*.md` | Your internal paths, service names, team conventions |
| `skills/*/references/*.md` | Real examples from your organization |
| `config.yaml` | Environment-specific variables |
| `github-actions-check.yaml` | Your repository mappings |

## Usage

The install script (`./install.sh`) handles overlay merging automatically. Files in `.local/` take precedence when you reference them explicitly.

When you want **your version**:
```
"Read .local/skills/vault-helper/references/examples.md"
```

When you want **generic version** (or sharing):
```
"Read skills/vault-helper/references/examples.md"
```

## Files in This Template

```
.local.example/
├── README.md                              # This file
├── config.yaml                            # Environment configuration template
├── github-actions-check.yaml              # Repository mapping template
├── agents/
│   └── example-customization.md           # Example customized agent
└── skills/
    └── vault-helper/
        └── references/
            └── examples.md                # Example: your real vault paths
```

## Tips

1. **Start small**: Only copy files you need to customize
2. **Keep generic versions**: Don't delete the public versions
3. **Document your changes**: Add comments explaining org-specific parts
4. **Share templates**: If others in your org use this, share your `.local/` structure
5. **Use config.yaml**: Store common variables (team name, repo URLs, etc.)

## Common Customizations

### GitHub Actions Check
Create `.local/github-actions-check.yaml`:
```yaml
# Map your working directories to repositories
repositories:
  /home/youruser/project1: your-org/project1
  /home/youruser/project2: your-org/project2
```

### Vault/Secrets Helper
Create `.local/skills/vault-helper/references/examples.md`:
```markdown
# Your team's Vault paths
- secrets/your-team/production
- secrets/your-team/staging
```

### PR Mining
Create `.local/config.yaml`:
```yaml
# Default repositories for PR mining
default_repos:
  - your-org/main-repo
  - your-org/shared-libs
```
