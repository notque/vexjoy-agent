# Workflow Patterns

Reusable phase structures for skill design.

## Pattern 1: Sequential Workflow Orchestration

**Use when**: Multi-step processes in a specific order.

**Key techniques**:
- Explicit step ordering
- Dependencies between steps
- Validation at each stage
- Rollback instructions for failures

**Example Structure**:
```markdown
### Phase 1: Prepare
- Step 1: Validate inputs
- Step 2: Set up environment
- **GATE**: All prerequisites satisfied

### Phase 2: Execute
- Step 1: Run main operation
- Step 2: Verify output
- **GATE**: Operation completed successfully

### Phase 3: Finalize
- Step 1: Clean up temporary files
- Step 2: Generate report
```

**Best for**: Deployment workflows, build pipelines, data processing

---

## Pattern 2: Multi-Service Coordination

**Use when**: Workflows span multiple tools or MCP servers.

**Key techniques**:
- Clear phase separation
- Data passing between services
- Validation before moving to next phase
- Centralized error handling

**Example Structure**:
```markdown
### Phase 1: Gather (Service A)
- Collect data from source
- **GATE**: Data retrieved and validated

### Phase 2: Transform (Service B)
- Process gathered data
- **GATE**: Transformation complete

### Phase 3: Publish (Service C)
- Push to destination
- **GATE**: Published successfully
```

**Best for**: API integration, multi-tool workflows, MCP-based skills

---

## Pattern 3: Iterative Refinement

**Use when**: Output quality improves with iteration.

**Key techniques**:
- Initial draft → quality check (via script) → refinement loop → finalization
- Explicit quality criteria
- Know when to stop iterating (max 3 iterations)

**Example Structure**:
```markdown
### Phase 1: Initial Generation
- Create first draft
- **GATE**: Draft exists

### Phase 2: Quality Check
- Run validation script
- Collect issues
- **GATE**: Issues identified OR no issues found

### Phase 3: Refinement (max 3 iterations)
- Fix identified issues
- Re-run validation
- **GATE**: All criteria met OR max iterations reached

### Phase 4: Finalize
- Apply final formatting
- Generate output
```

**Best for**: Content generation, code formatting, design systems

---

## Pattern 4: Context-Aware Tool Selection

**Use when**: Same outcome, different tools depending on context.

**Key techniques**:
- Decision tree based on input characteristics
- Fallback options
- Transparency about choices made

**Example Structure**:
```markdown
### Phase 1: Analyze Context
- Detect input type
- Determine available tools
- **GATE**: Tool selected

### Phase 2: Execute (branching)
**If**: Input type A → Use Tool 1
**Else if**: Input type B → Use Tool 2
**Else**: Use fallback Tool 3

### Phase 3: Validate
- Verify output regardless of tool used
- **GATE**: Output meets criteria
```

**Best for**: Multi-format processors, cross-platform workflows, adaptive automation

---

## Pattern 5: Domain-Specific Intelligence

**Use when**: Skill adds specialized knowledge beyond tool access.

**Key techniques**:
- Domain expertise embedded in logic (compliance rules, industry standards)
- Validation before action
- Comprehensive audit trail

**Example Structure**:
```markdown
### Phase 1: Compliance Check
- Apply domain rules
- Check against standards
- **GATE**: Meets compliance requirements

### Phase 2: Execute with Safeguards
- Apply operation with domain constraints
- Log all decisions
- **GATE**: Operation complete, audit trail generated

### Phase 3: Verification
- Domain-specific validation
- Generate compliance report
```

**Best for**: Security workflows, regulatory compliance, industry-specific automation

---

## Pattern 6: Eval-Driven Skill Development

**Use when**: Building or improving skills where output quality can be measured.

**Key techniques**:
- Draft skill → test with real prompts → measure results → improve → repeat
- Compare with-skill vs without-skill (or old-skill) outputs
- Quantitative assertions for objective criteria, human review for subjective quality
- Baseline comparisons to prove the skill actually helps

**Core Loop**:
```markdown
### Phase 1: Draft
- Write initial SKILL.md
- **GATE**: Skill has valid frontmatter and instructions

### Phase 2: Test
- Create 2-3 realistic test prompts (the kind of thing a real user would say)
- Run each prompt with the skill loaded
- Run each prompt WITHOUT the skill (baseline)
- Save both outputs for comparison
- **GATE**: All test runs complete

### Phase 3: Evaluate
- Compare with-skill vs without-skill outputs
- For objective criteria: write assertions (file exists, format correct, etc.)
- For subjective criteria: human reviews the outputs
- **GATE**: Evaluation complete, feedback collected

### Phase 4: Improve (max 3 iterations)
- Generalize from feedback (don't overfit to test cases)
- Remove instructions that aren't pulling their weight
- Add scripts for repeated work across test cases
- Explain the why behind each instruction change
- **GATE**: Improvement applied OR max iterations reached

### Phase 5: Scale
- Expand test set with more diverse prompts
- Run larger eval to catch edge cases
- **GATE**: Pass rate acceptable across expanded set
```

**Improvement principles** (from Anthropic's skill-creator):
1. **Generalize, don't overfit** — Skills will be used across many prompts, not just your test cases. Avoid fiddly, overfitting changes.
2. **Keep the prompt lean** — Read test transcripts, not just outputs. If the skill causes unproductive work, remove those instructions.
3. **Explain the why** — Motivation-based instructions generalize better than rigid MUSTs.
4. **Extract repeated work** — If all test runs independently wrote similar helper scripts, bundle that script in `scripts/`.

**Test prompt quality**: Use realistic prompts with detail — file paths, personal context, casual phrasing, typos. Not abstract one-liners like "Format this data". The richer the test prompt, the better it tests the skill.

**Best for**: Any skill where you can objectively measure output quality, especially skills that will be widely used.

---

## Phase Gate Patterns

### Hard Gate (MUST pass)
```markdown
### Phase N: [Name]
- Step 1
- Step 2
- **GATE**: [Condition] verified before proceeding

If gate fails:
- STOP execution
- Report failure
- Provide remediation steps
```

### Soft Gate (WARNING only)
```markdown
### Phase N: [Name]
- Step 1
- Step 2
- **GATE**: [Condition] recommended but not required

If gate fails:
- WARNING: [Consequence of proceeding]
- User can choose to continue
```

### Iterative Gate (retry allowed)
```markdown
### Phase N: [Name] (max 3 attempts)
- Step 1
- Step 2
- **GATE**: [Condition] OR max attempts reached

If gate fails and attempts < 3:
- Log failure
- Adjust parameters
- Retry from Phase N

If max attempts reached:
- STOP execution
- Report all failures
```

---

## Error Recovery Patterns

### Rollback on Failure
```markdown
### Phase N: [Risky Operation]
- Create checkpoint
- Execute operation
- **GATE**: Success OR rollback triggered

If failure:
- Restore from checkpoint
- Clean up partial changes
- Report error
```

### Graceful Degradation
```markdown
### Phase N: [Primary Attempt]
- Try optimal method
- **GATE**: Success OR fallback triggered

If failure:
- Try fallback method
- **GATE**: Success OR report limitation

If both fail:
- Report both failures
- Suggest manual intervention
```

### Progressive Enhancement
```markdown
### Phase 1: Core Functionality
- Implement minimum viable output
- **GATE**: Core complete

### Phase 2: Enhancements (optional)
- Try to add nice-to-have features
- If any fail: Continue anyway
- **GATE**: Best-effort complete

Result: Core guaranteed, enhancements best-effort
```
