"""Tests for scripts/mutation_check: operators, sampling, sandbox redirect, baseline logic, scope, and report."""

from __future__ import annotations

import ast
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import ClassVar

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from mutation_check import engine, mutate, report, scope


def gen(source: str, **kw):
    """Generate every mutant (cap high) for a dedented snippet."""
    return mutate.generate(textwrap.dedent(source), "snippet.py", cap=kw.pop("cap", 500), **kw)


def mutated(source: str, operator: str) -> list[str]:
    """Return the mutated sources an operator produces for a snippet."""
    return [m.source for m in gen(source).mutants if m.operator == operator]


def line_diffs(source: str, operator: str) -> set[tuple[str, str]]:
    """Return {(removed line, added line)} pairs, stripped, for one operator."""
    original = textwrap.dedent(source).splitlines()
    out = set()
    for new in mutated(source, operator):
        for before, after in zip(original, new.splitlines(), strict=False):
            if before != after:
                out.add((before.strip(), after.strip()))
    return out


# --------------------------------------------------------------------------------------------- operators


class TestOperators:
    def test_comparison_flip_covers_each_operator(self):
        src = "def f(x, y):\n    if x == 1 and y is not None and x not in y and x < 3:\n        return 1\n"
        pairs = {a for _, a in line_diffs(src, "cmp_flip")}
        assert any("x != 1" in p for p in pairs)
        assert any("y is None" in p for p in pairs)
        assert any("x in y" in p and "not in" not in p.split("x in y")[0][-4:] for p in pairs)
        assert any("x >= 3" in p for p in pairs)

    def test_bool_swap_changes_one_connector_at_a_time(self):
        out = mutated("def f(a, b, c):\n    return a and b or c\n", "bool_swap")
        assert sorted(o.splitlines()[1].strip() for o in out) == ["return a and b and c", "return a or b or c"]

    def test_negate_if_wraps_and_unwraps(self):
        pairs = line_diffs("def f(a, b):\n    if a:\n        return 1\n    if not b:\n        return 2\n", "negate_if")
        assert ("if a:", "if not (a):") in pairs
        assert ("if not b:", "if b:") in pairs

    def test_drop_branch_empties_if_else_and_except(self):
        src = """
        def f(a):
            try:
                if a:
                    x = 1
                    y = 2
                else:
                    x = 3
            except ValueError:
                x = 4
            return x
        """
        outs = mutated(src, "drop_branch")
        assert len(outs) == 3
        assert all(ast.parse(o) for o in outs)
        joined = "\n".join(outs)
        assert "pass" in joined and joined.count("x = 1") == 2  # if-body dropped in exactly one mutant

    def test_drop_branch_skips_bodies_that_are_already_empty(self):
        assert mutated("def f(a):\n    if a:\n        pass\n", "drop_branch") == []

    def test_const_flips_bools_ints_and_decision_strings(self):
        src = 'def f():\n    a = True\n    b = 0\n    c = 7\n    d = {"permissionDecision": "deny"}\n    return a, b, c, d\n'
        pairs = {a for _, a in line_diffs(src, "const")}
        assert "a = False" in pairs
        assert "b = 1" in pairs
        assert "c = 8" in pairs
        assert 'd = {"permissionDecision": "allow"}' in pairs

    def test_const_leaves_docstrings_fstrings_and_annotations_alone(self):
        src = 'def f(x: "deny", n: int = 5) -> "allow":\n    """deny 3"""\n    return f"deny {x} 3"\n'
        descs = [m.description for m in gen(src).mutants if m.operator == "const"]
        assert descs == ["`5` -> `6`"]

    def test_regex_alt_drops_each_alternative_and_keeps_classes_and_escapes(self):
        src = 'import re\nP = re.compile(r"foo|bar|(a|b)x|[|]y|z\\|w")\n'
        pairs = {a for _, a in line_diffs(src, "regex_alt")}
        assert 'P = re.compile(r"bar|(a|b)x|[|]y|z\\|w")' in pairs
        assert 'P = re.compile(r"foo|bar|(b)x|[|]y|z\\|w")' in pairs
        # 5 top-level alternatives + 2 inside the group; `[|]` and `\|` are not alternation points
        assert len(pairs) == 7

    def test_regex_alt_reaches_a_pattern_held_in_a_name(self):
        src = 'import re\nPAT = r"one|two"\nRX = re.compile(PAT)\n'
        assert len(mutated(src, "regex_alt")) == 2

    def test_regex_alt_ignores_strings_that_never_reach_re(self):
        assert mutated('X = "one|two"\n', "regex_alt") == []

    def test_regex_alt_skips_nonraw_literal_with_backslash(self):
        assert mutated('import re\nP = re.compile("a\\\\d|b")\n', "regex_alt") == []

    def test_early_return_goes_in_the_middle_of_a_long_function(self):
        src = "def f(a):\n    a += 1\n    a += 2\n    a += 3\n    a += 4\n    return a\n"
        out = mutated(src, "early_return")
        assert len(out) == 1
        assert out[0].splitlines()[3] == "    return"

    def test_early_return_skips_short_functions(self):
        assert mutated("def f(a):\n    a += 1\n    return a\n", "early_return") == []

    def test_return_none_replaces_values_only(self):
        pairs = line_diffs("def f(a):\n    if a:\n        return a + 1\n    return None\n", "return_none")
        assert pairs == {("return a + 1", "return None")}

    def test_main_guard_is_never_mutated(self):
        src = 'def main():\n    return 1\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'
        assert not [m for m in gen(src).mutants if m.line >= 4]


