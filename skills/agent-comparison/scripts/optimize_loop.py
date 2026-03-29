#!/usr/bin/env python3
"""Autoresearch optimization loop for agent/skill files.

Wraps the existing agent-comparison evaluation infrastructure in an outer
loop that proposes variants, evaluates them, and keeps/reverts based on
score improvement. The keep/revert decision is arithmetic — no LLM
judgment in the loop itself.

Usage:
    python3 skills/agent-comparison/scripts/optimize_loop.py \
        --target agents/golang-general-engineer.md \
        --goal "improve error handling instructions" \
        --benchmark-tasks tasks.json \
        --max-iterations 20 \
        --min-gain 0.02

See ADR-131 for architecture details.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

QUALITY_WEIGHTS = {
    "correctness": 0.40,
    "error_handling": 0.20,
    "language_idioms": 0.15,
    "testing": 0.15,
    "efficiency": 0.10,
}

HARD_GATE_KEYS = ["parses", "compiles", "tests_pass", "protected_intact"]


def passes_hard_gates(scores: dict) -> bool:
    """Layer 1: Hard gates — score is 0 if any fail."""
    return all(scores.get(key, False) for key in HARD_GATE_KEYS)


def composite_score(scores: dict) -> float:
    """Layer 2: Weighted quality score, conditional on hard gates passing."""
    if not passes_hard_gates(scores):
        return 0.0
    total = 0.0
    for dim, weight in QUALITY_WEIGHTS.items():
        total += scores.get(dim, 0.0) * weight
    return round(total, 4)


def holdout_diverges(
    train_score: float,
    holdout_score: float,
    baseline_holdout: float,
    baseline_train: float = 0.0,
    threshold: float = 0.5,
) -> bool:
    """Goodhart alarm: held-out score drops while train has improved."""
    holdout_dropped = (baseline_holdout - holdout_score) > threshold
    train_improved = train_score > baseline_train
    return holdout_dropped and train_improved


# ---------------------------------------------------------------------------
# Iteration snapshot
# ---------------------------------------------------------------------------


def save_iteration(
    output_dir: Path,
    iteration: int,
    variant_content: str,
    scores: dict,
    verdict: str,
    reasoning: str,
    diff_text: str,
    change_summary: str,
    stop_reason: str | None = None,
    deletions: list[str] | None = None,
    deletion_justification: str = "",
) -> dict:
    """Save a full iteration snapshot and return its metadata."""
    iter_dir = output_dir / f"{iteration:03d}"
    iter_dir.mkdir(parents=True, exist_ok=True)

    (iter_dir / "variant.md").write_text(variant_content)
    (iter_dir / "scores.json").write_text(json.dumps(scores, indent=2))

    verdict_data = {
        "iteration": iteration,
        "verdict": verdict,
        "composite_score": composite_score(scores),
        "change_summary": change_summary,
        "reasoning": reasoning,
        "stop_reason": stop_reason,
        "deletions": deletions or [],
        "deletion_justification": deletion_justification,
    }
    (iter_dir / "verdict.json").write_text(json.dumps(verdict_data, indent=2))

    if diff_text:
        (iter_dir / "diff.patch").write_text(diff_text)

    return verdict_data


# ---------------------------------------------------------------------------
# Diff generation
# ---------------------------------------------------------------------------


def generate_diff(original: str, variant: str, label: str = "target") -> str:
    """Generate a unified diff between two strings."""
    import difflib

    original_lines = original.splitlines(keepends=True)
    variant_lines = variant.splitlines(keepends=True)
    diff = difflib.unified_diff(
        original_lines,
        variant_lines,
        fromfile=f"a/{label}",
        tofile=f"b/{label}",
        lineterm="\n",
    )
    return "".join(diff)


def make_dry_run_variant(current_content: str, iteration: int) -> tuple[str, str, str]:
    """Generate a deterministic local variant for --dry-run mode."""
    marker = f"<!-- dry-run iteration {iteration} -->"
    if marker in current_content:
        marker = f"<!-- dry-run iteration {iteration}b -->"
    if current_content.endswith("\n"):
        variant = current_content + marker + "\n"
    else:
        variant = current_content + "\n" + marker + "\n"
    return variant, "Synthetic dry-run mutation", "dry-run synthetic variant"


# ---------------------------------------------------------------------------
# HTML report generation
# ---------------------------------------------------------------------------


def _build_report_data(
    target: str,
    goal: str,
    baseline_composite: float,
    baseline_holdout: float | None,
    train_size: int,
    test_size: int,
    iterations: list[dict],
    max_iterations: int,
    status: str,
    total_tokens: int,
) -> dict:
    """Build the data structure for HTML report generation."""
    return {
        "target": target,
        "goal": goal,
        "status": status,
        "baseline_score": {"train": baseline_composite, "test": baseline_holdout},
        "task_counts": {"train": train_size, "test": test_size},
        "max_iterations": max_iterations,
        "total_tokens": total_tokens,
        "iterations": iterations,
    }


def generate_optimization_report(data: dict, auto_refresh: bool = False) -> str:
    """Generate iteration history HTML report.

    The convergence chart is built client-side using safe DOM methods
    (createElementNS, setAttribute, textContent) — no innerHTML.
    All string data is escaped server-side via html.escape before
    embedding in the template.
    """
    import html as html_mod

    target = html_mod.escape(data.get("target", ""))
    goal = html_mod.escape(data.get("goal", ""))
    status = data.get("status", "RUNNING")
    iterations = data.get("iterations", [])
    baseline = data.get("baseline_score", {})
    task_counts = data.get("task_counts", {})

    refresh = '<meta http-equiv="refresh" content="10">' if auto_refresh else ""

    rows = ""
    for it in iterations:
        v = it["verdict"]
        vcls = {"KEEP": "keep", "REVERT": "revert", "STOP": "stop"}.get(v, "")
        sc = it["score"]
        train_score = sc.get("train")
        test_score = sc.get("test")
        score_str = f'{train_score:.2f}' if isinstance(train_score, (int, float)) else "?"
        if isinstance(test_score, (int, float)):
            score_str += f' / {test_score:.2f}'
        delta = str(it.get("delta", ""))
        dcls = "d-pos" if delta.startswith("+") and delta != "+0" else "d-neg" if delta.startswith("-") else "d-zero"
        summary = html_mod.escape(str(it.get("change_summary", ""))[:80])
        diff_esc = html_mod.escape(str(it.get("diff", "")))
        is_keep = v == "KEEP"
        n = it["number"]

        rows += f"""
        <tr class="iter-row" data-iteration="{n}">
          <td>{n}</td>
          <td><span class="verdict-{vcls}">{v}</span></td>
          <td>{score_str}</td>
          <td class="{dcls}">{delta}</td>
          <td>{summary}</td>
          <td><label><input type="checkbox" class="cherry-pick-cb" data-iteration="{n}" {"checked" if is_keep else ""} {"disabled" if not is_keep else ""}> Pick</label></td>
        </tr>
        <tr class="diff-row hidden" id="diff-{n}">
          <td colspan="6"><pre class="diff-block">{diff_esc}</pre></td>
        </tr>"""

    chart_json = json.dumps([
        {"x": it["number"], "train": it["score"].get("train", 0), "test": it["score"].get("test")}
        for it in iterations
    ])
    diffs_json = json.dumps({it["number"]: str(it.get("diff", "")) for it in iterations})

    bt = baseline.get("train", 0.0)
    best = max((it["score"].get("train", bt) for it in iterations), default=bt)
    kept = sum(1 for it in iterations if it["verdict"] == "KEEP")
    reverted = sum(1 for it in iterations if it["verdict"] == "REVERT")
    cur = len(iterations)
    mx = data.get("max_iterations", 20)
    scls = "running" if status == "RUNNING" else "done" if status in ("CONVERGED", "COMPLETE") else "alarm"
    score_label = f"Train tasks: {task_counts.get('train', 0)}"
    if task_counts.get("test"):
        score_label += f" | Held-out tasks: {task_counts['test']}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">{refresh}
<title>Optimization: {target}</title>
<style>
:root {{ --bg:#0a0c10;--surface:#111318;--surface-2:#161a22;--border:#222832;--text:#b8c4d4;--muted:#5c6a7e;--bright:#e8edf5;--accent:#4d8ef5;--green:#3dba6c;--green-dim:#0d2420;--red:#e05454;--red-dim:#2a1015;--yellow:#d4a830;--font-sans:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;--font-mono:'SF Mono','Cascadia Code','Fira Code',monospace;--radius:8px; }}
*,*::before,*::after {{ margin:0;padding:0;box-sizing:border-box; }}
body {{ font-family:var(--font-sans);background:var(--bg);color:var(--text);font-size:14px;padding:24px 32px; }}
h1 {{ font-size:18px;color:var(--bright);margin-bottom:4px; }}
.subtitle {{ color:var(--muted);font-size:13px;margin-bottom:20px; }}
.dashboard {{ background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin-bottom:20px;display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px; }}
.dash-item {{ display:flex;flex-direction:column;gap:2px; }}
.dash-label {{ font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:0.06em; }}
.dash-value {{ font-size:16px;font-weight:600;color:var(--bright);font-variant-numeric:tabular-nums; }}
.dash-value.running {{ color:var(--accent); }}
.dash-value.done {{ color:var(--green); }}
.dash-value.alarm {{ color:var(--red); }}
.chart-box {{ background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px;margin-bottom:20px; }}
table {{ width:100%;border-collapse:collapse;font-size:13px; }}
th,td {{ padding:8px 12px;text-align:left;border-bottom:1px solid var(--border); }}
th {{ color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:0.06em;background:var(--surface-2); }}
.iter-row {{ cursor:pointer;transition:background 0.1s; }}
.iter-row:hover {{ background:var(--surface-2); }}
.diff-row td {{ padding:0; }}
.diff-block {{ background:#080b0f;padding:12px;font-family:var(--font-mono);font-size:11px;max-height:400px;overflow:auto;white-space:pre;line-height:1.5;color:var(--muted); }}
.verdict-keep {{ color:var(--green);font-weight:600; }}
.verdict-revert {{ color:var(--red);font-weight:600; }}
.verdict-stop {{ color:var(--yellow);font-weight:600; }}
.d-pos {{ color:var(--green);font-weight:600; }}
.d-neg {{ color:var(--red);font-weight:600; }}
.d-zero {{ color:var(--muted); }}
.hidden {{ display:none; }}
.actions {{ margin-top:16px;display:flex;gap:10px; }}
.btn {{ padding:8px 18px;border-radius:var(--radius);border:1px solid var(--border);background:var(--surface-2);color:var(--text);cursor:pointer;font-size:13px;font-family:var(--font-sans); }}
.btn:hover {{ background:var(--surface);color:var(--bright); }}
.btn-primary {{ background:var(--accent);color:#fff;border:none; }}
.btn-primary:hover {{ background:#5a99f8; }}
</style>
</head>
<body>
<h1>Optimization: {target}</h1>
<p class="subtitle">Goal: {goal}</p>
<div class="dashboard">
  <div class="dash-item"><span class="dash-label">Status</span><span class="dash-value {scls}">{status}</span></div>
  <div class="dash-item"><span class="dash-label">Progress</span><span class="dash-value">{cur}/{mx}</span></div>
  <div class="dash-item"><span class="dash-label">Baseline</span><span class="dash-value">{bt:.2f}</span></div>
  <div class="dash-item"><span class="dash-label">Best</span><span class="dash-value">{best:.2f} ({best - bt:+.2f})</span></div>
  <div class="dash-item"><span class="dash-label">Kept</span><span class="dash-value">{kept}</span></div>
  <div class="dash-item"><span class="dash-label">Reverted</span><span class="dash-value">{reverted}</span></div>
</div>
<p class="subtitle">{score_label}</p>
<div class="chart-box" id="chart"></div>
<table>
<thead><tr><th>#</th><th>Verdict</th><th>Score</th><th>Delta</th><th>Change</th><th>Pick</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<div class="actions">
  <button class="btn btn-primary" id="btn-preview">Preview Combined</button>
  <button class="btn" id="btn-export">Export Selected</button>
</div>
<div id="preview-area" class="hidden" style="margin-top:16px">
  <h3 style="color:var(--bright);margin-bottom:8px">Combined Preview</h3>
  <pre class="diff-block" id="preview-content"></pre>
</div>
<script>
// Toggle diff rows
document.querySelectorAll('.iter-row').forEach(function(row) {{
  row.addEventListener('click', function(e) {{
    if (e.target.type === 'checkbox') return;
    document.getElementById('diff-' + row.dataset.iteration).classList.toggle('hidden');
  }});
}});

// Convergence chart — safe DOM construction only (no innerHTML)
var points = {chart_json};
var bscore = {bt};
var scoreCandidates = points.reduce(function(acc, point) {{
  if (point.train != null) acc.push(point.train);
  if (point.test != null) acc.push(point.test);
  return acc;
}}, [bscore]);

function drawChart() {{
  var box = document.getElementById('chart');
  if (!points.length) {{ box.textContent = 'No iterations yet'; return; }}
  var W = Math.min(box.clientWidth - 32, 800), H = 200;
  var pad = {{l:40, r:20, t:10, b:30}};
  var pW = W - pad.l - pad.r, pH = H - pad.t - pad.b;
  var xMax = Math.max.apply(null, points.map(function(p){{return p.x}}));
  if (xMax < 1) xMax = 1;
  var rawMax = Math.max.apply(null, scoreCandidates);
  var yMin = Math.max(0, Math.floor(Math.min.apply(null, scoreCandidates)) - 0.5);
  var yMax = Math.ceil(rawMax + 0.5);
  if (yMax <= yMin) yMax = yMin + 1;
  function sx(x) {{ return pad.l + (x / xMax) * pW; }}
  function sy(y) {{ return pad.t + pH - ((y - yMin) / (yMax - yMin)) * pH; }}
  var NS = 'http://www.w3.org/2000/svg';
  var svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('width', String(W));
  svg.setAttribute('height', String(H));
  svg.style.display = 'block';
  function line(x1,y1,x2,y2,s,w,d) {{
    var l = document.createElementNS(NS,'line');
    l.setAttribute('x1',x1);l.setAttribute('y1',y1);l.setAttribute('x2',x2);l.setAttribute('y2',y2);
    l.setAttribute('stroke',s);l.setAttribute('stroke-width',w);
    if(d)l.setAttribute('stroke-dasharray',d);
    svg.appendChild(l);
  }}
  function circ(cx,cy,r,f,s) {{
    var c = document.createElementNS(NS,'circle');
    c.setAttribute('cx',cx);c.setAttribute('cy',cy);c.setAttribute('r',r);
    c.setAttribute('fill',f||'none');if(s)c.setAttribute('stroke',s);
    svg.appendChild(c);
  }}
  function txt(x,y,t,f,sz,a) {{
    var e = document.createElementNS(NS,'text');
    e.setAttribute('x',x);e.setAttribute('y',y);e.setAttribute('fill',f);
    e.setAttribute('font-size',sz);if(a)e.setAttribute('text-anchor',a);
    e.textContent = t; svg.appendChild(e);
  }}
  function path(d,s,w,da) {{
    var p = document.createElementNS(NS,'path');
    p.setAttribute('d',d);p.setAttribute('fill','none');
    p.setAttribute('stroke',s);p.setAttribute('stroke-width',w);
    if(da)p.setAttribute('stroke-dasharray',da);
    svg.appendChild(p);
  }}
  for(var y=yMin;y<=yMax+0.001;y+=0.5){{line(pad.l,sy(y),W-pad.r,sy(y),'#222832',1);txt(pad.l-6,sy(y)+4,y.toFixed(1),'#5c6a7e',10,'end');}}
  line(pad.l,sy(bscore),W-pad.r,sy(bscore),'#d4a830',1,'4,4');
  var tp=points.filter(function(p){{return p.train!=null}});
  if(tp.length>1){{var d=tp.map(function(p,i){{return(i===0?'M':'L')+sx(p.x)+','+sy(p.train)}}).join(' ');path(d,'#4d8ef5',2);}}
  tp.forEach(function(p){{circ(sx(p.x),sy(p.train),3,'#4d8ef5');}});
  var hp=points.filter(function(p){{return p.test!=null}});
  if(hp.length>1){{var d2=hp.map(function(p,i){{return(i===0?'M':'L')+sx(p.x)+','+sy(p.test)}}).join(' ');path(d2,'#3dba6c',2,'6,3');}}
  hp.forEach(function(p){{circ(sx(p.x),sy(p.test),3,'none','#3dba6c');}});
  for(var x=1;x<=xMax;x++){{txt(sx(x),H-5,String(x),'#5c6a7e',10,'middle');}}
  txt(pad.l+10,pad.t+14,'Train','#4d8ef5',10);
  txt(pad.l+50,pad.t+14,'Held-out','#3dba6c',10);
  txt(pad.l+110,pad.t+14,'Baseline','#d4a830',10);
  box.replaceChildren(svg);
}}
drawChart();
window.addEventListener('resize', drawChart);

var iterDiffs = {diffs_json};
function getSelected(){{return Array.from(document.querySelectorAll('.cherry-pick-cb:checked')).map(function(cb){{return parseInt(cb.dataset.iteration)}});}}
document.getElementById('btn-preview').addEventListener('click',function(){{
  var sel=getSelected();if(!sel.length){{alert('No iterations selected');return;}}
  var combined=sel.map(function(n){{return'--- Iteration '+n+' ---\\n'+(iterDiffs[String(n)]||'(no diff)')}}).join('\\n\\n');
  document.getElementById('preview-content').textContent=combined;
  document.getElementById('preview-area').classList.remove('hidden');
}});
document.getElementById('btn-export').addEventListener('click',function(){{
  var sel=getSelected();if(!sel.length){{alert('No iterations selected');return;}}
  var out={{selected_iterations:sel,diffs:{{}}}};
  sel.forEach(function(n){{out.diffs[String(n)]=iterDiffs[String(n)]||''}});
  var blob=new Blob([JSON.stringify(out,null,2)],{{type:'application/json'}});
  var url=URL.createObjectURL(blob);
  var a=document.createElement('a');a.href=url;a.download='cherry-picked-iterations.json';a.click();
  URL.revokeObjectURL(url);
}});
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Task loading and splitting
# ---------------------------------------------------------------------------


def load_benchmark_tasks(path: Path) -> list[dict]:
    """Load benchmark tasks from JSON file."""
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if "tasks" in data:
        return data["tasks"]
    if "train" in data or "test" in data:
        tasks = []
        for split_name in ("train", "test"):
            for task in data.get(split_name, []):
                normalized = dict(task)
                normalized.setdefault("split", split_name)
                tasks.append(normalized)
        return tasks
    raise ValueError("Task file must be a list, {'tasks': [...]}, or {'train': [...], 'test': [...]}.")


def split_tasks(
    tasks: list[dict],
    train_split: float,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """Split tasks into train and test sets.

    Uses explicit 'split' field if present, otherwise random split
    stratified by complexity.
    """
    has_explicit = any("split" in t for t in tasks)
    if has_explicit:
        train = [t for t in tasks if t.get("split", "train") == "train"]
        test = [t for t in tasks if t.get("split") == "test"]
        return train, test

    rng = random.Random(seed)
    by_complexity: dict[str, list[dict]] = {}
    for t in tasks:
        by_complexity.setdefault(t.get("complexity", "medium"), []).append(t)

    train, test = [], []
    for group in by_complexity.values():
        rng.shuffle(group)
        n_train = max(1, int(len(group) * train_split))
        train.extend(group[:n_train])
        test.extend(group[n_train:])

    return train, test


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> tuple[bool, str]:
    """Parse YAML frontmatter, returning (valid, description)."""
    if not content.startswith("---"):
        return False, ""
    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        return False, ""

    description = ""
    fm_lines = lines[1:end_idx]
    idx = 0
    while idx < len(fm_lines):
        line = fm_lines[idx]
        if line.startswith("description:"):
            value = line[len("description:"):].strip()
            if value in (">", "|", ">-", "|-"):
                parts: list[str] = []
                idx += 1
                while idx < len(fm_lines) and (fm_lines[idx].startswith("  ") or fm_lines[idx].startswith("\t")):
                    parts.append(fm_lines[idx].strip())
                    idx += 1
                description = " ".join(parts)
                continue
            else:
                description = value.strip('"').strip("'")
        idx += 1
    return True, description


def _is_trigger_task(task: dict) -> bool:
    return "query" in task and "should_trigger" in task


def _is_pattern_task(task: dict) -> bool:
    return "prompt" in task and (
        "expected_patterns" in task or "forbidden_patterns" in task or "weight" in task
    )


def _validate_task_set(tasks: list[dict]) -> None:
    """Reject unsupported or mixed task formats early with a clear error."""
    if not tasks:
        raise ValueError("Task file is empty.")

    trigger_tasks = sum(1 for task in tasks if _is_trigger_task(task))
    pattern_tasks = sum(1 for task in tasks if _is_pattern_task(task))

    if trigger_tasks and pattern_tasks:
        raise ValueError("Task file mixes trigger-rate and pattern benchmark formats. Use one format per run.")

    if trigger_tasks == len(tasks):
        return

    if pattern_tasks == len(tasks):
        raise ValueError(
            "Pattern benchmark tasks are not supported by optimize_loop.py yet. "
            "Use trigger-rate tasks with 'query' and 'should_trigger' fields."
        )

    raise ValueError(
        "Unsupported task format. Expected trigger-rate tasks with 'query' and 'should_trigger' fields."
    )


# ---------------------------------------------------------------------------
# Trigger-rate evaluator (uses existing run_eval infrastructure)
# ---------------------------------------------------------------------------


def _run_trigger_rate(
    target_path: Path,
    description: str,
    tasks: list[dict],
    num_workers: int = 5,
    timeout: int = 30,
    verbose: bool = False,
) -> dict:
    """Run trigger-rate assessment using the skill_eval infrastructure.

    Tasks must have 'query' and 'should_trigger' fields.
    Returns run_eval-style results dict.
    """
    import os
    import tempfile

    task_file = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(tasks, f)
            task_file = f.name

        with tempfile.TemporaryDirectory() as skill_dir:
            skill_md = Path(skill_dir) / "SKILL.md"
            skill_md.write_text(target_path.read_text())

            project_root = Path.cwd()
            for parent in [project_root, *project_root.parents]:
                if (parent / ".claude").is_dir():
                    project_root = parent
                    break

            cmd = [
                sys.executable, "-m", "scripts.skill_eval.run_eval",
                "--eval-set", task_file,
                "--skill-path", skill_dir,
                "--description", description,
                "--num-workers", str(num_workers),
                "--timeout", str(timeout),
                "--runs-per-query", "1",
            ]
            if verbose:
                cmd.append("--verbose")
                print(f"Running trigger assessment: {len(tasks)} queries", file=sys.stderr)

            env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

            result = subprocess.run(
                cmd, capture_output=True, text=True,
                cwd=str(project_root), env=env, timeout=600,
            )

            if result.returncode != 0:
                if verbose:
                    print(f"Trigger assessment failed: {result.stderr[:300]}", file=sys.stderr)
                return {"results": [], "summary": {"total": 0, "passed": 0, "failed": 0}}

            return json.loads(result.stdout)
    finally:
        if task_file:
            Path(task_file).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Evaluation bridge
# ---------------------------------------------------------------------------


def assess_target(
    target_path: Path,
    tasks: list[dict],
    goal: str,
    verbose: bool = False,
    dry_run: bool = False,
) -> dict:
    """Assess a target file against tasks.

    Supports three modes:
    - Trigger-rate: tasks have 'query' + 'should_trigger' fields.
      Uses existing run_eval infrastructure via claude -p.
    - Dry-run: returns synthetic scores for testing loop mechanics.
    - Benchmark (NYI): tasks have 'prompt' + 'name' fields.

    Returns scores dict with hard gate booleans and quality dimensions.
    """
    scores: dict = {
        "parses": True,
        "compiles": True,
        "tests_pass": True,
        "protected_intact": True,
        "correctness": 0.0,
        "error_handling": 0.0,
        "language_idioms": 0.0,
        "testing": 0.0,
        "efficiency": 0.0,
        "task_results": [],
    }

    content = target_path.read_text()
    valid, description = _parse_frontmatter(content)
    if not valid or not description:
        scores["parses"] = False
        return scores

    # Dry-run mode: content-dependent synthetic scores for testing loop mechanics.
    # Hard gates always pass (the point is testing keep/revert logic).
    # Quality scores vary deterministically based on content hash so that
    # different variants produce different scores.
    if dry_run:
        import hashlib
        h = int(hashlib.sha256(content.encode()).hexdigest()[:8], 16)
        base = (h % 30 + 70) / 100.0  # 0.70-1.00 range — always decent
        scores["correctness"] = round(base * 10, 2)
        scores["error_handling"] = round(base * 8, 2)
        scores["language_idioms"] = round(base * 7, 2)
        scores["testing"] = round(base * 7, 2)
        scores["efficiency"] = round(base * 6, 2)
        scores["tests_pass"] = True  # always pass in dry-run
        for task in tasks:
            name = task.get("name", task.get("query", "unnamed"))[:40]
            scores["task_results"].append({
                "name": name, "passed": True,
                "score": base, "details": "dry-run",
            })
        return scores

    # Detect assessment mode from task format
    is_trigger = all(_is_trigger_task(task) for task in tasks)

    if is_trigger:
        results = _run_trigger_rate(target_path, description, tasks, verbose=verbose)
        summary = results.get("summary", {})
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        if total == 0:
            return scores

        accuracy = passed / total
        scores["correctness"] = round(accuracy * 10, 2)
        scores["error_handling"] = round(accuracy * 8, 2)
        scores["language_idioms"] = round(accuracy * 7, 2)
        scores["testing"] = round(accuracy * 8, 2)
        scores["efficiency"] = round(min(1.0, accuracy + 0.1) * 6, 2)
        scores["tests_pass"] = passed == total

        for r in results.get("results", []):
            scores["task_results"].append({
                "name": r.get("query", "unnamed")[:40],
                "passed": r.get("pass", False),
                "score": 1.0 if r.get("pass", False) else 0.0,
                "details": f"trigger_rate={r.get('trigger_rate', 0):.2f}",
            })
        return scores

    # Benchmark behavioral assessment — not yet implemented.
    # Use trigger-rate format (tasks with 'query' + 'should_trigger')
    # as the recommended starting point per ADR-131 research findings.
    raise NotImplementedError(
        "Pattern benchmark tasks are not yet implemented. "
        "Use trigger-rate tasks with 'query' and 'should_trigger' fields. "
        "See optimization-guide.md."
    )


# ---------------------------------------------------------------------------
# Protected section validation
# ---------------------------------------------------------------------------

_PROTECTED_RE = re.compile(
    r"<!--\s*DO NOT OPTIMIZE\s*-->(.*?)<!--\s*END DO NOT OPTIMIZE\s*-->",
    re.DOTALL,
)


def check_protected_sections(original: str, variant: str) -> bool:
    """Verify DO NOT OPTIMIZE sections are preserved verbatim."""
    orig = list(_PROTECTED_RE.finditer(original))
    var = list(_PROTECTED_RE.finditer(variant))
    if len(orig) != len(var):
        return False
    return all(orig_match.group(0) == var_match.group(0) for orig_match, var_match in zip(orig, var))


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------


def run_optimization_loop(
    target_path: Path,
    goal: str,
    benchmark_tasks_path: Path,
    max_iterations: int = 20,
    min_gain: float = 0.02,
    train_split: float = 0.6,
    model: str = "claude-sonnet-4-20250514",
    verbose: bool = False,
    report_path: Path | None = None,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> dict:
    """Run the autoresearch optimization loop."""
    if output_dir is None:
        output_dir = Path("evals/iterations")
    output_dir.mkdir(parents=True, exist_ok=True)

    all_tasks = load_benchmark_tasks(benchmark_tasks_path)
    _validate_task_set(all_tasks)
    train_tasks, test_tasks = split_tasks(all_tasks, train_split)

    if verbose:
        print(f"Tasks: {len(train_tasks)} train, {len(test_tasks)} test", file=sys.stderr)

    original_content = target_path.read_text()
    target_valid, target_description = _parse_frontmatter(original_content)
    if not target_valid or not target_description:
        raise ValueError(
            "Target must have YAML frontmatter with a non-empty description. "
            "optimize_loop.py currently supports frontmatter-description optimization only."
        )
    current_content = original_content
    target_label = target_path.name

    if verbose:
        print("Running baseline evaluation...", file=sys.stderr)

    baseline_scores = assess_target(target_path, train_tasks, goal, verbose, dry_run)
    baseline_composite = composite_score(baseline_scores)
    best_score = baseline_composite
    best_content = current_content
    best_iteration = 0

    baseline_holdout_scores = assess_target(target_path, test_tasks, goal, verbose, dry_run) if test_tasks else None
    baseline_holdout = composite_score(baseline_holdout_scores) if baseline_holdout_scores else None

    if verbose:
        holdout_display = f"{baseline_holdout:.4f}" if baseline_holdout is not None else "n/a"
        print(f"Baseline: train={baseline_composite:.4f}, holdout={holdout_display}", file=sys.stderr)

    iterations: list[dict] = []
    consecutive_reverts = 0
    exit_reason = "unknown"
    status = "RUNNING"
    total_tokens = 0

    for i in range(1, max_iterations + 1):
        if verbose:
            print(f"\n{'=' * 60}\nIteration {i}/{max_iterations} (best={best_score:.4f})", file=sys.stderr)

        # 1. Generate variant
        t0 = time.time()
        last_failures = []
        if iterations:
            last_scores_data = iterations[-1].get("scores", {})
            last_failures = [t for t in last_scores_data.get("task_results", []) if not t.get("passed")]
        history = [
            {
                "number": item["number"],
                "verdict": item["verdict"],
                "change_summary": item["change_summary"],
                "delta": item["delta"],
            }
            for item in iterations[-5:]
        ]

        if dry_run:
            variant_content, change_summary, reasoning = make_dry_run_variant(current_content, i)
            variant_output = {
                "variant": variant_content,
                "summary": change_summary,
                "reasoning": reasoning,
                "tokens_used": 0,
                "deletions": [],
                "deletion_justification": "",
            }
            deletions = []
            deletion_justification = ""
        else:
            with tempfile.NamedTemporaryFile(mode="w", suffix=target_path.suffix, encoding="utf-8") as current_file:
                current_file.write(current_content)
                current_file.flush()
                variant_result = subprocess.run(
                    [
                        sys.executable,
                        str(Path(__file__).parent / "generate_variant.py"),
                        "--target", str(target_path),
                        "--goal", goal,
                        "--current-content-file", current_file.name,
                        "--failures", json.dumps(last_failures),
                        "--history", json.dumps(history),
                        "--model", model,
                    ],
                    capture_output=True, text=True, timeout=120,
                )

            if variant_result.returncode != 0:
                if verbose:
                    print(f"Variant generation failed: {variant_result.stderr}", file=sys.stderr)
                consecutive_reverts += 1
                iterations.append({
                    "number": i, "verdict": "REVERT",
                    "score": {"train": best_score},
                    "delta": "0", "change_summary": "Variant generation failed",
                    "reasoning": variant_result.stderr[:200], "diff": "",
                })
                if consecutive_reverts >= 5:
                    exit_reason = f"converged (5 consecutive reverts at iteration {i})"
                    status = "CONVERGED"
                    break
                continue

            try:
                variant_output = json.loads(variant_result.stdout)
                variant_content = variant_output["variant"]
                change_summary = variant_output.get("summary", "")
                reasoning = variant_output.get("reasoning", "")
                total_tokens += variant_output.get("tokens_used", 0)
                deletions = variant_output.get("deletions", [])
                deletion_justification = variant_output.get("deletion_justification", "").strip()
            except (json.JSONDecodeError, KeyError) as e:
                if verbose:
                    print(f"Parse error: {e}", file=sys.stderr)
                consecutive_reverts += 1
                iterations.append({
                    "number": i, "verdict": "REVERT",
                    "score": {"train": best_score},
                    "delta": "0", "change_summary": f"Parse error: {e}",
                    "reasoning": "", "diff": "",
                })
                if consecutive_reverts >= 5:
                    exit_reason = f"converged (5 consecutive reverts at iteration {i})"
                    status = "CONVERGED"
                    break
                continue

        gen_elapsed = time.time() - t0

        # 2. Validate protected sections
        if not check_protected_sections(original_content, variant_content):
            if verbose:
                print("REJECTED: Protected sections modified", file=sys.stderr)
            diff_text = generate_diff(current_content, variant_content, target_label)
            save_iteration(output_dir, i, variant_content, {"protected_intact": False},
                           "REVERT", "Protected sections modified", diff_text, change_summary)
            iterations.append({
                "number": i, "verdict": "REVERT",
                "score": {"train": 0.0},
                "delta": "0", "change_summary": "Protected sections modified",
                "reasoning": reasoning, "diff": diff_text,
            })
            consecutive_reverts += 1
            if consecutive_reverts >= 5:
                exit_reason = f"converged (5 consecutive reverts at iteration {i})"
                status = "CONVERGED"
                break
            continue

        if deletions and not deletion_justification:
            if verbose:
                print(f"REJECTED: Deleted sections without justification: {deletions}", file=sys.stderr)
            diff_text = generate_diff(current_content, variant_content, target_label)
            save_iteration(
                output_dir,
                i,
                variant_content,
                {"protected_intact": True},
                "REVERT",
                "Deleted sections without justification",
                diff_text,
                change_summary,
                deletions=deletions,
            )
            iterations.append({
                "number": i,
                "verdict": "REVERT",
                "score": {"train": best_score},
                "delta": "0",
                "change_summary": "Deleted sections without justification",
                "reasoning": reasoning,
                "diff": diff_text,
                "deletions": deletions,
                "deletion_justification": "",
            })
            consecutive_reverts += 1
            if consecutive_reverts >= 5:
                exit_reason = f"converged (5 consecutive reverts at iteration {i})"
                status = "CONVERGED"
                break
            continue

        # 3. Evaluate variant
        temp_target = target_path.parent / f".{target_path.stem}_variant{target_path.suffix}"
        temp_target.write_text(variant_content)
        try:
            t0 = time.time()
            variant_scores = assess_target(temp_target, train_tasks, goal, verbose, dry_run)
            eval_elapsed = time.time() - t0
            variant_composite = composite_score(variant_scores)
        finally:
            temp_target.unlink(missing_ok=True)

        diff_text = generate_diff(current_content, variant_content, target_label)

        if verbose:
            print(f"Score: {variant_composite:.4f} (gain={variant_composite - best_score:.4f}, gen={gen_elapsed:.1f}s, eval={eval_elapsed:.1f}s)", file=sys.stderr)

        # 4. Keep/revert (deterministic arithmetic)
        gain = variant_composite - best_score
        if gain > min_gain:
            verdict = "KEEP"
            best_score = variant_composite
            best_content = variant_content
            best_iteration = i
            current_content = variant_content
            consecutive_reverts = 0
            delta_str = f"+{gain:.2f}"
        else:
            verdict = "REVERT"
            consecutive_reverts += 1
            delta_str = f"{gain:+.2f}" if gain != 0 else "0"

        if deletions and deletion_justification:
            change_summary = f"{change_summary} [deletion justified]"

        save_iteration(output_dir, i, variant_content, variant_scores,
                       verdict, reasoning, diff_text, change_summary,
                       deletions=deletions, deletion_justification=deletion_justification)

        iteration_data: dict = {
            "number": i, "verdict": verdict,
            "score": {"train": variant_composite, "test": None},
            "delta": delta_str, "change_summary": change_summary,
            "reasoning": reasoning, "diff": diff_text,
            "tokens_used": variant_output.get("tokens_used", 0),
            "scores": variant_scores,
            "deletions": deletions,
            "deletion_justification": deletion_justification,
        }

        # 5. Goodhart alarm — every 5 iterations, check held-out set
        if test_tasks and i % 5 == 0:
            try:
                temp_target.write_text(best_content)
                holdout_scores = assess_target(temp_target, test_tasks, goal, verbose, dry_run)
                holdout_composite = composite_score(holdout_scores)
                iteration_data["score"]["test"] = holdout_composite
            finally:
                temp_target.unlink(missing_ok=True)

            if holdout_diverges(best_score, holdout_composite, baseline_holdout, baseline_composite):
                if verbose:
                    print(f"GOODHART ALARM: holdout={holdout_composite:.4f} vs baseline={baseline_holdout:.4f}", file=sys.stderr)
                exit_reason = f"goodhart_alarm (iteration {i})"
                status = "GOODHART_ALARM"
                iterations.append(iteration_data)
                break

        iterations.append(iteration_data)

        # 6. Convergence check
        if consecutive_reverts >= 5:
            exit_reason = f"converged (5 consecutive reverts at iteration {i})"
            status = "CONVERGED"
            break

        # Regenerate live report
        if report_path:
            rd = _build_report_data(target_label, goal, baseline_composite, baseline_holdout,
                                    len(train_tasks), len(test_tasks), iterations, max_iterations,
                                    status, total_tokens)
            report_path.write_text(generate_optimization_report(rd, auto_refresh=True))

    else:
        exit_reason = f"max_iterations ({max_iterations})"
        status = "COMPLETE"

    # Final report
    if report_path:
        rd = _build_report_data(target_label, goal, baseline_composite, baseline_holdout,
                                len(train_tasks), len(test_tasks), iterations, max_iterations,
                                status, total_tokens)
        report_path.write_text(generate_optimization_report(rd, auto_refresh=False))

    if best_iteration > 0:
        best_path = output_dir / "best_variant.md"
        best_path.write_text(best_content)
        if verbose:
            print(f"\nBest variant saved to: {best_path}", file=sys.stderr)

    result = {
        "exit_reason": exit_reason, "status": status,
        "target": str(target_path), "goal": goal,
        "baseline_score": {"train": baseline_composite, "test": baseline_holdout},
        "baseline_train_score": baseline_composite,
        "baseline_holdout_score": baseline_holdout,
        "best_score": best_score,
        "best_iteration": best_iteration, "iterations_run": len(iterations),
        "max_iterations": max_iterations,
        "improvements_found": sum(1 for it in iterations if it["verdict"] == "KEEP"),
        "total_tokens": total_tokens,
        "train_size": len(train_tasks), "test_size": len(test_tasks),
        "iterations": iterations,
    }
    (output_dir / "results.json").write_text(json.dumps(result, indent=2))
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(description="Autoresearch optimization loop for agent/skill files")
    parser.add_argument("--target", required=True, help="Path to agent/skill file to optimize")
    parser.add_argument("--goal", required=True, help="Optimization objective")
    parser.add_argument("--benchmark-tasks", required=True, help="Path to benchmark tasks JSON")
    parser.add_argument("--max-iterations", type=int, default=20, help="Max iterations (default: 20)")
    parser.add_argument("--min-gain", type=float, default=0.02, help="Min score gain to keep (default: 0.02)")
    parser.add_argument("--train-split", type=float, default=0.6, help="Train fraction (default: 0.6)")
    parser.add_argument("--model", required=True, help="Model for variant generation")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    parser.add_argument("--dry-run", action="store_true", help="Use synthetic scores (test loop mechanics without API)")
    parser.add_argument("--report", default=None, help="Path for live HTML report")
    parser.add_argument("--output-dir", default=None, help="Directory for iteration snapshots")
    args = parser.parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"Error: Target not found: {target}", file=sys.stderr)
        sys.exit(1)

    tasks_path = Path(args.benchmark_tasks)
    if not tasks_path.exists():
        print(f"Error: Tasks not found: {tasks_path}", file=sys.stderr)
        sys.exit(1)

    try:
        result = run_optimization_loop(
            target_path=target, goal=args.goal,
            benchmark_tasks_path=tasks_path,
            max_iterations=args.max_iterations, min_gain=args.min_gain,
            train_split=args.train_split, model=args.model,
            verbose=args.verbose,
            report_path=Path(args.report) if args.report else None,
            output_dir=Path(args.output_dir) if args.output_dir else None,
            dry_run=args.dry_run,
        )
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, indent=2))
    if args.verbose:
        print(f"\nExit: {result['exit_reason']}", file=sys.stderr)
        print(f"Best: {result['best_score']:.4f} (iteration {result['best_iteration']})", file=sys.stderr)
        print(f"Improvements: {result['improvements_found']}/{result['iterations_run']}", file=sys.stderr)


if __name__ == "__main__":
    main()
