---
title: Migration Planning — Cost Estimation, Phased Rollout, Rollback Plans, Data Migration Patterns
domain: build-vs-buy
level: 3
skill: build-vs-buy
---

# Migration Planning Reference

> **Scope**: Migration cost estimation frameworks, phased rollout templates, rollback plan design, and data migration patterns for build-vs-buy transitions. Use when switching from an existing solution — whether migrating FROM a custom-built system to a vendor, or FROM one vendor to another. Covers the gap between "we decided to switch" and "we are fully switched."
> **Version range**: Framework-agnostic — patterns apply to database migrations, SaaS replacements, and internal system cutover equally.
> **Generated**: 2026-04-09 — validate migration effort estimates against your specific data volume and integration count before using.

---

## Overview

Migration cost is the most underestimated dimension of build-vs-buy decisions. The TCO framework (tco-framework.md) includes a migration cost line item, but that line is typically a single number arrived at quickly. Migrations fail most often not because the new system is bad, but because migration planning underestimated the data complexity, left no rollback path, and used a big-bang cutover that put the whole business at risk simultaneously. This reference gives migration the depth it deserves.

---

## Migration Cost Estimation Framework

Fill this out BEFORE finalizing the build-vs-buy decision. Migration cost is a critical input to the TCO comparison.

### Phase 1: Inventory Assessment

```
## Migration Inventory

### Data Volume
- Total records to migrate: ___
- Data size (GB/TB): ___
- Age range of data: ___ years
- Data quality assessment: [Clean / Mixed / Poor — check for nulls, duplicates, format inconsistencies]

### Schema Complexity
- Number of tables/entities to migrate: ___
- Many-to-many relationships requiring transformation: ___
- Denormalized columns requiring normalization (or vice versa): ___
- Custom data types not supported by target: ___

### Integration Count
- APIs consuming data from current system: ___
- APIs producing data to current system: ___
- Webhooks/events being sent or received: ___
- Batch jobs or ETL pipelines touching current system: ___

### User Impact
- Estimated users affected by cutover: ___
- Acceptable downtime window: [None / <1 hour / <4 hours / Scheduled maintenance]
- Geographic distribution (time zone complexity): ___
```

### Phase 2: Effort Estimation by Component

| Migration Component | Effort Level | Hours Estimate | Dependencies |
|---------------------|-------------|----------------|--------------|
| Schema mapping document | Low | 8-16 hrs | Inventory complete |
| Data transformation scripts | Low/Med/High | ___ hrs | Schema mapping |
| Historical data migration (one-time) | Med/High | ___ hrs | Transform scripts |
| Delta sync (catch up during cutover) | Med/High | ___ hrs | Historical complete |
| API client updates (per integration) | Low per integration | ___ × ___ hrs | New system ready |
| Webhook reconfiguration | Low | 4-8 hrs | New system ready |
| Auth/credential rotation | Low | 4-8 hrs | All integrations |
| User communication and training | Low/Med | 8-40 hrs | Launch date set |
| Parallel run validation | Med | 16-40 hrs | Both systems live |
| Data reconciliation audit | Med | 8-24 hrs | Migration complete |
| **Total** | | **___ hrs** | |

**Complexity multipliers**:
- Data quality is Poor: multiply transform estimate × 2.5
- Zero downtime required: multiply cutover estimate × 2
- 10+ integrations: add 20% to total (coordination overhead)
- No migration precedent in team: multiply total × 1.5 (learning curve)

---

## Phased Rollout Template

Use for any migration affecting more than 10 users or involving more than 50K records. Big-bang cutover is the most common migration failure pattern.

### Phase Gate Structure

