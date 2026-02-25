# Claude Code CLI Container for Digital CTO
# This container provides an isolated environment for Claude Code execution

FROM python:3.12-slim

# Install system dependencies including Node.js for Claude Code
RUN apt-get update && apt-get install -y \
    git \
    github-cli \
    vim \
    curl \
    wget \
    build-essential \
    jq \
    nodejs \
    npm \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Install Claude Code CLI globally
RUN npm install -g @anthropic-ai/claude-code || \
    pip install --no-cache-dir claude-code

# Verify installation
RUN which claude || echo "claude command location varied"

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
