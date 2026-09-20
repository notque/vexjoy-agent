# Long and terminology-heavy translation

Build a session glossary before parallel work:

| Source form | Approved target form | Action | Context |
|---|---|---|---|
| exact source spelling | exact target spelling | translate / preserve / annotate | disambiguating use |

Preserve technical identifiers such as API, HTTP, JSON, SQL, and HTML unless the user's locale guide says otherwise. Unify aliases under one concept and ensure no term is simultaneously marked preserve and translate.

For documents over roughly 2,000 words, split at headings or paragraph boundaries into coherent 200–600 word chunks. Give every worker the document type, register, chunk position, and only the relevant glossary rows. Reassemble in original order with headings and blank lines intact. Then scan the whole output for terminology variants, dropped cross-references, broken lists, and register drift.

“Quick” may skip deep source analysis, but it does not skip preservation of names and identifiers. “Refined” adds a final native-language polish pass after the document-wide consistency check.
