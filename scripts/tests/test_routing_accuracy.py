"""Pytest test suite for index-router.py routing accuracy.

Three tiers of tests:
- TestForceRoutes: Script MUST return the correct force_route. Failure = script bug.
- TestCandidates: Correct answer must appear in the top-3 candidates. Failure = regression worth monitoring.
- TestLLMOnly: Script must NOT fire a false-positive force_route. Failure = script bug.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BENCHMARK = REPO_ROOT / "scripts" / "routing-benchmark.json"
ROUTER = REPO_ROOT / "scripts" / "index-router.py"


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
            assert routed_skill == expected_skill, (
                f"Expected force_route skill={expected_skill!r}, got {fr}"
            )

        if expected_agent is not None:
            routed_agent = fr.get("agent")
            assert routed_agent == expected_agent, (
                f"Expected force_route agent={expected_agent!r}, got {fr}"
            )


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

        if expected_skill is not None:
            assert expected_skill in top_n_names, (
                f"Expected skill {expected_skill!r} in top-{depth} candidates: {top_n_names}\n"
                f"Full top-{depth}: {top_n}"
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