```
## Migration Rollout Plan: [System Name]

### Phase 0: Foundation (weeks 1-2)
- [ ] New system provisioned in production environment
- [ ] Data transformation scripts written and reviewed
- [ ] Rollback plan documented and tested in staging
- [ ] Monitoring alerts configured for new system
- [ ] Communication plan drafted

Gate criteria: Staging migration completed successfully. Rollback drill completed in under 15 minutes.

---

### Phase 1: Shadow Mode (weeks 3-4)
New system receives all writes but is NOT the system of record.

- [ ] New system receiving writes (via dual-write or event forwarding)
- [ ] Data reconciliation running daily: [old system vs. new system comparison]
- [ ] Divergence rate below threshold: ___% acceptable drift
- [ ] No reads redirected yet

Gate criteria: Zero data divergence for 5 consecutive business days. Performance benchmarks met.

---

### Phase 2: Pilot Group (weeks 5-6)
Small group of users reads from and writes to new system. Old system remains for everyone else.

- [ ] Pilot group selected: [internal team / power users / specific account]
- [ ] Pilot users notified and trained
- [ ] Support channel for pilot feedback established
- [ ] Escalation path to rollback pilot users only (not full revert)

Gate criteria: Pilot group satisfaction ≥ ___ (survey). Zero data loss incidents. No blocking bugs.

---

### Phase 3: Progressive Rollout (weeks 7-10)
Expand in cohorts. Use percentage-based or account-based expansion.

| Cohort | % of Users | Start Date | Gate Metric |
|--------|-----------|------------|-------------|
| Cohort 1 | 10% | ___ | Error rate < 0.1%, 48 hours stable |
| Cohort 2 | 25% | ___ | Error rate < 0.1%, 72 hours stable |
| Cohort 3 | 50% | ___ | Zero P1 incidents, 1 week stable |
| Cohort 4 | 100% | ___ | All previous gates passed |

Gate criteria per cohort: Error rate below threshold for minimum stable period.

---

### Phase 4: Cutover and Decommission (weeks 11-14)
Old system moved to read-only, then decommissioned.

- [ ] Old system made read-only (writes disabled)
- [ ] Final data reconciliation audit run
- [ ] All integrations confirmed pointing to new system
- [ ] Old system retained in backup mode for [30 / 60 / 90 days]
- [ ] Decommission scheduled: ___

Gate criteria: Full week of operation with 100% of users on new system, zero rollback requests, data reconciliation showing 100% match.
```

---

## Rollback Plan Design

Every migration phase must have a rollback procedure. Design rollback BEFORE starting migration.

### Rollback Decision Matrix

| Trigger | Rollback Scope | Time to Execute | Authorization Required |
|---------|---------------|----------------|----------------------|
| Data corruption detected | Full rollback | < 30 minutes | On-call engineer |
| Error rate > 1% for > 15 minutes | Cohort rollback | < 15 minutes | On-call engineer |
| P1 incident lasting > 1 hour | Full rollback | < 30 minutes | Engineering lead |
| User data loss confirmed | Full rollback + incident | < 15 minutes | Any engineer |
| Performance degradation > 3× baseline | Cohort rollback | < 15 minutes | On-call engineer |

### Rollback Procedure Template

```
## Rollback Procedure: [Migration Phase N]

### Pre-conditions for rollback
- [ ] [Old system is still running and current]
- [ ] [Reverse sync scripts are ready and tested]
- [ ] [Communication template is drafted]

### Rollback Steps (must complete in < ___ minutes)

1. [ ] Declare rollback decision in incident channel (#incident or #migration)
2. [ ] Switch traffic back to old system:
       [specific command or feature flag change]
3. [ ] Verify old system is serving traffic:
       [curl or health check command]
4. [ ] Disable writes to new system:
       [specific command]
5. [ ] Run delta sync (new system → old system) for any writes that occurred:
       [command or script path]
6. [ ] Verify data consistency:
       [reconciliation script command]
7. [ ] Notify affected users:
       [template: "We've temporarily reverted [feature] due to [issue]. Your data is intact."]
8. [ ] Post-rollback audit (within 24 hours):
       - Root cause of rollback trigger
       - Data integrity confirmation
       - Next steps for re-attempt

### Rollback drill schedule
Run this procedure in staging: [quarterly / before each phase gate]
Last drill date: ___
Drill completion time: ___ minutes (target: < ___ minutes)
```

**Non-negotiable rollback rules**:
1. Rollback procedures must be tested in staging before production cutover
2. Any engineer on the team must be able to execute the rollback, not just the migration lead
3. Rollback must be possible without database admin access (use application-level controls)
4. If rollback time exceeds the acceptable downtime window, the architecture must change before proceeding

---

## Data Migration Patterns

### Pattern 1: Extract-Transform-Load (ETL) — Offline Migration

