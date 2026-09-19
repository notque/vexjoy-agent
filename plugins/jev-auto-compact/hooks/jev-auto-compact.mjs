/**
 * Jev Auto-Compact: constant verbatim compaction via function hooks.
 *
 * Two hooks:
 *   turn.complete — triggers $.session.compact() once context >= 60%
 *   session.compact — Jev-judges each tool call, returns pruned {messages}
 *
 * Three tiers (programs -> Jev -> no LLM):
 *   Tier 1: pair tool calls with results, pin recent, pre-filter obvious drops
 *   Tier 2: Jev judges ambiguous calls (3 criteria-rich Nouls per call)
 *   Tier 3: not needed -- zero generation, verbatim pruning only
 *
 * Zero dependencies. Uses $.http.fetch for Jev API, nothing else external.
 *
 * Nothing leaves the host with a secret in it: every message text and tool
 * input is passed through ./redact.mjs before it enters the Jev state.
 */

import { redactText, redactToolInput } from './redact.mjs';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MIN_REDUCTION_RATIO = 0.15;
/** Context-window percent at which turn.complete triggers a compaction. */
const COMPACT_AT_PERCENT = 60;
const PRESERVE_RECENT = 6;
const KEEP_THRESHOLD = 0.5;
const TRUNCATE_HEAD_CHARS = 300;
const MAX_STATE_TOKENS = 12000;
/**
 * Jev accepts 64k tokens per request, and `state` plus the longest question
 * must stay under 32k. The two limits below leave margin for the rough token
 * estimate. State is billed once per request, so every request should carry
 * as many questions as fit.
 */
const MAX_REQUEST_TOKENS = 56000;
const STATE_HARD_LIMIT_TOKENS = 28000;
/** A compaction that needs more requests than this goes to the fallback path. */
const MAX_REQUESTS_PER_COMPACTION = 4;
/** Auth and billing failures never succeed on retry; stop sending after one. */
const STOP_ON_STATUS = new Set([401, 402]);
const MAX_GOAL_CHARS = 500;
const ABRIDGE_TEXT_THRESHOLD = 550;
const ABRIDGE_HEAD = 400;
const ABRIDGE_TAIL = 150;
const JEV_URL = 'https://api.typesafe.ai/v1/systemone';
const JEV_MODEL = 'jev-latest';
/**
 * After a `{skip}` (Jev found nothing to prune) the transcript is unchanged,
 * so asking again next turn only repeats the same cold-cache Jev pass. Retry
 * once the conversation has grown by this many messages ...
 */
const SKIP_RETRY_MIN_NEW_MESSAGES = 8;
/** ... or context has risen by this many percentage points. */
const SKIP_RETRY_MIN_PERCENT = 5;

/** Per-tool threshold overrides (lower = keep more aggressively). */
const TOOL_THRESHOLDS = { Edit: 0.35, Write: 0.35, NotebookEdit: 0.35 };

// ---------------------------------------------------------------------------
// Token estimation
// ---------------------------------------------------------------------------

function estimateTokens(text) {
  if (!text) return 0;
  let tokens = 0;
  for (const ch of text) {
    if (/[a-zA-Z]/.test(ch)) tokens += 1 / 6;
    else if (/[0-9]/.test(ch)) tokens += 0.5;
    else tokens += 0.9;
  }
  return Math.floor(tokens) + 1;
}

// ---------------------------------------------------------------------------
// Tool call collection from SessionMessage[]
// ---------------------------------------------------------------------------

