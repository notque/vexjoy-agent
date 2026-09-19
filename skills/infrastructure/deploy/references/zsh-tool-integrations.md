# Zsh Tool Integrations

> **Scope**: Concrete zsh integration patterns for common dev tools (Go, Rust, Docker, Node.js, Python, and shell enhancers). Covers PATH setup, eval hooks, and alias patterns. Does not cover tool installation.
> **Version range**: Zsh 5.8+; tool-version notes inline where behavior differs
> **Generated**: 2026-05-26

---

## Overview

Each tool integration follows the same structure: (1) PATH and env setup in `~/.zshenv`, (2) eval hook with availability guard in `~/.zshrc`, (3) aliases in `~/.zshrc` inside an interactive guard. Use `(( $+commands[tool] ))` (hash lookup, no subprocess) or `command -v tool &>/dev/null` (POSIX, spawns subprocess) for availability checks.

---

## Pattern Table

| Tool | Init Pattern | PATH Location | Version Notes |
|------|-------------|---------------|---------------|
| Go | `export GOPATH` | `path+=(~/go/bin)` | Go 1.16+: `GOPATH` defaults to `~/go` |
| Rust/Cargo | source `~/.cargo/env` | `path+=(~/.cargo/bin)` | rustup writes `~/.cargo/env` for sh/bash/zsh |
| Node/fnm | `eval "$(fnm env --use-on-cd)"` | handled by fnm | fnm 1.32+: native zsh support |
| Python/pyenv | `eval "$(pyenv init -)"` | `path+=(~/.pyenv/bin ~/.pyenv/shims)` | pyenv 2.0+: use `pyenv init -` |
| Docker | none (PATH handled by installer) | none | aliases only |
| starship | `eval "$(starship init zsh)"` | none | requires starship 0.46+ |
| direnv | `eval "$(direnv hook zsh)"` | none | requires direnv 2.21+ |
| fzf | `source <(fzf --zsh)` | none | `--zsh` flag: fzf 0.48+; older: source `~/.fzf.zsh` |
| zoxide | `eval "$(zoxide init zsh)"` | none | all versions |
| mise | `eval "$(mise activate zsh)"` | none | replaces asdf |
| Homebrew (macOS) | `eval "$(brew shellenv)"` | handled by shellenv | place in `~/.zprofile` for login shells |

---

## Availability Check Patterns

```zsh
# Preferred: hash lookup (fastest, no subprocess)
if (( $+commands[starship] )); then
  eval "$(starship init zsh)"
fi

# Alternative: command -v (POSIX, spawns subprocess)
if command -v direnv &>/dev/null; then
  eval "$(direnv hook zsh)"
fi

# For checking files/directories (not commands)
if [[ -f ~/.cargo/env ]]; then
  source ~/.cargo/env
fi

if [[ -d ~/.pyenv ]]; then
  path=(~/.pyenv/bin ~/.pyenv/shims $path)
fi
```

---

## Go

```zsh
# ~/.zshenv
export GOPATH=~/go
# GOROOT only needed for non-standard Go installations:
# export GOROOT=/usr/local/go

typeset -U path
path=(~/go/bin $path)       # Compiled binaries (go install output)
# path=(/usr/local/go/bin $path)  # Go toolchain — only if not already in PATH
export PATH
```

```zsh
# ~/.zshrc — aliases (inside interactive check or at top level, zsh always checks)
if (( $+commands[go] )); then
  alias gob="go build ./..."
  alias got="go test ./..."
  alias gotr="go test -race ./..."
  alias gom="go mod tidy"
  alias gor="go run ."
  alias goi="go install ./..."
fi
```

**Version note**: Go 1.16+ sets `GOPATH` to `~/go` automatically if unset. Explicitly setting it is harmless but documents the intent. `GOROOT` is only needed for non-standard installations (e.g., Go installed via tarball to a custom path).

---

## Rust / Cargo

```zsh
# ~/.zshenv
# Option A: source rustup's env script (sets PATH, CARGO_HOME, RUSTUP_HOME)
[[ -f ~/.cargo/env ]] && source ~/.cargo/env

# Option B: direct path addition (simpler, equivalent for most setups)
typeset -U path
path=(~/.cargo/bin $path)
export PATH
```

```zsh
# ~/.zshrc — aliases
if (( $+commands[cargo] )); then
  alias cb="cargo build"
  alias cbr="cargo build --release"
  alias ct="cargo test"
  alias cr="cargo run"
  alias cc="cargo check"
  alias ccl="cargo clippy"
  alias cf="cargo fmt"
  alias cfd="cargo fmt --check"
fi
```

