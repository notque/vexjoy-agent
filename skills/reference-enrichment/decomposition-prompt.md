# Reference Decomposition — Headless Prompt

You are running as an autonomous process to improve the toolkit's progressive disclosure architecture. This is the inverse of enrichment: instead of ADDING reference files, you EXTRACT content from bloated SKILL.md and agent files into properly structured reference files.

The goal is to keep agent/skill bodies lean (workflow, phases, routing) while domain knowledge lives in reference files loaded on demand.

## Context

- **Date:** ${DECOMP_DATE}
- **Run ID:** ${DECOMP_RUN_ID}
- **Repository:** ${DECOMP_REPO_DIR}
- **Worktree:** ${DECOMP_WORKTREE}
- **Targets:** ${DECOMP_TARGETS}
- **Max targets:** ${DECOMP_MAX_TARGETS}
- **Dry-run mode:** ${DECOMP_DRY_RUN_MODE}

These targets were identified by the detection script as containing extractable content blocks (catalogs, examples, specs, rosters) that belong in reference files rather than the main body. Each target includes file paths, content types, line ranges, and suggested reference filenames.

## If Dry-Run Mode is "yes"

Only perform the audit analysis. For each target:
1. Read the target file and measure its current line count
2. Identify which content blocks are extractable (catalogs, example tables, anti-pattern lists, spec sections, rosters)
3. Check for existing reference files that could absorb the content
4. Report what WOULD be decomposed: block types, estimated line counts, suggested reference filenames
5. Do NOT create any files, branches, or PRs

Print a summary and exit.

## If Dry-Run Mode is "no"

### Phase 1: Setup

1. Check for existing open decomposition PRs: `gh pr list --search "decomp/refs" --state open --json number | python3 -c "import json,sys; d=json.load(sys.stdin); print(len(d))"`
2. If 3 or more decomposition PRs are already open, log "Too many open decomposition PRs (>=3), skipping to avoid accumulation" and exit. Decomposition changes are larger than enrichment, so the threshold is lower.
3. Verify you are running inside the worktree path (should contain /tmp/decomp-worktree):
   - Run `pwd` to confirm you're in the worktree path
   - Run `git log --oneline -1` to confirm you're at the expected HEAD
4. Create a feature branch: `git checkout -b decomp/refs-${DECOMP_RUN_ID}`

### Phase 2: Decompose Each Target

Process up to ${DECOMP_MAX_TARGETS} targets from the targets list. For each target:

1. **Save a snapshot** before any modifications:
   ```bash
   cp {path} /tmp/decomp-before-{component}.md
   ```

2. **Read the current file** (SKILL.md or agent body) and note its line count.

3. **Read the detection script output** in the target data to understand what content blocks are extractable: their types, line ranges, and suggested reference filenames.

4. **Read any existing reference files** in the component's `references/` directory to avoid creating duplicates. If a reference file with related content already exists, you will MERGE into it rather than creating a new file.

5. **Read the reference file template** at `skills/reference-enrichment/references/reference-file-template.md` for the standard structure that new reference files must follow.

6. **For each extractable block**, perform the extraction:

   a. **Determine the reference filename.** Use the detection script's suggestion as a starting point. Follow the naming convention: `{domain}-{topic}.md` (e.g., `go-anti-patterns.md`, `voice-banned-patterns.md`).

   b. **Check for merge targets.** If a reference file with related content already exists, MERGE into it instead of creating a duplicate. Two files covering the same sub-domain is worse than one longer file.

   c. **Create or update the reference file** with the extracted content. Ensure it follows the reference file template structure: scope header, overview, pattern tables, anti-pattern catalog, etc. Maximum 500 lines per reference file. If content would exceed 500 lines, split into two reference files covering narrower sub-domains.

   d. **Remove the content from the SKILL.md body.** The content is being MOVED, not copied. Do not leave the original content in place.

   e. **Add a loading table entry** that maps task signals to the new reference file. The loading table tells the agent/skill when to load each reference. Format:
      ```
      | Signal/Task | Reference File | When to Load |
      |-------------|---------------|--------------|
      | {signal pattern} | `references/{filename}` | {condition} |
      ```

7. **Verify retained structure.** After extraction, confirm the SKILL.md still retains these essential sections:
   - Frontmatter (title, description, etc.)
   - Brief overview / purpose statement
   - Phase workflow (if applicable)
   - Loading table (with entries for all reference files, including new ones)
   - Error handling / safety section (if applicable)

8. **Run validation:**
   ```bash
   python3 scripts/validate-decomposition.py --before /tmp/decomp-before-{component}.md --after {path} --refs {refs_dir}/
   ```

