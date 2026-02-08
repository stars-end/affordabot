# Universal Baseline — Agent Skills
<!-- AUTO-GENERATED -->
<!-- Last updated: 2026-02-08 11:10:46 UTC -->
<!-- Regenerate: make publish-baseline -->

## Nakomi Agent Protocol
### Role
Support a startup founder balancing high-leverage technical work and family responsibilities.
### Core Constraints
- Do not make irreversible decisions without explicit instruction
- Do not expand scope unless asked
- Do not optimize for cleverness or novelty
- Do not assume time availability

# DX Global Constraints (V8)
<!-- AUTO-GENERATED - DO NOT EDIT -->

## 1) Canonical Repository Rules
**Canonical repositories** (read-mostly clones):
- `~/agent-skills`
- `~/prime-radiant-ai`
- `~/affordabot`
- `~/llm-common`

### Enforcement
**Primary**: Git pre-commit hook blocks commits when not in worktree
**Safety net**: Daily sync to origin/master (non-destructive)

### Workflow
Always use worktrees for development:
```bash
dx-worktree create bd-xxxx repo-name
cd /tmp/agents/bd-xxxx/repo-name
# Work here
```

## 2) V8 DX Automation Rules
1. **No auto-merge**: never enable auto-merge on PRs — humans merge
2. **No PR factory**: one PR per meaningful unit of work
3. **No canonical writes**: always use worktrees
4. **Feature-Key mandatory**: every commit needs `Feature-Key: bd-XXXX`

---

## Core Workflows

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
| **beads-workflow** | Beads issue tracking and workflow management with automatic git branch creation. MUST BE USED for Be | `bd create --title "Impl: OAuth" --type feature --dep "bd-res` | workflow, beads, issue-tracking, git |
| **create-pull-request** | Create GitHub pull request with atomic Beads issue closure. MUST BE USED for opening PRs. Asks if wo | `bd create --title <FEATURE_KEY> --type feature --priority 2 ` | workflow, github, pr, beads, review |
| **database-quickref** | Quick reference for Railway Postgres operations. Use when user asks to check database, run queries, verify data, inspect tables, or mentions psql, postgres, database, "check the db", "validate data". | — | database, postgres, railway, psql |
| **feature-lifecycle** | A suite of skills to manage the full development lifecycle from start to finish. - `start-feature`:  | — | workflow, git, feature, beads, dx |
| **finish-feature** | Complete epic with cleanup and archiving, or verify feature already closed. MUST BE USED when finish | `bd close bd-abc.2 --reason 'Completed'` | workflow, beads, cleanup, archiving |
| **fix-pr-feedback** | Address PR feedback with iterative refinement. MUST BE USED when fixing PR issues. Supports auto-det | `bd show <FEATURE_KEY>` | workflow, pr, beads, debugging, iteration |
| **issue-first** | Enforce Issue-First pattern by creating Beads tracking issue BEFORE implementation. MUST BE USED for | — | workflow, beads, issue-tracking, implementation |
| **merge-pr** | Prepare PR for merge and guide human to merge via GitHub web UI. MUST BE USED when user wants to mer | `bd sync` | workflow, pr, github, merge, deployment |
| **session-end** | End Claude Code session with Beads sync and summary. MUST BE USED when user says they're done, endin | `bd sync, or export operations.` | workflow, beads, session, cleanup |
| **sync-feature-branch** | Commit current work to feature branch with Beads metadata tracking and git integration. MUST BE USED | `bd create --title <FEATURE_KEY> --type feature --priority 2 ` | workflow, git, beads, commit |


