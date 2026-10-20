#!/usr/bin/env python3
# hook-version: 1.0.0
"""PreToolUse Bash gate: no push or PR to a repo that is not mine before a local /pr-review.

Blocks `git push` and `git subtree push` (behind `cd`, `git -C`, `GIT_DIR=`,
chains, shell keywords like `if`/`until`/`!`, wrappers like `timeout`/`sudo`/
`env`/`xargs`, and `sh -c '...'`), `gh pr create`, and `gh pr edit --base`
when the target is not mine and the commit being sent has no review record
written by /pr-review. A `git` word followed by `push` under a wrapper this
hook does not know still counts as a push. A push it cannot judge (unresolvable
`cd`/`GIT_DIR` target, `git $SUB push`) is denied.

Mine = every push URL of the target is github.com/notque/<repo> AND the repo
is not a fork. Fork: any configured remote points at another owner or host;
otherwise `gh repo view --json isFork` (disk cache, memoized per run). Unknown
counts as not mine, so a notque repo with a mirror or colleague remote, or an
ssh host alias, needs a review too (fail closed on purpose). Pushes to a local
path (`/x`, `./x`, `file://`) reach no remote and pass.

Commit checked: each pushed refspec source (default HEAD); `gh pr create
--head B` checks branch B; `gh pr edit --base` checks HEAD. Matching (`:`),
pattern, `--all`-style, `push.default=matching`, and `remote.<r>.push` pushes
are denied in repos that are not mine. A record matches one SHA in one repo
(git common dir), so stale or foreign records fail.

The whole run has a 6 s budget (hook timeout is 10 s); running out denies.

Bypass: REVIEW_PUSH_GATE_BYPASS=1 in the Claude Code process environment
(set when launching the session; a `VAR=1 git push` prefix in a command does
not reach this hook). Each bypass is logged to
~/.claude/state/review-gate/bypass.log.

Always exits 0; the deny goes out as JSON permissionDecision on stdout. A
crash after the command matched a push or `gh pr` shape denies it.
"""

import sys  # vexjoy-pyguard

if sys.version_info < (3, 10):  # vexjoy-pyguard gate
    import os

    if not os.environ.get("VEXJOY_PYGUARD_REEXEC"):
        os.environ["VEXJOY_PYGUARD_REEXEC"] = "1"
        for _d in [*os.environ.get("PATH", "").split(os.pathsep), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"]:
            for _v in ("14", "13", "12", "11", "10"):
                _p = os.path.join(_d, "python3." + _v)
                if _d and "/shims" not in _d and os.access(_p, os.X_OK):
                    os.execv(_p, [_p, *sys.argv])
    sys.stderr.write(
        "[vexjoy] hook %s needs Python 3.10+, got %s (%s); run ./install.sh in vexjoy-agent from a terminal"
        " outside Claude Code (gated tool calls stay blocked until then)\n"
        % (__file__.rsplit("/", 1)[-1], sys.version.split()[0], sys.executable)
    )
    sys.exit(2)

import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
import review_record
from stdin_timeout import read_stdin

_BYPASS_ENV = "REVIEW_PUSH_GATE_BYPASS"
HOOK = "review-before-push-gate"
MY_OWNER = "notque"
MY_HOST = "github.com"
FORK_CACHE_TTL = 7 * 24 * 3600
GH_TIMEOUT = 4
# Total budget per run, well under the 10 s hook timeout: a hook killed by the
# timeout is a non-blocking error, so the command would run.
DEADLINE_SECONDS = 6.0
review_record.GIT_TIMEOUT = 2

_QUICK_RE = re.compile(r"\bpush\b|\bgh\b")
# Commands this hook judges; a crash after one matches is a deny.
_GATED_RE = re.compile(r"\bpush\b|\bgh\b[^\n;&|]*\bpr\b")
_PUNCT = "();&|{}"
_SHELLS = {"sh", "bash", "zsh", "fish", "dash", "ksh"}
# Shell words that start a segment but are not the command.
_KEYWORDS = {"if", "then", "elif", "else", "do", "while", "until", "!", "fi", "done", "{", "}"}
# Segment heads with no command after them.
_SKIP_HEADS = {"for", "case", "select", "function", "esac", "in"}
# Wrapper commands: (options that take a value, positional args before the command).
_WRAPPERS: dict[str, tuple[frozenset[str], int]] = {
    "nohup": (frozenset(), 0),
    "builtin": (frozenset(), 0),
    "exec": (frozenset({"-a"}), 0),
    "command": (frozenset(), 0),
    "time": (frozenset({"-f", "-o", "--format", "--output"}), 0),
    "timeout": (frozenset({"-s", "--signal", "-k", "--kill-after"}), 1),
    "nice": (frozenset({"-n", "--adjustment"}), 0),
    "sudo": (
        frozenset({"-u", "-g", "-h", "-p", "-C", "-U", "-r", "-t", "-D", "-R", "-T", "--user", "--group", "--chdir"}),
        0,
    ),
    "doas": (frozenset({"-u", "-C"}), 0),
    "env": (frozenset({"-u", "--unset", "-C", "--chdir", "-S", "--split-string"}), 0),
    "xargs": (
        frozenset({"-I", "-n", "-P", "-L", "-d", "-a", "-E", "-s", "--max-args", "--max-procs", "--delimiter"}),
        0,
    ),
    "caffeinate": (frozenset({"-t", "-w"}), 0),
    "stdbuf": (frozenset({"-i", "-o", "-e"}), 0),
    "ionice": (frozenset({"-c", "-n", "-p", "-P", "-u"}), 0),
    "chronic": (frozenset(), 0),
    "unbuffer": (frozenset(), 0),
    "watch": (frozenset({"-n", "--interval"}), 0),
    "flock": (frozenset({"-w", "--timeout", "-E", "--conflict-exit-code"}), 1),
    "taskset": (frozenset(), 1),
    "chrt": (frozenset(), 1),
    "torsocks": (frozenset(), 0),
    "proxychains": (frozenset(), 0),
    "proxychains4": (frozenset(), 0),
}
_GIT_VALUE_OPTS = {
    "-C",
    "-c",
    "--config-env",
    "--exec-path",
    "--git-dir",
    "--namespace",
    "--super-prefix",
    "--work-tree",
}
_PASS_OPTS = {"-c", "--git-dir", "--work-tree", "--namespace", "--config-env"}
_GIT_ENV = {"GIT_DIR": "--git-dir", "GIT_WORK_TREE": "--work-tree"}
_PUSH_VALUE_OPTS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
_PUSH_MULTI = {"--all", "--mirror", "--tags", "--branches"}
_GH_PR_GATED = {"create", "edit"}
_REDIRECT_RE = re.compile(r"^\d*(>>?|<<?|>&|<&|&>)")
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
_SUBST_RE = re.compile(r"\$\(([^()]*)\)|`([^`]*)`")
_ENV_ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)
_GH_REMOTE_ORDER = {"upstream": 0, "github": 1, "origin": 2}
_ACTION = {
    "push": "git push",
    "subtree": "git subtree push",
    "unresolved": "git push",
    "gh-create": "gh pr create",
    "gh-edit": "gh pr edit --base",
}

