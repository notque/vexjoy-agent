# Harbor container image for the /do router benchmark.
#
# Harbor launches tasks inside a container. This Dockerfile defines the
# baseline image; the BaseInstalledAgent.install() method layers Node,
# Claude Code, and the toolkit on top at job start so the image can stay
# small and cacheable.
#
# Keep this image minimal: anything agent-specific belongs in
# ClaudeCodeDoAgent.install(), not here.

FROM ubuntu:24.04

# Non-interactive apt for reproducible builds.
ENV DEBIAN_FRONTEND=noninteractive \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Baseline tooling used by terminal-bench tasks and the install step.
# git and curl are needed by BaseInstalledAgent.install() itself; the rest
# are common enough that having them preinstalled trims install-phase wall
# time for every task.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        build-essential \
        python3 \
        python3-pip \
        python3-venv \
        jq \
        sudo \
        vim-tiny \
    && rm -rf /var/lib/apt/lists/*

# Harbor expects an "agent" user that exec_as_agent runs commands as.
RUN useradd --create-home --shell /bin/bash agent \
    && mkdir -p /logs /workspace \
    && chown -R agent:agent /logs /workspace

# /logs is where ClaudeCodeDoAgent.run() drops claude-stdout.json,
# claude-stderr.log, and claude-exit-code. Harbor also writes
# /logs/verifier/reward.txt at task end.
VOLUME ["/logs", "/workspace"]

USER agent
WORKDIR /workspace

# Sanity check only. The real CLI install happens in
# BaseInstalledAgent.install() so the image is reusable across toolkit
# versions without a rebuild.
CMD ["/bin/bash"]
