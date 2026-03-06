# Agent Orchestration

## Available Agents

Located in `~/.claude/agents/`:

| Agent | Purpose | When to Use |
|-------|---------|-------------|
| planner | Implementation planning | Complex features, refactoring |
| architect | System design | Architectural decisions |
| tdd-guide | Test-driven development | New features, bug fixes |
| code-reviewer | Code review | After writing code |
| security-reviewer | Security analysis | Before commits |
| build-error-resolver | Fix build errors | When build fails |
| e2e-runner | E2E testing | Critical user flows |
| refactor-cleaner | Dead code cleanup | Code maintenance |
| doc-updater | Documentation | Updating docs |
| **qa-reviewer** | **獨立品質測試（只讀 spec，不讀程式碼）** | **Phase 5 QA** |

## ECC v2 流程中的角色對應

| Phase | Agent | 產出文件 |
|-------|-------|---------|
| Phase 0 RECEIVE | Orchestrator | `01_spec.md` |
| Phase 1 ARCHITECT | architect | `02_architecture.md` |
| Phase 2 PLAN | planner | `03_dev_plan.md` |
| Phase 3 DEV | tdd-guide | 程式碼 + 單元測試 |
| Phase 4 REVIEW | python-reviewer + security-reviewer | 審查報告 |
| Phase 5 QA | **qa-reviewer** | `04_test_plan.md` + `05_test_report.md` |
| Phase 7 DOCUMENT | doc-updater | CODEMAPS + 記憶 |

## Immediate Agent Usage

No user prompt needed:
1. Complex feature requests - Use **planner** agent
2. Code just written/modified - Use **code-reviewer** agent
3. Bug fix or new feature - Use **tdd-guide** agent
4. Architectural decision - Use **architect** agent

## Parallel Task Execution

ALWAYS use parallel Task execution for independent operations:

```markdown
# GOOD: Parallel execution
Launch 3 agents in parallel:
1. Agent 1: Security analysis of auth module
2. Agent 2: Performance review of cache system
3. Agent 3: Type checking of utilities

# BAD: Sequential when unnecessary
First agent 1, then agent 2, then agent 3
```

## Multi-Perspective Analysis

For complex problems, use split role sub-agents:
- Factual reviewer
- Senior engineer
- Security expert
- Consistency reviewer
- Redundancy checker