Use when: Historical data needs format transformation. Downtime is acceptable. Volume < 100GB.

```
## ETL Migration Script Structure

# Step 1: Extract from source
extract_query = """
SELECT id, user_id, created_at, metadata_json
FROM old_table
WHERE migrated = FALSE
LIMIT {batch_size}
"""

# Step 2: Transform
def transform_row(row):
    return {
        'external_id': str(row['id']),
        'owner': row['user_id'],
        'created_at': row['created_at'].isoformat(),
        # Flatten JSON: old_table.metadata_json.settings → new_table.settings
        'settings': json.loads(row['metadata_json']).get('settings', {}),
    }

# Step 3: Load in batches (never row-by-row in production)
def load_batch(transformed_rows):
    # Use bulk insert API or COPY command — not INSERT per row
    new_system_api.bulk_create(transformed_rows)
    mark_source_as_migrated(transformed_rows)

# Idempotency: mark migrated=TRUE in source after successful load
# Resume: re-run will skip migrated=TRUE rows automatically
```

**Checklist**:
```
[ ] Script is idempotent — safe to re-run without duplicating data
[ ] Processes data in configurable batches (default: 1,000 records)
[ ] Writes migration log with timestamp, batch_id, count, and errors
[ ] Handles NULL values in every column explicitly
[ ] Has a dry-run mode that transforms but does not load
[ ] Error handling: logs failed rows, does not abort entire batch on single failure
```

### Pattern 2: Change Data Capture (CDC) — Zero-Downtime Migration

Use when: Zero downtime required. Volume > 100GB. Migration window is weeks.

```
## CDC Migration Phases

Phase A: Historical load
- Run ETL (Pattern 1) on all data older than T₀ (cutoff timestamp)
- Mark T₀ explicitly: migration_start_timestamp = NOW()

Phase B: Change capture (parallel operation)
- Enable CDC on source: capture all INSERT/UPDATE/DELETE after T₀
- Forward changes to new system via event queue or direct replication
- Both systems diverge until cutover but CDC closes the gap continuously

Phase C: Delta reconciliation
- Stop writes to old system (maintenance window, or use DB-level read-only flag)
- Drain the CDC queue completely (time estimate: queue_size / event_throughput)
- Run final reconciliation: count matches, spot-check 1% of rows

Phase D: Cutover
- Switch application traffic to new system
- Old system enters read-only mode
- Total downtime = drain time + validation time (typically 1-15 minutes)
```

### Pattern 3: Dual-Write — Low-Risk Incremental Migration

Use when: Cannot accept rollback. New and old systems must stay in sync during transition.

```
## Dual-Write Architecture

# Application layer writes to BOTH systems simultaneously
def save_record(data):
    old_result = old_system.save(data)       # Primary (source of truth)
    try:
        new_result = new_system.save(data)   # Shadow (not yet authoritative)
    except Exception as e:
        log_error('dual-write-shadow-failure', e, data)
        # Do NOT fail the request — old system is primary
        return old_result
    
    compare_results(old_result, new_result)  # Log divergences
    return old_result                         # Return old system result during shadow phase

# When ready to flip:
def save_record_post_cutover(data):
    new_result = new_system.save(data)       # New system is now primary
    try:
        old_result = old_system.save(data)   # Old system in shadow mode
    except Exception as e:
        log_error('dual-write-legacy-failure', e, data)
    return new_result                         # Return new system result
```

**Dual-write checklist**:
```
[ ] Failures in shadow system DO NOT fail the primary request
[ ] Divergences are logged to monitoring, not silently ignored
[ ] Shadow system has separate error budget (does not pollute primary alerts)
[ ] Cutover is a single feature flag change, not a code deployment
[ ] Old system write path can be disabled independently of read path
```

---

## Patterns to Detect and Fix
<!-- no-pair-required: section header, not an individual anti-pattern -->

