#!/usr/bin/env python3
"""Tests for scripts/validate-workflow-conformance.py — the conformance gate.

A native .js workflow declares a pure-literal ``meta.contract`` (phases, the
static Wave-1 roster of ``{agentType, skill}``, ``agents:{static,dynamic}``, and a
top-level ``dynamic`` flag for data-driven passes). The validator asserts the
actual script against that contract:

- STATIC: ``meta.phases`` titles == ``contract.phases``; the static roster's
  agentType+skill pairs are present in source ``agentType:``/exact Skill-tool calls
  tokens; the declared static agent count matches the roster.
- DYNAMIC (only when node is available): shells to conformance-harness.mjs and
  asserts the recorded trace (phases entered subset of contract.phases; static
  Wave-1 roster agentType+skills) against the contract. For ``dynamic:true``
  rosters it asserts SHAPE + SKILLS, not COUNT (honest limits).

Files WITHOUT a ``meta.contract`` are EXEMPT (skipped), not failed.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "validate-workflow-conformance.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "conformance"
REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_WORKFLOW_DIR = REPO_ROOT / "skills" / "process" / "workflow" / "references"
CONTRACTED_WORKFLOWS = tuple(
    REAL_WORKFLOW_DIR / name
    for name in (
        "comprehensive-review-workflow.js",
        "de-ai-pipeline.js",
        "explore-pipeline.js",
        "fan-out-workflow.js",
        "research-pipeline.js",
        "toolkit-improvement.js",
    )
)

# Import the module for unit-level tests of the static checker.
sys.path.insert(0, str(SCRIPT.parent))
import importlib.util

_spec = importlib.util.spec_from_file_location("validate_workflow_conformance", SCRIPT)
vwc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vwc)

NODE = shutil.which("node")

_rsr_spec = importlib.util.spec_from_file_location("right_size_review", SCRIPT.parent / "right-size-review.py")
_rsr = importlib.util.module_from_spec(_rsr_spec)
_rsr_spec.loader.exec_module(_rsr)


def rsr_native_estimate(tier: int) -> int:
    """Native-path reviewer count right-size-review.py reports for a tier."""
    return _rsr.composition_for_tier(tier)["native_agent_estimate"]


# The validator and workflow-helpers.js read agents/INDEX.json and
# skills/INDEX.json beside themselves (helpers by static JSON import). Those are
# generated and gitignored, so a fresh checkout has none. Runs go through a tmp
# copy of the validator, harness, and workflows laid out beside a public index
# build; source-text checks still read the real files. Set per test below.
RUN_SCRIPT: Path = SCRIPT
RUN_WORKFLOW_DIR: Path = REAL_WORKFLOW_DIR


@pytest.fixture(scope="session")
def conformance_tree(public_index_dir, tmp_path_factory) -> Path:
    """Repo-shaped tmp tree: validator, harness, workflows, and public indexes."""
    root = tmp_path_factory.mktemp("conformance-tree")
    (root / "scripts").mkdir()
    shutil.copy2(SCRIPT, root / "scripts" / SCRIPT.name)
    shutil.copy2(REPO_ROOT / "scripts" / "conformance-harness.mjs", root / "scripts")
    (root / "scripts" / "lib").mkdir()
    shutil.copy2(REPO_ROOT / "scripts" / "lib" / "index_freshness.py", root / "scripts" / "lib")
    shutil.copytree(REAL_WORKFLOW_DIR, root / "skills" / "process" / "workflow" / "references")
    (root / "agents").mkdir()
    shutil.copy2(public_index_dir / "agents.json", root / "agents" / "INDEX.json")
    shutil.copy2(public_index_dir / "skills.json", root / "skills" / "INDEX.json")
    return root


@pytest.fixture(autouse=True)
def _run_against_public_index(conformance_tree, monkeypatch):
    """Point CLI and node runs at the tmp tree, and the in-process checker at its indexes."""
    this = sys.modules[__name__]
    monkeypatch.setattr(this, "RUN_SCRIPT", conformance_tree / "scripts" / SCRIPT.name)
    monkeypatch.setattr(this, "RUN_WORKFLOW_DIR", conformance_tree / "skills" / "process" / "workflow" / "references")
    monkeypatch.setattr(
        vwc, "KNOWN_AGENTS", vwc._load_index_names(conformance_tree / "agents" / "INDEX.json", "agents")
    )
    monkeypatch.setattr(
        vwc, "KNOWN_SKILLS", vwc._load_index_names(conformance_tree / "skills" / "INDEX.json", "skills")
    )


def _run_json(*paths_or_flags):
    """Run the validator CLI with --json over given dir/flags; return (rc, data)."""
    proc = subprocess.run(
        [sys.executable, str(RUN_SCRIPT), "--json", *paths_or_flags],
        capture_output=True,
        text=True,
    )
    data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    return proc.returncode, data


def _result_for(data, name_substr):
    """Find the per-file result whose path contains name_substr."""
    for r in data["files"]:
        if name_substr in r["file"]:
            return r
    raise AssertionError(f"no result for {name_substr} in {[r['file'] for r in data['files']]}")


def _run_helper(skills):
    """Call skillDirectives() in a fresh Node process."""
    helper = RUN_WORKFLOW_DIR / "workflow-helpers.js"
    script = (
        "import { skillDirectives } from "
        + json.dumps(helper.as_uri())
        + "; process.stdout.write(skillDirectives(JSON.parse(process.argv[1])));"
    )
    return subprocess.run(
        [NODE, "--input-type=module", "-e", script, json.dumps(skills)],
        capture_output=True,
        text=True,
    )


def _run_fan_out(roster, synth_agent="research-coordinator-engineer"):
    """Execute fan-out with recording mocks and return its fail-closed trace."""
    workflow = RUN_WORKFLOW_DIR / "fan-out-workflow.js"
    script = """
      const calls = [];
      globalThis.phase = () => {};
      globalThis.budget = { remaining: () => 100000 };
      globalThis.agent = async ({ agentType }) => {
        calls.push(agentType);
        return { verdict: "PASS", summary: "ok" };
      };
      globalThis.parallel = (thunks) => Promise.all(thunks.map((thunk) => thunk()));
      const mod = await import(WORKFLOW_URL);
      try {
        await mod.default({ scope: {}, roster: ROSTER, synthAgentType: SYNTH_AGENT });
        process.stdout.write(JSON.stringify({ threw: false, calls }));
      } catch (error) {
        process.stdout.write(JSON.stringify({ threw: true, calls, error: String(error.message) }));
      }
    """
    script = script.replace("WORKFLOW_URL", json.dumps(workflow.as_uri()))
    script = script.replace("ROSTER", json.dumps(roster))
    script = script.replace("SYNTH_AGENT", json.dumps(synth_agent))
    proc = subprocess.run([NODE, "--input-type=module", "-e", script], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


# --- STATIC: pure parser unit tests ------------------------------------------


def test_extract_contract_present():
    src = (FIXTURES / "matching.js").read_text()
    contract = vwc.extract_contract(src)
    assert contract is not None
    assert contract["phases"] == ["wave-1", "verify"]
    assert contract["agents"]["static"] == 2


def test_extract_contract_absent_is_none():
    src = (FIXTURES / "no-contract.js").read_text()
    assert vwc.extract_contract(src) is None


def test_extract_phase_titles_from_source():
    src = (FIXTURES / "matching.js").read_text()
    assert vwc.extract_phase_titles(src) == {"wave-1", "verify"}


def test_extract_skill_tokens_from_source():
    src = (FIXTURES / "matching.js").read_text()
    skills = vwc.extract_skill_tokens(src)
    assert "review" in skills
    assert "assessment" in skills


def test_extract_skill_tokens_picks_up_skills_array():
    """Skill names declared inside a `skills: ["a", "b"]` array are resolvable.

    The roster entry now carries a skills LIST; every element must be collected
    as a resolvable skill token (so the per-skill check can verify each one).
    """
    src = (FIXTURES / "matching.js").read_text()
    skills = vwc.extract_skill_tokens(src)
    # testing is declared only inside skills:[...] arrays.
    assert "testing" in skills


def test_extract_skills_list_from_roster_entry():
    """Each static roster entry exposes its full skills LIST (not a single skill)."""
    matching = vwc.extract_contract((FIXTURES / "matching.js").read_text())
    entry = matching["roster"][0]
    assert vwc.entry_skills(entry) == ["review", "testing"]


@pytest.mark.parametrize(
    ("skills", "message"),
    (
        ([], "at least one skill"),
        (["not-an-indexed-skill"], "unknown skill"),
        (["reviewer-system"], "agent, not a skill"),
        ([42], "skill name must be a string"),
    ),
)
@pytest.mark.skipif(NODE is None, reason="node not available; helper runtime tests require node")
def test_skill_directives_rejects_untrusted_or_empty_names(skills, message):
    """Directive rendering fails closed before untrusted names enter a prompt."""
    proc = _run_helper(skills)
    assert proc.returncode != 0, proc.stdout
    assert message in proc.stderr.lower(), proc.stderr


@pytest.mark.parametrize(
    ("roster", "synth_agent", "message"),
    (
        (
            [
                {"agentType": "reviewer-system", "skills": ["review"]},
                {"agentType": "not-an-indexed-agent", "skills": ["review"]},
            ],
            "research-coordinator-engineer",
            "unknown agent",
        ),
        (
            [
                {"agentType": "reviewer-system", "skills": ["review"]},
                {"agentType": "reviewer-code", "skills": ["not-an-indexed-skill"]},
            ],
            "research-coordinator-engineer",
            "unknown skill",
        ),
        (
            [{"agentType": "reviewer-system", "skills": ["review"]}],
            "not-an-indexed-agent",
            "unknown agent",
        ),
        (
            [{"agentType": "review", "skills": ["testing"]}],
            "research-coordinator-engineer",
            "skill, not an agent",
        ),
        (
            [
                {"agentType": "reviewer-system", "skills": ["review"]},
                {"agentType": "reviewer-code", "skills": []},
            ],
            "research-coordinator-engineer",
            "at least one skill",
        ),
    ),
)
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_fan_out_rejects_entire_untrusted_dispatch_before_agent_calls(roster, synth_agent, message):
    """One invalid dynamic name rejects the whole fan-out before any dispatch."""
    trace = _run_fan_out(roster, synth_agent)
    assert trace["threw"] is True, trace
    assert trace["calls"] == [], trace
    assert message in trace["error"].lower(), trace


def test_fully_dynamic_roster_requires_registry_validation_call():
    """Shape-only conformance cannot pass without fail-closed name validation."""
    source = (FIXTURES / "dynamic-roster.js").read_text()
    contract = vwc.extract_contract(source)
    stripped = source.replace("validateRoster(roster)", "roster")
    errors, _ = vwc._static_checks(stripped, contract)
    assert any("validate" in error.lower() and "roster" in error.lower() for error in errors), errors


@pytest.mark.parametrize(
    ("agent_type", "skills", "message"),
    (
        ("not-an-indexed-agent", ["review"], "unknown agent"),
        ("reviewer-system", ["reviewer-code"], "agent, not a skill"),  # reviewer-code is an agent name, not a skill
        ("reviewer-system", [], "at least one skill"),
    ),
)
def test_static_contract_rejects_untrusted_wrong_type_or_empty_roster_entries(agent_type, skills, message):
    """Conformance validates roster names against the trusted component indexes."""
    contract = {
        "phases": ["fan-out"],
        "roster": [{"agentType": agent_type, "skills": skills}],
        "agents": {"static": 1, "dynamic": False},
        "dynamic": False,
    }
    source = f'''
      enterPhase("fan-out");
      const roster = [{{agentType: "{agent_type}", skills: {json.dumps(skills)}}}];
      skillDirectives(roster[0].skills);
      agent({{agentType: "{agent_type}"}});
    '''
    errors, _ = vwc._static_checks(source, contract)
    assert any(message in error.lower() for error in errors), errors


def test_count_agent_callsites():
    src = (FIXTURES / "matching.js").read_text()
    # matching.js dispatches agent() twice (wave-1 map + verify).
    assert vwc.count_agent_callsites(src) == 2


# --- STATIC: pass / fail matrix via the CLI ----------------------------------


def test_matching_fixture_passes():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "matching.js")
    assert res["status"] == "pass", res
    # matching.js itself passes; rc reflects whole-dir (which includes mismatches).


def test_mismatch_phase_fails():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-phase.js")
    assert res["status"] == "fail"
    assert any("phase" in e.lower() for e in res["static_errors"]), res["static_errors"]
    assert rc != 0


def test_mismatch_skill_fails():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-skill.js")
    assert res["status"] == "fail"
    assert any("skill" in e.lower() for e in res["static_errors"]), res["static_errors"]


def test_mismatch_agentcount_fails():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-agentcount.js")
    assert res["status"] == "fail"
    assert any("count" in e.lower() or "roster" in e.lower() or "static" in e.lower() for e in res["static_errors"]), (
        res["static_errors"]
    )


def test_no_contract_is_exempt():
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "no-contract.js")
    assert res["status"] == "exempt"


# --- Real workflow source: exact skill-call syntax and names ----------------


def test_active_workflow_contract_surfaces_drop_legacy_skill_syntax():
    """Active workflow guidance must not compete with the exact call contract."""
    offenders = [p.name for p in (*CONTRACTED_WORKFLOWS, SCRIPT) if "Skill(" in p.read_text(encoding="utf-8")]
    assert not offenders, f"legacy Skill() contract remains in {offenders}"


def test_contracted_workflows_use_only_active_skill_names():
    """Retired aliases stay out of executable native workflow surfaces."""
    source = "\n".join(path.read_text(encoding="utf-8") for path in CONTRACTED_WORKFLOWS)
    assert '"roast"' not in source
    assert '"codebase-analyzer"' not in source
    assert '"assessment"' in source
    assert '"review"' in source


# --- DYNAMIC: only when node is available ------------------------------------


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_matching_fixture_passes_dynamic():
    rc, data = _run_json("--dir", str(FIXTURES))
    res = _result_for(data, "matching.js")
    assert res["status"] == "pass", res
    assert res.get("dynamic_ran") is True


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_real_workflow_dynamic_trace_matches_contract():
    rc, data = _run_json("--dir", str(RUN_WORKFLOW_DIR))
    res = _result_for(data, "comprehensive-review-workflow.js")
    assert res["status"] == "pass", res
    assert res.get("dynamic_ran") is True
    assert not res["dynamic_errors"], res["dynamic_errors"]


def test_node_absent_skips_dynamic_gracefully(monkeypatch):
    """When node is unavailable the dynamic pass is skipped, not failed."""
    # Force the 'node missing' path regardless of host.
    monkeypatch.setattr(vwc, "node_available", lambda: False)
    results = vwc.validate_dir(FIXTURES / "matching.js", static_only=False)
    res = results[0]
    assert res["status"] == "pass"
    assert res["dynamic_ran"] is False
    assert any("node" in n.lower() for n in res["notes"]), res["notes"]


# --- Honest-limits surface ---------------------------------------------------


def test_output_labels_count_vs_shape_checks():
    """The validator must say which checks are COUNT vs SHAPE+SKILLS."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "matching.js")
    blob = json.dumps(res).lower()
    assert "count" in blob and ("shape" in blob or "skills" in blob), res