function collectCalls(messages) {
  const uses = new Map();
  const results = new Map();

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    for (const tu of msg.toolUses || []) {
      uses.set(tu.tool_use_id, { use: tu, msgIdx: i });
    }
    for (const tr of msg.toolResults || []) {
      results.set(tr.tool_use_id, { result: tr, msgIdx: i });
    }
  }

  const total = messages.length;
  const calls = [];
  let seq = 0;

  for (const [uid, { use, msgIdx: useIdx }] of uses) {
    const res = results.get(uid);
    if (!res) continue;
    const { result, msgIdx: resIdx } = res;

    seq++;
    const pinned =
      useIdx === 0 ||
      resIdx === 0 ||
      useIdx >= total - PRESERVE_RECENT ||
      resIdx >= total - PRESERVE_RECENT;

    const resultText = result.text || '';
    const inputStr =
      typeof use.input === 'string' ? use.input : JSON.stringify(use.input || {});

    calls.push({
      uid,
      seqId: `t${seq}`,
      tool: use.tool || 'unknown',
      input: inputStr,
      resultText,
      resultChars: resultText.length,
      useIdx,
      resIdx,
      pinned,
      isError: result.isError || false,
      useRef: use,
      resRef: result,
    });
  }
  return calls;
}

// ---------------------------------------------------------------------------
// Tier 1: programmatic pre-filters
// ---------------------------------------------------------------------------

function prefilter(call) {
  const { tool, resultChars, isError, input } = call;

  // Obvious keeps: long error results (diagnostic info)
  if (isError && resultChars > 200) return false;

  // Obvious drops
  if (tool === 'Glob' || tool === 'ListDirectory') return true;

  if (tool === 'Bash') {
    let cmd = input;
    try {
      const parsed = JSON.parse(input);
      cmd = parsed.command || input;
    } catch { /* not JSON, use raw */ }
    const stripped = cmd.trim();
    if (['ls', 'pwd', 'ls -la', 'ls -l', 'ls -a'].includes(stripped)) return true;
    if (stripped.startsWith('git status')) return true;
  }

  return null; // Jev decides
}

function prefilterCalls(calls) {
  const candidates = [];
  const decisions = {};

  for (const call of calls) {
    if (call.pinned) {
      decisions[call.seqId] = { action: 'keep', reason: 'pinned' };
      continue;
    }
    const verdict = prefilter(call);
    if (verdict === true) {
      decisions[call.seqId] = { action: 'drop_call', reason: 'prefilter_drop' };
    } else if (verdict === false) {
      decisions[call.seqId] = { action: 'keep', reason: 'prefilter_keep' };
    } else {
      candidates.push(call);
    }
  }
  return { candidates, decisions };
}

// ---------------------------------------------------------------------------
// Multi-stage state fitting (ported from Python jev-compact.py)
// ---------------------------------------------------------------------------

/** Last three user prompts, redacted. Returns { goal, redactions }. */
function extractGoal(messages) {
  const texts = [];
  let redactions = 0;
  for (let i = messages.length - 1; i >= 0 && texts.length < 3; i--) {
    if (messages[i].role === 'user' && messages[i].text) {
      const r = redactText(messages[i].text);
      redactions += r.count;
      texts.unshift(r.text.substring(0, MAX_GOAL_CHARS));
    }
  }
  return { goal: texts.join('\n---\n'), redactions };
}

// `msg.text` and each call's `input` arrive here already redacted (fitState
// does that once, before the fitting stages, so a redaction counts once).
function buildHistoryEntry(msg, idx, callsByMsg, inputLimit, abridge, collapse, pinnedIndices) {
  const role = msg.role || 'unknown';
  const text = msg.text || '';

  // Collapse non-pinned messages without tool calls
  if (collapse && !pinnedIndices.has(idx) && !callsByMsg.has(idx)) {
    if (!text.trim()) return null;
    return { i: idx, role, text: `[... ${text.length} chars omitted ...]` };
  }

  // Abridge long non-pinned text
  let displayText = text;
  if (abridge && !pinnedIndices.has(idx) && text.length > ABRIDGE_TEXT_THRESHOLD) {
    displayText =
      text.substring(0, ABRIDGE_HEAD) +
      `\n[... ${text.length - ABRIDGE_HEAD - ABRIDGE_TAIL} chars omitted ...]\n` +
      text.substring(text.length - ABRIDGE_TAIL);
  }

  const entry = { i: idx, role, text: displayText };

  const mc = callsByMsg.get(idx);
  if (mc) {
    entry.tool_calls = mc.map((c) => ({
      id: c.seqId,
      tool: c.tool,
      input: c.input.substring(0, inputLimit),
      result: `${c.isError ? 'error' : 'ok'}, ${c.resultChars} chars (omitted)`,
    }));
  }

  return entry;
}

