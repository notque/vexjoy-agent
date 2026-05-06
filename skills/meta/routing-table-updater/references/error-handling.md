# Routing Table Updater — Error Handling

### Error: "YAML Parse Error in {file}"
Cause: Malformed YAML frontmatter in skill/agent file
Solution: Fix YAML syntax (missing colons, bad indentation, unquoted special characters), re-run extraction

### Error: "Routing Conflict -- High Severity"
Cause: Same trigger phrase maps to incompatible routes (e.g., "deploy" to both Docker and Kubernetes)
Solution: Add domain context to patterns ("deploy Docker" vs "deploy K8s"), update skill descriptions, document resolution in `references/conflict-resolution.md`

### Error: "Manual Entry Overwrite Detected"
Cause: Bug in manual entry detection logic
Solution: CRITICAL -- DO NOT PROCEED. Restore from backup immediately. Report detection regex issue.

### Error: "Markdown Table Validation Failed"
Cause: Generated table has misaligned pipes, missing headers, or inconsistent column counts
Solution: Restore from backup, fix table generation logic, re-run. Do not commit broken markdown.

---

### Phase Gate Failure Recovery

#### Phase 1: SCAN gate failures
- "Repository not found": Verify --repo path points to agents directory
- "No skills found": Check skills/ directory exists and has subdirectories
- "Permission denied": Verify file read permissions

#### Phase 2: EXTRACT gate failures
- "Invalid YAML in {file}": Fix YAML frontmatter in the skill/agent file
- "Missing description field": Add description to YAML frontmatter
- "No trigger patterns found": Update description to include clear trigger phrases

#### Phase 3: GENERATE gate failures
- "Unknown routing table target": Update routing table mapping logic
- "High-severity conflict": Review conflicting patterns manually before proceeding

#### Phase 5: VERIFY gate failures
- "Duplicate pattern detected": Remove duplicate from do.md
- "Missing skill/agent file": Remove routing entry or create missing capability
- "Invalid complexity level": Fix complexity value in routing entry
