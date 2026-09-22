---
description: "Plan, then apply, the VexJoy Agent install with the vexinstall engine"
allowed-tools: ["Read", "Bash", "Glob", "Grep"]
---

Install or repair VexJoy Agent with the vexinstall engine. The engine lives in `scripts/vexinstall/`; its layout contract is in `docs/installer-layout.md`.

1. Show the plan. It writes nothing:

   ```bash
   PYTHONPATH=<repo>/scripts python3 -m vexinstall plan --target all
   ```

   Report the per-target counts (add, replace, remove, adopt, blocked, collisions) and any `CAP-TRIPPED` or `note:` lines. Exit 3 means a name collision: name both sources and stop.

2. Ask the user before applying. Apply only the targets the user approves:

   ```bash
   PYTHONPATH=<repo>/scripts python3 -m vexinstall apply --target <target>
   ```

   Never pass `--allow-mass-remove`, `--adopt-source`, or `--mode` unless the user asks for that flag by name after reading the plan.

3. Check the result:

   ```bash
   PYTHONPATH=<repo>/scripts python3 -m vexinstall doctor --target <target>
   ```

Exit codes: 0 ok, 1 error, 2 usage, 3 collision, 4 guard (write into the repo refused), 5 mass-removal cap, 6 source refused (worktree, `/tmp`, or moved repo), 7 lock timeout.

`./install.sh` runs `apply --takeover` for every present runtime; the SessionStart hook runs `sync --target all`. Pass `--takeover` to `apply` only when the plan shows `takeover` entries the user wants replaced. Undo an apply with `python3 -m vexinstall restore-trash <ts>` and `restore-settings <ts>`.
