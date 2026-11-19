# Technical documentation

Load this reference when you write API references (REST/GraphQL), architecture docs, integration guides, or runbooks from verified source code. Include service configuration examples. Before finalizing, search the source for every documented parameter, return type, and endpoint path; correct every mismatch. Use MCP for cross-service documentation validation when needed. For tests that back documented examples, call the Skill tool with `testing`.

## Rules

### Hardcoded Behaviors (Always Apply)
- **Over-Engineering Prevention**: Only document what exists. Limit documentation to features and capabilities present in the codebase.
- **Source Code Verification FIRST**: ALWAYS verify documentation against actual source code before writing
- **Professional Quality Standard**: Match Google Cloud documentation quality (clear, accurate, comprehensive)
- **Accuracy Over Speed**: Verify every endpoint, parameter, and error code against source before documenting
- **Working Examples Required**: All code examples must be tested and verified to work
- **Error Code Completeness**: Document ALL error codes with causes and resolutions

### Default Behaviors (ON unless disabled)
- **curl Examples for APIs**: Provide working curl commands for all API endpoints
- **Authentication Documentation**: Include complete auth flows with examples
- **Troubleshooting Sections**: Add common issues and resolutions for each feature
- **Parameter Tables**: Use tables for parameters with type, required/optional, description
- **Response Examples**: Show complete request/response pairs for clarity
- **Cross-Links**: Link related documentation sections for navigation
- **Communication Style**: Technical precision with clarity. Assume intelligent reader.

### Optional Behaviors (OFF unless enabled)
- **Multi-Language Examples**: Provide examples in multiple programming languages
- **Interactive API Playground**: Create interactive examples (requires tooling)
- **Auto-Generated Docs**: Generate from code annotations (requires setup)
- **Version-Specific Docs**: Maintain separate docs for multiple API versions

## Capabilities & Limitations

### Scope

Document existing behavior, authentication flows, security requirements, and integration dependencies. Verify `curl` examples against the API. Include error codes, handling, and root-cause-to-resolution troubleshooting. Do not invent features or infer unverified behavior.

## Explicit Output Contract

Every documentation task MUST produce these sections in this order:

```
1. SCOPE: module/API documented, source files read
2. OVERVIEW: 2-3 sentence module purpose
3. API REFERENCE: endpoint/function table with signatures
4. PARAMETERS: type-annotated parameter tables per endpoint
5. EXAMPLES: 1 per endpoint, verified compilable
6. COVERAGE: source endpoints found vs documented (must be 100%)
7. VERDICT: COMPLETE / INCOMPLETE (with list of undocumented items)
```

If any section cannot be completed, the VERDICT is INCOMPLETE with an explicit list of what is missing and why.

## Documentation Standards

### Numeric Anchors

Use these limits:

- **Each endpoint/function gets exactly**: 1 description sentence, 1 parameter table, 1 return type, 1 example. No more, no less per endpoint.
- Keep each description under 30 words and focused on the interface.
- Use the one code example for the most common successful use case.
- **Every section must have at least 1 sentence; every parameter must have a type and description.** Empty sections and untyped parameters are defects.

Load [documentation-templates.md](technical-documentation/documentation-templates.md) for the full API endpoint template, integration guide template, 4-phase source code verification workflow with STOP checkpoints, preferred patterns with before/after examples, and the adversarial self-check checklist.

## Anti-Rationalization

### Domain-Specific Rationalizations

| Rationalization | Why It's Wrong | Required Action |
|-----------------|----------------|-----------------|
| "The API probably works like this" | Guessing creates inaccurate docs | Verify against source code |
| "Users will figure out the errors" | Incomplete error docs cause support load | Document all error codes with resolutions |
| "The example looks right" | Untested examples often fail | Test all code examples |
| "Basic troubleshooting is enough" | Vague guidance doesn't help users | Provide specific root cause -> resolution paths |
| "I'm pretty sure this parameter exists" | Pretty sure != verified | Grep the source. Zero results = hallucinated. Remove it. |
| "The return type is probably X based on usage" | Inference != declaration | Read the function signature, not the call sites |
| "This example should work" | Should != does | If you can't prove it compiles, mark it UNVERIFIED |

## Blocker Criteria

Resolve routine issues from repository evidence and existing authorization. When you are sure, decide, record the assumption in your report, and continue; ask Jev when genuinely unsure. Ask only when these situations leave a material decision uncovered:

| Situation | Why Stop | Ask This |
|-----------|----------|----------|
| Source code unavailable | Cannot verify accuracy | "Can I access the source code to verify documentation?" |
| API endpoint unreachable | Cannot test examples | "Is there a test/staging environment to verify examples?" |
| Multiple API versions | Version-specific docs needed | "Which API version should I document? Maintain separate docs?" |
| Unclear error semantics | Cannot document errors accurately | "What should error code X mean in this context?" |

## Reference Loading Table

Load the appropriate reference file when the task matches the signal:

| Task Signal | Reference File | Covers |
|-------------|---------------|--------|
| Writing docs from scratch, API endpoint template, integration guide, verification workflow, adversarial self-check | `technical-documentation/documentation-templates.md` | Templates, 4-phase workflow, preferred patterns with before/after |
| Parameter tables, error tables, heading structure, prose style | `technical-documentation/documentation-standards.md` | Google style guide standards, column order, 30-word endpoint descriptions |
| Hallucinated params, type mismatches, untested examples, stale response examples | `technical-documentation/api-doc-verification-failures.md` | Verification failures with detection commands for each |
| Runbook, incident response, troubleshooting guide, operational doc, deploy runbook | `technical-documentation/runbook-patterns.md` | 5-section runbook format, command-first diagnosis, rollback requirements |

Load `documentation-templates.md` plus the relevant domain file when writing documentation from scratch.
