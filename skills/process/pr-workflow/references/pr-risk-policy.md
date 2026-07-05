# PR Risk Classification Policy

Deterministic risk classification for pull requests. Maps changed paths and change size to a risk level (LOW / MEDIUM / HIGH) that drives review lane selection.

## Risk Domains

### HIGH-risk paths (always HIGH regardless of size)

Changes touching infrastructure, safety controls, or install surfaces:

| Path pattern | Rationale |
|---|---|
| `hooks/` | Safety hooks govern tool access and session behavior |
| `.github/` | CI workflows, PR templates, Actions config |
| `install.sh` | First-run installer; broad system side effects |
| `scripts/sync-*` | Post-merge sync to user config; add-only invariant |
| `.claude/settings.json` | Permissions, hook registration, tool allowlists |
| `.claude/settings.local.json` | Local permission overrides |
| `CLAUDE.md` (root) | Top-level policy file; governs all agent behavior |

### LOW-risk paths (LOW when no HIGH paths present and size is small)

Changes confined to documentation or registry metadata:

| Path pattern | Rationale |
|---|---|
| `docs/**` | Documentation only |
| `adr/**` | Architecture decision records (local-only) |
| `**/INDEX.json` | Generated registry indices |
| `skills/**/references/*.md` | Reference content (progressive disclosure) |
| `agents/**/references/*.md` | Agent reference content (progressive disclosure) |

### MEDIUM baseline

Everything else. Adjusted upward by size: changes exceeding the size ceiling become HIGH.

## Size Classification

Derived from `right-size-review.py` tier data:

| Size tier | Changed lines | Label |
|---|---|---|
| small | 1-200 | Routine change |
| medium | 201-800 | Substantial change |
| large | 801+ | Recommend split |

### Size ceiling

Above 800 changed lines (Tier 3+ territory from right-size-review), emit `recommend_split: true` with rationale. Large PRs increase review burden and merge-conflict risk disproportionately.

## Risk Resolution Rules

1. Any HIGH-risk path present => risk = HIGH (path dominance).
2. All paths LOW-risk AND size small => risk = LOW.
3. All paths LOW-risk AND size medium => risk = MEDIUM (size escalation).
4. All paths LOW-risk AND size large => risk = HIGH (size escalation).
5. Any MEDIUM-risk path AND size small => risk = MEDIUM.
6. Any MEDIUM-risk path AND size medium/large => risk = MEDIUM (size large adds recommend_split).
7. Path-based HIGH always wins; size can escalate but path dominance takes priority.

Simplified: HIGH path wins. Otherwise, start at the highest path risk and let size escalate (LOW->MEDIUM->HIGH).

## Review Lanes

| Risk | Review lane | Action |
|---|---|---|
| LOW | Quick single review | `parallel-code-review` (3 agents) |
| MEDIUM | Full right-size-review roster | Tier-appropriate waves from `right-size-review.py` |
| HIGH | Full roster + operator sign-off | Right-size-review roster + require operator sign-off note in PR body |

When `recommend_split` is true, surface the recommendation before review dispatch. The reviewer proceeds with the current PR but notes the split guidance in findings.

## Script Interface

```
python3 scripts/pr-risk-classify.py --base main
python3 scripts/pr-risk-classify.py --base main --head HEAD
```

Output: JSON to stdout, exit 0 always (warn-only gate per PHILOSOPHY.md).

```json
{
  "risk": "medium",
  "size_tier": "small",
  "total_lines": 142,
  "file_count": 8,
  "recommend_split": false,
  "reasons": ["8 files changed across medium-risk paths"],
  "high_risk_files": [],
  "review_lane": "full-roster"
}
```
