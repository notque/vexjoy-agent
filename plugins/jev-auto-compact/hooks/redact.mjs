/**
 * Secret redaction for text that leaves the host to the Jev API.
 *
 * Owner rule: nothing leaves the host to Jev with a secret in it. Every tool
 * input and message text passes through `redactText` before it enters the
 * compaction state; tool inputs that name a protected path are withheld whole.
 *
 * TYPE names are shared with the Python twin (`scripts/jev_redact.py`):
 *   bearer, cookie, jwt, aws_key, aws_secret, github, openai, slack, google,
 *   pem, url_credentials, kv_secret
 *
 * Replacement: `<redacted:TYPE:last4>` when the value is >= 12 chars,
 * `<redacted:TYPE>` otherwise. Zero dependencies.
 */

const MIN_LAST4_LEN = 12;
const MARK = '<redacted:';

export function mark(type, value) {
  const v = String(value ?? '');
  return v.length >= MIN_LAST4_LEN ? `${MARK}${type}:${v.slice(-4)}>` : `${MARK}${type}>`;
}

// PEM armor, assembled from pieces so a secret scanner never sees a
// key-shaped literal in this source file.
const ARMOR = '-'.repeat(5);
const PEM_BLOCK = new RegExp(
  `${ARMOR}BEGIN [A-Z ]*PRIVATE KEY${ARMOR}[\\s\\S]*?${ARMOR}END [A-Z ]*PRIVATE KEY${ARMOR}`,
  'g'
);

// Each rule: [type, regex, replacer(match, ...groups) -> string]. Order matters:
// multi-line and structured forms first, the generic KEY=VALUE rule last, and
// a value already marked `<redacted:` is never redacted twice.
const RULES = [
  ['pem', PEM_BLOCK, (m) => mark('pem', m)],
  ['url_credentials', /\b([a-z][a-z0-9+.-]*:\/\/)(?!<redacted:)([^\s/:@<]+):([^\s/@<]+)@/gi,
    (m, scheme, user, pass) => `${scheme}${mark('url_credentials', `${user}:${pass}`)}@`],
  // JWT before bearer: `Bearer eyJ...` is reported as a jwt, the more specific type.
  ['jwt', /\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b/g,
    (m) => mark('jwt', m)],
  // Header with a scheme (Bearer/Basic/Token) or a bare `Bearer x`/`Basic x`.
  ['bearer', /\b(authorization\s*[:=]\s*["']?)(bearer|basic|token)(\s+)(?!<redacted:)([A-Za-z0-9\-._~+/]+=*)/gi,
    (m, hdr, scheme, sp, tok) => `${hdr}${scheme}${sp}${mark('bearer', tok)}`],
  ['bearer', /(?<!redacted:)\b(bearer|basic)(\s+)(?!<redacted:)([A-Za-z0-9\-._~+/]{8,}=*)/gi,
    (m, scheme, sp, tok) => `${scheme}${sp}${mark('bearer', tok)}`],
  // Header with no scheme: the whole value is the credential.
  ['bearer', /\b(authorization\s*[:=]\s*["']?)(?!<redacted:)(?!bearer\b|basic\b|token\b)([^\s"',;<>]{8,})/gi,
    (m, hdr, tok) => `${hdr}${mark('bearer', tok)}`],
  // Not preceded by `:` or a word char: the `cookie:xxxx>` inside a mark is not a header.
  ['cookie', /(?<![:\w])((?:set-)?cookie\s*[:=]\s*["']?)([^\s"'<][^\r\n"']*)/gi,
    (m, hdr, val) => `${hdr}${mark('cookie', val)}`],
  ['aws_secret', /\b(aws_secret_access_key|aws[_-]?secret(?:[_-]?key)?)(\s*[:=]\s*["']?)(?!<redacted:)([A-Za-z0-9/+=]{40})\b/gi,
    (m, key, sep, val) => `${key}${sep}${mark('aws_secret', val)}`],
  ['aws_key', /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/g, (m) => mark('aws_key', m)],
  ['github', /\bgh[pousr]_[A-Za-z0-9]{20,}\b/g, (m) => mark('github', m)],
  ['openai', /\bsk-(?:proj-|live-|test-)?[A-Za-z0-9_-]{16,}\b|\bsk_(?:live|test)_[A-Za-z0-9]{8,}\b/g,
    (m) => mark('openai', m)],
  ['slack', /\bxox[abp]-[A-Za-z0-9-]{10,}\b/g, (m) => mark('slack', m)],
  ['google', /\bAIza[0-9A-Za-z_-]{35}\b/g, (m) => mark('google', m)],
  // A key inside an existing mark (`<redacted:kv_secret:…`) is never a key,
  // and a value never spans into a mark's `<`/`>`.
  ['kv_secret',
    /(?<!redacted:)\b([A-Za-z0-9_.-]*(?:secret|token|passw|api[_-]?key|private|credential|auth)[A-Za-z0-9_.-]*)("?\s*[:=]\s*["']?)(?!<redacted:)([^\s"',;<>]{8,})/gi,
    (m, key, sep, val) => `${key}${sep}${mark('kv_secret', val)}`],
];

/**
 * Redact secrets in `text`.
 * @param {string} text
 * @returns {{ text: string, count: number }}
 */
export function redactText(text) {
  let out = String(text ?? '');
  if (!out) return { text: out, count: 0 };
  let count = 0;
  for (const [, re, fn] of RULES) {
    out = out.replace(re, (...args) => {
      count++;
      return fn(...args);
    });
  }
  return { text: out, count };
}

// A tool input that names one of these is withheld whole: its content is a
// credential file by construction, and a path alone says enough to Jev.
const PROTECTED_PATH = new RegExp(
  [
    String.raw`(?:^|[\s"'=/\\])\.env(?:\.[A-Za-z0-9_-]+)?\b`,
    String.raw`\.pem\b`,
    String.raw`\.key\b`,
    String.raw`(?:^|[\s"'=/\\])id_[A-Za-z0-9]+\b`,
    String.raw`\.ssh[/\\]`,
    String.raw`\.aws[/\\]`,
    String.raw`\.gnupg[/\\]`,
    String.raw`\btoken\.json\b`,
    String.raw`\bcredentials[^/\\\s"']*`,
  ].join('|'),
  'i'
);

export const WITHHELD_INPUT = '[input withheld: protected path]';

/** True when a tool input string names a protected path. */
export function namesProtectedPath(input) {
  return PROTECTED_PATH.test(String(input ?? ''));
}

/**
 * Redact a tool input: withheld whole for a protected path, else redactText.
 * A withheld input counts as one redaction.
 * @returns {{ text: string, count: number }}
 */
export function redactToolInput(input) {
  if (namesProtectedPath(input)) return { text: WITHHELD_INPUT, count: 1 };
  return redactText(input);
}
