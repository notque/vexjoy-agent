#!/usr/bin/env python3
"""
Deterministic utility for creating and validating pipeline artifacts.

Implements the dual-layer artifact format from the Self-Improving Pipeline Generator ADR.
Layer 1 (manifest.json) is machine-readable metadata; Layer 2 (content.md) is human-readable output.

Usage:
    python3 scripts/artifact-utils.py create-manifest \\
        --schema research-artifact --step RESEARCH --phase 2 --status complete \\
        --outputs content.md agent-1-findings.md \\
        --inputs adr/pipeline-prometheus.md \\
        [--verdict PASS] [--tags prometheus metrics] [--ttl 24h]

    python3 scripts/artifact-utils.py validate-manifest manifest.json

    python3 scripts/artifact-utils.py validate-chain pipeline-spec.json

Exit codes:
    0 = success
    1 = validation failure
    2 = usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_SCHEMAS: set[str] = {
    "research-artifact",
    "structured-corpus",
    "decision-record",
    "generation-artifact",
    "execution-report",
    "verdict",
    "refinement-log",
    "comparison-report",
    "safety-record",
    "interaction-record",
    "orchestration-manifest",
    "state-record",
    "experiment-report",
    "learning-record",
    "pipeline-summary",
}

VALID_STATUSES: set[str] = {"complete", "partial", "failed", "blocked"}

VALID_VERDICTS: set[str] = {"PASS", "BLOCK", "NEEDS_CHANGES", "CRITICAL"}

# Schemas that use verdict fields
VERDICT_SCHEMAS: set[str] = {"verdict", "comparison-report", "safety-record"}

# Type compatibility matrix from the ADR Step Output Contracts.
# Maps step family -> (set of consumed schema types, set of produced schema types).
# A value of None means "any schema" (wildcard).

STEP_FAMILIES: dict[str, set[str]] = {
    "research-gathering": {"GATHER", "SCAN", "RESEARCH", "FETCH", "SEARCH", "SAMPLE"},
    "structuring": {"COMPILE", "MAP", "OUTLINE"},
    "decision-planning": {"ASSESS", "BRAINSTORM", "DECIDE", "RANK", "PLAN", "PRIME", "SYNTHESIZE"},
    "generation": {"GROUND", "GENERATE", "TEMPLATE", "ADAPT"},
    "validation": {"VALIDATE", "VERIFY", "CHARACTERIZE", "CONFORM", "LINT"},
    "review": {"REVIEW", "AGGREGATE"},
    "refinement": {"REFINE", "RETRY"},
    "git-release": {"EXECUTE", "MIGRATE", "STAGE", "COMMIT", "PUSH", "CREATE_PR"},
    "safety-guarding": {"GUARD", "SIMULATE", "SNAPSHOT", "ROLLBACK", "QUARANTINE"},
    "comparison-evaluation": {"COMPARE", "DIFF", "BENCHMARK", "ABLATE", "SHADOW"},
    "transformation": {"TRANSFORM", "NORMALIZE", "ENRICH", "EXTRACT"},
    "observation": {"MONITOR", "PROBE", "TRACE"},
    "domain-extension": {"LINT", "TEMPLATE", "MIGRATE", "CONFORM", "ADAPT"},
    "interaction": {"PROMPT", "NOTIFY", "APPROVE", "PRESENT"},
    "orchestration": {"DECOMPOSE", "DELEGATE", "CONVERGE", "SEQUENCE"},
    "state-management": {"CACHE", "RESUME", "HYDRATE", "PERSIST", "EXPIRE"},
    "experimentation": {"CANARY", "FUZZ", "REPLAY", "ABLATE", "SHADOW"},
    "learning-retro": {"WALK", "MERGE", "GATE", "APPLY", "CHECKPOINT"},
    "synthesis-reporting": {"REPORT", "OUTPUT", "CLEANUP"},
    "invariant": {"ADR"},
}


@dataclass
class TypeCompatibility:
    """Defines what schema types a step family consumes and produces."""

    consumes: set[str] | None  # None = any
    produces: str


# From the ADR Type Compatibility Matrix
TYPE_COMPAT: dict[str, TypeCompatibility] = {
    "research-gathering": TypeCompatibility(
        consumes=None,  # starts chains
        produces="research-artifact",
    ),
    "structuring": TypeCompatibility(
        consumes={"research-artifact"},
        produces="structured-corpus",
    ),
    "decision-planning": TypeCompatibility(
        consumes={"research-artifact", "structured-corpus", "comparison-report", "decision-record"},
        produces="decision-record",
    ),
    "generation": TypeCompatibility(
        consumes={"structured-corpus", "decision-record"},
        produces="generation-artifact",
    ),
    "validation": TypeCompatibility(
        consumes={"generation-artifact", "execution-report"},
        produces="verdict",
    ),
    "review": TypeCompatibility(
        consumes={"generation-artifact", "execution-report"},
        produces="verdict",
    ),
    "refinement": TypeCompatibility(
        consumes={"verdict", "generation-artifact"},
        produces="generation-artifact",
    ),
    "git-release": TypeCompatibility(
        consumes={"generation-artifact", "execution-report", "decision-record"},  # EXECUTE can follow PLAN
        produces="execution-report",
    ),
    "safety-guarding": TypeCompatibility(
        consumes=None,  # wraps any step
        produces="safety-record",
    ),
    "comparison-evaluation": TypeCompatibility(
        consumes=None,  # any two artifacts of same type
        produces="comparison-report",
    ),
    "transformation": TypeCompatibility(
        consumes=None,  # any artifact
        produces=None,  # produces different type (dynamic)
    ),
    "observation": TypeCompatibility(
        consumes={"execution-report", "safety-record", "decision-record", "research-artifact"},
        produces="research-artifact",
    ),
    "domain-extension": TypeCompatibility(
        consumes={"generation-artifact"},
        produces="verdict",
    ),
    "interaction": TypeCompatibility(
        consumes=None,  # any artifact (transparent)
        produces="interaction-record",
    ),
    "orchestration": TypeCompatibility(
        consumes={"decision-record", "structured-corpus"},
        produces="orchestration-manifest",
    ),
    "state-management": TypeCompatibility(
        consumes=None,  # any artifact
        produces="state-record",
    ),
    "experimentation": TypeCompatibility(
        consumes=None,  # any two artifacts + comparison-report
        produces="experiment-report",
    ),
    "learning-retro": TypeCompatibility(
        consumes=None,  # any artifact
        produces="learning-record",
    ),
    "synthesis-reporting": TypeCompatibility(
        consumes=None,  # any artifact(s)
        produces="pipeline-summary",
    ),
    "invariant": TypeCompatibility(
        consumes=None,  # starts chains
        produces="decision-record",
    ),
}

# Steps that are transparent — they produce a side-effect record but the primary
# data type passes through unchanged. Per the ADR:
# - Interaction steps produce Interaction Records as side effects
# - Safety steps wrap, they don't replace
# - Validation/review steps produce verdicts that gate but don't change data flow
TRANSPARENT_STEPS: set[str] = {
    "PROMPT",
    "NOTIFY",
    "APPROVE",
    "PRESENT",  # Interaction
    "GUARD",
    "SIMULATE",
    "SNAPSHOT",  # Safety (wraps, doesn't replace)
    "VALIDATE",
    "VERIFY",
    "CONFORM",
    "LINT",  # Validation (gates, doesn't replace)
    "REVIEW",
    "AGGREGATE",  # Review (gates, doesn't replace)
    "CHARACTERIZE",  # Captures behavior, doesn't change data flow
}

# Terminal schemas — nothing should consume these
TERMINAL_SCHEMAS: set[str] = {"pipeline-summary"}

# Chain-starting schemas — ADR must start the chain
CHAIN_STARTERS: set[str] = {"ADR"}

# Chain-ending steps
CHAIN_ENDERS: set[str] = {"OUTPUT", "REPORT", "CLEANUP"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step_to_family(step: str) -> str | None:
    """Resolve a step name to its family name."""
    for family, steps in STEP_FAMILIES.items():
        if step in steps:
            return family
    return None


def _iso_now() -> str:
    """Return current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _is_valid_iso8601(ts: str) -> bool:
    """Check if a string is a valid ISO 8601 timestamp."""
    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            datetime.strptime(ts, fmt)
            return True
        except ValueError:
            continue
    return False


