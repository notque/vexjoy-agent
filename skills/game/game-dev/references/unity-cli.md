# Unity CLI (`unity`)

The `unity` CLI is Unity's standalone command-line tool, in beta (1.0.0-beta releases). It installs Editors and modules, manages projects and licenses, runs batch builds and tests, and drives a running Editor. It replaces the Hub CLI (`"Unity Hub.exe" -- --headless`).

Source tags:

- **(beta.6)**: checked on 2026-11-07 against `unity` 1.0.0-beta.6 `--help` output and real runs on Windows 11 with Unity 6000.6.0f1.
- **(docs)**: from docs.unity.com or Unity's own agent skill, which track the newest CLI (1.0.0-beta.17 on that date). Not run locally.

## Check the version first

Commands and output fields change between betas, so an old CLI fails in ways that look like doc errors.

| Step | Command |
|---|---|
| Installed version | `unity --version` |
| Newest release | `unity upgrade --check --json`, read `data.latestVersion` (beta.6); `unity self-update --check` on newer CLIs (docs) |
| Commands this build has | `unity --help`, then `unity <command> --help` |

When a documented command is missing, the CLI is older than the docs. Report the version gap. Upgrading replaces a binary on the user's machine, so ask first.

## Install and update

```powershell
irm https://unity.com/install.ps1 | iex      # Windows, PowerShell
winget install Unity.CLI                     # Windows, MSIX package
```

```bash
curl -fsSL https://unity.com/install.sh | bash   # macOS, Linux
brew install --cask unity-cli                    # Homebrew
```

- Observed Windows path: `%LOCALAPPDATA%\Unity\bin\unity.exe`. Set `UNITY_CLI_HOME` before running the script to install to `<UNITY_CLI_HOME>\bin`.
- Update: `unity upgrade` (beta.6) or `unity self-update` (docs; `upgrade` stays an alias). beta.6 also has `--target <version>`, `--rollback`, `--channel stable|beta`, and `--dry-run`.
- Homebrew and Linux package installs update through their package manager. A winget install is an MSIX package: `unity self-update` still works, Windows also updates it in the background, and rollback is unavailable.
- Unity Hub installs and updates the CLI itself, with no off switch. `unity config update-check off` silences only the CLI's update notice.

## Run it from an agent

Agent shells start fresh on each call, so set the environment in the same command:

```bash
UNITY_NON_INTERACTIVE=1 UNITY_NO_BANNER=1 UNITY_NO_PAGER=1 unity <command> --json
```

In PowerShell, set `$env:UNITY_NON_INTERACTIVE = '1'` and the other variables first.

- Default output is `human` on a terminal and `tsv` when piped (docs). Pass `--json` or `--format ndjson` every time.
- Error text goes to stderr. In `json` and `ndjson` modes the failed result is also on stdout.
- `--format github` prints failures as GitHub Actions annotations.
- Other variables in beta.6 help: `UNITY_PROJECT_PATH` (default `--project-path`), `UNITY_BUILD_TIMEOUT`, `UNITY_RUN_TIMEOUT`, `UNITY_TEST_TIMEOUT`, `UNITY_EDITOR_VERSION`, and `UNITY_PROXY`.
- From the docs: `UNITY_NO_ELEVATE` (Windows), and `UNITY_SERVICE_ACCOUNT_ID` with `UNITY_SERVICE_ACCOUNT_SECRET` for service-account sign-in. In beta.6, sign a service account in with `unity auth login --client-id <id> --secret-from-stdin`.

## Parse the output

Every result uses one envelope: `{"success", "command", "data", "errors": [{"code", "message"}], "warnings"}`.

| Format | Observed shape (beta.6) | Parse rule |
|---|---|---|
| `--json` | One pretty-printed envelope. `unity build` prints NDJSON progress lines (`{"type":"progress",...}`) before it, and `--quiet` keeps them. | Take the last top-level JSON object on stdout. |
| `--format ndjson` | Progress frames (`{"type":"progress","pct":0,"msg":...}`), then one `{"type":"result",...}` frame. | Take the line whose `type` is `result`. |

