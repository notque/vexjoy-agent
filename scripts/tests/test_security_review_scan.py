#!/usr/bin/env python3
"""
Tests for scripts/security-review-scan.py — deterministic security scanner.

Run with: python3 -m pytest scripts/tests/test_security_review_scan.py -v

Covers (ADR acceptance criteria 8 + 10):
- One positive match AND one documented-exclusion negative per NEW rule ported
  from Anthropic's patterns.py (parity).
- Existing rules (secrets, SQLi, shell, IP) still fire.
- Per-language file gating (JS rules skip .py; Python rules skip .js).
- Documentation files (.md/.json) suppress code-pattern rules.
- Custom-rule loading: valid rule fires; ReDoS/invalid skipped non-fatally.
- Exit-code contract: HIGH/CRITICAL -> 1, MEDIUM-only/clean -> 0.
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCAN_PATH = Path(__file__).resolve().parents[2] / "scripts" / "security-review-scan.py"

spec = importlib.util.spec_from_file_location("security_review_scan", SCAN_PATH)
scan = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scan)

RULES = scan._build_rules()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _findings(content: str, filename: str) -> list[dict]:
    """Scan an in-memory snippet written to a temp file with the given name."""
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        fp = Path(d) / filename
        fp.parent.mkdir(parents=True, exist_ok=True)
        fp.write_text(content, encoding="utf-8")
        return scan._scan_file(str(fp), RULES)


def _rules_hit(content: str, filename: str) -> set[str]:
    return {f["rule"] for f in _findings(content, filename)}


def _run_cli(files: list[str], cwd: str | None = None) -> tuple[int, dict]:
    """Invoke the scanner as a subprocess; return (exit_code, parsed_json)."""
    result = subprocess.run(
        [sys.executable, str(SCAN_PATH), "--format", "json", "--files", *files],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    return result.returncode, json.loads(result.stdout)


# ---------------------------------------------------------------------------
# Existing rules still fire (regression — ADR criterion 11)
# ---------------------------------------------------------------------------


class TestExistingRules:
    def test_hardcoded_password(self):
        assert "hardcoded-secret" in _rules_hit('password = "hunter2"', "a.py")

    def test_aws_key(self):
        assert "hardcoded-secret" in _rules_hit("key = AKIAIOSFODNN7EXAMPLE", "a.py")

    def test_password_redacted(self):
        f = _findings('password = "hunter2"', "a.py")
        assert any("[REDACTED]" in x["match"] for x in f)

    def test_sql_injection_fstring(self):
        assert "sql-injection" in _rules_hit('q = f"SELECT * FROM t WHERE id = {uid}"', "a.py")

    def test_public_ip_flagged(self):
        assert "hardcoded-ip" in _rules_hit("host = 8.8.8.8", "a.py")

    def test_private_ip_not_flagged(self):
        assert "hardcoded-ip" not in _rules_hit("host = 192.168.1.1", "a.py")


# ---------------------------------------------------------------------------
# Ported rules: positive match + documented exclusion (ADR criterion 8)
# ---------------------------------------------------------------------------


class TestEvalExec:
    def test_eval_python(self):
        assert "dangerous-eval" in _rules_hit("eval(user_input)", "a.py")

    def test_method_eval_excluded(self):
        # Lookbehind skips method calls like model.eval()
        assert "dangerous-eval" not in _rules_hit("model.eval()", "a.py")

    def test_eval_in_markdown_excluded(self):
        # Documentation files are skipped for code-pattern rules
        assert "dangerous-eval" not in _rules_hit("Call eval(x) to run.", "a.md")

    def test_new_function_js(self):
        assert "dangerous-eval" in _rules_hit("const f = new Function(body)", "a.js")

    def test_new_function_not_in_python(self):
        # JS-only rule; bare "new Function" should not fire in .py
        assert "dangerous-eval" not in _rules_hit("x = new Function(body)", "a.py")


class TestShellInjection:
    def test_child_process_exec(self):
        assert "shell-injection" in _rules_hit("child_process.exec(cmd)", "a.js")

    def test_exec_sync(self):
        assert "shell-injection" in _rules_hit("execSync(`ls ${d}`)", "a.ts")

    def test_bare_exec_js(self):
        assert "shell-injection" in _rules_hit("exec(cmd, cb)", "a.js")

    def test_method_exec_excluded(self):
        # cp.exec() is a method call — lookbehind skips it
        assert "shell-injection" not in _rules_hit("cp.exec(cmd)", "a.js")

    def test_js_exec_not_flagged_in_python(self):
        assert "shell-injection" not in _rules_hit("db.exec(query)", "a.py")

    def test_os_system(self):
        assert "shell-injection" in _rules_hit("os.system(cmd)", "a.py")

    def test_subprocess_shell_true(self):
        assert "shell-injection" in _rules_hit("subprocess.run(cmd, shell=True)", "a.py")

    def test_subprocess_shell_false_not_flagged(self):
        assert "shell-injection" not in _rules_hit("subprocess.run(['ls', d])", "a.py")

    def test_go_exec_shell(self):
        assert "shell-injection" in _rules_hit('exec.Command("sh", "-c", c)', "a.go")

    def test_go_exec_direct_not_flagged(self):
        # Direct binary invocation (no shell) is safe
        assert "shell-injection" not in _rules_hit('exec.Command("ping", "-c", "1", host)', "a.go")


class TestDeserialization:
    def test_pickle_loads(self):
        assert "unsafe-deserialization" in _rules_hit("pickle.loads(b)", "a.py")

    def test_pickle_dump_not_flagged(self):
        # dump is not a deserialization sink
        assert "unsafe-deserialization" not in _rules_hit("pickle.dump(obj, f)", "a.py")

    def test_pickle_unpickler(self):
        assert "unsafe-deserialization" in _rules_hit("pickle.Unpickler(f).load()", "a.py")

    def test_cloudpickle(self):
        assert "unsafe-deserialization" in _rules_hit("cloudpickle.loads(b)", "a.py")

    def test_dill(self):
        assert "unsafe-deserialization" in _rules_hit("dill.load(f)", "a.py")

    def test_marshal(self):
        assert "unsafe-deserialization" in _rules_hit("marshal.loads(b)", "a.py")

    def test_shelve(self):
        assert "unsafe-deserialization" in _rules_hit("shelve.open(p)", "a.py")

    def test_joblib(self):
        assert "unsafe-deserialization" in _rules_hit("joblib.load(p)", "a.py")

    def test_read_pickle(self):
        assert "unsafe-deserialization" in _rules_hit("pandas.read_pickle(p)", "a.py")

    def test_numpy_allow_pickle(self):
        assert "unsafe-deserialization" in _rules_hit("np.load(p, allow_pickle=True)", "a.py")

    def test_numpy_default_not_flagged(self):
        # allow_pickle defaults to False — not a sink
        assert "unsafe-deserialization" not in _rules_hit("np.load(p)", "a.py")

    def test_torch_load_unsafe(self):
        assert "unsafe-deserialization" in _rules_hit("torch.load(p)", "a.py")

    def test_torch_load_weights_only_excluded(self):
        # weights_only=True within 200 chars suppresses (documented exclusion)
        assert "unsafe-deserialization" not in _rules_hit("torch.load(p, weights_only=True)", "a.py")

    def test_pickle_not_flagged_in_js(self):
        assert "unsafe-deserialization" not in _rules_hit("pickle.loads(b)", "a.js")


class TestYaml:
    def test_yaml_load_unsafe(self):
        assert "unsafe-yaml" in _rules_hit("yaml.load(s)", "a.py")

    def test_yaml_safe_loader_excluded(self):
        # Loader=SafeLoader suppresses (documented exclusion)
        assert "unsafe-yaml" not in _rules_hit("yaml.load(s, Loader=SafeLoader)", "a.py")

    def test_yaml_safe_load_not_flagged(self):
        assert "unsafe-yaml" not in _rules_hit("yaml.safe_load(s)", "a.py")

    def test_yaml_unsafe_load(self):
        assert "unsafe-yaml" in _rules_hit("yaml.unsafe_load(s)", "a.py")


class TestXssSinks:
    def test_dangerously_set_inner_html(self):
        assert "xss-sink" in _rules_hit("<div dangerouslySetInnerHTML={h} />", "a.jsx")

    def test_inner_html_assign(self):
        assert "xss-sink" in _rules_hit("el.innerHTML = userInput", "a.js")

    def test_outer_html_assign(self):
        assert "xss-sink" in _rules_hit("el.outerHTML = userInput", "a.ts")

    def test_insert_adjacent_html(self):
        assert "xss-sink" in _rules_hit("el.insertAdjacentHTML('beforeend', h)", "a.js")

    def test_text_content_not_flagged(self):
        # textContent is the safe alternative — no finding
        assert "xss-sink" not in _rules_hit("el.textContent = userInput", "a.js")

    def test_document_write_medium(self):
        f = _findings("document.write(x)", "a.js")
        assert any(x["rule"] == "xss-document-write" and x["severity"] == "MEDIUM" for x in f)

    def test_xss_not_flagged_in_python(self):
        assert "xss-sink" not in _rules_hit("el.innerHTML = userInput", "a.py")


class TestSri:
    def test_external_script_no_sri(self):
        c = '<script src="https://cdn.example.com/lib.js"></script>'
        assert "missing-sri" in _rules_hit(c, "page.html")

    def test_script_with_integrity_excluded(self):
        c = '<script src="https://cdn.example.com/lib.js" integrity="sha384-abc"></script>'
        assert "missing-sri" not in _rules_hit(c, "page.html")


class TestCrypto:
    def test_node_create_cipher(self):
        assert "weak-crypto" in _rules_hit("crypto.createCipher('aes', k)", "a.js")

    def test_create_cipheriv_not_flagged(self):
        # createCipheriv is the safe form
        assert "weak-crypto" not in _rules_hit("crypto.createCipheriv('aes-256-gcm', k, iv)", "a.js")

    def test_aes_ecb_python(self):
        assert "weak-crypto" in _rules_hit("c = AES.new(k, AES.MODE_ECB)", "a.py")

    def test_aes_ecb_string(self):
        assert "weak-crypto" in _rules_hit('algo = "aes-256-ecb"', "a.js")

    def test_aes_gcm_not_flagged(self):
        assert "weak-crypto" not in _rules_hit("c = AES.new(k, AES.MODE_GCM)", "a.py")


class TestTlsDisabled:
    def test_verify_false(self):
        assert "tls-disabled" in _rules_hit("requests.get(u, verify=False)", "a.py")

    def test_reject_unauthorized_false(self):
        assert "tls-disabled" in _rules_hit("{ rejectUnauthorized: false }", "a.js")

    def test_insecure_skip_verify(self):
        assert "tls-disabled" in _rules_hit("tls.Config{InsecureSkipVerify: true}", "a.go")

    def test_node_tls_reject_env(self):
        assert "tls-disabled" in _rules_hit("NODE_TLS_REJECT_UNAUTHORIZED=0", "a.js")

    def test_unverified_context(self):
        assert "tls-disabled" in _rules_hit("ctx = ssl._create_unverified_context()", "a.py")

    def test_check_hostname_false(self):
        assert "tls-disabled" in _rules_hit("ctx.check_hostname = False", "a.py")

    def test_verify_true_not_flagged(self):
        assert "tls-disabled" not in _rules_hit("requests.get(u, verify=True)", "a.py")


class TestXxe:
    def test_element_tree_parse(self):
        assert "xxe-unsafe-xml" in _rules_hit("ET.parse(path)", "a.py")

    def test_element_tree_fromstring(self):
        assert "xxe-unsafe-xml" in _rules_hit("ElementTree.fromstring(data)", "a.py")

    def test_minidom_parse(self):
        assert "xxe-unsafe-xml" in _rules_hit("minidom.parseString(data)", "a.py")

    def test_xml_sax(self):
        assert "xxe-unsafe-xml" in _rules_hit("xml.sax.make_parser()", "a.py")

    def test_json_loads_not_flagged(self):
        assert "xxe-unsafe-xml" not in _rules_hit("json.loads(data)", "a.py")


class TestGithubActions:
    def test_event_title_injection(self):
        c = 'run: echo "${{ github.event.issue.title }}"'
        assert "github-actions-injection" in _rules_hit(c, ".github/workflows/ci.yml")

    def test_not_in_non_workflow_yaml(self):
        # Same string in a non-workflow yaml file should not fire
        c = 'value: "${{ github.event.issue.title }}"'
        assert "github-actions-injection" not in _rules_hit(c, "config.yaml")

    def test_env_indirection_path_still_workflow(self):
        # github.event.inputs is not in the injectable set
        c = "run: echo ${{ github.event.inputs.name }}"
        assert "github-actions-injection" not in _rules_hit(c, ".github/workflows/ci.yml")


# ---------------------------------------------------------------------------
# Exit-code contract (ADR criterion 11)
# ---------------------------------------------------------------------------


class TestExitCodes:
    def test_high_finding_exit_1(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("os.system(cmd)\n")
        code, report = _run_cli([str(f)])
        assert code == 1
        assert report["summary"]["high"] >= 1

    def test_medium_only_exit_0(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("# TODO security: fix later\n")
        code, report = _run_cli([str(f)])
        assert code == 0
        assert report["summary"]["medium"] >= 1
        assert report["summary"]["high"] == 0
        assert report["summary"]["critical"] == 0

    def test_clean_exit_0(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x = 1 + 1\n")
        code, report = _run_cli([str(f)])
        assert code == 0
        assert report["summary"]["total"] == 0


# ---------------------------------------------------------------------------
# Custom-rule loading (ADR criterion 10)
# ---------------------------------------------------------------------------


def _write_patterns(cwd: Path, name: str, data: dict) -> None:
    claude = cwd / ".claude"
    claude.mkdir(parents=True, exist_ok=True)
    (claude / name).write_text(json.dumps(data), encoding="utf-8")


class TestCustomRules:
    def test_valid_custom_rule_loads_and_fires(self, tmp_path):
        _write_patterns(
            tmp_path,
            "security-patterns.json",
            {"patterns": [{"rule_name": "no-foo", "severity": "HIGH", "regex": r"foo_secret"}]},
        )
        target = tmp_path / "app.py"
        target.write_text("x = foo_secret\n")
        code, report = _run_cli([str(target)], cwd=str(tmp_path))
        names = {f["rule"] for f in report["findings"]}
        assert "custom:no-foo" in names
        assert code == 1  # HIGH severity → exit 1

    def test_substring_custom_rule(self, tmp_path):
        _write_patterns(
            tmp_path,
            "security-patterns.json",
            {"patterns": [{"rule_name": "ban-token", "substrings": ["MAGIC_TOKEN"]}]},
        )
        target = tmp_path / "app.py"
        target.write_text("k = MAGIC_TOKEN\n")
        _, report = _run_cli([str(target)], cwd=str(tmp_path))
        assert "custom:ban-token" in {f["rule"] for f in report["findings"]}

    def test_redos_rule_skipped_nonfatally(self, tmp_path):
        _write_patterns(
            tmp_path,
            "security-patterns.json",
            {"patterns": [{"rule_name": "evil", "regex": r"(a+)+$", "severity": "HIGH"}]},
        )
        target = tmp_path / "app.py"
        target.write_text("aaaaaaaaaa\n")
        result = subprocess.run(
            [sys.executable, str(SCAN_PATH), "--format", "json", "--files", str(target)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        report = json.loads(result.stdout)
        assert "custom:evil" not in {f["rule"] for f in report["findings"]}
        assert "ReDoS-prone" in result.stderr  # warned, not crashed
        assert result.returncode == 0

    def test_invalid_regex_skipped_nonfatally(self, tmp_path):
        _write_patterns(
            tmp_path,
            "security-patterns.json",
            {"patterns": [{"rule_name": "bad", "regex": r"(unclosed", "severity": "HIGH"}]},
        )
        target = tmp_path / "app.py"
        target.write_text("hello\n")
        result = subprocess.run(
            [sys.executable, str(SCAN_PATH), "--format", "json", "--files", str(target)],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert result.returncode == 0  # non-fatal
        assert "invalid regex" in result.stderr

    def test_rule_without_name_skipped(self, tmp_path):
        _write_patterns(
            tmp_path,
            "security-patterns.json",
            {"patterns": [{"regex": r"foo", "severity": "HIGH"}]},
        )
        target = tmp_path / "app.py"
        target.write_text("foo\n")
        code, report = _run_cli([str(target)], cwd=str(tmp_path))
        # No valid custom rule → only built-ins run, nothing matches
        assert all(not f["rule"].startswith("custom:") for f in report["findings"])

    def test_custom_rule_path_glob_restriction(self, tmp_path):
        _write_patterns(
            tmp_path,
            "security-patterns.json",
            {"patterns": [{"rule_name": "py-only", "regex": "BANNED", "paths": ["*.py"]}]},
        )
        py = tmp_path / "a.py"
        py.write_text("BANNED\n")
        js = tmp_path / "a.js"
        js.write_text("BANNED\n")
        _, report = _run_cli([str(py), str(js)], cwd=str(tmp_path))
        hits = [f for f in report["findings"] if f["rule"] == "custom:py-only"]
        assert len(hits) == 1
        assert hits[0]["file"].endswith("a.py")


class TestRedosHeuristic:
    def test_nested_quantifier(self):
        assert scan._has_redos_structure("(a+)*")
        assert scan._has_redos_structure("(a*b)+")

    def test_wildcard_group(self):
        assert scan._has_redos_structure("(.*)*")

    def test_overlapping_alternation(self):
        assert scan._has_redos_structure("(a|aa)*")

    def test_safe_alternation(self):
        assert not scan._has_redos_structure("(a|b)*")

    def test_plain_regex_safe(self):
        assert not scan._has_redos_structure(r"\bos\.system\s*\(")


# ---------------------------------------------------------------------------
# Parity count guard (ADR criterion 8 — all 25 Anthropic patterns covered)
# ---------------------------------------------------------------------------


class TestParityCoverage:
    @pytest.mark.parametrize(
        "snippet,filename,expected_rule",
        [
            ('run: echo "${{ github.event.issue.title }}"', ".github/workflows/x.yml", "github-actions-injection"),
            ("child_process.exec(c)", "a.js", "shell-injection"),
            ("new Function(b)", "a.js", "dangerous-eval"),
            ("eval(x)", "a.py", "dangerous-eval"),
            ("<div dangerouslySetInnerHTML={h}/>", "a.jsx", "xss-sink"),
            ("document.write(x)", "a.js", "xss-document-write"),
            ("el.innerHTML = u", "a.js", "xss-sink"),
            ("el.outerHTML = u", "a.js", "xss-sink"),
            ("el.insertAdjacentHTML('x', h)", "a.js", "xss-sink"),
            ('<script src="//cdn/x.js"></script>', "a.html", "missing-sri"),
            ("pickle.loads(b)", "a.py", "unsafe-deserialization"),
            ("os.system(c)", "a.py", "shell-injection"),
            ("subprocess.run(c, shell=True)", "a.py", "shell-injection"),
            ('exec.Command("sh", "-c", c)', "a.go", "shell-injection"),
            ("yaml.load(s)", "a.py", "unsafe-yaml"),
            ("crypto.createCipher('aes', k)", "a.js", "weak-crypto"),
            ("AES.MODE_ECB", "a.py", "weak-crypto"),
            ("requests.get(u, verify=False)", "a.py", "tls-disabled"),
            ("marshal.loads(b)", "a.py", "unsafe-deserialization"),
            ("shelve.open(p)", "a.py", "unsafe-deserialization"),
            ("ET.parse(p)", "a.py", "xxe-unsafe-xml"),
            ("dill.load(f)", "a.py", "unsafe-deserialization"),
            ("torch.load(p)", "a.py", "unsafe-deserialization"),
            ("yaml.unsafe_load(s)", "a.py", "unsafe-yaml"),
            ("joblib.load(p)", "a.py", "unsafe-deserialization"),
        ],
    )
    def test_each_anthropic_pattern_detected(self, snippet, filename, expected_rule):
        assert expected_rule in _rules_hit(snippet, filename)
