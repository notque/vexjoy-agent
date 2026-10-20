"""grill-jev image flags: parsing, key check, direct transport, batching, per-question references."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

pytest.importorskip("PIL")
import jev_images
import jev_limits
import jev_transport
import jev_vercel
from jev_images import JevImage
from PIL import Image


def _load_module() -> Any:
    spec = importlib.util.spec_from_file_location("grill_jev_images_under_test", SCRIPTS / "grill-jev.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


grill = _load_module()


def _png(path: Path, size: tuple[int, int] = (400, 400), color: Any = (200, 30, 30)) -> Path:
    Image.new("RGB", size, color).save(path, "PNG")
    return path


def _noul(text: str, **extra: Any) -> dict[str, Any]:
    return {"type": "noul", "report_when": "true", "instructions": {"question": text}, **extra}


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("JEV_TRANSPORT", "AI_GATEWAY_API_KEY", "TYPESAFE_API_KEY"):
        monkeypatch.delenv(name, raising=False)


# --- flag parsing ------------------------------------------------------------------------------


def test_image_flag_takes_bare_paths_and_name_equals_path(tmp_path: Path) -> None:
    home = _png(tmp_path / "home page.png")
    cpu = _png(tmp_path / "cpu.png")

    found = grill._parse_image_specs([f"dash={cpu}", str(home)], None)

    assert found == {"dash": cpu, "home_page": home}


def test_path_containing_equals_is_a_path_not_a_name(tmp_path: Path) -> None:
    odd = _png(tmp_path / "a=b.png")

    assert grill._parse_image_specs([str(odd)], None) == {"a_b": odd}


def test_images_dir_adds_image_files_by_stem_and_skips_others(tmp_path: Path) -> None:
    shots = tmp_path / "shots"
    shots.mkdir()
    b = _png(shots / "b.PNG")
    a = _png(shots / "a.png")
    (shots / "notes.txt").write_text("x")

    found = grill._parse_image_specs([], str(shots))

    assert list(found) == ["a", "b"]
    assert found == {"a": a, "b": b}


@pytest.mark.parametrize("case", ["duplicate", "missing", "empty_dir", "no_dir"])
def test_bad_image_inputs_raise_value_error(tmp_path: Path, case: str) -> None:
    one = _png(tmp_path / "one.png")
    empty = tmp_path / "empty"
    empty.mkdir()
    specs, directory = {
        "duplicate": ([f"x={one}", f"x={one}"], None),
        "missing": ([str(tmp_path / "nope.png")], None),
        "empty_dir": ([], str(empty)),
        "no_dir": ([], str(tmp_path / "gone")),
    }[case]

    with pytest.raises(ValueError):
        grill._parse_image_specs(specs, directory)


# --- CLI: key check and forced direct transport -------------------------------------------------


def _run_main(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> int:
    monkeypatch.setattr(sys, "argv", ["grill-jev.py", *argv])
    with pytest.raises(SystemExit) as exc:
        grill.main()
    return int(exc.value.code)


def _battery(tmp_path: Path, questions: dict[str, Any]) -> str:
    path = tmp_path / "q.json"
    path.write_text(json.dumps({"questions": questions}), encoding="utf-8")
    return str(path)


def test_images_without_typesafe_key_exit_nonzero_with_one_line_and_no_calls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    shot = _png(tmp_path / "shot.png")
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gw")  # a Vercel key must not be a way around it

    def boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("no transport call without TYPESAFE_API_KEY")

    monkeypatch.setattr(jev_transport, "evaluate", boom)
    monkeypatch.setattr(jev_vercel, "evaluate", boom)

    code = _run_main(monkeypatch, ["--image", str(shot), "--questions-file", _battery(tmp_path, {"q": _noul("ok?")})])

    err = capsys.readouterr().err.strip().splitlines()
    assert code == 2
    assert len(err) == 1 and "TYPESAFE_API_KEY" in err[0]


def _answer_for(question: dict[str, Any]) -> dict[str, Any]:
    if question.get("type") == "choice":
        return {"choice": next(iter(question["criteria"])), "confidence": 0.5}
    if question.get("type") == "score":
        return {"score": 1.0}
    return {"noul": 0.5}


def _fake_direct(calls: list[dict[str, Any]]) -> Any:
    def fake(state: Any, questions: dict[str, Any], *, timeout: float, assets: Any = None, images_header: bool = False):
        calls.append({"state": state, "questions": questions, "assets": assets, "header": images_header})
        return {"answers": {qid: _answer_for(q) for qid, q in questions.items()}}

    return fake


def test_images_force_direct_even_when_vercel_is_configured(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shot = _png(tmp_path / "shot.png")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gw")
    monkeypatch.setenv("JEV_TRANSPORT", "vercel")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(jev_transport, "_direct_one", _fake_direct(calls))

    def vercel_boom(*a: Any, **k: Any) -> Any:
        raise AssertionError("Vercel must not be attempted for images")

    monkeypatch.setattr(jev_vercel, "evaluate", vercel_boom)

    code = _run_main(
        monkeypatch, ["--image", f"shot={shot}", "--questions-file", _battery(tmp_path, {"q": _noul("ok?")})]
    )

    assert code == 0
    assert len(calls) == 1
    assert calls[0]["header"] is True
    assert len(calls[0]["assets"]) == 1
    assert list(calls[0]["state"]["images"]) == ["shot"]
    assert isinstance(calls[0]["state"]["images"]["shot"], str)  # swapped for a reference


def test_images_alone_need_no_text_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shot = _png(tmp_path / "shot.png")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(jev_transport, "_direct_one", _fake_direct(calls))

    code = _run_main(monkeypatch, ["--image", str(shot), "--questions-file", _battery(tmp_path, {"q": _noul("ok?")})])

    assert code == 0
    artifact = calls[0]["state"]["artifact"]
    assert "attached" in artifact and "state.images" not in artifact


# --- per-question references ---------------------------------------------------------------------


def test_plan_images_field_limits_state_images_and_unreferenced_gets_all() -> None:
    names = ["a", "b", "c"]

    assert grill._image_plan("q", _noul("x", images=["b"]), names) == (["b"], {})
    assert grill._image_plan("q", _noul("x"), names) == (["a", "b", "c"], {})
    assert grill._image_plan("q", _noul("Is {img:c} clear? Compare {img:c}"), names) == ([], {"c": 2})


def test_plan_rejects_unknown_names_and_bad_field() -> None:
    with pytest.raises(ValueError, match="unknown image"):
        grill._image_plan("q", _noul("x", images=["zzz"]), ["a"])
    with pytest.raises(ValueError, match="unknown image"):
        grill._image_plan("q", _noul("see {img:zzz}"), ["a"])
    with pytest.raises(ValueError, match="list of image names"):
        grill._image_plan("q", _noul("x", images="a"), ["a"])


def test_each_request_carries_only_the_images_its_questions_reference(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    images = {
        "home": JevImage(_png(tmp_path / "home.png")),
        "cpu": JevImage(_png(tmp_path / "cpu.png", color=(10, 10, 200))),
        "disk": JevImage(_png(tmp_path / "disk.png", color=(10, 200, 10))),
    }
    sent: list[tuple[dict[str, Any], dict[str, Any], Any]] = []

    def fake_evaluate(state: Any, questions: dict[str, Any], *, timeout: float, images: Any = None) -> dict[str, Any]:
        sent.append((state, questions, images))
        return {"answers": {qid: {"noul": 0.2} for qid in questions}}

    monkeypatch.setattr(jev_transport, "evaluate", fake_evaluate)
    questions = {
        "q_home": _noul("home clear?", images=["home"]),
        "q_cpu": _noul("cpu misleading?", images=["cpu"]),
        "q_inline": _noul("is {img:disk} labeled?"),
        "q_both": _noul("do they agree?", images=["home", "cpu"]),
    }

    answers = grill._run_battery({"artifact": "review"}, questions, timeout=5, images=images)

    assert set(answers) == set(questions)
    seen = {frozenset(q): (sorted(s.get("images", {})), sorted(i or {})) for s, q, i in sent}
    assert seen[frozenset({"q_home"})] == (["home"], ["home"])
    assert seen[frozenset({"q_cpu"})] == (["cpu"], ["cpu"])
    assert seen[frozenset({"q_inline"})] == ([], ["disk"])
    assert seen[frozenset({"q_both"})] == (["cpu", "home"], ["cpu", "home"])
    assert all("images" not in q for _, qs, _ in sent for q in qs.values())  # grill-only field stripped


# --- batching within limits ----------------------------------------------------------------------


def test_questions_sharing_images_pack_into_requests_under_the_image_target() -> None:
    tokens = {"a": 6000, "b": 6000}
    questions = {f"q{i}": _noul("x" * 4000, images=["a"]) for i in range(40)}  # ~1000 tokens each
    plans = {qid: grill._image_plan(qid, q, ["a", "b"]) for qid, q in questions.items()}

    batches, refused = grill._image_batches({"artifact": "plan"}, questions, plans, tokens)

    assert not refused
    assert len(batches) > 1
    assert sorted(q for b in batches for q in b) == sorted(questions)
    for batch in batches:
        total = (
            jev_limits.estimate_tokens({"artifact": "plan"})
            + tokens["a"]
            + sum(jev_limits.estimate_tokens(grill._wire_question(questions[q])) for q in batch)
        )
        assert total <= jev_limits.IMAGE_REQUEST_TARGET_TOKENS
        assert len(batch) <= grill.BATCH_SIZE


def test_one_request_when_everything_fits_and_groups_by_image_set() -> None:
    tokens = {"a": 500, "b": 500}
    questions = {
        "qa1": _noul("x", images=["a"]),
        "qb": _noul("x", images=["b"]),
        "qa2": _noul("x", images=["a"]),
    }
    plans = {qid: grill._image_plan(qid, q, ["a", "b"]) for qid, q in questions.items()}

    batches, refused = grill._image_batches({"artifact": "plan"}, questions, plans, tokens)

    assert not refused
    assert sorted(map(sorted, batches)) == [["qa1", "qa2"], ["qb"]]


def test_unreferenced_question_that_cannot_carry_all_images_is_refused_with_a_reason() -> None:
    tokens = {"a": 14000, "b": 14000}
    questions = {"q_all": _noul("overall?"), "q_a": _noul("a?", images=["a"])}
    plans = {qid: grill._image_plan(qid, q, ["a", "b"]) for qid, q in questions.items()}

    batches, refused = grill._image_batches({"artifact": "plan"}, questions, plans, tokens)

    assert batches == [["q_a"]]
    assert list(refused) == ["q_all"]
    assert "--questions-file" in refused["q_all"] and '"images": ["a"]' in refused["q_all"]


def test_refused_question_is_reported_unanswered_and_run_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    big = [_png(tmp_path / f"big{i}.png", (1500, 1500)) for i in range(5)]  # ~6000 tokens each
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(jev_transport, "_direct_one", _fake_direct(calls))
    questions = {"q_all": _noul("overall?"), "q_one": _noul("first?", images=["big0"])}
    argv = [x for p in big for x in ("--image", str(p))]

    code = _run_main(monkeypatch, [*argv, "--questions-file", _battery(tmp_path, questions)])

    out = capsys.readouterr().out
    assert code == 2
    assert "UNANSWERED" in out and "q_all" in out
    assert [list(c["questions"]) for c in calls] == [["q_one"]]


def test_images_field_without_image_flags_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")

    code = _run_main(
        monkeypatch, ["--text", "plan", "--questions-file", _battery(tmp_path, {"q": _noul("x", images=["a"])})]
    )

    assert code == 2
    assert "no --image" in capsys.readouterr().err


def test_unknown_image_name_in_battery_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    shot = _png(tmp_path / "shot.png")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")

    code = _run_main(
        monkeypatch,
        ["--image", str(shot), "--questions-file", _battery(tmp_path, {"q": _noul("x", images=["nope"])})],
    )

    assert code == 2
    assert "unknown image" in capsys.readouterr().err


# --- review fixes ---------------------------------------------------------------------------------


def test_literal_placeholders_in_artifact_and_context_are_sent_as_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shot = _png(tmp_path / "shot.png")
    doc = tmp_path / "SKILL.md"
    doc.write_text("Write {img:foo} or {img:shot} in a question.", encoding="utf-8")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(jev_transport, "_direct_one", _fake_direct(calls))

    code = _run_main(
        monkeypatch,
        [
            "--file", str(doc), "--context", "see {img:shot}", "--image", str(shot),
            "--questions-file", _battery(tmp_path, {"q": _noul("ok?")}),
        ],
    )  # fmt: skip

    state = calls[0]["state"]
    assert code == 0
    assert "{img :foo}" in state["artifact"] and "{img :shot}" in state["artifact"]
    assert state["context"] == "see {img :shot}"
    assert len(calls[0]["assets"]) == 1  # only the real image, not one per literal placeholder


def test_fallback_battery_with_many_images_is_sent_once_per_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    shots = tmp_path / "shots"
    shots.mkdir()
    for i in range(5):
        _png(shots / f"s{i}.png", (1500, 1500))  # ~6000 tokens each: all five never fit one request
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(jev_transport, "_direct_one", _fake_direct(calls))

    _run_main(monkeypatch, ["--images-dir", str(shots)])

    captured = capsys.readouterr()
    assert "UNANSWERED" not in captured.out
    assert len(calls) == 5
    assert all(len(c["assets"]) == 1 for c in calls)
    assert len(grill.FALLBACK_QUESTIONS) * 5 == sum(len(c["questions"]) for c in calls)
    assert "once per image" in captured.err


def test_earlier_answers_are_reported_when_a_later_batch_fails() -> None:
    qs = {f"q{i}": _noul("x" * 4000) for i in range(40)}  # forces several batches
    seen: list[int] = []

    def fake_evaluate(state: Any, questions: dict[str, Any], *, timeout: float, images: Any = None) -> dict[str, Any]:
        seen.append(len(questions))
        if len(seen) > 1:
            raise jev_transport.JevTransportError("too big", source=jev_transport.REQUEST_TOO_LARGE)
        return {"answers": {qid: {"noul": 0.2} for qid in questions}}

    original = jev_transport.evaluate
    jev_transport.evaluate = fake_evaluate  # type: ignore[assignment]
    try:
        answers = grill._run_battery({"artifact": "a"}, qs, timeout=5)
    finally:
        jev_transport.evaluate = original  # type: ignore[assignment]

    paid = [q for q, a in answers.items() if "error" not in a]
    unrun = [q for q, a in answers.items() if "error" in a]
    assert paid and unrun and len(paid) + len(unrun) == 40
    assert all("not run: too big" in answers[q]["error"] for q in unrun)


def test_explicit_vercel_transport_is_overridden_with_a_warning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    shot = _png(tmp_path / "shot.png")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("JEV_TRANSPORT", "vercel")
    monkeypatch.setattr(jev_transport, "_direct_one", _fake_direct([]))

    _run_main(monkeypatch, ["--image", str(shot), "--questions-file", _battery(tmp_path, {"q": _noul("ok?")})])

    assert "JEV_TRANSPORT=vercel ignored" in capsys.readouterr().err


@pytest.mark.parametrize("transport", [None, "auto", "direct"])
def test_no_vercel_warning_unless_vercel_is_explicitly_requested(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], transport: str | None
) -> None:
    shot = _png(tmp_path / "shot.png")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    monkeypatch.setenv("AI_GATEWAY_API_KEY", "gw")
    if transport is None:
        monkeypatch.delenv("JEV_TRANSPORT", raising=False)
    else:
        monkeypatch.setenv("JEV_TRANSPORT", transport)
    monkeypatch.setattr(jev_transport, "_direct_one", _fake_direct([]))

    _run_main(monkeypatch, ["--image", str(shot), "--questions-file", _battery(tmp_path, {"q": _noul("ok?")})])

    assert "ignored" not in capsys.readouterr().err


def test_missing_name_equals_path_error_shows_the_original_argument(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"from 'a=b/nonexist.png'"):
        grill._parse_image_specs(["a=b/nonexist.png"], None)


def test_text_only_main_sends_the_same_payload_and_leaves_transport_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JEV_TRANSPORT", "vercel")
    sent: list[tuple[Any, dict[str, Any], Any]] = []

    def fake_evaluate(state: Any, questions: dict[str, Any], *, timeout: float, images: Any = None) -> dict[str, Any]:
        sent.append((state, questions, images))
        return {
            "answers": {
                qid: {"noul": 0.5, "choice": next(iter(q.get("criteria") or {"x": 0})), "score": 1.0}
                for qid, q in questions.items()
            }
        }

    monkeypatch.setattr(jev_transport, "evaluate", fake_evaluate)

    _run_main(monkeypatch, ["--text", "plan {img:x}", "--context", "ctx"])

    assert sent
    assert all(state == {"artifact": "plan {img:x}", "context": "ctx"} for state, _, _ in sent)
    assert all(images is None for _, _, images in sent)
    assert set().union(*(q for _, q, _ in sent)) == set(grill.FALLBACK_QUESTIONS)
    assert grill.os.environ["JEV_TRANSPORT"] == "vercel"