Newer CLIs send `--json` progress frames to stderr (docs). The last-object rule works for both.

Branch on the exit code first, then on `errors[0].code`. beta.6 departs from the docs in three places:

- The same failed build reports `COMMAND_FAILED` under `--json` and `BUILD_FAILED` under `--format ndjson`. Both exit 6.
- `unity auth status` with an expired session prints `success: true` and `data.loggedIn: false`, then exits 3. Newer CLIs print `success: false` (docs).
- On a successful build, `data.editorErrors` lists harmless licensing lines as `license-error`. Ignore them when the exit code is 0.

## Exit codes

| Code | Meaning | Retry unchanged |
|---|---|---|
| 0 | Success | n/a |
| 1 | General error | no |
| 2 | Usage error: bad flag, value, or missing argument. Also `unity open --wait` on Windows (docs). | no |
| 3 | Not signed in, expired session, or permission denied | after sign-in |
| 4 | A required setting or context is missing | after setup |
| 6 | Primary operation failed: Editor exited non-zero, compile error, project lock, `--timeout` hit (beta.6) | after fixing the cause |
| 7 | A Unity service was unreachable | yes |
| 8 | `unity test` only: tests ran and some failed | no |
| 130, 143 | Interrupted (Ctrl+C) or terminated (SIGTERM) | yes |

Newer CLIs add 9 `INSTALL_LOCKED`, 10 `READY_TIMEOUT`, 11 `NOT_FOUND`, 12 `EDITOR_UNREACHABLE`, 13 `REMOTE_COMMAND_FAILED`, 14 `TIMEOUT`, 15 `RUN_FAILED`, 16 `JOB_SUSPENDED`, 17 `UNAVAILABLE`, 18 `AWAITING_INPUT`, and 141 `OUTPUT_CLOSED` (docs). Of these, retry 9, 10, 12, 14, 16, 17, and 18 once the cause clears. Treat any other non-zero code as a failure.

The CLI reports its own exit code. The Editor's code appears only in `errors[0].message`, for example `Unity process exited with code 1.` (`unity run`) or `Build failed (exit 1)` (`unity build`).

## Commands verified in beta.6

| Task | Command |
|---|---|
| Installed Editors and their paths | `unity editors -i --json`, read `data[].version` and `data[].location` |
| Folder of one Editor version | `unity editors path <version>` |
| Running Editors and their projects | `unity editors running --json` |
| Install an Editor | `unity install <version> -m <module...> --cm --accept-eula -y` (`--dry-run` previews; `--no-elevate` skips the UAC helper) |
| Add modules | `unity install-modules -e <version> -m <module...>`; `-l` lists them |
| Project facts, no Editor launch | `unity projects info <project> --json`: `version`, `changeset`, `buildTarget`, `renderPipeline`, `scriptingBackend`, `packages` |
| Integrity check, no Editor launch | `unity projects verify <project> --json` (add `--strict`, `--expect-editor <version>`) |
| Install the project's Editor if missing | `unity projects require <project> -y` |
| Disk use and cache cleanup | `unity projects size <project>`, `unity projects clean <project> --dry-run` |
| New project | `unity projects new <name> --path <dir> --editor-version <version> --template <id>` |
| Move a project to another Editor | `unity projects upgrade <project> --to <version>` |
| Player build | `unity build`; see `unity-batchmode-builds.md` |
| Batch run of a C# method | `unity run <project> --timeout <s> -- -executeMethod <Class.Method> -logFile <log>` |
| Tests | `unity test <project> --mode EditMode --output <xml> --timeout <s>` |
| Licenses | `unity license` with `list`, `status`, `activate`, `return`, or `server`; see `unity-licensing.md` |
| Sign-in | `unity auth` with `login`, `status`, `list`, `switch`, `default`, or `logout` |
| Preflight | `unity doctor --ci --json`: blocking `license`, `editor`, `disk-space`, and `network` checks. Run it inside the project folder, or it skips the `editor` check. |
| Hub paths | `unity env --json`: `userDataPath`, `editorInstallPath`, `downloadCachePath`, `configPath` |
| CLI log | `unity logs --tail 50 --level warn`; files are `cli-log.json` and `info-log.json` in `%APPDATA%\UnityHub\logs` |

