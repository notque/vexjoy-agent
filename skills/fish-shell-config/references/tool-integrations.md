# Fish Shell Tool Integrations

> **Scope**: Concrete fish shell integration patterns for common dev tools (Go, Rust, Docker, Node.js, Python, and shell enhancers). Covers PATH setup, init hooks, and abbreviation patterns. Does not cover tool installation.
> **Version range**: Fish 3.0+; tool-version notes inline where behavior differs
> **Generated**: 2026-04-17

---

## Overview

Each tool integration follows the same three-part structure: (1) PATH and env setup in `conf.d/00-path.fish` or `conf.d/10-env.fish`, (2) init hook with `type -q` guard in `conf.d/30-tools.fish`, (3) abbreviations in `conf.d/20-abbreviations.fish` guarded by `status is-interactive`. Copy-paste sections into the appropriate file.

---

## Pattern Table

| Tool | Init Pattern | PATH Location | Version Notes |
|------|-------------|---------------|---------------|
| Go | `set -gx GOPATH` | `fish_add_path ~/go/bin` | Go 1.16+: `GOPATH` auto-set if unset |
| Rust/Cargo | none (cargo sets PATH via rustup) | `fish_add_path ~/.cargo/bin` | rustup 1.24+ writes to `fish_user_paths` on install |
| Node/fnm | `fnm env --use-on-cd \| source` | handled by fnm | fnm 1.32+ has native Fish support |
| Python/pyenv | `pyenv init - fish \| source` | `fish_add_path ~/.pyenv/bin` | pyenv 2.0+ Fish init command |
| Docker | none (PATH handled by install) | none | abbreviations only |
| starship | `starship init fish \| source` | none | requires starship 0.46+ for Fish |
| direnv | `direnv hook fish \| source` | none | requires direnv 2.21+ for Fish |
| fzf | `fzf --fish \| source` | none | `--fish` flag: fzf 0.48+; older: use fzf.fish plugin |
| zoxide | `zoxide init fish \| source` | none | all versions |
| mise/rtx | `mise activate fish \| source` | none | replaces asdf for Fish |

---

## Go

```fish
# conf.d/10-env.fish
set -gx GOPATH ~/go
set -gx GOROOT /usr/local/go          # Only if Go installed outside $PATH
set -gx CGO_ENABLED 0                 # Optional: disable CGO for pure Go builds

# conf.d/00-path.fish
fish_add_path ~/go/bin                # Your compiled binaries (go install output)
fish_add_path /usr/local/go/bin       # Go toolchain itself (if not in /usr/bin)
```

```fish
# conf.d/20-abbreviations.fish — inside is-interactive guard
abbr -a gob "go build ./..."
abbr -a got "go test ./..."
abbr -a gotr "go test -race ./..."
abbr -a gom "go mod tidy"
abbr -a gor "go run ."
```

**Version note**: Go 1.16+ sets `GOPATH` to `~/go` automatically if unset. Explicitly setting it is harmless but redundant. `GOROOT` is only needed for non-standard Go installations.

---

## Rust / Cargo

```fish
# conf.d/00-path.fish
fish_add_path ~/.cargo/bin            # All cargo-installed tools end up here
```

```fish
# conf.d/20-abbreviations.fish — inside is-interactive guard
abbr -a cb "cargo build"
abbr -a cbr "cargo build --release"
abbr -a ct "cargo test"
abbr -a cr "cargo run"
abbr -a cc "cargo check"
abbr -a ccl "cargo clippy"
abbr -a cf "cargo fmt"
```

**Note**: `rustup` writes a `~/.cargo/env` script for Bash. Ignore it — just add `~/.cargo/bin` to PATH as above. Rustup 1.24+ also tries to update `fish_user_paths` on install; `fish_add_path` is idempotent so running both is harmless.

---

## Node.js — fnm (Recommended)

```fish
# conf.d/30-tools.fish
if type -q fnm
    fnm env --use-on-cd | source      # Auto-switches Node version on cd
end
```

```fish
# conf.d/20-abbreviations.fish — inside is-interactive guard
if type -q fnm
    abbr -a ni "npm install"
    abbr -a nid "npm install --save-dev"
    abbr -a nr "npm run"
    abbr -a nx "npx"
end
```

**Version note**: `fnm env --use-on-cd` requires fnm 1.32+. For older fnm, use `fnm env | source` without `--use-on-cd` and manually run `fnm use` when changing projects.

## Node.js — nvm (Alternative)

```fish
# conf.d/30-tools.fish — nvm is Bash-native; use bass or nvm.fish wrapper
if test -d ~/.nvm
    # Option A: nvm.fish plugin (preferred — native Fish)
    # Install: fisher install jorgebucaran/nvm.fish
    # No additional config needed after plugin install

    # Option B: bass (Bash source wrapper)
    if type -q bass
        function nvm
            bass source ~/.nvm/nvm.sh --no-use ";" nvm $argv
        end
    end
end
```

**Note**: nvm is a Bash project. The `nvm.fish` Fisher plugin is a drop-in replacement that avoids the Bash interop complexity. Prefer fnm or nvm.fish over Bash-bridge patterns.

---

## Python — pyenv

```fish
# conf.d/00-path.fish
fish_add_path ~/.pyenv/bin
fish_add_path ~/.pyenv/shims

# conf.d/30-tools.fish
if type -q pyenv
    pyenv init - fish | source
end
```

