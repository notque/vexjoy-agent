# Local Customization Templates

This directory contains tracked examples for private or organization-specific
configuration. Put your edited copies under `.local/`; that directory is
gitignored.

## Quick start

Running `./install.sh` creates `.local/` and copies these templates when the
directory has no files other than `.gitkeep`. It does not overwrite an existing
local setup.

To copy only one template, create its destination first. For example:

```bash
mkdir -p .local/skills/vault-helper/references
cp .local.example/skills/vault-helper/references/examples.md \
  .local/skills/vault-helper/references/examples.md
```

Edit the copy, not the tracked template.

## How local files are used

`.local/` mirrors repository paths, but it is private storage rather than a
general automatic override system. Use a local agent, skill reference, or
configuration file only through the command or workflow that reads it.

For example, explicitly ask an agent to read a customized reference:

```text
Read .local/skills/vault-helper/references/examples.md
```

Use the tracked version when you want the public example:

```text
Read skills/vault-helper/references/examples.md
```

The install profile is the exception: `./install.sh` automatically reads
`.local/profile.yaml` when it exists.

## Install profile

Use `.local/profile.yaml` to exclude selected skills, agents, or hooks during
installation. The easiest setup is the interactive picker:

```bash
./install.sh --configure       # write the profile, then install
./install.sh --configure-only  # write the profile, then exit
```

Or edit a copy by hand:

```bash
cp .local.example/profile.yaml .local/profile.yaml
$EDITOR .local/profile.yaml
./install.sh
```

Without `.local/profile.yaml`, the installer includes the full toolkit. The
picker uses `questionary` when available and falls back to a numbered prompt;
it adds no required dependency.

Profile filtering applies to top-level skills, agents, and hooks. Nested
category skills remain in the Claude tree, while the Codex mirror filters its
top-level skills, agents, and hooks.

## Included templates

| Path | Intended use |
|---|---|
| `profile.yaml` | Components for `./install.sh` to exclude |
| `config.yaml` | Example organization and project values |
| `github-actions-check.yaml` | Example working-directory-to-repository mappings |
| `inject.yaml` | Example placeholder values; no automatic rendering is performed |
| `agents/kubernetes-helm-engineer.md` | Organization-specific agent instructions |
| `skills/vault-helper/references/examples.md` | Organization-specific Vault examples |

Except for `profile.yaml`, these files are examples for workflows that
explicitly read them; copying them alone does not activate new behavior.

## Common customizations

Repository mappings:

```yaml
# .local/github-actions-check.yaml
repositories:
  /home/youruser/project1: your-org/project1
  /home/youruser/project2: your-org/project2
```

Default repositories:

```yaml
# .local/config.yaml
github:
  repos:
    - your-org/main-repo
    - your-org/shared-libs
```

Private references can contain real paths and service names, but avoid storing
credentials in them. Prefer environment variables or your secret manager for
tokens and secrets.