`projects verify` checks `META_MISSING`, `META_ORPHAN`, `GUID_DUPLICATE`, `CONFLICT_MARKERS`, and `MANIFEST_INVALID`; it runs `EDITOR_VERSION_DRIFT` only with `--expect-editor`.

Point `<project>` at the folder that holds `ProjectSettings/ProjectVersion.txt`. It can sit below the repository root, and the root itself fails with exit 6 (`Not a Unity project`).

## Docs-only commands

Documented on 2026-11-07 but absent from beta.6 `--help`. Confirm with `unity <command> --help` before you use one:

- `self-update`, `close`, `assets`, `recompile [--strict]`, and `watch`.
- `commands --format json` (a machine-readable command manifest) and `commands --grep <term>` (command search).
- `auth consumers`, `auth revoke`, `run --log-file`, and `open --until-ready`.
- `build --list-targets`, `build --list-profiles`, `build --create-profile <target>`, and `build run`.
- The `vcs` group for Git and Unity Version Control: `setup`, `status`, `sync`, `switch`, `doctor --fix`, `merge-setup`, `conflicts`, `explain`, `resolve`, `diff`, `blame`, `summarize`, `affected`, `hooks`, `providers`, `git`, and `uvcs`.

## Drive a running Editor

Editor control runs through the `com.unity.pipeline` package (Unity 6.0+) and its local HTTP API.

| Step | Command |
|---|---|
| Add the package | `unity pipeline install --project-path <project>`. This edits `Packages/manifest.json`, so ask before changing the user's project. |
| Find Editors | `unity status --json`. With none connected, beta.6 exits 6 with `STATUS_NO_INSTANCES`. |
| List an Editor's commands | `unity command --project-path <project>`, or `unity list` |
| Run one | `unity command <name> <args> --project-path <project> --timeout <s>` |
| Long jobs | `unity command <name> --detach`, then `unity job wait <id>` |
| Clients without a shell | `unity mcp` (stdio server) or `unity mcp configure <client>` |

Pass `--project-path` whenever more than one Editor can be open. An Editor whose project has compile errors starts in Safe Mode and never loads the package, so `unity command` cannot connect until the errors are fixed (docs).

## Migrate Hub CLI scripts

| Hub CLI | Unity CLI |
|---|---|
| `"Unity Hub.exe" -- --headless <command>` | `unity <command>` |
| `install --version <version>` | `install <version>` |
| `install-modules --version <version> --module <id>` | `install-modules -e <version> -m <id>` |
| `editors --add <path>` | `editors add <path...>` |
| Plain-text stdout, exit 0 or 1 | TSV when piped, errors on stderr, coded exits |

Removed with no replacement: `--headless`, `--errors`, `--silent`, `--logLevel`, `--bugReporter`, `--debugMode`, `--inspect`, `--userEmail`, `--theme`, `--editorLicense`, `--servicesUrlInterval`, and `--cloudEnvironment`.

## Unity's own agent skill

Unity publishes a `unity-cli` agent skill, a full command reference for the newest CLI, and 35 task skills (URP, UI Toolkit, in-app purchases, multiplayer) at `github.com/Unity-Technologies/skills`. It also ships a Unity plugin for Claude Code, Codex, and Grok.

- `unity skill install --list` shows supported clients and paths. For Claude Code the target is `~/.claude/skills/unity-cli`. `--dry-run` previews and `--local` writes into the project. The embedded copy matches the installed CLI version.
- Installing it adds files to the user's agent setup, so ask first.
- Use that skill for exhaustive command syntax. Use this mode for tool choice, the field-tested beta.6 quirks, batch builds, and license triage.
