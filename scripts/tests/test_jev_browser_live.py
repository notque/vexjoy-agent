"""Live integration tests for the Jev browser driver against a loopback fixture.

Needs Node 22+ and a local Chromium; skipped otherwise. No Jev calls: the
agent loop runs with a scripted decider so the tests cover the driver,
snapshot, freshness guards, masking, and secret scrubbing end to end.
"""

from __future__ import annotations

import http.server
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
DRIVER = SCRIPTS / "lib" / "jev_browser" / "cdp_driver.mjs"

FIXTURE = """<!doctype html><title>Fixture</title><h1>Sign in</h1>
<form onsubmit="event.preventDefault();document.getElementById('msg').textContent='Welcome '+document.getElementById('u').value;">
<label for="u">Username</label><input id="u" name="username">
<label for="p">Password</label><input id="p" type="password" name="password">
<label for="c">Country</label><select id="c"><option value="us">USA</option><option value="ca">Canada</option></select>
<label><input type="checkbox" id="k"> Remember</label>
<button type="submit">Sign in</button></form><p id="msg"></p>
<button id="covered" style="position:absolute;top:300px;left:10px">Covered</button>
<div style="position:absolute;top:290px;left:0;width:200px;height:40px;background:#ccc"></div>
<script>setInterval(() => { document.title = 'reg:' + typeof window.__jevBrowser; }, 30);</script>
<div style="height:2000px"></div>
"""


def _have_chrome() -> bool:
    if not shutil.which("node"):
        return False
    if os.environ.get("CHROME_PATH") and Path(os.environ["CHROME_PATH"]).exists():
        return True
    cache = Path.home() / ".cache" / "ms-playwright"
    return cache.exists() and any(cache.glob("chromium-*/chrome-linux*/chrome"))


pytestmark = pytest.mark.skipif(not _have_chrome(), reason="node + local Chromium required")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    root = tmp_path_factory.mktemp("site")
    (root / "index.html").write_text(FIXTURE)
    handler = lambda *a, **k: _Quiet(*a, directory=str(root), **k)  # noqa: E731
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/"
    srv.shutdown()


