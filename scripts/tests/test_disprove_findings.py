"""Tests for scripts/disprove-findings.py: prompt building and the drop rule."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

_scripts = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, _scripts)
df = importlib.import_module("disprove-findings")
sys.path.pop(0)

DIFF = """--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
 def load(path):
+    data = json.loads(open(path).read())
     return data
"""
FILES = {"app.py": "def load(path):\n    data = json.loads(open(path).read())\n    return data\n"}
FINDINGS = [
    {
        "file": "app.py",
        "line": 2,
        "severity": "HIGH",
        "quote": "json.loads(open(path).read())",
        "claim": "leaks handle",
    },
    {"fid": "x9", "file": "app.py", "line": 3, "severity": "LOW", "quote": "return data", "claim": "odd return"},
]


def reply(verdicts: dict) -> str:
    return "```json\n" + json.dumps({"verdicts": verdicts}) + "\n```"


def apply(verdicts: dict) -> dict:
    return df.apply_verdicts(FINDINGS, reply(verdicts), DIFF, FILES)


def test_prompt_carries_diff_numbered_files_and_every_fid() -> None:
    text = df.build_prompt(FINDINGS, DIFF, FILES, "python")
    assert "+    data = json.loads" in text
    assert '<file path="app.py">' in text and "    2|     data = json.loads" in text
    assert "fid=f1 " in text and "fid=x9 " in text
    assert "Language: python" in text


def test_grounded_refute_drops() -> None:
    out = apply({"f1": {"verdict": "refuted", "reason": "`json.loads(open(path).read())` is fine here"}})
    assert [f["fid"] for f in out["dropped"]] == ["f1"]
    assert [f["fid"] for f in out["kept"]] == ["x9"]
    assert "refuted_by" in out["dropped"][0]


def test_whitespace_in_quote_is_normalized() -> None:
    out = apply({"f1": {"verdict": "refuted", "reason": "`return   data` is fine"}})
    assert len(out["dropped"]) == 1


@pytest.mark.parametrize(
    "verdict",
    [
        {"verdict": "stands", "reason": "`json.loads(open(path).read())` leaks"},
        {"verdict": "refuted", "reason": "this cannot happen"},
        {"verdict": "refuted", "reason": "`os.remove(path)` is never called"},
        {"verdict": "refuted", "reason": "`a=1` is short"},
        {"verdict": "maybe", "reason": "`json.loads(open(path).read())`"},
        {"reason": "`json.loads(open(path).read())`"},
        "refuted",
    ],
)
def test_everything_else_keeps(verdict) -> None:
    out = apply({"f1": verdict})
    assert out["dropped"] == [] and len(out["kept"]) == 2


def test_quote_from_removed_diff_line_grounds() -> None:
    diff = DIFF.replace(" def load", "-    gone_line_here(path)\n def load")
    out = df.apply_verdicts(
        FINDINGS, reply({"f1": {"verdict": "refuted", "reason": "`gone_line_here(path)` is dead"}}), diff, {}
    )
    # removed lines are code the reviewer saw, so a quote of one is grounded
    assert len(out["dropped"]) == 1


@pytest.mark.parametrize("text", ["", "not json", "[1, 2]", '{"verdicts": []}', '{"verdicts": {"f1": 3}}'])
def test_malformed_reply_keeps_all(text) -> None:
    out = df.apply_verdicts(FINDINGS, text, DIFF, FILES)
    assert out["dropped"] == [] and len(out["kept"]) == 2


def test_bare_verdict_map_without_wrapper_is_accepted() -> None:
    text = json.dumps({"f1": {"verdict": "refuted", "reason": "`json.loads(open(path).read())` ok"}})
    assert len(df.apply_verdicts(FINDINGS, text, DIFF, FILES)["dropped"]) == 1


def test_cli_prompt_and_apply(tmp_path, capsys) -> None:
    (tmp_path / "f.json").write_text(json.dumps(FINDINGS))
    (tmp_path / "d.patch").write_text(DIFF)
    (tmp_path / "app.py").write_text(FILES["app.py"])
    (tmp_path / "r.txt").write_text(reply({"f1": {"verdict": "refuted", "reason": "`return data` x"}}))
    base = [
        "--findings",
        str(tmp_path / "f.json"),
        "--diff",
        str(tmp_path / "d.patch"),
        "--file",
        str(tmp_path / "app.py"),
    ]
    assert df.main(["prompt", *base]) == 0
    assert "<findings>" in capsys.readouterr().out
    assert df.main(["apply", *base, "--verdicts", str(tmp_path / "r.txt")]) == 0
    out = json.loads(capsys.readouterr().out)
    assert [f["fid"] for f in out["dropped"]] == ["f1"] and [f["fid"] for f in out["kept"]] == ["x9"]


def test_cli_bad_input_exits_2(tmp_path, capsys) -> None:
    (tmp_path / "f.json").write_text('{"not": "a list"}')
    (tmp_path / "d.patch").write_text(DIFF)
    assert df.main(["prompt", "--findings", str(tmp_path / "f.json"), "--diff", str(tmp_path / "d.patch")]) == 2
    assert df.main(["prompt", "--findings", str(tmp_path / "missing.json"), "--diff", str(tmp_path / "d.patch")]) == 2
