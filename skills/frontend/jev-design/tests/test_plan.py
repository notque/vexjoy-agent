from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/plan.py"
SPEC = importlib.util.spec_from_file_location("jev_design_plan", SCRIPT)
planner = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(planner)
limits = planner.jev_limits
CATALOG = planner.load_catalog()


def ready():
    return True, "test"


def unavailable():
    return False, "no transport configured"


def request(**updates):
    value = {
        "brief": "Dense technical support workspace",
        "style_traits": ["technical", "dense"],
        "requirements": [
            {
                "id": "results",
                "role": "Show and act on cases",
                "capabilities": ["tabular-data", "filter", "row-actions"],
            },
            {"id": "details", "role": "Inspect a case", "capabilities": ["overlay", "details"]},
        ],
    }
    value.update(updates)
    return value


def answer(questions, *, component_overrides=None, fitness=0.9, style="technical-console"):
    component_overrides = component_overrides or {}
    answers = {}
    for name, question in questions.items():
        if question["type"] == "choice":
            options = list(question["criteria"])
            picked = (
                style if name == "style" else component_overrides.get(name, next(x for x in options if x != "none"))
            )
            answers[name] = {
                "choice": picked,
                "probabilities": {x: 1.0 if x == picked else 0.0 for x in options},
                "confidence": 1.0,
            }
        else:
            answers[name] = {"noul": fitness}
    return {"answers": answers, "usage": {"input_tokens": 10, "output_tokens": 2}, "model": "typesafe-ai/jev"}


def fake(**kwargs):
    return lambda _state, questions, _timeout: answer(questions, **kwargs)


def run(value=None, **kwargs):
    kwargs.setdefault("available", ready)
    return planner.plan(value or request(), **kwargs)


def test_end_to_end_selects_components_style_and_implementation():
    result = run(send=fake())
    assert result["status"] == "selected"
    assert [x["component"] for x in result["plan"]["components"]] == ["data-table", "sheet"]
    assert result["plan"]["style"]["id"] == "technical-console"
    build = result["plan"]["implementation"]
    assert build["install"].startswith("npx shadcn@latest add table ")
    assert "sheet" in build["install"].split() and build["npm"] == "npm install @tanstack/react-table"
    assert ":root {" in build["css"] and ".dark {" in build["css"] and "--radius: 0.25rem;" in build["css"]
    assert all(row["ok"] for row in build["contrast"])
    assert result["run"]["requests"] == len(result["attempts"]) == 2


def test_deterministic_filter_and_baseline_precede_call():
    seen = []

    def send(state, questions, _timeout):
        seen.append(state)
        return answer(questions)

    result = run(send=send)
    component_state = next(s for s in seen if "candidates" in s)
    assert list(component_state["candidates"]["results"]) == ["data-table"]
    assert result["baseline"]["components"] == {"results": "data-table", "details": "sheet"}
    assert result["baseline"]["style"] == "technical-console"


def test_eligible_ranks_tightest_fit_and_caps_candidates():
    rows = planner.eligible({"capabilities": ["data-entry"]}, CATALOG)
    assert len(rows) == planner.MAX_CANDIDATES
    assert rows[0]["id"] == "label"
    assert all(row.get("status") != "legacy" for row in rows)
    assert run(request(requirements=[{"id": "x", "capabilities": ["data-entry"]}]), send=fake())["truncated"]["x"] > 0


def test_primitives_filter_excludes_components_missing_from_that_base():
    ids = [r["id"] for r in planner.eligible({"capabilities": ["notification"]}, CATALOG, "radix")]
    assert ids == ["sonner"]
    ids = [r["id"] for r in planner.eligible({"capabilities": ["conversation"]}, CATALOG, "radix")]
    assert ids == []


def test_normalized_requirement_ids_cannot_collide():
    value = request(
        requirements=[
            {"id": "a-b", "capabilities": ["summary"]},
            {"id": "a_b", "capabilities": ["summary"]},
        ]
    )
    assert run(value, send=fake())["reason"] == "invalid_request"


def test_no_candidate_and_unavailable_abstain_without_sending():
    def no_call(*_):
        raise AssertionError("called")

    result = run(request(requirements=[{"id": "x", "capabilities": ["unknown"]}]), send=no_call)
    assert result["reason"] == "no_compatible_component" and "unknown" in result["next_action"]
    assert run(send=no_call, available=unavailable)["reason"] == "jev_unavailable"


