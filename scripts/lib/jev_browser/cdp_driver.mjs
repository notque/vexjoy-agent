#!/usr/bin/env node
// Zero-dependency Chromium driver for the Jev browser harness.
//
// Launches a local Chromium (Playwright cache or CHROME_PATH), speaks the
// Chrome DevTools Protocol over Node's built-in WebSocket, and serves a
// JSON-lines command protocol on stdin/stdout so a Python loop can drive it.
//
// Commands (one JSON object per line on stdin):
//   {"cmd":"open","url":"https://...","headers":{},"header_hosts":[]}
//                                                create a tab, navigate, wait for load;
//                                                headers go only to the home host (+ header_hosts)
//   {"cmd":"observe"}                            run snapshot.js -> page state (+ `dialog` when one was auto-dismissed)
//   {"cmd":"fresh","page":<snapshot>,"action":<action|null>}
//                                                semantic freshness check -> {fresh:bool}
//   {"cmd":"act","action":<action>,"text":"..."} execute one observed action
//   {"cmd":"navigate","url":"https://..."}
//   {"cmd":"screenshot"}                          -> {data: base64 jpeg}
//   {"cmd":"close"}
//
// Replies (one JSON object per line on stdout):
//   {"ok":true,"result":...} | {"ok":false,"error":"...","stale":bool}
//
// Model output never becomes selectors, coordinates, or JavaScript. Every
// executable action carries a code-owned integer node id issued by snapshot.js.

import { spawn } from "node:child_process";
import { existsSync, readdirSync, readFileSync, mkdtempSync, rmSync } from "node:fs";
import { createInterface } from "node:readline";
import { tmpdir, homedir } from "node:os";
import { join } from "node:path";

const SNAPSHOT_JS = readFileSync(new URL("./snapshot.js", import.meta.url), "utf8");
const VIEWPORT = { width: 1280, height: 800 };
const NAV_TIMEOUT_MS = 20000;
const SETTLE_MS = 50;
const COMBOBOX_SETTLE_MS = 200;
const WAIT_MS = 1500;          // explicit WAIT: minimum pause (animations, reels, spinners)
const QUIET_MS = 600;          // no DOM mutations for this long = page is quiet
const QUIET_MAX_MS = 3000;     // observe never waits longer than this for quiet
const WAIT_QUIET_MAX_MS = 8000; // explicit WAIT may settle much longer

class StalePage extends Error {}

// ---------------------------------------------------------------------------
// Chromium discovery and launch
// ---------------------------------------------------------------------------

function findChrome() {
  if (process.env.CHROME_PATH && existsSync(process.env.CHROME_PATH)) return process.env.CHROME_PATH;
  const cache = join(homedir(), ".cache", "ms-playwright");
  if (existsSync(cache)) {
    const dirs = readdirSync(cache)
      .filter((d) => /^chromium(_headless_shell)?-\d+$/.test(d))
      .sort((a, b) => Number(b.match(/\d+$/)[0]) - Number(a.match(/\d+$/)[0]));
    for (const d of dirs) {
      for (const rel of ["chrome-linux64/chrome", "chrome-linux/chrome", "chrome-headless-shell-linux64/chrome-headless-shell"]) {
        const p = join(cache, d, rel);
        if (existsSync(p)) return p;
      }
    }
  }
  for (const p of ["/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome", "/opt/google/chrome/chrome"]) {
    if (existsSync(p)) return p;
  }
  throw new Error("No Chromium found. Set CHROME_PATH or install Playwright browsers.");
}

