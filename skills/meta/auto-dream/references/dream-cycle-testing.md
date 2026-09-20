# Auto-Dream verification

Run the wrapper without arguments first. A valid dry run writes scan, analysis, both latest/dated reports, and an injection payload, but leaves the memory tree unchanged.

For live-path testing, copy the memory directory to a temporary location and point a test invocation at that snapshot; do not experiment on the live index. Verify archives, `merged_from`, index targets, limits (five changes/two insights), and absence of leftover `.tmp` files.

When piping a wrapper in a test, assert the producer status (`PIPESTATUS[0]`), not `tee`'s status.