/**
 * Build the Jev state, shrinking it stage by stage until it fits.
 * Redacts every message text and tool input first. Returns { state, redactions }.
 */
function fitState(rawMessages, rawCalls, goal) {
  let redactions = 0;
  const messages = rawMessages.map((m) => {
    if (!m.text) return m;
    const r = redactText(m.text);
    redactions += r.count;
    return r.count ? { ...m, text: r.text } : m;
  });
  const calls = rawCalls.map((c) => {
    const r = redactToolInput(c.input);
    redactions += r.count;
    return r.count ? { ...c, input: r.text } : c;
  });

  const callsByMsg = new Map();
  const pinnedIndices = new Set();

  for (const c of calls) {
    if (!callsByMsg.has(c.useIdx)) callsByMsg.set(c.useIdx, []);
    callsByMsg.get(c.useIdx).push(c);
    if (c.pinned) {
      pinnedIndices.add(c.useIdx);
      pinnedIndices.add(c.resIdx);
    }
  }

  // Pin recent messages and first message
  const total = messages.length;
  for (let i = Math.max(0, total - PRESERVE_RECENT); i < total; i++) {
    pinnedIndices.add(i);
  }
  pinnedIndices.add(0);

  const contextText =
    'A coding assistant conversation is being compacted to free context. ' +
    '`history` is the whole conversation; tool outputs are replaced by notes. ' +
    'Each question asks whether one tool call or result still needs to stay verbatim. ' +
    'Whatever is not kept is deleted permanently, but the assistant can re-run any tool.';

  // Progressive stages: [inputLimit, abridge, collapse, dropTextOnly]
  const stages = [
    [1000, false, false, false],
    [200, false, false, false],
    [60, false, false, false],
    [60, true, false, false],
    [60, true, true, false],
    [60, true, true, true],
  ];

  let state;
  for (const [inputLimit, abridge, collapse, dropTextOnly] of stages) {
    const history = [];
    for (let i = 0; i < messages.length; i++) {
      const entry = buildHistoryEntry(
        messages[i], i, callsByMsg, inputLimit, abridge, collapse, pinnedIndices
      );
      if (entry === null) continue;
      if (dropTextOnly && !pinnedIndices.has(i) && !callsByMsg.has(i)) continue;
      history.push(entry);
    }

    state = { context: contextText, goal, history };
    const stateStr = JSON.stringify(state);
    if (estimateTokens(stateStr) <= MAX_STATE_TOKENS) return { state, redactions };
  }

  return { state, redactions }; // smallest version
}

// ---------------------------------------------------------------------------
// Build Jev questions
// ---------------------------------------------------------------------------

function questionsFor(call) {
  const { seqId, tool, resultChars } = call;
  return {
    [`call_${seqId}`]: {
      type: 'noul',
      instructions: {
        question: `Tool call ${seqId} (${tool}) should stay in the history: knowing this call was made, with its input, still matters for what the assistant does next.`,
        criteria: {
          true: 'The call\'s input or the fact it was made is referenced, constrains, or informs later actions.',
          false: 'The call was exploratory, superseded by a later call to the same tool on the same target, or its input is fully captured in later context.',
        },
      },
    },
    [`result_${seqId}`]: {
      type: 'noul',
      instructions: {
        question: `The full output of tool call ${seqId} (${tool}, ${resultChars} chars) should stay verbatim: the assistant still needs its contents and re-running the tool would not reproduce it.`,
        criteria: {
          true: 'The result contains information not available elsewhere: error details, file contents being modified, test output. Re-running would not reproduce it.',
          false: 'The result is a simple acknowledgment, a file listing available from later reads, or output reproducible by re-running.',
        },
      },
    },
    [`referenced_${seqId}`]: {
      type: 'noul',
      instructions: {
        question: `The result of tool call ${seqId} (${tool}) was referenced or used in a later assistant message or tool call input.`,
      },
    },
  };
}

