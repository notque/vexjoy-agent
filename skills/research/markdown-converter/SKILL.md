---
name: markdown-converter
description: "Convert PDF, Office, HTML, structured data, media, or archives to Markdown with the local zero-install command."
user_invocable: false
agent: python-general-engineer
allowed-tools: [Bash, Read]
routing:
  triggers: [convert to markdown, markitdown, extract text from PDF, PDF to markdown, docx to markdown, ingest document, read this PDF, read this document, extract text from document, convert PDF, convert document, pptx to markdown, xlsx to markdown]
  category: research
  pairs_with: [research, domain]
---

# Markdown Converter

```bash
uvx 'markitdown[all]' input.pdf -o output.md
uvx 'markitdown[all]' input.docx
cat blob | uvx 'markitdown[all]' -x .pdf
```

Use `pipx run 'markitdown[all]'` when `uvx` is unavailable. For a scanned PDF with empty/garbled extraction, render pages with `pdftoppm` and convert the images so OCR runs. Video subtitle extraction belongs to `video-transcript`.
