# Ambiguity triage

Classify each unresolved choice by impact, reversibility, evidence source, and
dependency on other choices.

| Condition | Action |
|---|---|
| low impact, reversible, or fixed by repository convention | state assumption and proceed |
| another person owns the fact or authority | use `pl-human-source-elicitation.md` |
| one high-impact choice owned by the current user | ask one question with a recommendation |
| multiple linked high-impact choices | use `pl-depth-first-interview.md` |
| observation can decide | use `pl-empirical-prototype.md` |

Do not ask a preference question that repository evidence already answers.
