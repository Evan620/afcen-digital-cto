# AfCEN Digital CTO - Architectural Blueprint

## Overview

The Digital CTO is an advanced, multi-agent orchestration system for the Africa Climate Energy Nexus (AfCEN). It translates plain-language executive directives into rigorous software architecture, autonomously codes applications, supervises third-party vendors (Bayes Consulting), ingests context from meetings, and identifies commercialization opportunities through market scanning.

## Core Architecture: Hierarchical Multi-Agent Supervisor

The Digital CTO uses the **Supervisor Pattern** built on LangGraph. It operates as a central orchestrator managing a network of specialized worker agents.

```
┌─────────────────────────────────────────────────────────────┐
│                    DIGITAL CTO AGENT                         │
│                  (LangGraph Supervisor)                       │
│                                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ ┌──────┐ │
│  │Code Review│ │ Sprint   │ │DevOps &  │ │Market │ │Arch  │ │
│  │  Agent    │ │ Planner  │ │CI/CD     │ │Scanner│ │Advisor│ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───┬───┘ └──┬───┘ │
│       └─────────────┴────────────┴───────────┴────────┘     │
│                         │                                    │
│  ┌──────────────────────┴──────────────────────────────────┐ │
│  │              3-TIER MEMORY LAYER                         │ │
│  │  Working: Redis  │  Episodic: PostgreSQL  │  Semantic:  │ │
│  │  (active state)  │  (decisions, meetings) │  Qdrant     │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────┬───────────────────┬───────────────────────────┘
               │                   │
    ┌──────────┴───────┐   ┌──────┴──────────────────────┐
    │  MCP TOOL MESH   │   │  JARVIS COMMUNICATION       │
    │  ├─ GitHub MCP   │   │  ├─ Redis Streams (async)   │
    │  ├─ Slack MCP    │   │  ├─ REST API (sync)         │
    │  ├─ Database MCP │   │  ├─ Shared PostgreSQL       │
    │  ├─ Filesystem   │   │  ├─ Shared Qdrant           │
    │  └─ Memory MCP   │   │  └─ Cloudflare Tunnel       │
    └──────────────────┘   └─────────────────────────────┘
```

## Supervisor Pattern Mechanics

1. **Intent Analysis**: CTO parses high-level request (e.g., "Build a landing page for the new Agribusiness TWG")
2. **Delegation**: Partitions request, assigning sub-tasks to specialized agents
3. **Strict Quality Review**: Evaluates output against architectural standards and security protocols
4. **Aggregation and Deployment**: Aggregates codebase, compiles application, reports to CEO

## Model Context Protocol (MCP)

MCP functions as a universal translation layer allowing AI models to dynamically discover, inspect, and securely invoke external tools and data sources.

### Key MCP Servers

| Server | Purpose |
|--------|---------|
| GitHub MCP | Read repositories, monitor CI/CD, merge PRs |
| Jira MCP | Generate epic tickets, update task statuses |
| Database MCP | Query PostgreSQL, manage migrations |
| Slack MCP | Send notifications, receive commands |
| Memory MCP | Access vector store, episodic memory |

### Benefits

- Solves "context window crisis" - selectively query only necessary files
- Reduces latency and API inference costs
- Vendor-neutral protocol for tool integration

## Technology Stack

| Component Layer | Protocol / Framework | Primary Function |
|-----------------|---------------------|------------------|
| Orchestration Engine | LangGraph / PydanticAI | Hierarchical Supervisor Pattern, state management |
| Tool Integration | MCP | Standardized access to GitHub, Jira, Azure, etc. |
| Code Generation | SWE-agent / OpenDevin / Claude Code | Autonomous coding in sandboxed environments |
| Security Scanning | CodeQL / Semgrep | Automated vulnerability detection |
| LLM Provider | Azure OpenAI / Anthropic Claude | Primary reasoning engines |
| Working Memory | Redis | Active state, inter-agent messaging |
| Episodic Memory | PostgreSQL | Decisions, meetings, audit trails |
| Semantic Memory | Qdrant | Vector embeddings, context retrieval |

## Five Sub-Agents

1. **Code Review Agent** - PR analysis, security scanning, architectural compliance
2. **Sprint Planner Agent** - Sprint management, velocity tracking, Bayes oversight
3. **DevOps & CI/CD Agent** - Pipeline monitoring, deployment management
4. **Market Scanner Agent** - Commercialization intelligence, morning briefs
5. **Architecture Advisor Agent** - Technical decisions, infrastructure recommendations

See [SUBAGENTS.md](./SUBAGENTS.md) for detailed specifications.

## Key Design Principles

1. **No decentralized peer-to-peer communication** among sub-agents
2. **Human-in-the-Loop (HITL)** for high-stakes decisions
3. **Progressive autonomy** - start as assistant, expand scope with trust
4. **Plain-language interface** for CEO interaction
5. **Context engineering** - selective retrieval over massive context windows