**Note**: `rustup` writes `~/.cargo/env` — a sh/bash/zsh-compatible script that sets `PATH`, `CARGO_HOME`, and `RUSTUP_HOME`. Sourcing it is equivalent to manually adding `~/.cargo/bin` to PATH. Both approaches work; sourcing `~/.cargo/env` is more robust when `CARGO_HOME` is customized.

---

## Node.js — fnm (Recommended)

```zsh
# ~/.zshrc
if (( $+commands[fnm] )); then
  eval "$(fnm env --use-on-cd)"    # Auto-switches Node version on cd
fi
```

```zsh
# ~/.zshrc — aliases
if (( $+commands[fnm] )); then
  alias ni="npm install"
  alias nid="npm install --save-dev"
  alias nr="npm run"
  alias nx="npx"
  alias nls="fnm list"
  alias nuse="fnm use"
fi
```

**Version note**: `fnm env --use-on-cd` requires fnm 1.32+. For older fnm, use `eval "$(fnm env)"` without `--use-on-cd` and run `fnm use` manually when changing projects.

## Node.js — nvm (Alternative)

```zsh
# ~/.zshrc — nvm is bash-native; source directly in zsh (zsh is sh-compatible)
if [[ -s ~/.nvm/nvm.sh ]]; then
  source ~/.nvm/nvm.sh              # Load nvm
  source ~/.nvm/bash_completion     # Optional: nvm tab completion
fi
```

**Note**: nvm works in Zsh despite being written for Bash — Zsh's POSIX compatibility handles it. For a native experience, prefer fnm (faster, has native Zsh hooks) or install the `zsh-nvm` plugin.

---

## Python — pyenv

```zsh
# ~/.zshenv
if [[ -d ~/.pyenv ]]; then
  typeset -U path
  path=(~/.pyenv/bin ~/.pyenv/shims $path)
  export PATH
  export PYENV_ROOT=~/.pyenv
fi
```

```zsh
# ~/.zshrc
if (( $+commands[pyenv] )); then
  eval "$(pyenv init -)"
fi
```

```zsh
# ~/.zshrc — aliases
if (( $+commands[pyenv] )); then
  alias py="python"
  alias pip="python -m pip"
fi
```

**Version note**: pyenv 2.0+ uses `pyenv init -` (no language argument). Older pyenv (< 2.0) used the same syntax but without the `--path` / `--no-path` flags added later. Both work; the newer form is preferred.

## Python — venv Helper

```zsh
# ~/.zshrc — venv activation function
venv() {
  local venv_dir="${1:-.venv}"
  if [[ -d "$venv_dir" ]]; then
    source "$venv_dir/bin/activate"
  else
    python -m venv "$venv_dir" && source "$venv_dir/bin/activate"
  fi
}
```

---

## Docker / Docker Compose

```zsh
# ~/.zshrc — aliases (no init hook needed; Docker modifies PATH at install)
if (( $+commands[docker] )); then
  alias d="docker"
  alias dc="docker compose"
  alias dcu="docker compose up"
  alias dcud="docker compose up -d"
  alias dcd="docker compose down"
  alias dcl="docker compose logs -f"
  alias dps="docker ps"
  alias dpsa="docker ps -a"
  alias dex="docker exec -it"
  alias drm="docker rm"
  alias drmi="docker rmi"
  alias dprune="docker system prune -af"
fi
```

**Note**: `docker compose` (V2, no hyphen) is the current syntax. `docker-compose` (V1, with hyphen) is deprecated since Docker Desktop 4.20 / Docker Engine 23.0.

---

## Shell Enhancers

### starship (Cross-Shell Prompt)

```zsh
# ~/.zshrc
if (( $+commands[starship] )); then
  eval "$(starship init zsh)"
fi
```

**Version note**: starship 0.46+ has native Zsh support. Place this after any framework loading (oh-my-zsh, prezto) so starship overrides their prompt.

### direnv (Per-Directory Env)

```zsh
# ~/.zshrc
if (( $+commands[direnv] )); then
  eval "$(direnv hook zsh)"
fi
```

**Note**: direnv 2.21+ has native Zsh hook support. The hook wraps `cd` to load/unload `.envrc` files automatically. Does not slow down non-cd operations.

### fzf (Fuzzy Finder)

