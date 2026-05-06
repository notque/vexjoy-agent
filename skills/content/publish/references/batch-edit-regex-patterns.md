# Common Regex Patterns for Hugo Content

Tested regex patterns for batch editing Hugo blog posts.

---

## Date Patterns

### ISO Date (YYYY-MM-DD)

```regex
Pattern: \d{4}-\d{2}-\d{2}
Matches: 2024-12-24, 2025-01-15
```

**Convert to US format (MM/DD/YYYY):**
```
Find:    (\d{4})-(\d{2})-(\d{2})
Replace: $2/$3/$1
Result:  12/24/2024
```

**Convert to European format (DD/MM/YYYY):**
```
Find:    (\d{4})-(\d{2})-(\d{2})
Replace: $3/$2/$1
Result:  24/12/2024
```

---

## URL Patterns

### Markdown Links

```regex
# Inline links: [text](url)
Pattern: \[([^\]]+)\]\(([^)]+)\)
Groups:  $1 = text, $2 = url

# Reference links: [text][ref]
Pattern: \[([^\]]+)\]\[([^\]]+)\]
Groups:  $1 = text, $2 = reference

# Reference definitions: [ref]: url
Pattern: ^\[([^\]]+)\]:\s*(.+)$
Groups:  $1 = reference, $2 = url
```

**Convert http to https:**
```
Find:    \[([^\]]+)\]\(http://
Replace: [$1](https://
```

**Add target="_blank" to external links (Hugo shortcode):**
```
Find:    \[([^\]]+)\]\((https?://[^)]+)\)
Replace: {{< external-link text="$1" url="$2" >}}
```

---

## Image Patterns

### Markdown Images

```regex
# Basic: ![alt](path)
Pattern: !\[([^\]]*)\]\(([^)]+)\)
Groups:  $1 = alt text, $2 = path

# With title: ![alt](path "title")
Pattern: !\[([^\]]*)\]\(([^"]+)\s+"([^"]+)"\)
Groups:  $1 = alt, $2 = path, $3 = title
```

**Add missing alt text placeholder:**
```
Find:    !\[\]\(([^)]+)\)
Replace: ![TODO: add alt text]($1)
```

**Convert to Hugo figure shortcode:**
```
Find:    !\[([^\]]*)\]\(([^)]+)\)
Replace: {{< figure src="$2" alt="$1" >}}
```

---

## Heading Patterns

### Match Headings by Level

```regex
# H1 only
Pattern: ^# (.+)$

# H2 only
Pattern: ^## (.+)$

# H3 only
Pattern: ^### (.+)$

# Any heading (H1-H6)
Pattern: ^(#{1,6}) (.+)$
Groups:  $1 = hashes, $2 = title
```

**Demote all headings (# -> ##):**
```
Find:    ^(#{1,5}) (.+)$
Replace: #$1 $2
```

**Promote all headings (## -> #):**
```
Find:    ^##(#{0,4}) (.+)$
Replace: #$1 $2
```

---

## Code Patterns

### Inline Code

```regex
# Single backticks
Pattern: `([^`]+)`
Groups:  $1 = code content

# Triple backticks with language
Pattern: ^```(\w+)?\n([\s\S]*?)```$
Groups:  $1 = language, $2 = code
```

**Wrap specific terms in backticks:**
```
Find:    \b(kubectl|docker|npm|yarn|git)\b
Replace: `$1`
Note:    Only matches outside existing backticks
```

---

## Whitespace Patterns

### Trailing Whitespace

```regex
Pattern: [ \t]+$
Replace: (empty)
Note:    Matches spaces/tabs at end of line
```

### Multiple Blank Lines

```regex
Pattern: \n{3,}
Replace: \n\n
Note:    Normalizes 3+ newlines to 2
```

### Leading Whitespace

```regex
Pattern: ^[ \t]+
Note:    Matches spaces/tabs at start of line
```

---

## Quote Patterns

### Smart Quotes to Straight

```regex
# Left double quotes
Find:    \u201C
Replace: "

# Right double quotes
Find:    \u201D
Replace: "

# Left single quotes / apostrophe
Find:    \u2018
Replace: '

# Right single quotes / apostrophe
Find:    \u2019
Replace: '

# Combined pattern
Find:    [\u201C\u201D]
Replace: "
```

### Straight to Smart (context-aware)

```regex
# Opening quote (after space or start)
Find:    (^|[ \n])"
Replace: $1\u201C

# Closing quote (before space, punctuation, or end)
Find:    "($|[ \n.,!?])
Replace: \u201D$1
```

---

## Frontmatter Patterns

### YAML Frontmatter Block

```regex
Pattern: ^---\n([\s\S]*?)\n---
Groups:  $1 = frontmatter content
```

### Specific Field

```regex
# Author field
Pattern: ^author:\s*["']?(.+?)["']?$

# Date field
Pattern: ^date:\s*(.+)$

# Tags array
Pattern: ^tags:\s*\[(.*)\]$

# Draft boolean
Pattern: ^draft:\s*(true|false)$
```

**Change field value:**
```
Find:    ^(author:\s*)["']?.*["']?$
Replace: $1"New Author"
```

---

## Hugo Shortcode Patterns

### Any Shortcode

```regex
# Paired shortcode
Pattern: {{<\s*(\w+)\s*([^>]*)>}}([\s\S]*?){{<\s*/\1\s*>}}
Groups:  $1 = name, $2 = params, $3 = content

# Self-closing shortcode
Pattern: {{<\s*(\w+)\s*([^>]*)/?\\s*>}}
Groups:  $1 = name, $2 = params
```

### Specific Shortcodes

```regex
# Figure shortcode
Pattern: {{<\s*figure\s+src="([^"]+)"([^>]*)>}}

# Highlight shortcode
Pattern: {{<\s*highlight\s+(\w+)\s*>}}([\s\S]*?){{<\s*/highlight\s*>}}

# Ref/relref shortcode
Pattern: {{<\s*(rel)?ref\s+"([^"]+)"\s*>}}
```

---

## Common Cleanup Patterns

### TODO/FIXME Comments

```regex
# HTML comments with TODO
Pattern: <!--\s*TODO:?\s*(.+?)\s*-->

# Markdown TODO
Pattern: ^\s*[-*]\s*\[ \]\s*TODO:?\s*(.+)$

# Inline TODO
Pattern: TODO:?\s*(.+)$
```

**Find and list all TODOs:**
```
Find:    (TODO|FIXME|XXX):?\s*(.+)
```

### Placeholder Text

```regex
# Square bracket placeholders
Pattern: \[(?:insert|add|TBD|TODO|XXX)[^\]]*\]

# Lorem ipsum
Pattern: Lorem ipsum.*?(?:\.|$)

# Placeholder markers
Pattern: (?:PLACEHOLDER|INSERT_HERE|XXX)
```

---

## Safe Patterns (Non-Greedy)

Always use non-greedy quantifiers to avoid over-matching:

```regex
# Greedy (dangerous - matches too much)
Pattern: \[.*\]

# Non-greedy (safe - matches minimum)
Pattern: \[.*?\]

# Greedy (matches entire file between ---)
Pattern: ---(.*)---

# Non-greedy (matches just frontmatter)
Pattern: ---(.*?)---
```

---

## Testing Patterns

Before batch applying, test patterns with grep:

```bash
# Test pattern matches
grep -rn -E "pattern" content/posts/

# Count matches
grep -rc -E "pattern" content/posts/

# Show context
grep -rn -E -B2 -A2 "pattern" content/posts/

# Test on single file first
grep -n -E "pattern" content/posts/first-post.md
```
