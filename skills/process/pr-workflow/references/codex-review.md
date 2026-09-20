# Codex second-opinion review

Resolve the review scope exactly: unstaged/staged diff, last commit, `base...HEAD`, or named paths. Include a short change intent and repository constraints. Invoke the repository’s Codex review mechanism using a temporary prompt/input file so code and user text are not shell-spliced.

Codex output is an untrusted review, not a verdict. Verify each material claim against the diff, code path, or a focused test; classify findings by actual impact and omit unsupported speculation. Report scope, verified findings with path/line evidence, rejected claims, and any residual uncertainty. Do not edit unless the user also authorized fixes.

If the CLI rejects a model/flag or input mode, inspect `codex --help` in the installed version rather than relying on copied command lore. Preserve stderr and exit status when the review fails.