# Set once main() sees a push or `gh pr` shape; a crash after that denies.
_GATED: dict[str, str] = {}
_DEADLINE = [0.0]
_FORK_MEMO: dict[str, bool | None] = {}


class DeadlineHit(Exception):
    pass


class Invocation:
    def __init__(
        self,
        kind: str,
        cwd: str | None,
        args: list[str],
        git_opts: list[str] | None = None,
        problem: str = "",
    ):
        self.kind = kind  # push, subtree, unresolved, gh-create, gh-edit
        self.cwd = cwd
        self.args = args
        self.git_opts = git_opts or []
        self.problem = problem  # set when the command cannot be judged; always a deny


# --------------------------------------------------------------------------
# Command parsing
# --------------------------------------------------------------------------


class ParseError(Exception):
    pass


def _strip_heredocs(command: str) -> str:
    """Drop heredoc bodies so their text is not parsed as commands."""
    out: list[str] = []
    terminator: str | None = None
    for line in command.split("\n"):
        if terminator is not None:
            if line.strip() == terminator:
                terminator = None
            continue
        out.append(line)
        m = _HEREDOC_RE.search(line)
        if m:
            terminator = m.group(2)
    return "\n".join(out)


def _newlines_to_semicolons(command: str) -> str:
    """Unquoted newlines separate commands; shlex would treat them as spaces."""
    out: list[str] = []
    quote: str | None = None
    escaped = False
    for ch in command:
        if escaped:
            escaped = False
        elif ch == "\\" and quote != "'":
            escaped = True
        elif quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "\n":
            ch = ";"
        out.append(ch)
    return "".join(out)


class Where:
    """Effective directory of a command: a path, or why it cannot be known."""

    def __init__(self, path: str | None, problem: str = ""):
        self.path = path
        self.problem = problem


def _resolve_dir(base: Where, path: str, what: str = "cd") -> Where:
    if base.problem:
        return base
    if (
        path == "-"
        or "$" in path
        or "`" in path
        or (path.startswith("~") and path != "~" and not path.startswith("~/"))
    ):
        return Where(None, f"cannot resolve the `{what}` target `{path}`")
    p = Path(os.path.expanduser(path))
    if not p.is_absolute():
        if not base.path:
            return Where(None, f"cannot resolve the `{what}` target `{path}`")
        p = Path(base.path) / p
    norm = os.path.normpath(str(p))
    if not os.path.isdir(norm):
        return Where(None, f"the `{what}` target `{path}` does not exist")
    return Where(norm)


