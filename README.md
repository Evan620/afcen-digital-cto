# 🧠 AfCEN Digital CTO

**AI-powered multi-agent technical leadership system** for the Africa Climate Energy Nexus.

The Digital CTO is a network of specialized AI agents coordinated by a central LangGraph supervisor. It reviews code, manages sprints, joins meetings, scans markets, and communicates with the CEO's personal AI ("Jarvis").

## 🚀 Phase 1: Foundation

Phase 1 delivers:
- **Automated Code Review** — Reviews every PR from Bayes Consulting against a comprehensive checklist (security, architecture, dependencies, quality)
- **GitHub Webhook Integration** — Receives PR events in real-time via webhooks
- **3-Tier Memory** — Redis (working), PostgreSQL (episodic), Qdrant (semantic)
- **LangGraph Supervisor** — Routes events to the correct sub-agent

## 📦 Quick Start

### Option A: Using the TUI (Recommended)

The Digital CTO now includes a Terminal User Interface (TUI) for easy setup and interaction.

```bash
# Install the Digital CTO
pip install -e .

# Run the onboarding wizard
cto onboard

# Start the main interface
cto
```

The TUI provides:
- 🧙 Interactive onboarding wizard
- 💬 Chat interface with all agents
- 📊 Real-time system status dashboard
- 📜 Live log viewer
- ⚙️ Configuration management

### Option B: Manual Setup

```bash
# 1. Clone & configure
cp .env.example .env
# Edit .env with your API keys (see below)

# 2. Run with Docker
docker compose up -d

# 3. Verify
curl http://localhost:8000/health
```

## 🔑 Required Configuration

Edit `.env` with:

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes* | Claude API key (preferred for code review) |
| `AZURE_OPENAI_API_KEY` | Yes* | Azure OpenAI key (alternative to Anthropic) |
| `ZAI_API_KEY` | Yes* | z.ai API key (GLM-5, OpenAI-compatible) |
| `GITHUB_TOKEN` | Yes | GitHub PAT with `repo` scope |
| `GITHUB_WEBHOOK_SECRET` | Yes | Secret for webhook HMAC verification |
| `GITHUB_REPOS` | No | Comma-separated repos to monitor (e.g., `afcen/platform`) |

*At least one LLM provider is required.

## 🧪 Run Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## 🏗️ Architecture

```
LangGraph Supervisor
  └── Code Review Agent (Phase 1)
  └── Sprint Planner (Phase 2)
  └── Market Scanner (Phase 3)
  └── Architecture Advisor (Phase 4)
```

## 📁 Project Structure

```
src/
├── main.py                 # FastAPI entrypoint + webhook endpoint
├── config.py               # Environment-based configuration
├── supervisor/graph.py     # LangGraph supervisor (event routing)
├── tui/                    # Terminal User Interface
│   ├── cli.py              # 'cto' command entry point
│   ├── main.py             # TUI orchestration
│   ├── onboard/            # Onboarding wizard
│   │   ├── wizard.py        # Wizard flow
│   │   ├── steps.py         # Individual wizard steps
│   │   └── config.py        # TUI config management
│   ├── screens/            # TUI screens
│   │   ├── menu.py          # Main menu
│   │   ├── status.py        # Status dashboard
│   │   ├── chat.py          # Chat interface
│   │   └── logs.py          # Log viewer
│   ├── components/         # Reusable components
│   │   ├── agent_selector.py
│   │   └── status_bar.py
│   └── utils/              # TUI utilities
│       ├── formatting.py    # Text styling
│       └── navigation.py    # Input handling
├── agents/code_review/     # Code Review agent
│   ├── agent.py            # LangGraph subgraph (5-step pipeline)
│   ├── prompts.py          # Review checklist prompts
│   └── tools.py            # GitHub tool wrappers
├── integrations/
│   └── github_client.py    # GitHub API (webhooks, PRs, reviews)
├── memory/
│   ├── redis_store.py      # Working memory
│   ├── postgres_store.py   # Episodic memory (audit logs)
│   └── qdrant_store.py     # Semantic memory (code embeddings)
└── models/schemas.py       # Pydantic data models
```

## 🖥️ TUI Commands

The `cto` command provides terminal-based access to the Digital CTO:

| Command | Description |
|---------|-------------|
| `cto` | Open the main TUI menu |
| `cto onboard` | Run the first-time setup wizard |
| `cto status` | Show system health status |
| `cto chat` | Open interactive chat with agents |
| `cto logs` | View real-time logs |
| `cto config` | View configuration |
| `cto doctor` | Run system diagnostics |
| `cto review <url>` | Request code review for a PR |
| `cto sprint` | Show current sprint status |
| `cto brief` | Generate morning brief |
