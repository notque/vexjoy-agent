# PR review-pattern mining

Use `scripts/miner.py <owner/repo>[,<owner/repo>...] <output.json> [--limit N]` after validating GitHub access and remaining rate limit. The script records PR/comment context and resolution hints; output is evidence, not an automatic rule set.

Spot-check repository/reviewer coverage, comment URLs, code context, and resolution labels. Separate raw extraction from rule generation. Promote only repeated imperative feedback with source links, multiple examples, a clear action, and known counterexamples; distinguish repository policy from reviewer preference.

Group promoted rules by topic and confidence. Keep raw output provenance and mining date so later work can detect changed conventions. See [mining-commands.md](mining-commands.md), [reviewer-usernames.md](reviewer-usernames.md), and [pattern-categories.md](pattern-categories.md) only when mining.
