# Common Evaluation Issues

Separate deterministic failures from qualitative findings. Only the eight checks in `score-component.py` affect the structural score.

## Deterministic Failures

| Check | Common cause | Fix |
|---|---|---|
| Valid YAML frontmatter | Missing delimiters, invalid YAML, empty `name` or `description` | Repair the frontmatter and parse it again |
| Referenced files exist | Backtick-quoted path is stale or resolves from the wrong base | Correct the path or remove the stale claim |
| Patterns section | No heading containing `pattern` | Add a useful patterns section only when the component needs one |
| Error handling section | No heading containing `error` or `failure mode` | Document concrete recovery paths |
| Registered in routing | Missing from the applicable index or `/do` routing | Register the component through the normal index workflow |
| Reference files | No `references/` directory | Add references when progressive disclosure is useful; do not add empty padding |
| Workflow instructions | Missing `Instructions`, numbered Phase/Step heading, or `**Gate**` | Add the missing execution structure |
| No broken internal links | Relative Markdown links do not resolve | Repair or remove each broken link |

## Qualitative Findings

These do not change the structural score:

- **Stale guidance**: Instructions disagree with current code or repository policy.
- **Thin domain knowledge**: The component repeats generic advice without task-specific constraints or failure modes.
- **Unnecessary bulk**: Long examples, repeated rules, or catalogs crowd the entrypoint without changing behavior.
- **Tool mismatch**: Instructions require capabilities the declared tool set cannot provide.
- **Weak recovery guidance**: An error heading exists, but the listed action does not let the operator recover.
- **Placeholder content**: TODO or template prose remains in runtime instructions.
- **Broken examples**: Included scripts or commands fail syntax or focused execution checks.

Every qualitative finding must cite a file and line and state the behavioral impact. Do not recommend adding content solely to increase line count.
