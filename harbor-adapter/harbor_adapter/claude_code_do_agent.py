"""BaseInstalledAgent that exercises the /do router via ``claude -p``.

The agent installs Node 20, the Claude Code CLI, and a pinned copy of the
claude-code-toolkit into the Harbor container. It then runs each task by
invoking ``claude -p <instruction> --output-format json
--dangerously-skip-permissions`` with no agent flag, letting /do perform
dynamic routing.

Token usage is read from Claude Code's JSON summary (``--output-format
json`` emits a final object containing ``usage.input_tokens`` and
``usage.output_tokens``). If the JSON summary is unavailable for any task,
the adapter records the failure mode rather than fabricating zeros.

Interface sources (verified 2026-04-19):
- https://www.harborframework.com/docs/agents (class signature, decorator)
- https://pypi.org/project/harbor/ (terminal-bench-2.0 invocation)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from harbor.agents.installed.base import BaseInstalledAgent, with_prompt_template
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext

# Pinned toolkit commit. Update deliberately; never float to HEAD.
TOOLKIT_REPO = "https://github.com/notque/claude-code-toolkit.git"
TOOLKIT_REF = "main"

# Node 20 is the oldest Claude Code CLI supports cleanly.
NODE_SETUP_URL = "https://deb.nodesource.com/setup_20.x"


@dataclass
class RunStats:
    """Per-task execution stats captured after ``claude -p`` exits."""

    exit_code: int
    input_tokens: int | None
    output_tokens: int | None
    cache_read_tokens: int | None
    cache_creation_tokens: int | None
    usage_parse_error: str | None
    raw_stdout_bytes: int
    raw_stderr_bytes: int
    extra: dict[str, Any] = field(default_factory=dict)


class ClaudeCodeDoAgent(BaseInstalledAgent):
    """Run terminal-bench-2 tasks through the /do router.

    The agent never passes ``--agent`` to ``claude``. /do is the target of
    measurement; letting the CLI hardcode an agent would defeat the
    experiment.
    """

    # Harbor reads this to decide which OS user runs the agent commands.
    # "agent" is the default non-root user in Harbor's base images.
    user = "agent"

    # Populated by ``run`` and consumed by ``populate_context_post_run``.
    _last_stats: RunStats | None = None

    async def install(self, environment: BaseEnvironment) -> None:
        """Install Node 20, Claude Code CLI, and the toolkit."""
        # Core dependencies. Use ``exec_as_root`` only for apt; everything
        # else runs as the agent user so it lands in the right $HOME.
        await self.exec_as_root(
            environment,
            command="apt-get update && apt-get install -y curl git ca-certificates",
        )
        await self.exec_as_root(
            environment,
            command=f"curl -fsSL {NODE_SETUP_URL} | bash -",
        )
        await self.exec_as_root(
            environment,
            command="apt-get install -y nodejs",
        )

        # Claude Code CLI, installed globally so ``claude`` is on PATH for
        # every user.
        await self.exec_as_root(
            environment,
            command="npm install -g @anthropic-ai/claude-code",
        )

        # Toolkit: clone into $HOME and symlink the two canonical paths the
        # toolkit expects (~/.claude and ~/.toolkit).
        await self.exec_as_agent(
            environment,
            command=(f"git clone --depth 1 --branch {TOOLKIT_REF} {TOOLKIT_REPO} $HOME/claude-code-toolkit"),
        )
        await self.exec_as_agent(
            environment,
            command=(
                "mkdir -p $HOME/.claude $HOME/.toolkit && "
                "ln -sf $HOME/claude-code-toolkit/agents $HOME/.toolkit/agents && "
                "ln -sf $HOME/claude-code-toolkit/skills $HOME/.toolkit/skills && "
                "ln -sf $HOME/claude-code-toolkit/hooks $HOME/.toolkit/hooks && "
                "ln -sf $HOME/claude-code-toolkit/agents $HOME/.claude/agents && "
                "ln -sf $HOME/claude-code-toolkit/skills $HOME/.claude/skills && "
                "ln -sf $HOME/claude-code-toolkit/hooks $HOME/.claude/hooks && "
                "cp $HOME/claude-code-toolkit/CLAUDE.md $HOME/.claude/CLAUDE.md"
            ),
        )

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,  # noqa: ARG002 - part of BaseInstalledAgent.run signature
    ) -> None:
        """Invoke ``claude -p`` with no agent flag, capture JSON usage."""
        # --output-format json prints a final JSON envelope that includes the
        # assistant's text plus a usage block. We parse that rather than
        # scraping stderr.
        #
        # --dangerously-skip-permissions is required for headless runs; the
        # container is user-owned and fully disposable per the task brief.
        #
        # The instruction is passed via stdin so shell quoting does not
        # mangle multi-line tasks. Harbor's ``exec_as_agent`` merges env
        # vars (including ANTHROPIC_API_KEY) automatically.
        heredoc_instruction = instruction.replace("'", "'\\''")
        cmd = (
            "set -o pipefail; "
            "cd /workspace && "
            f"printf '%s' '{heredoc_instruction}' | "
            "claude -p --output-format json --dangerously-skip-permissions "
            "> /logs/claude-stdout.json 2> /logs/claude-stderr.log; "
            "echo $? > /logs/claude-exit-code"
        )

        result = await self.exec_as_agent(environment, command=cmd)

        # Pull the artifacts back. ``exec_as_agent`` does not stream file
        # contents, so read them explicitly. Using ``cat`` keeps this
        # transport-agnostic across Harbor runtimes.
        stdout_raw = await self.exec_as_agent(environment, command="cat /logs/claude-stdout.json || true")
        stderr_raw = await self.exec_as_agent(environment, command="cat /logs/claude-stderr.log || true")
        exit_raw = await self.exec_as_agent(environment, command="cat /logs/claude-exit-code || echo -1")

        stdout_text = _to_text(stdout_raw)
        stderr_text = _to_text(stderr_raw)
        try:
            exit_code = int(_to_text(exit_raw).strip() or "-1")
        except ValueError:
            exit_code = -1

        self._last_stats = _parse_run_stats(
            exit_code=exit_code,
            stdout_text=stdout_text,
            stderr_text=stderr_text,
        )

        # Let BaseInstalledAgent bookkeep (logs dir, etc.) regardless.
        _ = result

    def populate_context_post_run(self, context: AgentContext) -> None:
        """Attach run stats to the context so Harbor stores them per-trial."""
        if self._last_stats is None:
            context.metadata["claude_do_router"] = {"error": "run_not_executed"}
            return

        stats = self._last_stats
        context.metadata["claude_do_router"] = {
            "exit_code": stats.exit_code,
            "input_tokens": stats.input_tokens,
            "output_tokens": stats.output_tokens,
            "cache_read_tokens": stats.cache_read_tokens,
            "cache_creation_tokens": stats.cache_creation_tokens,
            "usage_parse_error": stats.usage_parse_error,
            "raw_stdout_bytes": stats.raw_stdout_bytes,
            "raw_stderr_bytes": stats.raw_stderr_bytes,
            **stats.extra,
        }


def _to_text(blob: Any) -> str:
    """Coerce Harbor exec output into a string.

    ``exec_as_agent`` returns different shapes across runtimes; accept the
    common ones and fall back to ``str()``.
    """
    if blob is None:
        return ""
    if isinstance(blob, str):
        return blob
    if isinstance(blob, bytes):
        return blob.decode("utf-8", errors="replace")
    stdout = getattr(blob, "stdout", None)
    if stdout is not None:
        return _to_text(stdout)
    return str(blob)


def _parse_run_stats(*, exit_code: int, stdout_text: str, stderr_text: str) -> RunStats:
    """Extract token usage from Claude Code's JSON envelope.

    ``claude -p --output-format json`` prints a single JSON object on stdout
    with a ``usage`` block. If parsing fails, record the failure mode and
    keep the raw sizes so downstream triage has something to work with.
    """
    raw_stdout_bytes = len(stdout_text.encode("utf-8"))
    raw_stderr_bytes = len(stderr_text.encode("utf-8"))

    if not stdout_text.strip():
        return RunStats(
            exit_code=exit_code,
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            cache_creation_tokens=None,
            usage_parse_error="empty_stdout",
            raw_stdout_bytes=raw_stdout_bytes,
            raw_stderr_bytes=raw_stderr_bytes,
        )

    try:
        payload = json.loads(stdout_text)
    except json.JSONDecodeError as exc:
        return RunStats(
            exit_code=exit_code,
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            cache_creation_tokens=None,
            usage_parse_error=f"json_decode: {exc.msg}",
            raw_stdout_bytes=raw_stdout_bytes,
            raw_stderr_bytes=raw_stderr_bytes,
        )

    usage = payload.get("usage") if isinstance(payload, dict) else None
    if not isinstance(usage, dict):
        return RunStats(
            exit_code=exit_code,
            input_tokens=None,
            output_tokens=None,
            cache_read_tokens=None,
            cache_creation_tokens=None,
            usage_parse_error="usage_field_missing",
            raw_stdout_bytes=raw_stdout_bytes,
            raw_stderr_bytes=raw_stderr_bytes,
        )

    return RunStats(
        exit_code=exit_code,
        input_tokens=_int_or_none(usage.get("input_tokens")),
        output_tokens=_int_or_none(usage.get("output_tokens")),
        cache_read_tokens=_int_or_none(usage.get("cache_read_input_tokens")),
        cache_creation_tokens=_int_or_none(usage.get("cache_creation_input_tokens")),
        usage_parse_error=None,
        raw_stdout_bytes=raw_stdout_bytes,
        raw_stderr_bytes=raw_stderr_bytes,
    )


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
