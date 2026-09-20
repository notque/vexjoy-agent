# Checker source map

The bundled scripts currently compare these repository surfaces:

| Tool source | Primary documentation |
|---|---|
| `skills/**/SKILL.md` | `docs/skills.md` |
| `agents/*.md` | `agents/README.md` |
| `commands/**/*.md` | `commands/README.md` |

`README.md` and `docs/REFERENCE.md` are secondary cross-reference surfaces.
Namespaced commands retain their relative namespace. Skill and agent identity
comes from frontmatter and must match the directory or filename respectively.

The separate docs catalog covers `docs/*.md`, excluding `archive/` and
`images/`; every included file needs `summary` and `read_when` frontmatter.
Treat exclusions implemented by the scanner as authoritative.
