# Claude Code CLI Container for Digital CTO
# This container provides an isolated environment for Claude Code execution

FROM python:3.12-slim

# Install system deps + add GitHub CLI apt source (not in default Debian repos)
RUN apt-get update && apt-get install -y \
    git \
    vim \
    curl \
    wget \
    build-essential \
    jq \
    docker.io \
    gpg \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       | gpg --dearmor -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y gh \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 22 LTS (Debian slim ships outdated nodejs/npm)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code

# Verify installations
RUN claude --version && gh --version && node --version

# Create workspace directory
WORKDIR /workspace

# Set up environment
ENV PYTHONUNBUFFERED=1
ENV CLAUDE_DISABLE_ANALYTICS=1
ENV NODE_ENV=production

# Create a non-root user for execution (but allow Docker access)
RUN useradd -m -u 1000 -s /bin/bash claude && \
    usermod -aG docker claude && \
    chown -R claude:claude /workspace

USER claude

# Keep container running for on-demand tasks
CMD ["tail", "-f", "/dev/null"]
