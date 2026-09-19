# Dissolving a skill into a Jev program

## Method

1. List every phase of the skill.
2. Classify each: program (deterministic), Jev (judgment), LLM (generation), orchestration.
3. Judgment phases become Noul/Choice/Score questions with hard-case criteria.
4. Deterministic phases stay as code.
5. Any generation phase keeps an LLM that receives Jev's decisions as `prior_results`.
6. Write a pure policy function with named thresholds. This is the dissolved skill's contract.
7. Prove agreement on the skill's labeled cases before deleting the SKILL.md.

## Worked example: joy-check

**Why this skill.** joy-check has four phases. Three are fully deterministic or judgment. Only the `--fix` rewrite in Phase 3 requires generation. Without `--fix`, the entire skill dissolves into a program plus Jev.

### Phase table

| Phase | Current tier | Dissolved tier | Reason |
|---|---|---|---|
| 0: Detect mode | Program | Program | file path matching, flag parsing |
| 1: Pre-filter | Program | Program | regex/grep scan |
| 2: Analyze | LLM | Jev | score each item against rubric dimensions |
| 3: Report (scoring) | LLM | Program + Jev | average scores (program), classify overall (Jev) |
| 3: Report (fix mode) | LLM | LLM | rewriting flagged items requires generation |

### Jev question set

Phase 2 currently uses an LLM to evaluate each paragraph or instruction against a rubric. The rubric has named dimensions. Each dimension becomes a Jev question.

**Writing mode** (per paragraph):

| Question ID | Type | Instruction |
|---|---|---|
| `curiosity` | Noul | Does the paragraph frame the experience through curiosity or exploration? |
| `grievance` | Noul | Does the paragraph frame the experience through accusation, blame, or resentment? |
| `defensive` | Noul | Does the paragraph contain defensive disclaimers or reluctant generosity? |
| `overall_joy` | Score | How does this paragraph sit on the joy-grievance spectrum? |

**Instruction mode** (per instruction):

| Question ID | Type | Instruction |
|---|---|---|
| `positive_frame` | Noul | Does the instruction tell the reader what to do (not what to avoid)? |
| `prohibition` | Noul | Is the instruction framed as a prohibition (NEVER, do NOT, must NOT, FORBIDDEN)? |
| `subordinate_neg` | Noul | Is a negative clause subordinate to a positive instruction (e.g., "use X, not Y")? |

### Policy function

```python
# Named thresholds — the dissolved skill's contract
GRIEVANCE_T, CURIOSITY_FLOOR = 0.6, 0.3
PROHIBITION_T, SUBORDINATE_PASS = 0.7, 0.6
OVERALL_PASS, STRICT_FLOOR = 60, 60

def score_item_writing(a: dict) -> dict:
    """Score one paragraph in writing mode. Pure function."""
    g, c, d = a["grievance"]["noul"], a["curiosity"]["noul"], a["defensive"]["noul"]
    normalized = round((1 - a["overall_joy"]["score"] / 2) * 100)
    flagged = g > GRIEVANCE_T or c < CURIOSITY_FLOOR or d > GRIEVANCE_T
    label = "GRIEVANCE" if g > GRIEVANCE_T else ("CAUTION" if flagged else "JOY")
    return {"score": normalized, "label": label, "flagged": flagged}

def score_item_instruction(a: dict) -> dict:
    """Score one instruction in instruction mode. Pure function."""
    pr, pos, sub = a["prohibition"]["noul"], a["positive_frame"]["noul"], a["subordinate_neg"]["noul"]
    if pr > PROHIBITION_T and sub > SUBORDINATE_PASS:
        return {"score": 85, "label": "PASS", "flagged": False}
    if pr > PROHIBITION_T:
        return {"score": 20, "label": "NEGATIVE", "flagged": True}
    s = round(pos * 100)
    return {"score": s, "label": "PASS" if s >= 60 else "CAUTION", "flagged": s < 60}

def policy(items: list[dict], strict: bool = False) -> dict:
    """Overall pass/fail. Pure function, no Jev calls."""
    scores = [r["score"] for r in items]
    avg = round(sum(scores) / len(scores)) if scores else 0
    ok = avg >= OVERALL_PASS and not any(r["label"] == "GRIEVANCE" for r in items)
    if strict:
        ok = ok and all(r["score"] >= STRICT_FLOOR for r in items)
    return {"score": avg, "passed": ok, "items": items}
```

### What stays in the LLM

Only `--fix` mode: rewriting a flagged paragraph to shift its framing while preserving substance. The LLM receives `prior_results` (which items were flagged, why, at what score) and rewrites only those items. It does not re-judge.

### Proving agreement

Run the dissolved program on joy-check's existing labeled cases (rubric examples in `references/writing-rubric.md` and `references/instruction-rubric.md`). Compare each item's score and label against the rubric's expected classification. The dissolved version ships only when agreement matches or exceeds the LLM-based version on those cases.