def test_low_fitness_and_none_abstain():
    assert run(send=fake(fitness=0.4))["reason"] == "low_fitness"
    result = run(send=fake(component_overrides={"component_results": "none"}))
    assert result["reason"] == "none_or_out_of_catalog" and "results" in result["next_action"]
    assert run(send=fake(style="none"))["reason"] == "low_style_fitness"


def test_partial_malformed_and_out_of_catalog_abstain():
    assert run(send=lambda *_: {"answers": {}})["reason"] == "malformed_response"

    def bad(_state, questions, _timeout):
        data = answer(questions)
        if "component_results" in data["answers"]:
            data["answers"]["component_results"]["choice"] = "invented"
        return data

    assert run(send=bad)["reason"] == "malformed_response"

    def bad_prob(_state, questions, _timeout):
        data = answer(questions)
        if "style" in data["answers"]:
            data["answers"]["style"]["probabilities"] = {"technical-console": 1.5}
        return data

    assert run(send=bad_prob)["reason"] == "malformed_response"

    def contradictory(_state, questions, _timeout):
        data = answer(questions)
        if "component_results" in data["answers"]:
            data["answers"]["component_results"]["probabilities"] = {"data-table": 0.01, "none": 0.99}
        return data

    assert run(send=contradictory)["reason"] == "malformed_response"


def test_one_failed_request_abstains_the_whole_plan():
    def flaky(state, questions, _timeout):
        if "styles" in state:
            raise RuntimeError("503 after retries")
        return answer(questions)

    result = run(send=flaky)
    assert result["status"] == "abstained" and result["reason"] == "jev_unavailable"


def test_bounds_and_capabilities_contract():
    assert run(request(brief="x" * (planner.MAX_BRIEF + 1)), send=fake())["reason"] == "invalid_request"
    assert run(request(primitives="mui"), send=fake())["reason"] == "invalid_request"
    listed = planner.capabilities(CATALOG)
    assert "tabular-data" in listed["capabilities"] and listed["capabilities"]["tabular-data"]
    assert "technical" in listed["style_traits"] and len(listed["styles"]) == len(CATALOG["styles"])


def test_default_send_uses_packed_selectable_transport(monkeypatch):
    seen = {}

    def evaluate_packed(state, questions, *, timeout):
        seen["timeout"] = timeout
        return answer(questions)

    monkeypatch.setattr(planner.jev_transport, "evaluate_packed", evaluate_packed)
    assert planner.plan(request(), available=ready, timeout=7.0)["status"] == "selected"
    assert seen["timeout"] == 7.0


# --- Request size ------------------------------------------------------------


def _capability_rank():
    """Capabilities ordered by the request tokens one requirement using them costs, largest first."""
    sized = []
    for cap in CATALOG["capabilities"]:
        item = {"id": "x", "key": "x", "role": "r" * planner.MAX_FIELD_CHARS, "capabilities": [cap]}
        rows = planner.eligible(item, CATALOG)
        if rows:
            state, questions = planner._component_unit(item, rows)
            sized.append((limits.estimate_tokens(state) + limits.estimate_tokens(questions), cap))
    return [cap for _, cap in sorted(sized, reverse=True)]


def worst_case_request():
    caps = _capability_rank()
    return {
        "brief": "b" * planner.MAX_BRIEF,
        "style_traits": sorted({t for s in CATALOG["styles"] for t in s["traits"]})[: planner.MAX_STYLE_TRAITS],
        "requirements": [
            {"id": f"{i}-" + "r" * 62, "role": "w" * planner.MAX_FIELD_CHARS, "capabilities": [caps[i % 3]]}
            for i in range(planner.MAX_REQUIREMENTS)
        ],
    }


def test_worst_case_brief_stays_under_request_size_limit():
    value = worst_case_request()
    requests, candidates, _, _ = planner.build_requests(value, CATALOG)
    assert all(len(rows) == planner.MAX_CANDIDATES for rows in candidates.values())
    sizes = [limits.request_tokens(r["state"], r["questions"]) for r in requests]
    assert max(s["total"] for s in sizes) <= limits.TARGET_REQUEST_TOKENS <= limits.MAX_REQUEST_TOKENS
    assert max(s["state_plus_longest"] for s in sizes) < limits.STATE_PLUS_LONGEST_QUESTION_LIMIT
    total = sum(s["total"] for s in sizes)
    assert total < limits.CASCADE_TOKENS_PER_RUN
    check = limits.check_run(requests, concurrency=len(requests), attempts=4)
    assert check["verdict"] != "fail", check["findings"]
    result = run(value, send=fake())
    assert result["status"] == "selected" and result["run"]["requests"] == len(requests)


