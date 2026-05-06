# Subagent Delegation for Per-Row Sprite Generation

## Boundary Rules

The per-row pipeline (Phase 4) splits work between a **parent orchestrator** and per-row **subagents**. Each role has a strict scope.

### Subagent Scope (one per row)

| Responsibility | Detail |
|---|---|
| Generate one row strip image | Calls `sprite_prompt build-row-strip` + `sprite_generate generate-spritesheet` |
| Return output path | Absolute path to the generated strip PNG |
| Return QA note | Free-text observation about generation quality |
| Mark own status | `row_job_status.py mark --status done\|failed` |

Subagents **must not**:
- Modify the manifest structure
- Touch other rows' outputs
- Run verifier gates (parent owns verification)
- Composite strips into the final sheet

### Parent Scope

| Responsibility | Detail |
|---|---|
| Manifest lifecycle | `row_job_status.py init` / `status` / `list-pending` |
| Canonical base generation | Phase A identity lock image |
| Subagent dispatch | Spawn one subagent per pending row |
| Recording | Log subagent results in manifest |
| Identity verification | Compare strip identity against canonical base |
| Compositing | `_composite_strips()` to stitch rows into sheet |
| Verifier gates | `_run_spritesheet_verifiers()` on final sheet |
| QA artifacts | `qa_artifacts.py` contact sheet + preview GIFs |
| Finalization & packaging | Metadata JSON, output directory structure |

## Manifest Format

File: `row-jobs.json` in the work directory.

```json
{
  "preset": "fighter",
  "total_rows": 9,
  "created_at": "2026-05-02T00:00:00+00:00",
  "jobs": [
    {
      "row_index": 0,
      "state": "idle",
      "frames": 6,
      "action": "combat stance guard breathing loop",
      "status": "pending",
      "updated_at": null,
      "output_path": null,
      "error": null
    }
  ]
}
```

## Status Transitions

```
pending -> in-progress -> done
                       -> failed -> pending (retry)
```

## Failure Handling

- Failed rows are retryable: parent calls `list-pending` and re-dispatches.
- After max retries, parent composites available rows and marks missing rows in metadata.
- Verifier gates run on the composited sheet regardless; missing rows surface as `verify_frames_have_content` failures.