```zsh
# ~/.zshrc — fzf 0.48+ (native --zsh flag)
if (( $+commands[fzf] )); then
  source <(fzf --zsh)
fi

# Fallback for fzf < 0.48 (installed via package manager)
# if [[ -f ~/.fzf.zsh ]]; then
#   source ~/.fzf.zsh
# fi
```

**Version note**: `fzf --zsh` (outputting Zsh-native key bindings) was introduced in fzf 0.48.0 (2024-01). For older fzf, the `~/.fzf.zsh` file (written by `fzf --install`) provides equivalent Ctrl+R, Ctrl+T, Alt+C bindings.

### zoxide (Smart cd Replacement)

```zsh
# ~/.zshrc
if (( $+commands[zoxide] )); then
  eval "$(zoxide init zsh)"
  # After init: 'z dirname' jumps to frecent match; 'zi' opens fzf selector
fi
```

### mise / rtx (Version Manager, asdf Replacement)

```zsh
# ~/.zshrc
if (( $+commands[mise] )); then
  eval "$(mise activate zsh)"
fi
```

**Note**: mise (formerly rtx) replaces asdf for managing language versions (Node, Python, Go, Ruby, etc.). The Zsh activation hook manages shims automatically. Remove asdf integration if switching to mise — they conflict.

### Homebrew (macOS)

```zsh
# ~/.zprofile — login shells only (brew shellenv is slow; run once per login)
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
fi

# Intel Mac
if [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi
```

**Note**: Place in `~/.zprofile` (login shells), not `~/.zshrc` (interactive only). `brew shellenv` sets `HOMEBREW_PREFIX`, `HOMEBREW_CELLAR`, `HOMEBREW_REPOSITORY`, and adds Homebrew bin/sbin to PATH.

---

## Full ~/.zshrc Tool Block Example

```zsh
# ~/.zshrc — tool integrations block (place near end of file)

# Version managers (mise replaces asdf)
if (( $+commands[mise] )); then
  eval "$(mise activate zsh)"
fi

# Python
if (( $+commands[pyenv] )); then
  eval "$(pyenv init -)"
fi

# Node
if (( $+commands[fnm] )); then
  eval "$(fnm env --use-on-cd)"
fi

# Prompt
if (( $+commands[starship] )); then
  eval "$(starship init zsh)"
fi

# Directory env
if (( $+commands[direnv] )); then
  eval "$(direnv hook zsh)"
fi

# Smart cd
if (( $+commands[zoxide] )); then
  eval "$(zoxide init zsh)"
fi

# Fuzzy finder
if (( $+commands[fzf] )); then
  source <(fzf --zsh)
fi
```

---

## Error-Fix Mappings

| Error / Symptom | Root Cause | Fix |
|-----------------|------------|-----|
| `command not found: go` after install | `~/go/bin` not in PATH | Add `path=(~/go/bin $path)` to `~/.zshenv` |
| `cargo: command not found` | `~/.cargo/bin` not in PATH | Add `source ~/.cargo/env` or `path+=(~/.cargo/bin)` to `~/.zshenv` |
| `fnm: Unknown version` on new shell | `--use-on-cd` not in init | Change to `eval "$(fnm env --use-on-cd)"` |
| direnv not loading `.envrc` | direnv hook not sourced | Add `eval "$(direnv hook zsh)"` to `~/.zshrc` |
| `fzf --zsh` flag unknown | fzf version < 0.48 | Use `source ~/.fzf.zsh` instead |
| `pyenv: command not found` | pyenv shims not in PATH | Add `path=(~/.pyenv/bin ~/.pyenv/shims $path)` to `~/.zshenv` |
| Tool init error on every shell | Init without availability guard | Wrap in `(( $+commands[tool] ))` check |
| `GOPATH` not set for scripts | `GOPATH` in `~/.zshrc` not `~/.zshenv` | Move `export GOPATH` to `~/.zshenv` |
| Homebrew tools not found in scripts | `brew shellenv` in `~/.zshrc` | Move `eval "$(brew shellenv)"` to `~/.zprofile` |
| starship prompt missing on non-login shells | `starship init` in `~/.zprofile` | Move to `~/.zshrc` |

---

## See Also

- `zsh-preferred-patterns.md` — Detection commands for common Zsh config mistakes
- `bash-migration.md` — Bash→Zsh syntax translation
- `zsh-quick-reference.md` — Variable scoping and PATH management cheatsheet