9. **Run structural check** (if the validation script exists):
   ```bash
   python3 scripts/validate-references.py --skill {name}
   ```
   Or for agents: `python3 scripts/validate-references.py --agent {name}`

10. **Run depth audit:**
    ```bash
    python3 scripts/audit-reference-depth.py --skill {name} --verbose
    ```
    Or for agents: `python3 scripts/audit-reference-depth.py --agent {name} --verbose`

### Phase 2.5: Validate Decomposition (Keep-or-Revert Gate)

For each decomposed target, evaluate whether the decomposition is valid:

1. **Run validate-decomposition.py** and check the exit code:

   - **Exit code 0 (PASS):** The decomposition is valid. KEEP all changes for this target.

   - **Exit code 1 (FAIL):** The decomposition has issues.
     - Check the error output. Common fixable issues:
       - Missing loading table entry: add the entry and re-run validation
       - Reference file missing scope header: add the header
     - Attempt to fix the issue, then re-run validation
     - If validation still fails after the fix attempt: REVERT by restoring from the snapshot:
       ```bash
       cp /tmp/decomp-before-{component}.md {path}
       ```
       Remove any reference files that were created for this target.

2. **Check the resulting SKILL.md line count.** If the file is still above 500 lines after decomposition, log a warning:
   ```
   [WARN] {name}: still {N} lines after decomposition (target: <=500)
   ```
   This is a warning, not a failure. Some skills have legitimate large workflows that cannot be decomposed further.

3. **Log the decision** for each target:
   - `[KEEP] {name}: {N} blocks extracted, {before} -> {after} lines`
   - `[REVERT] {name}: validation failed — {reason}`
   - `[SKIP] {name}: {reason}`

### Phase 3: Commit and PR

If any targets were successfully decomposed (KEEP decisions exist):

1. **Stage only modified and created files.** This includes:
   - Modified SKILL.md / agent body files
   - New or updated reference files in `references/` directories
   - Do NOT stage unrelated files

2. **Commit** with a descriptive message:
   ```
   refactor(refs): {component} — extract {N} content blocks into references ({before_lines}->{after_lines} lines)
   ```
   If multiple components were decomposed:
   ```
   refactor(refs): decompose {N} components — extract content blocks into references
   ```

3. **Push:**
   ```bash
   git push -u origin decomp/refs-${DECOMP_RUN_ID}
   ```

4. **Create PR:**
   ```bash
   gh pr create --title "refactor(refs): {component} — extract references ({before}->{after} lines)" --body "$(cat <<'EOF'
   ## Reference Decomposition

   Extracted content blocks from bloated skill/agent bodies into structured reference files.

   ### Changes
   - **{component}**: {before_lines} -> {after_lines} lines ({N} blocks extracted)
     - `references/{filename1}`: {description}
     - `references/{filename2}`: {description}

   ### Validation
   - validate-decomposition.py: PASS
   - validate-references.py: PASS
   - audit-reference-depth.py: Level {N}

   *Automated decomposition run ${DECOMP_RUN_ID}*
   EOF
   )"
   ```

5. **Auto-merge:**
   ```bash
   gh pr merge --squash --auto --delete-branch
   ```

6. Do NOT run `git checkout main`. You are in a worktree and the primary checkout owns the main branch.

## Safety Constraints

- **Never modify skill/agent LOGIC.** Only move content and add routing. Workflow phases, gates, and decision points STAY in the SKILL.md. Only catalogs, examples, specs, and rosters move to reference files.
- **Never delete content without first putting it in a reference file.** The operation is MOVE, not DELETE. Every line removed from a SKILL.md must appear in a reference file.
- **Maximum 500 lines per reference file.** Split into narrower sub-domain files if needed.
- **Content in `<!-- DO NOT OPTIMIZE -->` blocks must NOT be moved or modified.** These blocks are explicitly protected from decomposition.
- **No force-push, no commits to main.** Everything goes through a PR.
- **If anything fails, restore from snapshot and continue with the next target.** One failure should not abort the entire run.
- **Preserve loading table integrity.** Every reference file must have a corresponding loading table entry in the parent skill/agent body.
- **Validation gate is mandatory.** Never skip Phase 2.5, even if the decomposition "looks correct".

## Output

End your session with a summary:

```
=== Reference Decomposition Summary ===
Date: {date}
Targets processed: N/M
  - {name}: {before_lines} -> {after_lines} lines ({N} blocks extracted to {M} reference files)
  - {name}: SKIPPED ({reason})
  - {name}: REVERTED ({reason})
PR: {url or "none (dry-run)"}
===
```
