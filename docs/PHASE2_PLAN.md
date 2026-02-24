# Phase 2 Implementation Plan: Sprint Management & OpenClaw Integration

## Architecture Decision: OpenClaw Node Host (Most Reliable & Secure)

After analyzing three options (OpenClaw Node Host, Redis Streams + REST, Hybrid), we chose **OpenClaw Node Host** because:

| Criteria | OpenClaw Node Host | Why It Wins |
|----------|-------------------|-------------|
| **Reliability** | ⭐⭐⭐⭐⭐ | Battle-tested with 17 agents, auto-reconnection, message queuing |
| **Security** | ⭐⭐⭐⭐⭐ | Approval workflow, token auth, Docker isolation, no public endpoints |
| **Complexity** | ⭐⭐⭐⭐⭐ | Uses existing infrastructure, no new components |

### Security Benefits

- **Isolation:** CTO's memory stores are NOT accessible from Mac mini agents
- **Approval workflow:** Admin must explicitly approve each node connection
- **Blast radius:** If CTO compromised, attacker only has CTO data, not org data
- **Audit logging:** All cross-boundary messages are logged by OpenClaw

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Mac mini (Trusted Zone)                       │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │              OpenClaw Gateway (:18789)                        │ │
│   │                                                              │ │
│   │   • Token authentication                                     │ │
│   │   • Node approval workflow                                   │ │
│   │   • Message queuing (offline resilience)                     │ │
│   │   • Audit logging                                            │ │
│   └──────────────────────────────────────────────────────────────┘ │
│                              │                                      │
│   ┌──────────────────────────┴───────────────────────────────────┐ │
│   │                    17 Trusted Agents                          │ │
│   │   JARVIS · MANSA · VAULT · ECHO-OPS · AEGIS · etc.           │ │
│   └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                               │
                               │ WebSocket (authenticated, encrypted)
                               │
┌──────────────────────────────┴──────────────────────────────────────┐
│                     Docker Container (Isolated Zone)                 │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐ │
│   │              OpenClaw Node Host                               │ │
│   │                                                              │ │
│   │   • Must be approved by admin                                │ │
│   │   • Scoped capabilities: code_review, sprint_planning, etc.  │ │
│   │   • All actions logged                                       │ │
│   └──────────────────────────────────────────────────────────────┘ │
│                              │                                      │
│   ┌──────────────────────────┴───────────────────────────────────┐ │
│   │                  Digital CTO Agents                           │ │
│   │   Code Review · Sprint Planner · Architecture Advisor        │ │
│   │                      (LangGraph Supervisor)                   │ │
│   └──────────────────────────────────────────────────────────────┘ │
│                              │                                      │
│   ┌──────────────────────────┴───────────────────────────────────┐ │
│   │              Isolated Memory Stores                           │ │
│   │   Redis (working) · PostgreSQL (episodic) · Qdrant (semantic)│ │
│   │                                                              │ │
│   │   NOT accessible from Mac mini agents                        │ │
│   │   Data stays in container                                    │ │
│   └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### Communication Flow (Secure)

```
1. Joseph asks JARVIS: "What's the sprint status?"
   └── Message stays in trusted zone (Mac mini)

2. JARVIS sends to Digital CTO via sessions_send
   └── Authenticated, logged, approved channel

3. Digital CTO queries its own PostgreSQL
   └── Data never leaves Docker container

4. Digital CTO sends summary back to JARVIS
   └── Only the ANSWER is transmitted, not raw data

5. JARVIS presents to Joseph
   └── Human sees result, never raw database
```

---

## Phase 2 Goals

| Goal | Description |
|------|-------------|
| **1. OpenClaw Integration** | Connect Digital CTO to OpenClaw Gateway via Node Host |
| **2. Sprint Planner Agent** | Build agent for sprint management and Bayes oversight |
| **3. JARVIS Communication** | Enable bidirectional messaging with JARVIS agent |
| **4. CEO Interface** | Joseph can issue plain-language commands via JARVIS → CTO |

---

## Week-by-Week Breakdown

### Week 5: OpenClaw Node Host Integration

#### Tasks
- [ ] Add OpenClaw Node Host to Docker container
- [ ] Configure connection to Mac mini Gateway
- [ ] Test bidirectional communication
- [ ] Register Digital CTO as "digital-cto" agent in OpenClaw

