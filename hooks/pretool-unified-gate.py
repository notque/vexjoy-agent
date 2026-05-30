#!/usr/bin/env python3
# hook-version: 1.0.0
"""
PreToolUse Hook: Unified Gate (ADR-068)

Consolidates 5 PreToolUse gate hooks into a single entry point:
1. block-gitignore-bypass   — Bash: blocks git add -f on gitignored paths & .gitignore edits
2. pretool-git-submission-gate — Bash: blocks raw git push, gh pr create/merge
3. pretool-dangerous-command-guard — Bash: blocks destructive commands
4. pretool-creation-gate    — Write: blocks new agent/skill file creation
5. pretool-sensitive-file-guard — Write+Edit: blocks writes to .env, credentials, SSH keys, etc.
6. public-dev-server-guard     — Bash: blocks dev servers bound to non-loopback interfaces
                                  (python http.server binds 0.0.0.0 by default; php -S, vite --host, etc.)
                                  Supersedes the narrow, dormant prevent-homedir-server.py.

Attribution blocking removed: use settings.json {"attribution": {"commit": "", "pr": ""}} instead.
Each check preserves its original stderr prefix and bypass mechanism.
Exit 0 always. Blocks emit JSON permissionDecision:deny to stdout. Entire main() wrapped in try/except to fail OPEN.

Creation-gate allowlist: see _CREATION_PATH_ALLOWLIST. Path shapes produced
by named non-skill-creator skills (e.g. create-voice → skills/voice-*/SKILL.md)
pass through. Without this, those skills had to bypass via /tmp + cp.

Performance: <50ms. Early-exit for non-matching tools. Only gitignore bypass uses subprocess.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from learning_db_v2 import record_governance_event
from stdin_timeout import read_stdin

# ═══════════════════════════════════════════════════════════════
# 1. GITIGNORE BYPASS (block-gitignore-bypass.py)
# ═══════════════════════════════════════════════════════════════

# (patterns are inline in check_gitignore_bypass function)

# ═══════════════════════════════════════════════════════════════
# 2. GIT SUBMISSION PATTERNS (pretool-git-submission-gate.py)
# ═══════════════════════════════════════════════════════════════

_GIT_SUBMISSION_BYPASS = "CLAUDE_GATE_BYPASS=1"

_GIT_PUSH_PATTERN = re.compile(r"^(?:\w+=\S+\s+)*git\s+push\b")

_GIT_SUBMISSION_PATTERNS = [
    (_GIT_PUSH_PATTERN, "pr-sync", "Use /pr-sync to push (runs review loop first)"),
    (
        re.compile(r"^(?:\w+=\S+\s+)*gh\s+pr\s+create\b"),
        "pr-pipeline",
        "Use /pr-pipeline to create PR (runs review loop first)",
    ),
    (
        re.compile(r"^(?:\w+=\S+\s+)*gh\s+pr\s+merge\b"),
        "pr-pipeline",
        "Use /pr-pipeline to merge (requires review to pass first)",
    ),
]

# ═══════════════════════════════════════════════════════════════
# 3. DANGEROUS COMMAND PATTERNS (pretool-dangerous-command-guard.py)
# ═══════════════════════════════════════════════════════════════

_DANGEROUS_BYPASS_ENV = "DANGEROUS_GUARD_BYPASS"

_DANGEROUS_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Filesystem destruction — match -r and -f flags in ANY order, including:
    #   combined short flags: -rf, -fr, -rfi, etc.
    #   separate short flags: -r -f, -f -r
    #   long flags: --recursive --force, --recursive -f, -r --force
    #   mixed: -rf, -r -f, --recursive --force, --recursive -f, -r --force
    # The pattern uses a lookahead to require both recursive AND force flags
    # before the dangerous target path.
    (
        re.compile(
            r"\brm\s+"
            r"(?=.*(?:-[a-zA-Z]*r[a-zA-Z]*\b|--recursive\b))"
            r"(?=.*(?:-[a-zA-Z]*f[a-zA-Z]*\b|--force\b))"
            r"(?:(?:-[a-zA-Z]+|--(?:recursive|force|no-preserve-root))\s+)*"
            r"/\s*$"
        ),
        "filesystem",
        "rm -rf /",
    ),
    (
        re.compile(
            r"\brm\s+"
            r"(?=.*(?:-[a-zA-Z]*r[a-zA-Z]*\b|--recursive\b))"
            r"(?=.*(?:-[a-zA-Z]*f[a-zA-Z]*\b|--force\b))"
            r"(?:(?:-[a-zA-Z]+|--(?:recursive|force|no-preserve-root))\s+)*"
            r"/\*"
        ),
        "filesystem",
        "rm -rf /*",
    ),
    (
        re.compile(
            r"\brm\s+"
            r"(?=.*(?:-[a-zA-Z]*r[a-zA-Z]*\b|--recursive\b))"
            r"(?=.*(?:-[a-zA-Z]*f[a-zA-Z]*\b|--force\b))"
            r"(?:(?:-[a-zA-Z]+|--(?:recursive|force|no-preserve-root))\s+)*"
            r"~/?(\s|$)"
        ),
        "filesystem",
        "rm -rf ~",
    ),
    (
        re.compile(
            r"\brm\s+"
            r"(?=.*(?:-[a-zA-Z]*r[a-zA-Z]*\b|--recursive\b))"
            r"(?=.*(?:-[a-zA-Z]*f[a-zA-Z]*\b|--force\b))"
            r"(?:(?:-[a-zA-Z]+|--(?:recursive|force|no-preserve-root))\s+)*"
            r"\./?(\s|$)"
        ),
        "filesystem",
        "rm -rf .",
    ),
    # Database destruction
    (re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE), "database", "DROP DATABASE"),
    (re.compile(r"\bDROP\s+SCHEMA\b", re.IGNORECASE), "database", "DROP SCHEMA"),
    (re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE), "database", "TRUNCATE TABLE"),
    # Permission escalation
    (re.compile(r"\bchmod\s+(-R\s+)?777\b"), "permissions", "chmod 777"),
    # Force-push to protected branches
    (re.compile(r"\bgit\s+push\s+.*--force\s+.*\b(main|master)\b"), "git", "git push --force main/master"),
    (re.compile(r"\bgit\s+push\s+-f\s+.*\b(main|master)\b"), "git", "git push -f main/master"),
    # Container mass-kill
    (re.compile(r"\bdocker\s+system\s+prune\s+-af\b"), "container", "docker system prune -af"),
    (re.compile(r"\bkubectl\s+delete\s+namespace\b"), "container", "kubectl delete namespace"),
    (re.compile(r"\bkubectl\s+delete\s+ns\b"), "container", "kubectl delete ns"),
    # System-level danger
    (re.compile(r"\bmkfs\b"), "system", "mkfs (format disk)"),
    (re.compile(r"\bdd\s+if="), "system", "dd (raw disk write)"),
    # Cloud destructive
    (re.compile(r"\bterraform\s+destroy\b(?!.*-target)"), "cloud", "terraform destroy (no -target)"),
    (re.compile(r"\baws\s+s3\s+rb\s+.*--force\b"), "cloud", "aws s3 rb --force"),
]

# ═══════════════════════════════════════════════════════════════
# 4. CREATION GATE PATTERNS (pretool-creation-gate.py)
# ═══════════════════════════════════════════════════════════════

_CREATION_BYPASS_ENV = "CREATION_GATE_BYPASS"

_AGENT_PATTERN = re.compile(r"/agents/[^/]+\.md$")
_SKILL_PATTERN = re.compile(r"/(skills|pipelines)/(?:[^/]+/)?[^/]+/SKILL\.md$")
_WORKFLOW_REF_PATTERN = re.compile(r"/skills/workflow/references/[^/]+\.md$")

# Path-shape allowlist for components produced by non-skill-creator paths.
#
# Why this exists: the creation gate's default policy is "all new skills must
# route through skill-creator." That is correct for general-purpose skills,
# but several specialised skills are themselves the documented authoring
# pipeline for a specific kind of component. Forcing those outputs through
# skill-creator would break their methodology and (as observed) silently
# pushes agents into bypass workarounds (Write to /tmp/, then `cp`).
#
# Each entry must point to a path shape produced by exactly one well-known
# upstream skill/pipeline whose methodology is the de-facto SOP for that
# component type. Add new entries sparingly and document the producer.
#
# Maintainer note: this allowlist is intentionally narrow. Do NOT add broad
# patterns like `/skills/.+/SKILL\.md$` — that would defeat the gate. The
# correct test for a new entry is: "Is there a single, named skill whose
# documented output is this path shape?" If not, route through skill-creator.
_CREATION_PATH_ALLOWLIST: list[tuple[re.Pattern[str], str]] = [
    # voice-* skills are produced by the `create-voice` skill (Step 5: GENERATE
    # in skills/content/create-voice/SKILL.md and skills/content/create-voice/references/
    # skill-generation.md). create-voice is the canonical SOP for voice
    # profiles; it scaffolds skills/voice-{name}/SKILL.md, config.json, and
    # profile.json directly via Write.
    (re.compile(r"/skills/(?:content/)?voice-[^/]+/SKILL\.md$"), "create-voice"),
]

# ═══════════════════════════════════════════════════════════════
# 5. SENSITIVE FILE PATTERNS (pretool-sensitive-file-guard.py)
# ═══════════════════════════════════════════════════════════════

_SENSITIVE_BYPASS_ENV = "SENSITIVE_FILE_GUARD_BYPASS"

_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    # Environment files (except .env.example)
    (re.compile(r"/\.env$"), "env", ".env"),
    (re.compile(r"/\.env\.(local|production|staging|development|dev|prod)$"), "env", ".env.*"),
    # Credential files
    (re.compile(r"/credentials\.(json|yml|yaml)$"), "credentials", "credentials file"),
    (re.compile(r"/service-account[^/]*\.json$"), "credentials", "service account JSON"),
    # SSH keys
    (re.compile(r"/\.ssh/"), "ssh", "SSH directory"),
    (re.compile(r"/id_(rsa|ed25519|ecdsa|dsa)$"), "ssh", "SSH private key"),
    # Private key / certificate files
    (re.compile(r"\.p12$"), "certificate", ".p12 certificate"),
    (re.compile(r"\.pfx$"), "certificate", ".pfx certificate"),
    (re.compile(r"\.key$"), "certificate", ".key private key"),
    # Cloud configs
    (re.compile(r"\.aws/credentials$"), "cloud", "AWS credentials"),
    (re.compile(r"\.kube/config$"), "cloud", "kubeconfig"),
    (re.compile(r"\.gcloud/"), "cloud", "gcloud config directory"),
    # Token files
    (re.compile(r"/token\.json$"), "token", "token.json"),
    (re.compile(r"/\.tokens$"), "token", ".tokens file"),
]

_SENSITIVE_EXCEPTIONS: list[re.Pattern[str]] = [
    re.compile(r"\.env\.example$"),
    re.compile(r"\.env\.sample$"),
    re.compile(r"\.env\.template$"),
    re.compile(r"/testdata/"),
    re.compile(r"/fixtures/"),
    re.compile(r"/__fixtures__/"),
    re.compile(r"/test_?data/"),
]

# ═══════════════════════════════════════════════════════════════
# 6. PUBLIC DEV SERVER GUARD (supersedes prevent-homedir-server.py)
# ═══════════════════════════════════════════════════════════════
#
# WHY: A raw dev server bound to a non-loopback interface exposes the served
# directory to the public internet. `python -m http.server` binds 0.0.0.0 BY
# DEFAULT (all interfaces). On a public VPS this silently publishes files. The
# old prevent-homedir-server.py only blocked serving the BARE home dir and
# explicitly allowed `cd ~/project && http.server` — i.e. it permitted the exact
# unsafe pattern. This check is block-by-default for python http.server unless
# an explicit loopback bind is present, and blocks any dev server given an
# explicit non-loopback bind/host.
#
# Bound to its own bypass var, consistent with the gate's per-check convention.
_PUBLIC_SERVER_BYPASS_ENV = "PUBLIC_SERVER_GUARD_BYPASS"

# Loopback / local-only host values (lowercased).
_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})

# python -m http.server / SimpleHTTPServer. Handles python / python2 / python3 /
# python3.11 / the `py` launcher, a space or no space after -m (`-m http.server`,
# `-mhttp.server`), both module names, and an optionally quoted module name
# (`-m 'http.server'`, `-m "http.server"`). Detection is regex-on-text (a shared
# limit of every check in this gate): variable-expanded interpreters (`$p -m …`)
# or module names built in a var are NOT caught — that is an accepted residual.
_PY_HTTP_SERVER_RE = re.compile(r"(?:\bpython[\d.]*\b|\bpy\b)[^|;&]*?-m\s*['\"]?(?:http\.server|SimpleHTTPServer)\b")

# `FOO=bar` env-assignment prefix (transparent: the real executable follows).
# Tokenized via shlex, so the value (quotes already removed) may contain spaces;
# match the assignment prefix and accept any value content.
_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# Transparent command wrappers — the real executable is the next NON-OPTION token.
# Their own option flags (e.g. `sudo -u nobody`, `env -i`) are stripped so they do
# not become the command token (which would hide the wrapped server). `-u`/`-g`/
# etc. that take a value: the value (a non-option token) is consumed by the normal
# "skip options" loop only if it is itself an option; a bare value token is treated
# as the next executable candidate, so we conservatively skip one token after a
# known value-taking wrapper flag.
_WRAPPERS = frozenset(
    {"sudo", "env", "exec", "command", "nohup", "time", "nice", "setsid", "stdbuf", "ionice", "doas", "timeout"}
)
# Wrappers that take a mandatory POSITIONAL value before the command, after any
# options: `timeout [opts] DURATION cmd …`. Its duration token is skipped (unless
# it is itself an executable, guarded like flag values).
_POSITIONAL_VALUE_WRAPPERS = frozenset({"timeout"})
# Exec-style runners that launch an INNER command (`npx vite`, `npm exec next`,
# `yarn dlx astro`, `pnpm dlx vite`, `bun x next`). The inner command is the real
# server, so these prefixes are stripped to expose it as the command token.
_EXEC_RUNNER_PREFIXES = (
    ("npx",),
    ("npm", "exec"),
    ("pnpm", "exec"),
    ("pnpm", "dlx"),
    ("yarn", "exec"),
    ("yarn", "dlx"),
    ("bun", "x"),
)
# Wrapper short flags that consume a following value token (so we skip that token
# too): sudo -u/-g/-C/-h/-p/-r/-t/-U; env -u NAME / -C dir; nice -n N; ionice -c
# CLASS / -n N; stdbuf -i/-o/-e. NOTE: these letters mean different things across
# wrappers (env -i is valueless; stdbuf -i takes a value), so a value token is
# NEVER consumed when it is itself a known server/runner/interpreter name (see
# _is_executable_token) — that prevents `env -i vite …` from eating `vite`.
_WRAPPER_VALUE_FLAGS = frozenset(
    {"-u", "-g", "-C", "-p", "-r", "-t", "-U", "-i", "-o", "-e", "-h", "-n", "-c", "-s", "-k"}
)
# Long wrapper value-flags in space-separated form (`sudo --user nobody`,
# `nice --adjustment 5`, `timeout --signal KILL`). The `--key=value` form is a
# single token (no value skip); this set covers `--key value`.
_WRAPPER_LONG_VALUE_FLAGS = frozenset(
    {
        "--user",
        "--group",
        "--chdir",
        "--prompt",
        "--role",
        "--type",
        "--adjustment",
        "--class",
        "--signal",
        "--kill-after",
    }
)
# Exec-runner option flags that take a value (so the value token is skipped too):
# `npx -p <pkg>`, `npx --package <pkg>`, `npx -c <cmd>`. Plain `--yes`/`-y`/`-q`
# are valueless and skipped by the generic option loop.
_EXEC_RUNNER_VALUE_FLAGS = frozenset({"-p", "--package", "-c", "--call"})


def _is_executable_token(tok: str) -> bool:
    """True if `tok` (basename, lowercased) names a server/runner/interpreter.

    Used as a guard so a wrapper/runner flag's VALUE is never consumed when it is
    actually the wrapped command: `env -i vite …` must not eat `vite` as the value
    of `-i`. A real flag value (a username, niceness, fd, package) is never one of
    these executable names.
    """
    base = tok.rsplit("/", 1)[-1].lower()
    at = base.find("@", 1)  # drop a version spec (vite@latest) before matching
    if at != -1:
        base = base[:at]
    return (
        base in _JS_DEV_SERVERS
        or base in _NODE_RUNNERS
        or base in _PY_WEB_SERVERS
        or base in _SHELL_LAUNCHERS  # `env -i bash -c …` must not eat `bash`
        or base in {"php", "py"}
        or base.startswith("python")
    )


def _strip_leading_prefixes(segment: str) -> str:
    """Strip leading env-assignments, transparent wrappers, and exec-runner
    prefixes so the real executable is at the front.

    Handles `FOO=bar`, wrappers and THEIR option flags (`sudo -u nobody`, `env -i`,
    `nice -n 5`, `sudo --user nobody`), path-qualified wrappers (`/usr/bin/env`),
    and exec-style runners launching an inner command (`npx vite`, `npm exec next`,
    `yarn dlx astro`). Without this, a wrapped server (`sudo -u nobody php -S
    0.0.0.0`) or an exec-launched server (`npx vite --host 0.0.0.0`) would slip
    past command-token detection. A flag's value is not consumed when it is itself
    an executable name (guards `env -i vite …` against eating `vite`).
    """
    seg = segment.strip().lstrip("'\"")
    # shlex respects quotes so a quoted env value with spaces (`A='x y' vite …`)
    # stays one token; fall back to naive split on a parse error (unbalanced quote).
    try:
        toks = shlex.split(seg, posix=True)
    except ValueError:
        toks = seg.split()

    def base(tok: str) -> str:
        return tok.rsplit("/", 1)[-1].lower()

    i = 0
    changed = True
    while changed and i < len(toks):
        changed = False
        # env-assignment prefix: FOO=bar
        if i < len(toks) and _ENV_ASSIGN_RE.match(toks[i]):
            i += 1
            changed = True
            continue
        # transparent wrapper (basename-normalized) + its option flags
        if i < len(toks) and base(toks[i]) in _WRAPPERS:
            wrapper = base(toks[i])
            i += 1
            changed = True
            while i < len(toks) and toks[i].startswith("-"):
                flag = toks[i]
                i += 1
                # `-u nobody` / `--user nobody`: skip the value token too — unless it
                # is itself an executable (then it is the wrapped command, not a value).
                takes_value = flag in _WRAPPER_VALUE_FLAGS or flag in _WRAPPER_LONG_VALUE_FLAGS
                if takes_value and i < len(toks) and not toks[i].startswith("-") and not _is_executable_token(toks[i]):
                    i += 1
            # mandatory positional value (`timeout DURATION cmd`): skip it unless it
            # is itself an executable (guards against eating the wrapped command).
            if (
                wrapper in _POSITIONAL_VALUE_WRAPPERS
                and i < len(toks)
                and not toks[i].startswith("-")
                and not _is_executable_token(toks[i])
            ):
                i += 1
            continue
        # exec-style runner prefix (basename-normalized) + the runner's own option
        # flags (`npx --yes vite`, `npx -p pkg vite`), so the INNER command — not a
        # runner flag like `--yes` — becomes the executable token.
        matched = False
        for prefix in _EXEC_RUNNER_PREFIXES:
            n = len(prefix)
            if n and [base(t) for t in toks[i : i + n]] == list(prefix):
                i += n
                changed = True
                matched = True
                while i < len(toks) and toks[i].startswith("-"):
                    if toks[i] == "--":  # explicit end-of-options
                        i += 1
                        break
                    flag = toks[i]
                    i += 1
                    if (
                        flag in _EXEC_RUNNER_VALUE_FLAGS
                        and i < len(toks)
                        and not toks[i].startswith("-")
                        and not _is_executable_token(toks[i])
                    ):
                        i += 1
                break
        if matched:
            continue
    return " ".join(toks[i:])


def _command_token(segment: str) -> str:
    """Return the lowercased executable token of a shell segment.

    Anchors server-name detection to the COMMAND, not a free-floating word in an
    argument (so `git commit -a -m next` does not match the `next` dev server).
    Returns the basename so `/usr/bin/vite` and `./node_modules/.bin/vite` match,
    and strips a trailing `@version` so `npx vite@latest` still resolves to `vite`.
    """
    seg = _strip_leading_prefixes(segment)
    m = re.match(r"['\"]?([^\s'\"]+)", seg)
    if not m:
        return ""
    tok = m.group(1).rsplit("/", 1)[-1].lower()
    # Drop a package version spec (`vite@latest`, `http-server@14`). A leading `@`
    # (scoped pkg like `@angular/cli`) is preserved by only splitting after char 0.
    at = tok.find("@", 1)
    if at != -1:
        tok = tok[:at]
    return tok


# Node task runners (npm/pnpm/yarn/bun) recognized as the COMMAND token. On their
# own they default to localhost (do NOT over-block), but `npm run dev -- --host
# 0.0.0.0` forwards an explicit public host flag, caught by the host-flag scan.
_NODE_RUNNERS = frozenset({"npm", "pnpm", "yarn", "bun"})

# Explicit bind flag value on a python http.server invocation (http.server uses
# --bind/-b). Captures bracketed IPv6 too: --bind [::1].
_PY_BIND_RE = re.compile(r"(?:--bind(?:\s+|=)|(?<![\w-])-b\s+)['\"]?(\[[^\]]+\]|[^\s'\"]+)")

# Long-form public-bind/host flags used by node/JS/go/python dev servers:
#   --bind/--host/--listen/--address <value>. Supports `=` form. Always scanned —
#   long flags do not collide with common non-server short flags.
_HOST_FLAG_RE = re.compile(r"(?:--(?:bind|host|listen|address)(?:\s+|=))['\"]?(\[[^\]]+\]|[^\s'\"]+)")


# Per-server SHORT bind/host flags. Each server uses a DIFFERENT short letter, and
# those letters collide with unrelated tools (git -a, curl -H, ssh -b) AND with
# other servers' unrelated flags (ng's passthrough -a is not a host). So a short
# flag is honored only for the specific server that uses it for binding:
#   next -H <host>;  http-server -a <addr>;  gunicorn -b <host:port>;  flask -h.
# Built once; compiled regexes capture the flag's value (bracketed IPv6 too).
def _short_flag_re(letter: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![\w-])-{letter}(?:\s+|=)?['\"]?(\[[^\]]+\]|[^\s'\"]+)")


_SERVER_SHORT_FLAGS: dict[str, re.Pattern[str]] = {
    "next": _short_flag_re("H"),
    "http-server": _short_flag_re("a"),
    "gunicorn": _short_flag_re("b"),
    "flask": _short_flag_re("h"),  # `flask run -h <host>` is short for --host
}

# php -S <host>:<port>  (built-in PHP dev server; binds exactly the given host).
_PHP_SERVER_RE = re.compile(r"\bphp\b[^|;&]*?\s-S\s+['\"]?(\[[^\]]+\]|[^\s'\":]+)")

# `php artisan serve` (Laravel dev server). Only THIS php subcommand exposes a
# server via --host; a plain `php script.php --host …` is an ordinary CLI script.
_PHP_ARTISAN_SERVE_RE = re.compile(r"\bartisan\s+serve\b")

# Client-side JS/static dev servers whose --host flag exposes the server publicly,
# matched as the COMMAND token (not a free-floating word).
_JS_DEV_SERVERS = frozenset(
    {
        "vite",
        "next",
        "nuxt",
        "http-server",
        "hugo",
        "webpack",
        "webpack-dev-server",
        "ng",
        "astro",
        "remix",
        "svelte-kit",
        "vue-cli-service",
    }
)

# Python web servers (flask run, uvicorn, gunicorn) that expose a public host
# through a --host/--bind/-b flag. Caught by the long-flag scan (plus gunicorn's
# -b short flag). Recognized either as their own console-script command token or
# via `python -m <module>` (see _PY_MODULE_RE).
_PY_WEB_SERVERS = frozenset({"flask", "uvicorn", "gunicorn"})

# `python[-ver] -m <module>` — captures the module a python interpreter runs, so
# `python3 -m flask run --host=0.0.0.0` maps to the `flask` server. Anchored at
# the segment's leading interpreter token (after wrappers are stripped upstream).
_PY_MODULE_RE = re.compile(r"^(?:\S*/)?(?:python[\d.]*|py)\b[^|;&]*?-m\s+['\"]?([A-Za-z0-9_.\-]+)")


def _host_is_public(host: str) -> bool:
    """Return True if a host/bind value exposes a non-loopback interface.

    Bare `0` is the classic shorthand for 0.0.0.0. Empty/odd values fail safe
    (treated as public → block). IPv6 `::` / `[::]` is the wildcard. Any
    concrete non-loopback IP or hostname on an explicit bind flag is public.
    A value starting with `-` is another flag, not a host → NOT public.
    """
    h = host.strip().strip("'\"")
    if not h:
        return True  # flag present with no usable value — fail safe (block)
    if h.startswith("-"):
        return False  # captured token is a flag, not a host address
    low = h.lower()
    if low in _LOCAL_HOSTS:
        return False
    if low.startswith("127."):  # IPv4 loopback range (127.x)
        return False
    if low in {"0.0.0.0", "0", "::", "[::]", "*", "[::0]", "::0"}:  # wildcards
        return True
    # Any other concrete host on an explicit public-bind flag → non-loopback.
    return True


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════


def _load_guard_whitelist() -> list[str]:
    """Load per-project whitelist from .guard-whitelist if it exists."""
    whitelist_path = Path.cwd() / ".guard-whitelist"
    if not whitelist_path.is_file():
        return []
    try:
        entries = []
        for line in whitelist_path.read_text().splitlines():
            entry = line.strip()
            if not entry or entry.startswith("#"):
                continue
            if len(entry) < 8:
                print(
                    f"[dangerous-command-guard] WARN: Skipping short whitelist entry (< 8 chars): {entry!r}",
                    file=sys.stderr,
                )
                continue
            entries.append(entry)
        print(
            f"[dangerous-command-guard] INFO: Loaded {len(entries)} whitelist entries ({whitelist_path})",
            file=sys.stderr,
        )
        return entries
    except OSError:
        return []


def _is_whitelisted(command: str, whitelist: list[str]) -> bool:
    """Check if the command matches any whitelist entry."""
    for entry in whitelist:
        if entry in command:
            return True
    return False


def _load_guard_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """Load per-project sensitive patterns from .guard-patterns.

    Entries are treated as glob-like patterns: ``*`` matches any sequence,
    ``?`` matches a single character, and all other regex metacharacters
    are escaped.  Malformed entries that fail ``re.compile`` are logged to
    stderr and skipped so that a single bad line cannot disable the entire
    sensitive-file guard.
    """
    guard_path = Path.cwd() / ".guard-patterns"
    if not guard_path.is_file():
        return []
    extra: list[tuple[re.Pattern[str], str, str]] = []
    try:
        for line in guard_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Escape ALL regex metacharacters first, then selectively
                # convert glob wildcards back to their regex equivalents.
                regex = re.escape(line)
                regex = regex.replace(r"\*", ".*")  # glob * -> regex .*
                regex = regex.replace(r"\?", ".")  # glob ? -> regex .
                try:
                    extra.append((re.compile(regex), "custom", line))
                except re.error as exc:
                    print(
                        f"[sensitive-file-guard] WARN: Skipping malformed .guard-patterns entry {line!r}: {exc}",
                        file=sys.stderr,
                    )
    except OSError:
        pass
    return extra


def _is_sensitive_exception(file_path: str) -> bool:
    """Check if file matches a sensitive-file exception pattern."""
    return any(p.search(file_path) for p in _SENSITIVE_EXCEPTIONS)


def _block(message: str, tool_name: str = "", reason: str = "") -> None:
    """Emit a structured deny decision and exit 0.

    Keeps the stderr message for debug visibility (Ctrl+O verbose mode)
    and emits JSON permissionDecision to stdout so Claude Code surfaces
    the reason to the model rather than a generic error.
    """
    print(message, file=sys.stderr)
    try:
        record_governance_event("hook_blocked", tool_name=tool_name, hook_phase="pre", severity="high", blocked=True)
    except Exception:
        pass  # Never let recording prevent a block
    deny_reason = reason if reason else message
    deny_output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    print(json.dumps(deny_output))
    sys.exit(0)


# ═══════════════════════════════════════════════════════════════
# CHECK FUNCTIONS — each returns normally (allow) or calls _block (JSON deny + exit 0)
# ═══════════════════════════════════════════════════════════════


def check_gitignore_bypass(command: str) -> None:
    """Block git add -f on gitignored paths and .gitignore edits."""
    # Block 1: .gitignore modification attempts
    cmd_part = command.split("<<")[0] if "<<" in command else command
    if (
        re.search(r"(>|>>)\s*\.gitignore", cmd_part)
        or re.search(r"(sed|awk|tee)\b.*\.gitignore", cmd_part)
        or re.search(r"mv\s+\S+\s+\.gitignore", cmd_part)
    ):
        _block(
            "[gitignore-bypass] BLOCKED: Agents must not modify .gitignore.\n"
            "[gitignore-bypass] This file controls repository safety boundaries.",
            reason="Agents must not modify .gitignore. This file controls repository safety boundaries.",
        )

    # Fast path: no git add in command
    if "git add" not in command:
        return

    # Block 2: git add with force flags
    if not re.search(r"git\s+add\s+.*(-f|--force)", command):
        return

    # Extract paths being force-added
    parts = command.split()
    try:
        add_idx = parts.index("add")
    except ValueError:
        return

    paths = []
    past_separator = False
    for part in parts[add_idx + 1 :]:
        if part == "--":
            past_separator = True
            continue
        if part.startswith("-") and not past_separator:
            continue
        paths.append(part)

    if not paths:
        return

    # Check which paths are gitignored
    try:
        result = subprocess.run(
            ["git", "check-ignore"] + paths,
            capture_output=True,
            text=True,
            timeout=3,
        )
        ignored = [p for p in result.stdout.strip().split("\n") if p]
    except (subprocess.TimeoutExpired, OSError):
        return  # Don't block on check failure

    if ignored:
        _block(
            f"[gitignore-bypass] BLOCKED: git add -f on gitignored paths: {', '.join(ignored)}\n"
            "[gitignore-bypass] These paths are gitignored for a reason. Do not force-add them.",
            reason=f"Cannot force-add gitignored paths: {', '.join(ignored)}. These paths are gitignored for a reason. Stage only tracked files.",
        )


def _extract_effective_cwd(command: str, default_cwd: str | None = None) -> str | None:
    """Extract the effective working directory from a command string.

    Detects two patterns:
    - ``cd <path> && ...`` or ``cd <path> ; ...`` prefix
    - ``git -C <path> ...`` flag

    Returns the extracted path if found, otherwise default_cwd.
    """
    m = re.match(r'cd\s+(?:"([^"]+)"|(\S+))\s*(?:&&|;)', command.lstrip())
    if m:
        p = (m.group(1) or m.group(2) or "").strip()
        if p:
            return p
    m = re.search(r'\bgit\s+-C\s+(?:"([^"]+)"|(\S+))', command)
    if m:
        return m.group(1) or m.group(2)
    return default_cwd


def _is_worktree_on_feature_branch(cwd: str) -> bool:
    """Return True if cwd is a worktree directory on a non-protected branch."""
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            return bool(branch) and branch not in {"main", "master"}
    except (subprocess.TimeoutExpired, OSError):
        pass
    return False


def check_git_submission(command: str) -> None:
    """Block raw git push, gh pr create, gh pr merge unless bypassed or personal profile."""
    # Skills prefix blocked commands with CLAUDE_GATE_BYPASS=1 to pass through
    if command.lstrip().startswith(_GIT_SUBMISSION_BYPASS):
        return

    # Personal operator profile: full autonomy, no approval gates
    operator = os.environ.get("CLAUDE_OPERATOR_PROFILE", "personal")
    if operator == "personal":
        return

    cmd = command.lstrip()
    for pattern, skill_name, message in _GIT_SUBMISSION_PATTERNS:
        if pattern.search(cmd):
            # Allow git push from worktree directories on feature branches
            if pattern is _GIT_PUSH_PATTERN:
                effective_cwd = _extract_effective_cwd(command)
                project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
                if effective_cwd and effective_cwd != project_dir and _is_worktree_on_feature_branch(effective_cwd):
                    return
            _block(
                f"[git-submission-gate] BLOCKED: {message}\n[fix-with-skill] {skill_name}",
                reason=f"{message} Use the {skill_name} skill instead.",
            )


def check_dangerous_command(command: str) -> None:
    """Block destructive commands unless bypassed or whitelisted."""
    if os.environ.get(_DANGEROUS_BYPASS_ENV) == "1":
        return

    # Load whitelist once before scanning rather than on each match.
    whitelist = _load_guard_whitelist()

    # Intentionally scans full command including heredoc bodies.
    # Over-blocking preferred for destructive commands.
    for pattern, category, description in _DANGEROUS_PATTERNS:
        if pattern.search(command):
            if _is_whitelisted(command, whitelist):
                return
            _block(
                f"[dangerous-command] BLOCKED: {description} ({category})\n"
                f"[dangerous-command] Command: {command}\n"
                f"[dangerous-command] To allow: add pattern to .guard-whitelist",
                reason=f"Dangerous command blocked: {description} (category: {category}). To allow, add a pattern to .guard-whitelist.",
            )


def check_creation_gate(file_path: str) -> None:
    """Block new agent/skill file creation unless bypassed or on the producer allowlist."""
    if os.environ.get(_CREATION_BYPASS_ENV) == "1":
        return

    is_agent = bool(_AGENT_PATTERN.search(file_path))
    is_skill = bool(_SKILL_PATTERN.search(file_path))
    is_workflow_ref = bool(_WORKFLOW_REF_PATTERN.search(file_path))
    if not is_agent and not is_skill and not is_workflow_ref:
        return

    # Allow overwrites of existing files (update, not creation)
    if os.path.exists(file_path):
        return

    # Allow creation paths produced by named upstream skills (see
    # _CREATION_PATH_ALLOWLIST docstring).
    for allowed_pattern, _producer in _CREATION_PATH_ALLOWLIST:
        if allowed_pattern.search(file_path):
            return

    component_type = "agent" if is_agent else "workflow reference" if is_workflow_ref else "skill"
    _block(
        f"[creation-gate] BLOCKED: New {component_type} must be created via skill-creator or skill-creation-pipeline.\n"
        f"[creation-gate] Path: {file_path}\n"
        f"[fix-with-agent] skill-creator",
        reason=f"New {component_type} files must be created via the skill-creator agent, not written directly. Use [fix-with-agent] skill-creator.",
    )


def check_sensitive_file(file_path: str) -> None:
    """Block writes to sensitive files unless bypassed or excepted."""
    if os.environ.get(_SENSITIVE_BYPASS_ENV) == "1":
        return

    if _is_sensitive_exception(file_path):
        return

    all_patterns = _SENSITIVE_PATTERNS + _load_guard_patterns()
    for pattern, category, description in all_patterns:
        if pattern.search(file_path):
            _block(
                f"[sensitive-file-guard] BLOCKED: Write to sensitive file ({category})\n"
                f"[sensitive-file-guard] Path: {file_path}\n"
                f"[sensitive-file-guard] Pattern: {description}\n"
                f"[sensitive-file-guard] To allow: set SENSITIVE_FILE_GUARD_BYPASS=1 or add exception to .guard-patterns",
                reason=f"Write to sensitive file blocked ({category}: {description}). Path: {file_path}. Set SENSITIVE_FILE_GUARD_BYPASS=1 or add an exception to .guard-patterns to allow.",
            )


_PUBLIC_SERVER_DENY_MSG = (
    "BLOCKED: this command would expose a dev server on a PUBLIC network interface.\n\n"
    "`python -m http.server` (and many dev servers) bind 0.0.0.0 — ALL interfaces — "
    "by default, publishing the served directory to the internet on a public host.\n\n"
    "For LOCAL preview, bind loopback explicitly:\n"
    "  python3 -m http.server 8080 --bind 127.0.0.1\n"
    "  php -S 127.0.0.1:8000\n"
    "  vite --host 127.0.0.1\n\n"
    "For PUBLIC hosting, do NOT expose a raw dev server. Put it behind a real web "
    "server / tunnel (nginx, Caddy, Cloudflare Tunnel) — see the public-web-deploy skill.\n\n"
    "Rare intentional case: set PUBLIC_SERVER_GUARD_BYPASS=1."
)


# Commands that merely DISPLAY or SEARCH text — a server string in their args is
# data, not an executed invocation. Used to suppress false positives like
# `echo 'python3 -m http.server'` and `grep -r 'vite --host 0.0.0.0' .`.
_DISPLAY_CMD_RE = re.compile(
    r"^(?:#|:|echo\b|printf\b|grep\b|egrep\b|fgrep\b|rg\b|cat\b|less\b|more\b|head\b|tail\b|comm\b)"
)

# Shell separators that start a new command segment. Splitting on these lets us
# evaluate each segment independently: `echo foo && python3 -m http.server`
# still blocks the real invocation while `echo 'python3 -m http.server'` does not.
# Deliberately does NOT split on newline: heredoc bodies and quoted multiline
# args contain literal newlines that must stay attached to their leading command
# (e.g. `printf '%s\n' '...'`, `cat <<'EOF' ... EOF`) — splitting them produced
# false positives (codex-found). Chaining is still caught via ; && || | &.
_SEGMENT_SPLIT_RE = re.compile(r"(?:&&|\|\||[;|&])")

# Command-substitution bodies: $(...), `...`, and <(...) / >(...) process subs.
# A server launched inside a substitution is a real invocation even when the
# outer command is a display command (`echo $(python3 -m http.server)`), so the
# body is evaluated independently before display-command suppression. Single
# level (no recursive $( $( ) ) nesting) — an accepted regex-on-text residual.
_SUBSTITUTION_RE = re.compile(r"\$\((?P<dollar>[^()]*)\)|`(?P<back>[^`]*)`|[<>]\((?P<proc>[^()]*)\)")


def _single_quoted_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans of LITERAL single-quoted regions in `text`.

    In POSIX shells single quotes are literal — `$(...)`/backticks inside them are
    NOT substitutions — so a substitution inside such a span is data, not an
    invocation (`echo '$(python3 -m …)'` must NOT block). Three subtleties this
    scanner honors so the suppression cannot be abused to hide a real server:
      * A `'` inside a DOUBLE-quoted region is an ordinary char, NOT a span opener
        (`echo "'$(…)'"` still executes the substitution → must block).
      * A backslash-escaped `\\'` outside quotes is a literal `'`, NOT a span
        opener (`echo \\'$(…)\\'` still executes → must block).
      * Inside a single-quoted span, backslash is NOT special (POSIX) — the span
        ends at the next raw `'`.
    """
    spans: list[tuple[int, int]] = []
    in_double = False
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and not in_double:
            i += 2  # backslash escapes the next char outside double quotes
            continue
        if c == '"':
            in_double = not in_double
        elif c == "'" and not in_double:
            close = text.find("'", i + 1)
            if close == -1:
                break  # unterminated single quote — no literal span
            spans.append((i, close + 1))
            i = close + 1
            continue
        i += 1
    return spans


