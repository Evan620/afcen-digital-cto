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

### 1. Clone & configure
```bash
cp .env.example .env
# Edit .env with your API keys (see below)
```

### 2. Run with Docker
```bash
docker compose up -d
```

### 3. Verify
```bash
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