def test_every_question_is_sent_exactly_once():
    requests, *_ = planner.build_requests(worst_case_request(), CATALOG)
    names = [name for r in requests for name in r["questions"]]
    assert len(names) == len(set(names))


def test_oversized_request_abstains_without_sending(monkeypatch):
    monkeypatch.setattr(limits, "MAX_REQUEST_TOKENS", 100)

    def no_call(*_):
        raise AssertionError("called")

    assert run(send=no_call)["reason"] == "request_too_large"


# --- Catalog integrity -------------------------------------------------------


def test_catalog_v2_is_versioned_and_sourced():
    assert planner.CATALOG_FILE.endswith("catalog-v2.json")
    assert CATALOG["version"] == "shadcn-style-catalog-v2"
    assert CATALOG["source"]["components"].startswith("https://ui.shadcn.com/")
    assert CATALOG["source"]["fetched"]
    assert (planner.SKILL_DIR / "references/catalog-v1.json").is_file()


def test_component_ids_unique_and_packages_non_empty():
    ids = [row["id"] for row in CATALOG["components"]]
    assert len(ids) == len(set(ids)) >= 60
    for row in CATALOG["components"]:
        assert isinstance(row["package"], str) and row["package"].strip()
        assert row["use_when"].strip() and row["avoid_when"].strip()
        assert len(row["use_when"]) <= 120 and len(row["avoid_when"]) <= 120
        assert set(row.get("bases", planner.PRIMITIVES)) <= set(planner.PRIMITIVES)


def test_every_capability_defined_used_and_every_component_reachable():
    defined = set(CATALOG["capabilities"])
    used = {cap for row in CATALOG["components"] for cap in row["capabilities"]}
    assert used == defined
    for row in CATALOG["components"]:
        assert row["capabilities"], row["id"]
        reachable = any(
            row in planner.eligible({"capabilities": [cap]}, CATALOG) for cap in row["capabilities"]
        ) or row in planner.eligible({"capabilities": row["capabilities"]}, CATALOG)
        assert reachable, row["id"]


def test_pairs_and_additions_point_at_catalog_or_registry_items():
    ids = {row["id"] for row in CATALOG["components"]}
    for row in CATALOG["components"]:
        assert set(row.get("pairs_with", [])) <= ids, row["id"]
        assert set(row.get("also_add", [])) <= ids, row["id"]


def test_style_recipes_are_distinct_complete_and_accessible():
    styles = CATALOG["styles"]
    assert 8 <= len(styles) <= 12
    assert len({s["id"] for s in styles}) == len(styles)
    shapes = {(s["base_color"], s["radius"], s["density"], s["shadow"]) for s in styles}
    assert len(shapes) == len(styles)
    for a in styles:
        for b in styles:
            if a is not b:
                assert len(set(a["traits"]) ^ set(b["traits"])) >= 2, (a["id"], b["id"])
    for style in styles:
        assert style["base_color"] in CATALOG["base_colors"]
        assert style["density"] in CATALOG["density"] and style["shadow"] in CATALOG["shadow"]
        assert len({style["fonts"]["heading"], style["fonts"]["body"]}) <= 2
        report = planner.contrast_report(planner.recipe_variables(style, CATALOG))
        failing = [row for row in report if not row["ok"]]
        assert not failing, (style["id"], failing)
        assert {row["pair"] for row in report} >= {"ring on background", "input on background"}


@pytest.mark.parametrize("style", CATALOG["styles"], ids=lambda s: s["id"])
def test_recipe_css_contains_every_variable(style):
    css = planner.recipe_css(style, CATALOG)
    for name in planner.recipe_variables(style, CATALOG)["light"]:
        assert f"--{name}:" in css


# --- CLI ---------------------------------------------------------------------


def test_cli_storage_failure_abstains(tmp_path, monkeypatch, capsys):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request()))
    monkeypatch.setattr(
        "sys.argv",
        [
            "plan.py",
            "--input",
            str(source),
            "--output",
            str(tmp_path / "out.json"),
            "--receipt",
            "/proc/nope/receipt.json",
        ],
    )
    monkeypatch.setattr(planner, "plan", lambda *_a, **_k: {"status": "abstained", "reason": "x", "plan": None})
    assert planner.main() == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "storage_error"