// ---------------------------------------------------------------------------
// Batching
// ---------------------------------------------------------------------------

function batchCalls(candidates, stateTokens) {
  if (!candidates.length) return [];
  // State over the hard limit cannot be judged in any request.
  if (stateTokens > STATE_HARD_LIMIT_TOKENS) return null;

  const available = MAX_REQUEST_TOKENS - stateTokens;
  const batches = [];
  let current = [];
  let used = 0;
  for (const c of candidates) {
    const cost = estimateTokens(JSON.stringify(questionsFor(c)));
    if (current.length > 0 && used + cost > available) {
      batches.push(current);
      current = [];
      used = 0;
    }
    current.push(c);
    used += cost;
  }
  if (current.length > 0) batches.push(current);

  // Each request re-sends the whole state. Past the cap the run costs more
  // than it saves, so the caller takes its fallback path.
  if (batches.length > MAX_REQUESTS_PER_COMPACTION) return null;
  return batches;
}

// ---------------------------------------------------------------------------
// Jev API call
// ---------------------------------------------------------------------------

async function callJev(fetchFn, apiKey, state, questions) {
  const payload = { model: JEV_MODEL, state, questions };
  const response = await fetchFn(JEV_URL, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const err = new Error(`Jev HTTP ${response.status}`);
    err.status = response.status; // status only: the body is never logged
    throw err;
  }

  const data = JSON.parse(response.text);
  if (!data.answers) throw new Error('Jev response missing answers');
  return data;
}

// ---------------------------------------------------------------------------
// Decision logic
// ---------------------------------------------------------------------------

function noulValue(answers, key) {
  const a = answers[key];
  if (!a || typeof a.noul !== 'number') return null;
  return a.noul;
}

function decideCall(call, keepCall, keepResult, referenced) {
  const threshold = TOOL_THRESHOLDS[call.tool] || KEEP_THRESHOLD;

  let effectiveResult = keepResult;
  if (referenced >= 0.6) {
    effectiveResult = Math.max(keepResult, 0.5 + (referenced - 0.6) * 0.5);
  }

  if (effectiveResult >= threshold) {
    return { action: 'keep', reason: 'kept', keepCall, keepResult, referenced };
  } else if (keepCall >= threshold) {
    return { action: 'drop_result', reason: 'result_dropped', keepCall, keepResult, referenced };
  } else {
    return { action: 'drop_call', reason: 'call_dropped', keepCall, keepResult, referenced };
  }
}

// ---------------------------------------------------------------------------
// Apply decisions to SessionMessage[]
// ---------------------------------------------------------------------------

