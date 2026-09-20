# Drift classifications

- Missing: source tool absent from its primary documentation. High severity.
- Stale: documented tool absent from source. Medium severity.
- Incomplete: recognized entry lacks fields required by its format. Low severity.

The scripts calculate the score and exclusions. Never hand-recompute a
different score for the same run. Deprecation text does not make a deleted tool
invocable; stale entries remain visible unless the scanner's explicit exclusion
policy says otherwise.

Auto-fix is experimental and requires explicit authorization. It may insert or
remove recognized entries; it must not invent descriptions, rewrite surrounding
prose, or repair malformed input speculatively.
