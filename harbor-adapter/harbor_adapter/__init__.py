"""Harbor adapter that invokes the /do router via a headless Claude Code CLI.

The adapter installs Node 20, the Claude Code CLI, and the claude-code-toolkit
into a Harbor-managed container, then shells out to ``claude -p`` with no agent
flag so /do performs dynamic routing inside the CLI.
"""

from harbor_adapter.claude_code_do_agent import ClaudeCodeDoAgent

__all__ = ["ClaudeCodeDoAgent"]
