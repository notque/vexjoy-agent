# Routing index maintenance

Frontmatter is source-of-truth. Use the repository generators for indexes and
routing maps; do not hand-edit generated entries.

The bundled updater scripts scan, extract, generate, update, and validate.
Preserve manual records identified by their schema. Surface duplicate names,
trigger conflicts, invalid companion names, and parse failures; never resolve a
conflict by last-write-wins. A successful run ends with a clean generator
`--check` against a fresh rescan.
