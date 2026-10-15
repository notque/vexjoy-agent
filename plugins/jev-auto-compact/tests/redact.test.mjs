// Run: node --test plugins/jev-auto-compact/tests/redact.test.mjs
// Every value below is fake and shaped to match a pattern, nothing more.
// Prefixes are concatenated at runtime so secret scanners see no key-shaped literal.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { redactText, redactToolInput, namesProtectedPath, WITHHELD_INPUT, mark } from '../hooks/redact.mjs';

const AKIA = 'AK' + 'IA';
const ASIA = 'AS' + 'IA';
const ARMOR = '-'.repeat(5);
const pemBlock = (body) =>
  `${ARMOR}BEGIN RSA PRIVATE KEY${ARMOR}\n${body}\n${ARMOR}END RSA PRIVATE KEY${ARMOR}`;

const JWT = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dGVzdHNpZ25hdHVyZQ';
const GOOGLE = 'AIza' + 'SyA-abcdefghijklmnopqrstuvwxyz01234'; // 4 + 35 chars

// [type, text, secret value inside it, expected mark]
const cases = [
  ['bearer', 'Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123', 'abcdefghijklmnopqrstuvwxyz0123', '<redacted:bearer:0123>'],
  ['bearer', 'authorization=basic QWxhZGRpbjpvcGVuIHNlc2FtZQ==', 'QWxhZGRpbjpvcGVuIHNlc2FtZQ==', '<redacted:bearer:ZQ==>'],
  ['bearer', 'Authorization: Token abcdefghijklmnop1234', 'abcdefghijklmnop1234', '<redacted:bearer:1234>'],
  ['bearer', 'Authorization: rawtokenvalue1234', 'rawtokenvalue1234', '<redacted:bearer:1234>'],
  ['bearer', 'curl -H "Bearer abcdefghijklmnop"', 'abcdefghijklmnop', '<redacted:bearer:mnop>'],
  ['cookie', 'Cookie: session=abc123def456; theme=dark', 'abc123def456', '<redacted:cookie:dark>'],
  ['cookie', 'Set-Cookie: sid=zzzzzzzz; HttpOnly', 'zzzzzzzz', '<redacted:cookie:Only>'],
  ['jwt', `token ${JWT} end`, JWT, '<redacted:jwt:VyZQ>'],
  ['jwt', `Authorization: Bearer ${JWT}`, JWT, '<redacted:jwt:VyZQ>'],
  ['aws_key', `key ${AKIA}IOSFODNN7EXAMPLE here`, `${AKIA}IOSFODNN7EXAMPLE`, '<redacted:aws_key:MPLE>'],
  ['aws_key', `${ASIA}IOSFODNN7EXAMPLE`, `${ASIA}IOSFODNN7EXAMPLE`, '<redacted:aws_key:MPLE>'],
  ['aws_secret', 'aws_secret_access_key = wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY', 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY', '<redacted:aws_secret:EKEY>'],
  ['github', 'ghp_abcdefghijklmnopqrstuvwxyz0123456789', 'ghp_abcdefghijklmnopqrstuvwxyz0123456789', '<redacted:github:6789>'],
  ['github', 'gho_abcdefghijklmnopqrstuvwxyz0123456789', 'gho_abcdefghijklmnopqrstuvwxyz0123456789', '<redacted:github:6789>'],
  ['github', 'ghu_abcdefghijklmnopqrstuvwxyz0123456789', 'ghu_abcdefghijklmnopqrstuvwxyz0123456789', '<redacted:github:6789>'],
  ['github', 'ghs_abcdefghijklmnopqrstuvwxyz0123456789', 'ghs_abcdefghijklmnopqrstuvwxyz0123456789', '<redacted:github:6789>'],
  ['github', 'ghr_abcdefghijklmnopqrstuvwxyz0123456789', 'ghr_abcdefghijklmnopqrstuvwxyz0123456789', '<redacted:github:6789>'],
  ['openai', 'sk-abcdefghijklmnopqrstuvwxyz', 'sk-abcdefghijklmnopqrstuvwxyz', '<redacted:openai:wxyz>'],
  ['openai', 'sk_live_abcdefghijklmnop', 'sk_live_abcdefghijklmnop', '<redacted:openai:mnop>'],
  ['openai', 'sk_test_abcdefghijklmnop', 'sk_test_abcdefghijklmnop', '<redacted:openai:mnop>'],
  // Slack tokens are assembled at runtime to avoid triggering GitHub push protection.
  ['slack', `xox${'b'}-1234567890-abcdefghijklmnop`, `xox${'b'}-1234567890-abcdefghijklmnop`, '<redacted:slack:mnop>'],
  ['slack', `xox${'a'}-1234567890-abcdefghijklmnop`, `xox${'a'}-1234567890-abcdefghijklmnop`, '<redacted:slack:mnop>'],
  ['slack', `xox${'p'}-1234567890-abcdefghijklmnop`, `xox${'p'}-1234567890-abcdefghijklmnop`, '<redacted:slack:mnop>'],
  ['google', `key ${GOOGLE} here`, GOOGLE, '<redacted:google:1234>'],
  ['url_credentials', 'https://alice:s3cretpassword@db.example.test/x', 's3cretpassword', '<redacted:url_credentials:word>'],
  ['kv_secret', 'API_KEY=abcdefghijkl', 'abcdefghijkl', '<redacted:kv_secret:ijkl>'],
  ['kv_secret', '"password": "hunter2hunter2"', 'hunter2hunter2', '<redacted:kv_secret:ter2>'],
  ['kv_secret', 'my_token: 1234567890ab', '1234567890ab', '<redacted:kv_secret:90ab>'],
  ['kv_secret', 'private_credential=abcdefghijklmnop', 'abcdefghijklmnop', '<redacted:kv_secret:mnop>'],
  // Vendor prefixes and the bare-token rule match scripts/jev_redact.py (see test_jev_redact.py).
  ['gitlab', 'glpat-' + 'a1B2c3D4e5F6g7H8i9J0', 'glpat-' + 'a1B2c3D4e5F6g7H8i9J0', '<redacted:gitlab:i9J0>'],
  ['npm', 'npm_' + 'a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8', 'npm_' + 'a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8', '<redacted:npm:q7R8>'],
  ['huggingface', 'hf_' + 'a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5', 'hf_' + 'a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5', '<redacted:huggingface:N4o5>'],
  ['vercel', 'vck_' + 'a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6', 'vck_' + 'a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6', '<redacted:vercel:o5P6>'],
  ['docker', 'dckr_pat_' + 'a1B2c3D4e5F6g7H8i9J0k1L2', 'dckr_pat_' + 'a1B2c3D4e5F6g7H8i9J0k1L2', '<redacted:docker:k1L2>'],
  ['entropy', 'token a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8', 'a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8', '<redacted:entropy:e7f8>'],
];

for (const [type, input, secret, expected] of cases) {
  test(`redacts ${type}: ${input.slice(0, 40)}`, () => {
    const { text, count } = redactText(input);
    assert.ok(text.includes(expected), `${text} should contain ${expected}`);
    assert.ok(count >= 1);
    assert.ok(!text.includes(secret), `secret value must be gone: ${text}`);
    assert.equal(redactText(text).count, 0, `stable on re-run: ${text}`);
  });
}

test('pem block is replaced whole', () => {
  const pem = pemBlock('MIIBOgIBAAJBAKfake\nline2fake');
  const { text, count } = redactText(`before\n${pem}\nafter`);
  assert.equal(count, 1);
  assert.ok(!text.includes('MIIBOgIBAAJBAKfake'));
  assert.ok(text.startsWith('before\n<redacted:pem:'));
  assert.ok(text.endsWith('>\nafter'));
});

test('short values get no last4 suffix', () => {
  assert.equal(mark('kv_secret', 'abcdefgh'), '<redacted:kv_secret>');
  assert.equal(mark('kv_secret', 'abcdefghijkl'), '<redacted:kv_secret:ijkl>');
  const { text } = redactText('token=abcdefgh');
  assert.ok(text.includes('<redacted:kv_secret>'), text);
});

test('does not double-redact or touch benign text', () => {
  const once = redactText('Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123').text;
  const twice = redactText(once);
  assert.equal(twice.count, 0);
  assert.equal(twice.text, once);
  for (const benign of [
    'process.env.NODE_ENV = "production"',
    'auth_required: true',
    'the token count is 5',
    'version 1.2.3 released',
    'Read file /home/user/project/src/main.py',
  ]) {
    const r = redactText(benign);
    assert.equal(r.count, 0, benign);
    assert.equal(r.text, benign);
  }
});

test('counts every redaction in a mixed text', () => {
  const { text, count } = redactText(
    `A ghp_abcdefghijklmnopqrstuvwxyz0123456789 and ${AKIA}IOSFODNN7EXAMPLE and SECRET_KEY=abcdefghijklmnop`
  );
  assert.equal(count, 3);
  assert.ok(text.includes('<redacted:github:6789>'));
  assert.ok(text.includes('<redacted:aws_key:MPLE>'));
  assert.ok(text.includes('<redacted:kv_secret:mnop>'));
});

test('protected paths withhold the whole tool input', () => {
  for (const p of [
    '{"file_path":"/home/u/app/.env"}',
    '{"file_path":".env.local"}',
    '{"file_path":"/etc/ssl/server.pem"}',
    '{"file_path":"deploy.key"}',
    '{"file_path":"/home/u/.ssh/id_ed25519"}',
    '{"command":"cat ~/.ssh/config"}',
    '{"command":"ls ~/.aws/"}',
    '{"command":"gpg --homedir ~/.gnupg/ --list-keys"}',
    '{"file_path":"/srv/app/token.json"}',
    '{"file_path":"/srv/app/credentials.yaml"}',
    '{"file_path":"/srv/app/credentials"}',
  ]) {
    assert.ok(namesProtectedPath(p), p);
    const r = redactToolInput(p);
    assert.equal(r.text, WITHHELD_INPUT, p);
    assert.equal(r.count, 1);
  }
  for (const p of [
    '{"file_path":"src/environment.ts"}',
    '{"command":"echo $NODE_ENV"}',
    '{"file_path":"src/keys.ts"}',
    '{"file_path":"docs/identity.md"}',
    '{"old_string":"process.env.PORT"}',
  ]) {
    assert.ok(!namesProtectedPath(p), p);
    assert.equal(redactToolInput(p).text, p);
  }
});

test('plugin module imports its redactor (engine loads plugin-relative imports)', async () => {
  const mod = await import('../hooks/jev-auto-compact.mjs');
  assert.equal(typeof mod.register, 'function');
});
