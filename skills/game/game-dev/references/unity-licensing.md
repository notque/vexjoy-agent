# Unity licensing in batch mode

Every Editor launch needs a valid license from the Unity Licensing Client. That includes `-batchmode`, `unity build`, `unity run`, and `unity test`. A missing license stops the run before any project code runs. Field-tested on 2026-11-07 on Windows 11 with Unity 6000.6.0f1 and `unity` 1.0.0-beta.6, unless a line says otherwise.

## Two separate states

| State | Check | Needed for |
|---|---|---|
| Editor license (entitlement) | `unity license status --json`, read `data.active` and `data.licenses[].product` | Every Editor launch |
| CLI sign-in | `unity auth status --json`, read `data.loggedIn` and `data.sessionState` | Cloud commands, `unity bug`, and `unity license activate` in its default and `--personal` modes |

The two are independent. On the test machine, `unity auth status` reported `sessionState: expired` and exited 3. At the same time `unity license status` reported Unity Personal active, `unity doctor --ci` passed `LICENSE_OK`, and batch builds succeeded. A signed-out CLI does not block builds; a lapsed license does.

`unity license status` also reports `data.signedIn`, which follows the licensing client's sign-in, not the CLI session: it read `true` while `unity auth status` read `expired`. Check CLI sign-in with `unity auth status` only.

## Preflight

```bash
unity doctor --ci --json      # data.verdict pass or fail; checks license, editor, disk, network
unity license status --json   # data.active must be true
```

Without the CLI, read the entitlement cache at `%LOCALAPPDATA%\Unity\licenses\UnityEntitlementLicense.xml`:

```bash
grep -o '<UpdateDate>[^<]*' "$LOCALAPPDATA/Unity/licenses/UnityEntitlementLicense.xml"
```

`<UpdateDate>` sits 30 days after the last refresh. A refresh at 2026-11-07T16:45Z wrote `2026-12-07T16:45:49Z`. A date in the past means the cache has lapsed.

## Failure signatures

| Signal | Cause | Fix |
|---|---|---|
| Exit code 198. The Editor log shows `No valid Unity Editor license found`, `'com.unity.editor.headless' was not found`, and `Found 0 entitlement groups`. | The Unity Personal entitlement cache lapsed: `<UpdateDate>` is in the past. | Start Unity Hub while signed in. It refreshed the cache within seconds and moved `<UpdateDate>` a month ahead. Then rerun. |
| The same signature with the Hub signed out (not field-tested) | No signed-in user to refresh the entitlement | Ask the user to sign in to the Hub. Or run `unity auth login`, then `unity license activate --personal --accept-eula` after the user agrees to Unity's terms. |
| `unity license status` shows `data.active: false` | No license on the machine | Activate one; see "Activate or return a license". |
| `unity license activate --floating` exits 4 (docs) | No floating license server configured | Run `unity license server list`, then configure the server. |

198 is `Unity.exe`'s exit code. Through the CLI, expect exit 6 with the Editor's code in `errors[0].message`: `Unity process exited with code 198.` from `unity run`, or `Build failed (exit 198)` from `unity build`. That form is inferred from the captured exit-1 messages; a 198 through the CLI was not captured.

These lines are harmless; every successful run on the test machine logged them:

- `[Licensing::Client] Code 10 while verifying Licensing Client signature`
- `[Licensing::Module] LicensingClient has failed validation; ignoring`
- `[Licensing::Module] Error: Access token is unavailable; failed to update`

`unity build` also lists the last two in `data.editorErrors` as `license-error` when the build succeeds. A working license logs `Product: Unity Personal`, `Type: Assigned`, and `Expiration: Unlimited` under `License group`.

The Editor talks to the licensing client that ships with Unity Hub, `C:\Program Files\Unity Hub\UnityLicensingClient_V1\Unity.Licensing.Client.exe`, over a named pipe.

## Activate or return a license

beta.6 flags for `unity license activate`. Pass one mode per call:

| Mode | Command | Sign-in (docs) |
|---|---|---|
| Signed-in user's subscription | `unity license activate` | yes |
| Unity Personal | `unity license activate --personal --accept-eula` | yes |
| Serial: perpetual, legacy Pro, or Plus | `unity license activate --serial <serial>` | no |
| Floating seat | `unity license activate --floating` | no; needs a configured server |
| Offline | `unity license activate --generate-request <file>.alf`, exchange it for a `.ulf` on a machine with internet, then `unity license activate --file <file>.ulf` | no |

- `--accept-eula` accepts Unity's license terms on the user's behalf. Activation and `unity license return` change the user's seat assignment. Ask before running any of them on the user's machine.
- A service account (`UNITY_SERVICE_ACCOUNT_ID` plus `UNITY_SERVICE_ACCOUNT_SECRET`) signs the CLI in for cloud commands, but it cannot activate a license (docs).
- A serial passed as a flag lands in shell history. Newer CLIs read `UNITY_LICENSE_SERIAL` from the environment instead (docs; not in beta.6 help).
- In CI: activate, build, then run `unity license return --yes` for serial or assigned seats.
