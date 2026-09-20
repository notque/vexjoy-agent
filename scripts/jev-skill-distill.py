#!/usr/bin/env python3
"""Run a 50-head Jev distillation review over one skill directory."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import jev_transport

BUNDLE_COUNT = 50
QUESTIONS_PER_BUNDLE = 1
MAX_BUNDLE_CHARS = 72_000
TEXT_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".csv"}


def _pieces(skill_dir: Path) -> list[dict[str, str]]:
    files = [skill_dir / "SKILL.md"]
    refs = skill_dir / "references"
    if refs.is_dir():
        files.extend(
            path for path in sorted(refs.rglob("*")) if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES
        )

    pieces: list[dict[str, str]] = []
    for path in files:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(skill_dir))
        blocks = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        if not blocks:
            blocks = [""]
        for block_index, block in enumerate(blocks):
            for part_index, start in enumerate(range(0, max(1, len(block)), MAX_BUNDLE_CHARS)):
                label = f"{rel}#block-{block_index + 1}"
                if len(block) > MAX_BUNDLE_CHARS:
                    label += f"-part-{part_index + 1}"
                pieces.append({"path": label, "text": block[start : start + MAX_BUNDLE_CHARS]})
    return pieces


def _bundles(pieces: list[dict[str, str]]) -> list[list[dict[str, str]]]:
    bundles: list[list[dict[str, str]]] = [[] for _ in range(BUNDLE_COUNT)]
    sizes = [0] * BUNDLE_COUNT
    for piece in sorted(pieces, key=lambda item: len(item["text"]), reverse=True):
        target = min(range(BUNDLE_COUNT), key=sizes.__getitem__)
        bundles[target].append(piece)
        sizes[target] += len(piece["text"])
    if pieces:
        # Small skills still need evidence for all 50 independent heads. Reuse a
        # local block rather than asking Jev to judge an empty state.
        for index, bundle in enumerate(bundles):
            if not bundle:
                bundles[index] = [pieces[index % len(pieces)]]
    return bundles


def _questions(bundle_index: int) -> dict[str, dict[str, object]]:
    prefix = f"bundle_{bundle_index + 1}"
    definitions = {
        "general": (
            "Does this bundle substantially explain general knowledge a capable current coding model already knows, "
            "rather than repository-specific, domain-specific, or workflow-specific knowledge?"
        ),
        "unique": (
            "Does this bundle contain rare facts, local contracts, hard-won failure knowledge, exact commands, "
            "or domain distinctions that would materially improve work and should be preserved?"
        ),
        "duplicate": (
            "Is substantial guidance in this bundle repeated elsewhere within the same bundle or restated in "
            "multiple forms without changing an action?"
        ),
        "actionable": (
            "Does the specific guidance in this bundle change a decision, command, validation gate, handoff, "
            "or failure response compared with relying on normal model competence?"
        ),
        "brittle": (
            "Does this bundle contain stale, exhaustive, overly procedural, or brittle prescription that is more "
            "likely to constrain a capable model incorrectly than to improve its result?"
        ),
    }
    name = tuple(definitions)[bundle_index % len(definitions)]
    return {
        f"{prefix}_{name}": {
            "type": "noul",
            "instructions": definitions[name],
            "criteria": {
                "true": "The condition is materially present in `bundle.files`.",
                "false": "The condition is absent or only incidental in `bundle.files`.",
            },
        }
    }


def review(skill_dir: Path) -> dict[str, object]:
    pieces = _pieces(skill_dir)
    bundles = _bundles(pieces)
    reviews = []
    for index, bundle in enumerate(bundles):
        state = {
            "skill": skill_dir.name,
            "goal": (
                "Distill this skill so it retains knowledge and constraints that materially improve a capable "
                "current model, while removing generic instruction and duplication."
            ),
            "bundle": {"files": bundle},
        }
        questions = _questions(index)
        response = jev_transport.evaluate(state, questions, timeout=45)
        reviews.append(
            {
                "bundle": index + 1,
                "paths": [item["path"] for item in bundle],
                "chars": sum(len(item["text"]) for item in bundle),
                "answers": response.get("answers", response),
            }
        )
    return {
        "skill_dir": str(skill_dir),
        "files_reviewed": len(pieces),
        "questions": BUNDLE_COUNT * QUESTIONS_PER_BUNDLE,
        "bundles": reviews,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("skill_dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = review(args.skill_dir.resolve())
    rendered = json.dumps(result, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