def _drop_redirects(argv: list[str]) -> list[str]:
    out: list[str] = []
    skip = False
    for tok in argv:
        if skip:
            skip = False
            continue
        m = _REDIRECT_RE.match(tok)
        if m:
            skip = tok == m.group(0)  # bare operator: the target is the next token
            continue
        out.append(tok)
    return out


def _skip_options(argv: list[str], values: frozenset[str]) -> tuple[int, list[tuple[str, str]]]:
    """Index of the first non-option word after argv[0], plus (option, value) pairs seen."""
    seen: list[tuple[str, str]] = []
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--":
            return i + 1, seen
        if a in values:
            seen.append((a, argv[i + 1] if i + 1 < len(argv) else ""))
            i += 2
            continue
        if a.startswith("--") and "=" in a:
            name, _, val = a.partition("=")
            seen.append((name, val))
            i += 1
            continue
        if a.startswith("-") and len(a) > 1:
            if a[:2] in values:  # value attached: -n5, -I{}
                seen.append((a[:2], a[2:]))
            i += 1
            continue
        return i, seen
    return i, seen


def _strip_prefixes(argv: list[str], where: Where) -> tuple[list[str], dict[str, str], Where]:
    """Drop shell keywords, env assignments, and wrapper commands in front of the real command."""
    assigns: dict[str, str] = {}
    while argv:
        head = argv[0]
        name = os.path.basename(head)
        m = _ENV_ASSIGN_RE.match(head)
        if head in _KEYWORDS or head == "$":
            argv = argv[1:]
        elif m:
            assigns[m.group(1)] = m.group(2)
            argv = argv[1:]
        elif name in _WRAPPERS:
            values, positionals = _WRAPPERS[name]
            i, seen = _skip_options(argv, values)
            for opt, val in seen:
                if name == "env" and opt in {"-C", "--chdir"}:
                    where = _resolve_dir(where, val, "env -C")
            if name in {"env", "sudo"}:
                while i < len(argv) and (am := _ENV_ASSIGN_RE.match(argv[i])):
                    assigns[am.group(1)] = am.group(2)
                    i += 1
            argv = argv[i + positionals :]
        else:
            break
    return argv, assigns, where


def _git_env_opts(env: dict[str, str], where: Where) -> tuple[list[str], str]:
    """`--git-dir=`/`--work-tree=` options for GIT_DIR/GIT_WORK_TREE, or a problem."""
    opts: list[str] = []
    for var, flag in _GIT_ENV.items():
        val = env.get(var)
        if val is None:
            continue
        if "$" in val or "`" in val or not (os.path.isabs(val) or where.path):
            return [], f"cannot resolve `{var}={val}`"
        opts.append(f"{flag}={os.path.normpath(os.path.join(where.path or '', os.path.expanduser(val)))}")
    return opts, ""


