"""Pytest test suite for index-router.py routing accuracy.

Three tiers of tests:
- TestForceRoutes: Script MUST return the correct force_route. Failure = script bug.
- TestCandidates: Correct answer must appear in the top-3 candidates. Failure = regression worth monitoring.
- TestLLMOnly: Script must NOT fire a false-positive force_route. Failure = script bug.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BENCHMARK = REPO_ROOT / "scripts" / "routing-benchmark.json"
ROUTER = REPO_ROOT / "scripts" / "index-router.py"
BENCHMARK_SCRIPT = REPO_ROOT / "scripts" / "routing-benchmark.py"

sys.path.insert(0, str(REPO_ROOT / "scripts"))
routing_benchmark = importlib.import_module("routing-benchmark")


def load_benchmark() -> list[dict]:
    """Load all test cases from routing-benchmark.json.

    Returns:
        List of test case dicts with routing_tier and expectation fields.
    """
    data = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    return data["test_cases"]


def run_router(request: str) -> dict:
    """Invoke index-router.py for a request and return parsed JSON output.

    Args:
        request: The user request string to route.

    Returns:
        Parsed JSON dict from router stdout.

    Raises:
        AssertionError: If the router returns a non-zero exit code or invalid JSON.
    """
    result = subprocess.run(
        ["python3", str(ROUTER), "--request", request, "--json"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"Router exited with {result.returncode}: {result.stderr}"
    return json.loads(result.stdout)


def _tier_cases(tier: str) -> list[dict]:
    """Return test cases for a given routing_tier.

    Args:
        tier: One of 'force_route', 'candidate', or 'llm_only'.

    Returns:
        Filtered list of test case dicts.
    """
    return [c for c in load_benchmark() if c.get("routing_tier") == tier]


def _case_id(case: dict) -> str:
    """Generate a short pytest ID from the request text.

    Args:
        case: Test case dict with a 'request' field.

    Returns:
        First 50 characters of the request string.
    """
    return case["request"][:50]


class TestForceRoutes:
    """Script MUST return the correct force_route for these cases.

    These are requests with clear keyword triggers for force-routed skills.
    A test failure here means a trigger was removed or broken in the INDEX —
    it is a script/config bug, not an acceptable regression.
    """

    @pytest.mark.parametrize(
        "case",
        _tier_cases("force_route"),
        ids=_case_id,
    )
    def test_force_route_matches(self, case: dict) -> None:
        """Assert the router fires a force_route matching the expected skill.

        Args:
            case: Test case dict from routing-benchmark.json.
        """
        result = run_router(case["request"])
        expected_skill = case.get("expected_skill")
        expected_agent = case.get("expected_agent")

        assert result["force_route"] is not None, (
            f"Expected a force_route to {expected_skill!r} but got none.\n"
            f"Top candidates: {[c['name'] for c in result.get('candidates', [])[:3]]}"
        )

        fr = result["force_route"]

        if expected_skill is not None:
            # force_route dict may use 'skill' or 'pipeline' as key
            routed_skill = fr.get("skill") or fr.get("pipeline")
            assert routed_skill == expected_skill, f"Expected force_route skill={expected_skill!r}, got {fr}"

        if expected_agent is not None:
            routed_agent = fr.get("agent")
            assert routed_agent == expected_agent, f"Expected force_route agent={expected_agent!r}, got {fr}"


class TestCandidates:
    """Correct answer should appear in the top-3 scored candidates.

    These cases use keyword scoring, not force-routes. The router is not
    guaranteed to get first place right, but the correct answer must at least
    surface in the top-3 for the LLM to have a reasonable chance of picking it.
    A test failure here is an acceptable regression worth monitoring — it means
    the skill's trigger words have drifted away from how users phrase the request.
    """

    @pytest.mark.parametrize(
        "case",
        _tier_cases("candidate"),
        ids=_case_id,
    )
    def test_candidate_in_top_n(self, case: dict) -> None:
        """Assert the expected skill or agent appears in the top-N candidates.

        Uses candidate_depth from the test case (default 3) to control how
        deep to search. Some requests have weak trigger overlap and need a
        deeper window to surface the correct answer.

        Args:
            case: Test case dict from routing-benchmark.json.
        """
        result = run_router(case["request"])
        depth = case.get("candidate_depth", 3)
        top_n = result.get("candidates", [])[:depth]
        top_n_names = [c["name"] for c in top_n]
        top_n_agents = [c.get("agent") for c in top_n]

        expected_skill = case.get("expected_skill")
        expected_agent = case.get("expected_agent")

        if expected_skill is None and expected_agent is None:
            pytest.fail(
                f"Candidate-tier case {case['request']!r} has no expected_skill or expected_agent. "
                f"Every candidate case must assert something — add an expectation or reclassify."
            )

        if expected_skill is not None:
            assert expected_skill in top_n_names, (
                f"Expected skill {expected_skill!r} in top-{depth} candidates: {top_n_names}\nFull top-{depth}: {top_n}"
            )

        if expected_agent is not None:
            # Agent may appear as a named candidate OR as the agent field on a skill candidate
            assert expected_agent in top_n_names or expected_agent in top_n_agents, (
                f"Expected agent {expected_agent!r} in top-{depth} names={top_n_names} or agents={top_n_agents}"
            )


class TestLLMOnly:
    """Script should NOT false-positive force-route these requests.

    Cases where the correct routing requires LLM intent understanding —
    either the request is ambiguous, state-dependent, or requires multi-skill
    chaining that the deterministic pre-pass cannot evaluate.

    For cases with expected_skill=None and expected_agent=None: the script must
    return force_route=None (true negative — no force-routing at all).

    For cases with expectations set: those expectations are documented for the
    LLM layer, not verified here. We only verify the script does not send the
    user somewhere definitively wrong via force-route.
    """

    @pytest.mark.parametrize(
        "case",
        _tier_cases("llm_only"),
        ids=_case_id,
    )
    def test_no_false_positive_force_route(self, case: dict) -> None:
        """Assert requests that require LLM judgment do not get spurious force-routes.

        For true-negative cases (no expected_skill, no expected_agent), the script
        must return force_route=None. For cases with expectations, the assertion is
        informational — we verify the force_route is either None or matches the
        expected_skill (not some wrong skill).

        Args:
            case: Test case dict from routing-benchmark.json.
        """
        result = run_router(case["request"])
        expected_skill = case.get("expected_skill")
        expected_agent = case.get("expected_agent")

        if expected_skill is None and expected_agent is None:
            # True negative: script must not force-route at all
            assert result["force_route"] is None, (
                f"False positive force_route for {case['request']!r}: {result['force_route']}\n"
                f"This request requires LLM judgment and must not be force-routed deterministically."
            )
        else:
            # Expectations are LLM-layer targets. Script may return None or the expected skill.
            # We only flag if the script force-routes to something WRONG (not expected).
            fr = result.get("force_route")
            if fr is not None and expected_skill is not None:
                routed = fr.get("skill") or fr.get("pipeline")
                assert routed == expected_skill, (
                    f"Script force-routed to {routed!r} but expected {expected_skill!r} "
                    f"(or None) for LLM-only case: {case['request']!r}"
                )


# ---------------------------------------------------------------------------
# pre-route.py tier — exercises the FAST pre-router used by /do Phase 2 Step 0
# ---------------------------------------------------------------------------

PRE_ROUTE_SCRIPT = REPO_ROOT / "scripts" / "pre-route.py"


def run_pre_route(request: str) -> dict:
    """Invoke pre-route.py for a request and return parsed JSON output.

    pre-route.py is the FAST pre-router that /do Phase 2 Step 0 calls before
    the orchestrator self-routes off the manifest in-session. It returns
    matched/agent/skill/confidence, not scored candidates.

    Args:
        request: The user request string to route.

    Returns:
        Parsed JSON dict from pre-route.py stdout.
    """
    result = subprocess.run(
        [sys.executable, str(PRE_ROUTE_SCRIPT), "--request", request, "--json-compact"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"pre-route.py exited with {result.returncode}: {result.stderr}"
    return json.loads(result.stdout)


class TestPreRoute:
    """Tests for the pre-route.py fast pre-router (used by /do Phase 2 Step 0).

    pre-route.py is invoked first by /do; if it returns matched=True with high
    confidence, /do skips the in-session manifest route. These tests verify the
    pre-route layer routes correctly for cases where it's the authoritative
    decision-maker.
    """

    @pytest.mark.parametrize(
        "case",
        _tier_cases("pre_route_only"),
        ids=_case_id,
    )
    def test_pre_route_matches(self, case: dict) -> None:
        """Assert pre-route.py returns the expected skill or agent for the request.

        Args:
            case: Test case dict from routing-benchmark.json.
        """
        result = run_pre_route(case["request"])
        expected_skill = case.get("expected_skill")
        expected_agent = case.get("expected_agent")

        # Every pre_route_only case must declare at least one expectation.
        # Without this assertion, a fixture with neither expected_skill nor
        # expected_agent would silently pass on the matched-only check below.
        assert expected_skill is not None or expected_agent is not None, (
            f"pre_route_only case {case['request']!r} has neither expected_skill nor expected_agent. "
            f"Add an expectation or move the case to llm_only tier."
        )

        assert result.get("matched") is True, (
            f"Expected pre-route.py to match {case['request']!r} but got matched=False. "
            f"Reasoning: {result.get('reasoning')}"
        )

        if expected_skill is not None:
            assert result.get("skill") == expected_skill, (
                f"Expected skill={expected_skill!r}, got {result.get('skill')!r}. Reasoning: {result.get('reasoning')}"
            )

        if expected_agent is not None:
            assert result.get("agent") == expected_agent, (
                f"Expected agent={expected_agent!r}, got {result.get('agent')!r}. Reasoning: {result.get('reasoning')}"
            )


class TestPreRouteNegative:
    """pre-route.py must NOT force-route these requests (tier: pre_route_negative).

    The corpus pins idiom guards ("push back on this design"), the D7 planning
    unigram classes (continue/resume/pause/unsure/handoff — originals in
    test_pre_route_planning.py), pure fallthroughs, and sanitized patterns from
    route-events history. A force-route here would override the semantic route
    in /do Phase 2, so any force_route match at any confidence is a failure.
    The corpus is the contract: if a phrase fails, fix the trigger or guard,
    do not drop the case. See adr/router-improvement-program.md (C3).
    """

    @pytest.mark.parametrize(
        "case",
        _tier_cases("pre_route_negative"),
        ids=_case_id,
    )
    def test_no_force_route(self, case: dict) -> None:
        """Assert pre-route.py fires no force_route for the request.

        Args:
            case: Test case dict from routing-benchmark.json.
        """
        result = run_pre_route(case["request"])
        assert result.get("match_type") != "force_route", (
            f"{case['request']!r} must not force-route but got "
            f"skill={result.get('skill')!r} agent={result.get('agent')!r} "
            f"confidence={result.get('confidence')!r}. Reasoning: {result.get('reasoning')}"
        )


class TestCoverageReport:
    """Coverage accounting distinguishes benchmarked skills from explicit exclusions."""

    def test_compute_coverage_splits_known_skills(self) -> None:
        """Skills referenced by expected_skill are covered; the rest are not."""
        cases = [{"expected_skill": "fact-check"}, {"expected_skill": None}]
        covered, uncovered = routing_benchmark.compute_coverage(cases, {"fact-check", "headlines"})
        assert covered == {"fact-check"}
        assert uncovered == {"headlines"}

    def test_compute_coverage_counts_stacked_skills(self) -> None:
        """Skills referenced via expected_stacked count as covered."""
        cases = [{"expected_skill": None, "expected_stacked": ["go-patterns"]}]
        covered, uncovered = routing_benchmark.compute_coverage(cases, {"go-patterns"})
        assert covered == {"go-patterns"}
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
            [{"expected_skill": "fact-check"}], {"fact-check", "headlines"}, {}
        )
        assert covered == {"fact-check"}
        assert excluded == set()
        assert unaccounted == {"headlines"}
        assert errors == ["Indexed skills lack a benchmark case or exclusion: ['headlines']"]

    def test_coverage_accounting_rejects_stale_or_overlapping_exclusions(self) -> None:
        """Exclusions cannot hide removed skills or duplicate real benchmark coverage."""
        _, _, _, errors = routing_benchmark.compute_coverage_accounting(
            [{"expected_skill": "fact-check"}],
            {"fact-check"},
            {"fact-check": "duplicate", "ghost": "stale"},
        )
        assert errors == [
            "Exclusions name skills absent from skills/INDEX.json: ['ghost']",
            "Skills are both benchmarked and excluded: ['fact-check']",
        ]

    def test_coverage_flag_reports_accounted_inventory(self) -> None:
        """The checked-in corpus and exclusions account for every indexed skill."""
        result = subprocess.run(
            [sys.executable, str(BENCHMARK_SCRIPT), "--coverage"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"--coverage must pass, got {result.returncode}: {result.stderr}"
        assert "Coverage:" in result.stdout
        assert "0 unaccounted" in result.stdout
