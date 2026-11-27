// Run: node --test plugins/jev-auto-compact/tests/prefilter.test.mjs
// Prefilter-only compaction computes real reduction stats, and chained git status
// commands are never prefilter-dropped.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { compact } from '../hooks/jev-auto-compact.mjs';

function buildTranscript(toolCalls) {
  const messages = [{ role: 'user', text: 'Check repo state.' }];
  for (let i = 0; i < toolCalls.length; i++) {
    const id = `tu_${i}`;
    const { tool, input, resultText } = toolCalls[i];
    messages.push({
      role: 'assistant',
      text: '',
      toolUses: [{ tool_use_id: id, tool, input }],
    });
    messages.push({
      role: 'user',
      text: '',
      toolResults: [{ tool_use_id: id, text: resultText }],
    });
  }
  // Trailing non-tool messages so earlier tool calls are outside PRESERVE_RECENT.
  for (let i = 0; i < 8; i++) {
    messages.push({ role: i % 2 ? 'user' : 'assistant', text: `note ${i}` });
  }
  return messages;
}

test('prefilter-only compaction computes real ratio, bytes, and decision counts', async () => {
  let fetchCalled = false;
  const fetchFn = async () => {
    fetchCalled = true;
    throw new Error('fetch must not be called when candidates is empty');
  };

  const messages = buildTranscript([
    { tool: 'Glob', input: { pattern: '**/*.py' }, resultText: 'a.py\n'.repeat(400) },
    { tool: 'Bash', input: { command: 'git status' }, resultText: 'M file.py\n'.repeat(400) },
    { tool: 'Bash', input: { command: 'git status -s' }, resultText: '?? tmp.txt\n'.repeat(200) },
  ]);

  const { messages: out, stats, decisions } = await compact(fetchFn, 'fake-key', messages);

  assert.equal(fetchCalled, false);
  assert.equal(stats.totalCalls, 3);
  assert.equal(stats.jevJudged, 0);
  assert.equal(stats.prefiltered, 3);
  assert.equal(stats.droppedCall, 3);
  assert.equal(stats.droppedResult, 0);
  assert.equal(stats.kept, 0);
  assert.equal(stats.beforeBytes, JSON.stringify(messages).length);
  assert.equal(stats.afterBytes, JSON.stringify(out).length);
  assert.ok(stats.afterBytes < stats.beforeBytes);
  assert.ok(stats.ratio > 0.5, `expected real reduction ratio > 0.5, got ${stats.ratio}`);
  assert.equal(
    stats.ratio,
    Math.round((1 - stats.afterBytes / stats.beforeBytes) * 10000) / 10000,
  );
  assert.ok(Object.values(decisions).every((d) => d.action === 'drop_call'));
});

test('chained git status commands are not prefilter-dropped', async () => {
  const chainedCommands = [
    'git status && pytest',
    'git status || echo failed',
    'git status; pytest',
    'git status | grep modified',
    'git status\npytest',
  ];

  const askedIds = [];
  const fetchFn = async (_url, init) => {
    const qs = Object.keys(JSON.parse(init.body).questions);
    askedIds.push(...qs);
    return {
      ok: true,
      status: 200,
      text: JSON.stringify({
        answers: Object.fromEntries(qs.map((k) => [k, { noul: 0.9 }])),
      }),
    };
  };

  const messages = buildTranscript(
    chainedCommands.map((command) => ({
      tool: 'Bash',
      input: { command },
      resultText: '10 passed in 1.2s\n',
    })),
  );

  const { stats, decisions } = await compact(fetchFn, 'fake-key', messages);

  assert.equal(stats.prefiltered, 0, 'chained git status commands must not be prefiltered');
  assert.equal(stats.jevJudged, chainedCommands.length);
  assert.equal(stats.kept, chainedCommands.length);
  assert.equal(stats.droppedCall, 0);
  assert.ok(askedIds.length >= chainedCommands.length * 3);
  assert.ok(Object.values(decisions).every((d) => d.action === 'keep'));
});