class Drv:
    def __init__(self):
        self.p = subprocess.Popen(["node", str(DRIVER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.ready = self._read()

    def _read(self):
        return json.loads(self.p.stdout.readline())

    def call(self, cmd, **kw):
        self.p.stdin.write(json.dumps({"cmd": cmd, **kw}) + "\n")
        self.p.stdin.flush()
        return self._read()

    def close(self):
        try:
            self.call("close")
        finally:
            self.p.wait(timeout=10)


@pytest.fixture
def drv(site):
    d = Drv()
    assert d.ready["ok"], d.ready
    assert d.call("open", url=site)["ok"]
    yield d
    d.close()


def _el(snap, label):
    # Prefer actionable elements: the fixture has a heading and a button both labeled "Sign in".
    matches = [e for e in snap["elements"] if e["label"] == label]
    return next((e for e in matches if e["operations"]), matches[0])


def test_observe_contract_and_password_masking(drv):
    snap = drv.call("observe")["result"]
    labels = {e["label"] for e in snap["elements"]}
    assert {"Username", "Password", "Country", "Remember", "Sign in"} <= labels
    pw = _el(snap, "Password")
    assert "TYPE_TEXT" in pw["operations"]
    fill = next(a for a in snap["actions"] if a["kind"] == "fill" and a["node"] == pw["node"])
    assert drv.call("act", action=fill, page=snap, text="hunter2")["ok"]
    snap2 = drv.call("observe")["result"]
    assert _el(snap2, "Password")["value"] == "(filled)"
    assert "hunter2" not in json.dumps(snap2)


def test_registry_lives_in_isolated_world(drv):
    # The fixture's own script keeps writing typeof window.__jevBrowser into
    # the title. After observe() installs the registry it must stay invisible
    # to page-world code, and node ids must stay stable across observes.
    a = drv.call("observe")["result"]
    drv.call("act", action=next(x for x in a["actions"] if x["id"] == "wait"), page=a)
    b = drv.call("observe")["result"]
    assert b["title"] == "reg:undefined"
    assert _el(a, "Username")["node"] == _el(b, "Username")["node"]


def test_covered_target_is_rejected(drv):
    snap = drv.call("observe")["result"]
    covered = next((e for e in snap["elements"] if e["label"] == "Covered"), None)
    if covered is None:
        pytest.skip("covered button not in viewport list")
    click = next(a for a in snap["actions"] if a["kind"] == "click" and a["node"] == covered["node"])
    r = drv.call("act", action=click, page=snap)
    assert r["ok"] is False and r["stale"] is True and "covered" in r["error"]


def test_stale_guard_blocks_action_after_change(drv):
    snap = drv.call("observe")["result"]
    user = _el(snap, "Username")
    fill = next(a for a in snap["actions"] if a["kind"] == "fill" and a["node"] == user["node"])
    assert drv.call("act", action=fill, page=snap, text="alice")["ok"]
    # Same decision replayed against the old snapshot: guard (value changed) must reject.
    r = drv.call("act", action=fill, page=snap, text="bob")
    assert r["ok"] is False and r["stale"] is True
    fresh = drv.call("observe")["result"]
    assert _el(fresh, "Username")["value"] == "alice"


def test_select_checkbox_scroll_and_submit(drv):
    snap = drv.call("observe")["result"]
    sel = next(a for a in snap["actions"] if a["id"].endswith(":sel:ca"))
    assert drv.call("act", action=sel, page=snap)["ok"]
    snap = drv.call("observe")["result"]
    assert _el(snap, "Country")["value"] == "Canada"
    box = _el(snap, "Remember")
    assert drv.call(
        "act", action=next(a for a in snap["actions"] if a["kind"] == "click" and a["node"] == box["node"]), page=snap
    )["ok"]
    snap = drv.call("observe")["result"]
    assert _el(snap, "Remember")["checked"] is True
    assert drv.call("act", action=next(a for a in snap["actions"] if a["id"] == "scroll_down"), page=snap)["ok"]
    snap = drv.call("observe")["result"]
    assert snap["scroll"]["y"] > 0
    assert drv.call("act", action=next(a for a in snap["actions"] if a["id"] == "scroll_up"), page=snap)["ok"]
    snap = drv.call("observe")["result"]
    btn = _el(snap, "Sign in")
    assert drv.call(
        "act", action=next(a for a in snap["actions"] if a["kind"] == "click" and a["node"] == btn["node"]), page=snap
    )["ok"]
    snap = drv.call("observe")["result"]
    assert "Welcome" in snap["text"]


def test_agent_loop_scrubs_secret_from_snapshots(site):
    spec = importlib.util.spec_from_file_location("agent", SCRIPTS / "jev-browser-agent.py")
    agent = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent)
    seen: list[dict] = []
    plan = iter([("TYPE_TEXT", "Username"), ("CLICK", "Sign in"), ("DONE", None)])

    def decide(req):
        seen.append(req)
        op, label = next(plan)
        target = next((e["index"] for e in req["elements"] if e["label"] == label and e["operations"]), None)
        return {"operation": op, "target": target, "confidence": 0.9, "needs_text": op == "TYPE_TEXT", "source": "test"}

    r = agent.run(
        site,
        "log in",
        decide_fn=decide,
        # The verifier sees the scrubbed page, never the secret.
        verify_fn=lambda req: {"goal_met": "welcome (secret)" in req["page"]["text"].lower(), "source": "test"},
        secrets={"username": "s3cr3t"},
    )
    assert r["status"] == "done", r
    assert "s3cr3t" not in json.dumps(r)
    assert "s3cr3t" not in json.dumps(seen[1:])  # after typing, every snapshot is scrubbed
    assert "(secret)" in seen[-1]["page"]["text"]
