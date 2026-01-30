<!-- AUTO-COMPILED AGENTS.md -->
<!-- global-hash:c3776232b73b4c34652d923c834779fb local-hash:2fa99415139399f86caa5a9b6ea07b07 context-hash:7f14024c1c43726fb9c3e9d2d8c3b202 -->
<!-- Source: ~/agent-skills/AGENTS.global.md + ./AGENTS.local.md + .claude/skills/context-*/ -->
<!-- DO NOT EDIT - edit AGENTS.local.md instead -->

# Skill Routing Table

## Global Skills
| Activation Keywords | Skill | Purpose |
|---------------------|-------|---------|
| "add database", "add postgres", "add redis", "connect database" | railway/database | This skill should be used when the user wants to add a datab... |
| "add domain", "railway domain", "custom domain", "service URL" | railway/domain | This skill should be used when the user wants to add a domai... |
| "beads guard", "beads conflict", "jsonl conflict", "beads sync issue" | safety/beads-guard | Safe Beads workflow helper (warning-only). Use before bd syn... |
| "check mcp", "mcp status", "mcp health", "verify mcp" | health/mcp-doctor | Warn-only health check for canonical MCP configuration and r... |
| "check skills", "skills health", "validate skills", "missing skills" | health/skills-doctor | Validate that the current VM has the right `agent-skills` in... |
| "check ssh", "ssh health", "ssh keys", "vm connection" | health/ssh-key-doctor | Fast, deterministic SSH health check for canonical VMs (no h... |
| "commit work", "save work", "git commit", "sync branch" | core/sync-feature-branch | Commit current work to feature branch with Beads metadata tr... |
| "create PR", "open PR", "merge into master", "ready for review" | core/create-pull-request | Create GitHub pull request with atomic Beads issue closure. ... |
| "create issue", "track work", "start feature", "finish feature" | core/beads-workflow | Beads issue tracking and workflow management with automatic ... |
| "dispatch task", "run on vm", "switch vm", "jules dispatch" | dispatch/multi-agent-dispatch | Cross-VM task dispatch using dx-dispatch (canonical). Suppor... |
| "finish feature", "close epic", "archive work", "cleanup branch" | core/finish-feature | Complete epic with cleanup and archiving, or verify feature ... |
| "fix PR", "address feedback", "fix CI", "resolve comments" | core/fix-pr-feedback | Address PR feedback with iterative refinement. MUST BE USED ... |
| "fix beads", "check beads", "beads sync failing", "beads doctor" | health/bd-doctor | Check and fix common Beads workflow issues across all repos. |
| "fix lockfile", "lockfile out of sync", "poetry.lock error", "pnpm lockfile" | health/lockfile-doctor | Check and fix lockfile drift across Poetry (Python) and pnpm... |
| "full lifecycle", "manage feature", "feature suite", "development workflow" | core/feature-lifecycle | A suite of skills to manage the full development lifecycle f... |
| "git reset --hard", "force push", "delete branch", "rm -rf" | safety/dcg-safety | Destructive Command Guard (DCG) safety hook for all AI codin... |
| "goodbye", "bye", "done for now", "logging off" | core/session-end | End Claude Code session with Beads sync and summary. MUST BE... |
| "install safety guard", "setup git guard", "protect from destructive commands", "add safety hooks" | safety/git-safety-guard | Installs a Git safety guard hook for Claude Code to prevent ... |
| "list projects", "switch project", "railway projects", "project settings" | railway/projects | This skill should be used when the user wants to list all pr... |
| "manage deployment", "view logs", "deployment history", "stop deployment" | railway/deployment | This skill should be used when the user wants to manage Rail... |
| "merge PR", "merge it", "merge this", "ready to merge" | core/merge-pr | Prepare PR for merge and guide human to merge via GitHub web... |
| "python version", "mise check", "poetry env", "toolchain check" | health/toolchain-health | Validate Python toolchain alignment between mise, Poetry, an... |
| "railway check", "railway deploy failed", "debug railway", "railway error" | health/railway-doctor | Pre-flight checks for Railway deployments to catch failures ... |
| "railway config", "environment variables", "env vars", "set variable" | railway/environment | This skill should be used when the user asks "what's the con... |
| "railway docs", "railway features", "how railway works", "docs.railway" | railway/railway-docs | This skill should be used when the user asks about Railway f... |
| "railway metrics", "resource usage", "CPU usage", "memory usage" | railway/metrics | This skill should be used when the user asks about resource ... |
| "railway status", "is it running", "what's deployed", "deployment status" | railway/status | This skill should be used when the user asks "railway status... |
| "railway template", "add service template", "find template", "ghost template" | railway/templates | This skill should be used when the user wants to add a servi... |
| "railway up", "deploy to railway", "ship to railway", "push code" | railway/deploy | This skill should be used when the user wants to push code t... |
| "service status", "rename service", "service health", "docker service" | railway/service | This skill should be used when the user asks about service s... |
| "setup railway", "initialize railway", "create project", "create service" | railway/new | This skill should be used when the user says "setup", "deplo... |
| "start work", "implement feature", "fix bug", "create task" | core/issue-first | Enforce Issue-First pattern by creating Beads tracking issue... |
| "verify pipeline", "check my work", "run tests", "validate changes" | health/verify-pipeline | Run project verification checks using standard Makefile targ... |


## Repo Context Skills
| Activation Keywords | Skill | Purpose |
|---------------------|-------|---------|
| "admin ui", "dashboard", "admin panel", "task management" | context-admin-ui | Admin dashboard, task management, and review interfaces. |
| "analytics", "metrics", "performance", "dashboard data" | context-analytics | Portfolio analytics, metrics calculation, performance tracki... |
| "api contracts", "api endpoints", "routes", "type definitions" | context-api-contracts | Frontend-backend API contracts, routes, clients, and type de... |
| "authentication", "authorization", "clerk", "rls policies" | context-security-resolver | Authentication, authorization, Clerk integration, RLS polici... |
| "backend development", "API endpoints", "database schema", "server-side logic" | backend-engineer | Backend developer for your project. MUST BE USED for buildin... |
| "database schema", "migrations", "supabase", "rls policies" | context-database-schema | Supabase PostgreSQL schema management, 86+ migrations, RLS p... |
| "dx workflow", "skill creation", "slash commands", "beads" | context-dx-meta | DX V3 workflow system, skills, slash commands, Beads issue t... |
| "llm", "rag pipeline", "embeddings", "ai orchestration" | context-llm-pipeline | RAG pipeline, embeddings, LLM interactions, and flow orchest... |
| "railway deployment", "ci/cd", "github actions", "smoke tests" | context-infrastructure | Railway deployment, CI/CD workflows, GitHub Actions, and smo... |
| "scraper", "scraping", "web crawler", "data extraction" | context-scrapers | Web scraping spiders (Scrapy), parsers, and source managemen... |
| "testing", "test setup", "fixtures", "mocks" | context-testing-infrastructure | Tiered testing strategy (UI mock, auth stub, full-stack), fi... |
| "ui design", "Material-UI", "theme", "design system" | context-ui-design | UI theme system, design tokens, Material-UI patterns, and ac... |

---

# Nakomi Agent Protocol

> This protocol applies to all agents (Claude Code, Antigravity, Gemini CLI, Codex CLI).

## Role
This agent supports a startup founder balancing high-leverage technical work and family responsibilities. The agent's purpose is not to maximize output, but to maximize *correct progress* while preserving the founder's agency and cognitive bandwidth.

## Core Constraints
- Do not make irreversible decisions without explicit instruction
- Do not expand scope unless asked
- Do not optimize for cleverness or novelty
- Do not assume time availability

## Decision Autonomy

| Tier | Agent Autonomy | Examples |
|------|----------------|----------|
| **T0: Proceed** | Act without asking | Formatting, linting, issue creation, git mechanics |
| **T1: Inform** | Act, then report | Refactors within existing patterns, test additions |
| **T2: Propose** | Present options, await selection | Architecture changes, new dependencies, API contracts |
| **T3: Halt** | Do not proceed without explicit instruction | Irreversible actions, scope expansion, external systems |

When uncertain, escalate one tier up.

## Intervention Rules
Act only when: task is blocking, founder is looping, hidden complexity exists, or small clarification unlocks progress.

## Cognitive Load Principles
1. **Continuity over correctness** — If resuming context takes >30s of reading, you've written too much
2. **One decision surface** — Consolidate related choices into a single ask
3. **State, don't summarize** — "Tests pass" not "I ran the test suite which verified..."
4. **Handoff-ready** — Assume another agent will pick up this thread

## Founder Commitments
> Reminder: At session start, remind founder if not addressed.
- Provide priority signal (P0-P4)
- State time/energy constraints upfront
- Explicitly close decision loops ("go with option 2", "not now")

---

# AGENTS.md — Agent Skills V3 DX

**Start Here**
1. **Initialize**: `source ~/.bashrc && dx-check || curl -fsSL https://raw.githubusercontent.com/stars-end/agent-skills/master/scripts/dx-hydrate.sh | bash`
2. **Check Environment**: `dx-check` checks git, Beads, and Skills.

**Core Tools**:
- **Beads**: Issue tracking. Use `bd` CLI.
- **Skills**: Automated workflows.

**Daily Workflow**:
1. `start-feature bd-xxx` - Start work.
2. Code...
3. `sync-feature "message"` - Save work.
4. `finish-feature` - Verify & PR.

---

## Quick Start (5 Commands)

Every agent session starts here:

| Step | Command | Purpose |
|------|---------|---------|
| 1 | `dx-check` | Verify environment |
| 2 | `bd list` | See current issues |
| 3 | `bd create "title" --type task` | Create tracking issue |
| 4 | `/skill core/sync-feature-branch` | Save work |
| 5 | `/skill core/create-pull-request` | Create PR |

### Example: Fix a Bug

```bash
# 1. Check environment
dx-check

# 2. Create tracking issue
bd create "Fix auth timeout bug" --type bug --priority 2

# 3. Start work (creates branch)
/skill core/beads-workflow
# Select: start-feature bd-xxx

# 4. Make your changes...

# 5. Save work
/skill core/sync-feature-branch
# Enter: sync-feature "fixed auth timeout"

# 6. Create PR when done
/skill core/create-pull-request
```

---

## Session Start Bootstrap (Mandatory Sequence)

**Every agent session MUST execute these steps in order:**

### 1. Git Sync
```bash
cd ~/your-repo
git pull origin master
```

**Purpose**: Ensure working directory matches latest team state
**Failure mode**: If pull fails, resolve conflicts before proceeding

### 2. DX Check
```bash
# Canonical baseline check (all repos)
dx-check

# Optional: Full diagnostics
dx-doctor
```

**Purpose**: Preflight check for:
- Canonical clones on trunk + clean (where required)
- Toolchain presence (mise, gh, railway, op, etc.)
- Optional MCP configuration — warn-only

**Failure mode**:
- ❌ Missing REQUIRED items → fix before proceeding
- ⚠️ Missing OPTIONAL items → note but continue

---

## Beads Integration

### Beads State Sync

**Before starting work**:
```bash
bd sync --dry-run  # Check for remote changes
bd sync            # Pull latest JSONL from remote
```

**Failure mode**: Merge conflicts in `.beads/*.jsonl`
- Use `beads-guard` skill for conflict prevention
- Resolve manually if conflicts occur

### Feature-Key Trailers

**All commits MUST include**:
```
Feature-Key: {beads-id}
Agent: {routing-name or DX_AGENT_ID}
Role: {engineer-type}
```

**Examples**:
- `Feature-Key: bd-3871.5`
- `Agent: epyc6-codex-cli` (recommended: use `$DX_AGENT_ID`)
- `Role: backend-engineer`

### Beads CLI Reference

| Command | Purpose |
|---------|---------|
| `bd list` | Show all issues |
| `bd create "title" --type task` | Create new issue |
| `bd start bd-xxx` | Start working on issue |
| `bd sync` | Pull latest JSONL from remote |
| `bd export -o .beads/issues.jsonl` | Export to JSONL |

---

## Skills (agentskills.io Format)

Skills are stored in `~/agent-skills/*/SKILL.md` using the [agentskills.io](https://agentskills.io) open standard.

## Skill Categories

Skills are organized into categories for easy discovery:

| Category | Purpose | When to Use |
|----------|---------|-------------|
| `core/` | Daily workflow | Every session - creating issues, syncing work, PRs |
| `safety/` | Safety guards | Auto-loaded - prevents destructive commands |
| `health/` | Diagnostics | When something isn't working right |
| `infra/` | VM/environment | Setting up new VMs or debugging environment |
| `dispatch/` | Cross-VM work | When task needs another VM (GPU, macOS) |
| `railway/` | Railway deployment | Deploying to Railway |
| `search/` | Context/history | Finding past solutions or building context |
| `extended/` | Advanced workflows | Optional - parallelization, planning, etc. |

### Finding Skills by Need

| Need | Skill | Category |
|------|-------|----------|
| Create/track issues | `/skill core/beads-workflow` | core/ |
| Save work | `/skill core/sync-feature-branch` | core/ |
| Create PR | `/skill core/create-pull-request` | core/ |
| Dispatch to another VM | `/skill dispatch/multi-agent-dispatch` | dispatch/ |
| Deploy to Railway | `/skill railway/deploy` | railway/ |
| Search past sessions | `/skill search/cass-search` | search/ |
| Debug environment | `/skill health/bd-doctor` | health/ |
| Set up new VM | `/skill infra/vm-bootstrap` | infra/ |

**Agent Skill Discovery:**

| Agent | Discovery Method |
|-------|------------------|
| Claude Code | Native `/skill <name>` command |
| OpenCode | Native `skill <name>` tool |
| Codex CLI | Native skill loading |
| Antigravity | Native slash commands |
| Gemini CLI | Native skill loading |

**Available Skills:**
- `multi-agent-dispatch` - Cross-VM task dispatch
- `beads-workflow` - Issue tracking with dependency management
- `sync-feature-branch` - Git workflows
- `fix-pr-feedback` - PR iteration
- `dcg-safety` - Destructive command guard (blocks dangerous git/rm commands)
- `bv-integration` - Beads Viewer and robot-plan API
- `cass-search` - Search past agent sessions

---

## Safety Tools

**DCG (Destructive Command Guard)**: Blocks dangerous commands before execution.

```bash
# Test DCG blocking
dcg explain "git reset --hard"

# What it blocks: git reset --hard, rm -rf /, git push --force
# What it allows: git status, git diff, rm temp files
```

**Installed on**: homedesktop-wsl, macmini (epyc6 uses fallback)

---

## Smart Task Selection

Use **BV** for intelligent task prioritization:

```bash
# Get next highest-impact task
bv --robot-plan | jq '.summary.highest_impact'

# Or via lib/fleet:
python3 -c "from lib.fleet import FleetDispatcher; print(FleetDispatcher().auto_select_task('affordabot'))"
```

---

## Session Search

Use **CASS** to search past agent work:

```bash
# Find how something was solved before
cass search "authentication oauth"

# Check indexed sessions
cass stats
```

**Installed on**: homedesktop-wsl, macmini (epyc6 blocked by GLIBC)


## When You Need More

### Cross-VM Dispatch

Use when task needs specific VM capabilities:

```bash
# SSH dispatch to canonical VMs
dx-dispatch epyc6 "Run GPU tests in ~/affordabot"
dx-dispatch macmini "Build iOS app"
dx-dispatch homedesktop-wsl "Run integration tests"

# Check VM status
dx-dispatch --list

# Jules Cloud dispatch (async)
dx-dispatch --jules --issue bd-123
```

### Environment Issues

```bash
# Quick health check
dx-check

# Full diagnostics
/skill health/bd-doctor
/skill health/mcp-doctor
/skill health/toolchain-health
```

### Fleet Operations

```bash
# Finalize PR for a session
dx-dispatch --finalize-pr ses_abc123 --beads bd-123

# Abort a running session
dx-dispatch --abort ses_abc123
```

---

## Multi-Agent Dispatch

`dx-dispatch` is the canonical tool for cross-VM and cloud dispatch.

### SSH Dispatch (default)

```bash
dx-dispatch epyc6 "Run make test in ~/affordabot"
dx-dispatch macmini "Build iOS app"
dx-dispatch --list  # Check VM status
```

### Jules Cloud Dispatch

```bash
dx-dispatch --jules --issue bd-123
dx-dispatch --jules --issue bd-123 --dry-run  # Preview prompt
```

### Canonical VMs

| VM | User | Capabilities |
|----|------|--------------|
| homedesktop-wsl | fengning | Primary dev, DCG, CASS |
| macmini | fengning | macOS builds, iOS |
| epyc6 | feng | GPU work, ML training |

**Add Slack notifications** to long tasks:
```
After completing, use slack_conversations_add_message
to post summary to channel C09MQGMFKDE.
```

📖 **Full guide**: [docs/MULTI_AGENT_COMMS.md](docs/MULTI_AGENT_COMMS.md)



## Claude CLI: Always Use `cc-glm`

**`cc-glm`** is a pre-configured Claude Code alias (defined in `~/.zshrc`) that:
- Uses the correct model configuration
- Handles authentication automatically
- Supports all standard `claude` flags

```bash
# Interactive session
cc-glm

# Non-interactive (one-shot)
cc-glm -p "Your prompt here"

# With output format
cc-glm -p "Prompt" --output-format text

# Resume session
cc-glm --resume <session-id>
```

**RULE:** Always use `cc-glm` instead of raw `claude` command.

---
## Platform-Specific Session Start Hooks

For automated bootstrap at session start, configure these hooks in your IDE:

### Claude Code

**SessionStart hook** (`.claude/hooks/SessionStart/dx-bootstrap.sh`):
```bash
#!/usr/bin/env bash
set -euo pipefail

# 1. Git sync
git pull origin master || echo "⚠️  git pull failed (resolve conflicts)"

# 2. DX check
dx-check || true

# 3. Optional coordinator stack checks
dx-doctor || true

echo "✅ DX bootstrap complete"
```

### Codex CLI

**Config** (`~/.codex/config.toml`):
```toml
[session]
on_start = "bash ~/.agent/skills/session-start-hooks/dx-bootstrap.sh"
```

### Antigravity

**Config** (`~/.antigravity/config.yaml`):
```yaml
session:
  on_start:
    - git pull origin master
    - dx-check || true
    - dx-doctor || true
```

**See also**: `docs/IDE_SPECS.md` for full IDE configuration details.

---

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds


---

# REPO-SPECIFIC CONTEXT

# Affordabot Local Context

## Verification

| Target | Command | When |
|--------|---------|------|
| Local | `make verify-local` | Before commit |
| E2E | `make verify-pipeline` | Before PR |
| Analysis | `make verify-analysis` | Logic changes |

## Quick Start

```bash
dx-check
bd create "title" --type task
```

## Repo Layout

- `frontend/` - React/Next.js job application UI
- `frontend-v2/` - New version (WIP)
- `backend/` - FastAPI Python API
- `affordabot_scraper/` - LinkedIn scraper service
- `tests/` - Playwright E2E tests
