# Review feedback workflow

Fetch all three GitHub channels because they are separate: submitted reviews, inline review comments, and issue/PR conversation comments. Deduplicate while preserving IDs, authors, paths, line context, and outdated/resolved state.

Independently classify every actionable claim as `VALID`, `INVALID`, or `NEEDS-DISCUSSION`. Prefer executed tests or reproduction, then service/HTTP evidence, search, source reading, and finally reviewer assertion. Search for moved code before calling a comment stale. Performance claims need measurement; logic and boundary claims need a trace or focused test.

Show the complete classification table before editing. Resolve discussion items that materially affect the fix. Apply minimal fixes only for validated items, verify each and the combined diff, then commit/push only when authorized. Never fabricate feedback when all channels are empty.

Record a reusable rule only when the finding reflects a repeated repository convention or failure mechanism—not a one-off preference.
