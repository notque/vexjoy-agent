"""The Model choice block is one policy stated in two skills: `/do` and `/d`.

Both load independently, so each carries the block. This test keeps the two
copies byte-identical and pinned to the tiers `build-dispatch.py` enforces.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
START = "Set `model` from the task type, not `inherit`."
# Owner, verbatim, 2026-11-09. Every file that states the policy quotes it with the date.
OWNER_MEDIUM_ORDER = '2026-11-09: "Also I prefer opus 5.5 medium over high"'
POLICY_FILES = (
    "skills/meta/do/SKILL.md",
    "skills/meta/d/SKILL.md",
    "skills/meta/do/references/model-selection.md",
    "skills/meta/d/references/model-task-fit.md",
    "docs/REFERENCE.md",
    "scripts/build-dispatch.py",
)
END = "`skills/meta/d/references/model-task-fit.md`."


def _block(skill: str) -> str:
    text = (REPO_ROOT / "skills" / "meta" / skill / "SKILL.md").read_text(encoding="utf-8")
    assert text.count(START) == 1, f"{skill}: Model choice block start missing or repeated"
    start = text.index(START)
    return text[start : text.index(END, start) + len(END)]


def test_model_choice_block_is_identical_in_do_and_d() -> None:
    assert _block("do") == _block("d")


def test_model_choice_block_states_the_decided_tiers_and_ladder() -> None:
    block = _block("do")
    for required in (
        "low-risk = haiku/low",
        "standard = opus/medium",
        "high-risk = opus/medium",
        OWNER_MEDIUM_ORDER,
        "opus/high is no tier's default",
        "max-power = fable/high",
        "haiku → opus/medium → opus/high → fable/medium → fable/high",
        "Sonnet is no row's default.",
        "manual_model_override=true",
    ):
        assert required in block, f"Model choice block lost {required!r}"


def _task_rows(text: str) -> list[str]:
    """The four `| task | model / effort |` rows of a Model choice table."""
    return [line for line in text.splitlines() if line.startswith("| ") and line.rstrip(" |").endswith(MODEL_CELLS)]


MODEL_CELLS = ("| haiku", "| opus / medium, then high", "| fable / medium, then high")


def test_reference_doc_table_copies_the_skill_rows() -> None:
    """docs/REFERENCE.md restates the task rows. A paraphrase there dropped the
    unmatched-task rule and the Opus-to-Fable trigger, so the rows stay verbatim."""
    skill_rows = _task_rows(_block("do"))
    assert len(skill_rows) == 4
    reference = (REPO_ROOT / "docs" / "REFERENCE.md").read_text(encoding="utf-8")
    assert _task_rows(reference) == skill_rows


def test_every_opus_row_starts_at_medium() -> None:
    """Owner 2026-11-09: no task row starts Opus at high, the high-risk row included."""
    for path in ("skills/meta/do/SKILL.md", "docs/REFERENCE.md", "skills/meta/d/references/model-task-fit.md"):
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        rows = [line for line in text.splitlines() if line.lower().startswith("| high-risk")]
        assert rows, f"{path}: high-risk row missing"
        current = [row.split("|")[2].strip() for row in rows if row.split("|")[2].strip().startswith("opus /")]
        assert current, f"{path}: no current high-risk row"
        for cell in current:
            assert cell.startswith("opus / medium"), f"{path}: high-risk starts at {cell!r}"


def test_every_policy_file_quotes_the_owner_order_with_its_date() -> None:
    for path in POLICY_FILES:
        text = " ".join((REPO_ROOT / path).read_text(encoding="utf-8").replace("#", " ").split())
        assert OWNER_MEDIUM_ORDER in text, f"{path} states the policy without the owner's 2026-11-09 words"


def test_no_policy_file_names_opus_high_as_a_tier() -> None:
    for path in POLICY_FILES[:5]:
        text = (REPO_ROOT / path).read_text(encoding="utf-8")
        assert "high-risk = opus/high" not in text, path
        assert "| high-risk | `opus` / `high`" not in text, path
        assert "| high-risk | opus / high |" not in text, path


def test_wave_references_send_no_review_agent_to_sonnet() -> None:
    """The prose path of the comprehensive review follows the same model rule as its script."""
    waves = REPO_ROOT / "skills/process/workflow/references/comprehensive-review/references"
    files = sorted(waves.glob("wave-*.md"))
    assert len(files) >= 4
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "model: sonnet" not in text, path.name
        assert "run on Sonnet" not in text, path.name
