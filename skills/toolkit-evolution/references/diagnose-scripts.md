# DIAGNOSE Phase Scripts

> **Scope**: Concrete bash/Python commands for each step of Phase 1 DIAGNOSE and Phase 0 DISCOVER frequency check. Load this reference before running those phases. The SKILL.md contains the prose instructions and decision logic; this file contains the exact commands to execute.

---

## Discovery Frequency Check

Check the last discovery run date before starting Phase 0:

```bash
# Find the most recent discovery report
latest=$(ls -t evolution-reports/discovery-*.md 2>/dev/null | head -1)
if [ -z "$latest" ]; then
  echo "NO_PREVIOUS_DISCOVERY"
else
  # Extract date from filename: discovery-YYYY-MM-DD.md
  report_date=$(basename "$latest" | sed 's/discovery-//;s/\.md//')
  days_ago=$(( ($(date +%s) - $(date -d "$report_date" +%s)) / 86400 ))
  echo "Last discovery: $report_date ($days_ago days ago)"
  [ "$days_ago" -ge 30 ] && echo "DISCOVER_DUE" || echo "DISCOVER_SKIPPED"
fi
```

## DISCOVER Step 1: Briefing Data

Collect current toolkit state to brief all perspective agents:

```bash
# Skill count and category distribution
python3 -c "
import json
with open('skills/INDEX.json') as f:
    idx = json.load(f)
skills = idx.get('skills', {})
print(f'Total skills: {len(skills)}')
categories = {}
for s, meta in skills.items():
    cat = meta.get('category', 'uncategorized')
    categories[cat] = categories.get(cat, 0) + 1
for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
    print(f'  {cat}: {count}')
"

# Agent count
python3 -c "
import json
with open('agents/INDEX.json') as f:
    idx = json.load(f)
agents = idx.get('agents', {})
print(f'Total agents: {len(agents)}')
for a in sorted(agents):
    print(f'  {a}')
"
```

---

## DIAGNOSE Step 1: Learning DB Search Queries

Run these four queries to surface recent failures and routing mismatches:

```bash
python3 ~/.claude/scripts/learning-db.py search "routing decision" --min-confidence 0.0 --limit 20
python3 ~/.claude/scripts/learning-db.py search "routing gap mismatch reroute" --min-confidence 0.3 --limit 20
python3 ~/.claude/scripts/learning-db.py search "error pattern failure bug" --min-confidence 0.3 --limit 20
python3 ~/.claude/scripts/learning-db.py search "skill gap missing improvement" --min-confidence 0.3 --limit 20
```

Note: The first query uses `--min-confidence 0.0` because `effectiveness` entries (routing decisions recorded by /do) start at 0.5-0.6 confidence. The FTS5 tokenizer splits hyphens, so use space-separated terms, not `routing-decision`.

## DIAGNOSE Step 2: Git History Scan

```bash
# Frequent fixes to same areas suggest chronic issues
git log --oneline --since="2 weeks ago" | head -40

# Files changed most frequently (churn = potential problems)
git log --since="2 weeks ago" --pretty=format: --name-only | sort | uniq -c | sort -rn | head -20
```

## DIAGNOSE Step 3: Dream Report Check

```bash
ls -t ~/.claude/state/dream-* 2>/dev/null | head -5
# Then read the most recent dream-analysis-*.md file
```

## DIAGNOSE Step 3b: Dream Insight Cross-Validation

For each insight from the dream report, verify it still matches current state before treating it as a proposal signal. A dream report can be days old; the repo moves fast.

For each insight that names a specific file path:

```bash
# Verify the file exists
ls -la {path-mentioned-in-dream} 2>/dev/null || echo "STALE: path does not exist -- exclude this insight"
```

For each insight that claims recent activity on a file or area:

```bash
# Verify recent git activity matches the insight
git log --oneline --since="7 days ago" -- {path} 2>/dev/null | head -5
# If empty: the "recent activity" the dream described may be older than 7 days
```

**Staleness rules:**
- Name a file that no longer exists → mark STALE, exclude from opportunity list
- Claims "recent activity" but git log shows nothing in 7 days → mark STALE
- References a pattern already captured in a merged PR → check git log to confirm, then exclude (it is done)

Only forward dream insights where at least one current-state check passes.

## DIAGNOSE Step 4: Routing-Table Drift Check

```bash
python3 -c "
import json, re
with open('skills/INDEX.json') as f:
    idx = json.load(f)
index_skills = set(idx.get('skills', {}).keys())

with open('skills/do/references/routing-tables.md') as f:
    table_text = f.read()

missing = [s for s in sorted(index_skills) if s not in table_text]
if missing:
    print(f'{len(missing)} skill(s) in INDEX.json absent from routing-tables.md:')
    for s in missing:
        print(f'  {s}')
else:
    print('routing-tables.md is in sync with INDEX.json')
"
```

## DIAGNOSE Step 4b: Orphaned ADR Session Check

```bash
if [ -f ".adr-session.json" ]; then
  adr_id=$(python3 -c "
import json, sys
try:
    d = json.load(open('.adr-session.json'))
    print(d.get('adr_id', d.get('id', 'unknown')))
except Exception as e:
    print('PARSE_ERROR')
")
  adr_file="adr/ADR-${adr_id}.md"
  if [ "$adr_id" = "PARSE_ERROR" ]; then
    echo "WARNING: .adr-session.json exists but is unparseable -- flag as cleanup opportunity"
  elif [ ! -f "$adr_file" ]; then
    echo "WARNING: .adr-session.json references ADR-${adr_id} but $adr_file does not exist"
    echo "  Orphaned session file. Add 'Remove orphaned .adr-session.json' to the opportunity list."
  else
    echo "ADR session OK: ADR-${adr_id} exists at $adr_file"
  fi
else
  echo "No active ADR session file (OK)"
fi
```

## DIAGNOSE Step 4c: Stub Hook Audit

```bash
python3 -c "
import json, os, re
from pathlib import Path

settings_path = Path('.claude/settings.json')
if not settings_path.exists():
    print('No .claude/settings.json found -- skip hook stub audit')
else:
    with open(settings_path) as f:
        settings = json.load(f)
    hooks = settings.get('hooks', {})
    stubs = []
    for event, groups in hooks.items():
        for group in (groups if isinstance(groups, list) else [groups]):
            entries = group.get('hooks', [group]) if isinstance(group, dict) else [group]
            for entry in entries:
                cmd = entry.get('command', '') if isinstance(entry, dict) else str(entry)
                m = re.search(r'python3 [\"\x27]?([\w/.\$~-]+\.py)[\"\x27]?', cmd)
                if not m:
                    continue
                script = m.group(1).replace('\$HOME', str(Path.home()))
                script = os.path.expandvars(script)
                if not os.path.exists(script):
                    continue
                with open(script) as sf:
                    body = sf.read()
                if 'DISABLED' in body or 'empty_output()' in body:
                    desc = entry.get('description', '(no description)') if isinstance(entry, dict) else ''
                    stubs.append((event, os.path.basename(script), desc))
    if stubs:
        print(f'{len(stubs)} stub hook(s) registered in settings.json:')
        for ev, name, desc in stubs:
            print(f'  [{ev}] {name} -- {desc}')
        print('  Add stub deregistration to the opportunity list.')
    else:
        print('No stub hooks found (OK)')
"
```
