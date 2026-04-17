# PPTX Generator Script Reference

## JSON File Writing Template (Phase 3 Step 2)

Save the approved slide map and design config to temp files before calling the generation script:

```bash
# Write slide map JSON to temp file
python3 -c "
import json
slide_map = [...]  # the approved slide map
with open('/tmp/slide_map.json', 'w') as f:
    json.dump(slide_map, f, indent=2)
"

# Write design config JSON
python3 -c "
import json
design = {'palette': 'corporate'}  # whichever palette was selected
with open('/tmp/design_config.json', 'w') as f:
    json.dump(design, f, indent=2)
"
```

## Output Report Template (Phase 6 Step 2)

```
===============================================================
 PRESENTATION GENERATED
===============================================================

 File: /absolute/path/to/presentation.pptx
 Slides: 10
 Palette: Corporate
 Format: 16:9 widescreen
 Size: 45,230 bytes

 Slide Map:
   1. [Title] "Q4 Revenue Analysis"
   2. [Content] "Executive Summary"
   ...
  10. [Closing] "Questions?"

 QA Result: PASS (2 iterations, 3 issues fixed)

 Notes:
   - [any remaining minor issues or caveats]

===============================================================
```

## generate_pptx.py

**Purpose**: Deterministic slide construction. Reads slide map JSON + design config JSON, produces .pptx.

| Argument | Required | Description |
|----------|----------|-------------|
| `--slide-map` | Yes | Path to slide map JSON file |
| `--design` | Yes | Path to design config JSON file |
| `--output` | Yes | Output .pptx file path |

**Design config format**:
```json
{
  "palette": "minimal",
  "template_path": null
}
```

Exit codes: 0 = success, 1 = missing python-pptx, 2 = invalid input, 3 = generation failed.

## convert_slides.py

**Purpose**: PPTX to PDF to per-slide PNG conversion for visual QA.

| Argument | Required | Description |
|----------|----------|-------------|
| `--input` | Yes | Path to .pptx file |
| `--output-dir` | Yes | Directory for output PNG files |
| `--dpi` | No | PNG resolution (default: 150) |
| `--keep-pdf` | No | Keep intermediate PDF file |

Exit codes: 0 = success, 1 = no LibreOffice, 2 = conversion failed, 3 = invalid input.

## validate_structure.py

**Purpose**: Validate .pptx structural integrity against the slide map.

| Argument | Required | Description |
|----------|----------|-------------|
| `--input` | Yes | Path to .pptx file |
| `--expected-slides` | No | Expected slide count |
| `--slide-map` | No | Path to slide map JSON for content validation |
| `--json` | No | Output results as JSON |

Exit codes: 0 = passed, 1 = missing python-pptx, 2 = validation failed, 3 = invalid input.