function applyDecisions(messages, decisions, calls) {
  const uidDecision = new Map();
  for (const call of calls) {
    const d = decisions[call.seqId];
    if (d) uidDecision.set(call.uid, d);
  }

  const result = [];
  for (const msg of messages) {
    let changed = false;
    let newToolUses = msg.toolUses || [];
    let newToolResults = msg.toolResults || [];

    if (newToolUses.length > 0) {
      const filtered = newToolUses.filter((tu) => {
        const d = uidDecision.get(tu.tool_use_id);
        if (d && d.action === 'drop_call') { changed = true; return false; }
        return true;
      });
      if (filtered.length !== newToolUses.length) {
        newToolUses = filtered;
        changed = true;
      }
    }

    if (newToolResults.length > 0) {
      const filtered = [];
      for (const tr of newToolResults) {
        const d = uidDecision.get(tr.tool_use_id);
        if (d && d.action === 'drop_call') { changed = true; continue; }
        if (d && d.action === 'drop_result') {
          const text = tr.text || '';
          if (text.length > TRUNCATE_HEAD_CHARS) {
            const truncated = text.length - TRUNCATE_HEAD_CHARS;
            filtered.push({
              ...tr,
              text: text.substring(0, TRUNCATE_HEAD_CHARS) +
                `\n[jev-compact truncated ${truncated} chars; re-run the tool if needed]`,
            });
            changed = true;
          } else {
            filtered.push(tr);
          }
        } else {
          filtered.push(tr);
        }
      }
      if (changed || filtered.length !== newToolResults.length) {
        newToolResults = filtered;
        changed = true;
      }
    }

    if (!msg.text && newToolUses.length === 0 && newToolResults.length === 0) continue;

    if (!changed) {
      result.push(msg);
    } else {
      const rebuilt = { ...msg, text: msg.text || '', toolUses: newToolUses };
      if (newToolResults.length > 0) rebuilt.toolResults = newToolResults;
      else delete rebuilt.toolResults;
      result.push(rebuilt);
    }
  }
  return result;
}

// ---------------------------------------------------------------------------
// Full compaction pipeline
// ---------------------------------------------------------------------------

/**
 * @param {(url, init) => Promise<{status, ok, text}>} fetchFn
 * @param {string} apiKey
 * @param {SessionMessage[]} messages
 * @param {(line: string) => void} [log] status-only diagnostics (never a payload)
 */
