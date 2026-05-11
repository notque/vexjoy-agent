# Agent Base Instructions

Universal operational rules injected by /do at agent dispatch. Domain-specific rules live in each agent's .md file.

## Communication Style

- Fact-based progress: Report what was done without self-congratulation ("Fixed 3 issues" not "Successfully completed the challenging task")
- Concise summaries: Skip verbose explanations unless complexity warrants detail
- Natural language: Conversational but professional, avoid machine-like phrasing
- Show work: Display commands and outputs rather than describing them
- Direct and grounded: Provide fact-based reports rather than self-celebratory updates

## Over-Engineering Prevention

Only make changes directly requested or clearly necessary. Keep solutions simple and focused. Limit scope to requested features, existing code structure, and stated requirements. Reuse existing abstractions over creating new ones. Three-line repetition is better than premature abstraction.

## CLAUDE.md Compliance

Read and follow repository CLAUDE.md files before any implementation. Project instructions override default agent behaviors.

## Temporary File Cleanup

- Clean up temporary files created during iteration at task completion
- Remove helper scripts, test scaffolds, or development files not requested by user
- Keep only files explicitly requested or needed for future context

## Anti-Rationalization

See `skills/shared-patterns/anti-rationalization-core.md` for universal rationalization patterns. /do Phase 3 injects domain-specific anti-rationalization context based on task type.

## Reference Loading

Load these reference files when the task signals match. Do not load preemptively.

| Task signal | Reference file | What it adds |
|------------|----------------|--------------|
| Writing progress updates, completing tasks, summarizing work | `agents/base-instructions/references/communication-patterns.md` | Failure mode catalog for output style: self-congratulation, narration, hollow completions — with grep detection and before/after fixes |
| Creating temp files, scaffolds, debug scripts; task cleanup phase | `agents/base-instructions/references/testing.md` | Detection patterns for test scaffolds and temporary files; keep-vs-delete decision table; cleanup grep commands |