def parse_invocations(command: str, cwd: str | None, depth: int = 0, env: dict | None = None) -> list[Invocation]:
    """Every gated invocation in *command*, in shell order, with its effective cwd."""
    text = _newlines_to_semicolons(_strip_heredocs(command))
    # `2>&1` would otherwise lex as `2>` `&` `1` and split the segment.
    text = re.sub(r"(?<![\w&])\d*>&(\d+|-)", " ", text)
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=_PUNCT)
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError as exc:
        raise ParseError(str(exc)) from exc

    found: list[Invocation] = []
    state = {"where": Where(cwd) if isinstance(cwd, str) or cwd is None else cwd, "env": dict(env or {})}
    stack: list[tuple[Where, dict]] = []
    segment: list[str] = []

    def execute(raw: list[str]) -> None:
        if depth < 3:
            # Command substitutions run even inside double quotes: `echo "$(git push)"`.
            for tok in raw:
                for inner in _SUBST_RE.findall(tok):
                    found.extend(parse_invocations(inner[0] or inner[1], state["where"], depth + 1, state["env"]))
        argv, assigns, where = _strip_prefixes(_drop_redirects(raw), state["where"])
        if not argv:
            # A bare `GIT_DIR=x` sets a shell variable; treat it as effective (fail toward the right repo).
            state["env"].update({k: v for k, v in assigns.items() if k in _GIT_ENV})
            return
        name = os.path.basename(argv[0])
        if name in _SKIP_HEADS:
            return
        if name in {"cd", "pushd"}:
            state["where"] = _resolve_dir(state["where"], argv[1] if len(argv) > 1 else "~", name)
            return
        if name == "export":
            for word in argv[1:]:
                am = _ENV_ASSIGN_RE.match(word)
                if am and am.group(1) in _GIT_ENV:
                    state["env"][am.group(1)] = am.group(2)
            return
        if name == "unset":
            for word in argv[1:]:
                state["env"].pop(word, None)
            return
        cmd_env = {**state["env"], **{k: v for k, v in assigns.items() if k in _GIT_ENV}}
        if name == "eval" and depth < 3:
            found.extend(parse_invocations(" ".join(argv[1:]), where, depth + 1, cmd_env))
            return
        if name in _SHELLS and depth < 3:
            for i, tok in enumerate(argv[1:-1], start=1):
                if tok == "-c" or (tok.startswith("-") and not tok.startswith("--") and "c" in tok[1:]):
                    found.extend(parse_invocations(argv[i + 1], where, depth + 1, cmd_env))
                    break
            return
        if name == "git":
            _parse_git(argv, where, cmd_env, found)
            return
        if name == "gh":
            _parse_gh(argv, where, found)
            return
        # Backstop: an unknown wrapper in front of `git ... push` or `gh ... pr`.
        for i in range(1, len(argv)):
            tail = argv[i:]
            base = os.path.basename(argv[i])
            if base == "git" and "push" in tail[1:]:
                before = len(found)
                _parse_git(tail, where, cmd_env, found)
                if len(found) == before:
                    found.append(
                        Invocation(
                            "unresolved",
                            where.path,
                            [],
                            problem=f"`{argv[0]}` runs `git` with `push` in its arguments and the push cannot be judged",
                        )
                    )
                return
            if base == "gh" and "pr" in tail[1:]:
                _parse_gh(tail, where, found)
                return

    for tok in [*tokens, ";"]:
        if tok and all(c in _PUNCT for c in tok):
            execute(segment)
            segment = []
            for c in tok:
                if c == "(":
                    stack.append((state["where"], dict(state["env"])))
                elif c == ")" and stack:
                    state["where"], state["env"] = stack.pop()
            continue
        segment.append(tok)
    return found


def _parse_git(argv: list[str], where: Where, env: dict[str, str], found: list[Invocation]) -> None:
    git_where = where
    opts, env_problem = _git_env_opts(env, where)
    i = 1
    while i < len(argv):
        arg = argv[i]
        if arg in _GIT_VALUE_OPTS and i + 1 < len(argv):
            if arg == "-C":
                git_where = _resolve_dir(git_where, argv[i + 1], "git -C")
            elif arg in _PASS_OPTS:
                opts += [arg, argv[i + 1]]
            i += 2
            continue
        if arg.startswith("--") and "=" in arg:
            if arg.split("=", 1)[0] in _PASS_OPTS:
                opts.append(arg)
            i += 1
            continue
        if arg.startswith("-"):
            i += 1
            continue
        rest = argv[i + 1 :]
        problem = git_where.problem or env_problem
        if arg == "push":
            found.append(Invocation("push", git_where.path, rest, opts, problem))
        elif arg == "subtree" and "push" in rest:
            found.append(Invocation("subtree", git_where.path, rest[rest.index("push") + 1 :], opts, problem))
        elif ("$" in arg or "`" in arg) and "push" in rest:
            found.append(
                Invocation("unresolved", git_where.path, [], problem=f"cannot tell which git command `{arg}` runs")
            )
        return


def _is_base_flag(arg: str) -> bool:
    return arg in {"-B", "--base"} or arg.startswith(("--base=", "-B"))


def _parse_gh(argv: list[str], where: Where, found: list[Invocation]) -> None:
    rest = argv[1:]
    # gh takes --repo before the subcommand too: `gh -R o/r pr create`.
    lead: list[str] = []
    while rest and rest[0].startswith("-"):
        lead.append(rest[0])
        rest = rest[1:]
        if lead[-1] in {"-R", "--repo"} and rest:
            lead.append(rest[0])
            rest = rest[1:]
    if len(rest) >= 2 and rest[0] == "pr" and rest[1] in _GH_PR_GATED:
        if rest[1] == "edit" and not any(_is_base_flag(a) for a in rest[2:]):
            return  # title/body/label edits add no code
        found.append(Invocation(f"gh-{rest[1]}", where.path, lead + rest[2:], problem=where.problem))


# --------------------------------------------------------------------------
# Remote classification
# --------------------------------------------------------------------------

_SCP_RE = re.compile(r"^(?:[^@/]+@)?([^:/]+):(?!//)(.+)$")
_URL_RE = re.compile(r"^[a-z][a-z0-9+.-]*://(?:[^@/]+@)?([^/:]+)(?::\d+)?/(.+)$", re.IGNORECASE)


