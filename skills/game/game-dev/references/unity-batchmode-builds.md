# Unity batch-mode builds and tests

Build, compile-check, and test a Unity project without the Editor UI, through the `unity` CLI or classic `Unity.exe -batchmode`. Field-tested on 2026-11-07 on Windows 11 with Unity 6000.6.0f1 and `unity` 1.0.0-beta.6, against a copy of a real project.

## Pick the tool

| Situation | Use |
|---|---|
| Desktop player build (Windows, macOS, Linux) of the enabled scenes in Build Settings | `unity build <project> --target StandaloneWindows64 -o <path>` |
| Android, iOS, or WebGL player build | `unity build <project> --profile <name>` (Unity 6 build profile), or `--target <target> --execute-method <Class.Method>` |
| The project already has a build method (`BuildPipeline.BuildPlayer` in an `Editor` folder) | `unity build --target <target> --execute-method <Class.Method>`, or `unity run -- -executeMethod <Class.Method>` |
| The method renders, captures screenshots, bakes on the GPU, or needs a graphics device | `unity run`, or classic `Unity.exe`. `unity build` adds `-nographics`. |
| Compile check | `unity run <project> --timeout 600 -- -logFile <log>`, or classic `Unity.exe` without `-executeMethod` |
| EditMode or PlayMode tests | `unity test`. The project needs the `com.unity.test-framework` package. |
| No `unity` CLI on the machine, or you need exact Editor flags | Classic `Unity.exe -batchmode` |

Both routes start the same Editor, use the same license, and take the same project lock.

## What the CLI passes to the Editor

Observed in each run's log:

| CLI command | Editor arguments |
|---|---|
| `unity build P --target StandaloneWindows64 -o X.exe` | `-batchmode -nographics -quit -projectPath P -buildTarget StandaloneWindows64 -buildWindows64Player X.exe -logFile <log> -hubSessionId <id>` |
| `unity run P -- <args>` | `-batchmode -quit -projectPath P <args> -hubSessionId <id>` |
| `unity test P --mode EditMode --output R.xml` | `-batchmode -runTests -projectPath P -testResults R.xml -testPlatform EditMode -hubSessionId <id>` |

- `unity run` checks forwarded arguments before launch. A forwarded `-batchmode` failed in 0 s with exit 6 (`conflicts with a reserved Unity flag`). Unity's agent skill lists `-quit`, `-projectPath`, `-useHub`, and `-hubIPC` as reserved too. Forward `-executeMethod`, `-logFile`, `-nographics`, and other flags after `--`.
- The CLI reads the Editor version from `ProjectSettings/ProjectVersion.txt`. `--editor-version <version>` or `-e <path to Unity.exe>` overrides it, and `--allow-install` installs a missing Editor.

## Build with `unity build`

```bash
unity build <project> --target StandaloneWindows64 -o <out>/Game.exe \
  --log-file <out>/build.log --no-tail --timeout 1800 --format ndjson
```

- Without `--execute-method` or `--profile`, the CLI uses the legacy desktop player flags. That path takes desktop targets only, builds the enabled scenes in `ProjectSettings/EditorBuildSettings.asset`, and requires `-o`. Android, iOS, and WebGL need `--profile` or `--execute-method` (docs).
- `--profile <name or path>` builds a Unity 6 build profile from `Assets/Settings/Build Profiles`. The profile sets the target.
- With `--execute-method`, the CLI forwards `-o` as `-buildOutput`, and your method must read it.
- The default log is `<project>/Logs/build-<target>-<timestamp>.log`. It also streams to the console unless you pass `--no-tail` or `--quiet`, or use `--format ndjson`.
- A provenance manifest, `<output name>.provenance.json`, lands beside the build output. It records the outcome, exit code, Editor version and changeset, git revision, a `dirty` flag, and package versions. `--no-provenance` skips it.
- `--versioning-strategy` and `--build-version` apply only with `--execute-method`. Otherwise beta.6 warns and ignores them.
- The uncommitted-changes guard belongs to versioning. With `--versioning-strategy semantic`, `tag`, or `custom`, a dirty tree is rejected unless you pass `--allow-dirty-build` (docs). A built-in build of a tree with a modified tracked file went ahead in beta.6, and the manifest recorded `"dirty": true`.
- Android targets take `--android-export-type apk|aab|android-studio-project` and keystore flags. Passwords passed as flags land in shell history and CI logs, so read them from CI secrets.
- Timing on the test machine: the first open of a 158 MB project spent 42 s importing assets, and warm rebuilds took 8 to 12 s.

## Build with classic `Unity.exe`

