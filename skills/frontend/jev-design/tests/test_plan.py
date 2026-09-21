from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts/plan.py"
SPEC = importlib.util.spec_from_file_location("jev_design_plan", SCRIPT)
planner = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(planner)
TEST_CREDENTIAL = "unit-test-placeholder"
EMPTY_CREDENTIAL = ""


def request(**updates):
    value = {
        "brief": "Dense technical support workspace",
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


def response(payload, *, component_overrides=None, fitness=0.9, style="technical-console"):
    component_overrides = component_overrides or {}
    answers = {}
    for name, question in payload["questions"].items():
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
    return {"answers": answers, "usage": {"input_tokens": 10, "output_tokens": 2}}


def fake(**kwargs):
    return lambda payload, *_: (response(payload, **kwargs), 4.0)


def test_end_to_end_selects_multiple_components_and_style():
    result = planner.plan(request(), api_key=TEST_CREDENTIAL, call=fake())
    assert result["status"] == "selected"
    assert [x["component"] for x in result["plan"]["components"]] == ["data-table", "sheet"]
    assert result["plan"]["style"]["id"] == "technical-console"
    assert result["model"] == "jev-1.13.0" and len(result["attempts"]) == 1


def test_deterministic_filter_and_baseline_precede_call():
    seen = []

    def call(payload, *_):
        seen.append(payload)
        return response(payload), 1.0

    result = planner.plan(request(), api_key=TEST_CREDENTIAL, call=call)
    assert [x["id"] for x in seen[0]["state"]["eligible_components"]["results"]] == ["data-table"]
    assert result["baseline"] == {"results": "data-table", "details": "sheet"}


def test_normalized_requirement_ids_cannot_collide():
    value = request(
        requirements=[
            {"id": "a-b", "capabilities": ["summary"]},
            {"id": "a_b", "capabilities": ["summary"]},
        ]
    )
    assert planner.plan(value, api_key=TEST_CREDENTIAL, call=fake())["reason"] == "invalid_request"


def test_no_candidate_and_unavailable_abstain_without_permission():
    def no_call(*_):
        raise AssertionError("called")

    assert (
        planner.plan(
            request(requirements=[{"id": "x", "capabilities": ["unknown"]}]), api_key=TEST_CREDENTIAL, call=no_call
        )["reason"]
        == "no_compatible_component"
    )
    assert planner.plan(request(), api_key=EMPTY_CREDENTIAL, call=no_call)["reason"] == "jev_unavailable"


def test_low_fitness_and_none_abstain():
    assert planner.plan(request(), api_key=TEST_CREDENTIAL, call=fake(fitness=0.4))["reason"] == "low_fitness"
    assert (
        planner.plan(request(), api_key=TEST_CREDENTIAL, call=fake(component_overrides={"component_results": "none"}))[
            "reason"
        ]
        == "none_or_out_of_catalog"
    )


def test_partial_malformed_and_out_of_catalog_abstain():
    assert (
        planner.plan(request(), api_key=TEST_CREDENTIAL, call=lambda *_: ({"answers": {}}, 1.0))["reason"]
        == "malformed_response"
    )

    def bad(payload, *_):
        data = response(payload)
        data["answers"]["component_results"]["choice"] = "invented"
        return data, 1.0

    assert planner.plan(request(), api_key=TEST_CREDENTIAL, call=bad)["reason"] == "malformed_response"

    def bad_prob(payload, *_):
        data = response(payload)
        data["answers"]["style"]["probabilities"] = {"technical-console": 1.5}
        return data, 1.0

    assert planner.plan(request(), api_key=TEST_CREDENTIAL, call=bad_prob)["reason"] == "malformed_response"

    def contradictory(payload, *_):
        data = response(payload)
        answer = data["answers"]["component_results"]
        answer["probabilities"] = {"data-table": 0.01, "none": 0.99}
        return data, 1.0

    assert planner.plan(request(), api_key=TEST_CREDENTIAL, call=contradictory)["reason"] == "malformed_response"


def test_bounds_and_capabilities_contract():
    assert (
        planner.plan(request(brief="x" * (planner.MAX_BRIEF + 1)), api_key=TEST_CREDENTIAL, call=fake())["reason"]
        == "invalid_request"
    )
    listed = planner.capabilities(planner.load_catalog())
    assert "tabular-data" in listed["capabilities"] and "technical" in listed["style_traits"]


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
    assert planner.main() == 2
    assert json.loads(capsys.readouterr().out)["reason"] == "storage_error"


def test_cli_replaces_stale_plan_with_abstention(tmp_path, monkeypatch):
    source = tmp_path / "request.json"
    source.write_text(json.dumps(request(requirements=[{"id": "x", "capabilities": ["unknown"]}])))
    output, receipt = tmp_path / "plan.json", tmp_path / "receipt.json"
    output.write_text('{"stale": true}')
    monkeypatch.setattr(
        "sys.argv",
        ["plan.py", "--input", str(source), "--output", str(output), "--receipt", str(receipt)],
    )
    assert planner.main() == 2
    assert json.loads(output.read_text())["status"] == "abstained"


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
