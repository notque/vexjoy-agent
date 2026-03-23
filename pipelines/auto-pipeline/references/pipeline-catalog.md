# Pipeline Catalog
Auto-generated reference for auto-pipeline dedup checks.
Generated: 2026-03-23T17:42:13Z

| Pipeline | Phases | Chain | Task Type | Triggers |
|----------|--------|-------|-----------|----------|
| agent-upgrade | 5 | AUDIT → DIFF → PLAN → IMPLEMENT → RE-EVALUATE | git-workflow | agent, upgrade |
| article-evaluation-pipeline | 4 | FETCH → VALIDATE → ANALYZE → REPORT | content-validation | evaluate article, check article voice, is this authentic, review my article, voice evaluation |
| auto-pipeline | 5 | DEDUP CHECK → CHAIN SELECTION → CONTEXT CHECK → CRYSTALLIZE → EPHEMERAL EXECUTE | meta | auto-pipeline, ephemeral pipeline, no route found, unrouted task |
| chain-composer | 4 | LOAD → COMPOSE → VALIDATE → PRODUCE | meta | compose chains, build pipeline chains, chain composition, pipeline spec, compose pipeline |
| comprehensive-review | 9 | SCOPE → WAVE 0 DISPATCH — PER-PACKAGE DEEP REVIEW → WAVE 0 AGGREGATE — PER-PACKAGE SUMMARY → WAVE 1 DISPATCH → WAVE 0+1 AGGREGATE → WAVE 2 DISPATCH → FULL AGGREGATE → FIX → REPORT | review | comprehensive review, full review, review everything, review and fix, thorough review |
| de-ai-pipeline | 4 | SCAN → FIX → VERIFY → REPORT | content | de-ai docs, clean ai patterns, fix ai writing, scan and fix docs, remove ai tells |
| do-perspectives | 5 | VALIDATE INPUTS → MULTI-PERSPECTIVE ANALYSIS → SYNTHESIZE → APPLY → VERIFY AND REPORT | content-pipeline | perspectives |
| doc-pipeline | 5 | RESEARCH → OUTLINE → GENERATE → VERIFY → OUTPUT | documentation | document this, create readme, write documentation, document codebase, generate docs |
| domain-research | 4 | DISCOVER → CLASSIFY → MAP → PRODUCE | meta | research domain, discover subdomains, domain decomposition, what pipelines, domain research |
| explore-pipeline | 8 | SCAN → MAP → ANALYZE → COMPILE → ASSESS → SYNTHESIZE → REFINE → REPORT | exploration | understand codebase, explore repo, how does this work, codebase exploration, understand this code |
| github-profile-rules | 8 | ADR → FETCH → RESEARCH → SAMPLE → COMPILE → GENERATE → VALIDATE → OUTPUT | review | github, profile, rules |
| hook-development-pipeline | 9 | SPEC → IMPLEMENT → TEST → REGISTER → DOCUMENT → PERFORMANCE GATE FAILS → NON-BLOCKING GATE FAILS → JSON PARSE FAILS ON SETTINGS.JSON → HOOK-DEVELOPMENT-ENGINEER PRODUCES HOOK WITHOUT LAZY IMPORTS | git-workflow | hook, development, pipeline |
| mcp-pipeline-builder | 5 | ANALYSIS ERRORS → DESIGN ERRORS → VALIDATION ERRORS → EVALUATION ERRORS → REGISTRATION ERRORS | pipeline | mcp pipeline, repo to mcp, create mcp from repo, generate mcp, mcp builder |
| perses-dac-pipeline | 6 | INITIALIZE → DEFINE → BUILD → VALIDATE → DEPLOY → CI/CD INTEGRATION | general | perses, dac, pipeline |
| perses-plugin-pipeline | 6 | SCAFFOLD → SCHEMA → IMPLEMENT → TEST → BUILD → DEPLOY | git-workflow | perses, plugin, pipeline |
| pipeline-retro | 5 | INGEST → TRACE → PROPOSE → REGENERATE → REPORT | meta | pipeline retro, trace failures, generator improvement, three-layer fix, fix generator |
| pipeline-scaffolder | 5 | LOAD → SCAFFOLD AGENT → SCAFFOLD SKILLS → INTEGRATE → REPORT | research | pipeline, scaffolder |
| pipeline-test-runner | 4 | DISCOVER TARGETS → EXECUTE → VALIDATE OUTPUTS → REPORT | meta | test generated pipelines, run pipeline tests, validate scaffolded skills, pipeline test runner |
| pr-pipeline | 12 | CLASSIFY REPO → PREFLIGHT CHECKLIST → STAGE → REVIEW → COMMIT → PUSH → REVIEW-FIX LOOP → RETRO → ADR VALIDATION → CREATE PR → VERIFY → CLEANUP | git-workflow | submit PR, create pull request, send for review, push and PR, submit changes |
| research-pipeline | 5 | SCOPE → GATHER → SYNTHESIZE → VALIDATE → DELIVER | research | research, pipeline |
| research-to-article | 6 | GATHER → COMPILE → GROUND → GENERATE → VALIDATE → OUTPUT | content-pipeline | research then write, article with research, write about, research and article, full article pipeline |
| skill-creation-pipeline | 5 | DISCOVER → DESIGN → SCAFFOLD → VALIDATE → INTEGRATE | git-workflow | skill, creation, pipeline |
| system-upgrade | 6 | CHANGELOG → AUDIT → PLAN → IMPLEMENT → VALIDATE → DEPLOY | git-workflow | system, upgrade |
| voice-calibrator | 3 | VOICE GROUNDING → VOICE METRICS → THINKING PATTERNS | content-pipeline | voice, calibrator |
| voice-writer | 8 | LOAD → GROUND → GENERATE → VALIDATE → REFINE → JOY-CHECK → OUTPUT → CLEANUP | content | write article, blog post, write in voice, generate voice content, voice workflow |
| workflow-orchestrator | 4 | BRAINSTORM → WRITE-PLAN → VALIDATE-PLAN → EXECUTE-PLAN | git-workflow | workflow, orchestrator |