# --------------------------------------------------------------------------------------- validity/sampling


class TestGeneration:
    SRC = textwrap.dedent(
        """
        import re
        RX = re.compile(r"a|b")
        def f(x, y, z):
            if x > 1 and y:
                z += 1
                z += 2
                z += 3
            elif x == 0:
                return True
            else:
                return 3
            return z
        """
    )

    def test_same_seed_same_mutants_and_cap_respected(self):
        a = mutate.generate(self.SRC, "f.py", cap=9, seed=1)
        b = mutate.generate(self.SRC, "f.py", cap=9, seed=1)
        assert [m.id for m in a.mutants] == [m.id for m in b.mutants]
        assert [m.source for m in a.mutants] == [m.source for m in b.mutants]
        assert len(a.mutants) == 9

    def test_different_seed_samples_differently(self):
        a = mutate.generate(self.SRC, "f.py", cap=6, seed=1)
        c = mutate.generate(self.SRC, "f.py", cap=6, seed=2)
        assert {m.source for m in a.mutants} != {m.source for m in c.mutants}

    def test_sampling_spreads_over_operators(self):
        ops = {m.operator for m in mutate.generate(self.SRC, "f.py", cap=8).mutants}
        assert len(ops) >= 6

    def test_every_mutant_parses_and_differs_by_one_hunk(self):
        for m in mutate.generate(self.SRC, "f.py", cap=200).mutants:
            ast.parse(m.source)
            assert m.source != self.SRC
            assert m.diff.count("\n@@") <= 1

    def test_unparseable_mutant_is_rejected(self):
        broken = mutate._Edit("const", 0, 1, b"(", 1, "bad")
        assert not mutate._valid("x = 1\n", mutate.apply_edit("x = 1\n", broken), broken, "x.py")

    def test_unchanged_mutant_is_rejected(self):
        same = mutate._Edit("const", 0, 1, b"x", 1, "noop")
        assert not mutate._valid("x = 1\n", "x = 1\n", same, "x.py")

    def test_regex_mutant_that_no_longer_compiles_is_rejected(self):
        src = 'import re\nP = re.compile(r"(a|b)+|*")\n'
        out = gen(src).mutants
        for m in out:
            ast.parse(m.source)
            if m.operator == "regex_alt":
                re.compile(re.search(r'r"(.*)"', m.source).group(1))

    def test_anchor_not_found_is_an_error_not_a_skip(self, monkeypatch):
        monkeypatch.setattr(mutate, "CMP_FIND", re.compile(rb"(?!x)x"))
        result = mutate.generate("def f(a):\n    return a == 1\n", "f.py", cap=50)
        assert result.errors and "comparison operator" in result.errors[0]
        assert not [m for m in result.mutants if m.operator == "cmp_flip"]

    def test_clean_corpus_has_no_anchor_errors(self):
        repo = SCRIPTS.parent
        for hook in ("pretool-worktree-edit-guard.py", "ci-merge-gate.py"):
            result = mutate.generate((repo / "hooks" / hook).read_text(encoding="utf-8"), hook, cap=40)
            assert result.errors == []
            assert len(result.mutants) == 40


