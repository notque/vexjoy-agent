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
| Skill precedence is enterprise > personal > project. A project skill with the same name as a personal skill shadows it. | Documented | `doctor` reports a name in both `~/.claude/skills` and a project `.claude/skills` as `duplicate-skill-name` (error). |
| Plugin skills are namespaced `<plugin>:<skill>`, so they never collide with a bare name. | Documented | `doctor` reports a bare name also shipped by an enabled plugin as `plugin-bare-name` (warn, routing ambiguity only). |
| A skill and a command with the same name: the skill wins. | Documented | `plan` skips the command and lists it in `shadowed_commands`. `doctor` flags a leftover command file. |
| Agent dirs are scanned recursively. Project `.claude/agents` beats personal `~/.claude/agents`. | Documented | Agents install as per-file entries in a real `agents/` dir, never a whole-dir link. `doctor` flags a whole-dir `agents` link (error) and project-scope agent duplicates (warn). |
| Nested `<subdir>/.claude/skills` dirs are discovered. | Documented | `doctor` lists every nested `.claude/skills` or `.claude/agents` under the repo, including `.claude/worktrees/*/.claude/...`, as `project-scope-nested-source` (warn), and names found there that are also installed as `duplicate-skill-name` (error). |
| A symlinked skill dir under `~/.claude/skills` loads. | Undocumented; observed working | Symlink mode depends on it. Copy mode (`apply --mode copy`) builds the same shape without links if this ever breaks. |
| Nested dirs in the personal skills root (`~/.claude/skills/<cat>/<name>`) load as skills. | Undocumented | Not relied on. Every skill installs flat as `skills/<name>`. A category dir or link in a flat root is a `doctor` error. |
| Unknown keys inside a hook entry in `settings.json` are accepted. | Undocumented | Not relied on. Owned hook entries carry no marker key. Ownership comes from the command path (spec 10) and the ledger hashes. |
| Stray non-skill dirs in a skills root (no `SKILL.md`) are ignored. | Undocumented | Only `SUPPORT_DIRS` are installed there. `doctor` warns on any other non-skill dir. |

## Shared rules

- **Flat names.** `skills/<category>/<name>` installs as `<name>`. `scripts/validate-skill-names.py` fails CI when two public skills share a name. Overlay entries may add a prefix, such as `voice-`.
- **One owner per name.** Overlays never replace public entries, and an `overrides` key in `overlays.json` is rejected. A collision makes `plan` and `apply` exit 3. `sync` leaves that one name as it is on disk and warns.
- **Support dirs** (`SUPPORT_DIRS`): `shared-patterns`, `kb`, `voice-shared`. These install next to skills and have no `SKILL.md`.
- **Data dirs** (`DATA_DIRS`): `reddit-data`, `synced`. Other tools write these under a skills root. The engine never installs, adopts, or removes them, and `doctor` names them as runtime data dirs.
- **Mode.** Symlink mode is the default for a main git checkout outside `/tmp`. Copy mode is used otherwise. Copy and symlink modes produce the same shape. The ledger records the mode, and only `apply --mode` changes it.
- **State.** `~/.claude/vexjoy/`: `ledger.json`, `overlays.json`, `reports/`, `backups/`, `trash/`, `lock`.
- **Installed indexes.** `~/.<target>/vexjoy/index/{skills,agents}.json` (public + overlays). Readers find them through `resolve_index(kind, target)` in `scripts/routing_index_merge.py`: `$VEXJOY_INDEX_DIR`, then the installed index, then the repo public index (plus a legacy `INDEX.local.json` if one exists).
- **Repo guard.** No engine write may resolve inside the repo or an overlay root. A write that would triggers exit 4. Every command also refuses up front (exit 4) when the state dir or any target root resolves inside the repo, for example `HOME` set to the checkout.
- **Takeover** (`apply --takeover`, never `sync`). An unowned entry at a desired dest (stale copy, foreign link, or a linked container dir) moves to trash and is replaced. The report lists it under `taken_over`; `restore-trash <ts>` undoes it. Unowned entries at other names are left alone. Takeover containers do not count toward the mass-removal cap.

## Per-target layout

"mode" means the entry follows the install mode (symlink or copy). "external" means the engine generates the whole file (`scripts/vexinstall/external.py`), writes it only when bytes change (mode 600), keeps non-`hooks` keys, drops profile-disabled hooks, and backs up the old file to `~/.claude/vexjoy/backups/<target>-<file>.<ts>`.

| Target | Root | Skills (+ support) | Agents | Commands | Hooks | Scripts | Settings |
|---|---|---|---|---|---|---|---|
| claude | `~/.claude` | `skills/<name>`, mode | `agents/<entry>`, mode | `commands/<name>.md`, mode | `hooks`, whole-dir entry | `scripts`, whole-dir entry | `settings.json`, owned entries merged |
| codex | `~/.codex` | `skills/<name>`, copy; support copy | `agents/<entry>`, copy | none | `hooks/<entry>` + `hooks/lib/<entry>` | `scripts/<entry>` | `hooks.json`, `config.toml`: external |
| factory | `~/.factory` | `skills/<name>`, mode | `droids/<entry>`, mode | `commands/<name>.md`, mode | `hooks`, whole-dir entry | `scripts`, whole-dir entry | `settings.json`: external |
| hermes | `~/.hermes` | `skills/<name>`, mode | none | none | none | `scripts/<entry>` | none |
| reasonix | `~/.reasonix` | `skills/<name>`, mode; support copy | none | none | `hooks/<allowlisted>` + `hooks/lib` | `scripts/<entry>` | `settings.json`: external |

Allowlists:

- Codex hooks: `scripts/codex-hooks-allowlist.txt`, rendered to `hooks.json`; `config.toml` gets `[features] hooks = true`.
- Factory hooks: the repo `.claude/settings.json` hooks with `~/.claude/` rewritten to `~/.factory/`.
- Reasonix hooks: `scripts/reasonix-hooks-allowlist.txt`, which also selects the mirrored hook files.

A target other than claude is planned only when its root dir exists (`--target all`).

## Operations

| Task | Command |
|---|---|
| Write overlays from the legacy private roots | `./install.sh --migrate-overlays` |
| Preview | `./install.sh --dry-run` or `vexinstall plan --dry-run --takeover --target all` |
| Install or repair | `./install.sh` (`vexinstall apply --takeover`) |
| Roll back the last apply | `./install.sh --rollback` (`restore-settings` + `restore-trash` with the newest ts) |
