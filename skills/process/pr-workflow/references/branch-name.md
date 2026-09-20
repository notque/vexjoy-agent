# Branch naming contract

Repository `.branch-naming.json` overrides this default. Map Conventional Commit types to matching prefixes, except `feat` → `feature/`. Sanitize the subject to lowercase kebab-case, ASCII letters/digits/hyphens only, collapsing separators.

Default maximum is 50 characters including prefix. Shorten at word boundaries before truncating. Check local and remote collisions; never overwrite an existing branch. Offer a meaningful suffix or version when collision remains. Ask only when the change type cannot be inferred safely.