# ---------------------------------------------------------------------------
# create-manifest
# ---------------------------------------------------------------------------


def create_manifest(args: argparse.Namespace) -> int:
    """Create a manifest.json and write it to stdout.

    Args:
        args: Parsed CLI arguments with schema, step, phase, status, outputs,
              and optional fields.

    Returns:
        Exit code: 0 on success, 2 on usage error.
    """
    if args.schema not in VALID_SCHEMAS:
        print(f"Error: unknown schema '{args.schema}'. Valid schemas: {sorted(VALID_SCHEMAS)}", file=sys.stderr)
        return 2

    if args.status not in VALID_STATUSES:
        print(f"Error: unknown status '{args.status}'. Valid statuses: {sorted(VALID_STATUSES)}", file=sys.stderr)
        return 2

    if args.verdict and args.verdict not in VALID_VERDICTS:
        print(f"Error: unknown verdict '{args.verdict}'. Valid verdicts: {sorted(VALID_VERDICTS)}", file=sys.stderr)
        return 2

    manifest: dict[str, Any] = {
        "schema": args.schema,
        "step": args.step,
        "phase": args.phase,
        "status": args.status,
        "outputs": args.outputs,
        "timestamp": _iso_now(),
    }

    # Optional fields — only include if provided
    if args.verdict is not None:
        manifest["verdict"] = args.verdict

    if args.metrics is not None:
        try:
            manifest["metrics"] = json.loads(args.metrics)
        except json.JSONDecodeError as e:
            print(f"Error: --metrics must be valid JSON: {e}", file=sys.stderr)
            return 2

    if args.inputs is not None:
        manifest["inputs"] = args.inputs

    if args.files_changed is not None:
        manifest["files_changed"] = args.files_changed

    if args.ttl is not None:
        manifest["ttl"] = args.ttl

    if args.tags is not None:
        manifest["tags"] = args.tags

    if args.error is not None:
        try:
            manifest["error"] = json.loads(args.error)
        except json.JSONDecodeError as e:
            print(f"Error: --error must be valid JSON: {e}", file=sys.stderr)
            return 2

    if args.parent is not None:
        manifest["parent"] = args.parent

    print(json.dumps(manifest, indent=2))
    return 0


