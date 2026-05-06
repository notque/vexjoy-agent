# PPTX Generator Dependencies

## Required

| Dependency | Type | Purpose | Install |
|------------|------|---------|---------|
| `python-pptx` | pip | PPTX generation and manipulation | `pip install python-pptx` |

## Optional (enhances capability)

| Dependency | Type | Purpose | Install |
|------------|------|---------|---------|
| LibreOffice | system | PDF/PNG conversion for visual QA loop | `apt install libreoffice-impress` |
| `Pillow` | pip | Image handling for embedded images | `pip install Pillow` |
| `pdftoppm` (poppler-utils) | system | Higher-quality PDF-to-PNG conversion | `apt install poppler-utils` |
| `markitdown` | pip | Extract text from existing PPTX for content reuse | `pip install markitdown` |

## Out-of-Scope Tools

| Tool | Why Not |
|------|---------|
| `pptxgenjs` / Node.js | Foreign ecosystem; python-pptx covers our needs |
| Raw XML unzip/rezip | python-pptx + lxml handles this natively |
| Headless browser | LibreOffice handles conversion |
