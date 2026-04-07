#!/usr/bin/env python3
"""
Blind scorer for adaptive-thinking A/B test.

Reads result files from results/ and asks claude -p to score each one on
4 dimensions without knowing which variant produced it. Outputs scores.json.

Scoring dimensions (1-10 each):
  1. true_positives    — real bugs found; no fabricated issues
  2. severity_calib    — severity ratings match actual severity of issues
  3. actionability     — developer can fix from the review alone
  4. thoroughness      — coverage of the file's distinct code paths

Run AFTER run_ab_test.py. Do NOT load mapping.json in this script.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).parent.resolve()
RESULTS_DIR = SCRIPT_DIR / "results"
SCORES_FILE = SCRIPT_DIR / "scores.json"
REPO_ROOT = Path("/home/feedgen/claude-code-toolkit")

CLAUDE_BIN = "claude"

# ── embedded reference file (same content used in run_ab_test.py) ─────────────
# The judge is given the original file so it can verify claims.

REFERENCE_FILE_CONTENT = r'''#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse Hook: Unified Gate (ADR-068)

Consolidates 5 PreToolUse gate hooks into a single entry point:
1. block-gitignore-bypass   — Bash: blocks git add -f on gitignored paths & .gitignore edits
2. pretool-git-submission-gate — Bash: blocks raw git push, gh pr create/merge
3. pretool-dangerous-command-guard — Bash: blocks destructive commands
4. pretool-creation-gate    — Write: blocks new agent/skill file creation
5. pretool-sensitive-file-guard — Write+Edit: blocks writes to .env, credentials, SSH keys, etc.

Attribution blocking removed: use settings.json {"attribution": {"commit": "", "pr": ""}} instead.
Each check preserves its original stderr prefix and bypass mechanism.
Exit 0 always. Blocks emit JSON permissionDecision:deny to stdout. Entire main() wrapped in try/except to fail OPEN.

Performance: <50ms. Early-exit for non-matching tools. Only gitignore bypass uses subprocess.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from learning_db_v2 import record_governance_event
from stdin_timeout import read_stdin

# ═══════════════════════════════════════════════════════════════
# 1. GITIGNORE BYPASS (block-gitignore-bypass.py)
# ═══════════════════════════════════════════════════════════════

# (patterns are inline in check_gitignore_bypass function)

# ═══════════════════════════════════════════════════════════════
# 2. GIT SUBMISSION PATTERNS (pretool-git-submission-gate.py)
# ═══════════════════════════════════════════════════════════════

_GIT_SUBMISSION_BYPASS = "CLAUDE_GATE_BYPASS=1"

_GIT_PUSH_PATTERN = re.compile(r"^(?:\w+=\S+\s+)*git\s+push\b")

_GIT_SUBMISSION_PATTERNS = [
    (_GIT_PUSH_PATTERN, "pr-sync", "Use /pr-sync to push (runs review loop first)"),
    (
        re.compile(r"^(?:\w+=\S+\s+)*gh\s+pr\s+create\b"),
        "pr-pipeline",
        "Use /pr-pipeline to create PR (runs review loop first)",
    ),
    (
        re.compile(r"^(?:\w+=\S+\s+)*gh\s+pr\s+merge\b"),
        "pr-pipeline",
        "Use /pr-pipeline to merge (requires review to pass first)",
    ),
]

# ═══════════════════════════════════════════════════════════════
# 3. DANGEROUS COMMAND PATTERNS (pretool-dangerous-command-guard.py)
# ═══════════════════════════════════════════════════════════════

_DANGEROUS_BYPASS_ENV = "DANGEROUS_GUARD_BYPASS"

_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Filesystem destruction
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+/\s*$"), "filesystem", "rm -rf /"),
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+/\*"), "filesystem", "rm -rf /*"),
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+~/?(\s|$)"), "filesystem", "rm -rf ~"),
    (re.compile(r"\brm\s+(-[a-zA-Z]*f[a-zA-Z]*\s+)?-[a-zA-Z]*r[a-zA-Z]*\s+\./?(\s|$)"), "filesystem", "rm -rf ."),
    # Database destruction
    (re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE), "database", "DROP DATABASE"),
    (re.compile(r"\bDROP\s+SCHEMA\b", re.IGNORECASE), "database", "DROP SCHEMA"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE), "database", "TRUNCATE TABLE"),
    # Permission escalation
    (re.compile(r"\bchmod\s+(-R\s+)?777\b"), "permissions", "chmod 777"),
    # Force-push to protected branches
    (re.compile(r"\bgit\s+push\s+.*--force\s+.*\b(main|master)\b"), "git", "git push --force main/master"),
    (re.compile(r"\bgit\s+push\s+-f\s+.*\b(main|master)\b"), "git", "git push -f main/master"),
    # Container mass-kill
    (re.compile(r"\bdocker\s+system\s+prune\s+-af\b"), "container", "docker system prune -af"),
    (re.compile(r"\bkubectl\s+delete\s+namespace\b"), "container", "kubectl delete namespace"),
    (re.compile(r"\bkubectl\s+delete\s+ns\b"), "container", "kubectl delete ns"),
    # System-level danger
    (re.compile(r"\bmkfs\b"), "system", "mkfs (format disk)"),
    (re.compile(r"\bdd\s+if="), "system", "dd (raw disk write)"),
    # Cloud destructive
    (re.compile(r"\bterraform\s+destroy\b(?!.*-target)"), "cloud", "terraform destroy (no -target)"),
    (re.compile(r"\baws\s+s3\s+rb\s+.*--force\b"), "cloud", "aws s3 rb --force"),
]

# ═══════════════════════════════════════════════════════════════
# 4. CREATION GATE PATTERNS (pretool-creation-gate.py)
# ═══════════════════════════════════════════════════════════════

_CREATION_BYPASS_ENV = "CREATION_GATE_BYPASS"

_AGENT_PATTERN = re.compile(r"/agents/[^/]+\.md$")
_SKILL_PATTERN = re.compile(r"/(skills|pipelines)/[^/]+/SKILL\.md$")
_WORKFLOW_REF_PATTERN = re.compile(r"/skills/workflow/references/[^/]+\.md$")

# ═══════════════════════════════════════════════════════════════
# 5. SENSITIVE FILE PATTERNS (pretool-sensitive-file-guard.py)
# ═══════════════════════════════════════════════════════════════

_SENSITIVE_BYPASS_ENV = "SENSITIVE_FILE_GUARD_BYPASS"

_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Environment files (except .env.example)
    (re.compile(r"/\.env$"), "env", ".env"),
    (re.compile(r"/\.env\.(local|production|staging|development|dev|prod)$"), "env", ".env.*"),
    # Credential files
    (re.compile(r"/credentials\.(json|yml|yaml)$"), "credentials", "credentials file"),
    (re.compile(r"/service-account[^/]*\.json$"), "credentials", "service account JSON"),
    # SSH keys
    (re.compile(r"/\.ssh/"), "ssh", "SSH directory"),
    (re.compile(r"/id_(rsa|ed25519|ecdsa|dsa)$"), "ssh", "SSH private key"),
    # Private key / certificate files
    (re.compile(r"\.p12$"), "certificate", ".p12 certificate"),
    (re.compile(r"\.pfx$"), "certificate", ".pfx certificate"),
    (re.compile(r"\.key$"), "certificate", ".key private key"),
    # Cloud configs
    (re.compile(r"\.aws/credentials$"), "cloud", "AWS credentials"),
    (re.compile(r"\.kube/config$"), "cloud", "kubeconfig"),
    (re.compile(r"\.gcloud/"), "cloud", "gcloud config directory"),
    # Token files
    (re.compile(r"/token\.json$"), "token", "token.json"),
    (re.compile(r"/\.tokens$"), "token", ".tokens file"),
]

_SENSITIVE_EXCEPTIONS: list[re.Pattern[str]] = [
    re.compile(r"\.env\.example$"),
    re.compile(r"\.env\.sample$"),
    re.compile(r"\.env\.template$"),
    re.compile(r"/testdata/"),
    re.compile(r"/fixtures/"),
    re.compile(r"/__fixtures__/"),
    re.compile(r"/test_?data/"),
]


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════


def _load_guard_whitelist() -> list[str]:
    """Load per-project whitelist from .guard-whitelist if it exists."""
    whitelist_path = Path.cwd() / ".guard-whitelist"
    if not whitelist_path.is_file():
        return []
    try:
        entries = []
        for line in whitelist_path.read_text().splitlines():
            entry = line.strip()
            if not entry or entry.startswith("#"):
                continue
            if len(entry) < 8:
                print(
                    f"[dangerous-command-guard] WARN: Skipping short whitelist entry (< 8 chars): {entry!r}",
                    file=sys.stderr,
                )
                continue
            entries.append(entry)
        print(
            f"[dangerous-command-guard] INFO: Loaded {len(entries)} whitelist entries from {whitelist_path}",
            file=sys.stderr,
        )
        return entries
    except OSError:
        return []


def _is_whitelisted(command: str, whitelist: list[str]) -> bool:
    """Check if the command matches any whitelist entry."""
    for entry in whitelist:
        if entry in command:
            return True
    return False


def _load_guard_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """Load per-project sensitive patterns from .guard-patterns."""
    guard_path = Path.cwd() / ".guard-patterns"
    if not guard_path.is_file():
        return []
    extra = []
    try:
        for line in guard_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                regex = line.replace(".", r"\.").replace("*", ".*").replace("?", ".")
                extra.append((re.compile(regex), "custom", line))
    except OSError:
        pass
    return extra


def _is_sensitive_exception(file_path: str) -> bool:
    """Check if file matches a sensitive-file exception pattern."""
    return any(p.search(file_path) for p in _SENSITIVE_EXCEPTIONS)


def _block(message: str, tool_name: str = "", reason: str = "") -> None:
    """Emit a structured deny decision and exit 0."""
    print(message, file=sys.stderr)
    try:
        record_governance_event("hook_blocked", tool_name=tool_name, hook_phase="pre", severity="high", blocked=True)
    except Exception:
        pass
    deny_reason = reason if reason else message
    deny_output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    print(json.dumps(deny_output))
    sys.exit(0)


# ═══════════════════════════════════════════════════════════════
# CHECK FUNCTIONS
# ═══════════════════════════════════════════════════════════════


def check_gitignore_bypass(command: str) -> None:
    """Block git add -f on gitignored paths and .gitignore edits."""
    cmd_part = command.split("<<")[0] if "<<" in command else command
    if (
        re.search(r"(>|>>)\s*\.gitignore", cmd_part)
        or re.search(r"(sed|awk|tee)\b.*\.gitignore", cmd_part)
        or re.search(r"mv\s+\S+\s+\.gitignore", cmd_part)
    ):
        _block(
            "[gitignore-bypass] BLOCKED: Agents must not modify .gitignore.\n"
            "[gitignore-bypass] This file controls repository safety boundaries.",
            reason="Agents must not modify .gitignore. This file controls repository safety boundaries.",
        )

    if "git add" not in command:
        return

    if not re.search(r"git\s+add\s+.*(-f|--force)", command):
        return

    parts = command.split()
    try:
        add_idx = parts.index("add")
    except ValueError:
        return

    paths = []
    past_separator = False
    for part in parts[add_idx + 1 :]:
        if part == "--":
            past_separator = True
            continue
        if part.startswith("-") and not past_separator:
            continue
        paths.append(part)

    if not paths:
        return

    try:
        result = subprocess.run(
            ["git", "check-ignore"] + paths,
            capture_output=True,
            text=True,
            timeout=3,
        )
        ignored = [p for p in result.stdout.strip().split("\n") if p]
    except (subprocess.TimeoutExpired, OSError):
        return

    if ignored:
        _block(
            f"[gitignore-bypass] BLOCKED: git add -f on gitignored paths: {', '.join(ignored)}\n"
            "[gitignore-bypass] These paths are gitignored for a reason. Do not force-add them.",
            reason=f"Cannot force-add gitignored paths: {', '.join(ignored)}. These paths are gitignored for a reason. Stage only tracked files.",
        )


def _extract_effective_cwd(command: str, default_cwd: str | None = None) -> str | None:
    """Extract the effective working directory from a command string."""
    m = re.match(r'cd\s+(?:"([^"]+)"|(\S+))\s*(?:&&|;)', command.lstrip())
    if m:
        p = (m.group(1) or m.group(2) or "").strip()
        if p:
            return p
    m = re.search(r'\bgit\s+-C\s+(?:"([^"]+)"|(\S+))', command)
    if m:
        return m.group(1) or m.group(2)
    return default_cwd


def _is_worktree_on_feature_branch(cwd: str) -> bool:
    """Return True if cwd is a worktree directory on a non-protected branch."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return bool(branch) and branch not in {"main", "master"}
    except (subprocess.TimeoutExpired, OSError):
        pass
    return False