export async function compact(fetchFn, apiKey, messages, log = () => {}) {
  const calls = collectCalls(messages);
  if (calls.length === 0) return { messages, stats: { totalCalls: 0, ratio: 0, errorBatches: 0, redactions: 0 } };

  // Tier 1: pre-filter
  const { candidates, decisions } = prefilterCalls(calls);
  const pinned = Object.values(decisions).filter((d) => d.reason === 'pinned').length;
  const prefiltered = Object.values(decisions).filter((d) => d.reason === 'prefilter_drop').length;

  if (candidates.length === 0) {
    const result = applyDecisions(messages, decisions, calls);
    return {
      messages: result,
      decisions,
      stats: { totalCalls: calls.length, pinned, prefiltered, jevJudged: 0, ratio: 0, errorBatches: 0, redactions: 0 },
    };
  }

  // Build state with multi-stage fitting. Nothing below this line may read
  // `messages` text or `calls[].input` for the Jev payload: only `state`.
  const { goal, redactions: goalRedactions } = extractGoal(messages);
  const { state, redactions: stateRedactions } = fitState(messages, calls, goal);
  const redactions = goalRedactions + stateRedactions;
  const stateTokens = estimateTokens(JSON.stringify(state));

  // Batch questions to fit Jev limits
  const batches = batchCalls(candidates, stateTokens);
  if (batches === null) {
    log(`[jev-auto-compact] ${candidates.length} tool calls with a ${stateTokens}-token state do not fit in ${MAX_REQUESTS_PER_COMPACTION} Jev requests`);
    return {
      messages,
      decisions,
      stats: { totalCalls: calls.length, pinned, prefiltered, jevJudged: 0, jevCalls: 0, ratio: 0, errorBatches: 0, redactions, overBudget: true, callLog: [] },
    };
  }

  const start = Date.now();
  const answers = {};
  let jevCalls = 0;
  let errorBatches = 0;
  const callLog = []; // one entry per Jev request, for the call log

  // Process batches sequentially ($.http.fetch may not support concurrent)
  for (const batch of batches) {
    const batchQuestions = {};
    for (const c of batch) {
      Object.assign(batchQuestions, questionsFor(c));
    }

    const callStart = Date.now();
    const callEntry = {
      ts: new Date(callStart).toISOString(),
      n_questions: Object.keys(batchQuestions).length,
    };
    try {
      const jevData = await callJev(fetchFn, apiKey, state, batchQuestions);
      Object.assign(answers, jevData.answers || {});
      jevCalls++;
      const u = jevData.usage || {};
      callLog.push({
        ...callEntry,
        ok: true,
        latency_ms: Date.now() - callStart,
        input_tokens: typeof u.input_tokens === 'number' ? u.input_tokens : null,
        output_tokens: typeof u.output_tokens === 'number' ? u.output_tokens : null,
      });
    } catch (err) {
      callLog.push({
        ...callEntry,
        ok: false,
        latency_ms: Date.now() - callStart,
        error: typeof err?.status === 'number' ? `HTTP ${err.status}` : err?.name || 'error',
      });
      // On batch failure, keep all calls in this batch (fail-safe). Say so
      // once per compaction, status only: never the request or response body.
      errorBatches++;
      if (errorBatches === 1) {
        const status = typeof err?.status === 'number' ? `HTTP ${err.status}` : (err?.name || 'error');
        log(`[jev-auto-compact] Jev batch failed (${status}); keeping its ${batch.length} calls`);
      }
      for (const c of batch) {
        decisions[c.seqId] = { action: 'keep', reason: 'jev_error' };
      }
      if (STOP_ON_STATUS.has(err?.status)) {
        // Keep everything not yet judged and send nothing more.
        for (const c of candidates) {
          if (!decisions[c.seqId]) decisions[c.seqId] = { action: 'keep', reason: 'jev_error' };
        }
        break;
      }
    }
  }

  const latencyMs = Date.now() - start;

  // Decide per candidate
  for (const call of candidates) {
    if (decisions[call.seqId]) continue; // already decided (error fallback)
    const kc = noulValue(answers, `call_${call.seqId}`);
    const kr = noulValue(answers, `result_${call.seqId}`);
    const ref = noulValue(answers, `referenced_${call.seqId}`);

    if (kc === null) {
      decisions[call.seqId] = { action: 'keep', reason: 'missing_answer' };
    } else {
      decisions[call.seqId] = decideCall(call, kc, kr ?? 0.5, ref ?? 0.5);
    }
  }

  // Apply
  const result = applyDecisions(messages, decisions, calls);
  const kept = Object.values(decisions).filter((d) => d.action === 'keep').length;
  const droppedResult = Object.values(decisions).filter((d) => d.action === 'drop_result').length;
  const droppedCall = Object.values(decisions).filter((d) => d.action === 'drop_call').length;

  const origLen = JSON.stringify(messages).length;
  const resultLen = JSON.stringify(result).length;
  const ratio = origLen > 0 ? 1 - resultLen / origLen : 0;

  return {
    messages: result,
    decisions,
    stats: {
      totalCalls: calls.length,
      pinned,
      prefiltered,
      jevJudged: candidates.length,
      kept,
      droppedResult,
      droppedCall,
      ratio: Math.round(ratio * 10000) / 10000,
      latencyMs,
      jevCalls,
      errorBatches,
      redactions,
      callLog,
    },
  };
}

// ---------------------------------------------------------------------------
// Evidence: bounded ring buffer in the plugin's own $.store (a JSON file the
// engine keeps under the user's Claude Code config dir). $.fs.write to a
// home-dir path is refused by the plugin sandbox, so the store is the one
// durable place. scripts/jev-compact-evidence.py ingests it into learning.db.
// ---------------------------------------------------------------------------

const EVIDENCE_KEY = 'events';
const EVIDENCE_MAX = 500;

async function appendEvidence($, record) {
  try {
    const prior = await $.store.get(EVIDENCE_KEY);
    let events = Array.isArray(prior) ? prior : [];
    events.push(...(Array.isArray(record) ? record : [record]));
    if (events.length > EVIDENCE_MAX) events = events.slice(-EVIDENCE_MAX);
    await $.store.set(EVIDENCE_KEY, events);
  } catch (error) {
    // Evidence is best-effort; never let it break compaction. Say why once.
    $.ui.log(`[jev-auto-compact] evidence not recorded (${error instanceof Error ? error.message : String(error)})`);
  }
}