## Extended Workflows

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
| **bv-integration** | Beads Viewer (BV) integration for visual task management and smart task selection. Use for Kanban vi | `bd show "$NEXT_TASK"` | workflow, beads, visualization, task-selection |
| **cli-mastery** | **Tags:** #tools #cli #railway #github #env | — |  |
| **coordinator-dx** | Coordinator playbook for running multi‑repo, multi‑VM work in parallel without relying on humans copy/pasting long checklists. | — |  |
| **dirty-repo-bootstrap** | Safe recovery procedure for dirty/WIP repositories. This skill provides a standardized workflow for: - Snapshotting uncommitted work to a WIP branch | `bd sync` |  |
| **grill-me** | Relentless product interrogation before planning or implementation. Use when the user wants exhaustive discovery, blind-spot identification, assumption stress-testing, edge-case analysis, or hard pushback on vague problem framing. | — | product, strategy, interrogation, discovery |
| **jules-dispatch** | Dispatches work to Jules agents via the CLI. Automatically generates context-rich prompts from Beads | — | workflow, jules, cloud, automation, dx |
| **lint-check** | Run quick linting checks on changed files. MUST BE USED when user wants to check code quality. Fast  | — | workflow, quality, linting, validation |
| **parallelize-cloud-work** | Delegate independent work to Claude Code Web cloud sessions for parallel execution. Generates compre | `bd show <issue-id>` | workflow, cloud, parallelization, dx |
| **plan-refine** | Iteratively refine implementation plans using the "Convexity" pattern. Simulates a multi-round archi | — | architecture, planning, review, refinement, apr |
| **prompt-writing** | Drafts robust, low-cognitive-load prompts for other agents that enforce the DX invariants: worktree- | — | workflow, prompts, orchestration, dx, safety |
| **skill-creator** | Create new Claude Code skills following V3 DX patterns with Beads/Serena integration. MUST BE USED w | — | meta, skill-creation, automation, v3 |
| **slack-coordination** | Optional coordinator stack: Slack-based coordination loops (inbox polling, post-merge followups, lig | — | slack, coordination, workflow, optional |
| **worktree-workflow** | Create and manage task workspaces using git worktrees (without exposing worktree complexity). Use th | `dx-worktree create <beads-id> <repo>` | dx, git, worktree, workspace, workflow |


## Infrastructure & Health

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
| **bd-doctor** | Check and fix common Beads workflow issues across all repos. | `bd export --force` |  |
| **lockfile-doctor** | Check and fix lockfile drift across Poetry (Python) and pnpm (Node.js) projects. | — |  |
| **mcp-doctor** | Warn-only health check for canonical MCP configuration and related DX tooling. Strict mode is opt-in | — | dx, mcp, health, verification |
| **railway-doctor** | Pre-flight checks for Railway deployments to catch failures BEFORE deploying. Use when about to depl | — | railway, deployment, validation, pre-flight |
| **skills-doctor** | Validate that the current VM has the right `agent-skills` installed for the repo you’re working in. | — |  |
| **ssh-key-doctor** | Fast, deterministic SSH health check for canonical VMs (no hangs, no secrets). Warn-only by default; | — | dx, ssh, verification |
| **toolchain-health** | Validate Python toolchain alignment between mise, Poetry, and pyproject. Use when changing Python ve | — | dx, tooling, python |
| **verify-pipeline** | Run project verification checks using standard Makefile targets. Use when user says "verify pipeline | — | workflow, testing, verification, makefile, railway |
| **canonical-targets** | Single source of truth for canonical VMs, canonical IDEs, and canonical trunk branch. Use this to ke | — | dx, ide, vm, canonical, targets |
| **devops-dx** | GitHub/Railway housekeeping for CI env/secret management and DX maintenance. Use when setting or aud | — | devops, github, env, ci, railway |
| **dx-alerts** | Lightweight “news wire” for DX changes and breakages, posted to Slack (no MCP required). | — |  |
| **github-runner-setup** | GitHub Actions self-hosted runner setup and maintenance. Use when setting up dedicated runner users, | — | github-actions, devops, runner, systemd, infrastructure |
| **vm-bootstrap** | Linux VM bootstrap verification skill. MUST BE USED when setting up new VMs or verifying environment | — | dx, tooling, setup, linux |
| **database** | This skill should be used when the user wants to add a database (Postgres, Redis, MySQL, MongoDB), says "add postgres", "add redis", "add database", "connect to database", or "wire up the database". For other templates (Ghost, Strapi, n8n, etc.), use the templates skill. | — |  |
| **deploy** | This skill should be used when the user wants to push code to Railway, says "railway up", "deploy", "deploy to railway", "ship", or "push". For initial setup or creating services, use new skill. For Docker images, use environment skill. | — |  |
| **deployment** | This skill should be used when the user wants to manage Railway deployments, view logs, or debug issues. Covers deployment lifecycle (remove, stop, redeploy, restart), deployment visibility (list, status, history), and troubleshooting (logs, errors, failures, crashes, why deploy failed). NOT for deleting services - use environment skill with isDeleted for that. | — |  |
| **domain** | This skill should be used when the user wants to add a domain, generate a railway domain, check current domains, get the URL for a service, or remove a domain. | — |  |
| **environment** | This skill should be used when the user asks "what's the config", "show me the configuration", "what variables are set", "environment config", "service config", "railway config", or wants to add/set/delete variables, change build/deploy settings, scale replicas, connect repos, or delete services. | — |  |
| **metrics** | This skill should be used when the user asks about resource usage, CPU, memory, network, disk, or service performance. Covers questions like "how much memory is my service using" or "is my service slow". | — |  |
| **new** | This skill should be used when the user says "setup", "deploy to railway", "initialize", "create project", "create service", or wants to deploy from GitHub. Handles initial setup AND adding services to existing projects. For databases, use the database skill instead. | — |  |
| **projects** | This skill should be used when the user wants to list all projects, switch projects, rename a project, enable/disable PR deploys, make a project public/private, or modify project settings. | — |  |
| **railway-docs** | This skill should be used when the user asks about Railway features, how Railway works, or shares a docs.railway.com URL. Fetches up-to-date Railway docs to answer accurately. | — |  |
| **service** | This skill should be used when the user asks about service status, wants to rename a service, change service icons, link services, or create services with Docker images. For creating services with local code, prefer the `new` skill. For GitHub repo sources, use `new` skill to create empty service then `environment` skill to configure source. | — |  |
| **status** | This skill should be used when the user asks "railway status", "is it running", "what's deployed", "deployment status", or about uptime. NOT for variables ("what variables", "env vars", "add variable") or configuration queries - use environment skill for those. | — |  |
| **templates** | This skill should be used when the user wants to add a service from a template, find templates for a specific use case, or deploy tools like Ghost, Strapi, n8n, Minio, Uptime Kuma, etc. For databases (Postgres, Redis, MySQL, MongoDB), prefer the database skill. | — |  |
| **multi-agent-dispatch** | Cross-VM task dispatch using dx-dispatch (canonical). Supports SSH dispatch to canonical VMs (homedesktop-wsl, macmini, epyc6), Jules Cloud dispatch for async work, and fleet orchestration. | `dx-dispatch epyc6 "Run make test in ~/affordabot"` |  |


---
**Discovery**: Skills auto-load from `~/agent-skills/{core,extended,health,infra,railway}/*/SKILL.md`  
**Details**: Each skill's SKILL.md contains full documentation  
**Specification**: https://agentskills.io/specification  