def check_git_submission(command: str) -> None:
    """Block raw git push, gh pr create, gh pr merge unless bypassed or personal profile."""
    if command.lstrip().startswith(_GIT_SUBMISSION_BYPASS):
        return

    operator = os.environ.get("CLAUDE_OPERATOR_PROFILE", "personal")
    if operator == "personal":
        return

    cmd = command.lstrip()
    for pattern, skill_name, message in _GIT_SUBMISSION_PATTERNS:
        if pattern.search(cmd):
            if pattern is _GIT_PUSH_PATTERN:
                effective_cwd = _extract_effective_cwd(command)
                project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
                if effective_cwd and effective_cwd != project_dir and _is_worktree_on_feature_branch(effective_cwd):
                    return
            _block(
                f"[git-submission-gate] BLOCKED: {message}\n[fix-with-skill] {skill_name}",
                reason=f"{message} Use the {skill_name} skill instead.",
            )


def check_dangerous_command(command: str) -> None:
    """Block destructive commands unless bypassed or whitelisted."""
    if os.environ.get(_DANGEROUS_BYPASS_ENV) == "1":
        return

    whitelist = _load_guard_whitelist()

    for pattern, category, description in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            if _is_whitelisted(command, whitelist):
                return
            _block(
                f"[dangerous-command] BLOCKED: {description} ({category})\n"
                f"[dangerous-command] Command: {command}\n"
                f"[dangerous-command] To allow: add pattern to .guard-whitelist",
                reason=f"Dangerous command blocked: {description} (category: {category}). To allow, add a pattern to .guard-whitelist.",
            )


