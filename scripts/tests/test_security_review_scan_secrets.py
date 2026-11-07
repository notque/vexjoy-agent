"""Secret, staged-index and robustness tests for scripts/security-review-scan.py.

Covers the audit findings fixed together:
- D-01: a finding never prints secret material, only <redacted:TYPE:last4>.
- D-02: long lines scan in bounded time; a malformed rules file, a crash or a
  spent time budget is reported (exit 2 and a reason) instead of a silent pass.
- D-03: --staged scans the index blobs, from any subdirectory, renames included.
- D-15 / I-03: common secret formats fire in every scanned file whatever its
  extension, while nosec and security-review-ignore keep working.

Secret-shaped fixtures are assembled from parts at runtime, so this file holds none.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

SCAN_PATH = Path(__file__).resolve().parents[2] / "scripts" / "security-review-scan.py"

_spec = importlib.util.spec_from_file_location("security_review_scan_secrets", SCAN_PATH)
scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(scan)

# --- fixtures built from parts ------------------------------------------------

AWS_ID = "AK" + "IA" + "QX7T" * 4
STS_ID = "AS" + "IA" + "M2PZ" * 4
GH_PAT = "gh" + "p_" + "Ab9Cd8Ef7Gh6" * 3
SLACK_BOT = "xo" + "xb-" + "2048613577" + "-" + "Kx7Lm2Nq9Rs4Tv8W"
GOOGLE_KEY = "AI" + "za" + "SyD4" * 8 + "K7m"
PEM_BEGIN = "-----BEGIN " + "RSA PRIVATE" + " KEY-----"
PEM_END = "-----END " + "RSA PRIVATE" + " KEY-----"
SSH_BEGIN = "-----BEGIN " + "OPENSSH PRIVATE" + " KEY-----"
KEY_BODY = "MIIEow" + "IBAAKCAQEA" + "q9Rt8Uv7Wx6Yz5" * 6
SECRET_40 = "Fk29" + "dLq8" * 9
SECRET_24 = "FAKE" + "k3x9" * 5
SECRET_22 = "FAKE" + "qwertyuiopasdfghjk"
SHORT_PW = "hun" + "ter2"
ENV_KEY = "FAKE" + "abc-defghijk"
SH_KEY = "sk" + "-" + "QWERTYUIOPAS"
HIGH_LINE = "os." + "system(cmd)"
EVAL_LINE = "ev" + "al(x)"


def _q(value: str) -> str:
    return '"' + value + '"'


# The 17 formats lane D's probe found missing (D-15), plus the one it caught.
FORMATS = [
    ("gh.py", "GITHUB_TOKEN = " + _q(GH_PAT), "github-token"),
    ("tok.py", "token = " + _q(SECRET_24), "token"),
    ("awssec.py", "aws_secret_access_key = " + _q(SECRET_40), "access-key"),
    ("awssec2.py", "AWS_SECRET_ACCESS_KEY = " + _q(SECRET_40), "access-key"),
    ("sts.py", "key_id = " + _q(STS_ID), "aws-access-key-id"),
    ("privkey.py", "private_key = " + _q(SECRET_22), "private-key"),
    ("go_short.go", "password := " + _q(SHORT_PW), "password"),
    ("js_obj.js", "const cfg = { apiKey: " + _q(GOOGLE_KEY) + " };", "google-api-key"),
    ("js_quoted.js", "const cfg = { " + _q("password") + ": " + _q(SHORT_PW) + " };", "password"),
    ("yaml_pw.yaml", "password: " + SHORT_PW, "password"),
    ("slack.py", "SLACK_BOT = " + _q(SLACK_BOT), "slack-token"),
    ("dotenv.env", "API_" + "KEY=" + ENV_KEY, "api-key"),
    ("shell.sh", "export API_" + "KEY=" + _q(SH_KEY), "api-key"),
    ("terraform.tf", "access_key = " + _q(AWS_ID), "aws-access-key-id"),
    ("server.pem", PEM_BEGIN, "private-key"),
    ("id_rsa", SSH_BEGIN, "private-key"),
    ("settings.toml", "pass" + "word = " + _q(SHORT_PW), "password"),
    ("anthropic.py", "client = Anthropic(api_" + "key=" + _q("sk-" + "ant-" + "QWERTYUIOPAS") + ")", "api-key"),
]

# Things that look like credentials to a keyword rule but are not.
NOT_SECRETS = [
    ("openai_kw.py", "OpenAI(api_" + "key = os.environ[" + _q("X") + "])"),
    (".env.example", "API_" + "KEY=\nTOKEN=your-token-here\nPASSWORD=${DB_PASS" + "WORD}\nSECRET_KEY=changeme"),
    ("ci.yml", "password: ${{ secrets.DB_PASS" + "WORD }}\ntoken: " + _q("{{ vault_token }}") + "\nsecret: true"),
    ("labels.js", "const msgs = { password: " + _q("Required") + ", token: " + _q("Your access token") + " };"),
    ("tokenizer.py", "eos_" + "token = " + _q("</s>") + "\npad_" + "token = " + _q("[PAD]")),
    ("empty.go", "token := " + _q("")),
    ("kind.py", "token_type = " + _q("bearer")),
    ("names.py", "api_key_env = " + _q("OPENAI_API_KEY") + "\nsecret_name = " + _q("prod/db/main")),
]


def _env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update({"HOME": str(home), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    return env


def _cli(args: list[str], cwd: Path, home: Path, fmt: str = "json", timeout: float = 120):
    return subprocess.run(
        [sys.executable, str(SCAN_PATH), "--format", fmt, *args],
        cwd=str(cwd),
        env=_env(home),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, env=_env(repo.parent), capture_output=True, text=True, check=True)


def _repo(root: Path, name: str = "repo") -> Path:
    repo = root / name
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    return repo


def _commit(repo: Path) -> None:
    _git(repo, "-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "--quiet", "-m", "base")


def _write(root: Path, rel: str, body: str | bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(body, bytes):
        path.write_bytes(body)
    else:
        path.write_text(body + "\n", encoding="utf-8")
    return path


def _secret_hits(report: dict) -> dict[str, list[dict]]:
    hits: dict[str, list[dict]] = {}
    for f in report["findings"]:
        if f["rule"] == "hardcoded-secret":
            hits.setdefault(f["file"], []).append(f)
    return hits


# --- D-01: findings never echo secret material --------------------------------


class TestRedaction:
    def test_one_line_private_key_reports_only_a_placeholder(self, tmp_path):
        blob = PEM_BEGIN + "\\n" + KEY_BODY + "\\n" + PEM_END + "\\n"
        _write(tmp_path, "sa.json", json.dumps({"type": "service_account", "private_key": blob}))
        for fmt in ("json", "text"):
            proc = _cli(["--files", "sa.json"], tmp_path, tmp_path, fmt=fmt)
            assert proc.returncode == 1, proc.stderr
            assert KEY_BODY not in proc.stdout
            assert KEY_BODY[:12] not in proc.stdout
            assert "<redacted:private-key>" in proc.stdout
        report = json.loads(_cli(["--files", "sa.json"], tmp_path, tmp_path).stdout)
        [finding] = report["findings"]
        assert finding == {
            "file": "sa.json",
            "line": 1,
            "severity": "CRITICAL",
            "rule": "hardcoded-secret",
            "match": "<redacted:private-key>",
        }

    def test_long_secret_shows_type_and_last_four_only(self, tmp_path):
        _write(tmp_path, "README.md", "Example key: " + AWS_ID + " in our docs.")
        proc = _cli(["--files", "README.md"], tmp_path, tmp_path)
        assert AWS_ID not in proc.stdout
        [finding] = json.loads(proc.stdout)["findings"]
        assert finding["match"] == "<redacted:aws-access-key-id:" + AWS_ID[-4:] + ">"

    def test_short_secret_shows_no_characters(self, tmp_path):
        _write(tmp_path, "a.py", "pass" + "word = " + _q(SHORT_PW))
        proc = _cli(["--files", "a.py"], tmp_path, tmp_path)
        assert SHORT_PW not in proc.stdout
        assert [f["match"] for f in json.loads(proc.stdout)["findings"]] == ["<redacted:password>"]

    def test_secret_inside_another_rules_match_is_redacted(self, tmp_path):
        sql = "q = f" + _q("SEL" + "ECT * FROM t WHERE k = '" + AWS_ID + "' AND id = {uid}")
        _write(tmp_path, "q.py", sql)
        for fmt in ("json", "text"):
            proc = _cli(["--files", "q.py"], tmp_path, tmp_path, fmt=fmt)
            assert AWS_ID not in proc.stdout
        rules = {f["rule"] for f in json.loads(_cli(["--files", "q.py"], tmp_path, tmp_path).stdout)["findings"]}
        assert rules == {"hardcoded-secret", "sql-injection"}

    def test_key_body_after_a_header_inside_another_rules_match_is_dropped(self, tmp_path):
        # The private-key rule matches the header alone, so the redaction of
        # another rule's match must not leave the key body that follows it.
        sql = "q = " + _q("SEL" + "ECT * FROM t WHERE k = " + PEM_BEGIN + KEY_BODY + " %s") + " % v"  # nosec - SQL rule fixture
        _write(tmp_path, "q.py", sql)
        for fmt in ("json", "text"):
            proc = _cli(["--files", "q.py"], tmp_path, tmp_path, fmt=fmt)
            assert KEY_BODY[:12] not in proc.stdout
            assert KEY_BODY[-12:] not in proc.stdout
        rules = {f["rule"] for f in json.loads(_cli(["--files", "q.py"], tmp_path, tmp_path).stdout)["findings"]}
        assert rules == {"hardcoded-secret", "sql-injection"}

    def test_long_match_text_is_cut(self, tmp_path):
        _write(tmp_path, "a.py", "subprocess.run(" + "x, " * 200 + "shell" + "=True)")
        [*findings] = json.loads(_cli(["--files", "a.py"], tmp_path, tmp_path).stdout)["findings"]
        assert findings
        assert all(len(f["match"]) <= 163 for f in findings)


# --- D-15 / I-03: formats and file types --------------------------------------


class TestSecretFormats:
    def test_every_format_fires_once_with_its_type_via_files(self, tmp_path):
        for name, body, _ in FORMATS:
            _write(tmp_path, name, body)
        proc = _cli(["--files", *[n for n, _, _ in FORMATS]], tmp_path, tmp_path)
        hits = _secret_hits(json.loads(proc.stdout))
        for name, _, secret_type in FORMATS:
            assert [f["match"].split(":")[1].rstrip(">") for f in hits.get(name, [])] == [secret_type], name
        assert proc.returncode == 1

    def test_every_format_fires_when_staged(self, tmp_path):
        repo = _repo(tmp_path)
        for name, body, _ in FORMATS:
            _write(repo, name, body)
        _git(repo, "add", "-A")
        proc = _cli(["--staged"], repo, tmp_path)
        hits = _secret_hits(json.loads(proc.stdout))
        assert sorted(hits) == sorted(n for n, _, _ in FORMATS)
        assert proc.returncode == 1

    @pytest.mark.parametrize("name,body", NOT_SECRETS, ids=[n for n, _ in NOT_SECRETS])
    def test_lookalikes_stay_quiet(self, tmp_path, name, body):
        _write(tmp_path, name, body)
        report = json.loads(_cli(["--files", name], tmp_path, tmp_path).stdout)
        assert _secret_hits(report) == {}

    def test_secret_in_a_binary_file_still_fires(self, tmp_path):
        _write(tmp_path, "blob.bin", b"\x00\x01PNG\x00" + GH_PAT.encode() + b"\x00\xff")
        hits = _secret_hits(json.loads(_cli(["--files", "blob.bin"], tmp_path, tmp_path).stdout))
        assert [f["match"].split(":")[1] for f in hits["blob.bin"]] == ["github-token"]

    def test_code_rules_do_not_run_on_unsupported_files(self, tmp_path):
        _write(tmp_path, "run.sh", HIGH_LINE + "\n" + EVAL_LINE)
        report = json.loads(_cli(["--files", "run.sh"], tmp_path, tmp_path).stdout)
        assert report["findings"] == []
        assert report["summary"]["files_scanned"] == 1

    def test_keyword_rules_stay_out_of_docs(self, tmp_path):
        _write(tmp_path, "guide.md", "Use token = " + _q(SECRET_24) + " in prose.")
        assert _secret_hits(json.loads(_cli(["--files", "guide.md"], tmp_path, tmp_path).stdout)) == {}

    def test_nosec_and_ignore_file_still_apply_to_the_secret_pass(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, ".env", "API_" + "KEY=" + ENV_KEY + "  # nosec - fixture")
        _write(repo, "vendor/x.sh", "export API_" + "KEY=" + _q(SH_KEY))
        _write(repo, ".claude/security-review-ignore", "vendor/*")
        _git(repo, "add", "-A")
        report = json.loads(_cli(["--staged"], repo, tmp_path).stdout)
        assert report["findings"] == []
        assert report["summary"]["files_skipped"] >= 1


# --- D-03: --staged reads the index -------------------------------------------


class TestStagedIndex:
    def test_staged_content_is_scanned_not_the_working_tree(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, "app.py", "import os\n" + HIGH_LINE)
        _git(repo, "add", "app.py")
        _write(repo, "app.py", "x = 1")
        report = json.loads(_cli(["--staged"], repo, tmp_path).stdout)
        assert [(f["file"], f["line"], f["rule"]) for f in report["findings"]] == [("app.py", 2, "shell-injection")]

    def test_unstaged_working_tree_change_is_not_scanned(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, "app.py", "x = 1")
        _git(repo, "add", "app.py")
        _write(repo, "app.py", "import os\n" + HIGH_LINE)
        proc = _cli(["--staged"], repo, tmp_path)
        assert json.loads(proc.stdout)["findings"] == []
        assert proc.returncode == 0

    def test_subdirectory_cwd_scans_paths_from_the_top_level(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, "pkg/app.py", "import os\n" + HIGH_LINE)
        _git(repo, "add", "-A")
        proc = _cli(["--staged"], repo / "pkg", tmp_path)
        report = json.loads(proc.stdout)
        assert [f["file"] for f in report["findings"]] == ["pkg/app.py"]
        assert report["summary"]["files_scanned"] == 1
        assert proc.returncode == 1

    def test_renamed_file_is_scanned(self, tmp_path):
        repo = _repo(tmp_path)
        body = "\n".join(f"value_{i} = {i}" for i in range(30))
        _write(repo, "old.py", body)
        _git(repo, "add", "old.py")
        _commit(repo)
        _git(repo, "mv", "old.py", "new.py")
        _write(repo, "new.py", body + "\nimport os\n" + HIGH_LINE)
        _git(repo, "add", "new.py")
        status = subprocess.run(
            ["git", "diff", "--cached", "--name-status"], cwd=repo, env=_env(tmp_path), capture_output=True, text=True
        ).stdout
        assert status.startswith("R"), status
        report = json.loads(_cli(["--staged"], repo, tmp_path).stdout)
        assert [f["file"] for f in report["findings"]] == ["new.py"]

    @pytest.mark.skipif(sys.platform == "win32", reason="needs symlinks")
    def test_symlink_replaced_by_a_file_is_scanned(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, "target.txt", "x")
        (repo / "link.py").symlink_to("target.txt")
        _git(repo, "add", "-A")
        _commit(repo)
        (repo / "link.py").unlink()
        _write(repo, "link.py", "import os\n" + HIGH_LINE)
        _git(repo, "add", "link.py")
        report = json.loads(_cli(["--staged"], repo, tmp_path).stdout)
        assert [f["file"] for f in report["findings"]] == ["link.py"]

    def test_non_ascii_path_is_scanned(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, "café.py", "import os\n" + HIGH_LINE)
        _git(repo, "add", "-A")
        report = json.loads(_cli(["--staged"], repo, tmp_path).stdout)
        assert [f["file"] for f in report["findings"]] == ["café.py"]

    def test_deleted_file_is_not_an_error(self, tmp_path):
        repo = _repo(tmp_path)
        _write(repo, "gone.py", "x = 1")
        _git(repo, "add", "gone.py")
        _commit(repo)
        _git(repo, "rm", "--quiet", "gone.py")
        proc = _cli(["--staged"], repo, tmp_path)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert json.loads(proc.stdout)["summary"]["incomplete"] == []

    def test_outside_a_work_tree_is_reported_not_passed(self, tmp_path):
        bare = tmp_path / "not-a-repo"
        bare.mkdir()
        proc = _cli(["--staged"], bare, tmp_path)
        assert proc.returncode == 2
        reasons = json.loads(proc.stdout)["summary"]["incomplete"]
        assert reasons and "git" in reasons[0]

    def test_oversized_staged_file_is_reported(self, tmp_path, monkeypatch):
        repo = _repo(tmp_path)
        _write(repo, "big.txt", "y" * 4096)
        _write(repo, "app.py", "x = 1")
        _git(repo, "add", "-A")
        monkeypatch.setattr(scan, "_MAX_SCAN_BYTES", 1024)
        code, report = _main_in_process(["--staged"], repo, tmp_path, monkeypatch)
        assert code == 2
        assert any("big.txt" in r for r in report["summary"]["incomplete"])
        assert report["summary"]["files_scanned"] == 1


# --- D-02: robustness -----------------------------------------------------------


def _main_in_process(args: list[str], cwd: Path, home: Path, monkeypatch) -> tuple[int, dict]:
    monkeypatch.chdir(cwd)
    for key, value in _env(home).items():
        monkeypatch.setenv(key, value)
    for key in [k for k in os.environ if k.startswith("GIT_") and k not in _env(home)]:
        monkeypatch.delenv(key, raising=False)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = scan.main(["--format", "json", *args])
    return code, json.loads(out.getvalue())


class TestRobustness:
    @pytest.mark.parametrize("config", [{"patterns": None}, [{"rule_name": "x"}], {"patterns": "x"}, "text"])
    def test_malformed_rules_file_warns_and_built_ins_still_run(self, tmp_path, config):
        _write(tmp_path, ".claude/security-patterns.json", json.dumps(config))
        _write(tmp_path, "app.py", "import os\n" + HIGH_LINE)
        proc = _cli(["--files", "app.py"], tmp_path, tmp_path)
        assert "Traceback" not in proc.stderr
        assert "security-patterns" in proc.stderr
        assert [f["rule"] for f in json.loads(proc.stdout)["findings"]] == ["shell-injection"]
        assert proc.returncode == 1

    def test_crash_exits_2_with_a_reason(self, tmp_path, monkeypatch):
        _write(tmp_path, "app.py", "x = 1")

        def boom(rule, filepath):
            raise RuntimeError("rule table broke")

        monkeypatch.setattr(scan, "_rule_applies_to_file", boom)
        code, report = _main_in_process(["--files", "app.py"], tmp_path, tmp_path, monkeypatch)
        assert code == 2
        assert any("rule table broke" in r for r in report["summary"]["incomplete"])

    def test_spent_time_budget_exits_2_with_a_reason(self, tmp_path):
        for i in range(3):
            _write(tmp_path, f"m{i}.py", "x = 1")
        proc = _cli(["--time-budget", "0.000001", "--files", "m0.py", "m1.py", "m2.py"], tmp_path, tmp_path)
        assert proc.returncode == 2, proc.stderr
        reasons = json.loads(proc.stdout)["summary"]["incomplete"]
        assert reasons and "time budget" in reasons[0]

    def test_time_budget_is_checked_inside_one_long_line(self):
        # A single multi-megabyte line must not run past the budget: the hook
        # kills an overrunning scan and loses every finding it already had.
        class _SpentAfterTwoChecks:
            calls = 0

            def check(self):
                self.calls += 1
                if self.calls > 2:
                    raise scan._OutOfTime

        line = "k='" + AWS_ID + "';" + "x" * (20 * scan._WINDOW_CHARS)
        found: list[dict] = []
        with pytest.raises(scan._OutOfTime):
            scan._scan_text("min.js", line, scan._build_rules(), _SpentAfterTwoChecks(), found)
        assert [f["match"].split(":")[1] for f in found] == ["aws-access-key-id"]

    def test_budget_spent_in_a_long_line_keeps_earlier_findings(self, tmp_path):
        _write(tmp_path, "a.py", "import os\n" + HIGH_LINE)
        _write(tmp_path, "b.py", "x = 1;" * 400_000)
        proc = _cli(["--time-budget", "0.3", "--files", "a.py", "b.py"], tmp_path, tmp_path)
        report = json.loads(proc.stdout)
        assert proc.returncode == 1, proc.stderr
        assert [f["file"] for f in report["findings"]] == ["a.py"]
        assert any("time budget" in r for r in report["summary"]["incomplete"])

    def test_findings_beyond_the_first_window_are_found_once(self, tmp_path):
        line = "var a=1;" * 1500 + "k='" + AWS_ID + "';" + "b=2;" * 3000 + "t='" + GH_PAT + "'"
        assert len(line) > 4 * scan._WINDOW_CHARS
        _write(tmp_path, "min.js", line)
        hits = _secret_hits(json.loads(_cli(["--files", "min.js"], tmp_path, tmp_path).stdout))
        assert sorted(f["match"].split(":")[1] for f in hits["min.js"]) == ["aws-access-key-id", "github-token"]

    def test_a_match_across_a_window_edge_is_found_once(self):
        stride = scan._WINDOW_CHARS - scan._WINDOW_OVERLAP
        rule = {"name": "probe", "severity": "HIGH", "pattern": scan.re.compile(r"QQQQ[0-9]{6}"), "scope": "any"}
        for offset in (stride - 5, stride - 1, stride, stride + 3, 2 * stride - 2):
            line = "-" * offset + "QQQQ123456" + "-" * (3 * scan._WINDOW_CHARS)
            assert [f["rule"] for f in scan._scan_text("x.txt", line, [rule])] == ["probe"], offset


class TestBoundedSqlRules:
    """The bounded SQL rules keep what the old `.*` and `[^"']*` forms matched."""

    RULES = scan._build_rules()

    def _sql(self, name: str, src: str) -> int:
        return sum(f["rule"] == "sql-injection" for f in scan._scan_text(name, src, self.RULES))

    @pytest.mark.parametrize(
        "name, src",
        [
            ("a.py", 'q = f"SEL' + 'ECT name FROM users WHERE id = {uid}"'),
            ("b.py", 'q = f"SEL' + "ECT name FROM users WHERE name = '{name}'\""),
            ("c.py", 'q = "SEL' + 'ECT name FROM users WHERE id = %s" % uid'),
            ("d.py", 'q = "SEL' + 'ECT name FROM users WHERE id = {}".format(uid)'),
            ("e.go", 'q := fmt.Sprintf("SEL' + 'ECT name FROM users WHERE id = %d", id)'),  # nosec - SQL rule fixture
            ("f.js", 'q = "SEL' + 'ECT name FROM users WHERE id = " + id;'),  # nosec - SQL rule fixture
        ],
    )
    def test_query_built_from_input_fires(self, name, src):
        assert self._sql(name, src) >= 1

    def test_brace_before_the_keyword_stays_quiet(self):
        # A report line, not a query: the only keyword (values) follows every brace.
        src = 'msg = f"{pct:.0f}% of {sum(p.counts.val' + 'ues())} rows match"'
        assert self._sql("report.py", src) == 0


# Adversarial single-line inputs from lane D's probe. On the old patterns each took
# minutes (one 20 KB line took 18 s on one rule). Built at runtime from parts.
_ADVERSARIAL = {
    "unterminated.js": 'var s = "' + ("sel" + "ect from where ") * 60_000,
    "todo_line.py": "x = '" + ("to" + "do ") * 200_000 + "'",
    "fstring_line.py": "q = " + ("f'sel" + "ect ") * 120_000,
    "minified.js": (
        'function(e,t){if("undefined"==typeof e)return t.update({id:e.id,select:!0});'
        "var n=e.de" + "lete?e.de" + 'lete(t):null;n&&n.insertBefore(t,"a"+t+"b");'
        'for(var r=0;r<t.length;r++){o[r]="from "+t[r]+" where";}return n},'
    )
    * 10_000,
    "pct_segments.py": ('"' + ("sel" + "ect %s ") * 45 + '" ') * 2_500,
}


@pytest.mark.performance
@pytest.mark.parametrize("name", sorted(_ADVERSARIAL))
def test_adversarial_long_line_scans_quickly(tmp_path, name):
    _write(tmp_path, name, _ADVERSARIAL[name])
    started = time.monotonic()
    proc = _cli(["--files", name], tmp_path, tmp_path, timeout=120)
    elapsed = time.monotonic() - started
    assert proc.returncode in (0, 1), proc.stderr
    assert elapsed < 15, f"{name} took {elapsed:.1f}s"
