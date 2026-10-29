# Installer layout contract

This page is the layout contract for the `vexinstall` engine (`scripts/vexinstall/`). The engine installs each runtime from this contract, and `vexinstall doctor` checks it.

- Engine CLI: `PYTHONPATH=<repo>/scripts python3 -m vexinstall <plan|apply|sync|doctor|uninstall|repair-repo|prune|restore-trash|restore-settings|migrate-overlays>`
- Callers: `install.sh` (runs `apply`, takeover on) and the SessionStart hook `hooks/sync-to-user-claude.py` (runs `sync --target all`, fail-open). No other code writes a runtime root.
- Source of truth for the per-target tables: `ADAPTERS` in `scripts/vexinstall/adapters.py`. If this page and the code disagree, the code is the bug report.

## Verified Claude Code behavior

Checked on 2026-09-22 against these pages:

- [Skills](https://code.claude.com/docs/en/skills.md)
- [Subagents](https://code.claude.com/docs/en/sub-agents.md)
- [Plugins](https://code.claude.com/docs/en/plugins.md)
- [Settings](https://code.claude.com/docs/en/settings.md)

| Fact | Status | What the engine does about it |
|---|---|---|
| Skill precedence is enterprise > personal > project. A project skill with the same name as a personal skill shadows it. | Documented | `doctor` reports a name in both `~/.claude/skills` and a project `<repo>/.claude/skills` as `duplicate-skill-name` (error). |
| Plugin skills are namespaced `<plugin>:<skill>`, so they never collide with a bare name. | Documented | `doctor` reports a bare name also shipped by an enabled plugin as `plugin-bare-name` (warn, routing ambiguity only). |
| A skill and a command with the same name: the skill wins. | Documented | `plan` skips the command and lists it in `shadowed_commands`. `doctor` flags a leftover command file. |
| Agent dirs are scanned recursively. Project `<repo>/.claude/agents` beats personal `~/.claude/agents`. | Documented | Agents install as per-file entries in a real `agents/` dir, never a whole-dir link. `doctor` flags a whole-dir `agents` link (error) and project-scope agent duplicates (warn). |
| Nested `<subdir>/.claude/skills` dirs are discovered. | Documented | `doctor` lists every nested `<repo>/.claude/skills` or `<repo>/.claude/agents` under the repo, including `.claude/worktrees/*/.claude/...`, as `project-scope-nested-source` (warn), and names found there that are also installed as `duplicate-skill-name` (error). |
| A symlinked skill dir under `~/.claude/skills` loads. | Undocumented; observed working | Symlink mode depends on it. Copy mode (`apply --mode copy`) builds the same shape without links if this ever breaks. |
| Nested dirs in the personal skills root (`~/.claude/skills/<cat>/<name>`) load as skills. | Undocumented | Not relied on. Every skill installs flat as `<root>/skills/<name>`. A category dir or link in a flat root is a `doctor` error. |
| Unknown keys inside a hook entry in `settings.json` are accepted. | Undocumented | Not relied on. Owned hook entries carry no marker key. Ownership comes from the command path (spec 10) and the ledger hashes. |
| Stray non-skill dirs in a skills root (no `SKILL.md`) are ignored. | Undocumented | Only `SUPPORT_DIRS` are installed there. `doctor` warns on any other non-skill dir. |

## Shared rules

- **Flat names.** `<root>/skills/<category>/<name>` installs as `<name>`. `scripts/validate-skill-names.py` fails CI when two public skills share a name. Overlay entries may add a prefix, such as `voice-`.
- **One owner per name.** Overlays never replace public entries, and an `overrides` key in `overlays.json` is rejected. A collision makes `plan` and `apply` exit 3. `sync` leaves that one name as it is on disk and warns.
- **Support dirs** (`SUPPORT_DIRS`): `shared-patterns`, `kb`, `voice-shared`. These install next to skills and have no `SKILL.md`.
- **Data dirs** (`DATA_DIRS`): `reddit-data`, `synced`. Other tools write these under a skills root. The engine never installs, adopts, or removes them, and `doctor` names them as runtime data dirs.
- **Mode.** Symlink mode is the default for a main git checkout outside `/tmp`. Copy mode is used otherwise. Copy and symlink modes produce the same shape. The ledger records the mode, and only `apply --mode` changes it.
- **State.** `~/.claude/vexjoy/`: `ledger.json`, `overlays.json`, `reports/`, `backups/`, `trash/`, `lock`, `bin/python3`.
- **Installed indexes.** `~/.<target>/vexjoy/index/{skills,agents}.json` (public + overlays). Readers find them through `resolve_index(kind, target)` in `scripts/routing_index_merge.py`: `$VEXJOY_INDEX_DIR`, then the installed index, then the repo public index (plus a legacy `INDEX.local.json` if one exists).
- **Repo guard.** No engine write may resolve inside the repo or an overlay root. A write that would triggers exit 4. Every command also refuses up front (exit 4) when the state dir or any target root resolves inside the repo, for example `HOME` set to the checkout.
- **Takeover** (`apply --takeover`, never `sync`). An unowned entry at a desired dest (stale copy, foreign link, or a linked container dir) moves to trash and is replaced. The report lists it under `taken_over`; `restore-trash <ts>` undoes it. Unowned entries at other names are left alone. Takeover containers do not count toward the mass-removal cap.

## Per-target layout

"mode" means the entry follows the install mode (symlink or copy). "external" means the engine generates the whole file (`scripts/vexinstall/external.py`), writes it only when bytes change (mode 600), keeps non-`hooks` keys, drops profile-disabled hooks, and backs up the old file to `~/.claude/vexjoy/backups/<target>-<file>.<ts>`.

| Target | Root | Skills (+ support) | Agents | Commands | Hooks | Scripts | Settings |
|---|---|---|---|---|---|---|---|
| claude | `~/.claude` | `<root>/skills/<name>`, mode | `<root>/agents/<entry>`, mode | `commands/<name>.md`, mode | `hooks`, whole-dir entry | `scripts`, whole-dir entry | `settings.json`, owned entries merged |
| codex | `~/.codex` | `<root>/skills/<name>`, copy; support copy | `<root>/agents/<entry>`, copy | none | `<root>/hooks/<entry>` + `<root>/hooks/lib/<entry>` | `<root>/scripts/<entry>` | `hooks.json`, `config.toml`: external |
| factory | `~/.factory` | `<root>/skills/<name>`, mode | `<root>/droids/<entry>`, mode | `commands/<name>.md`, mode | `hooks`, whole-dir entry | `scripts`, whole-dir entry | `settings.json`: external |
| hermes | `~/.hermes` | `<root>/skills/<name>`, mode | none | none | none | `<root>/scripts/<entry>` | none |
| reasonix | `~/.reasonix` | `<root>/skills/<name>`, mode; support copy | none | none | `<root>/hooks/<allowlisted>` + `hooks/lib` | `<root>/scripts/<entry>` | `settings.json`: external |
| antigravity | `~/.gemini` | `<root>/skills/<name>`, mode | `<root>/agents/<entry>`, mode | none | `hooks`, whole-dir entry | `scripts`, whole-dir entry | `config/hooks.json`: external |

Allowlists:

- Codex hooks: `scripts/codex-hooks-allowlist.txt`, rendered to `hooks.json`; `config.toml` gets `[features] hooks = true`.
- Factory hooks: the repo `.claude/settings.json` hooks with `~/.claude/` rewritten to `~/.factory/`.
- Reasonix hooks: `scripts/reasonix-hooks-allowlist.txt`, which also selects the mirrored hook files.
- Antigravity hooks: `scripts/agy-hooks-allowlist.txt`, rendered via `scripts/generate-agy-hooks-json.py` and `hooks/agy-hook-adapter.py` to `~/.gemini/config/hooks.json`.

A target other than claude is planned only when its root dir exists (`--target all`).

## Hook interpreter

Hooks need Python 3.10+. Under 3.9 they crash at import with exit 1, and Claude Code blocks only on exit 2, so a safety gate would fail open. Three layers prevent that (`scripts/vexinstall/interp.py`, `hooks/lib/pyrun.sh`, `scripts/hook-pyguard.py`):

- **Link.** `apply` resolves one interpreter and points `~/.claude/vexjoy/bin/python3` at it. Order: `$VEXJOY_PYTHON`, `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`, `/usr/bin/python3`, then `python3` and `python3.N` on `PATH`, then the interpreter running the engine. Each candidate is run to read its version and whether it is a venv.
  - Shims (`/shims/`) and venvs are never linked.
  - Versioned dirs (pyenv, asdf, mise, uv, rye, checked on the path and its realpath; Homebrew `Cellar`, checked on the literal path only) are used only when nothing stable qualifies.
  - No 3.10+ found, or a regular file or non-dir in the way at `~/.claude/vexjoy/bin`: `apply` exits 1 before any write.
  - `sync` probes the link each run and re-resolves it when it is missing, dangling, broken, or older than 3.10. It never fails. `uninstall` trashes the link.
- **Launcher.** Every repo hook command has this form, and the engine copies it unchanged into `~/.claude`, every profile, and (with `~/.factory/` paths) Factory:

  ```sh
  sh "$HOME/.claude/hooks/lib/pyrun.sh" "$HOME/.claude/hooks/<file>.py"
  ```

  `pyrun.sh` runs the link, else the first `python3.14`…`python3.10` on `PATH`, `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`, then `python3`, skipping shims. The command string holds no machine path on purpose: Claude Code dedupes hooks by exact command string across project and user settings, and differing strings run every hook twice in repo sessions. Its first path sits inside `hooks/`, so every engine version owns the entry, older ones included: an older engine or a revert replaces the 70 entries instead of adding 70 duplicates. The command needs no shell syntax beyond quoting, so it also works in fish.
- **Guard.** Every registered hook starts with a version check that runs before any other import and parses on 3.8+. Under <3.10 it first re-execs the hook once under a `python3.1x` found on `PATH`, `/opt/homebrew/bin`, `/usr/local/bin`, or `/usr/bin`. That keeps a session working while its settings still say bare `python3` (an upgrade before the first sync) and lets the sync hook repair the link. With none found:
  - Gates (PreToolUse hooks that deny, `GATES` in `scripts/hook-pyguard.py`) exit 2 with a one-line message to run `./install.sh` from a terminal outside Claude Code.
  - Every other hook exits 0 with the same line on stderr. Stop and SubagentStop hooks stay advisory, because exit 2 there makes the model keep going.
  - `codex-hook-adapter.py` exits 2 only for `--failure-policy closed`.

  Every guarded file must also parse with the 3.8 grammar: a 3.10-only construct (`match`) is a SyntaxError on 3.9 before the guard runs. Stamp a new hook with `python3 scripts/hook-pyguard.py --apply --file hooks/<file>.py`; `register-hook.py add` refuses an unguarded hook. CI runs `hook-pyguard.py --check`.
- **Doctor.** `doctor` reports `python-pin-missing`, `python-pin-dangling`, `python-pin-not-link`, `python-pin-broken`, or `python-pin-old` (error).

Runtime scope:

| Target | Launcher | Guard | Why |
|---|---|---|---|
| claude + profiles | yes | yes | verified `/bin/sh -c` |
| factory | yes, `~/.factory/hooks/lib/pyrun.sh` | yes | plain `sh "<path>" "<path>"`, valid in any shell |
| codex | no, bare `python3` | adapter + hooks | Codex stores a trusted hash per hook command in `config.toml`, so a new string forces re-approval of every hook. Cost: when the first `python3` on `PATH` is 3.9 and no `python3.1x` exists, every `failure=closed` gate denies every call even though the link works. With a `python3.1x` present, the adapter re-execs and runs normally. |
| reasonix | no, bare `python3` | yes (advisory hooks only) | non-tool hooks only; the re-exec covers 3.9 |
| hermes | none | n/a | no hooks |

Residual: no 3.10+ anywhere and no `python3` exits 127, which fails open. Windows has no `sh` and is out of scope.

After pulling this change, run `./install.sh` once: until the first new-engine sync, repo sessions see the launcher in project settings and bare `python3` in user settings, so each hook runs twice for that session.

## Account profiles

Claude Code reads hooks from the `settings.json` of the config dir it runs with. A `CLAUDE_CONFIG_DIR` profile with no registrations runs no toolkit hooks outside the repo. When the claude target is applied (`apply` or `sync`), the engine handles each profile in `~/.claude-accounts/accounts.json` (`scripts/manage-accounts.py`) after `~/.claude`:

- Links `skills`, `agents`, `commands`, `hooks`, and `scripts` to the `~/.claude` entries when the profile has none. A real dir or a link elsewhere is reported (`doctor`: `account-link-conflict`) and left alone.
- Merges the toolkit-owned hook registrations into the profile's `settings.json` with the same owner rule as `~/.claude/settings.json`. Env, auth, model, permissions, plugins, MCP servers, and non-owned hooks stay as they are. Env vars from the repo settings are not added to profiles.
- Copies the old file to `~/.claude/vexjoy/backups/<name>-settings.<ts>.json` before a write (newest 10 kept). `restore-settings` does not cover profiles; copy the backup back by hand.

`plan` prints one `account <name>: links +N, hooks missing=M stale=S` line per profile. `doctor` reports `account-hooks-drift` (error) when `missing` or `stale` is not 0. `uninstall` removes the owned registrations from profiles and keeps the links.

## Operations

| Task | Command |
|---|---|
| Write overlays from the legacy private roots | `./install.sh --migrate-overlays` |
| Preview | `./install.sh --dry-run` or `vexinstall plan --dry-run --takeover --target all` |
| Install or repair | `./install.sh` (`vexinstall apply --takeover`) |
| Pick the hook python | `VEXJOY_PYTHON=/abs/python3 ./install.sh` |
| Roll back the last apply | `./install.sh --rollback` (`restore-settings` + `restore-trash` with the newest ts) |
