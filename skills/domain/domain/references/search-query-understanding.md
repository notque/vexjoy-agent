# Query-understanding decisions

Classify intent only when it changes retrieval: navigational, informational, transactional, or structured/filter intent. Keep the raw query and every transformation for debugging.

- Normalize conservatively; case, punctuation, identifiers, and quoted text can be meaningful.
- Synonyms are directional when expansion is asymmetric. Multiword synonyms need analyzer-compatible tokenization. Test both expected matches and false expansions.
- Apply spelling correction only above a confidence threshold and preserve an explicit “search instead” path; names and product codes are frequent false corrections.
- Entity extraction should produce typed filters only when the mapped field and normalized value are known. Otherwise retain the term in full-text retrieval.
- Query expansion improves recall but can destroy precision. Evaluate per query class, especially tail and ambiguous queries.
- Zero results, reformulation, and abandonment are different evidence; do not collapse them into one “bad query” label.
