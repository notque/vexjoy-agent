# Translate Skill: Glossary Reference

> **Load when**: Request contains "technical", "specialized", "glossary", "terms", or domain vocabulary.
> **Scope**: Glossary format, build procedure, chunk injection, term-preservation rules, example.

---

## Glossary Format

Use a markdown table with three columns:

```markdown
| Source Term | Target Term | Notes |
|---|---|---|
| machine learning | 機械学習 | Use consistently; annotate on first occurrence |
| API | API | Preserve as-is; internationally recognized |
| Docker | Docker | Brand name; preserve unchanged |
| microservice | マイクロサービス | Transliteration preferred over translation |
```

**Column definitions**:

| Column | Content |
|---|---|
| Source Term | Term exactly as it appears in the source document |
| Target Term | Agreed translation or "preserve" if keeping source-language form |
| Notes | Usage rule: annotate on first use, preserve unchanged, transliterate, etc. |

---

## Building a Glossary from the Source Document

**Step 1: Scan for specialized vocabulary**

Read the source document and list every term that falls into one of these categories:

- Technical identifiers: function names, library names, protocol names, data formats
- Domain vocabulary: field-specific terms that have a standard translation in the target language
- Brand and product names: trademarks, software product names, company names
- Proper nouns: person names, place names, organization names
- Abbreviations and acronyms: expand on first use in the target language if the expansion differs

**Step 2: Decide on treatment per term**

| Term type | Default treatment |
|---|---|
| Internationally recognized technical term (API, JSON, HTTP) | Preserve source-language form |
| Brand name or registered trademark | Preserve source-language form |
| Person name, place name | Preserve source-language form unless a standard transliteration exists |
| Domain vocabulary with a standard target-language equivalent | Translate; annotate on first use |
| Abbreviation whose expansion differs in target language | Translate expansion; keep source abbreviation in parentheses on first use |
| Culturally specific term with no equivalent | Preserve source-language form; add bracketed explanation on first use |

**Step 3: Populate the glossary table**

For each term identified in Step 1, add a row with the treatment decided in Step 2.

**Step 4: Review for consistency**

Check that no term appears in both "preserve" and "translate" rows. If the same concept appears in multiple surface forms in the source (e.g., "ML", "machine learning", "ML model"), unify them under one glossary entry.

---

## Injecting the Glossary into Chunk Translation Prompts

Prepend the glossary to each chunk prompt in this format:

```
Session glossary — apply these translations consistently throughout this chunk:

| Source Term | Target Term | Notes |
|---|---|---|
{glossary rows}

On first occurrence of a translated term, annotate it: "target-term (source-term)".
Preserve source-language form for all terms marked "preserve" in the Notes column.
```

Place the glossary block immediately after the context line and before the chunk text. Keep the glossary under 30 rows in a single prompt; if your glossary exceeds 30 rows, include only the rows relevant to the current chunk's content.

---

## Term Preservation Rules

Apply these in order when deciding whether to translate a term:

1. **Proper noun with no standard transliteration**: preserve unchanged.
2. **Internationally recognized technical identifier** (API, HTTP, JSON, SQL, HTML): preserve unchanged.
3. **Brand name or software product name**: preserve unchanged.
4. **Domain term with a widely used target-language equivalent**: translate and annotate on first use.
5. **Culturally specific concept with no equivalent**: preserve source term; add bracketed gloss explaining the concept on first use.

When in doubt, preserve the source-language term and annotate. A reader who encounters a preserved term can look it up. A reader who encounters a wrong translation has no signal that anything is wrong.

---

## Example Glossary: Technical Document (English to Japanese)

Source document: software architecture article discussing microservices, containers, and CI/CD pipelines.

| Source Term | Target Term | Notes |
|---|---|---|
| microservice | マイクロサービス | Transliterate; annotate on first use |
| container | コンテナ | Transliterate; annotate on first use |
| Docker | Docker | Brand name; preserve unchanged |
| Kubernetes | Kubernetes | Brand name; preserve unchanged |
| CI/CD | CI/CD | Abbreviation; preserve unchanged; expand on first use: 継続的インテグレーション/継続的デリバリー (CI/CD) |
| API gateway | APIゲートウェイ | Mixed: preserve API, transliterate gateway |
| service mesh | サービスメッシュ | Transliterate; annotate on first use |
| load balancer | ロードバランサー | Transliterate; annotate on first use |
| deployment | デプロイメント | Transliterate preferred over 展開 in technical contexts |
| pod | Pod | Kubernetes term; preserve source form; capitalize |
| namespace | 名前空間 | Standard Japanese translation; use consistently |
| YAML | YAML | Abbreviation; preserve unchanged |

**First-use annotation example**:
- Source: "A microservice handles one business capability."
- Target: "マイクロサービス（microservice）は1つのビジネス機能を担当します。"

---

## See Also

- `modes.md` — Chunking algorithm, parallel dispatch, per-mode workflow
