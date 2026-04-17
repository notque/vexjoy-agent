#!/usr/bin/env python3
"""Build small rewrite batches from extracted negative instruction blocks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SYSTEM_PROMPT = (
    "Rewrite each markdown block into positive-action guidance. "
    "State what to do, why it matters, and preserve any detection or verification "
    "details already present. Do not expand scope. Return only JSON."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build low-token instruction rewrite batches")
    parser.add_argument("--input", required=True, help="Path to extracted block JSON")
    parser.add_argument("--output-dir", required=True, help="Directory for batch JSONL files")
    parser.add_argument("--max-tokens", type=int, default=3500, help="Approximate tokens per batch")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    blocks = data["blocks"]
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    batches: list[list[dict]] = []
    current: list[dict] = []
    current_tokens = 0

    for block in blocks:
        estimate = int(block["estimated_tokens"]) + 150
        if current and current_tokens + estimate > args.max_tokens:
            batches.append(current)
            current = []
            current_tokens = 0
        current.append(block)
        current_tokens += estimate

    if current:
        batches.append(current)

    for idx, batch in enumerate(batches, start=1):
        path = out_dir / f"batch-{idx:03d}.jsonl"
        with path.open("w", encoding="utf-8") as handle:
            for block in batch:
                record = {
                    "custom_id": block["id"],
                    "system": SYSTEM_PROMPT,
                    "input": {
                        "file": block["file"],
                        "line_start": block["line_start"],
                        "line_end": block["line_end"],
                        "heading": block["heading"],
                        "rewrite_goal": block["rewrite_goal"],
                        "replacement_schema": block["replacement_schema"],
                        "block_text": block["block_text"],
                    },
                    "required_output_schema": {
                        "id": block["id"],
                        "file": block["file"],
                        "line_start": block["line_start"],
                        "line_end": block["line_end"],
                        "block_sha256": block["block_sha256"],
                        "replacement": "markdown only",
                    },
                }
                handle.write(json.dumps(record) + "\n")

    print(
        json.dumps(
            {
                "total_blocks": len(blocks),
                "batch_count": len(batches),
                "output_dir": str(out_dir),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