# Shell launchers whose `-c <payload>` argument is the real command to evaluate.
_SHELL_LAUNCHERS = frozenset({"sh", "bash", "zsh", "dash", "ash", "ksh"})


def _shell_c_payload(seg: str) -> str:
    """Return the `-c <payload>` argument of a shell launcher segment, or "".

    Handles `-c payload`, combined short flags `-lc payload` (the `c` may be the
    last letter of a short-flag cluster), and `--command payload`. Quotes are
    removed by shlex so the payload is the inner command string.
    """
    try:
        toks = shlex.split(seg, posix=True)
    except ValueError:
        toks = seg.split()
    for j, t in enumerate(toks):
        is_c = t == "-c" or t == "--command" or (t.startswith("-") and not t.startswith("--") and t.endswith("c"))
        if is_c and j + 1 < len(toks):
            return toks[j + 1]
    return ""


def _block_public_server() -> None:
    """Emit the public-server deny decision and exit 0."""
    _block(
        f"[public-server-guard] {_PUBLIC_SERVER_DENY_MSG}",
        tool_name="Bash",
        reason=_PUBLIC_SERVER_DENY_MSG,
    )


def _scan_host_flags(seg: str, short_re: re.Pattern[str] | None = None) -> bool:
    """Return True if any host/bind flag in `seg` resolves to a public host.

    Always scans long flags (--bind/--host/--listen/--address). Additionally
    scans `short_re` (the specific short bind flag this server uses) when given.
    """
    for m in _HOST_FLAG_RE.finditer(seg):
        if _host_is_public(m.group(1)):
            return True
    if short_re is not None:
        for m in short_re.finditer(seg):
            if _host_is_public(m.group(1)):
                return True
    return False


