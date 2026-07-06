#!/usr/bin/env python3
"""Fast static coverage test for hook registration health (ADR hook-health-gate).

Mirrors scripts/validate-hook-health.py so dormancy/schema/mirror/allowlist
regressions surface in the `test` job too, not only the dedicated `hook-health`
CI job. No subprocess, no ~/.claude dependency — reads repo files directly.

Run with: python3 -m pytest hooks/tests/test_hook_registration_coverage.py -v
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate-hook-health.py"

# Import the validator module under test (filename has a hyphen).
_spec = importlib.util.spec_from_file_location("validate_hook_health", VALIDATOR)
vhh = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vhh)

HOOKS_LIB = REPO_ROOT / "hooks" / "lib"
sys.path.insert(0, str(HOOKS_LIB))


def _settings() -> dict:
    return vhh.load_settings()


def test_no_dormant_hooks():
    """Every disk hook is registered, dispatched, or allowlisted-with-reason."""
    msgs = vhh.check_no_dormant(_settings())
    assert not msgs, "Dormant hooks found:\n" + "\n".join(msgs)


def test_every_registered_hook_has_repo_file():
    """No registered command points at a missing repo file (deadlock guard)."""
    msgs = vhh.check_registered_files_exist(_settings())
    assert not msgs, "Registered hooks without backing files:\n" + "\n".join(msgs)


def test_settings_hooks_schema():
    """Event names known, matchers are strings, commands are canonical."""
    msgs = vhh.check_schema(_settings())
    assert not msgs, "Settings schema violations:\n" + "\n".join(msgs)


def test_allowlist_has_no_stale_entries():
    """Every allowlist entry names a file that still exists on disk."""
    msgs = vhh.check_allowlist_not_stale()
    assert not msgs, "Stale allowlist entries:\n" + "\n".join(msgs)


def test_mirror_allowlists_have_no_phantom_entries():
    """Every codex mirror entry exists AND is registered (no phantoms)."""
    msgs = vhh.check_mirror(_settings())
    assert not msgs, "Phantom mirror entries:\n" + "\n".join(msgs)


def test_allowlist_entries_all_have_reasons():
    """No allowlist entry may silence the gate without a '# reason'."""
    msgs = vhh.check_allowlist_entries_have_reasons()
    assert not msgs, "Allowlist entries missing reasons:\n" + "\n".join(msgs)


def test_bare_allowlist_filename_does_not_silence_gate(tmp_path):
    """A bare filename (no reason) is NOT parsed as an allowlist entry, so it
    cannot mask a dormant hook — closes the bare-filename bypass."""
    al = tmp_path / "al.txt"
    al.write_text("foo.py            # has a legitimate reason\nbare-no-reason.py\n")
    parsed = vhh.parse_allowlist(al)
    assert "foo.py" in parsed
    assert "bare-no-reason.py" not in parsed
    assert "bare-no-reason.py" in vhh.allowlist_entries_missing_reason(al)


def test_invisible_unicode_reason_does_not_silence_gate(tmp_path):
    """A reason made of zero-width/invisible characters is NOT meaningful, so it
    cannot mask a dormant hook — closes the hidden-Unicode bypass."""
    al = tmp_path / "al.txt"
    # ghost.py followed by '#' + a zero-width space (U+200B) only.
    al.write_text("ghost.py            # ​‌\nreal.py  # legitimate deferred reason here\n", encoding="utf-8")
    parsed = vhh.parse_allowlist(al)
    assert "real.py" in parsed
    assert "ghost.py" not in parsed
    assert "ghost.py" in vhh.allowlist_entries_missing_reason(al)


def test_placeholder_reason_does_not_silence_gate(tmp_path):
    """Single-token / non-word placeholders ('___', '123', 'aaa') are NOT
    meaningful reasons and cannot mask a dormant hook."""
    al = tmp_path / "al.txt"
    al.write_text("p1.py  # ___\np2.py  # 123\np3.py  # aaa\nok.py  # legitimate deferred reason\n")
    parsed = vhh.parse_allowlist(al)
    assert set(parsed) == {"ok.py"}
    missing = set(vhh.allowlist_entries_missing_reason(al))
    assert {"p1.py", "p2.py", "p3.py"} <= missing


def test_meaningful_reason_floor():
    """Syntactic substance floor: real reasons pass; trivial/gibberish fail.

    The floor (>=2 distinct words AND >=12 letters) is intentionally syntactic —
    semantic truthfulness is a code-review concern. It rejects placeholders and
    short multi-token gibberish ('aa bb', 'aaa bbb') while accepting genuine
    justifications.
    """
    for good in (
        "deferred opt-in pending",
        "retired stub superseded",
        "superseded by voice-writer skill",
    ):
        assert vhh._meaningful_reason(good), good
    for bad in ("", "___", "123", "aaa", "x", "aa bb", "aaa bbb", "aa bb cc"):
        assert not vhh._meaningful_reason(bad), bad


def test_dispatched_detection_is_precise():
    """Dispatched-detection must not be fooled by prose mentions of a basename.

    Guards against the regression where comment/docstring references to a hook
    filename mask a genuinely dormant hook (a dispatched false-positive is a
    dormancy escape hatch). Only true subprocess CLI helpers should appear.
    """
    dispatched = vhh.dispatched_basenames()
    # voice-pipeline-tracker.py is dispatched by pretool-voice-publish-gate.py.
    assert "voice-pipeline-tracker.py" in dispatched
    # These are only ever mentioned in comments/docstrings of other hooks; they
    # must NOT be classified as dispatched.
    for prose_only in ("pretool-config-protection.py", "retro-knowledge-injector.py"):
        assert prose_only not in dispatched, (
            f"{prose_only} is mentioned in prose, not dispatched — detection is too loose and would mask dormancy."
        )


def _ast_dispatched(code: str, names: set[str]) -> set[str]:
    """Exercise the production dispatch logic over an in-memory hook source."""
    return vhh.dispatched_targets_in_source(code, names)


# Built at runtime so the literal "shell=<true>" never appears in this test
# file's source (it would otherwise trip the repo's static shell-injection
# scanner, even though these strings are only AST-parsed test fixtures, never
# executed as subprocess calls).
_SHELL = "shell=" + "True"


def test_dead_string_literal_is_not_dispatched():
    """A *.py string literal that never reaches a subprocess call must NOT be
    treated as dispatched — closes the dead-literal silent-dormancy bypass."""
    code = 'import subprocess\nUNUSED = "new-hook.py"\nsubprocess.run(["ls"])\n'
    assert _ast_dispatched(code, {"new-hook.py"}) == set()


def test_py_string_in_non_command_arg_is_not_dispatched():
    """A *.py string buried in env=/input= (data, not the command) must NOT be
    treated as dispatched — only the command argument counts."""
    env_case = 'import subprocess\nsubprocess.run(["ls"], env={"HOOK": "new-hook.py"})\n'
    input_case = 'import subprocess\nsubprocess.run(["ls"], input="x new-hook.py")\n'
    assert _ast_dispatched(env_case, {"new-hook.py"}) == set()
    assert _ast_dispatched(input_case, {"new-hook.py"}) == set()


def test_trailing_argv_py_is_not_dispatched():
    """Only the EXECUTED script (first .py in argv, or first shell-parsed token)
    is dispatched; a later argv slot holding another hook basename is data, not
    a dispatch target — closes the 'extra argv slot' silent-dormancy bypass."""
    argv_list = 'import subprocess\nsubprocess.run(["python3", "hooks/real.py", "hooks/dormant.py"])\n'
    # Multi-token strings only shell-parse in shell mode.
    bare_str = f'import subprocess\nsubprocess.run("python3 hooks/real.py hooks/dormant.py", {_SHELL})\n'
    assert _ast_dispatched(argv_list, {"real.py", "dormant.py"}) == {"real.py"}
    assert _ast_dispatched(bare_str, {"real.py", "dormant.py"}) == {"real.py"}


def test_shell_payload_py_is_not_dispatched():
    """A .py inside a shell payload (bash -c '...echo hooks/x.py') or as a
    non-program argument ('echo hooks/x.py') is NOT the executed script —
    closes the shell-payload silent-dormancy bypass."""
    bash_lc = 'import subprocess\nsubprocess.run(["bash", "-lc", "echo hooks/dormant.py"])\n'
    echo_arg = f'import subprocess\nsubprocess.run("echo hooks/dormant.py", {_SHELL})\n'
    assert _ast_dispatched(bash_lc, {"dormant.py"}) == set()
    assert _ast_dispatched(echo_arg, {"dormant.py"}) == set()
    # ...but a script at the program position or after the interpreter IS (shell):
    prog_first = f'import subprocess\nsubprocess.run("hooks/real.py --flag", {_SHELL})\n'
    interp = f'import subprocess\nsubprocess.run("python3 hooks/real.py hooks/dormant.py", {_SHELL})\n'
    assert _ast_dispatched(prog_first, {"real.py", "dormant.py"}) == {"real.py"}
    assert _ast_dispatched(interp, {"real.py", "dormant.py"}) == {"real.py"}


def test_variable_shell_payload_is_not_dispatched():
    """A hook basename inside a variable-held shell payload, a variable non-
    program arg to a non-python program, or an f-string payload is NOT the
    executed script — closes the variable/f-string silent-dormancy bypasses."""
    var_payload = 'import subprocess\npayload = "echo hooks/dormant.py"\nsubprocess.run(["bash", "-lc", payload])\n'
    var_arg_to_echo = 'import subprocess\narg = "hooks/dormant.py"\nsubprocess.run(["echo", arg])\n'
    fstring = 'import subprocess\nname = "dormant"\nsubprocess.run(["bash", "-lc", f"echo hooks/{name}"])\n'
    assert _ast_dispatched(var_payload, {"dormant.py"}) == set()
    assert _ast_dispatched(var_arg_to_echo, {"dormant.py"}) == set()
    assert _ast_dispatched(fstring, {"dormant.py"}) == set()


def test_basename_alias_and_path_composition_not_dispatched():
    """A same-named script in an unrelated absolute dir (/tmp/x.py), or a
    composed path whose FINAL component is not the hook (.../x.py + '.bak',
    Path('hooks/x.py') / 'extra'), must NOT alias onto a hook — closes the
    basename-alias and path-composition false positives."""
    tmp_alias = 'import subprocess\nsubprocess.run(["/tmp/x.py"])\n'
    concat = 'import subprocess\nsubprocess.run(["hooks/x.py" + ".bak"])\n'
    joined = 'import subprocess\nfrom pathlib import Path\nsubprocess.run([Path("hooks/x.py") / "extra"])\n'
    assert _ast_dispatched(tmp_alias, {"x.py"}) == set()
    assert _ast_dispatched(concat, {"x.py"}) == set()
    assert _ast_dispatched(joined, {"x.py"}) == set()


def test_attribute_and_external_hooks_path_not_dispatched():
    """A standalone attribute ('.parent', '.upper'), an absolute path into an
    unrelated dir that merely contains 'hooks', and a locally-defined Popen
    must NOT be treated as dispatch — closes the round-12 false positives."""
    parent_attr = 'import subprocess\nfrom pathlib import Path\nsubprocess.run(Path("hooks/x.py").parent)\n'
    upper_attr = 'import subprocess\ntarget = "hooks/x.py"\nsubprocess.run(target.upper)\n'
    ext_hooks = 'import subprocess\nsubprocess.run("/tmp/other/hooks/x.py")\n'
    local_popen = 'def Popen(*a, **k):\n    pass\nPopen(["hooks/x.py"])\n'
    assert _ast_dispatched(parent_attr, {"x.py"}) == set()
    assert _ast_dispatched(upper_attr, {"x.py"}) == set()
    assert _ast_dispatched(ext_hooks, {"x.py"}) == set()
    assert _ast_dispatched(local_popen, {"x.py"}) == set()


def test_real_popen_import_and_claude_hooks_path_detected():
    """A real `from subprocess import Popen` call and an absolute
    .claude/hooks/<file> script ARE detected."""
    real_popen = 'from subprocess import Popen\nPopen(["hooks/x.py"])\n'
    abs_hooks = 'import subprocess\nsubprocess.run(["/home/u/.claude/hooks/x.py"])\n'
    assert _ast_dispatched(real_popen, {"x.py"}) == {"x.py"}
    assert _ast_dispatched(abs_hooks, {"x.py"}) == {"x.py"}


def test_interpreter_flags_and_executable_override_not_dispatched():
    """A .py after a python -c/-m flag (data, not the script) or argv combined
    with executable= (overrides the program) must NOT be dispatched — closes the
    round-13 false positives."""
    dash_c = 'import subprocess\nsubprocess.run(["python3", "-c", "print(1)", "hooks/x.py"])\n'
    dash_m = 'import subprocess\nsubprocess.run(["python3", "-m", "mod", "hooks/x.py"])\n'
    exe_override = 'import subprocess\nsubprocess.run(["python3", "hooks/x.py"], executable="/bin/echo")\n'
    bare_dash_c = 'import subprocess\nsubprocess.run("python3 -c print hooks/x.py")\n'
    assert _ast_dispatched(dash_c, {"x.py"}) == set()
    assert _ast_dispatched(dash_m, {"x.py"}) == set()
    assert _ast_dispatched(exe_override, {"x.py"}) == set()
    assert _ast_dispatched(bare_dash_c, {"x.py"}) == set()


def test_shell_run_of_hook_script_is_detected():
    """Running a hook directly through a shell (os.system, shell command with
    the script at the program position) IS a real dispatch and is detected."""
    os_system = 'import os\nos.system("hooks/x.py")\n'
    shell_python = f'import subprocess\nsubprocess.run("python3 hooks/x.py", {_SHELL})\n'
    assert _ast_dispatched(os_system, {"x.py"}) == {"x.py"}
    assert _ast_dispatched(shell_python, {"x.py"}) == {"x.py"}


def test_multitoken_string_without_shell_is_not_dispatched():
    """A multi-token string command with the default shell=False does NOT run
    the script (the whole string is one program name -> FileNotFound), so it is
    not a dispatch. A single-token string command, or shell mode, still counts."""
    no_shell = 'import subprocess\nsubprocess.run("python3 hooks/dormant.py")\n'
    single = 'import subprocess\nsubprocess.run("hooks/x.py")\n'
    with_shell = f'import subprocess\nsubprocess.run("python3 hooks/x.py", {_SHELL})\n'
    os_shell = 'import os\nos.system("python3 hooks/x.py")\n'
    assert _ast_dispatched(no_shell, {"dormant.py"}) == set()
    assert _ast_dispatched(single, {"x.py"}) == {"x.py"}
    assert _ast_dispatched(with_shell, {"x.py"}) == {"x.py"}
    assert _ast_dispatched(os_shell, {"x.py"}) == {"x.py"}


def test_scripts_dir_dispatch_does_not_alias_hook():
    """A subprocess call to `repo_root / "scripts" / "<name>.py"` (a real,
    common pattern in this repo) must NOT be counted as dispatching a same-named
    hooks/<name>.py — the script lives in scripts/, not hooks/."""
    scripts_call = (
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        "repo_root = Path(__file__).resolve().parent.parent\n"
        'script = repo_root / "scripts" / "x.py"\n'
        "subprocess.run([sys.executable, str(script)])\n"
    )
    rel_scripts = 'import subprocess\nsubprocess.run(["python3", "scripts/x.py"])\n'
    # evals/, or any non-hooks dir, must also not alias (allowlist model).
    evals_call = (
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        'script = Path(__file__).parent.parent / "evals" / "harness.py"\n'
        "subprocess.run([sys.executable, str(script)])\n"
    )
    opaque_dir = 'import subprocess, sys\nd = some_unknown_dir()\nsubprocess.run([sys.executable, str(d / "x.py")])\n'
    assert _ast_dispatched(scripts_call, {"x.py"}) == set()
    assert _ast_dispatched(rel_scripts, {"x.py"}) == set()
    assert _ast_dispatched(evals_call, {"harness.py"}) == set()
    assert _ast_dispatched(opaque_dir, {"x.py"}) == set()


def test_real_subprocess_dispatch_is_detected():
    """A basename at an executable position (slot 0, or after a python
    interpreter / sys.executable), directly, via a bound variable, or via a
    Path(__file__).parent / 'x.py' construction, IS detected."""
    via_var = (
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        'T = str(Path(__file__).parent / "tracker.py")\n'
        "subprocess.run([sys.executable, T])\n"
    )
    inline = 'import subprocess\nsubprocess.run(["python3", "hooks/x.py"])\n'
    slot0 = 'import subprocess\nsubprocess.run(["hooks/x.py", "--flag"])\n'
    path_join = (
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        'subprocess.run([sys.executable, str(Path(__file__).parent / "x.py")])\n'
    )
    assert _ast_dispatched(via_var, {"tracker.py"}) == {"tracker.py"}
    assert _ast_dispatched(inline, {"x.py"}) == {"x.py"}
    assert _ast_dispatched(slot0, {"x.py"}) == {"x.py"}
    assert _ast_dispatched(path_join, {"x.py"}) == {"x.py"}


def test_hook_lib_exports_every_imported_helper():
    """Every hooks/lib named import in hooks/*.py must exist in that module."""
    lib_modules = {path.stem for path in HOOKS_LIB.glob("*.py") if path.name != "__init__.py"}
    imported: dict[str, dict[str, set[str]]] = {}
    for hook_path in sorted((REPO_ROOT / "hooks").glob("*.py")):
        tree = ast.parse(hook_path.read_text(encoding="utf-8"), filename=str(hook_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module in lib_modules:
                imported.setdefault(hook_path.name, {}).setdefault(node.module, set()).update(
                    alias.name for alias in node.names
                )

    missing = []
    loaded_modules = {}
    for hook_name, modules in imported.items():
        for module_name, names in modules.items():
            if module_name not in loaded_modules:
                module_path = HOOKS_LIB / f"{module_name}.py"
                spec = importlib.util.spec_from_file_location(f"repo_hook_lib_{module_name}", module_path)
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                loaded_modules[module_name] = module
            module = loaded_modules[module_name]
            for name in sorted(names):
                if not hasattr(module, name):
                    missing.append(f"{hook_name}: {module_name}.{name}")

    assert not missing, "hooks/lib missing imported helper(s):\n" + "\n".join(missing)
