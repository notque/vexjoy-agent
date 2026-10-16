"""Session-model route pick for /d, used by the eval drivers.

In production the session model reads /d's SKILL.md, the routing manifest, and
/do's rule text, then picks the agent, skill, and pipeline. The eval drivers
stand in for that session with `claude -p`: the system prompt holds the same
three texts, the user prompt holds the request and the prepared JEV_RESULT, and
the reply is the decision JSON. `jev-route.py --finalize` then validates the
decision and computes `attach`, exactly as in production.

Callers: `scripts/jev-eval.py`, `scripts/jev-eval-live.py`,
`scripts/router_attachment/run_eval.py`.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"
DEFAULT_MODEL = "sonnet"

_JSON_RE = re.compile(r"\{.*\}", re.S)

D_PROMPT = """You are executing the /d skill for the user request below. Its SKILL.md, /do's routing rules, and the routing
manifest are in your system prompt. Phase 1 step 1 already ran: JEV_RESULT is given. You cannot run tools and must not
execute the task. Apply Phase 1 step 2 exactly as SKILL.md instructs, then output ONLY the decision JSON object, with
these keys: {"agent": ..., "agents": [...], "skill": ..., "pipeline": ..., "complexity": ..., "confidence": ...,
"reasoning": ..., "fallback_reason": ...}. No prose, no code fences.

User request:
<request>
%s
</request>

JEV_RESULT:
%s
"""


def _load_jev_route():
    spec = importlib.util.spec_from_file_location("jev_route_for_eval", SCRIPTS / "jev-route.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS))
    spec.loader.exec_module(module)
    return module


def prepare(request: str, project: dict | None = None, timeout: float = 20.0) -> dict:
    """Run `jev-route.py` (prepare mode) for one request. Returns the JEV_RESULT dict."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(request)
        path = fh.name
    try:
        cmd = [sys.executable, str(SCRIPTS / "jev-route.py"), "--request-file", path, "--json-compact"]
        cmd += ["--timeout", str(timeout)]
        if project:
            cmd += ["--project-json", json.dumps(project)]
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO), timeout=timeout * 3 + 30, check=False)
        return json.loads(proc.stdout)
    finally:
        Path(path).unlink(missing_ok=True)


def route_rules() -> str:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / "print-route-rules.py")],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(REPO),
    ).stdout


def manifest_for(request: str) -> str:
    """The per-request routing manifest, as `get-routing-manifest.sh --request-file` prints it."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as fh:
        fh.write(request)
        path = fh.name
    try:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "routing-manifest.py"), "--request-file", path],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(REPO),
        ).stdout
    finally:
        Path(path).unlink(missing_ok=True)


def system_text(request: str) -> str:
    """What the session holds when it picks: /d's SKILL.md, /do's rule text, the manifest."""
    return (
        (REPO / "skills" / "meta" / "d" / "SKILL.md").read_text(encoding="utf-8")
        + "\n\n# /do routing rules (output of print-route-rules.py)\n\n"
        + route_rules()
        + "\n\n# Routing manifest (output of get-routing-manifest.sh)\n\n"
        + manifest_for(request)
    )


def system_file(request: str, scratch: Path) -> Path:
    """System prompt file named by content, so requests with one manifest share a prompt-cache prefix."""
    text = system_text(request)
    path = scratch / f"d-system-{hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]}.md"
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return path


def call_model(sys_file: Path, prompt: str, model: str, scratch: Path) -> tuple[dict | None, float, str, dict]:
    """One `claude -p` call. Returns (decision JSON or None, cost USD, raw text, usage)."""
    env = dict(os.environ)
    env.pop("CLAUDE_CODE_DISABLE_ADAPTIVE_THINKING", None)
    env.pop("CLAUDECODE", None)
    cmd = [
        "claude",
        "-p",
        "--model",
        model,
        "--tools",
        "",
        "--output-format",
        "json",
        "--exclude-dynamic-system-prompt-sections",
        "--append-system-prompt-file",
        str(sys_file),
    ]
    for attempt in range(3):
        proc = subprocess.run(
            cmd, input=prompt, capture_output=True, text=True, env=env, cwd=str(scratch), timeout=300, check=False
        )
        try:
            outer = json.loads(proc.stdout)
        except json.JSONDecodeError:
            time.sleep(5 * (attempt + 1))
            continue
        cost = float(outer.get("total_cost_usd") or 0.0)
        usage = outer.get("usage") or {}
        usage = {
            k: usage.get(k)
            for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
        }
        text = outer.get("result") or ""
        match = _JSON_RE.search(text)
        if match:
            try:
                return json.loads(match.group(0)), cost, text, usage
            except json.JSONDecodeError:
                pass
        return None, cost, text, usage
    return None, 0.0, "claude -p failed", {}


def finalize(prepared: dict, decision: dict | None) -> dict:
    """The production finalize step, called in-process."""
    module = _load_jev_route()
    return module.finalize(prepared, decision or {}, module._load_manifest_entries())


def pick_route(
    request: str,
    project: dict | None = None,
    model: str = DEFAULT_MODEL,
    scratch: Path | None = None,
    prepared: dict | None = None,
) -> dict:
    """prepare -> session-model pick -> finalize for one request.

    Returns the finalized route plus `prepared`, `decision`, `cost_usd`, and `usage`. A model reply that is not
    JSON yields an empty decision, so finalize still fills the skill and the agent.
    """
    scratch = scratch or Path(tempfile.gettempdir()) / "d-route-eval"
    scratch.mkdir(parents=True, exist_ok=True)
    prepared = prepared if prepared is not None else prepare(request, project)
    decision, cost, text, usage = call_model(
        system_file(request, scratch), D_PROMPT % (request, json.dumps(prepared)), model, scratch
    )
    route = finalize(prepared, decision)
    route.update(
        {
            "prepared": prepared,
            "decision": decision,
            "cost_usd": cost,
            "usage_model": usage,
            "decision_text": text[:2000] if decision is None else "",
        }
    )
    return route
