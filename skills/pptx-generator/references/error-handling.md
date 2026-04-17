# PPTX Generator Error Handling

## Error: python-pptx Not Installed
**Cause**: The `python-pptx` package is missing from the Python environment.
**Solution**: Run `pip install python-pptx Pillow`. This is a hard dependency -- the skill cannot function without it. Verify with `python3 -c "from pptx import Presentation; print('OK')"`.

## Error: LibreOffice Not Available
**Cause**: `soffice` binary not found on the system. Required for the visual QA loop (Phases 4-5).
**Solution**: This is a soft dependency. The skill degrades gracefully:
1. Log that visual QA is unavailable
2. Skip Phases 4-5
3. Rely on structural validation from `validate_structure.py`
4. Note in the output report that visual QA was skipped

Install with: `apt install libreoffice-impress` (Debian/Ubuntu) or `brew install --cask libreoffice` (macOS).

## Error: Slide Map JSON Invalid
**Cause**: Malformed JSON, missing `type` field, or unsupported layout type.
**Solution**:
1. Validate JSON syntax before passing to the script
2. Check that every slide object has a `type` field
3. Supported types: `title`, `section`, `content`, `two_column`, `quote`, `table`, `image_text`, `closing`
4. Unknown types fall back to `content` layout

## Error: Generated PPTX Empty or Corrupt
**Cause**: Script error during generation, typically from invalid slide data (null values, missing arrays).
**Solution**:
1. Run `validate_structure.py` to identify the specific failure
2. Check the slide map JSON for null or missing fields
3. Fix and re-generate. Max 2 retries before escalating.

## Error: QA Loop Exceeds 3 Iterations
**Cause**: Visual issues persist despite fixes. Usually indicates a fundamental design problem.
**Solution**: Stop iterating after 3 attempts. Report remaining issues, suggest the user simplify content or change layout approach, deliver the best available version with caveats.

---

## Blocker Criteria

STOP and ask the user (stop and resolve before proceeding autonomously) when:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Content too thin for requested slide count | Padding produces empty slides that waste audience time | "You have content for about 5 slides but requested 12. Create a 5-slide deck or add more content?" |
| No clear topic or audience | Cannot select palette or structure without context | "Who is the audience, and what is the key message?" |
| User provides a .pptx template to modify | Template editing has different constraints than blank-slate generation | "Should I modify your existing deck, or create a new one using your template's styling?" |
| QA finds structural issues (wrong slide count) | Structural failures indicate a slide map problem, not a visual fix | "The generated deck has 8 slides but the map specified 10. Regenerate or adjust the map?" |
| Multiple valid palette choices | Aesthetic preference is personal | "I'd suggest [Palette] for this type of presentation. Want that, or prefer something else?" |

### Confirm With User
- Audience and tone (business vs technical vs casual changes everything)
- Whether to use dark theme (Midnight palette) -- strong aesthetic choice
- Whether to include images (user must provide assets or explicitly request generation)
- Slide count when user is vague ("a few slides" -- ask for a number)
- Content that the user hasn't provided (build the deck from user-provided content only). Reason: Build the deck the user asked for. No speculative slides, no "bonus" content, no unsolicited animations or transitions.

---

## Retry Limits and Recovery

**Retry Limits**:
- Phase 3 (GENERATE): Max 2 retries for script failures before escalating to user
- Phase 5 (QA): Max 3 iterations of the fix-and-recheck cycle
- Slide map revision: Max 2 rounds of user feedback before freezing the map

**Recovery Protocol**:
1. **Detection**: Same QA issue reappearing after a fix attempt, generation script failing on the same input repeatedly, or slide map revisions not converging
2. **Intervention**: Simplify the deck. Reduce slide count, use only `content` and `title` layouts, drop complex layouts (table, two-column) that may be causing issues
3. **Prevention**: Validate the slide map JSON against the schema before generation. Check that bullet counts are within limits. Verify image paths exist before including `image_text` slides.