# ------------------------------------------------------------------------------------------ pytest parsing


class TestEngineParsing:
    def test_parse_failed_ids_and_passed_count(self):
        out = "FAILED hooks/tests/test_a.py::test_x - assert 1\nERROR hooks/tests/test_b.py::test_y\n2 failed, 14 passed in 3s\n"
        res = engine.parse_pytest(out, 1, 3.0)
        assert res.failed == ["hooks/tests/test_a.py::test_x", "hooks/tests/test_b.py::test_y"]
        assert res.passed == 14

    def test_collection_error_detected(self):
        res = engine.parse_pytest("ERROR collecting x.py\n", 2, 1.0)
        assert res.collection_error

    def _baseline(self, monkeypatch, runs):
        it = iter(runs)

        class FakeSandbox:
            def pytest(self, tests, deselect=None, timeout=0, fail_fast=False):
                return next(it)

        return engine.baseline(FakeSandbox(), ["t.py"])

    def test_flaky_tests_are_dropped_not_fatal(self, monkeypatch):
        runs = [
            engine.RunResult(1, 1, ["t::a"], 9),
            engine.RunResult(0, 1, [], 10),
            engine.RunResult(0, 1, [], 10),
        ]
        base = self._baseline(monkeypatch, runs)
        assert base.usable and base.deselect == ["t::a"]

    def test_always_failing_test_makes_hook_unrunnable(self, monkeypatch):
        runs = [engine.RunResult(1, 1, ["t::a"], 9) for _ in range(3)]
        base = self._baseline(monkeypatch, runs)
        assert not base.usable and base.broken == ["t::a"]

    def test_collection_error_makes_hook_unrunnable(self, monkeypatch):
        runs = [engine.RunResult(2, 1, [], 0, collection_error=True) for _ in range(3)]
        assert not self._baseline(monkeypatch, runs).usable


# ------------------------------------------------------------------------------- real sandbox, redirect


HOOK_SRC = textwrap.dedent(
    '''\
    """Tiny gate: deny when the command mentions rm."""

    def decide(command):
        if "rm" in command:
            return "deny"
        return "allow"


    def main():
        import json, sys
        data = json.load(sys.stdin)
        print(decide(data.get("command", "")))


    if __name__ == "__main__":
        main()
    '''
)
GOOD_TEST = textwrap.dedent(
    """\
    import importlib.util
    from pathlib import Path

    HOOK = Path(__file__).parent.parent / "gate.py"
    spec = importlib.util.spec_from_file_location("gate", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)


    def test_denies_rm():
        assert mod.decide("rm -rf x") == "deny"


    def test_allows_ls():
        assert mod.decide("ls") == "allow"
    """
)
HARDCODED_TEST = GOOD_TEST.replace('Path(__file__).parent.parent / "gate.py"', "Path(__REAL__)")


@pytest.fixture
def mini_repo(tmp_path):
    repo = tmp_path / "repo"
    (repo / "hooks" / "tests").mkdir(parents=True)
    (repo / "hooks" / "gate.py").write_text(HOOK_SRC, encoding="utf-8")
    (repo / "hooks" / "tests" / "test_gate.py").write_text(GOOD_TEST, encoding="utf-8")
    return repo


@pytest.fixture
def sandbox(mini_repo, tmp_path):
    return engine.Sandbox(mini_repo, tmp_path / "sb", 0)


