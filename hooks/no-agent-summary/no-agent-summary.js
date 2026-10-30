// no-agent-summary.js v3.1: Bun --preload hook that switches off Claude Code's `agent_summary`
// side-query. Fork of Flamerix AI's v3 (MIT, https://gist.github.com/flamerix-ai/c3905705cc4205e5de3011fa2e74efce).
// The gate, the anchors and the suppression are upstream's, unchanged.
// Added here, so an update cannot bring the summaries back without anyone noticing:
//   - Self-check once per Claude Code build. The binary is scanned for the anchors (~50 ms on a
//     276 MB build, cached by path + size + mtime). A build that lacks them prints one stderr line
//     at every start, instead of failing open silently.
//   - A state file per build in $XDG_STATE_HOME/no-agent-summary (default ~/.local/state/...),
//     which also records the first live suppression on that build, and a marker per hooked
//     process. `status.sh` prints both.
//   - Per-process timer stats (calls seen, callbacks stringified, ms spent) on the exit log line.
//
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Flamerix AI (https://flamerix.ai); self-check, state file and markers 2026 declanbx.
// Provided "as is", without warranty. Upstream contributions: Bedz01 (the --preload= form and the
// Claude-Code-only gate).
//
// Vendored from: https://gist.github.com/declanbx/c4511b8642c9d7179ab5761ff6473871
//
// Env: CC_AGENT_SUMMARY_MODE=off|pass, CC_AGENT_SUMMARY_LOG=<file>, CC_AGENT_SUMMARY_MARKER=<file>
// as upstream; CC_AGENT_SUMMARY_STATE=<dir> overrides the state directory.
const INSTALLED = Symbol.for("flamerix.no-agent-summary.installed");
const CC_MAIN = "/$bunfs/root/cli";
const CC_EXEC_BASENAMES = [".claude-wrapped", "claude.exe", "claude"];
const CC_NATIVE_VERSION = /\/claude\/versions\/\d+\.\d+\.\d+$/;
const ANCHORS = ["[AgentSummary] Timer fired", "agent_summary"];

function isClaudeCode() {
  if (typeof Bun === "undefined" || Bun.main !== CC_MAIN) return false;
  const p = process.execPath;
  const base = p.slice(p.lastIndexOf("/") + 1);
  return CC_EXEC_BASENAMES.includes(base) || CC_NATIVE_VERSION.test(p);
}

// One file per build: line 1 is the static verdict, a later "live" line the first suppression seen.
function buildState(fs, log) {
  const dir = process.env.CC_AGENT_SUMMARY_STATE ||
    `${process.env.XDG_STATE_HOME || `${process.env.HOME}/.local/state`}/no-agent-summary`;
  const exe = process.execPath;
  let st;
  try { st = fs.statSync(exe); } catch { return null; }
  const id = Bun.hash(`${exe}|${st.size}|${st.mtimeMs}`).toString(16);
  const file = `${dir}/${id}.txt`;
  let text = "";
  try { text = fs.readFileSync(file, "utf8"); } catch {}
  if (!text) {
    const found = scanBinary(fs, exe);
    const missing = ANCHORS.filter((a, i) => !found[i]);
    text = `${missing.length === ANCHORS.length ? "static FAIL" : "static ok"} ${new Date().toISOString()} ` +
      `missing=${JSON.stringify(missing)} exe=${exe}\n`;
    try {
      fs.mkdirSync(dir, { recursive: true });
      fs.writeFileSync(`${file}.${process.pid}`, text);
      fs.renameSync(`${file}.${process.pid}`, file); // atomic: parallel first starts race harmlessly
    } catch {}
    log(text.trimEnd());
  }
  if (text.startsWith("static FAIL")) {
    process.stderr.write(`[no-agent-summary] this Claude Code build (${exe}) has none of the anchors; ` +
      `agent summaries are NOT suppressed. Update the hook.\n`);
  }
  // One marker per hooked process, so status.sh can tell which running sessions carry the hook
  // (macOS will not show another process's environment).
  const pidFile = `${dir}/pids/${process.pid}`;
  try {
    fs.mkdirSync(`${dir}/pids`, { recursive: true });
    fs.writeFileSync(pidFile, `${exe}\n`);
    process.on("exit", () => { try { fs.unlinkSync(pidFile); } catch {} });
  } catch {}
  let live = text.includes("\nlive ");
  return {
    markLive() {
      if (live) return;
      live = true;
      try { fs.appendFileSync(file, `live ok ${new Date().toISOString()} first suppression pid=${process.pid}\n`); } catch {}
    },
  };
}

// Chunked, so the 276 MB binary never sits in memory at once; stops once every anchor is found.
function scanBinary(fs, exe) {
  const needles = ANCHORS.map((a) => Buffer.from(a));
  const found = needles.map(() => false);
  const OVERLAP = Math.max(...needles.map((n) => n.length));
  const CHUNK = 16 << 20;
  let fd;
  try {
    fd = fs.openSync(exe, "r");
    const buf = Buffer.allocUnsafe(CHUNK + OVERLAP);
    let pos = 0, keep = 0;
    for (;;) {
      const n = fs.readSync(fd, buf, keep, CHUNK, pos);
      if (n <= 0) break;
      const view = buf.subarray(0, keep + n);
      needles.forEach((nd, i) => { if (!found[i] && view.indexOf(nd) >= 0) found[i] = true; });
      if (found.every(Boolean)) break;
      pos += n;
      keep = Math.min(OVERLAP, view.length);
      buf.copy(buf, 0, view.length - keep, view.length);
    }
  } catch {} finally { if (fd !== undefined) try { fs.closeSync(fd); } catch {} }
  return found;
}

function install() {
  const fs = require("fs");
  const RAW_MODE = process.env.CC_AGENT_SUMMARY_MODE || "off";
  const MODE = RAW_MODE === "pass" ? "pass" : "off";
  if (RAW_MODE !== MODE) process.stderr.write(`[no-agent-summary] unknown mode ${RAW_MODE}, forcing off\n`);
  const LOG = process.env.CC_AGENT_SUMMARY_LOG;
  const log = (s) => { if (LOG) { try { fs.appendFileSync(LOG, `${new Date().toISOString()} pid=${process.pid} ${s}\n`); } catch {} } };
  const state = buildState(fs, log);

  const stats = { calls: 0, stringified: 0, ms: 0 };
  const verdict = new WeakMap(); // fn -> bool (is the summary timer callback)
  function isSummaryTimer(fn) {
    if (typeof fn !== "function") return false;
    let v = verdict.get(fn);
    if (v === undefined) {
      const t0 = performance.now();
      try {
        const src = Function.prototype.toString.call(fn);
        v = ANCHORS.some((a) => src.includes(a));
      } catch { v = false; }
      stats.stringified++;
      stats.ms += performance.now() - t0;
      verdict.set(fn, v);
    }
    return v;
  }

  let matched = 0;
  let suppressed = 0;
  const PROMISIFY = Symbol.for("nodejs.util.promisify.custom");
  const hookedFns = new WeakSet();
  function wrap(orig) {
    if (typeof orig !== "function") return orig;
    const hooked = function (fn, delay, ...args) {
      stats.calls++;
      if (isSummaryTimer(fn)) {
        matched++;
        if (MODE === "off") {
          suppressed++;
          if (state) state.markLive();
          if (matched <= 20) log(`summary timer #${matched} suppressed (setTimeout, delay=${delay})`);
          const t = orig(() => {}, 2 ** 31 - 1); // clearTimeout-compatible handle, never fires
          if (t && typeof t.unref === "function") t.unref();
          return t;
        }
        if (matched <= 20) log(`summary timer #${matched} passed (control, setTimeout, delay=${delay})`);
      }
      return orig(fn, delay, ...args);
    };
    Object.defineProperty(hooked, "name", { value: "setTimeout" });
    // util.promisify(setTimeout) reads these; without the custom one it calls the wrapper
    // callback-last and node throws ERR_INVALID_ARG_TYPE.
    if (orig.__promisify__) hooked.__promisify__ = orig.__promisify__;
    if (orig[PROMISIFY]) hooked[PROMISIFY] = orig[PROMISIFY];
    hookedFns.add(hooked);
    return hooked;
  }

  globalThis.setTimeout = wrap(globalThis.setTimeout);
  const hookedApis = hookedFns.has(globalThis.setTimeout) ? "global.setTimeout" : "";

  const active = `preload active mode=${MODE} bun=${Bun.version} hooked=${hookedApis}`;
  log(active);
  if (LOG) process.on("exit", () => log(`exit: ${suppressed} summary timer(s) suppressed, ${matched} matched; ` +
    `setTimeout calls=${stats.calls} stringified=${stats.stringified} ms=${stats.ms.toFixed(1)}`));
  const MARKER = process.env.CC_AGENT_SUMMARY_MARKER;
  if (MARKER) {
    try { fs.writeFileSync(MARKER, `${active} pid=${process.pid}\n`); }
    catch (e) { process.stderr.write(`[no-agent-summary] cannot write marker ${MARKER}: ${e.message}\n`); }
  }
}

if (isClaudeCode() && !globalThis[INSTALLED]) {
  globalThis[INSTALLED] = true;
  install();
}