# ---------------------------------------------------------------------------
# validate-manifest
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of manifest or chain validation."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _validate_manifest_data(data: dict[str, Any]) -> ValidationResult:
    """Validate a parsed manifest dict against the artifact schema.

    Args:
        data: Parsed JSON manifest data.

    Returns:
        ValidationResult with errors and warnings.
    """
    result = ValidationResult(valid=True)

    # Required fields
    required_fields = {
        "schema": str,
        "step": str,
        "phase": (int, float),
        "status": str,
        "outputs": list,
        "timestamp": str,
    }

    for field_name, expected_type in required_fields.items():
        if field_name not in data:
            result.errors.append(f"missing required field: '{field_name}'")
            result.valid = False
        elif not isinstance(data[field_name], expected_type):
            type_label = expected_type.__name__ if isinstance(expected_type, type) else str(expected_type)
            actual_label = type(data[field_name]).__name__
            result.errors.append(f"field '{field_name}' must be {type_label}, got {actual_label}")
            result.valid = False

    # If required fields are missing, stop early — further checks would fail
    if not result.valid:
        return result

    # Schema validation
    if data["schema"] not in VALID_SCHEMAS:
        result.errors.append(f"unknown schema: '{data['schema']}'. Valid: {sorted(VALID_SCHEMAS)}")
        result.valid = False

    # Status validation
    if data["status"] not in VALID_STATUSES:
        result.errors.append(f"unknown status: '{data['status']}'. Valid: {sorted(VALID_STATUSES)}")
        result.valid = False

    # Timestamp validation
    if not _is_valid_iso8601(data["timestamp"]):
        result.errors.append(f"invalid ISO 8601 timestamp: '{data['timestamp']}'")
        result.valid = False

    # Phase must be a non-negative integer
    if isinstance(data["phase"], float) and not data["phase"].is_integer():
        result.errors.append(f"phase must be an integer, got {data['phase']}")
        result.valid = False
    elif data["phase"] < 0:
        result.errors.append(f"phase must be non-negative, got {data['phase']}")
        result.valid = False

    # Outputs must be non-empty list of strings
    if not data["outputs"]:
        result.errors.append("outputs must be a non-empty list")
        result.valid = False
    elif not all(isinstance(o, str) for o in data["outputs"]):
        result.errors.append("all items in outputs must be strings")
        result.valid = False

    # Verdict validation — only meaningful for certain schemas
    if "verdict" in data and data["verdict"] is not None:
        if data["verdict"] not in VALID_VERDICTS:
            result.errors.append(f"unknown verdict: '{data['verdict']}'. Valid: {sorted(VALID_VERDICTS)}")
            result.valid = False

        if data.get("schema") not in VERDICT_SCHEMAS:
            result.warnings.append(
                f"verdict field is set but schema '{data.get('schema')}' is not a verdict-producing schema. "
                f"Expected one of: {sorted(VERDICT_SCHEMAS)}"
            )

    # Metrics must be an object if present
    if "metrics" in data and data["metrics"] is not None and not isinstance(data["metrics"], dict):
        result.errors.append(f"metrics must be an object, got {type(data['metrics']).__name__}")
        result.valid = False

    # Error must be an object with required fields if present
    if "error" in data and data["error"] is not None:
        if not isinstance(data["error"], dict):
            result.errors.append(f"error must be an object, got {type(data['error']).__name__}")
            result.valid = False
        else:
            for err_field in ("type", "message", "recoverable"):
                if err_field not in data["error"]:
                    result.errors.append(f"error object missing required field: '{err_field}'")
                    result.valid = False
            if "recoverable" in data["error"] and not isinstance(data["error"]["recoverable"], bool):
                result.errors.append("error.recoverable must be a boolean")
                result.valid = False

    # List-type optional fields
    for list_field in ("inputs", "files_changed", "tags"):
        if list_field in data and data[list_field] is not None:
            if not isinstance(data[list_field], list):
                result.errors.append(f"{list_field} must be a list, got {type(data[list_field]).__name__}")
                result.valid = False
            elif not all(isinstance(item, str) for item in data[list_field]):
                result.errors.append(f"all items in {list_field} must be strings")
                result.valid = False

    # TTL format check (simple pattern: digits + unit)
    if "ttl" in data and data["ttl"] is not None:
        if not isinstance(data["ttl"], str):
            result.errors.append(f"ttl must be a string, got {type(data['ttl']).__name__}")
            result.valid = False
        else:
            if not re.match(r"^\d+[smhd]$", data["ttl"]):
                result.errors.append(f"invalid ttl format: '{data['ttl']}'. Expected pattern like '24h', '7d', '30m'")
                result.valid = False

    # Parent must be a string if present
    if "parent" in data and data["parent"] is not None and not isinstance(data["parent"], str):
        result.errors.append(f"parent must be a string, got {type(data['parent']).__name__}")
        result.valid = False

    return result


