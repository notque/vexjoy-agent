# Routing Table Updater — Batch Mode

When invoked by `pipeline-scaffolder` Phase 4 (INTEGRATE), this skill operates in batch mode to register N skills and 0-1 agents in a single pass.

### Batch Input

The scaffolder provides a component list (from the Pipeline Spec):
```json
{
  "domain": "prometheus",
  "agent": { "name": "prometheus-grafana-engineer", "is_new": false },
  "skills": [
    { "name": "prometheus-metrics", "triggers": ["prometheus metrics", "PromQL", "recording rules"], "agent": "prometheus-grafana-engineer" },
    { "name": "prometheus-alerting", "triggers": ["prometheus alerting", "alert rules", "alertmanager"], "agent": "prometheus-grafana-engineer" },
    { "name": "prometheus-operations", "triggers": ["prometheus operations", "prometheus troubleshooting"], "agent": "prometheus-grafana-engineer" }
  ]
}
```

### Batch Process

1. **SCAN**: Skip full repo scan — use the provided component list directly
2. **EXTRACT**: Read YAML frontmatter from each listed skill file (verify they exist)
3. **GENERATE**: Create routing entries for ALL N skills in one pass. Check for inter-batch conflicts (skills within the same batch that share triggers).
4. **UPDATE**:
   - Add all N routing entries to `skills/do/references/routing-tables.md` in one write
   - If agent is new (`is_new: true`), add to `agents/INDEX.json`
   - Update `skills/do/SKILL.md` if force-route triggers are needed
   - Create `commands/{domain}-pipeline.md` manifest
5. **VERIFY**: Validate all N entries are present and correctly formatted

### Batch vs Single Mode

| Aspect | Single Mode | Batch Mode |
|--------|-------------|------------|
| Input | Full repo scan | Component list from Pipeline Spec |
| Scan | All skills/* and agents/* | Only listed components |
| Conflict check | Against existing entries | Against existing AND within batch |
| OUTPUT | One entry at a time | N entries in one pass |
| Invoked by | skill-creator | pipeline-scaffolder Phase 4 |
