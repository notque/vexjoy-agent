# Installer layout contract

This page is the layout contract for the `vexinstall` engine (`scripts/vexinstall/`). The engine installs each runtime from this contract, and `vexinstall doctor` checks it.

- Engine CLI: `PYTHONPATH=<repo>/scripts python3 -m vexinstall <plan|apply|sync|doctor|uninstall|repair-repo|prune|restore-trash|restore-settings|migrate-overlays>`
- Callers: `install.sh` (runs `apply`, takeover on), the SessionStart hook `hooks/sync-to-user-claude.py` (runs `sync --target all`, fail-open), and the `post-merge` git hook that `install.sh` writes (runs `sync --target all` after each merge, `git pull` included). No other code writes a runtime root.
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

## Verified Cline behavior

Checked against [Skills](https://docs.cline.bot/customization/skills).

| Fact | Status | What the engine does about it |
|---|---|---|
| Cline reads skills from `~/.cline/skills/<name>/SKILL.md`. | Documented | `adapter.skills="skills"` installs skills at `root/skills/<name>`. |
| No `settings.json` equivalent for hooks; hooks are SDK/plugin-only. | Documented | No hook entries are written. |
| Dirs without `SKILL.md` (support dirs) are ignored by Cline. | Documented | `adapter.no_support=True` — `desired_for` skips `pub.support` for this target. |

## Shared rules

- **Flat names.** `<root>/skills/<category>/<name>` installs as `<name>`. `scripts/validate-skill-names.py` fails CI when two public skills share a name. Overlay entries may add a prefix, such as `voice-`.
- **One owner per name.** Overlays never replace public entries, and an `overrides` key in `overlays.json` is rejected. A collision makes `plan` and `apply` exit 3. `sync` leaves that one name as it is on disk and warns.
- **Support dirs** (`SUPPORT_DIRS`): `shared-patterns`, `kb`, `voice-shared`. These install next to skills and have no `SKILL.md`.
- **Data dirs** (`DATA_DIRS`): `reddit-data`, `synced`. Other tools write these under a skills root. The engine never installs, adopts, or removes them, and `doctor` names them as runtime data dirs.
- **Mode.** Symlink mode is the default for a main git checkout outside `/tmp` on Linux and macOS. Copy mode is the default everywhere else, including on Windows. There, a symlink needs Developer Mode (error 1314 without it). `os.readlink` also returns the link with an extended-path prefix that never matches the source, and `os.replace` cannot swap a dir link. So a link install on Windows would fail on every run after the first. Copy and symlink modes produce the same shape. The ledger records the mode, and only a run with `--mode` changes it (`./install.sh --copy` or `--symlink`). A Windows install whose ledger says symlink gets the hint to run `./install.sh --copy` whenever an entry fails.
- **State.** `~/.claude/vexjoy/`: `ledger.json`, `overlays.json`, `reports/`, `backups/`, `trash/`, `lock` (`fcntl.flock`, or `msvcrt.locking` on Windows), `bin/python3`.
- **Replace.** A replace works in this order:
  1. It stages the new copy or link beside the dest.
  2. It records the move in the trash manifest.
  3. It moves the old entry to trash.
  4. It renames the staged entry into place.
  5. For a copy, it moves the old copy's `node_modules` dirs into the new one (see **npm dependencies**).

  A dir such as `~/.claude/hooks` is missing only between the two renames. If the staged entry cannot be placed, the old entry comes back out of trash. If that also fails, the error says where in trash the old entry is, and the next run installs the entry again. A move that fails or is undone leaves no record behind, and a trash session left empty is removed. So the rollback point a run records never names an empty session. An entry recorded inside a dir that the run replaces never moves on its own: it goes to trash inside the old dir, and its record goes once the new dir is in place.
- **npm dependencies.** The engine never copies or hashes `node_modules` (`IGNORE_NAMES`). `./install.sh` runs `npm ci` in the repo's `scripts/jev_gateway` and in each copied one under `~/.claude`, `~/.codex`, `~/.factory`, `~/.hermes`, and `~/.reasonix`. A copy-mode replace swaps a whole entry: `<root>/scripts` after any change under `scripts/` for a whole-dir target, or `<root>/scripts/jev_gateway` after a change there for a per-entry target. Once the new copy is in place, the replace moves each `node_modules` dir of the old copy, now in trash, into the same dir of the new copy (`fsops.carry_node_modules`). The Jev gateway keeps its dependencies across pulls, so `/d` keeps working without another `./install.sh` until `package-lock.json` changes.
  - A dir moves only from a dir physically inside the old copy into one physically inside the new copy, never through a link or junction. The `node_modules` behind a link install belongs to the checkout.
  - The new copy must still ship that package's `package.json` and a byte-identical `package-lock.json`, so a `node_modules` always matches the lock beside it, as `npm ci` leaves it. After a lock change, the dir stays in trash with the old copy, and `apply` and `sync` warn: `<dir> not carried over: package-lock.json changed; run ./install.sh (old one: <path in trash>)`. A package that left the repo leaves its dir in trash without a warning.
  - A dir that cannot move also stays in trash, and the warning says where. `sync` never runs `npm ci`: it must finish inside the 18 s SessionStart timeout.
  - `rollback` and `restore-trash` move the `node_modules` dirs of each engine entry they displace into the entry restored in its place, by the same rules. A restored copy gets back the dependencies it had: its own when the lock had changed, else the ones the replace moved out.
  - The report lists each move under `node_modules`. A moved dir never reads as a user edit, because the copy hash skips `node_modules`.
- **Busy paths.** Windows refuses to rename a dir while another process holds a file in it open or works inside it, such as a running hook, a virus scanner, or a terminal. It also refuses to replace a file another process has open. Engine renames and file replaces retry these errors (5 and 32) for about 3 s.
- **Failed entries.** An entry that still fails stays as it was and keeps its ledger record, and the rest of the run goes on.
  - A target with a failed entry keeps its settings and hook registrations (`settings.json`, profile settings, external hook configs) as they were. A registration must never point at a hook file that did not install.
  - The run saves the ledger even when something stops it early, Ctrl-C included, because the ledger holds only finished steps.
  - The run names each failed entry, up to five, and the report lists all of them. `apply` exits 1, `sync` warns, and the next run tries the entry again.
- **Installed indexes.** `~/.<target>/vexjoy/index/{skills,agents}.json` (public + overlays). Readers find them through `resolve_index(kind, target)` in `scripts/routing_index_merge.py`: `$VEXJOY_INDEX_DIR`, then the installed index, then the repo public index (plus a legacy `INDEX.local.json` if one exists).
- **Repo guard.** No engine write may resolve inside the repo or an overlay root. A write that would triggers exit 4. Every command also refuses up front (exit 4) when the state dir or any target root resolves inside the repo, for example `HOME` set to the checkout.
- **Legacy git hook.** The pre-engine `install.sh` wrote a `post-merge` that linked repo items into each runtime root after every pull. Under Git Bash without symlink privilege, `ln -s` made copies, which the engine treats as user edits and stops updating. An apply run of `./install.sh` (not `--dry-run`, `--configure-only` or `--uninstall`) writes its git hooks before it checks Python or runs `apply`. It replaces a hook marked `Written by vexjoy-agent` in the main checkout's `.git/hooks`, even when the install then fails. `doctor` (`legacy-git-hook`, error) and the SessionStart sync (one `[sync] warning` line, in worktree sessions too) report a legacy hook in the hooks dir git uses (`core.hooksPath`, else `git rev-parse --git-path hooks`). Neither rewrites it (repo guard). To fix one, delete it, or remove its `ln -s` loop if the file also runs your own hooks. The pre-engine installer wrote `.git/hooks/post-merge` under whatever directory it ran from, so check other clones too: `grep -l 'auto-syncs new items' <clone>/.git/hooks/post-merge`.
- **Uninstall and git hooks.** `./install.sh --uninstall` with no `--target`, or with `--target claude`, renames `post-merge` in the main checkout's `.git/hooks` to `post-merge.vexjoy-removed.<UTC time>`, which git never runs, when the file carries `Written by vexjoy-agent`. The engine's own `sync` skips uninstalled targets (see **Uninstall record**), but a pre-engine hook's `ln -s` loop, or an engine from a clone older than that record, would re-install everything on the next pull. The rename runs before the Python check and `vexinstall uninstall`, so a failed engine run does not stop it. A failed rename makes the uninstall exit 1. Run from a linked worktree, it finds the main checkout's `.git` with `git rev-parse --git-common-dir`, because git runs those hooks for merges in every worktree; when git cannot read `.git`, the uninstall exits 1 and says to run it in the main checkout. Git hooks belong to the checkout, not to `HOME`, so a run with a temporary `HOME` still renames the real hook: set `VEXJOY_NO_GIT_HOOKS=1` for such runs. It keeps unmarked hooks, and it keeps `pre-commit`: the private-leak gate blocks commits that carry private overlay data and installs nothing. An uninstall with any other `--target` keeps `post-merge` too: its `sync --target all` skips the uninstalled target and keeps claude and the rest current. `--dry-run` only reports, and `VEXJOY_NO_GIT_HOOKS=1` skips the step. `--rollback` of an uninstall writes the hook back in a main checkout (from a linked worktree it skips git hooks: run `./install.sh` in the main checkout).
- **Uninstall record.** `vexinstall uninstall` records each target it uninstalled, with the UTC time, under `uninstalled` in `ledger.json`. `sync` skips a recorded target, whether named or picked up by `--target all`, and prints one `[sync] warning: skipped uninstalled target(s) ...` line naming them. So neither the SessionStart sync hook, nor a `post-merge` hook in any clone, nor a later `sync --target all` brings an uninstalled target back. A `--target all` uninstall (install.sh's default) records every target the engine knows, not only the runtime dirs present, so a runtime dir created later is skipped too. An `apply` clears the record of each target it runs for, and `apply --target all` (`./install.sh`) clears all of them. `--rollback` of an uninstall puts the trashed files and settings.json back but keeps the record, and leaves the runtime configs below as the uninstall left them; run `./install.sh` to have the engine own and update the target again.
- **Uninstall and runtime configs.** Besides `~/.claude/settings.json` and account profiles, `uninstall` removes the owned hook entries from the runtime configs apply writes through `external`: codex `hooks.json`, factory and reasonix `settings.json`, and antigravity `~/.gemini/config/hooks.json`. An entry is owned under the `settings.json` rule: its first path is inside `<root>/hooks`, the repo's `hooks/`, or a legacy toolkit path. Other keys and entries stay, a matcher block or event emptied by the removal goes, and an antigravity group left with no events goes. A file with nothing owned in it is not rewritten; a changed one is backed up first, as apply does. An unreadable file is left as is with one `[uninstall] warning` line. Codex `config.toml` stays as it is: it holds the hooks feature flag, not hook entries, and turning the flag off would also stop the user's own hooks.
- **Takeover** (`apply --takeover`, never `sync`). An unowned entry at a desired dest (stale copy, foreign link, or a linked container dir) moves to trash and is replaced. The report lists it under `taken_over`; `restore-trash <ts>` undoes it. Unowned entries at other names are left alone. Takeover containers do not count toward the mass-removal cap.
- **Hook profile switch.** One whole-dir entry cannot leave a file out. So while the install profile (`.local/profile.yaml`, or `$VEXJOY_INSTALL_PROFILE`) disables a hook, the claude, factory and antigravity `hooks` entry installs per-entry in a real `hooks` dir, and clearing the profile turns it back into one entry. None of the removals below count toward the mass-removal cap.
  - To per-entry, symlink mode: the whole-dir link goes to trash, and the run links each enabled hook into a new real dir.
  - To per-entry, copy mode: the dir stays where it is, and its files become per-entry entries. A file the repo has changed since the last run is replaced. Only the disabled hooks and what the per-entry layout skips (`hooks/tests`) go to trash. A copy you edited stays as it is (`skip`), as any user-edited copy does.
  - Back to one entry: the whole-dir entry replaces the dir, and the per-entry entries go to trash inside the old dir. A user edit inside (`skip`) keeps the per-entry hooks, takeover included. A file no entry owns (`blocked`) keeps them until you move it or run `./install.sh`, which takes over.

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
| cline | `~/.cline` | `<root>/skills/<name>`, mode; no support dirs | none | none | none | none | none |

Allowlists:

- Codex hooks: `scripts/codex-hooks-allowlist.txt`, rendered to `hooks.json`; `config.toml` gets `[features] hooks = true`.
- Factory hooks: the repo `.claude/settings.json` hooks with `~/.claude/` rewritten to `~/.factory/`.
- Reasonix hooks: `scripts/reasonix-hooks-allowlist.txt`, which also selects the mirrored hook files.
- Antigravity hooks: `scripts/agy-hooks-allowlist.txt`, rendered via `scripts/generate-agy-hooks-json.py` and `hooks/agy-hook-adapter.py` to `~/.gemini/config/hooks.json`.

A target other than claude is planned only when its root dir exists (`--target all`).

## Hook interpreter

Hooks need Python 3.10+. Under 3.9 they crash at import with exit 1, and Claude Code blocks only on exit 2, so a safety gate would fail open. Three layers prevent that (`scripts/vexinstall/interp.py`, `hooks/lib/pyrun.sh`, `scripts/hook-pyguard.py`):

- **Link.** `apply` resolves one interpreter and points `~/.claude/vexjoy/bin/python3` at it. Order: `$VEXJOY_PYTHON`, `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`, `/usr/bin/python3`, then `python3` and `python3.N` on `PATH`, then the interpreter running the engine. Each candidate is run to read its version and whether it is a venv.
  - Version-manager shims (`/shims/`) and venvs are never linked.
  - Versioned dirs (pyenv, asdf, mise, uv, rye, checked on the path and its realpath; Homebrew `Cellar`, checked on the literal path only) are used only when nothing stable qualifies.
  - A host that cannot create a symlink (Windows error 1314 without Developer Mode or the create-symlink privilege, error 50 on a volume without symlinks) gets a script pin instead: an sh file whose line 2 is `# vexjoy-python-shim`, line 3 is `# vexjoy-python-target: <interpreter>`, and line 4 execs that interpreter. `sync`, `doctor`, and the dependency check probe the named interpreter, because Windows cannot run an sh file directly. A script pin stays a script pin; delete it and rerun `./install.sh` to get a symlink once the host allows one.
  - No 3.10+ found, or a foreign file (neither a symlink nor a script pin) or non-dir in the way at `~/.claude/vexjoy/bin`: `apply` exits 1 before any write. Any other error writing the pin makes `apply` exit 1 (`sync` warns) after it writes settings and the ledger; hooks then fall back to `python3` on `PATH`.
  - `sync` probes the pin each run and re-resolves it when it is missing, dangling, broken, or older than 3.10. It never fails. `uninstall` trashes the pin.
- **Launcher.** Every repo hook command has this form, and the engine copies it unchanged into `~/.claude`, every profile, and (with `~/.factory/` paths) Factory:

  ```sh
  sh "$HOME/.claude/hooks/lib/pyrun.sh" "$HOME/.claude/hooks/<file>.py"
  ```

  `pyrun.sh` runs the pin, else the first `python3.14`…`python3.10` on `PATH`, `/opt/homebrew/bin/python3`, `/usr/local/bin/python3`, then `python3`, skipping shims. For a script pin it execs the interpreter named on line 3, and only when that path is absolute and exists, as a dangling symlink fails `-x`, so the fallbacks run and the sync hook can repair the pin; a regular file that names no such interpreter is never run. The command string holds no machine path on purpose: Claude Code dedupes hooks by exact command string across project and user settings, and differing strings run every hook twice in repo sessions. Its first path sits inside `hooks/`, so every engine version owns the entry, older ones included: an older engine or a revert replaces the toolkit's entries instead of adding a duplicate of each. The command needs no shell syntax beyond quoting, so it also works in fish.
- **Guard.** Every registered hook starts with a version check that runs before any other import and parses on 3.8+. Under <3.10 it first re-execs the hook once under a `python3.1x` found on `PATH`, `/opt/homebrew/bin`, `/usr/local/bin`, or `/usr/bin`. That keeps a session working while its settings still say bare `python3` (an upgrade before the first sync) and lets the sync hook repair the link. With none found:
  - Gates (PreToolUse hooks that deny, `GATES` in `scripts/hook-pyguard.py`) exit 2 with a one-line message to run `./install.sh` from a terminal outside Claude Code.
  - Every other hook exits 0 with the same line on stderr. Stop and SubagentStop hooks stay advisory, because exit 2 there makes the model keep going.
  - `codex-hook-adapter.py` exits 2 only for `--failure-policy closed`.

  Every guarded file must also parse with the 3.8 grammar: a 3.10-only construct (`match`) is a SyntaxError on 3.9 before the guard runs. Stamp a new hook with `python3 scripts/hook-pyguard.py --apply --file hooks/<file>.py`; `register-hook.py add` refuses an unguarded hook. CI runs `hook-pyguard.py --check`.
- **Doctor.** `doctor` reports `python-pin-missing`, `python-pin-dangling`, `python-pin-not-link` (a foreign file at the pin path; a script pin is a valid pin), `python-pin-broken`, or `python-pin-old` (error).

Runtime scope:

| Target | Launcher | Guard | Why |
|---|---|---|---|
| claude + profiles | yes | yes | verified `/bin/sh -c` |
| factory | yes, `~/.factory/hooks/lib/pyrun.sh` | yes | plain `sh "<path>" "<path>"`, valid in any shell |
| codex | no, bare `python3` | adapter + hooks | Codex stores a trusted hash per hook command in `config.toml`, so a new string forces re-approval of every hook. Cost: when the first `python3` on `PATH` is 3.9 and no `python3.1x` exists, every `failure=closed` gate denies every call even though the link works. With a `python3.1x` present, the adapter re-execs and runs normally. |
| reasonix | no, bare `python3` | yes (advisory hooks only) | non-tool hooks only; the re-exec covers 3.9 |
| hermes | none | n/a | no hooks |

Residual: no 3.10+ anywhere and no `python3` exits 127, which fails open. On Windows, hooks run only under Git for Windows' `sh`.

**Homes with no launcher.** A home that never ran `./install.sh` has no `~/.claude/hooks/lib/pyrun.sh`. There, `sh` cannot open the launcher, exits 2, and every hook blocks with `sh: 0: cannot open .../pyrun.sh`. The repo's sync hook cannot repair this, because it also runs through the launcher.

A Claude cloud session is always such a home: a fresh VM running as root, where user-level settings do not carry over. The repo handles it with one SessionStart entry that is not a toolkit hook: `sh "$CLAUDE_PROJECT_DIR/scripts/session-bootstrap.sh"` (`scripts/session-bootstrap.sh`).
- **Launcher present:** it exits at once (about 4 ms).
- **Cloud session** (`CLAUDE_CODE_REMOTE=true`): it runs `./install.sh` from the checkout, capped at 200 s inside a 240 s hook timeout (the replay below gets the rest), and logs to `~/.claude/vexjoy/bootstrap.log`. A full install with dependencies takes about 30 s.
  - Claude Code starts every SessionStart hook at once, so the toolkit's other SessionStart hooks fail while the install runs.
  - After the install, `scripts/session-bootstrap-replay.py` runs those hooks again with the same payload and returns their context, plus one status line, as a single SessionStart result.
  - The first prompt waits for SessionStart hooks, so it reaches Claude with hooks working.
- **Local home without a launcher:** it prints one line saying to run `./install.sh` and changes nothing. That includes a home that ran `--uninstall`, or a session in a worktree.
- **Never blocks:** every path exits 0.
- **Repo-only:** `interp.REPO_BOOTSTRAP` names the entry. `settings.drop_repo_only` keeps it out of user settings, account homes and the Factory copy, and `validate-hook-health.py` exempts it from the launcher form. `scripts/tests/test_session_bootstrap.py` covers it.

**Faster cloud start (optional).** Put `./install.sh` in the cloud environment's setup script (the environment settings at claude.ai/code). The setup script runs as root before Claude Code launches and is cached when it finishes in about five minutes. With it, each session finds the launcher already in place: no 30 s install and no SessionStart failures to replay. The install also adds the repo's git hooks to the cloud clone and a block to `~/.bashrc`, the same as a local install.

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
| Switch mode (recorded in the ledger) | `./install.sh --copy`, or `./install.sh --symlink` on Linux and macOS |
| Pick the hook python | `VEXJOY_PYTHON=/abs/python3 ./install.sh` |
| Uninstall | `./install.sh --uninstall`: renames install.sh's `post-merge` hook (no `--target` or `--target claude` only), runs `vexinstall uninstall` (trashes owned entries, removes owned hook registrations, records the targets so `sync` skips them), and removes the no-agent-summary block from `~/.bashrc` |
| Install an uninstalled target again | `./install.sh` or `./install.sh --target <name>` (`apply` clears the uninstall record) |
| Roll back the last apply or uninstall | `./install.sh --rollback` (`vexinstall rollback`: the trash sessions and settings.json backup that run recorded in `~/.claude/vexjoy/rollback.json`; the uninstall record stays until the next `apply`) |