```fish
# conf.d/20-abbreviations.fish — inside is-interactive guard
if type -q pyenv
    abbr -a py "python"
    abbr -a pip3 "python -m pip"
end
```

**Version note**: pyenv 2.0+ uses `pyenv init - fish`. Older versions (< 2.0) used `pyenv init -` without the `fish` argument — both work but the newer form is more explicit.

## Python — virtualenv Activation

```fish
# functions/venv.fish — activate/deactivate shortcut
function venv --description "Activate or create .venv"
    if test -d .venv
        source .venv/bin/activate.fish
    else if test -n "$argv[1]"
        python -m venv $argv[1]
        source $argv[1]/bin/activate.fish
    else
        python -m venv .venv
        source .venv/bin/activate.fish
    end
end
```

**Why a function, not an abbreviation**: Activation requires `source`, which only works in Fish function context.

---

## Docker / Docker Compose

```fish
# conf.d/20-abbreviations.fish — inside is-interactive guard
if type -q docker
    abbr -a d "docker"
    abbr -a dc "docker compose"
    abbr -a dcu "docker compose up"
    abbr -a dcud "docker compose up -d"
    abbr -a dcd "docker compose down"
    abbr -a dcl "docker compose logs -f"
    abbr -a dps "docker ps"
    abbr -a dpsa "docker ps -a"
    abbr -a drm "docker rm"
    abbr -a drmi "docker rmi"
    abbr -a dex "docker exec -it"
end
```

**Note**: `docker compose` (V2, no hyphen) is the current syntax. `docker-compose` (V1, with hyphen) is deprecated since Docker Desktop 4.20 / Docker Engine 23.0.

---

## Shell Enhancers

### starship (Cross-Shell Prompt)

```fish
# conf.d/30-tools.fish
if type -q starship
    starship init fish | source
end
```

**Version note**: starship 0.46+ has native Fish support. Requires Fish 3.0+. The `starship init fish` command outputs a Fish function definition — `source` evaluates it in the current shell.

### direnv (Per-Directory Env)

```fish
# conf.d/30-tools.fish
if type -q direnv
    direnv hook fish | source
end
```

**Note**: direnv 2.21+ has native Fish hook support. The hook adds a `cd` event handler; it does not slow down non-cd commands.

### fzf (Fuzzy Finder)

```fish
# conf.d/30-tools.fish
if type -q fzf
    fzf --fish | source              # fzf 0.48+: native Fish key bindings
    # For older fzf (< 0.48), use the fzf.fish Fisher plugin instead
end
```

**Version note**: `fzf --fish` (outputting Fish-native bindings) was introduced in fzf 0.48.0 (2024-01). For fzf < 0.48, the `fzf.fish` Fisher plugin provides equivalent Ctrl+R, Ctrl+T, Alt+C bindings.

### zoxide (Smart cd Replacement)

```fish
# conf.d/30-tools.fish
if type -q zoxide
    zoxide init fish | source
    # After init, 'z dirname' jumps to frecent match
    # 'zi' opens interactive selection with fzf
end
```

### mise / rtx (Version Manager, asdf Replacement)

```fish
# conf.d/30-tools.fish
if type -q mise
    mise activate fish | source
end
```

**Note**: mise (formerly rtx) replaces asdf. The Fish activation hook manages shims automatically. Do not use `asdf` Fish integration alongside mise — they conflict.

---

## Full conf.d Example: Complete Setup

```fish
# ~/.config/fish/conf.d/30-tools.fish
# Tool integrations — all guarded with type -q

# Prompt
if type -q starship
    starship init fish | source
end

# Directory env
if type -q direnv
    direnv hook fish | source
end

# Node version management
if type -q fnm
    fnm env --use-on-cd | source
end

# Python version management
if type -q pyenv
    pyenv init - fish | source
end

# Version manager (mise/rtx)
if type -q mise
    mise activate fish | source
end

# Fuzzy finder
if type -q fzf
    fzf --fish | source
end

# Smart directory navigation
if type -q zoxide
    zoxide init fish | source
end

# Homebrew (macOS only)
if test -x /opt/homebrew/bin/brew
    eval (/opt/homebrew/bin/brew shellenv)
end
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| `command not found: go` after install | Go bin not in PATH | `fish_add_path /usr/local/go/bin` |
| `cargo: command not found` | `~/.cargo/bin` not in PATH | `fish_add_path ~/.cargo/bin` |
| `fnm: Unknown version` on new shell | `--use-on-cd` not in init | Add `fnm env --use-on-cd \| source` |
| direnv not loading `.envrc` | direnv hook not sourced | Add `direnv hook fish \| source` to conf.d |
| `fzf --fish` flag unknown | fzf version < 0.48 | Install fzf.fish plugin via Fisher instead |
| `pyenv: command not found` | pyenv shims not in PATH | `fish_add_path ~/.pyenv/bin ~/.pyenv/shims` |
| nvm not found in Fish | nvm is Bash-only | Use nvm.fish plugin or fnm instead |
| `GOPATH` changes not persisting | Set with `set -g` instead of `set -gx` | Use `set -gx GOPATH ~/go` |

---

## See Also

- `fish-anti-patterns.md` — Detection commands for common Fish config mistakes
- `bash-migration.md` — Bash-to-Fish syntax translation
- `fish-quick-reference.md` — Variable scoping and PATH management cheatsheet