def is_local_path(url: str) -> bool:
    return url in {".", ".."} or url.startswith(("/", "./", "../", "~/", "file://"))


def parse_slug(url: str) -> tuple[str, str, str] | None:
    """(host, owner, repo) for a GitHub-style URL, or None when unparseable."""
    url = url.strip()
    m = _URL_RE.match(url) or _SCP_RE.match(url)
    if not m:
        return None
    host, path = m.group(1).lower(), m.group(2).strip("/")
    path = path.removesuffix(".git")
    parts = path.split("/")
    if len(parts) != 2 or not all(parts):
        return None
    return host, parts[0], parts[1]


def parse_repo_flag(value: str) -> tuple[str, str, str] | None:
    """`gh --repo` value: OWNER/REPO, HOST/OWNER/REPO, or a URL."""
    if "://" in value or "@" in value:
        return parse_slug(value)
    parts = value.strip("/").split("/")
    if len(parts) == 2 and all(parts):
        return MY_HOST, parts[0], parts[1].removesuffix(".git")
    if len(parts) == 3 and all(parts):
        return parts[0].lower(), parts[1], parts[2].removesuffix(".git")
    return None


def _is_my_slug(slug: tuple[str, str, str] | None) -> bool:
    return bool(slug) and slug[0] == MY_HOST and slug[1].lower() == MY_OWNER


def _norm_key(key: str) -> str:
    """git config keys: section and variable are case-insensitive, the subsection is not."""
    if key.count(".") < 2:
        return key.lower()
    first, rest = key.split(".", 1)
    middle, _, last = rest.rpartition(".")
    return f"{first.lower()}.{middle}.{last.lower()}"


class RepoConfig:
    """Parsed `git config -l -z` for one repo."""

    def __init__(self, cwd: str | None, git_opts: list[str]):
        self.entries: list[tuple[str, str]] = []
        proc = review_record.git(["config", "-l", "-z"], cwd, git_opts)
        if proc.returncode != 0:
            return
        for item in proc.stdout.split("\0"):
            if item:
                key, _, value = item.partition("\n")
                self.entries.append((_norm_key(key), value))

    def get(self, key: str) -> str | None:
        vals = self.get_all(key)
        return vals[-1] if vals else None

    def get_all(self, key: str) -> list[str]:
        return [v for k, v in self.entries if k == key]

    def remotes(self) -> list[str]:
        names: list[str] = []
        for k, _ in self.entries:
            if k.startswith("remote.") and k.endswith((".url", ".pushurl")):
                name = k[len("remote.") : k.rfind(".")]
                if name not in names:
                    names.append(name)
        return names

    def _rewrite(self, url: str, kind: str) -> str | None:
        best: tuple[str, str] | None = None
        for k, v in self.entries:
            if k.startswith("url.") and k.endswith("." + kind) and url.startswith(v):
                if best is None or len(v) > len(best[1]):
                    best = (k[len("url.") : -len("." + kind)], v)
        return best[0] + url[len(best[1]) :] if best else None

    def push_urls(self, remote: str) -> list[str]:
        """URLs `git push <remote>` would contact, after insteadOf rewrites."""
        pushurls = self.get_all(f"remote.{remote}.pushurl")
        if pushurls:
            return [self._rewrite(u, "insteadof") or u for u in pushurls]
        urls = self.get_all(f"remote.{remote}.url") or [remote]
        return [self._rewrite(u, "pushinsteadof") or self._rewrite(u, "insteadof") or u for u in urls]

    def rewrite_fetch(self, url: str) -> str:
        return self._rewrite(url, "insteadof") or url

    def all_urls(self) -> list[str]:
        urls: list[str] = []
        for name in self.remotes():
            urls += self.push_urls(name)
            urls += [self._rewrite(u, "insteadof") or u for u in self.get_all(f"remote.{name}.url")]
        return urls


def _fork_cache_path() -> Path:
    return Path.home() / ".claude" / "state" / "review-gate" / "fork-cache.json"


def _remaining() -> float:
    return _DEADLINE[0] - time.monotonic() if _DEADLINE[0] else DEADLINE_SECONDS


def _gh_is_fork(owner: str, repo: str) -> bool | None:
    """isFork, memoized per run, from the disk cache or `gh repo view`; None when unknown (never cached on disk)."""
    key = f"{owner}/{repo}".lower()
    if key not in _FORK_MEMO:
        _FORK_MEMO[key] = _gh_is_fork_uncached(key)
    return _FORK_MEMO[key]