def _check_public_dev_server_segment(segment: str, _depth: int = 0) -> None:
    """Evaluate one shell command segment; _block on a public dev-server bind."""
    seg = segment.strip()
    if not seg:
        return
    if _depth > 4:  # death-loop guard for pathological nesting (fail open: stop)
        return

    # MEDIUM-1: evaluate command-substitution bodies ($(...), `...`, <(...))
    # independently FIRST. A display command (echo/grep/…) suppresses its OWN
    # text, but a server launched inside a substitution is a real invocation
    # (`echo $(python3 -m http.server 8080)`) and must still be caught.
    sq_spans = _single_quoted_spans(seg)
    for sub in _SUBSTITUTION_RE.finditer(seg):
        # `$(...)` inside SINGLE quotes is literal data, not a real substitution
        # (`echo '$(python3 -m http.server)'`) — skip it to avoid a false positive.
        if any(start <= sub.start() < end for start, end in sq_spans):
            continue
        body = sub.group("dollar") or sub.group("back") or sub.group("proc") or ""
        if body.strip():
            for sub_seg in _SEGMENT_SPLIT_RE.split(body):
                _check_public_dev_server_segment(sub_seg, _depth + 1)

    cmd = _command_token(seg)

    # Shell launcher (`bash -c '<cmd>'`, `sh -lc '…'`): the real invocation is the
    # `-c` payload. Recurse into it (split into segments) so a server launched via
    # a shell wrapper is still caught. The payload was a quoted token, so shlex
    # tokenization reconstructs it; the launcher itself is then not a server.
    if cmd in _SHELL_LAUNCHERS:
        payload = _shell_c_payload(seg)
        if payload:
            for sub_seg in _SEGMENT_SPLIT_RE.split(payload):
                _check_public_dev_server_segment(sub_seg, _depth + 1)
        return

    # A pure display/search command quoting a server string is data, not an
    # invocation — suppress the outer text (substitutions were already handled).
    if _DISPLAY_CMD_RE.match(seg.lstrip("'\"")):
        return

    # python http.server: block by default unless an explicit loopback --bind.
    if _PY_HTTP_SERVER_RE.search(seg):
        m = _PY_BIND_RE.search(seg)
        if m is None or _host_is_public(m.group(1)):
            _block_public_server()
        return  # explicit loopback bind → allow

    # php: two server forms only. `php -S <host>` (built-in server; block on a
    # non-loopback host) and `php artisan serve --host=…` (Laravel dev server).
    # A plain `php script.php --host …` CLI script is NOT a server — its --host is
    # the script's own arg, so host flags are scanned ONLY for `artisan serve`.
    if cmd == "php":
        m = _PHP_SERVER_RE.search(seg)
        if m and _host_is_public(m.group(1)):
            _block_public_server()
            return
        if _PHP_ARTISAN_SERVE_RE.search(seg) and _scan_host_flags(seg):
            _block_public_server()
        return

    # Resolve the effective server name. A python web server may be launched via
    # its own console script (`flask run`, `uvicorn`, `gunicorn`) OR as a module
    # (`python3 -m flask run`); the module form maps the interpreter token to the
    # module name so it is still anchored to a real invocation.
    server = cmd
    mod = _PY_MODULE_RE.match(_strip_leading_prefixes(seg))
    if mod and mod.group(1).lower() in _PY_WEB_SERVERS:
        server = mod.group(1).lower()

    # Known servers anchored at the COMMAND token (or `-m <module>` for python web
    # servers): client-side JS/static dev servers, node task runners
    # (npm/pnpm/yarn/bun run), and python web servers (flask/uvicorn/gunicorn).
    # Block ONLY on an EXPLICIT public bind/host flag — bare `vite` / `npm run dev`
    # default to localhost → allow (no false positive).
    is_known_server = server in _JS_DEV_SERVERS or server in _NODE_RUNNERS or server in _PY_WEB_SERVERS
    if not is_known_server:
        return

    # Command token is a known server, so this server's specific short bind flag
    # (if any) is safe to scan — the collision cases (git -a, curl -H, ssh -b)
    # never reach this point, and another server's short flag is not honored
    # (e.g. ng has no host short flag, so `ng build -- -a foo` is not a bind).
    if _scan_host_flags(seg, _SERVER_SHORT_FLAGS.get(server)):
        _block_public_server()
        return

    # Residual (accepted): a node runner forwarding a SHORT host flag to an unknown
    # inner dev server (`npm run dev -- -H 0.0.0.0`). The inner server is unknown,
    # so the short letter (-H/-a/-b) is ambiguous — `-a src` is a non-host arg on a
    # build script. Scanning it generically over-blocks routine `npm run … -- -a`,
    # which would re-introduce the very false positives this PR removes. The LONG
    # form (`-- --host 0.0.0.0`, the documented case) IS caught above, as is the
    # direct server form (`next dev -H 0.0.0.0`). Left as a documented residual.


