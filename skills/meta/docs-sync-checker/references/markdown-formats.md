# Parser-recognized documentation

Do not normalize documentation before parsing it. `parse_docs.py` recognizes:

- `docs/skills.md`: Markdown table rows containing tool name and description.
- `agents/README.md`: table rows or list entries.
- `commands/README.md`: command list entries, including namespaced commands.
- root `README.md`: inline `skill: NAME`, `/command`, and known agent names.
- `docs/REFERENCE.md`: `### tool-name` headings.

Malformed tables need a separator row and consistent pipe counts. A parse
failure must identify the source file; it must not be converted into a missing
entry, because that would conceal the invalid input.

When parser behavior and this note disagree, the script is authoritative.