async function safeUsage($) {
  try {
    const u = await $.session.usage();
    return {
      tokens: u?.context?.tokens ?? null,
      window: u?.context?.window ?? null,
      percent: u?.context?.percent ?? null,
      cost_usd: u?.cost?.usd ?? null,
    };
  } catch {
    return { tokens: null, window: null, percent: null, cost_usd: null };
  }
}

async function safeSessionId($) {
  try {
    return await $.session.id();
  } catch {
    return null;
  }
}

function pct(ratio) {
  return `${(ratio * 100).toFixed(0)}%`;
}

// ---------------------------------------------------------------------------
// Plugin registration
// ---------------------------------------------------------------------------

/** @type {import('claude-code').Register} */
export const register = (on, options) => {
  let compacting = false;
  /** Set when a plugin-triggered compaction answered {skip}: the transcript
   *  size it saw. turn.complete does not re-trigger until it has grown. */
  let skippedAt = null; // { messages: number, percent: number|null }

  on('session.compact', async ($, event, next) => {
    const trigger = event.trigger || 'unknown';

    // precompute installs nothing; a subagent's own transcript is covered by
    // the PreCompact Python hook (function hooks only see the main loop).
    if (trigger === 'precompute' || event.agentId) return next(event);

    const startedAt = Date.now();
    const ts = new Date(startedAt).toISOString();
    const sessionId = await safeSessionId($);
    const usage = await safeUsage($);
    const base = {
      kind: 'compaction',
      session_id: sessionId,
      ts,
      source: 'plugin',
      trigger,
      messages_before: event.messages.length,
      tokens_before: usage.tokens,
    };

    try {
      const apiKey =
        (await $.env.get('TYPESAFE_API_KEY')) ||
        ((await $.settings.read())?.env || {})['TYPESAFE_API_KEY'];

      if (!apiKey) {
        $.ui.log('[jev-auto-compact] no TYPESAFE_API_KEY, falling back to built-in');
        await appendEvidence($, { ...base, engine: 'builtin', note: 'no api key' });
        return next(event);
      }

      const fetchFn = async (url, init) => {
        const resp = await $.http.fetch(url, init);
        return { status: resp.status, ok: resp.ok, text: resp.text };
      };

      const result = await compact(fetchFn, apiKey, event.messages, (line) => $.ui.log(line));
      const { stats } = result;
      if (Array.isArray(stats.callLog) && stats.callLog.length > 0) {
        await appendEvidence(
          $,
          stats.callLog.map((c) => ({ kind: 'jev_call', session_id: sessionId, ...c }))
        );
      }
      const statsRecord = {
        messages_after: result.messages.length,
        reduction_ratio: stats.ratio,
        dropped_calls: stats.droppedCall ?? 0,
        truncated_results: stats.droppedResult ?? 0,
        pinned: stats.pinned ?? 0,
        prefiltered: stats.prefiltered ?? 0,
        jev_judged: stats.jevJudged ?? 0,
        jev_api_calls: stats.jevCalls ?? 0,
        jev_error_batches: stats.errorBatches ?? 0,
        redactions: stats.redactions ?? 0,
        latency_ms: stats.latencyMs ?? 0,
        duration_ms: Date.now() - startedAt,
      };

      if (stats.ratio < MIN_REDUCTION_RATIO) {
        if (trigger === 'plugin') {
          // We asked for this compaction and Jev found nothing worth pruning.
          // Leave the conversation as it is: never hand a self-triggered
          // compaction to the built-in summarizer (minutes of LLM time).
          const reason = stats.overBudget
            ? 'too large for one Jev pass'
            : `nothing to prune (${pct(stats.ratio)} < ${pct(MIN_REDUCTION_RATIO)} min)`;
          $.ui.log(`[jev-auto-compact] skipped: ${reason}`);
          await appendEvidence($, { ...base, ...statsRecord, engine: 'skipped', note: reason });
          skippedAt = { messages: event.messages.length, percent: usage.percent };
          return { skip: `jev-auto-compact: ${reason}` };
        }
        // The engine or the user needs this compaction; Jev alone is not
        // enough, so the built-in summarizer runs.
        const reason = stats.overBudget
          ? 'too large for one Jev pass'
          : `${pct(stats.ratio)} < ${pct(MIN_REDUCTION_RATIO)} min`;
        $.ui.log(`[jev-auto-compact] fallback to built-in (${reason})`);
        await appendEvidence($, { ...base, ...statsRecord, engine: 'builtin', note: reason });
        return next(event);
      }

      $.ui.log(
        `[jev-auto-compact] ${result.messages.length}/${event.messages.length} msgs, ` +
        `${pct(stats.ratio)} reduction, ` +
        `${stats.droppedCall} dropped, ${stats.droppedResult} truncated, ` +
        `${stats.pinned} pinned, ${stats.prefiltered} prefiltered ` +
        `(${stats.latencyMs}ms, ${stats.jevJudged} Jev-judged, ${stats.jevCalls} API calls` +
        (stats.errorBatches ? `, ${stats.errorBatches} failed` : '') +
        `, redactions: ${stats.redactions ?? 0}` +
        (usage.tokens ? `, ctx ${usage.tokens} tokens before)` : ')')
      );
      await appendEvidence($, { ...base, ...statsRecord, engine: 'jev' });
      skippedAt = null;

      const compacted = { messages: result.messages };
      if (typeof usage.tokens === 'number') compacted.tokensBefore = usage.tokens;
      return compacted;
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      $.ui.log(`[jev-auto-compact] fallback to built-in (${message})`);
      await appendEvidence($, { ...base, engine: 'error', note: message.substring(0, 200) });
      return next(event);
    }
  });

  on('turn.complete', async ($, event, next) => {
    // Main-loop turns only; a subagent's turn.complete carries agentId.
    if (event.agentId || compacting) return next(event);
    try {
      compacting = true;
      const usage = await safeUsage($);
      const sessionId = await safeSessionId($);
      await appendEvidence($, {
        kind: 'usage',
        session_id: sessionId,
        ts: new Date().toISOString(),
        phase: 'turn_complete',
        context_tokens: usage.tokens,
        context_window: usage.window,
        context_percent: usage.percent,
        cost_usd: usage.cost_usd,
      });
      // Threshold-gated. Every compaction is a cold KV-cache rewrite of the
      // whole prefix (measured: ~$2 vs ~$0.44 for a normal turn), so firing
      // every turn multiplies cost with no benefit. Fire only when context is
      // genuinely filling; if usage is unavailable, do nothing.
      if (typeof usage.percent !== 'number' || usage.percent < COMPACT_AT_PERCENT) {
        return next(event);
      }
      if (skippedAt) {
        // The last self-triggered compaction found nothing to prune. Re-ask
        // only once the conversation has moved on enough for a new answer.
        const messageCount = (await $.session.messages()).length;
        const grewBy = messageCount - skippedAt.messages;
        const roseBy = typeof skippedAt.percent === 'number' ? usage.percent - skippedAt.percent : Infinity;
        if (grewBy < SKIP_RETRY_MIN_NEW_MESSAGES && roseBy < SKIP_RETRY_MIN_PERCENT) return next(event);
      }
      $.ui.log(`[jev-auto-compact] context at ${usage.percent.toFixed(0)}% >= ${COMPACT_AT_PERCENT}%, compacting`);
      await $.session.compact();
    } catch (error) {
      $.ui.log(
        `[jev-auto-compact] auto-compact skipped (${error instanceof Error ? error.message : String(error)})`
      );
    } finally {
      compacting = false;
    }
    return next(event);
  });
};