def check_public_dev_server(command: str) -> None:
    """Block raw dev servers bound to non-loopback interfaces.

    Block-by-default for `python -m http.server` / SimpleHTTPServer (which bind
    0.0.0.0 by default) unless an explicit loopback --bind is present. Also block
    any dev server given an explicit public --bind/--host/--listen/--address/-H/
    -b/-a, and `php -S` on a non-loopback host. Allow loopback binds, deployment
    tooling (nginx/caddy/etc.), display/search commands that merely quote a
    server string, and commands with no dev-server invocation.

    The command is split on shell separators and each segment is evaluated
    independently, so chained invocations are caught while quoted-string data is
    not. Detection is regex-on-text (a shared limit of every check in this gate).
    """
    if os.environ.get(_PUBLIC_SERVER_BYPASS_ENV) == "1":
        return

    for segment in _SEGMENT_SPLIT_RE.split(command):
        _check_public_dev_server_segment(segment)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main() -> None:
    raw = read_stdin(timeout=2)
    try:
        event = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return

    # Field name compatibility: try new names first, fall back to old
    tool = event.get("tool_name") or event.get("tool", "")
    tool_input = event.get("tool_input", event.get("input", {}))

    if tool == "Bash":
        command = tool_input.get("command", "")
        if not command:
            return
        check_gitignore_bypass(command)
        check_git_submission(command)
        check_dangerous_command(command)
        check_public_dev_server(command)

    elif tool == "Write":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        check_creation_gate(file_path)
        check_sensitive_file(file_path)

    elif tool == "Edit":
        file_path = tool_input.get("file_path", "")
        if not file_path:
            return
        check_sensitive_file(file_path)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise  # Let sys.exit(0) propagate normally
    except Exception as e:
        # Fail OPEN — a crashed hook must never block tools.
        print(f"[unified-gate] HOOK-CRASH: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        sys.exit(0)
