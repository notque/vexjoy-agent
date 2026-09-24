"""Tests for scripts/routing-benchmark.py: coverage accounting and the pre-route corpus gate.

The pre_route_only / pre_route_negative rows of routing-benchmark.json are the
force-route corpus contract. routing-benchmark.py runs them through pre-route.py
in CI (routing-benchmark job); these tests prove that gate catches a bad row.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Routers read the generated, gitignored skills/agents INDEX.json and
# pre-route regenerates them in the checkout when missing. Read a tmp build.
pytestmark = pytest.mark.usefixtures("use_public_index")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BENCHMARK_SCRIPT = REPO_ROOT / "scripts" / "routing-benchmark.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
routing_benchmark = importlib.import_module("routing-benchmark")


def _run_fixture(tmp_path: Path, cases: list[dict]) -> subprocess.CompletedProcess[str]:
    """Run routing-benchmark.py against a fixture holding only ``cases``."""
    fixture = tmp_path / "bench.json"
    fixture.write_text(json.dumps({"version": "test", "test_cases": cases}), encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(BENCHMARK_SCRIPT), "--fixture", str(fixture)],
        capture_output=True,
        text=True,
        timeout=60,
    )


class TestPreRouteCorpusGate:
    """routing-benchmark.py executes pre-route tier rows and fails on a mismatch."""

    def test_good_rows_pass(self, tmp_path: Path) -> None:
        result = _run_fixture(
            tmp_path,
            [
                {"request": "deploy my site", "expected_skill": "deploy", "routing_tier": "pre_route_only"},
                {"request": "push back on this design", "routing_tier": "pre_route_negative"},
            ],
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Pre-route corpus: 2/2" in result.stdout

    @pytest.mark.parametrize(
        "case",
        [
            # positive that pre-route does not match
            {"request": "tell me about quantum physics", "expected_skill": "deploy", "routing_tier": "pre_route_only"},
            # negative that pre-route force-routes
            {"request": "deploy my site", "routing_tier": "pre_route_negative"},
            # skill-scoped negative that force-routes to the forbidden skill
            {"request": "deploy my site", "routing_tier": "pre_route_negative", "forbid_force_route_to": "deploy"},
        ],
        ids=["positive-unmatched", "negative-force-routed", "negative-forbidden-skill"],
    )
    def test_bad_row_fails(self, tmp_path: Path, case: dict) -> None:
        result = _run_fixture(tmp_path, [case])
        assert result.returncode == 1, result.stdout
        assert "FAILURES:" in result.stdout

    @pytest.mark.parametrize(
        ("case", "result", "ok"),
        [
            ({"routing_tier": "pre_route_only"}, {"matched": True, "skill": "deploy"}, False),
            (
                {"routing_tier": "pre_route_only", "expected_skill": "deploy"},
                {"matched": True, "skill": "quick"},
                False,
            ),
            (
                {"routing_tier": "pre_route_only", "expected_agent": "a"},
                {"matched": True, "agent": "b"},
                False,
            ),
            (
                {"routing_tier": "pre_route_negative", "forbid_force_route_to": "deploy"},
                {"match_type": "force_route", "skill": "quick"},
                True,
            ),
            ({"routing_tier": "candidate"}, {"match_type": "force_route"}, True),
        ],
        ids=["no-expectation", "wrong-skill", "wrong-agent", "forbid-other-skill-ok", "other-tier-ignored"],
    )
    def test_check_pre_route_case(self, case: dict, result: dict, ok: bool) -> None:
        assert (routing_benchmark.check_pre_route_case(case, result) is None) is ok

    def test_checked_in_corpus_has_pre_route_rows(self) -> None:
        """The deploy and PR-workflow corpora live in the benchmark fixture."""
        cases = json.loads((REPO_ROOT / "scripts" / "routing-benchmark.json").read_text(encoding="utf-8"))
        rows = [c for c in cases["test_cases"] if c.get("routing_tier") in routing_benchmark.PRE_ROUTE_TIERS]
        skills = {c.get("expected_skill") or c.get("forbid_force_route_to") for c in rows}
        assert {"deploy", "pr-workflow"} <= skills


class TestCoverageReport:
    """Coverage accounting distinguishes benchmarked skills from explicit exclusions."""

    def test_compute_coverage_splits_known_skills(self) -> None:
        """Skills referenced by expected_skill are covered; the rest are not."""
        cases = [{"expected_skill": "research"}, {"expected_skill": None}]
        covered, uncovered = routing_benchmark.compute_coverage(cases, {"research", "headlines"})
        assert covered == {"research"}
        assert uncovered == {"headlines"}

    def test_compute_coverage_counts_stacked_skills(self) -> None:
        """Skills referenced via expected_stacked count as covered."""
        cases = [{"expected_skill": None, "expected_stacked": ["programming"]}]
        covered, uncovered = routing_benchmark.compute_coverage(cases, {"programming"})
        assert covered == {"programming"}
        assert uncovered == set()

    def test_compute_coverage_ignores_unknown_references(self) -> None:
        """A reference to a skill missing from INDEX lands in neither set."""
        cases = [{"expected_skill": "ghost-skill"}]
        covered, uncovered = routing_benchmark.compute_coverage(cases, {"headlines"})
        assert covered == set()
        assert uncovered == {"headlines"}

    def test_public_skill_names_exclude_missing_overlay_paths(self, tmp_path: Path) -> None:
        """Public coverage ignores entries whose deployment path is absent from the repo."""
        public_skill = tmp_path / "skills" / "testing" / "public" / "SKILL.md"
        public_skill.parent.mkdir(parents=True)
        public_skill.write_text("# Public\n", encoding="utf-8")
        index = {
            "skills": {
                "public": {"file": "skills/testing/public/SKILL.md"},
                "local-overlay": {"file": "skills/local-overlay/SKILL.md"},
            }
        }

        assert routing_benchmark._public_skill_names(index, tmp_path) == {"public"}

    def test_coverage_accounting_rejects_unaccounted_skills(self) -> None:
        """An indexed skill must have a case or a documented exclusion."""
        covered, excluded, unaccounted, errors = routing_benchmark.compute_coverage_accounting(
            [{"expected_skill": "research"}], {"research", "headlines"}, {}
        )
        assert covered == {"research"}
        assert excluded == set()
        assert unaccounted == {"headlines"}
        assert errors == ["Indexed skills lack a benchmark case or exclusion: ['headlines']"]

    def test_coverage_accounting_rejects_stale_or_overlapping_exclusions(self) -> None:
        """Exclusions cannot hide removed skills or duplicate real benchmark coverage."""
        _, _, _, errors = routing_benchmark.compute_coverage_accounting(
            [{"expected_skill": "research"}],
            {"research"},
            {"research": "duplicate", "ghost": "stale"},
        )
        assert errors == [
            "Exclusions name skills absent from skills/INDEX.json: ['ghost']",
            "Skills are both benchmarked and excluded: ['research']",
        ]

    def test_coverage_flag_reports_accounted_inventory(self, public_index_dir: Path) -> None:
        """The checked-in corpus and exclusions account for every indexed skill."""
        # routing-benchmark.py reads skills/agents INDEX.json at fixed repo paths;
        # those are generated and gitignored. Run its CLI with them pointed at a
        # tmp public build.
        runner = (
            "import importlib.util, sys; from pathlib import Path\n"
            "spec = importlib.util.spec_from_file_location('routing_benchmark', sys.argv[1])\n"
            "mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)\n"
            "mod.SKILLS_INDEX = Path(sys.argv[2]) / 'skills.json'\n"
            "mod.AGENTS_INDEX = Path(sys.argv[2]) / 'agents.json'\n"
            "sys.argv = [sys.argv[1], *sys.argv[3:]]\n"
            "mod.main()\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", runner, str(BENCHMARK_SCRIPT), str(public_index_dir), "--coverage"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"--coverage must pass, got {result.returncode}: {result.stderr}"
        assert "Coverage:" in result.stdout
        assert "0 unaccounted" in result.stdout
