# AfCEN Digital CTO - Sub-Agent Specifications

The Digital CTO Supervisor routes tasks to five specialized sub-agents.

---

## 1. Code Review Agent

**Purpose:** Automated PR analysis, security scanning, architectural compliance

### Capabilities
- Analyzes PRs from Bayes Consulting and internal developers
- Constructs knowledge graph of entire AfCEN repository
- Evaluates code against architectural standards
- Detects security vulnerabilities (race conditions, unauthorized access)
- Verifies MFA protocols and security requirements from SOW
- Auto-rejects PRs using deprecated libraries or missing security controls

### Tool Connections
- GitHub MCP server (read repos, PRs, issues)
- PR-Agent (CodiumAI, self-hosted Docker)
- CodeQL / Semgrep for security scanning
- Claude Code CLI for deep codebase understanding

### Workflow
```
PR Opened → GitHub Webhook → FastAPI Receiver →
Code Review Agent analyzes diff →
PR-Agent provides line-by-line review →
Synthesize findings → Post review comment →
Approve / Request Changes
```

### Estimated Cost
$150-300/month for 20-30 PRs/week

### Data Models (Required)

```python
class SprintMetrics(BaseModel):
    """Sprint velocity and health metrics."""
    sprint_id: str
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
    summary: str
    metrics: SprintMetrics
    completed: list[DeliverableStatus]
    blocked: list[DeliverableStatus]
    overdue: list[DeliverableStatus]
    recommendations: list[str]
    bayes_deliverable_status: dict[str, Any]  # Specific tracking for Bayes
```

---

## 2. Sprint Planner Agent

**Purpose:** Sprint management, velocity tracking, Bayes Consulting oversight

### Capabilities
- Maintains sprint iterations in GitHub Projects V2
- Assigns issues to team members using labels
- Calculates velocity from completed story points
- Generates automated sprint reports
- Monitors Bayes deliverables against $527,807 SOW budget
- Tracks time-to-completion against estimates
- Flags overdue items automatically

### Tool Connections
- GitHub MCP server (GraphQL API for Projects V2)
- PostgreSQL for historical sprint data

### Bayes Consulting Labels
- `bayes-assigned` - Assigned to Bayes team
- `bayes-in-progress` - Currently being worked on
- `bayes-review` - Awaiting CTO review
- `bayes-blocked` - Blocked on dependencies

### Sprint Report Structure
1. Sprint summary
2. Velocity metrics
3. Completed items
4. Blocked items
5. Overdue items
6. Bayes-specific deliverable status
7. Recommendations

---

## 3. DevOps & CI/CD Agent

**Purpose:** Pipeline monitoring, deployment management, infrastructure health

### Capabilities
- Monitors GitHub Actions pipeline results
- Tracks production health via Sentry
- Triggers deployments via workflow_dispatch
- Manages infrastructure monitoring alerts
- Watches for failing builds, security scan results
- Detects performance regressions

### Tool Connections
- GitHub MCP (Actions API)
- Sentry MCP server (error tracking)
- Azure/AWS monitoring APIs

### Alert Categories
- Build failures
- Test failures
- Security vulnerabilities
- Performance degradation
- Deployment failures

---

## 4. Market Scanner Agent

**Purpose:** Commercialization intelligence, daily morning briefs

### Capabilities
- Aggregates data from multiple sources overnight
- Synthesizes structured morning briefing
- Identifies partnership opportunities
- Tracks competitor activities
- Monitors regulatory changes

### Data Sources

| Category | Sources |
|----------|---------|
| News | Feedly Enterprise, RSS feeds (ESI Africa, Carbon Pulse, Devex, Reuters Africa) |
| DFI Opportunities | World Bank Projects API, AfDB Data Portal, IFC project database |
| Carbon Markets | Verra registry, Gold Standard registry |
| Policy | EUR-Lex API (EUDR), Google Alerts |
| Research | OpenAlex API, Semantic Scholar API |
| Social | Twitter/X API (#ClimateFinance, #AfricanEnergy, #CarbonMarkets) |

### African-Specific Sources
- IRENA (renewable energy statistics)
- Africa Energy Portal (energydata.info)
- GET.invest Finance Catalyst
- Power Africa/USAID
- OECD Climate Finance database
- AUDA-NEPAD (direct relationship)

### Morning Brief Structure
1. **Market Moves** - Overnight developments
2. **Policy Updates** - Regulatory changes
3. **Funding & Partnership Opportunities** - DFI, investor activity
4. **Competitive Intelligence** - Market positioning
5. **Meeting Follow-ups** - Context for day's meetings
6. **Recommended Actions** - Decision-ready suggestions

### Pipeline Schedule
- 3:00 AM EAT: Data collection triggers
- 4:00-5:30 AM: Processing and synthesis
- 6:00 AM: Brief delivered via email + stored in vector DB

---

## 5. Architecture Advisor Agent

**Purpose:** Strategic technical decisions, infrastructure recommendations

### Capabilities
- Evaluates technology choices
- Reviews system designs
- Assesses technical debt
- Proposes infrastructure improvements
- Models cost implications
- Creates zero-downtime migration plans

### Decision Types
- Technology stack selection
- Database migrations (e.g., relational → vector)
- Cloud infrastructure changes
- Security architecture updates
- Performance optimization strategies

### Output Format
```python
class ArchitectureRecommendation(BaseModel):
    """Technical decision with rationale."""
    decision_id: str
    title: str
    context: str  # What triggered this analysis
    options_considered: list[dict]  # Options with pros/cons
    recommendation: str  # Final recommendation
    rationale: str  # Why this option
    cost_implications: dict
    timeline: str
    risks: list[str]
    migration_plan: str | None  # For infrastructure changes
    approval_status: Literal["pending", "approved", "rejected"]
    decision_trace_id: str  # For future reference
```

---

## Sub-Agent Communication Protocol

All sub-agents communicate ONLY through the CTO Supervisor:

```
┌─────────────────────────────────────────┐
│           CTO SUPERVISOR                │
│                                         │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐  │
│  │Agent A  │ │Agent B  │ │Agent C  │  │
│  └────┬────┘ └────┬────┘ └────┬────┘  │
│       │           │           │        │
│       └───────────┼───────────┘        │
│                   │                    │
│            Supervisor only             │
│            (no peer-to-peer)           │
└─────────────────────────────────────────┘
```

### Prohibited Patterns
- ❌ Direct agent-to-agent communication
- ❌ Decentralized decision making
- ❌ Infinite reasoning loops

### Required Patterns
- ✅ All communication through Supervisor
- ✅ Deterministic routing
- ✅ Centralized state management
- ✅ Human-in-the-loop for high-stakes decisions
