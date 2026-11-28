# Markdown converter

Convert PDF, Office, HTML, structured data, image, audio, ZIP, and EPub files to Markdown with `markitdown`, with zero local install.

## Usage

Run `uvx 'markitdown[all]'` directly from the shell:

```bash
uvx 'markitdown[all]' input.pdf -o output.md   # write to file
uvx 'markitdown[all]' input.docx               # print to stdout
cat blob | uvx 'markitdown[all]' -x .pdf       # read stdin with extension hint
```

If `uvx` is unavailable, run `pipx run 'markitdown[all]' ...` with the same arguments. The first run downloads dependencies; later runs hit the local cache. Output preserves headings, tables, lists, and links.

For video transcripts, use the `video-editing` skill instead.

## Supported formats

| Input | Output behavior |
|-------|-----------------|
| PDF, `.docx`, `.pptx`, `.xlsx`, `.xls` | Preserves document structure, headings, and tables |
| HTML, CSV, JSON, XML | Converts to structured Markdown |
| Images | Extracts EXIF metadata plus OCR text |
| Audio | Extracts EXIF metadata plus speech transcription |
| ZIP, EPub | Iterates archive contents and converts each file |

## Options

| Flag | Effect |
|------|--------|
| `-o FILE` | Write Markdown output to `FILE` |
| `-x .EXT` | Supply extension hint for stdin input |
| `-m MIME` | Supply MIME-type hint |
| `-c CHARSET` | Supply character-set hint, such as `UTF-8` |

## Error handling

### Garbled or empty text from a scanned PDF

- **Cause:** Each page is a raster image; the base PDF extractor reads embedded text layers only.
- **Solution:** Render pages to PNG images with `pdftoppm`, then pass the rendered images to `markitdown` so OCR runs:

```bash
pdftoppm -png scanned.pdf page
uvx 'markitdown[all]' page-1.png -o page-1.md
```
