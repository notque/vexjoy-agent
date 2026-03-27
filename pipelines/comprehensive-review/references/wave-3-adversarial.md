# Wave 3: Adversarial Agents (4-5 agents)

These agents receive Wave 0+1+2 aggregated findings as input. Their job is to CHALLENGE the consensus — not reinforce it. Wave 3 agents push back on findings, question whether issues are real, and surface tradeoffs that earlier waves may have accepted uncritically.

**ALL Wave 3 agents MUST be dispatched in ONE message for true parallel execution.**

Use `model: sonnet` for all Wave 3 agents. The orchestrator runs on Opus; dispatched agents run on Sonnet.

## Agent Roster

| # | Agent | Role | Challenge Focus |
|---|-------|------|----------------|
| 21 | `reviewer-contrarian` | Challenges findings | Are these findings actually important? Which are false positives? Which are over-severity? |
| 22 | `reviewer-skeptical-senior` | Experience-based skepticism | "I've seen this before" — which findings are theoretical vs real-world issues? |
| 23 | `reviewer-user-advocate` | User impact assessment | Does this change break users? Are UX tradeoffs justified? Are migration paths safe? |
| 24 | `reviewer-meta-process` | Process/approach review | Is this the right approach? Should the PR be split? Is the review itself focused correctly? |

## Conditional: SAPCC Structural Review

| # | Agent | Condition | Challenge Focus |
|---|-------|-----------|----------------|
| 25 | `reviewer-sapcc-structural` | Repo contains ANY of: `hybris/`, `core-customize/`, `config/localextensions.xml`, or `manifest.json` with `"commerceSuiteVersion"` | SAP Commerce Cloud structural integrity — extension wiring, build manifest, data model impacts |

SAPCC detection:
```bash
SAPCC_DETECTED=false
if [ -d "hybris" ] || [ -d "core-customize" ] || [ -f "config/localextensions.xml" ]; then
    SAPCC_DETECTED=true
fi
if [ -f "manifest.json" ] && grep -q '"commerceSuiteVersion"' manifest.json 2>/dev/null; then
    SAPCC_DETECTED=true
fi
```

If `SAPCC_DETECTED=false`, skip `reviewer-sapcc-structural` silently (no warning, no log).

## Standard Agent Prompt Template

Each Wave 3 agent prompt includes the standard review scope PLUS the full Wave 0+1+2 context, with explicit instructions to CHALLENGE rather than reinforce:

```
ADVERSARIAL REVIEW — Wave 3

REVIEW SCOPE:
- Files to review: [list of changed files]
- Change context: [what was changed and why, if known]
- Repository: [current directory]

WAVE 0+1+2 FINDINGS (the consensus you are challenging):
[Insert $WAVE012_SUMMARY — loaded from $REVIEW_DIR/wave012-summary.md]

YOUR ROLE: You are an ADVERSARIAL reviewer. Your job is NOT to find new issues.
Your job is to CHALLENGE the findings above. Push back. Question severity.
Identify false positives. Flag overreactions. Surface tradeoffs that earlier
waves accepted without scrutiny.

INSTRUCTIONS:
1. Read the CLAUDE.md file(s) in this repository first
2. Read the code being reviewed
3. Read the Wave 0+1+2 findings carefully
4. For each finding from earlier waves, determine:
   a. AGREE — the finding is real, correctly classified, and worth fixing
   b. CHALLENGE — the finding is questionable (explain why)
   c. DOWNGRADE — the finding is real but over-classified (suggest correct severity)
   d. DISMISS — the finding is a false positive or not worth fixing (provide evidence)
5. Surface any tradeoffs or second-order effects the earlier waves missed
6. Be specific — vague disagreement is not useful

OUTPUT FORMAT:
### CHALLENGE: [One-line summary of what you're challenging]
**Original finding**: [Wave N, Agent, Severity: summary]
**Your verdict**: [AGREE | CHALLENGE | DOWNGRADE | DISMISS]
**Reasoning**: [Why you disagree or agree]
**Evidence**: [Code reference, real-world precedent, or logical argument]
**Suggested action**: [Keep as-is | Reduce to MEDIUM | Drop | Needs human judgment]
---
```

## Agent-Specific Prompt Additions

| Agent | Extra Instructions |
|-------|-------------------|
| `reviewer-contrarian` | Challenge every HIGH and CRITICAL finding. Are they actually important? Which are false positives? Which are over-classified? Look for findings where Wave 1+2 agents reinforced each other's bias rather than independently verifying. Question whether suggested fixes introduce new problems. |
| `reviewer-skeptical-senior` | Apply 10+ years of engineering experience. Which findings are theoretical risks that never manifest in practice? Which are textbook answers that don't apply to this codebase's scale/context? Flag "resume-driven" suggestions (over-engineering, premature optimization). Identify findings where the cure is worse than the disease. |
| `reviewer-user-advocate` | Focus exclusively on user impact. Does this change break existing users? Are migration paths safe? Are UX tradeoffs justified? Challenge findings that improve code quality at the expense of user experience. Flag findings that ignore backward compatibility. Question whether "fixing" something makes it harder for users. |
| `reviewer-meta-process` | Step back from individual findings. Is the overall approach correct? Should this PR be split into smaller PRs? Are the right problems being solved? Is the review itself focused on the right things? Flag cases where the review is bikeshedding on style while missing structural issues. Question whether the fix phase will create more churn than the findings are worth. |
| `reviewer-sapcc-structural` | **(SAPCC repos only)** Challenge findings through SAP Commerce Cloud structural lens. Do findings account for hybris extension lifecycle? Are suggested fixes compatible with the SAP build system? Do architecture recommendations respect CCv2 manifest constraints? Flag findings that would break extension wiring or data model migrations. |

## Wave Agreement Labels

After Wave 3 completes, every finding from the final report MUST carry one of these labels:

| Label | Meaning | Criteria | Action |
|-------|---------|----------|--------|
| **UNANIMOUS** | All waves agree | Wave 1+2 found it AND Wave 3 agrees (or does not challenge) | HIGH confidence — fix without hesitation |
| **MAJORITY** | Most waves agree | Wave 1+2 found it AND 1-2 Wave 3 agents challenge but others agree | Fix, but note the challenge in the report |
| **CONTESTED** | Wave 3 contradicts Wave 1+2 | Wave 1+2 found it BUT 3+ Wave 3 agents challenge or dismiss | Needs human judgment — present both arguments |

Wave 3 challenge verdicts:
- **AGREE** verdicts: Reinforces the original finding (increases confidence)
- **CHALLENGE** verdicts: Flags the finding for human review
- **DOWNGRADE** verdicts: Suggests lower severity (adjust if multiple Wave 3 agents agree)
- **DISMISS** verdicts: Suggests dropping the finding (only drop if 2+ Wave 3 agents dismiss AND no Wave 1+2 agent rated it CRITICAL)

If Wave 3 returns >90% AGREE on all findings, note in the report: "Wave 3 did not provide meaningful challenge — findings may benefit from human review."