# --- FULLY-DYNAMIC ROSTER: the fan-out contract shape ------------------------
# A fully-dynamic-roster workflow has no static agentType/exact-call literals
# (the roster is caller-supplied). The contract declares roster:{dynamic:true}.
# The validator must assert the STRUCTURAL invariant — source emits a Skill(
# directive derived from a roster variable AND dispatches agentType from a roster
# variable — NOT specific names, and LABEL the check as structural.


def test_roster_is_fully_dynamic_helper():
    """roster_is_fully_dynamic() is True for {dynamic:true}, False for a list."""
    assert vwc.roster_is_fully_dynamic({"roster": {"dynamic": True}}) is True
    assert vwc.roster_is_fully_dynamic({"roster": [{"agentType": "x", "skill": "y"}]}) is False
    assert vwc.roster_is_fully_dynamic({"roster": []}) is False


def test_has_dynamic_skill_directive_detects_interpolated_skill():
    """A template-derived exact sentence counts as a per-roster Skill call."""
    yes = r"agent({ prompt: `Call the Skill tool with \`${r.skill}\`.`, agentType: r.agentType })"
    no = "agent({ prompt: `review the diff`, agentType: r.agentType })"
    assert vwc.has_dynamic_skill_directive(yes) is True
    assert vwc.has_dynamic_skill_directive(no) is False