#### Code Changes

**1. Update Dockerfile**
```dockerfile
# Add OpenClaw Node Host
RUN npm install -g openclaw

# Add startup script
COPY scripts/start-node.sh /scripts/
RUN chmod +x /scripts/start-node.sh
```

**2. Create Node Host Startup Script**
```bash
#!/bin/bash
# scripts/start-node.sh

# Start the Digital CTO FastAPI server
uvicorn src.main:app --host 0.0.0.0 --port 8000 &

# Connect to OpenClaw Gateway
openclaw node run \
  --host ${OPENCLAW_GATEWAY_HOST:-host.docker.internal} \
  --port ${OPENCLAW_GATEWAY_PORT:-18789} \
  --display-name "Digital CTO" \
  --capabilities "code_review,sprint_planning,architecture_advice,market_scanning"

# Keep container running
wait
```

**3. Update docker-compose.yml**
```yaml
services:
  cto-app:
    # ... existing config ...
    environment:
      - OPENCLAW_GATEWAY_HOST=${OPENCLAW_GATEWAY_HOST:-host.docker.internal}
      - OPENCLAW_GATEWAY_PORT=${OPENCLAW_GATEWAY_PORT:-18789}
      - OPENCLAW_GATEWAY_TOKEN=${OPENCLAW_GATEWAY_TOKEN}
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

#### Acceptance Criteria
- [ ] Digital CTO appears in `openclaw nodes list`
- [ ] JARVIS can send messages to Digital CTO
- [ ] Digital CTO can respond to JARVIS
- [ ] Tasks can be routed from OpenClaw to Digital CTO

---

### Week 6: Sprint Planner Agent

#### Tasks
- [ ] Create Sprint Planner sub-agent
- [ ] Implement GitHub Projects V2 integration
- [ ] Build Bayes deliverable tracking
- [ ] Create sprint report generation

#### Code Structure

**1. Create Agent Directory**
```
src/agents/sprint_planner/
├── __init__.py
├── agent.py           # LangGraph subgraph
├── prompts.py         # Sprint analysis prompts
├── tools.py           # GitHub Projects tools
└── models.py          # Sprint data models
```

**2. Data Models (src/agents/sprint_planner/models.py)**
```python
from pydantic import BaseModel
from datetime import datetime
from typing import Literal

class SprintMetrics(BaseModel):
    """Sprint velocity and health metrics."""
    sprint_id: str
    sprint_name: str
    start_date: datetime
    end_date: datetime
    total_story_points: int
    completed_story_points: int
    velocity: float  # points per day
    blocked_items: int
    overdue_items: int

class DeliverableStatus(BaseModel):
    """Status of a vendor deliverable."""
    deliverable_id: str
    title: str
    vendor: str  # e.g., "Bayes Consulting"
    status: Literal["not_started", "in_progress", "review", "done", "blocked"]
    due_date: datetime
    assigned_to: str
    story_points: int
    labels: list[str]  # e.g., ["bayes-assigned", "bayes-in-progress"]
    github_issue_id: int | None
    github_pr_id: int | None

class SprintReport(BaseModel):
    """Generated sprint report."""
    sprint_id: str
    generated_at: datetime
    summary: str
    metrics: SprintMetrics
    completed: list[DeliverableStatus]
    blocked: list[DeliverableStatus]
    overdue: list[DeliverableStatus]
    bayes_status: dict  # Bayes-specific tracking
    recommendations: list[str]

class SprintPlannerState(TypedDict):
    """State for Sprint Planner agent."""
    action: str  # "generate_report", "track_bayes", "get_status"
    repository: str
    sprint_id: str | None
    report: SprintReport | None
    bayes_deliverables: list[DeliverableStatus]
    recommendations: list[str]
    error: str | None
```

**3. Agent Implementation (src/agents/sprint_planner/agent.py)**
```python
"""
Sprint Planner Agent — LangGraph subgraph for sprint management.

Flow:
  1. Receive sprint query
  2. Fetch GitHub Projects V2 data
  3. Calculate metrics
  4. Track Bayes deliverables
  5. Generate report
"""

from langgraph.graph import StateGraph, END
from .models import SprintPlannerState, SprintReport, DeliverableStatus

