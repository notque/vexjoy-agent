# Voice Writer Reference (Stub)

This file is a placeholder for CI compatibility. The full voice-writer skill
lives in a private repository and is loaded at runtime via symlink.

At install time, `~/.claude/skills/voice-writer/` points to the private-skills
voice writer skill directory. The /do router discovers it through INDEX.json
triggers and force_route configuration.

See `skills/INDEX.json` entry for `voice-writer` for routing triggers and
skill metadata.