def check_creation_gate(file_path: str) -> None:
    """Block new agent/skill file creation unless bypassed."""
    if os.environ.get(_CREATION_BYPASS_ENV) == "1":
        return

    is_agent = bool(_AGENT_PATTERN.search(file_path))
    is_skill = bool(_SKILL_PATTERN.search(file_path))
    is_workflow_ref = bool(_WORKFLOW_REF_PATTERN.search(file_path))
    if not is_agent and not is_skill and not is_workflow_ref:
        return

    if os.path.exists(file_path):
        return

    component_type = "agent" if is_agent else "workflow reference" if is_workflow_ref else "skill"
    _block(
        f"[creation-gate] BLOCKED: New {component_type} must be created via skill-creator or skill-creation-pipeline.\n"
        f"[creation-gate] Path: {file_path}\n"
        f"[fix-with-agent] skill-creator",
        reason=f"New {component_type} files must be created via the skill-creator agent, not written directly. Use [fix-with-agent] skill-creator.",
    )


def check_sensitive_file(file_path: str) -> None:
    """Block writes to sensitive files unless bypassed or excepted."""
    if os.environ.get(_SENSITIVE_BYPASS_ENV) == "1":
        return

    if _is_sensitive_exception(file_path):
        return

    all_patterns = _SENSITIVE_PATTERNS + _load_guard_patterns()
    for pattern, category, description in all_patterns:
        if pattern.search(file_path):
            _block(
                f"[sensitive-file-guard] BLOCKED: Write to sensitive file ({category})\n"
                f"[sensitive-file-guard] Path: {file_path}\n"
                f"[sensitive-file-guard] Pattern: {description}\n"
                f"[sensitive-file-guard] To allow: set SENSITIVE_FILE_GUARD_BYPASS=1 or add exception to .guard-patterns",
                reason=f"Write to sensitive file blocked ({category}: {description}). Path: {file_path}. Set SENSITIVE_FILE_GUARD_BYPASS=1 or add an exception to .guard-patterns to allow.",
            )


