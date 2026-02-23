# AfCEN Digital CTO - JARVIS Integration

## Overview

The Digital CTO must communicate with JARVIS (the CEO's OpenClaw-based agent on a Mac Mini) through reliable, secure channels that handle both real-time synchronization and asynchronous task delegation.

## Three Communication Layers

### Layer 1: Redis Streams (Asynchronous Messaging)

**Primary channel for async communication.**

Unlike basic Redis Pub/Sub, Streams persist messages and support replay—critical when the Mac Mini goes offline (sleep, restart, network issues).

#### Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `strategic.directive` | CEO → CTO | High-level business directives |
| `tech.decision.request` | CEO → CTO | Request for technical decision |
| `tech.decision.response` | CTO → CEO | Decision with rationale |
| `implementation.plan` | CTO → CEO | Proposed implementation approach |
| `status.update` | Bidirectional | Progress updates |
| `escalation.human` | Either → Joseph | Requires human intervention |

#### Message Format

```python
class JarvisMessage(BaseModel):
    """Inter-agent message format."""
    message_id: str  # UUID
    message_type: str  # From types above
    timestamp: datetime
    sender: Literal["jarvis", "digital_cto"]
    recipient: Literal["jarvis", "digital_cto"]
    payload: dict
    idempotency_key: str  # Prevent duplicate processing
    signature: str  # HMAC-SHA256
    requires_response: bool
    priority: Literal["low", "normal", "high", "urgent"]
```

### Layer 2: REST API (Synchronous Requests)

**For immediate response scenarios.**

JARVIS on Mac Mini exposes a lightweight FastAPI endpoint through **Cloudflare Tunnel** (free, zero-configuration, no port forwarding).

#### Use Cases
- CTO needs CEO approval for high-stakes actions
- JARVIS needs immediate status from CTO
- Time-sensitive queries

#### Endpoints

```python
# On JARVIS (Mac Mini)
POST /api/v1/approval
POST /api/v1/query
GET  /api/v1/status

# On Digital CTO (Cloud)
POST /api/v1/directive
POST /api/v1/task
GET  /api/v1/health
```

### Layer 3: Shared State (PostgreSQL + Qdrant)

**Passive synchronization through shared databases.**

Both agents read from and write to shared database tables:

| Table | Purpose |
|-------|---------|
| `decision_log` | Technical decisions with rationale |
| `task_board` | Shared task tracking |
| `context_history` | Historical context for reference |
| `meeting_memory` | Meeting summaries and action items |
| `escalation_queue` | Items requiring human attention |

**Shared Qdrant Vector Store:**
- Organizational knowledge learned by either agent
- Immediately queryable by the other
- Enables context continuity across agents

## Conflict Resolution Protocol

Based on proven patterns from Project Martin's Secretariat Martin:

### Resolution Flow

```
┌─────────────────────────────────────────────────────┐
│        CONFLICT DETECTED                            │
│   (agents receive conflicting directives)           │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│        AUTOMATED DEBATE CYCLE                       │
│   Each agent presents constraints + alternatives    │
└─────────────────┬───────────────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│        RESOLUTION ATTEMPT                           │
│   Can agents reach consensus?                       │
└─────────────────┬───────────────────────────────────┘
                  │
         ┌────────┴────────┐
         │                 │
    YES  ▼                 ▼  NO
┌─────────────┐    ┌─────────────────────────────────┐
│  Execute    │    │  ESCALATE TO JOSEPH             │
│  agreed     │    │  - Full context provided        │
│  solution   │    │  - Both positions documented    │
└─────────────┘    │  - Awaiting human decision      │
                   └─────────────────────────────────┘
```

### Authority Boundaries

| Domain | Authority |
|--------|-----------|
| Technical implementation details | CTO |
| Business strategy and priorities | CEO |
| Budget decisions >$10K | CEO (requires approval) |
| Vendor management | CTO (within SOW), CEO (changes) |
| Product features | CEO (prioritization), CTO (feasibility) |
| Security protocols | CTO (technical), CEO (policy) |

## Human-in-the-Loop (HITL) Checkpoints

### Actions Requiring CEO Approval

- Deploying to production
- Changing system architecture
- External communications
- Payments to vendors
- Strategic technical decisions
- Partner communications
- Contract modifications

### HITL Workflow

```python
class ApprovalRequest(BaseModel):
    """Request for human approval."""
    request_id: str
    action_type: str
    summary: str  # Plain language summary
    proposed_action: str
    rationale: str
    risk_assessment: dict
    alternatives_considered: list[str]
    urgency: Literal["low", "normal", "high"]
    timeout: datetime  # When to escalate if no response
    context: dict  # Supporting information
```

## Future: Google A2A Protocol

**Target: Phase 4 implementation**

Google's Agent-to-Agent (A2A) protocol (released April 9, 2025) is purpose-built for cross-agent, cross-vendor communication.

### Benefits
- Standardized agent discovery via "Agent Cards"
- JSON capability descriptions at `/.well-known/agent.json`
- Future-proof for adding CFO, COO agents
- Backed by 50+ partners (Salesforce, SAP, Atlassian, LangChain)

### Migration Path
1. Keep Redis + REST for Phase 2-3
2. Implement A2A in Phase 4
3. Publish Agent Cards for both JARVIS and Digital CTO
4. Enable automatic capability discovery