def validate_manifest(args: argparse.Namespace) -> int:
    """Validate a manifest.json file.

    Args:
        args: Parsed CLI arguments with the manifest file path.

    Returns:
        Exit code: 0 if valid, 1 if invalid, 2 on usage error.
    """
    manifest_path = Path(args.manifest_file)
    if not manifest_path.exists():
        print(f"Error: file not found: {manifest_path}", file=sys.stderr)
        return 2

    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {manifest_path}: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print(f"Error: manifest must be a JSON object, got {type(data).__name__}", file=sys.stderr)
        return 1

    result = _validate_manifest_data(data)

    if result.warnings:
        for warning in result.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)

    if result.valid:
        print(f"VALID: {manifest_path}")
        return 0

    print(f"INVALID: {manifest_path}", file=sys.stderr)
    for error in result.errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# validate-chain
# ---------------------------------------------------------------------------


@dataclass
class PipelineStep:
    """A step in a pipeline specification."""

    step: str
    schema: str
    family: str | None = None


def _resolve_family_for_step(step_name: str) -> str | None:
    """Find the family a step belongs to, preferring non-domain-extension families.

    Some steps appear in multiple families (e.g., LINT in both validation and
    domain-extension). Prefer the primary family.
    """
    # Primary family mappings for ambiguous steps
    primary_overrides: dict[str, str] = {
        "EXECUTE": "git-release",
        "MIGRATE": "git-release",
        "LINT": "validation",
        "CONFORM": "validation",
        "TEMPLATE": "generation",
        "ADAPT": "generation",
        "ABLATE": "comparison-evaluation",
        "SHADOW": "comparison-evaluation",
    }

    if step_name in primary_overrides:
        return primary_overrides[step_name]

    return _step_to_family(step_name)