```powershell
& "C:\Program Files\Unity\Hub\Editor\<version>\Editor\Unity.exe" -batchmode -quit -projectPath "<project>" -executeMethod <Class.Method> -logFile "<log>"
```

- Find `Unity.exe` with `unity editors -i --json` (`data[].location`). The command uses the Hub's default location.
- `-noaudio`, seen in some scripts, is not in the Unity 6 manual's Editor arguments. Unity ignores unknown flags and passes them through to `Environment.GetCommandLineArgs()`.
- For a compile check, omit `-executeMethod`, then search the log for `error CS`. Compile errors end with `Scripts have compiler errors.` and exit code 1.
- Without `-logFile`, Unity 6.6 writes a short header to `%LOCALAPPDATA%\Unity\Editor\Editor.log`, then moves the rest to `<project>/Logs/Editor.log`.
- In Git Bash, quote paths that contain spaces. Unity accepts forward slashes in its arguments.
- Exit codes: 0 for success; 1 for compile errors or a project lock (seen), and for an exception in the build method (Unity manual); 198 for a license failure (seen; see `unity-licensing.md`).

## Make a build method fail loudly

`BuildPipeline.BuildPlayer` returns a report instead of throwing. A method that ignores the report exits 0 after a failed build. Throw when the result is not `Succeeded`; per the Unity manual, an exception from `-executeMethod` makes Unity exit 1. Read the output path from `-buildOutput`, which `unity build -o` forwards:

```csharp
// Assets/Editor/CiBuild.cs (an Editor folder keeps it out of the player)
using System;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;

public static class CiBuild
{
    public static void Windows()
    {
        string[] args = Environment.GetCommandLineArgs();
        int i = Array.IndexOf(args, "-buildOutput");
        string output = i >= 0 && i + 1 < args.Length ? args[i + 1] : "Build/Windows/Game.exe";
        var report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = EditorBuildSettings.scenes.Where(s => s.enabled).Select(s => s.path).ToArray(),
            locationPathName = output,
            target = BuildTarget.StandaloneWindows64,
        });
        if (report.summary.result != BuildResult.Succeeded)
            throw new Exception($"Build {report.summary.result}");
    }
}
```

`EditorApplication.Exit(1)` also works when the method has cleanup to finish first.

## Run tests

```bash
unity test <project> --mode EditMode --output <out>/editmode.xml --timeout 900 --format ndjson
```

- Check `Packages/manifest.json` for `com.unity.test-framework` first. Without it, the Editor loaded the project and then idled until `--timeout` ended the run: exit 6, `TEST_TIMED_OUT`, no report.
- Always pass `--timeout`, because the CLI sets none by default.
- Exit 8 means tests failed, so stop. Exit 6 means the run did not finish. Fix the cause first (missing test framework, compile errors, project lock, license), because an unchanged rerun fails the same way. Retry exit 7 unchanged.
- beta.6 `unity test` has no log flag and passes no `-logFile`. The Editor log lands in `<project>/Logs/Editor.log`.
- Reports are NUnit XML by default. For JUnit, pass `--report-format junit`, or `--report-format nunit,junit` with `--junit-output <path>`.
- Other flags: `--filter <pattern>`, `--shard N/M`, `--retries <n>`, `--rerun-failed`, and `--coverage`, which needs the Code Coverage package.

## Parallel builds and the project lock

Unity allows one Editor process per project folder. A second batch run on an open project exits 1 with `Multiple Unity instances cannot open the same project.` Through `unity run`, that shows as exit 6, `COMMAND_FAILED`. The user's own open Editor holds the lock too.

- Check first with `unity editors running --json`, which lists running Editors and their projects.
- For parallel builds, give each run its own project copy and its own output folder. Copy `Assets`, `Packages`, and `ProjectSettings`, plus `Library` to skip the reimport. One git worktree per build also works.
- A leftover `Temp/UnityLockfile` from a killed run did not block the next run. Only a live Editor holds the lock.
- Killing the `unity` CLI, for example with `timeout`, also stopped its Editor child in beta.6, so no orphan process kept the lock.

## Windows and shared desktops

- Batch runs open no Editor window. On the test machine they still brought Unity windows to the front of the user's screen, and the cause was not isolated. Before you launch Unity on a desktop someone is using, tell them. Group the runs instead of probing one flag at a time.
- `unity open --wait` is unsupported on Windows and exits 2 (docs).
- `unity doctor` warns when Windows long-path support is off, because deep paths can hit the 260-character limit. Keep project and output paths short.
- Editor installs ask for UAC elevation. `--no-elevate` skips the CLI's elevation helper; the docs add `UNITY_NO_ELEVATE=1`.
- Windows has no pager by default, so pass `--no-pager` or set `UNITY_NO_PAGER=1`.
