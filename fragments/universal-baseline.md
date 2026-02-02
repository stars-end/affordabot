# Universal Baseline — Agent Skills
<!-- AUTO-GENERATED -->
<!-- Source SHA: b6d064d5f5a91e610359e4aa8b4ee4191db57945 -->
<!-- Last updated: 2026-02-02 12:47:35 -->
<!-- Regenerate: make publish-baseline -->

## Operating Contract (Layer A — Curated)

## Nakomi Agent Protocol

### Role
Support a startup founder balancing high-leverage technical work and family responsibilities.

### Core Constraints
- Do not make irreversible decisions without explicit instruction
- Do not expand scope unless asked
- Do not optimize for cleverness or novelty
- Do not assume time availability

### Decision Autonomy

| Tier | Agent Autonomy | Examples |
|------|----------------|----------|
| **T0: Proceed** | Act without asking | Formatting, linting, issue creation, git mechanics |
| **T1: Inform** | Act, then report | Refactors within existing patterns, test additions |
| **T2: Propose** | Present options, await selection | Architecture changes, new dependencies, API contracts |
| **T3: Halt** | Do not proceed without explicit instruction | Irreversible actions, scope expansion, external systems |

When uncertain, escalate one tier up.

## Canonical Repository Rules

**Canonical repositories** (read-mostly clones):
- `~/agent-skills`
- `~/prime-radiant-ai`
- `~/affordabot`
- `~/llm-common`

### Enforcement

**Primary**: Git pre-commit hook blocks commits when not in worktree

**Safety net**: Daily sync to origin/master (non-destructive)
- Runs: 3am daily on all VMs
- Purpose: Ensure canonical clones stay aligned
- Note: Does NOT reset uncommitted changes

### Workflow

Always use worktrees for development:

```bash
dx-worktree create bd-xxxx repo-name
cd /tmp/agents/bd-xxxx/repo-name
# Work here
```

### Recovery

If you accidentally commit to canonical:

```bash
cd ~/repo
git reflog | head -20
git show <commit-hash>

# Recover to worktree
dx-worktree create bd-recovery repo
cd /tmp/agents/bd-recovery/repo
git cherry-pick <commit-hash>
git push origin bd-recovery
```

## External Beads Database (CRITICAL)

### Requirement

ALL agents MUST use centralized external beads database:

```bash
export BEADS_DIR="$HOME/bd/.beads"
```

### Verification

Every session:

```bash
echo $BEADS_DIR
# Expected: /home/fengning/bd/.beads

# If not set:
cd ~/agent-skills
./scripts/migrate-to-external-beads.sh
source ~/.zshrc
```

### Architecture

```
~/bd/.beads/              (Central database)
├── beads.db              (SQLite)
├── issues.jsonl          (Export)
├── config.yaml           (Config)
└── .git/                 (Multi-VM sync)
```

### Why External DB

| Problem | Solution |
|---------|----------|
| `.beads/` causes git conflicts | External DB separate from code |
| Each repo isolated | Single shared database |
| Multi-VM sync complex | One `~/bd` repo via git |
| Agent context fragments | All agents see same issues |

## Session Start Bootstrap

Every agent session MUST execute these steps:

### 1. Git Sync

```bash
cd ~/your-repo
git pull origin master
```

### 2. DX Check

```bash
dx-check  # Baseline check
dx-doctor  # Full diagnostics (optional)
```

### 3. Verify BEADS_DIR

```bash
echo $BEADS_DIR
# Expected: /home/$USER/bd/.beads
```

## Landing the Plane (Session Completion)

When ending a work session, MUST complete ALL steps:

1. **File issues** for remaining work
2. **Run quality gates** (if code changed)
3. **Update issue status**
4. **PUSH TO REMOTE** (MANDATORY):
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL**: Work is NOT complete until `git push` succeeds.

---

## Universal Skill Index (Layer B — Generated)

### Core Workflows

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |

### Extended Workflows

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |

### Health & Monitoring

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |

### Infrastructure

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |

### Railway Deployment

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |
|  |   | `See SKILL.md` |  |


---

**Discovery**: Skills auto-load from \`~/agent-skills/{core,extended,health,infra,railway}/*/SKILL.md\`  
**Details**: Each skill's SKILL.md contains full documentation  
**Specification**: https://agentskills.io/specification  
**Source**: Generated from agent-skills commit shown in header
