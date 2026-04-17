# Create Voice — Error Handling

### Error: "Insufficient samples" (< 50)

**Cause**: User provided fewer than 50 writing samples.
**Solution**:
1. Count current samples and report the gap
2. Suggest specific sources based on what's already provided (e.g., "You have 20 Reddit comments. Try also pulling from HN history, blog posts, or email")
3. Stop and resolve before proceeding past Step 1. The system does not work with fewer than 50 samples.

### Error: "voice-analyzer.py fails"

**Cause**: Script execution error.
**Solution**:
1. Check Python 3 is available: `python3 --version`
2. Check script exists: `ls scripts/voice-analyzer.py`
3. Check file paths: Glob expansion may not work as expected in all shells. Try listing files first: `ls skills/voice-{name}/references/samples/*.md`
4. Try with explicit file list instead of glob: `--samples file1.md file2.md file3.md`

### Error: "Validation score too low" (< 50 after 3 iterations)

**Cause**: Generated content does not match voice profile metrics.
**Solution**:
1. Check if profile.json metrics are achievable (some metrics from small sample sets may be skewed)
2. Review banned patterns for false positives specific to this voice
3. Consider relaxing `metric_tolerance` in config.json from 0.20 to 0.25
4. Check if the SKILL.md has enough samples (the answer is usually: add more samples)
5. Manual review of SKILL.md instructions for contradictory rules

### Error: "Authorship matching fails" (< 4/5 roasters)

**Cause**: Generated content does not sound like the original author.
**Solution**: See the failure pattern table in Step 7. The fix is almost always more samples, not more rules.

### Error: "SKILL.md too short" (< 2000 lines)

**Cause**: Not enough samples or sections in the generated skill.
**Solution**:
1. Check that all sample categories are populated (length-based AND pattern-based)
2. Verify all template sections are present
3. Add more samples -- they are the bulk of the line count
4. Keep content substantive — with verbose rules. The goal is 2000+ lines of USEFUL content, primarily samples.

### Error: "Wabi-sabi violations flagged as errors"

**Cause**: Validator is flagging natural imperfections that are actually part of the voice.
**Solution**: Adjust config.json thresholds, NOT the content. If the authentic writing "fails" validation, the validator is wrong, not the writing.