def validate_chain(args: argparse.Namespace) -> int:
    """Validate a pipeline chain specification for type compatibility.

    The pipeline spec is a JSON array of objects, each with 'step' (step name)
    and 'schema' (the schema type the step is expected to produce).

    Args:
        args: Parsed CLI arguments with the pipeline spec file path.

    Returns:
        Exit code: 0 if valid, 1 if invalid, 2 on usage error.
    """
    spec_path = Path(args.pipeline_spec)
    if not spec_path.exists():
        print(f"Error: file not found: {spec_path}", file=sys.stderr)
        return 2

    try:
        raw = json.loads(spec_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {spec_path}: {e}", file=sys.stderr)
        return 2

    if not isinstance(raw, list):
        print(f"Error: pipeline spec must be a JSON array, got {type(raw).__name__}", file=sys.stderr)
        return 2

    if len(raw) < 2:
        print("Error: pipeline must have at least 2 steps", file=sys.stderr)
        return 1

    # Parse steps
    steps: list[PipelineStep] = []
    errors: list[str] = []

    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            errors.append(f"step {i}: must be a JSON object")
            continue

        step_name = entry.get("step")
        schema_name = entry.get("schema")

        if not step_name:
            errors.append(f"step {i}: missing 'step' field")
            continue
        if not schema_name:
            errors.append(f"step {i}: missing 'schema' field")
            continue

        if schema_name not in VALID_SCHEMAS:
            errors.append(f"step {i} ({step_name}): unknown schema '{schema_name}'")
            continue

        family = _resolve_family_for_step(step_name)
        if family is None:
            errors.append(f"step {i} ({step_name}): unknown step name, not in any step family")
            continue

        steps.append(PipelineStep(step=step_name, schema=schema_name, family=family))

    if errors:
        print(f"INVALID: {spec_path}", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    # Rule: ADR starts the chain
    if steps[0].step not in CHAIN_STARTERS:
        errors.append(f"chain must start with ADR, got '{steps[0].step}'")

    # Rule: OUTPUT/REPORT ends the chain
    last_step = steps[-1]
    if last_step.step not in CHAIN_ENDERS:
        errors.append(f"chain must end with OUTPUT, REPORT, or CLEANUP, got '{last_step.step}'")

    # Rule: Pipeline Summary is terminal — nothing should consume it except end
    for i, step in enumerate(steps[:-1]):
        if step.schema == "pipeline-summary":
            errors.append(f"step {i} ({step.step}): pipeline-summary is terminal, cannot have subsequent steps")

    # Rule: No cycles — check for duplicate step names at same position
    step_positions: dict[str, list[int]] = {}
    for i, step in enumerate(steps):
        key = f"{step.step}:{step.schema}"
        if key not in step_positions:
            step_positions[key] = []
        step_positions[key].append(i)

    for key, positions in step_positions.items():
        if len(positions) > 1:
            # Allow duplicate steps only for VALIDATE (can appear multiple times in guarded chains)
            step_name = key.split(":")[0]
            if step_name not in {"VALIDATE", "VERIFY", "CHECKPOINT"}:
                errors.append(f"potential cycle: step '{key}' appears at positions {positions}")

    # Build the primary data flow — transparent steps pass through, so we track
    # the last non-transparent schema at each position.
    primary_flow: list[str] = []
    for step in steps:
        if step.step in TRANSPARENT_STEPS and primary_flow:
            # Transparent step: primary data passes through unchanged
            primary_flow.append(primary_flow[-1])
        else:
            primary_flow.append(step.schema)

    # Type compatibility checks — validate output -> input connections
    for i in range(len(steps) - 1):
        current = steps[i]
        next_step = steps[i + 1]

        current_family = current.family
        next_family = next_step.family

        if current_family is None or next_family is None:
            continue

        current_compat = TYPE_COMPAT.get(current_family)
        next_compat = TYPE_COMPAT.get(next_family)

        if current_compat is None or next_compat is None:
            continue

        # Check: the schema the current step produces must match what it claims
        if (
            current_compat.produces is not None
            and current.schema != current_compat.produces
            and current.step not in TRANSPARENT_STEPS
        ):
            errors.append(
                f"step {i} ({current.step}): family '{current_family}' produces "
                f"'{current_compat.produces}', but declared schema is '{current.schema}'"
            )

        # Check: next step can consume what flows to it
        if next_compat.consumes is not None:
            # For transparent steps, the data that actually flows is the primary data,
            # not the side-effect schema the step declares
            effective_schema = primary_flow[i]

            # Non-transparent next steps also check that what they consume matches
            # the primary flow, not the declared schema of a transparent predecessor
            if next_step.step in TRANSPARENT_STEPS:
                # Transparent consumers can accept anything (they just gate/wrap)
                continue

            if effective_schema not in next_compat.consumes:
                errors.append(
                    f"step {i + 1} ({next_step.step}): family '{next_family}' expects input from "
                    f"{sorted(next_compat.consumes)}, but primary data flow is "
                    f"'{effective_schema}' (from step {current.step})"
                )

    if errors:
        print(f"INVALID: {spec_path}", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    print(f"VALID: {spec_path} ({len(steps)} steps)")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="artifact-utils",
        description="Create and validate pipeline artifacts (dual-layer format).",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # -- create-manifest --
    create_parser = subparsers.add_parser(
        "create-manifest",
        help="Create a manifest.json and print to stdout",
        description="Generate a valid artifact manifest with required and optional fields.",
    )
    create_parser.add_argument(
        "--schema",
        required=True,
        choices=sorted(VALID_SCHEMAS),
        help="Schema archetype name",
    )
    create_parser.add_argument("--step", required=True, help="Pipeline step that produced this artifact")
    create_parser.add_argument("--phase", required=True, type=int, help="Phase number in the pipeline chain")
    create_parser.add_argument(
        "--status",
        required=True,
        choices=sorted(VALID_STATUSES),
        help="Artifact status",
    )
    create_parser.add_argument(
        "--outputs",
        required=True,
        nargs="+",
        help="Relative paths to content files produced",
    )
    create_parser.add_argument("--verdict", choices=sorted(VALID_VERDICTS), help="Verdict value (for verdict schemas)")
    create_parser.add_argument("--metrics", help="Metrics as a JSON string (e.g. '{\"score\": 0.9}')")
    create_parser.add_argument("--inputs", nargs="+", help="Relative paths to input files consumed")
    create_parser.add_argument("--files-changed", nargs="+", dest="files_changed", help="Files modified by this step")
    create_parser.add_argument("--ttl", help="Time-to-live for cached artifacts (e.g. '24h', '7d')")
    create_parser.add_argument("--tags", nargs="+", help="Tags for retrieval and relevance gating")
    create_parser.add_argument("--error", help="Error object as JSON string")
    create_parser.add_argument("--parent", help="ID of the parent artifact (for REFINE chains)")

    # -- validate-manifest --
    validate_parser = subparsers.add_parser(
        "validate-manifest",
        help="Validate a manifest.json file",
        description="Check that a manifest has all required fields, valid schemas, and correct types.",
    )
    validate_parser.add_argument("manifest_file", help="Path to the manifest.json file to validate")

    # -- validate-chain --
    chain_parser = subparsers.add_parser(
        "validate-chain",
        help="Validate a pipeline chain specification",
        description=(
            "Check type compatibility of a pipeline chain. Input is a JSON array of "
            "objects with 'step' and 'schema' fields."
        ),
    )
    chain_parser.add_argument("pipeline_spec", help="Path to the pipeline spec JSON file")

    return parser


def main() -> int:
    """Entry point for the artifact-utils CLI.

    Returns:
        Exit code: 0 on success, 1 on validation failure, 2 on usage error.
    """
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 2

    match args.command:
        case "create-manifest":
            return create_manifest(args)
        case "validate-manifest":
            return validate_manifest(args)
        case "validate-chain":
            return validate_chain(args)
        case _:
            parser.print_help()
            return 2


if __name__ == "__main__":
    sys.exit(main())
