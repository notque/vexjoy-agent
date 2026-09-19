// Run: node --test plugins/jev-auto-compact/tests/call-log.test.mjs
// Every Jev request the plugin makes must appear in stats.callLog, so the
// ingest script can load it into the jev_calls table.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { compact } from '../hooks/jev-auto-compact.mjs';

function conversation(toolCalls) {
  const messages = [{ role: 'user', text: 'Find why the build fails.' }];
  for (let i = 0; i < toolCalls; i++) {
    const id = `tu_${i}`;
    messages.push({ role: 'assistant', text: '', toolUses: [{ tool_use_id: id, tool: 'Read', input: { file_path: `/src/f${i}.py` } }] });
    messages.push({ role: 'user', text: '', toolResults: [{ tool_use_id: id, text: 'x = 1\n'.repeat(80) }] });
  }
  // Recent messages are pinned; pad so the tool calls above are judged.
  for (let i = 0; i < 30; i++) messages.push({ role: i % 2 ? 'user' : 'assistant', text: `note ${i}` });
  return messages;
}

function answersFor(body) {
  const answers = {};
  for (const key of Object.keys(JSON.parse(body).questions)) answers[key] = { noul: 0.1 };
  return answers;
}

test('a successful request is logged with tokens, latency and question count', async () => {
  const fetchFn = async (_url, init) => ({
    ok: true,
    status: 200,
    text: JSON.stringify({ answers: answersFor(init.body), usage: { input_tokens: 4321, output_tokens: 99 } }),
  });
  const { stats } = await compact(fetchFn, 'fake-key', conversation(3));
  assert.ok(stats.callLog.length >= 1);
  assert.equal(stats.callLog.length, stats.jevCalls);
  const entry = stats.callLog[0];
  assert.equal(entry.ok, true);
  assert.equal(entry.input_tokens, 4321);
  assert.equal(entry.output_tokens, 99);
  assert.ok(entry.n_questions > 0);
  assert.equal(typeof entry.latency_ms, 'number');
  assert.match(entry.ts, /^\d{4}-\d{2}-\d{2}T/);
});

test('a failed request is logged with its HTTP status and no body', async () => {
  const fetchFn = async () => ({ ok: false, status: 402, text: '{"detail":"secret body"}' });
  const { stats } = await compact(fetchFn, 'fake-key', conversation(3));
  assert.equal(stats.jevCalls, 0);
  assert.ok(stats.callLog.length >= 1);
  assert.equal(stats.callLog[0].ok, false);
  assert.equal(stats.callLog[0].error, 'HTTP 402');
  assert.ok(!JSON.stringify(stats.callLog).includes('secret body'));
});

function okFetch(sizes) {
  return async (_url, init) => {
    const body = JSON.parse(init.body);
    sizes.push(Object.keys(body.questions).length);
    return { ok: true, status: 200, text: JSON.stringify({ answers: answersFor(init.body), usage: { input_tokens: 1 } }) };
  };
}

test('many tool calls share one request, so the state is billed once', async () => {
  const sizes = [];
  const { stats } = await compact(okFetch(sizes), 'fake-key', conversation(60));
  assert.equal(sizes.length, 1);
  assert.equal(sizes[0], 60 * 3);
  assert.equal(stats.jevJudged, 60);
});

test('a run that would need too many requests sends none and reports overBudget', async () => {
  const sizes = [];
  const big = conversation(3);
  // A very long pinned first message makes the smallest state exceed the hard limit.
  big[0].text = 'goal: ' + '#!@$%^&*() '.repeat(9000);
  const { stats, messages } = await compact(okFetch(sizes), 'fake-key', big);
  assert.equal(sizes.length, 0);
  assert.equal(stats.overBudget, true);
  assert.equal(stats.ratio, 0);
  assert.equal(messages.length, big.length);
});

function manyReads(n) {
  const messages = [{ role: 'user', text: 'Find why the build fails.' }];
  for (let i = 0; i < n; i++) {
    const id = `tu_${i}`;
    messages.push({ role: 'assistant', text: '', toolUses: [{ tool_use_id: id, tool: 'Read', input: { file_path: `/src/f${i}.py` } }] });
    messages.push({ role: 'user', text: '', toolResults: [{ tool_use_id: id, text: 'y = 2\n'.repeat(80) }] });
  }
  for (let i = 0; i < 30; i++) messages.push({ role: i % 2 ? 'user' : 'assistant', text: `note ${i}` });
  return messages;
}

test('a billing failure stops further requests and keeps every unjudged call', async () => {
  const sizes = [];
  await compact(okFetch(sizes), 'fake-key', manyReads(250));
  assert.ok(sizes.length >= 2, 'fixture must need more than one request');

  let sent = 0;
  const failing = async () => {
    sent++;
    return { ok: false, status: 402, text: '{}' };
  };
  const { stats } = await compact(failing, 'fake-key', manyReads(250));
  assert.equal(sent, 1);
  assert.equal(stats.droppedCall, 0);
  assert.equal(stats.droppedResult, 0);
});
