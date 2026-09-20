# Jev question design

`instructions` must state the full literal question; IDs are not shown to Jev. Use structured `question`, `inspect`, `focus`, `compare`, `note`, or `field` entries when paths and scope matter.

- Noul: one absolute condition. Define both true and false for subtle boundaries.
- Choice: mutually intelligible supplied options. Use `{what, not_for, examples}` when neighboring options overlap; include an escape option when none can fit.
- Score: ordered descriptions with the same fields at every level. Each adjacent boundary must be labelable.

Ask one coherent relationship per head. Split dimensions only when their separate probabilities change policy. Avoid double negatives, implicit arithmetic, dates requiring computation, multi-hop inference, and instructions to generate text. Put examples on the side they belong to; a boundary example is more useful than many obvious ones.

When a result is wrong, first ask whether the state contains decisive evidence. Wording cannot recover absent evidence. Validate structured fields against the live API: undocumented keys may return 422 or be ignored, while mocks still pass.