def test_has_dynamic_agent_dispatch_detects_variable_agenttype():
    """agentType: <variable> (not a string literal) counts as dynamic dispatch."""
    yes = "agent({ agentType: r.agentType })"
    literal_only = 'agent({ agentType: "reviewer-system" })'
    assert vwc.has_dynamic_agent_dispatch(yes) is True
    assert vwc.has_dynamic_agent_dispatch(literal_only) is False


def test_dynamic_roster_fixture_passes_static():
    """Fully-dynamic roster WITH the structural invariant present PASSES."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "dynamic-roster.js")
    assert res["status"] == "pass", res


def test_dynamic_roster_missing_skill_fails_static():
    """Fully-dynamic roster MISSING the Skill(-from-roster invariant FAILS."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "dynamic-roster-missing-skill.js")
    assert res["status"] == "fail", res
    assert any("skill" in e.lower() for e in res["static_errors"]), res["static_errors"]


def test_dynamic_roster_labels_structural():
    """The validator must LABEL the dynamic-roster check as STRUCTURAL (honest limits)."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "dynamic-roster.js")
    blob = json.dumps(res["checks"]).lower()
    assert "structural" in blob, res["checks"]


def test_dynamic_roster_not_vacuous_pass():
    """A fully-dynamic contract must NOT pass merely because there are no names to
    check. Stripping the structural invariant from a {dynamic:true} contract source
    must produce a failure (proves the check is doing real work)."""
    src = (FIXTURES / "dynamic-roster.js").read_text()
    contract = vwc.extract_contract(src)
    assert vwc.roster_is_fully_dynamic(contract) is True
    errors, _ = vwc._static_checks(src, contract)
    assert errors == [], errors  # the real fixture passes
    # Remove the inline exact call literal AND the per-roster
    # skillDirectives(r.skills) CALL -> the structural invariant is violated ->
    # must error. The helper DEFINITION (function skillDirectives(...)) is excluded
    # from evidence by the gate's lookbehind, so it does not mask the removal.
    stripped = src.replace("Call the Skill tool with \\`${s}\\`.", "your usual methodology").replace(
        "skillDirectives(r.skills)", "your usual methodology"
    )
    errs2, _ = vwc._static_checks(stripped, contract)
    assert any("skill" in e.lower() for e in errs2), errs2


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_dynamic_roster_fixture_passes_dynamic():
    """With node, the fully-dynamic fixture records a real trace and PASSES."""
    rc, data = _run_json("--dir", str(FIXTURES))
    res = _result_for(data, "dynamic-roster.js")
    assert res["status"] == "pass", res
    assert res.get("dynamic_ran") is True
    assert not res["dynamic_errors"], res["dynamic_errors"]


# --- skills[] CONTRACT: full stack per agent (Stage 2.5) ---------------------
# Each roster entry now declares a skills LIST and the body must emit one
# exact Skill-tool call per element. The gate verifies EACH declared skill has a
# corresponding call (static for literal rosters; structural for
# fully-dynamic rosters where emission is delegated to skillDirectives(<var>)).


def test_missing_one_of_several_skills_fails_static():
    """A static roster entry declaring 2 skills but emitting only 1 FAILS."""
    rc, data = _run_json("--dir", str(FIXTURES), "--static-only")
    res = _result_for(data, "mismatch-skill.js")
    assert res["status"] == "fail", res
    assert any("testing" in e for e in res["static_errors"]), res["static_errors"]


def test_each_declared_skill_checked_independently():
    """The gate asserts EACH skill in the list, not just the first one."""
    src = (FIXTURES / "mismatch-skill.js").read_text()
    contract = vwc.extract_contract(src)
    errors, _ = vwc._static_checks(src, contract)
    # review is emitted (ok); testing is not.
    assert any("testing" in e for e in errors), errors
    assert not any("'review'" in e and "not resolvable" in e for e in errors), errors


def test_delegated_skill_directives_call_satisfies_invariant():
    """has_dynamic_skill_directive() also recognizes a skillDirectives(<var>) call.

    The real workflows delegate per-roster Skill-tool call emission to an imported helper
    skillDirectives(r.skills); the inline exact sentence lives in the
    helper module, not the workflow body. The structural invariant must accept the
    delegated call as evidence the per-roster methodology attach is emitted.
    """
    delegated = "agent({ prompt: `You are ${r.agentType}.` + skillDirectives(r.skills), agentType: r.agentType })"
    inline = r"agent({ prompt: `Call the Skill tool with \`${r.skill}\`.`, agentType: r.agentType })"
    none = "agent({ prompt: `review the diff`, agentType: r.agentType })"
    assert vwc.has_dynamic_skill_directive(delegated) is True
    assert vwc.has_dynamic_skill_directive(inline) is True
    assert vwc.has_dynamic_skill_directive(none) is False


@pytest.mark.skipif(NODE is None, reason="node not available; dynamic harness is a local/dev tool")
def test_real_fan_out_dynamic_records_every_skill():
    """The fan-out recorded trace shows every skill in each worker's list."""
    rc, data = _run_json("--dir", str(RUN_WORKFLOW_DIR))
    res = _result_for(data, "fan-out-workflow.js")
    assert res["status"] == "pass", res
    assert not res["dynamic_errors"], res["dynamic_errors"]


# --- MODEL rule: workflow scripts name no model -------------------------------
# One role-to-model table lives in workflow-helpers.js. Every other workflow .js
# sets `model: modelFor(role, modelOverride)`. The static gate fails a literal.

HELPERS_FILE = "workflow-helpers.js"


def _run_harness(workflow, tiers, args=None, stubs=None):
    """Run the recording harness on a real workflow; return (rc, parsed output)."""
    cmd = [
        NODE,
        str(RUN_SCRIPT.parent / "conformance-harness.mjs"),
        str(RUN_WORKFLOW_DIR / workflow),
        "--tiers",
        tiers,
    ]
    if args is not None:
        cmd += ["--args", json.dumps(args)]
    if stubs is not None:
        cmd += ["--stubs", json.dumps(stubs)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return proc.returncode, json.loads(proc.stdout)


def _run_model_for(role, override=None):
    """Call modelFor() in a fresh Node process; print the JSON result or the error."""
    helper = RUN_WORKFLOW_DIR / HELPERS_FILE
    script = (
        "import { modelFor } from "
        + json.dumps(helper.as_uri())
        + "; const [role, override] = JSON.parse(process.argv[1]);"
        + " const model = modelFor(role, override === null ? undefined : override);"
        + " process.stdout.write(JSON.stringify({ model: model === undefined ? null : model }));"
    )
    return subprocess.run(
        [NODE, "--input-type=module", "-e", script, json.dumps([role, override])],
        capture_output=True,
        text=True,
    )


@pytest.mark.parametrize(
    "source",
    [
        'agent({ prompt, model: "sonnet", agentType: "reviewer-code" })',
        "agent({ prompt, model: 'opus' })",
        "agent({ prompt, model: chosenModel })",
        "agent({ prompt, model })",
        'const DEFAULT = "haiku";\nagent({ prompt, model: modelFor("work", DEFAULT) })',
        'const m = "claude-opus-4-1";',
        'const m = "fable";',
    ],
)
def test_model_literal_errors_flags_a_named_model(source):
    assert vwc.model_literal_errors(source), source


@pytest.mark.parametrize(
    "source",
    [
        'agent({ prompt, model: modelFor("work", modelOverride), agentType: "reviewer-code" })',
        'agent({ prompt, model:\n  modelFor("lead", modelOverride) })',
        '// was model: "sonnet"\nagent({ prompt })',
        '/* model: "opus" */ agent({ prompt })',
        "const prompt = `Prefer the opus-sized answer over a sonnet.`;",
        "run({ scope, tier, modelOverride })",
    ],
)
def test_model_literal_errors_accepts_model_for_and_comments(source):
    assert vwc.model_literal_errors(source) == [], source


def test_literal_model_fails_a_contracted_file(tmp_path):
    """A contracted workflow that passes every contract check still fails on a literal model."""
    source = (FIXTURES / "matching.js").read_text()
    assert "agentType:" in source
    bad = tmp_path / "literal-model.js"
    bad.write_text(source.replace("agentType:", 'model: "sonnet", agentType:', 1))
    rc, data = _run_json("--dir", str(tmp_path), "--static-only")
    res = _result_for(data, "literal-model.js")
    assert rc == 1 and res["status"] == "fail", res
    assert any("sonnet" in e for e in res["static_errors"]), res["static_errors"]


def test_literal_model_fails_a_file_without_contract(tmp_path):
    """The contract exemption does not cover the MODEL rule."""
    bad = tmp_path / "no-contract-model.js"
    bad.write_text('export default async function run() {\n  return agent({ prompt: "x", model: "opus" });\n}\n')
    rc, data = _run_json("--dir", str(tmp_path), "--static-only")
    res = _result_for(data, "no-contract-model.js")
    assert rc == 1 and res["status"] == "fail", res
    assert any("opus" in e for e in res["static_errors"]), res["static_errors"]


def test_model_table_file_may_name_models(tmp_path):
    """Only workflow-helpers.js, which holds the table, may name a model."""
    (tmp_path / HELPERS_FILE).write_text('const ROLE_MODELS = { gather: "haiku", work: "opus" };\n')
    rc, data = _run_json("--dir", str(tmp_path), "--static-only")
    res = _result_for(data, HELPERS_FILE)
    assert rc == 0 and res["status"] == "exempt", res
    assert res["static_errors"] == [], res


def test_real_workflows_name_no_model():
    """Every shipped workflow .js except the table file passes the MODEL rule."""
    scripts = sorted(REAL_WORKFLOW_DIR.glob("*.js"))
    assert {p.name for p in CONTRACTED_WORKFLOWS} <= {p.name for p in scripts}
    for path in scripts:
        if path.name == HELPERS_FILE:
            continue
        source = path.read_text(encoding="utf-8")
        assert vwc.model_literal_errors(source) == [], path.name
        assert "modelFor(" in source and "modelOverride" in source, path.name


def test_real_workflows_pass_static_gate_with_model_rule():
    rc, data = _run_json("--dir", str(RUN_WORKFLOW_DIR), "--static-only")
    assert rc == 0, [r for r in data["files"] if r["status"] == "fail"]
    assert data["summary"]["failed"] == 0


@pytest.mark.parametrize(
    "role,override,expected",
    [
        ("gather", None, "haiku"),
        ("work", None, "opus"),
        ("lead", None, None),
        ("gather", "opus", "opus"),
        ("work", "haiku", "haiku"),
        ("lead", "sonnet", "sonnet"),
        ("lead", "claude-opus-4-1", "claude-opus-4-1"),
        ("work", "", "opus"),
    ],
)
@pytest.mark.skipif(NODE is None, reason="node not available; helper runtime tests require node")
def test_model_for_role_table_and_override(role, override, expected):
    proc = _run_model_for(role, override)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout) == {"model": expected}


@pytest.mark.parametrize(
    "role,override,message",
    [
        ("judge", None, "unknown role"),
        ("work", "gpt-4", "unknown model"),
        ("work", "best", "unknown model"),
        ("work", 5, "must be a string"),
    ],
)
@pytest.mark.skipif(NODE is None, reason="node not available; helper runtime tests require node")
def test_model_for_rejects_unknown_role_or_model(role, override, message):
    proc = _run_model_for(role, override)
    assert proc.returncode != 0
    assert message in proc.stderr, proc.stderr


@pytest.mark.parametrize("workflow", [p.name for p in CONTRACTED_WORKFLOWS])
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_model_override_reaches_every_agent(workflow):
    rc, out = _run_harness(workflow, "4", args={"modelOverride": "haiku"})
    assert rc == 0 and not out["errors"], out["errors"]
    agents = out["traces"]["4"]["agents"]
    assert agents, workflow
    assert {a["model"] for a in agents} == {"haiku"}, workflow


@pytest.mark.parametrize("workflow", [p.name for p in CONTRACTED_WORKFLOWS])
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_default_models_come_from_the_role_table(workflow):
    """With no override, each agent gets a role model: haiku, opus, or the inherited session model."""
    rc, out = _run_harness(workflow, "4")
    assert rc == 0 and not out["errors"], out["errors"]
    models = {a["model"] for a in out["traces"]["4"]["agents"]}
    assert models <= {"haiku", "opus", None}, (workflow, models)
    assert "sonnet" not in models


@pytest.mark.parametrize("workflow", [p.name for p in CONTRACTED_WORKFLOWS])
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_bad_model_override_stops_before_any_dispatch(workflow):
    rc, out = _run_harness(workflow, "4", args={"modelOverride": "gpt-4"})
    assert rc == 2, out
    assert out["traces"] == {}
    assert "modelOverride" in out["errors"][0]["error"], out["errors"]


# --- toolkit-improvement: evaluate-only default, implement gate, caps ----------

TOOLKIT = "toolkit-improvement.js"
REVIEW = "comprehensive-review-workflow.js"
EVALUATE_PHASES = ["evaluate", "research", "synthesize", "critique", "report"]
FULL_EVALUATE_PHASES = ["evaluate", "deep-dive", "adversarial", *EVALUATE_PHASES[1:]]
IMPLEMENT_PHASES = ["adr", "implement", "validate", "remediate", "record"]
IMPLEMENT_STUBS = {
    "synthesize": {
        "clusters": [
            {"title": "low-doc", "severity": "low"},
            {"title": "crit-hook", "severity": "critical"},
            {"title": "dismissed", "severity": "high"},
            {"title": "med-script", "severity": "medium"},
        ]
    },
    # The script numbers clusters c1..cN in synthesis order; the critique answers by id.
    "critique": {
        "dispositions": [
            {"id": "c3", "title": "dismissed", "disposition": "dismiss"},
            {"id": "c1", "title": "low-doc", "disposition": "confirm"},
            {"id": "c2", "title": "crit-hook (reworded)", "disposition": "confirm"},
            {"id": "c4", "title": "med-script", "disposition": "elevate"},
        ]
    },
    "adr": [
        {"title": "adr-hook", "decision": "d", "components": ["hooks/pre-tool.py", "docs/x.md"]},
        {"title": "adr-script", "decision": "d", "components": ["scripts/a.py", "scripts/tests/test_a.py:12"]},
        {"title": "adr-doc", "decision": "d", "components": ["skills/meta/do/SKILL.md"]},
    ],
    "validate": {"verdict": "regressed", "regressed_skills": ["do"]},
}


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_toolkit_improvement_default_is_evaluate_only_all_waves():
    """No args: all three evaluation waves, then research through report. Nothing past REPORT."""
    rc, out = _run_harness(TOOLKIT, "unset")
    assert rc == 0 and not out["errors"], out["errors"]
    trace = out["traces"]["unset"]
    assert trace["phases_entered"] == FULL_EVALUATE_PHASES
    # 10 foundation + 10 deep-dive + 5 adversarial + research, synthesize, critique, report.
    assert trace["agent_count"] == 29
    result = trace["result"]
    assert result["tier"] == 4
    assert result["evaluate_only"] is True
    assert result["deep_dive_ran"] is True and result["adversarial_ran"] is True
    assert result["dropped"] == []
    assert "implement is not set" in result["implement_blocked"]


@pytest.mark.parametrize(
    "tier,phases,agents",
    [
        ("1", EVALUATE_PHASES, 14),
        ("2", EVALUATE_PHASES, 14),
        ("3", ["evaluate", "deep-dive", *EVALUATE_PHASES[1:]], 24),
        ("4", FULL_EVALUATE_PHASES, 29),
    ],
)
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_toolkit_improvement_only_an_explicit_tier_shrinks_the_evaluation(tier, phases, agents):
    rc, out = _run_harness(TOOLKIT, tier)
    assert rc == 0 and not out["errors"], out["errors"]
    trace = out["traces"][tier]
    assert trace["phases_entered"] == phases
    assert trace["agent_count"] == agents
    assert trace["result"]["tier"] == int(tier)


@pytest.mark.parametrize("workflow", ["toolkit-improvement.js", "comprehensive-review-workflow.js"])
@pytest.mark.parametrize("bad_tier", ["3", True, [2]])
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_a_non_number_tier_fails_before_any_dispatch(workflow, bad_tier):
    """A mistyped tier never picks a roster silently."""
    rc, out = _run_harness(workflow, "unset", args={"tier": bad_tier})
    assert out["errors"] and "tier: expected a number" in out["errors"][0]["error"], out
    assert "unset" not in out["traces"]


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_null_tier_is_unset_and_runs_all_waves():
    rc, out = _run_harness(REVIEW, "unset", args={"tier": None})
    assert rc == 0 and not out["errors"], out["errors"]
    assert out["traces"]["unset"]["result"]["tier"] == 4


@pytest.mark.parametrize(
    "args,reason",
    [
        ({}, "implement is not set"),
        ({"implement": "yes", "branch": "fix/x"}, "implement is not set"),
        ({"implement": True}, "needs `branch`"),
        ({"implement": True, "branch": "main"}, "default branch main"),
        ({"implement": True, "branch": "master"}, "default branch master"),
        ({"implement": True, "branch": "fix/x; rm -rf ."}, "needs `branch`"),
        ({"implement": True, "branch": "fix/x", "evaluateOnly": True}, "evaluateOnly is set"),
    ],
)
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_toolkit_improvement_implement_gate_blocks(args, reason):
    """Even with clusters ready, no ADR or edit agent runs unless the gate is cleared."""
    rc, out = _run_harness(TOOLKIT, "4", args=args, stubs=IMPLEMENT_STUBS)
    assert rc == 0 and not out["errors"], out["errors"]
    trace = out["traces"]["4"]
    assert not set(trace["phases_entered"]) & set(IMPLEMENT_PHASES), trace["phases_entered"]
    assert trace["result"]["evaluate_only"] is True
    assert reason in trace["result"]["implement_blocked"], trace["result"]["implement_blocked"]


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_toolkit_improvement_implement_runs_on_a_work_branch_with_domain_engineers():
    rc, out = _run_harness(TOOLKIT, "unset", args={"implement": True, "branch": "fix/eval-1"}, stubs=IMPLEMENT_STUBS)
    assert rc == 0 and not out["errors"], out["errors"]
    trace = out["traces"]["unset"]
    assert trace["phases_entered"] == FULL_EVALUATE_PHASES + IMPLEMENT_PHASES
    by_phase = {}
    for a in trace["agents"]:
        by_phase.setdefault(a["phase"], []).append(a)

    # One ADR per cluster the critique kept, worst severity first.
    adr_prompts = [a["prompt"] for a in by_phase["adr"]]
    assert len(adr_prompts) == 3
    assert not any('"dismissed"' in p for p in adr_prompts)
    assert '"crit-hook"' in adr_prompts[0] and '"low-doc"' in adr_prompts[2]

    # Each ADR goes to the engineer for its components, never the coordinator.
    assert [a["agentType"] for a in by_phase["implement"]] == [
        "hook-development-engineer",
        "python-general-engineer",
        "toolkit-governance-engineer",
    ]
    assert by_phase["implement"][0]["skills"] == ["programming", "testing"]
    assert by_phase["implement"][2]["skills"] == ["toolkit", "testing"]
    for a in by_phase["implement"] + by_phase["remediate"]:
        assert "git branch --show-current" in a["prompt"], a["agentType"]
        assert "`fix/eval-1`" in a["prompt"]
        assert a["model"] == "opus"
    assert [a["agentType"] for a in by_phase["validate"] + by_phase["remediate"]] == ["toolkit-governance-engineer"] * 2
    for a in trace["agents"]:
        assert a["agentType"] and a["skills"], a["phase"]

    result = trace["result"]
    assert result["evaluate_only"] is False and result["branch"] == "fix/eval-1"
    assert result["adrs_created"] == 3 and result["implementations_ran"] == 3
    assert result["dropped"] == []
    assert result["unreviewed_clusters"] == []


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_toolkit_improvement_cluster_without_a_disposition_is_not_implemented():
    """Fail closed: the critic skipped one cluster and matched another by title
    only. Neither gets an ADR; both are reported."""
    stubs = dict(IMPLEMENT_STUBS)
    stubs["critique"] = {
        "dispositions": [
            {"id": "c1", "title": "low-doc", "disposition": "confirm"},
            {"id": "c3", "title": "dismissed", "disposition": "dismiss"},
            {"title": "crit-hook", "disposition": "confirm"},
        ]
    }
    rc, out = _run_harness(TOOLKIT, "unset", args={"implement": True, "branch": "fix/eval-1"}, stubs=stubs)
    assert rc == 0 and not out["errors"], out["errors"]
    trace = out["traces"]["unset"]
    adr_prompts = [a["prompt"] for a in trace["agents"] if a["phase"] == "adr"]
    assert len(adr_prompts) == 1 and '"low-doc"' in adr_prompts[0]
    assert trace["result"]["unreviewed_clusters"] == ["crit-hook", "med-script"]
    assert any("no critique disposition" in line and "crit-hook" in line for line in trace["logs"]), trace["logs"]


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_toolkit_improvement_no_critique_blocks_implementation():
    """A dropped critique reviewed nothing, so the cleared gate still stops the run."""
    stubs = dict(IMPLEMENT_STUBS)
    stubs["critique"] = None
    rc, out = _run_harness(TOOLKIT, "unset", args={"implement": True, "branch": "fix/eval-1"}, stubs=stubs)
    assert rc == 0 and not out["errors"], out["errors"]
    trace = out["traces"]["unset"]
    assert not set(trace["phases_entered"]) & set(IMPLEMENT_PHASES), trace["phases_entered"]
    result = trace["result"]
    assert result["evaluate_only"] is True and result["implement_requested"] is True
    assert "critique did not run" in result["implement_blocked"]
    assert len(result["unreviewed_clusters"]) == 4


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_toolkit_improvement_role_models():
    rc, out = _run_harness(TOOLKIT, "4")
    models = {}
    for a in out["traces"]["4"]["agents"]:
        models.setdefault(a["phase"], set()).add(a["model"])
    assert models == {
        "evaluate": {"opus"},
        "deep-dive": {"opus"},
        "adversarial": {"opus"},
        "research": {"opus"},  # rates priority and gap, so `work`, not `gather`
        "synthesize": {None},
        "critique": {"opus"},
        "report": {None},
    }


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_toolkit_improvement_max_agents_caps_and_reports_drops():
    rc, out = _run_harness(TOOLKIT, "4", args={"maxAgents": 12})
    assert rc == 0 and not out["errors"], out["errors"]
    trace = out["traces"]["4"]
    assert trace["agent_count"] == 12
    result = trace["result"]
    assert result["max_agents"] == 12 and result["agents_dispatched"] == 12
    dropped = {d["phase"]: d["agents"] for d in result["dropped"]}
    assert len(dropped["deep-dive"]) == 8
    assert len(dropped["adversarial"]) == 5
    assert dropped["research"] == ["research"]
    assert any("maxAgents=12" in line and "dropped 8" in line for line in trace["logs"]), trace["logs"]


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_toolkit_improvement_default_cap_fits_a_full_evaluation():
    rc, out = _run_harness(TOOLKIT, "4")
    result = out["traces"]["4"]["result"]
    assert result["max_agents"] == 40 and result["agents_dispatched"] == 29
    assert result["dropped"] == []


# --- comprehensive-review: all waves by default, fix gate, verify and fix agents --


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_comprehensive_review_unset_tier_runs_all_waves():
    """Owner, 2026-11-09: "Comprehensive review is no longer comprehensive with 1 wave"."""
    rc, out = _run_harness(REVIEW, "unset")
    assert rc == 0 and not out["errors"], out["errors"]
    trace = out["traces"]["unset"]
    assert trace["phases_entered"] == ["wave-1", "wave-2", "wave-3", "verify"]
    by_phase = {}
    for a in trace["agents"]:
        by_phase[a["phase"]] = by_phase.get(a["phase"], 0) + 1
    assert by_phase == {"wave-1": 4, "wave-2": 5, "wave-3": 4}
    assert trace["result"]["tier"] == 4 and trace["result"]["wave3_ran"] is True


@pytest.mark.parametrize(
    "tier,counts",
    [
        ("1", {"wave-1": 4}),
        ("2", {"wave-1": 4}),
        ("3", {"wave-1": 4, "wave-2": 3}),
        ("4", {"wave-1": 4, "wave-2": 5, "wave-3": 4}),
    ],
)
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_comprehensive_review_only_an_explicit_tier_shrinks_the_review(tier, counts):
    rc, out = _run_harness(REVIEW, tier)
    assert rc == 0 and not out["errors"], out["errors"]
    by_phase = {}
    for a in out["traces"][tier]["agents"]:
        by_phase[a["phase"]] = by_phase.get(a["phase"], 0) + 1
    assert by_phase == counts
    # The native roster sizes right-size-review.py reports for this path.
    assert sum(counts.values()) == rsr_native_estimate(int(tier))


REVIEW_FIX_STUBS = {
    "wave-1": {
        "findings": [{"title": "t1", "severity": "high", "location": "src/a.py:10", "description": "d"}],
    },
    "verify": {"finding_title": "t1", "disposition": "AGREE"},
}


@pytest.mark.parametrize(
    "args,reason",
    [
        ({}, "implement is not set"),
        ({"implement": "yes", "branch": "fix/x"}, "implement is not set"),
        ({"implement": True}, "needs `branch`"),
        ({"implement": True, "branch": "main"}, "default branch main"),
        ({"implement": True, "branch": "master"}, "default branch master"),
        ({"implement": True, "branch": "trunk"}, "default branch trunk"),
        ({"implement": True, "branch": "fix/x; rm -rf ."}, "needs `branch`"),
        ({"implement": True, "branch": "fix/x", "reviewOnly": True}, "reviewOnly is set"),
    ],
)
@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_comprehensive_review_fix_gate_blocks(args, reason):
    """A verified finding is reported, and no fix agent runs unless the gate is cleared."""
    rc, out = _run_harness(REVIEW, "2", args=args, stubs=REVIEW_FIX_STUBS)
    assert rc == 0 and not out["errors"], out["errors"]
    trace = out["traces"]["2"]
    assert "fix" not in trace["phases_entered"]
    assert not [a for a in trace["agents"] if a["phase"] == "fix"]
    result = trace["result"]
    assert reason in result["fix_blocked"], result["fix_blocked"]
    assert result["review_only"] is True and result["fixes"] == []
    assert result["unfixed"] == ["t1"]
    assert [f["title"] for f in result["verified"]] == ["t1"]


@pytest.mark.skipif(NODE is None, reason="node not available; workflow runtime tests require node")
def test_comprehensive_review_verify_and_fix_agents_carry_agent_and_skills():
    finding = {"title": "t1", "severity": "HIGH", "location": "src/a.py:10", "description": "d"}
    stubs = {
        "wave-1": {"findings": [finding]},
        "verify": {"finding_title": "t1", "disposition": "AGREE"},
    }
    rc, out = _run_harness(REVIEW, "2", args={"implement": True, "branch": "fix/review-1"}, stubs=stubs)
    assert rc == 0 and not out["errors"], out["errors"]
    result = out["traces"]["2"]["result"]
    assert result["fix_blocked"] is None and result["branch"] == "fix/review-1"
    agents = out["traces"]["2"]["agents"]
    verify = [a for a in agents if a["phase"] == "verify"]
    fix = [a for a in agents if a["phase"] == "fix"]
    assert len(verify) == 1 and len(fix) == 1, [(a["phase"], a["agentType"]) for a in agents]
    assert verify[0]["agentType"] == "reviewer-perspectives"
    assert verify[0]["skills"] == ["assessment", "testing"]
    assert fix[0]["agentType"] == "python-general-engineer"
    assert fix[0]["skills"] == ["programming", "testing"]
    assert "git branch --show-current" in fix[0]["prompt"] and "`fix/review-1`" in fix[0]["prompt"]
    assert "never commit or push" in fix[0]["prompt"]
    assert "Operating standards (injected)" in verify[0]["prompt"]
    assert "Operating standards (injected)" in fix[0]["prompt"]
