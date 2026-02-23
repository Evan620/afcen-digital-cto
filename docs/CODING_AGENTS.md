# AfCEN Digital CTO - Coding Agent Orchestration

## Overview

The Digital CTO doesn't write code itself—it orchestrates specialized coding agents matched to task complexity. This tiered approach maximizes cost-effectiveness.

## Tiered Deployment Strategy

### Tier 1: Quick Fixes and Small Changes

**Tool:** Aider (open-source, CLI-scriptable)
**Cost:** $0.01-0.05 per task
**Use Case:** Bug fixes, small refactors, documentation updates

```bash
# Invocation via Python subprocess
aider --message "fix the timezone bug in solar_agent.py" \
      --yes-always --auto-commits
```

**Capabilities:**
- Understands git repos
- Creates proper commits
- Almost zero cost to run

---

### Tier 2: Feature Implementation and Refactoring

**Tool:** Claude Code (Anthropic's terminal agent)
**Cost:** ~$3-15/MTok
**Use Case:** New features, significant refactoring, multi-file changes

```bash
# CLI invocation
claude -p "implement the EUDR compliance checker endpoint" \
       --allowedTools bash,write,read
```

**Capabilities:**
- Reads entire codebases
- Edits multiple files
- Runs tests autonomously
- Creates commits
- Most transparent agent (every action visible)

---

### Tier 3: Complex Autonomous Tasks

**Tool:** Devin (Cognition AI)
**Cost:** $500/month or ~$0.02-0.05/minute
**Use Case:** Complex multi-step tasks, full feature development

**Capabilities:**
- Fully sandboxed environment
- Own browser, terminal, editor
- Most autonomous
- Best for: "Set up the entire CI/CD pipeline for the new microservice"

**Trade-offs:**
- Most expensive
- Least transparent
- Reserve for high-complexity tasks

---

### Tier 4: Issue Resolution

**Tool:** SWE-Agent 2.0 (Princeton NLP, open-source)
**Cost:** Free (self-hosted)
**Use Case:** Well-defined bug reports with reproduction steps

```python
from sweagent import SWEAgent

agent = SWEAgent()
result = agent.run(issue)
```

**Performance:** Resolves ~12-18% of real GitHub issues autonomously

---

### Tier 5: Rapid Prototyping

**Tool:** OpenHands (formerly OpenDevin, open-source)
**Cost:** Free (self-hosted)
**Use Case:** Proof-of-concept applications, prototypes

**Capabilities:**
- Docker-based (fits existing AfCEN infrastructure)
- Full development environment
- REST API accessible
- Good for quick experiments

---

## Task Routing Logic

```python
class CodingTask(BaseModel):
    """Incoming coding task."""
    task_id: str
    description: str
    complexity: Literal["trivial", "simple", "moderate", "complex", "very_complex"]
    estimated_files: int
    requires_testing: bool
    requires_deployment: bool
    cost_sensitivity: Literal["low", "medium", "high"]
    autonomy_level: Literal["supervised", "semi_autonomous", "fully_autonomous"]

def route_coding_task(task: CodingTask) -> str:
    """Route task to appropriate coding agent."""

    if task.complexity == "trivial" or task.cost_sensitivity == "high":
        return "aider"

    elif task.complexity in ["simple", "moderate"] and task.autonomy_level != "fully_autonomous":
        return "claude_code"

    elif task.complexity == "complex" and task.autonomy_level == "fully_autonomous":
        return "devin"

    elif task.description.startswith("fix") and "reproduction" in task.description.lower():
        return "swe_agent"

    elif "prototype" in task.description.lower() or "proof of concept" in task.description.lower():
        return "openhands"

    else:
        return "claude_code"  # Default
```

---

## Quality Gate: Mandatory Review

**Every coding agent's output goes through the Code Review Agent before merging.**

```
┌─────────────────────────────────────────────────────┐
│                 CODING AGENT                         │
│         (Aider / Claude Code / Devin / etc.)        │
└─────────────────────┬───────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────┐
│            CODE REVIEW AGENT                         │
│   (Architecture compliance, security, quality)       │
└─────────────────────┬───────────────────────────────┘
                      │
               ┌──────┴──────┐
               │             │
          PASS ▼             ▼  FAIL
    ┌─────────────┐    ┌─────────────────────────────┐
    │   MERGE     │    │  RETURN TO CODING AGENT     │
    │   TO MAIN   │    │  with specific fix requests │
    └─────────────┘    └─────────────────────────────┘
```

**The Digital CTO never merges code it hasn't reviewed.**

---

## Estimated Monthly Costs by Usage

| Usage Level | Aider | Claude Code | Devin | Total |
|-------------|-------|-------------|-------|-------|
| Light (5 tasks/week) | $5 | $50 | $0 | $55 |
| Moderate (15 tasks/week) | $15 | $150 | $100 | $265 |
| Heavy (30 tasks/week) | $30 | $300 | $500 | $830 |

---

## Security Considerations

### Sandboxed Execution
- All coding agents run in isolated Docker containers
- No direct access to production databases
- No access to sensitive credentials
- Network access controlled via firewall rules

### Code Signing
- All commits signed with dedicated agent key
- Audit trail of which agent made which changes
- Rollback capability for any agent-generated code

### Scope Limitations
- Agents cannot modify `.env` files
- Agents cannot access billing/financial systems
- Agents cannot create new users or permissions
- All external API calls require CTO approval
