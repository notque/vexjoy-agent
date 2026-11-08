# Local Customization Templates

This directory contains tracked examples for private or organization-specific
configuration. Put your edited copies under `.local/`; that directory is
gitignored.

## Quick start

`./install.sh` creates `.local/` only when `--configure` writes
`.local/profile.yaml`. Copy the templates you want by hand.

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
Read .local.example/skills/vault-helper/references/examples.md
```

The install profile is the exception: `./install.sh` automatically reads
`.local/profile.yaml` when it exists (or the file `VEXJOY_INSTALL_PROFILE`
names).

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

Without `.local/profile.yaml`, the installer includes the full toolkit. It
also installs the full toolkit when PyYAML is missing (with no warning) or the
profile is not valid YAML (with only a warning on stderr). The picker uses
`questionary` when available and falls back to a numbered prompt; it adds no
required dependency.

Profile entries name skills by install name (the skill's directory name, such
as `debugging`), agents by file stem, and hooks by filename (`foo.py`). Skills
install flat, so the filter applies to every skill, and the same filter applies
to every runtime the installer writes.

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