def _gh_is_fork_uncached(key: str) -> bool | None:
    path = _fork_cache_path()
    try:
        cache = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    if not isinstance(cache, dict):
        cache = {}
    hit = cache.get(key)
    if isinstance(hit, dict) and isinstance(hit.get("is_fork"), bool):
        try:
            fresh = time.time() - float(hit.get("checked_at", 0)) < FORK_CACHE_TTL
        except (TypeError, ValueError):
            fresh = False
        if fresh:
            return hit["is_fork"]
    budget = min(GH_TIMEOUT, _remaining() - 0.5)
    if budget <= 0.2:
        raise DeadlineHit(f"no time left to check whether {key} is a fork")
    try:
        proc = subprocess.run(
            ["gh", "repo", "view", key, "--json", "isFork", "--jq", ".isFork"],
            capture_output=True,
            text=True,
            timeout=budget,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        if _remaining() <= 0.5:
            raise DeadlineHit(f"checking whether {key} is a fork took too long") from exc
        return None
    except (OSError, subprocess.SubprocessError):
        return None
    answer = proc.stdout.strip()
    if proc.returncode != 0 or answer not in {"true", "false"}:
        return None
    is_fork = answer == "true"
    cache[key] = {"is_fork": is_fork, "checked_at": time.time()}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        tmp.write_text(json.dumps(cache, indent=1), encoding="utf-8")
        os.replace(tmp, path)
    except OSError:
        pass
    return is_fork


def classify(target_urls: list[str], config: RepoConfig) -> tuple[bool, str]:
    """(mine, reason). Not mine on any doubt."""
    slugs = [parse_slug(u) for u in target_urls]
    if not target_urls or not all(_is_my_slug(s) for s in slugs):
        return False, "target is not a github.com/notque repo"
    repos = {(s[1].lower(), s[2].lower()) for s in slugs if s}
    if len(repos) != 1:
        return False, "target has push URLs for several notque repos"
    for url in config.all_urls():
        if not is_local_path(url) and not _is_my_slug(parse_slug(url)):
            return False, f"the repo also has a non-notque remote ({url}), so it is a fork"
    owner, repo = next(iter(repos))
    is_fork = _gh_is_fork(owner, repo)
    if is_fork is None:
        return False, f"could not confirm {owner}/{repo} is not a fork"
    if is_fork:
        return False, f"{owner}/{repo} is a fork"
    return True, "notque non-fork"


# --------------------------------------------------------------------------
# Per-invocation evaluation
# --------------------------------------------------------------------------


class Verdict:
    def __init__(self, allow: bool, target: str = "", reason: str = "", problem: str = ""):
        self.allow = allow
        self.target = target
        self.reason = reason
        self.problem = problem
        self.missing: list[str] = []


def _current_branch(cwd: str | None, opts: list[str]) -> str | None:
    proc = review_record.git(["symbolic-ref", "-q", "--short", "HEAD"], cwd, opts)
    return (proc.stdout.strip() or None) if proc.returncode == 0 else None


def _push_plan(inv: Invocation, config: RepoConfig) -> tuple[list[str], list[str] | None, str]:
    """(target urls, source revs or None when nothing is sent, problem)."""
    remote: str | None = None
    positional: list[str] = []
    delete = dry = multi = False
    args = inv.args
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            positional += args[i + 1 :]
            break
        if a in _PUSH_VALUE_OPTS and i + 1 < len(args):
            if a == "--repo":
                remote = args[i + 1]
            i += 2
            continue
        if a.startswith("--repo="):
            remote = a.split("=", 1)[1]
        elif a in {"-d", "--delete"}:
            delete = True
        elif a in {"-n", "--dry-run"}:
            dry = True
        elif a in _PUSH_MULTI:
            multi = True
        elif a.startswith("-") and not a.startswith("--") and len(a) > 2:
            for j, letter in enumerate(a[1:], start=1):
                if letter == "o":  # -o takes a value: the rest of the word, or the next word
                    if j == len(a) - 1:
                        i += 1
                    break
                delete |= letter == "d"
                dry |= letter == "n"
        elif not a.startswith("-"):
            positional.append(a)
        i += 1
    if remote is None and positional:
        remote = positional.pop(0)

    if remote is None:
        branch = _current_branch(inv.cwd, inv.git_opts)
        remote = (
            (branch and config.get(f"branch.{branch}.pushremote"))
            or config.get("remote.pushdefault")
            or (branch and config.get(f"branch.{branch}.remote"))
            or "origin"
        )
    urls = config.push_urls(remote)
    if dry or delete:
        return urls, None, ""
    many = "push many refs; push one reviewed ref by name, like `git push origin <branch>`"
    if multi:
        return urls, [], f"--all, --mirror, --tags, and --branches {many}"
    if not positional:
        if config.get_all(f"remote.{remote}.push"):
            return urls, [], f"`remote.{remote}.push` is set, so a bare push may {many}"
        if (config.get("push.default") or "").lower() == "matching":
            return urls, [], f"`push.default=matching` would {many}"
    srcs: list[str] = []
    for spec in positional or ["HEAD"]:
        spec = spec.lstrip("+")
        if spec in {"", ":"}:
            return urls, [], f"the matching refspec `:` would {many}"
        if "*" in spec:
            return urls, [], f"the pattern refspec `{spec}` would {many}"
        src = spec.split(":", 1)[0]
        if src:
            srcs.append(src)
    return urls, srcs, ""


def _subtree_plan(inv: Invocation, config: RepoConfig) -> tuple[list[str], list[str], str]:
    """`git subtree push [opts] <remote> <ref>` sends commits split from HEAD."""
    positional: list[str] = []
    i = 0
    while i < len(inv.args):
        a = inv.args[i]
        if a in {"-P", "--prefix", "-m", "--message", "--onto", "--annotate"}:
            i += 2
            continue
        if not a.startswith("-"):
            positional.append(a)
        i += 1
    if not positional:
        return [], [], "cannot tell which remote `git subtree push` targets"
    return config.push_urls(positional[0]), ["HEAD"], ""


def _gh_plan(inv: Invocation, config: RepoConfig) -> tuple[list[str], list[str], str]:
    repo_flag: str | None = None
    head: str | None = None
    args = inv.args
    i = 0
    while i < len(args):
        a = args[i]
        if a in {"-R", "--repo", "-H", "--head"} and i + 1 < len(args):
            if a in {"-R", "--repo"}:
                repo_flag = args[i + 1]
            else:
                head = args[i + 1]
            i += 2
            continue
        if a.startswith("--repo="):
            repo_flag = a.split("=", 1)[1]
        elif a.startswith("--head="):
            head = a.split("=", 1)[1]
        elif a.startswith("-R") and len(a) > 2:
            repo_flag = a[2:]
        i += 1
    if repo_flag is not None:
        slug = parse_repo_flag(repo_flag)
        urls = [f"https://{slug[0]}/{slug[1]}/{slug[2]}"] if slug else [repo_flag]
    else:
        names = config.remotes()
        resolved = [n for n in names if config.get(f"remote.{n}.gh-resolved") == "base"]
        if not resolved:
            resolved = sorted(names, key=lambda n: _GH_REMOTE_ORDER.get(n, 9))
        raw = config.get_all(f"remote.{resolved[0]}.url") if resolved else []
        urls = [config.rewrite_fetch(u) for u in raw]
    src = head.split(":", 1)[-1] if inv.kind == "gh-create" and head else "HEAD"
    return urls, [src], ""


def _resolve_src(src: str, cwd: str | None, opts: list[str], *, branch_like: bool) -> str | None:
    for rev in [f"refs/heads/{src}", src] if branch_like else [src]:
        sha = review_record.resolve_commit(rev, cwd, opts)
        if sha:
            return sha
    if branch_like:
        proc = review_record.git(["for-each-ref", "--format=%(objectname)", f"refs/remotes/*/{src}"], cwd, opts)
        shas = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
        if len(shas) == 1:
            return shas.pop()
    return None


def _identity_and_shas(inv: Invocation, srcs: list[str]) -> tuple[str | None, list[str | None]]:
    """Repo identity and each source's commit SHA; one git call in the common case."""
    if inv.kind != "gh-create":
        proc = review_record.git(
            ["rev-parse", "--git-common-dir", *[f"{s}^{{commit}}" for s in srcs]], inv.cwd, inv.git_opts
        )
        lines = proc.stdout.splitlines()
        if proc.returncode == 0 and len(lines) == len(srcs) + 1 and all(len(x) >= 40 for x in lines[1:]):
            common = lines[0]
            if not os.path.isabs(common):
                common = os.path.join(inv.cwd or os.getcwd(), common)
            return os.path.realpath(common), list(lines[1:])
    identity = review_record.repo_identity(inv.cwd, inv.git_opts)
    if not identity:
        return None, []
    branch_like = inv.kind == "gh-create"
    return identity, [_resolve_src(s, inv.cwd, inv.git_opts, branch_like=branch_like) for s in srcs]


def evaluate(inv: Invocation) -> Verdict:
    if inv.problem:
        return Verdict(False, "an unknown repo", "the command cannot be judged", problem=inv.problem)
    config = RepoConfig(inv.cwd, inv.git_opts)
    if inv.kind == "push":
        urls, srcs, problem = _push_plan(inv, config)
    elif inv.kind == "subtree":
        urls, srcs, problem = _subtree_plan(inv, config)
    else:
        urls, srcs, problem = _gh_plan(inv, config)
    target = ", ".join(urls) or "an unknown repo"
    if inv.kind in {"push", "subtree"} and urls and all(is_local_path(u) for u in urls):
        return Verdict(True, target, "local path")
    mine, reason = classify(urls, config)
    if mine:
        return Verdict(True, target, reason)
    if srcs is None:
        return Verdict(True, target, "nothing is sent (delete or dry run)")
    if problem:
        return Verdict(False, target, reason, problem=problem)
    identity, shas = _identity_and_shas(inv, srcs)
    if not identity:
        return Verdict(False, target, reason, problem="the working directory is not a git repository")
    verdict = Verdict(False, target, reason)
    for src, sha in zip(srcs, shas):
        if not sha:
            verdict.problem = f"cannot resolve {src!r} to a local commit"
            return verdict
        if review_record.read_record(identity, sha) is None:
            verdict.missing.append(sha)
    verdict.allow = not verdict.missing
    return verdict


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

_STEPS = (
    "Nothing reaches a repo that is not mine before a local review. Do this: (1) commit locally; "
    "(2) run /pr-review on that local commit; (3) fix every Critical and Important finding and commit the fixes; "
    "(4) run /pr-review again on the new commit until it is clean; (5) retry the push, then open the PR."
)
_UNJUDGED = (
    "Write the push as a plain command with literal paths, like `git -C <dir> push <remote> <branch>`, "
    "so the gate can see which repo and commit it sends."
)


def deny_message(inv: Invocation, v: Verdict) -> str:
    if inv.problem:
        return f"[{HOOK}] blocked `{_ACTION[inv.kind]}`: {inv.problem}. {_UNJUDGED} {_STEPS}"
    head = f"[{HOOK}] blocked `{_ACTION[inv.kind]}` to {v.target}: {v.reason}."
    if v.problem:
        why = f" {v.problem[0].upper()}{v.problem[1:]}."
    else:
        why = f" Commit {', '.join(s[:12] for s in v.missing)} has no local review record."
    return f"{head}{why} {_STEPS}"


def _deny(reason: str, command: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.stdout.flush()
    try:
        from hook_utils import record_governance

        record_governance(
            "approval_requested",
            hook_name=HOOK,
            tool_name="Bash",
            hook_phase="pre",
            severity="medium",
            blocked=True,
            command=command,
        )
    except Exception:
        pass


def _log_bypass(cwd: str | None, command: str) -> None:
    line = json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "cwd": cwd, "command": command[:300]})
    try:
        path = Path.home() / ".claude" / "state" / "review-gate" / "bypass.log"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    print(f"[{HOOK}] BYPASSED via {_BYPASS_ENV}=1 (logged): {command[:120]}", file=sys.stderr)