async def fetch_sprint_data(state: SprintPlannerState) -> dict:
    """Fetch sprint data from GitHub Projects V2."""
    # TODO: Implement GitHub Projects V2 API calls
    pass

async def calculate_metrics(state: SprintPlannerState) -> dict:
    """Calculate sprint velocity and health metrics."""
    # TODO: Implement metric calculations
    pass

async def track_bayes_deliverables(state: SprintPlannerState) -> dict:
    """Track Bayes Consulting deliverables against SOW."""
    # TODO: Implement Bayes tracking
    pass

async def generate_sprint_report(state: SprintPlannerState) -> dict:
    """Generate comprehensive sprint report."""
    # TODO: Implement report generation
    pass

def build_sprint_planner_graph() -> StateGraph:
    """Build the Sprint Planner agent graph."""
    graph = StateGraph(SprintPlannerState)

    graph.add_node("fetch_sprint_data", fetch_sprint_data)
    graph.add_node("calculate_metrics", calculate_metrics)
    graph.add_node("track_bayes", track_bayes_deliverables)
    graph.add_node("generate_report", generate_sprint_report)

    graph.set_entry_point("fetch_sprint_data")
    graph.add_edge("fetch_sprint_data", "calculate_metrics")
    graph.add_edge("calculate_metrics", "track_bayes")
    graph.add_edge("track_bayes", "generate_report")
    graph.add_edge("generate_report", END)

    return graph

sprint_planner_graph = build_sprint_planner_graph().compile()
```

#### Acceptance Criteria
- [ ] Can generate sprint report from GitHub Projects
- [ ] Tracks Bayes deliverables with labels
- [ ] Calculates velocity metrics
- [ ] Identifies blocked/overdue items

---

### Week 7: JARVIS Communication Layer

#### Tasks
- [ ] Implement OpenClaw sessions_send integration
- [ ] Create message handlers for JARVIS directives
- [ ] Build approval request flow for HITL
- [ ] Test CEO → JARVIS → Digital CTO flow

#### Integration Architecture

```
Joseph (Telegram)
      │
      ▼
  ┌───────┐
  │JARVIS │ (OpenClaw agent on Mac mini)
  └───┬───┘
      │ sessions_send
      │ target: "node:digital-cto"
      ▼
  ┌───────────────────────────────────────────────┐
  │           DIGITAL CTO (Docker)                │
  │                                               │
  │  ┌─────────────────────────────────────────┐ │
  │  │  OpenClaw Node Host                     │ │
  │  │  Receives: directives, queries, tasks   │ │
  │  │  Sends: reports, approvals, status      │ │
  │  └─────────────────────────────────────────┘ │
  │                      │                        │
  │                      ▼                        │
  │  ┌─────────────────────────────────────────┐ │
  │  │  LangGraph Supervisor                   │ │
  │  │  Routes to: Code Review, Sprint, etc.   │ │
  │  └─────────────────────────────────────────┘ │
  └───────────────────────────────────────────────┘
```

#### Message Types

```python
# From JARVIS to Digital CTO
class JarvisDirective(BaseModel):
    """Directive from JARVIS/CEO."""
    directive_id: str
    type: Literal[
        "sprint_report",      # Generate sprint report
        "review_pr",          # Review specific PR
        "track_bayes",        # Check Bayes deliverables
        "architecture_query", # Ask architecture question
        "approval_response",  # CEO approved/rejected something
    ]
    payload: dict
    priority: Literal["low", "normal", "high", "urgent"]
    requires_response: bool

# From Digital CTO to JARVIS
class CTOResponse(BaseModel):
    """Response to JARVIS."""
    response_to: str  # directive_id
    status: Literal["completed", "in_progress", "failed", "needs_approval"]
    result: dict | None
    approval_request: dict | None  # If needs_approval
    error: str | None