def test_cli_replaces_stale_plan_with_abstention_and_baseline(tmp_path, monkeypatch):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request(requirements=[{"id": "x", "capabilities": ["unknown"]}])))
    output, receipt = tmp_path / "plan.json", tmp_path / "receipt.json"
    output.write_text('{"stale": true}')
    monkeypatch.setattr(
        "sys.argv",
        ["plan.py", "--input", str(source), "--output", str(output), "--receipt", str(receipt)],
    )
    assert planner.main() == 2
    written = json.loads(output.read_text())
    assert written["status"] == "abstained" and "baseline" in written


def test_cli_writes_css_when_selected(tmp_path, monkeypatch):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request()))
    output, receipt, css = tmp_path / "plan.json", tmp_path / "receipt.json", tmp_path / "theme.css"
    real = planner.plan
    monkeypatch.setattr(planner, "plan", lambda value, **kw: real(value, send=fake(), available=ready, **kw))
    monkeypatch.setattr(
        "sys.argv",
        ["plan.py", "--input", str(source), "--output", str(output), "--receipt", str(receipt), "--css", str(css)],
    )
    assert planner.main() == 0
    assert css.read_text().startswith("/* jev-design recipe technical-console")


def test_cli_output_failure_never_leaves_selected_receipt(tmp_path, monkeypatch):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request()))
    output, receipt = tmp_path / "plan.json", tmp_path / "receipt.json"
    original = planner._write_json

    def fail_output(path, value):
        if path == output:
            raise OSError("output failed")
        original(path, value)

    monkeypatch.setattr(planner, "plan", lambda *_args, **_kwargs: {"status": "selected", "plan": {"ok": True}})
    monkeypatch.setattr(planner, "_write_json", fail_output)
    monkeypatch.setattr(
        "sys.argv",
        ["plan.py", "--input", str(source), "--output", str(output), "--receipt", str(receipt)],
    )
    assert planner.main() == 2
    assert json.loads(receipt.read_text())["reason"] == "storage_error"


def test_cli_receipt_failure_replaces_selected_output_with_abstention(tmp_path, monkeypatch):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request()))
    output, receipt = tmp_path / "plan.json", tmp_path / "receipt.json"
    original = planner._write_json

    def fail_receipt(path, value):
        if path == receipt:
            raise OSError("receipt failed")
        original(path, value)

    monkeypatch.setattr(planner, "plan", lambda *_args, **_kwargs: {"status": "selected", "plan": {"ok": True}})
    monkeypatch.setattr(planner, "_write_json", fail_receipt)
    monkeypatch.setattr(
        "sys.argv",
        ["plan.py", "--input", str(source), "--output", str(output), "--receipt", str(receipt)],
    )
    assert planner.main() == 2
    assert json.loads(output.read_text())["reason"] == "storage_error"


def test_cli_rejects_same_output_and_receipt_path(tmp_path, monkeypatch):
    source, shared = tmp_path / "request.json", tmp_path / "shared.json"
    source.write_text(json.dumps(request()))
    monkeypatch.setattr(
        "sys.argv",
        ["plan.py", "--input", str(source), "--output", str(shared), "--receipt", str(shared)],
    )
    assert planner.main() == 2
    assert not shared.exists()


# --- Docs stay in sync with the catalog --------------------------------------


def _json_blocks(text):
    import re

    return [json.loads(block) for block in re.findall(r"```json\n(.*?)```", text, re.S)]


def test_documented_briefs_and_mappings_use_catalog_names():
    skill = planner.SKILL_DIR
    briefs = _json_blocks((skill / "SKILL.md").read_text()) + _json_blocks(
        (skill / "references/brief-writing.md").read_text()
    )
    assert len(briefs) == 2
    traits = {t for s in CATALOG["styles"] for t in s["traits"]}
    for brief in briefs:
        _, candidates, _, _ = planner.build_requests(brief, CATALOG)
        assert all(candidates.values()), candidates
        assert set(brief["style_traits"]) <= traits
    table = (skill / "references/brief-writing.md").read_text().split("## Mapping")[1].split("## Worked")[0]
    rows = [line for line in table.splitlines() if line.startswith('| "')]
    assert len(rows) >= 10
    for line in rows:
        caps = [cell.strip(" `") for cell in line.split("|")[2].split(",")]
        assert planner.eligible({"capabilities": caps}, CATALOG), line