function launchOnce(headless, noSandbox) {
  const bin = findChrome();
  const profile = mkdtempSync(join(tmpdir(), "jev-browser-"));
  const args = [
    "--remote-debugging-port=0",
    `--user-data-dir=${profile}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-background-timer-throttling",
    "--disable-renderer-backgrounding",
    "--disable-features=TranslateUI",
    "--disable-extensions",
    `--window-size=${VIEWPORT.width},${VIEWPORT.height}`,
    "about:blank",
  ];
  if (headless) args.unshift("--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio");
  if (noSandbox) args.unshift("--no-sandbox");
  const proc = spawn(bin, args, { stdio: ["ignore", "ignore", "pipe"] });
  return new Promise((resolve, reject) => {
    let buf = "";
    const timer = setTimeout(() => {
      // Nothing owns this process yet: kill it and drop the profile so a hung
      // Chromium does not outlive the driver.
      try { proc.kill("SIGKILL"); } catch {}
      try { rmSync(profile, { recursive: true, force: true }); } catch {}
      reject(new Error("Chromium did not expose DevTools in time"));
    }, 15000);
    proc.stderr.on("data", (chunk) => {
      buf += chunk.toString();
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) {
        clearTimeout(timer);
        proc.stderr.removeAllListeners("data");
        proc.stderr.resume();
        resolve({ proc, wsUrl: m[1], profile });
      }
    });
    proc.on("exit", (code) => {
      clearTimeout(timer);
      const err = new Error(`Chromium exited early (${code}): ${buf.slice(-400)}`);
      err.noSandboxNeeded = /No usable sandbox/i.test(buf);
      reject(err);
    });
  });
}

// Try the sandboxed launch first. Hosts with unprivileged user namespaces
// disabled (Ubuntu 23.10+ AppArmor) report "No usable sandbox"; only then
// fall back to --no-sandbox. JEV_BROWSER_SANDBOX=1 forbids the fallback.
async function launch(headless = true) {
  try {
    return { ...(await launchOnce(headless, false)), sandbox: true };
  } catch (e) {
    if (!e.noSandboxNeeded || process.env.JEV_BROWSER_SANDBOX === "1") throw e;
    return { ...(await launchOnce(headless, true)), sandbox: false };
  }
}

// ---------------------------------------------------------------------------
// CDP connection
// ---------------------------------------------------------------------------

class CDP {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.pending = new Map();
    this.nextId = 1;
    this.events = [];
    this.ready = new Promise((res, rej) => {
      this.ws.addEventListener("open", res, { once: true });
      this.ws.addEventListener("error", (e) => rej(new Error(`WebSocket error: ${e.message || e}`)), { once: true });
    });
    this.closed = false;
    this.ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(`${msg.error.message}${msg.error.data ? ": " + msg.error.data : ""}`));
        else resolve(msg.result ?? {});
      } else if (msg.method) {
        for (const l of [...this.events]) l(msg);
      }
    });
    // A closed socket never answers: every in-flight command would hang the
    // JSON-lines loop forever. Reject them all so the caller sees a reply.
    this.ws.addEventListener("close", (ev) => this.rejectAll(`WebSocket closed (${ev.code || 0})`), { once: true });
  }
  rejectAll(reason) {
    this.closed = true;
    const pending = [...this.pending.values()];
    this.pending.clear();
    for (const { reject } of pending) reject(new Error(reason));
  }
  send(method, params = {}, sessionId) {
    if (this.closed) return Promise.reject(new Error("WebSocket closed"));
    const id = this.nextId++;
    const body = { id, method, params };
    if (sessionId) body.sessionId = sessionId;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      try { this.ws.send(JSON.stringify(body)); } catch (e) { this.pending.delete(id); reject(e); }
    });
  }
  on(listener) {
    this.events.push(listener);
  }
  off(listener) {
    const i = this.events.indexOf(listener);
    if (i >= 0) this.events.splice(i, 1);
  }
  close() {
    try { this.ws.close(); } catch {}
    this.rejectAll("WebSocket closed by driver");
  }
}

// ---------------------------------------------------------------------------
// Tab
// ---------------------------------------------------------------------------

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class Tab {
  constructor(cdp, sessionId, targetId) {
    this.cdp = cdp;
    this.session = sessionId;
    this.target = targetId;
    this.afterInput = null;
    this.loading = false;
    this.dialogs = [];        // auto-dismissed JS dialogs since the last observe
    this.extraHeaders = null; // [{name, value}] sent only to headerHosts
    this.headerHosts = new Set();
    this.listener = (msg) => {
      if (msg.sessionId !== this.session) return;
      if (msg.method === "Page.frameStartedLoading") this.loading = true;
      if (msg.method === "Runtime.executionContextsCleared" || msg.method === "Page.frameNavigated") this.contextId = null;
      if (msg.method === "Page.loadEventFired" || msg.method === "Page.frameStoppedLoading") this.loading = false;
      if (msg.method === "Page.javascriptDialogOpening") this.onDialog(msg.params || {});
      if (msg.method === "Fetch.requestPaused") this.onRequestPaused(msg.params || {});
    };
    cdp.on(this.listener);
  }
  call(method, params) {
    return this.cdp.send(method, params, this.session);
  }
  close() {
    this.cdp.off(this.listener);
  }
  onDialog(p) {
    // A page alert/confirm/prompt blocks every Runtime.evaluate until it is
    // handled. Dismiss it (never accept: no model output reaches a prompt)
    // and report it in the next observe so Jev knows the page said something.
    this.dialogs.push({ type: p.type || "unknown", message: String(p.message || "").slice(0, 500) });
    this.call("Page.handleJavaScriptDialog", { accept: false }).catch(() => {});
  }
  onRequestPaused(p) {
    // Header scoping: the caller's headers (e.g. a staging bypass token) go
    // only to the home host or an explicit allowlist, never to third parties.
    const params = { requestId: p.requestId };
    let host = "";
    try { host = new URL(p.request?.url || "").hostname.toLowerCase(); } catch {}
    if (this.extraHeaders && host && this.headerHosts.has(host)) {
      const existing = Object.entries(p.request?.headers || {}).map(([name, value]) => ({ name, value: String(value) }));
      const names = new Set(this.extraHeaders.map((h) => h.name.toLowerCase()));
      params.headers = [...existing.filter((h) => !names.has(h.name.toLowerCase())), ...this.extraHeaders];
    }
    this.call("Fetch.continueRequest", params).catch(() => {});
  }
  async scopeHeaders(headers, hosts) {
    this.extraHeaders = Object.entries(headers).map(([name, value]) => ({ name, value: String(value) }));
    this.headerHosts = new Set(hosts.map((h) => String(h).toLowerCase()).filter(Boolean));
    await this.call("Fetch.enable", { patterns: [{ urlPattern: "*" }] });
  }
  async context() {
    // Private execution context: the page's own scripts cannot see or
    // rewrite window.__jevBrowser. Recreated after every navigation.
    if (this.contextId) return this.contextId;
    const { frameTree } = await this.call("Page.getFrameTree");
    const { executionContextId } = await this.call("Page.createIsolatedWorld", {
      frameId: frameTree.frame.id, worldName: "jev-browser", grantUniveralAccess: false,
    });
    this.contextId = executionContextId;
    return executionContextId;
  }
  async evaluate(expression, { awaitPromise = false } = {}) {
    let r;
    for (let attempt = 0; attempt < 2; attempt++) {
      const contextId = await this.context();
      try {
        r = await this.call("Runtime.evaluate", { expression, contextId, returnByValue: true, awaitPromise });
        break;
      } catch (e) {
        this.contextId = null;
        const contextGone = /context|execution/i.test(String(e.message));
        if (!contextGone) throw e; // transport/protocol errors are not staleness
        if (attempt === 1) throw new StalePage("Document changed during evaluation");
      }
    }
    if (r.exceptionDetails) {
      const text = r.exceptionDetails.exception?.description || r.exceptionDetails.text || "evaluation failed";
      if (/context|destroyed|navigat/i.test(text)) throw new StalePage("Document changed during evaluation");
      throw new Error(text);
    }
    return r.result?.value;
  }
  async init() {
    await this.call("Page.enable");
    await this.call("Runtime.enable");
    await this.call("Emulation.setDeviceMetricsOverride", { ...VIEWPORT, deviceScaleFactor: 1, mobile: false });
    await this.call("Emulation.setFocusEmulationEnabled", { enabled: true });
  }
  async navigate(url) {
    const r = await this.call("Page.navigate", { url });
    // Chromium reports unreachable hosts, refused connections and TLS errors
    // here, not as an exception; the tab then shows an error page.
    if (r.errorText) throw new Error(`navigation failed: ${r.errorText}`);
    if (!(await this.waitForLoad())) throw new Error(`page did not finish loading within ${NAV_TIMEOUT_MS}ms`);
  }
  /** Resolves true when the document is complete, false on timeout. */
  async waitForLoad(timeout = NAV_TIMEOUT_MS) {
    const deadline = Date.now() + timeout;
    while (Date.now() < deadline) {
      try {
        const state = await this.evaluate("document.readyState");
        if (state === "complete" && !this.loading) return true;
      } catch (e) {
        if (!(e instanceof StalePage)) throw e;
      }
      await sleep(25);
    }
    return false;
  }
  async settle() {
    // After an interaction: at most two animation frames or SETTLE_MS; for a
    // combobox fill, wait for visible options up to COMBOBOX_SETTLE_MS.
    const action = this.afterInput;
    this.afterInput = null;
    if (!action) return;
    const combobox = action.kind === "fill" && action.role === "combobox";
    const budget = combobox ? COMBOBOX_SETTLE_MS : SETTLE_MS;
    try {
      await this.evaluate(
        `new Promise((resolve) => {
          const combobox = ${combobox};
          const field = window.__jevBrowser?.nodes.get(${Number(action.node) || 0});
          let frames = 0, done = false;
          const finish = () => { done = true; resolve(true); };
          setTimeout(finish, ${budget});
          const tick = () => {
            if (done) return;
            frames++;
            if (!combobox && frames >= 2) return finish();
            if (combobox) {
              const ids = (field?.getAttribute('aria-controls') || field?.getAttribute('aria-owns') || '').split(/\\s+/).filter(Boolean);
              const roots = ids.length ? ids.map((i) => document.getElementById(i)).filter(Boolean) : [document];
              const opts = roots.flatMap((r) => [...r.querySelectorAll('[role=option]')]);
              if (frames >= 2 && opts.some((o) => o.checkVisibility?.() && o.getBoundingClientRect().height)) return finish();
            }
            requestAnimationFrame(tick);
          };
          requestAnimationFrame(tick);
        })`,
        { awaitPromise: true }
      );
    } catch {
      // Navigation during settle is fine; observe() re-checks readiness.
    }
  }
  async quiet(maxMs = QUIET_MAX_MS) {
    // SPA data arrives after load. Wait for the DOM to stop mutating for
    // QUIET_MS, capped at maxMs, so Jev sees loaded content, not spinners.
    try {
      return await this.evaluate(
        `new Promise((resolve) => {
          const start = performance.now();
          let last = performance.now();
          const mo = new MutationObserver(() => { last = performance.now(); });
          mo.observe(document.documentElement, { childList: true, subtree: true, characterData: true, attributes: true });
          const tick = () => {
            const now = performance.now();
            if (now - last >= ${QUIET_MS}) { mo.disconnect(); return resolve({ quiet: true, ms: Math.round(now - start) }); }
            if (now - start >= ${maxMs}) { mo.disconnect(); return resolve({ quiet: false, ms: Math.round(now - start) }); }
            setTimeout(tick, 25);
          };
          tick();
        })`,
        { awaitPromise: true }
      );
    } catch {
      return { quiet: false, ms: 0 };
    }
  }
  async observe() {
    await this.settle();
    await this.waitForLoad(5000);
    const quiet = await this.quiet();
    for (let attempt = 0; attempt < 10; attempt++) {
      try {
        const snap = await this.evaluate(SNAPSHOT_JS);
        if (snap && typeof snap === "object") {
          const out = { ...snap, quiet };
          if (this.dialogs.length) { out.dialog = this.dialogs; this.dialogs = []; }
          return out;
        }
      } catch (e) {
        if (!(e instanceof StalePage) || attempt === 9) throw e;
      }
      await sleep(30);
    }
    throw new StalePage("Page did not settle");
  }
  async fresh(page, action) {
    // WAIT has no target: it is valid on any page, and the marker (which
    // embeds body text) changes on every animated page, so never gate it.
    if (action && action.kind === "wait") return true;
    if (action && (action.kind === "click" || action.kind === "select" || action.kind === "fill")) {
      const node = Number(action.node);
      if (!Number.isInteger(node)) return false;
      const cur = await this.evaluate(
        `(() => { const c = window.__jevBrowser; return c ? [c.pageKey(), c.guard(c.nodes.get(${node}))] : null; })()`
      );
      return Array.isArray(cur) && cur[0] === page.page_key && cur[1] === (page.guards?.[String(node)] ?? page.guards?.[node]);
    }
    const marker = await this.evaluate("window.__jevBrowser ? window.__jevBrowser.marker() : null");
    return marker === page.marker;
  }
  async act(action, text) {
    const kind = action.kind;
    if (kind === "wait") {
      // WAIT means "let the page finish": settle until the DOM is quiet,
      // bounded, so an endless animation cannot hang the loop.
      await sleep(WAIT_MS);
      const q = await this.quiet(WAIT_QUIET_MAX_MS);
      return { executed: action.id, quiet: q };
    }
    if (kind === "scroll") {
      await this.call("Input.dispatchMouseEvent", {
        type: "mouseWheel", x: VIEWPORT.width / 2, y: VIEWPORT.height / 2, deltaX: 0, deltaY: Number(action.delta) || 400,
      });
      this.afterInput = action;
      return { executed: action.id };
    }
    const node = Number(action.node);
    if (!Number.isInteger(node)) throw new Error("Invalid observed node");
    // Resolve current geometry from the code-owned node; reject covered,
    // hidden, disabled, or read-only controls. Never trust cached rects.
    const target = await this.evaluate(
      `((node, kind, value) => {
        const e = window.__jevBrowser?.nodes.get(node);
        if (!e?.isConnected) return { err: "gone" };
        if (e.matches(':disabled') || e.closest('[aria-disabled="true"],[inert]')) return { err: "disabled" };
        if (!e.checkVisibility?.({ checkOpacity: true, checkVisibilityCSS: true })) return { err: "hidden" };
        if (kind === 'fill' && (e.readOnly || e.getAttribute('aria-readonly') === 'true')) return { err: "readonly" };
        if (kind === 'select') {
          if (e.tagName !== 'SELECT') return { err: "not-select" };
          const opt = [...e.options].find((o) => o.value === value && !o.disabled);
          if (!opt) return { err: "no-option" };
          e.value = value;
          e.dispatchEvent(new Event('input', { bubbles: true }));
          e.dispatchEvent(new Event('change', { bubbles: true }));
          return { ok: true };
        }
        e.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        const r = e.getBoundingClientRect();
        const x = r.x + r.width / 2, y = r.y + r.height / 2;
        if (!r.width || !r.height || x < 0 || y < 0 || x >= innerWidth || y >= innerHeight) return { err: "offscreen" };
        const hit = document.elementFromPoint(x, y);
        if (!hit || !(e.contains(hit) || hit.contains(e) || (e.tagName === 'LABEL' && e.control === hit))) return { err: "covered" };
        return { x, y };
      })(${node}, ${JSON.stringify(kind)}, ${JSON.stringify(action.value ?? null)})`
    );
    if (!target || target.err) throw new StalePage(`Target ${target?.err || "unavailable"}. Observe again.`);
    if (kind === "select") {
      this.afterInput = action;
      return { executed: action.id };
    }
    const { x, y } = target;
    await this.call("Input.dispatchMouseEvent", { type: "mouseMoved", x, y });
    await this.call("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
    await this.call("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
    if (kind === "fill") {
      if (typeof text !== "string") throw new Error("fill requires text");
      const mod = process.platform === "darwin" ? 4 : 2;
      await this.call("Input.dispatchKeyEvent", { type: "keyDown", key: "a", code: "KeyA", modifiers: mod, commands: ["selectAll"] });
      await this.call("Input.dispatchKeyEvent", { type: "keyUp", key: "a", code: "KeyA", modifiers: mod });
      await this.call("Input.insertText", { text });
    }
    this.afterInput = action;
    return { executed: action.id };
  }
  async screenshot() {
    const r = await this.call("Page.captureScreenshot", { format: "jpeg", quality: 70 });
    return { data: r.data };
  }
}

// ---------------------------------------------------------------------------
// Command loop
// ---------------------------------------------------------------------------

async function main() {
  const headless = process.env.JEV_BROWSER_HEADLESS !== "0";
  const { proc, wsUrl, profile, sandbox } = await launch(headless);
  const cdp = new CDP(wsUrl);
  await cdp.ready;
  let tab = null;

  const reply = (obj) => process.stdout.write(JSON.stringify(obj) + "\n");
  const shutdown = () => {
    try { cdp.close(); } catch {}
    try { proc.kill("SIGTERM"); } catch {}
    try { rmSync(profile, { recursive: true, force: true }); } catch {}
  };
  process.on("exit", shutdown);
  process.on("SIGINT", () => process.exit(0));
  process.on("SIGTERM", () => process.exit(0));

  const openTab = async (url, headers, headerHosts) => {
    if (tab) {
      tab.close();
      try { await cdp.send("Target.closeTarget", { targetId: tab.target }); } catch {}
      tab = null;
    }
    const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
    const { sessionId } = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
    tab = new Tab(cdp, sessionId, targetId);
    await tab.init();
    if (headers && typeof headers === "object" && Object.keys(headers).length) {
      // e.g. a staging smoke-bypass token. Values come from the caller's
      // environment, are never echoed back, and reach only the home host
      // (plus header_hosts): a third-party script or redirect never sees them.
      let home = "";
      try { home = new URL(url).hostname.toLowerCase(); } catch {}
      const hosts = [home, ...(Array.isArray(headerHosts) ? headerHosts : [])];
      await tab.scopeHeaders(headers, hosts);
    }
    // navigate throws on errorText or load timeout; the command loop turns
    // that into {ok:false, error}. The tab stays open for a retry.
    await tab.navigate(url);
    return { url };
  };

  reply({ ok: true, result: { ready: true, chrome: findChrome(), headless, sandbox } });

  const rl = createInterface({ input: process.stdin });
  for await (const line of rl) {
    if (!line.trim()) continue;
    let req;
    try { req = JSON.parse(line); } catch { reply({ ok: false, error: "invalid JSON" }); continue; }
    try {
      switch (req.cmd) {
        case "open":
        case "navigate": {
          if (!req.url) throw new Error("url required");
          if (req.cmd === "open" || !tab) reply({ ok: true, result: await openTab(req.url, req.headers, req.header_hosts) });
          else { await tab.navigate(req.url); reply({ ok: true, result: { url: req.url } }); }
          break;
        }
        case "observe": {
          if (!tab) throw new Error("open a url first");
          reply({ ok: true, result: await tab.observe() });
          break;
        }
        case "fresh": {
          if (!tab) throw new Error("open a url first");
          reply({ ok: true, result: { fresh: await tab.fresh(req.page || {}, req.action || null) } });
          break;
        }
        case "act": {
          if (!tab) throw new Error("open a url first");
          if (!req.action || typeof req.action !== "object") throw new Error("action required");
          if (!(await tab.fresh(req.page || {}, req.action))) throw new StalePage("Page changed since this decision. Observe again.");
          reply({ ok: true, result: await tab.act(req.action, req.text) });
          break;
        }
        case "debug_eval": {
          // Development only. Never reachable unless JEV_BROWSER_DEBUG=1.
          if (process.env.JEV_BROWSER_DEBUG !== "1") throw new Error("debug_eval disabled");
          if (!tab) throw new Error("open a url first");
          reply({ ok: true, result: await tab.evaluate(String(req.expression), { awaitPromise: !!req.await }) });
          break;
        }
        case "screenshot": {
          if (!tab) throw new Error("open a url first");
          reply({ ok: true, result: await tab.screenshot() });
          break;
        }
        case "close": {
          reply({ ok: true, result: { closed: true } });
          process.exit(0);
          break;
        }
        default:
          reply({ ok: false, error: `unknown cmd ${req.cmd}` });
      }
    } catch (e) {
      reply({ ok: false, error: String(e.message || e), stale: e instanceof StalePage });
    }
  }
  process.exit(0);
}

main().catch((e) => {
  process.stdout.write(JSON.stringify({ ok: false, error: String(e.message || e), fatal: true }) + "\n");
  process.exit(1);
});