class TestSandbox:
    TESTS: ClassVar[list[str]] = ["hooks/tests/test_gate.py"]

    def test_baseline_passes_and_redirect_is_proved(self, sandbox):
        base = engine.baseline(sandbox, self.TESTS)
        assert base.usable, base.reason
        assert engine.redirect_proved(sandbox, "hooks/gate.py", self.TESTS, [], 120) is not None

    def test_module_level_probe_proves_redirect_when_tests_never_call_main(self, sandbox):
        # `main` is not exercised by the tests, so only the module-level probe can fail them.
        assert engine.redirect_proved(sandbox, "hooks/gate.py", self.TESTS, [], 120) == "module-level raise"

    def test_hardcoded_path_test_cannot_be_redirected(self, mini_repo, tmp_path):
        real = mini_repo / "hooks" / "gate.py"
        (mini_repo / "hooks" / "tests" / "test_gate.py").write_text(
            HARDCODED_TEST.replace("__REAL__", repr(str(real))), encoding="utf-8"
        )
        sb = engine.Sandbox(mini_repo, tmp_path / "sb2", 0)
        assert engine.redirect_proved(sb, "hooks/gate.py", self.TESTS, [], 120) is None

    def test_mutant_is_killed_or_survives_and_real_file_is_untouched(self, sandbox, mini_repo):
        before = (mini_repo / "hooks" / "gate.py").read_text(encoding="utf-8")
        original = sandbox.read("hooks/gate.py")
        killed = original.replace('return "deny"', 'return "allow"')
        status, kind, _ = engine.run_mutant(sandbox, "hooks/gate.py", killed, original, self.TESTS, [], 120)
        assert (status, kind) == ("killed", "test_failure")
        survivor = original.replace('"rm" in command', '"rm" in command or False')
        status, _, _ = engine.run_mutant(sandbox, "hooks/gate.py", survivor, original, self.TESTS, [], 120)
        assert status == "survived"
        assert sandbox.read("hooks/gate.py") == original
        assert (mini_repo / "hooks" / "gate.py").read_text(encoding="utf-8") == before

    def test_timeout_counts_as_killed(self, sandbox):
        original = sandbox.read("hooks/gate.py")
        hang = original.replace("def decide(command):\n", "def decide(command):\n    while True:\n        pass\n")
        status, kind, _ = engine.run_mutant(sandbox, "hooks/gate.py", hang, original, self.TESTS, [], 8)
        assert (status, kind) == ("killed", "timeout")

    def test_real_repo_is_not_the_cwd_of_a_sandbox_run(self, sandbox):
        assert sandbox.repo != sandbox.repo_src
        env = engine.sandbox_env(sandbox.home)
        assert env["HOME"] == str(sandbox.home)
        assert not [k for k in env if k.startswith("CLAUDE")]


# ---------------------------------------------------------------------------------------------- scope


class TestScope:
    def test_scope_lists_only_registered_hooks_with_tests(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        (tmp_path / "hooks" / "tests").mkdir(parents=True)
        (tmp_path / "scripts" / "tests").mkdir(parents=True)
        settings = {
            "hooks": {
                "PreToolUse": [
                    {"hooks": [{"command": 'python3 "$HOME/.claude/hooks/a-gate.py"'}]},
                    {"hooks": [{"command": 'python3 "$HOME/.claude/hooks/b-notest.py"'}]},
                ],
                "Stop": [{"hooks": [{"command": 'python3 "$HOME/.claude/hooks/c-stop.py"'}]}],
            }
        }
        (tmp_path / ".claude" / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        (tmp_path / "hooks" / "a-gate.py").write_text("from hook_utils import deny_tool_use\n", encoding="utf-8")
        (tmp_path / "hooks" / "b-notest.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "hooks" / "c-stop.py").write_text("print('deny_tool_use')\n", encoding="utf-8")
        (tmp_path / "hooks" / "unregistered.py").write_text("x = 1\n", encoding="utf-8")
        for name in ("test_a_gate.py", "test_c_stop.py", "test_unregistered.py"):
            (tmp_path / "hooks" / "tests" / name).write_text("", encoding="utf-8")
        (tmp_path / "scripts" / "validate-x.py").write_text("", encoding="utf-8")
        (tmp_path / "scripts" / "validate-y.py").write_text("", encoding="utf-8")
        (tmp_path / "scripts" / "tests" / "test_validate_x.py").write_text("", encoding="utf-8")
        targets, excluded = scope.discover(tmp_path)
        assert [(t.name, t.deny) for t in targets] == [
            ("a-gate.py", True),
            ("c-stop.py", False),
            ("validate-x.py", False),
        ]
        assert {e["name"] for e in excluded} == {"b-notest.py", "validate-y.py"}
        counts = scope.scope_json(targets, excluded)["counts"]
        assert counts == {"targets": 3, "hooks": 2, "validators": 1, "deny_hooks": 1, "excluded": 2}

    def test_real_scope_resolves_every_listed_test(self):
        repo = SCRIPTS.parent
        targets, _ = scope.discover(repo)
        assert len(targets) > 40
        for target in targets:
            assert (repo / target.source).exists()
            assert all((repo / t).exists() for t in target.tests)