```

#### Acceptance Criteria
- [ ] Joseph can ask JARVIS: "What's the sprint status?"
- [ ] JARVIS routes to Digital CTO
- [ ] Digital CTO generates sprint report
- [ ] Report returns to JARVIS → Joseph

---

### Week 8: CEO Interface & Testing

#### Tasks
- [ ] Build plain-language query parser
- [ ] Create approval workflow for high-stakes actions
- [ ] Implement 3-tier memory integration
- [ ] End-to-end testing

#### CEO Command Examples

```
Joseph → JARVIS: "How's the sprint going?"
JARVIS → Digital CTO: {type: "sprint_report"}
Digital CTO → JARVIS: {sprint report with metrics}
JARVIS → Joseph: "Sprint 12 is 68% complete. 3 items blocked..."

---

Joseph → JARVIS: "Are Bayes on track for the Summit deadline?"
JARVIS → Digital CTO: {type: "track_bayes"}
Digital CTO → JARVIS: {Bayes deliverable status}
JARVIS → Joseph: "Bayes has 4 items overdue. The Accreditation Agent is blocked on..."

---

Joseph → JARVIS: "Review PR #42"
JARVIS → Digital CTO: {type: "review_pr", pr_number: 42}
Digital CTO → JARVIS: {review results}
JARVIS → Joseph: "PR #42 reviewed. 3 security issues found. Recommendation: Request changes."
```

#### HITL Approval Flow

```
Digital CTO wants to merge PR #42
              │
              ▼
    ┌─────────────────────┐
    │ Approval Required   │
    │ Action: Merge PR    │
    │ Risk: Production    │
    └──────────┬──────────┘
               │
               ▼
    ┌─────────────────────┐
    │ Send to JARVIS      │
    │ type: approval_req  │
    └──────────┬──────────┘
               │
               ▼
    ┌─────────────────────┐
    │ Joseph receives:    │
    │ "Merge PR #42?      │
    │  [Approve] [Reject]"│
    └──────────┬──────────┘
               │
        ┌──────┴──────┐
        │             │
    Approve         Reject
        │             │
        ▼             ▼
   Execute PR     Don't merge
    merge         (log reason)
```

#### Acceptance Criteria
- [ ] Joseph can issue plain-language commands
- [ ] HITL approvals work correctly
- [ ] All memory tiers are populated
- [ ] End-to-end flow tested

---

## Dependencies

### From Mac mini (OpenClaw)
- [ ] OpenClaw Gateway token for Node Host
- [ ] Access to Gateway port 18789
- [ ] Agent-to-agent allowlist updated with "digital-cto"

### From This Project
- [ ] Docker environment with network access to Mac mini
- [ ] GitHub Projects V2 access
- [ ] Bayes Consulting SOW document for deliverable tracking

---

## File Changes Summary

| File | Change |
|------|--------|
| `Dockerfile` | Add OpenClaw Node Host |
| `docker-compose.yml` | Add OpenClaw environment variables |
| `scripts/start-node.sh` | NEW - Node Host startup script |
| `src/agents/sprint_planner/` | NEW - Sprint Planner agent |
| `src/supervisor/graph.py` | Add Sprint Planner routing |
| `src/models/schemas.py` | Add Sprint-related models |
| `src/integrations/openclaw_client.py` | NEW - OpenClaw messaging client |

---

## Testing Checklist

### Week 5 Tests
- [ ] Node Host connects to Gateway
- [ ] Node appears in `openclaw nodes list`
- [ ] Can receive message from JARVIS
- [ ] Can send message to JARVIS

### Week 6 Tests
- [ ] Sprint Planner generates report
- [ ] Bayes deliverables tracked correctly
- [ ] Velocity calculations accurate

### Week 7 Tests
- [ ] JARVIS → CTO message flow works
- [ ] CTO → JARVIS message flow works
- [ ] Approval requests reach JARVIS

### Week 8 Tests
- [ ] End-to-end: Joseph → JARVIS → CTO → JARVIS → Joseph
- [ ] HITL approval flow works
- [ ] Memory persists across sessions

---

## Questions for User

1. **Mac mini access:** Can the Docker container reach the Mac mini on port 18789? (Same network or Tailscale?)

2. **OpenClaw token:** Do you have a Gateway token for the Node Host to authenticate?

3. **GitHub Projects:** Is AfCEN using GitHub Projects V2 for sprint management, or another tool (Jira, Linear)?

4. **Bayes SOW:** Do you have the Bayes Consulting SOW document with deliverable list for tracking?

5. **ECHO-OPS integration:** Should Digital CTO replace ECHO-OPS, or work alongside it?