def main() -> None:
    raw = read_stdin(timeout=2)
    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        return
    if not isinstance(data, dict):
        return
    tool_input = data.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not _QUICK_RE.search(command):
        return
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else os.getcwd()
    _DEADLINE[0] = time.monotonic() + DEADLINE_SECONDS
    if _GATED_RE.search(command):
        _GATED["command"] = command

    try:
        invocations = parse_invocations(command, cwd)
    except ParseError:
        # Shell text shlex cannot split that still names a gated action: fail closed.
        if not re.search(r"\bgit\b.*\bpush\b|\bgh\b.*\bpr\s+(create|edit)\b", command, re.S):
            return
        if os.environ.get(_BYPASS_ENV) == "1":
            _log_bypass(cwd, command)
            return
        _deny(
            f"[{HOOK}] could not parse this command (unbalanced quotes?) and it looks like a push or PR. "
            f"Split it into plain commands. {_STEPS}",
            command,
        )
        return
    if not invocations:
        return
    _GATED["command"] = command

    if os.environ.get(_BYPASS_ENV) == "1":
        _log_bypass(cwd, command)
        return

    for inv in invocations:
        try:
            if _remaining() <= 0.5:
                raise DeadlineHit("the checks ran out of time")
            verdict = evaluate(inv)
        except DeadlineHit as exc:
            _deny(f"[{HOOK}] blocked `{_ACTION[inv.kind]}`: {exc}, so it cannot be judged. Retry; {_STEPS}", command)
            return
        if not verdict.allow:
            print(f"[{HOOK}] BLOCKED {_ACTION[inv.kind]} -> {verdict.target}", file=sys.stderr)
            _deny(deny_message(inv, verdict), command)
            return


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception as e:
        print(f"[{HOOK}] HOOK-CRASH: {type(e).__name__}: {e}", file=sys.stderr)
        if _GATED:
            _deny(
                f"[{HOOK}] crashed while checking this push or PR ({type(e).__name__}: {e}), so it is blocked. {_STEPS}",
                _GATED["command"],
            )
    finally:
        sys.exit(0)
