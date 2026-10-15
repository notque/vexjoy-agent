// Run: node --test plugins/jev-auto-compact/tests/answers.test.mjs
// Jev's reply decides which tool calls are deleted. Only a well-formed answer to a
// question that was asked may change a call; everything else keeps the call.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { compact } from '../hooks/jev-auto-compact.mjs';

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

const reply = (answers) => ({ ok: true, status: 200, text: JSON.stringify({ answers }) });
const asked = (init) => Object.keys(JSON.parse(init.body).questions);

test('a noul outside [0, 1] is no answer, so the call is kept', async () => {
  for (const bad of [-2, 7, '0.1', null]) {
    const fetchFn = async (_url, init) => reply(Object.fromEntries(asked(init).map((k) => [k, { noul: bad }])));
    const { stats, decisions } = await compact(fetchFn, 'fake-key', manyReads(3));
    assert.equal(stats.droppedCall, 0, `noul ${JSON.stringify(bad)} dropped a call`);
    assert.equal(stats.droppedResult, 0, `noul ${JSON.stringify(bad)} truncated a result`);
    assert.ok(Object.values(decisions).every((d) => d.action === 'keep'));
  }
});

test('an answer to a question another batch asked cannot change that batch', async () => {
  let requests = 0;
  await compact(
    async (_url, init) => {
      requests++;
      return reply(Object.fromEntries(asked(init).map((k) => [k, { noul: 0.9 }])));
    },
    'fake-key',
    manyReads(250),
  );
  assert.ok(requests >= 2, 'fixture must need more than one request');

  let n = 0;
  const fetchFn = async (_url, init) => {
    n++;
    const answers = Object.fromEntries(asked(init).map((k) => [k, { noul: 0.9 }]));
    if (n === requests) {
      // The last batch also answers about t1, which only the first batch asked.
      for (const key of ['call_t1', 'result_t1', 'referenced_t1']) answers[key] = { noul: 0 };
    }
    return reply(answers);
  };
  const { decisions } = await compact(fetchFn, 'fake-key', manyReads(250));
  assert.equal(decisions.t1.action, 'keep');
});

test('a request that never answers fails the batch and keeps its calls', { timeout: 5000 }, async () => {
  const never = () => new Promise(() => {});
  const { stats } = await compact(never, 'fake-key', manyReads(3), () => {}, { timeoutMs: 25 });
  assert.equal(stats.errorBatches, 1);
  assert.equal(stats.droppedCall, 0);
  assert.equal(stats.droppedResult, 0);
});