def main() -> None:
    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return

    tool = event.get("tool_name") or event.get("tool", "")
    tool_input = event.get("tool_input", event.get("input", {}))

    if tool == "Bash":
        command = tool_input.get("command", "")
        if not command:
            return
        check_gitignore_bypass(command)
        check_git_submission(command)
        check_dangerous_command(command)

    elif tool == "Write":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        check_creation_gate(file_path)
        check_sensitive_file(file_path)

    elif tool == "Edit":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        check_sensitive_file(file_path)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:
        print(f"[unified-gate] HOOK-CRASH: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        sys.exit(0)
'''

# ── judge prompt template ─────────────────────────────────────────────────────

JUDGE_PROMPT_TEMPLATE = """\
You are a code review judge. Your task is to evaluate the quality of a code review output.

The reviewer was asked to inspect a Python file for bugs, security issues, and improvements, \
and to provide: Severity (CRITICAL/HIGH/MEDIUM/LOW), line numbers, description, and suggested fix.

Score the review on four dimensions, each from 1 to 10:

1. **true_positives** (1-10): Are the reported issues real problems that actually exist in \
the file? Penalize fabricated or hallucinated issues. 10 = only real issues, 1 = mostly invented.

2. **severity_calib** (1-10): Do the severity labels match the actual risk of the issues? \
10 = perfectly calibrated, 1 = wildly miscalibrated (e.g., calling benign code CRITICAL).

3. **actionability** (1-10): Can a developer fix the issues using only the information \
provided? 10 = fully actionable with specific code suggestions, 1 = vague hand-waving.

4. **thoroughness** (1-10): How well does the review cover the distinct logic paths and \
concerns in the file? Consider: gitignore bypass check, git submission gate, dangerous command \
guard, creation gate, sensitive file guard, helper functions, main() flow, error handling. \
10 = comprehensive coverage, 1 = misses most of the file.

Respond ONLY with a JSON object in this exact format (no commentary, no markdown fences):
{{"true_positives": <int>, "severity_calib": <int>, "actionability": <int>, "thoroughness": <int>, "notes": "<one sentence>"}}

Reference file (the code being reviewed):
<reference_file>
{reference_content}
</reference_file>

Code review to evaluate:
<review>
{review_text}
</review>
"""


# ── helpers ───────────────────────────────────────────────────────────────────


def parse_result_file(path: Path) -> dict:
    """Parse metadata and review text from a result file.

    Args:
        path: Path to a result file.

    Returns:
        Dict with hex_id, round, exit_code, duration_s, review_text.
    """
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    meta: dict = {"hex_id": path.stem.split("_", 1)[1], "file": str(path.name)}
    review_lines: list[str] = []
    in_output = False

    for line in lines:
        if line.startswith("hex_id: "):
            meta["hex_id"] = line[len("hex_id: ") :]
        elif line.startswith("round: "):
            try:
                meta["round"] = int(line[len("round: ") :])
            except ValueError:
                pass
        elif line.startswith("exit_code: "):
            try:
                meta["exit_code"] = int(line[len("exit_code: ") :])
            except ValueError:
                meta["exit_code"] = -1
        elif line.startswith("duration_s: "):
            try:
                meta["duration_s"] = float(line[len("duration_s: ") :])
            except ValueError:
                pass
        elif line == "--- output ---":
            in_output = True
        elif line == "--- stderr ---":
            in_output = False
        elif in_output:
            review_lines.append(line)

    meta["review_text"] = "\n".join(review_lines).strip()
    return meta


def score_one(result_meta: dict) -> dict:
    """Call claude -p to score a single review.

    Args:
        result_meta: Parsed result file metadata including review_text.

    Returns:
        Dict with hex_id, scores (or error), duration_s.
    """
    hex_id = result_meta["hex_id"]
    review_text = result_meta.get("review_text", "")

    if not review_text:
        print(f"  [{hex_id}] SKIP — empty review text", flush=True)
        return {
            "hex_id": hex_id,
            "round": result_meta.get("round"),
            "error": "empty review text",
            "true_positives": None,
            "severity_calib": None,
            "actionability": None,
            "thoroughness": None,
            "notes": "",
            "run_duration_s": result_meta.get("duration_s"),
            "score_duration_s": 0,
        }

    judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
        reference_content=REFERENCE_FILE_CONTENT,
        review_text=review_text,
    )

    cmd = [
        CLAUDE_BIN,
        "--max-turns",
        "1",
        "-p",
        judge_prompt,
    ]

    print(f"  [{hex_id}] scoring ...", flush=True)
    start = time.monotonic()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=120,
        )
        score_duration = time.monotonic() - start

        if result.returncode != 0:
            print(f"  [{hex_id}] claude returned exit {result.returncode}", flush=True)
            return {
                "hex_id": hex_id,
                "round": result_meta.get("round"),
                "error": f"claude exit {result.returncode}: {result.stderr[:200]}",
                "true_positives": None,
                "severity_calib": None,
                "actionability": None,
                "thoroughness": None,
                "notes": "",
                "run_duration_s": result_meta.get("duration_s"),
                "score_duration_s": round(score_duration, 2),
            }

        raw_output = result.stdout.strip()

        # Extract JSON from output — model may include surrounding text
        json_start = raw_output.find("{")
        json_end = raw_output.rfind("}") + 1
        if json_start == -1 or json_end == 0:
            raise ValueError(f"No JSON found in output: {raw_output[:200]}")

        scores_json = json.loads(raw_output[json_start:json_end])

    except subprocess.TimeoutExpired:
        score_duration = time.monotonic() - start
        print(f"  [{hex_id}] TIMEOUT", flush=True)
        return {
            "hex_id": hex_id,
            "round": result_meta.get("round"),
            "error": "timeout",
            "true_positives": None,
            "severity_calib": None,
            "actionability": None,
            "thoroughness": None,
            "notes": "",
            "run_duration_s": result_meta.get("duration_s"),
            "score_duration_s": round(score_duration, 2),
        }
    except (json.JSONDecodeError, ValueError) as exc:
        score_duration = time.monotonic() - start
        print(f"  [{hex_id}] JSON parse error: {exc}", flush=True)
        return {
            "hex_id": hex_id,
            "round": result_meta.get("round"),
            "error": f"json parse: {exc}",
            "true_positives": None,
            "severity_calib": None,
            "actionability": None,
            "thoroughness": None,
            "notes": "",
            "run_duration_s": result_meta.get("duration_s"),
            "score_duration_s": round(score_duration, 2),
        }

    print(
        f"  [{hex_id}] scored: "
        f"tp={scores_json.get('true_positives')} "
        f"sc={scores_json.get('severity_calib')} "
        f"ac={scores_json.get('actionability')} "
        f"th={scores_json.get('thoroughness')}",
        flush=True,
    )

    return {
        "hex_id": hex_id,
        "round": result_meta.get("round"),
        "error": "",
        "true_positives": scores_json.get("true_positives"),
        "severity_calib": scores_json.get("severity_calib"),
        "actionability": scores_json.get("actionability"),
        "thoroughness": scores_json.get("thoroughness"),
        "notes": scores_json.get("notes", ""),
        "run_duration_s": result_meta.get("duration_s"),
        "score_duration_s": round(score_duration, 2),
    }


# ── main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    """Score all result files and write scores.json."""
    if not RESULTS_DIR.exists():
        print(f"ERROR: results directory not found: {RESULTS_DIR}", file=sys.stderr)
        sys.exit(1)

    result_files = sorted(RESULTS_DIR.glob("*.txt"))
    if not result_files:
        print("ERROR: no result files found in results/", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(result_files)} result files to score")

    scores: list[dict] = []
    for i, path in enumerate(result_files, 1):
        print(f"\n[{i}/{len(result_files)}] {path.name}")
        try:
            meta = parse_result_file(path)
        except Exception as exc:
            print(f"  PARSE ERROR: {exc}", flush=True)
            scores.append({"hex_id": path.stem, "error": f"parse: {exc}"})
            continue

        if meta.get("exit_code", 0) != 0:
            print(f"  SKIP — original run failed (exit {meta.get('exit_code')})", flush=True)
            scores.append(
                {
                    "hex_id": meta["hex_id"],
                    "round": meta.get("round"),
                    "error": f"original run failed (exit {meta.get('exit_code')})",
                    "true_positives": None,
                    "severity_calib": None,
                    "actionability": None,
                    "thoroughness": None,
                    "notes": "",
                    "run_duration_s": meta.get("duration_s"),
                    "score_duration_s": 0,
                }
            )
            continue

        score = score_one(meta)
        scores.append(score)

    with open(SCORES_FILE, "w", encoding="utf-8") as fh:
        json.dump(scores, fh, indent=2)

    scored = sum(1 for s in scores if s.get("error") == "")
    failed = sum(1 for s in scores if s.get("error"))
    print(f"\nScoring complete: {scored} scored, {failed} errors")
    print(f"Scores written to: {SCORES_FILE}")
    print("\nNext: run generate_report.py to unblind and compare variants.")


if __name__ == "__main__":
    main()