### Big-bang cutover
**What it looks like**: All users moved from old to new system in a single weekend deployment. No pilot, no phased rollout, no shadow period.
**Why wrong**: Big-bang cutover concentrates all migration risk into a single point. If anything goes wrong — and something always does — the entire user base is affected simultaneously and the rollback affects the entire user base.
**Detection**: If the migration plan says "go live on [date]" with no mention of cohorts, pilot groups, or shadow periods, it is a big-bang plan.
**Do instead**: Structure every migration affecting more than 10 users as a phased rollout: pilot group first, then progressive cohorts. Each cohort is a checkpoint where you can halt, observe, and correct before proceeding.
**Fix**: Any migration affecting more than 10 users or more than 30 days of data requires at minimum a pilot group phase before full rollout.

### Rollback plan written after cutover
**What it looks like**: Migration proceeds, and then someone asks "how do we roll back if this fails?" The answer is "we'd figure it out."
**Why wrong**: Under incident pressure, ad-hoc rollback takes 4-10× longer than a planned rollback and introduces additional errors. The migration should not start until rollback has been tested.
**Do instead**: Treat rollback as a phase gate. Write and drill the rollback procedure for Phase 1 in staging before Phase 1 begins. The question "how do we roll this back?" must have a documented, tested answer before any production traffic moves.
**Fix**: Rollback is a phase gate — migration to Phase 1 cannot proceed until rollback procedure for Phase 1 has been documented AND drilled in staging.

### Migrating data quality problems forward
**What it looks like**: Source database has 15% null values in required fields, duplicate records, and inconsistent date formats. Migration copies all of this into the new system verbatim.
**Why wrong**: Migrating dirty data validates bad data in the new system and causes downstream failures that are blamed on the new system, not the migration.
**Do instead**: Run a data quality assessment before any migration work begins. For every failing field, define the transformation rule before writing a single migration script. Data cleaning is part of the transform step, not a post-migration cleanup task.
**Fix**: Before migration begins, run a data quality assessment (null counts, duplicate counts, format inconsistency counts). For every failing field, define the transformation rule. Data cleaning happens in the transform step, not as an afterthought.

### Testing migration on wrong data volume
**What it looks like**: Migration scripts tested on a 1,000-row staging dataset. Production has 80 million rows. Performance characteristics are completely different.
**Why wrong**: Migration performance is non-linear. Scripts that complete in 2 minutes on 1K rows may take 8 hours on 80M rows due to index contention, network I/O, and API rate limits.
**Do instead**: Test migration on an anonymized 5% sample of production data in staging. Measure actual duration, then extrapolate. If 5% takes 30 minutes, plan for 10+ hours in production and schedule the cutover window accordingly.
**Fix**: Migrate a random 5% sample of production data (anonymized) in a staging environment and extrapolate timing. If 5% takes 30 minutes, production will take 10+ hours — plan accordingly.

---

## Detection Commands Reference

```bash
# Assess source data quality before migration
python3 -c "
import sqlite3  # replace with your DB connector
conn = sqlite3.connect('source.db')
cursor = conn.cursor()

# Null count per column (replace table_name and column list)
cursor.execute('''
SELECT
  COUNT(*) as total,
  SUM(CASE WHEN user_id IS NULL THEN 1 ELSE 0 END) as null_user_id,
  SUM(CASE WHEN email IS NULL OR email = '' THEN 1 ELSE 0 END) as null_email
FROM users
''')
print(cursor.fetchone())
conn.close()
"

# Estimate migration duration from batch test
python3 -c "
import time
BATCH_SIZE = 1000
TOTAL_RECORDS = 5_000_000  # replace with actual count

# Time a sample batch (replace with actual migration function)
start = time.time()
# migrate_batch(sample_rows)  # your function here
elapsed = time.time() - start

batches = TOTAL_RECORDS / BATCH_SIZE
total_seconds = elapsed * batches
print(f'Estimated total time: {total_seconds/3600:.1f} hours')
print(f'Estimated completion: {total_seconds/60:.0f} minutes')
"

# Check dual-write divergence rate
# (Assuming divergences are logged to a file or monitoring system)
grep "dual-write-shadow-failure" /var/log/app.log | \
  python3 -c "
import sys
lines = sys.stdin.readlines()
print(f'Shadow failures in log: {len(lines)}')
"
```

---

## See Also

- `tco-framework.md` — TCO calculation that includes migration cost as a line item
- `vendor-evaluation.md` — data portability and export capability checklist
- `skills/project-evaluation/references/feasibility-scoring.md` — technical feasibility assessment for migration complexity
