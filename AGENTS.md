<!-- ⚠️ IMPORTANT FOR AI AGENTS (Claude, Gemini, Codex, etc.) ⚠️
GEMINI.md and CLAUDE.md are SYMLINKS to this file (AGENTS.md).
DO NOT modify GEMINI.md or CLAUDE.md directly - they are read-only pointers.
ONLY modify AGENTS.md. Changes will automatically appear in all symlinks.
-->

# AGENTS.md — V3 DX Workflow

**Start Here (for Claude)**

**V3 Philosophy:** Minimal validation + Trust environments

**TL;DR:**
- Say: "commit my work" → Agent auto-invokes sync-feature-branch skill
- Say: "create PR" → Agent auto-invokes create-pull-request skill
- Tools: Use Serena for code search/edit, Beads CLI for state tracking
- Protected: Open `railway shell` for DB operations (Beads works everywhere)
- **No complex validation** - environments handle testing/deployment

**Quick Navigation:**
- 🚀 [Daily Workflow](#-daily-workflow) — V3 loop, commands, common mistakes
- 🔧 [Core Tools](#-core-tools) — Beads, Serena, Context Skills (14 static + N dynamic)
- 🏗️ [Environment & Setup](#-environment--setup) — Railway, onboarding, layout
- 🔒 [Rules & Conventions](#-rules--conventions) — Commits, branches, protection
- 📚 [Reference & Links](#-reference--links) — Docs, CI, deprecated, troubleshooting

---

## 🚀 Daily Workflow

### My Frequent Mistakes → Correct Tools

| ❌ WRONG | ✅ CORRECT | WHY |
|---------|-----------|-----|
| `bash grep -r` | `Serena search_for_pattern` | .gitignore-aware, context lines, file grouping |
| `bash find . -name "*.py"` | `Serena list_dir(..., recursive=True)` | Better metadata, filtering |
| `Read + Edit` on code | `Serena find_symbol → replace_symbol_body` | Symbol-aware, robust |
| `git add . && git commit` | Say "commit my work" | Agent uses skill automatically |
| `general-purpose` agent | `@backend-engineer`, `@frontend-engineer` | Specialized expertise |

**V3: Natural language > explicit commands**

---

### Natural Language → Skills (Auto-Invoked)

**User says these phrases, agent auto-invokes skill:**

- **"commit my work"** → sync-feature-branch skill
  - Checks Beads metadata
  - Quick lint (<5s)
  - Commits with Feature-Key trailer
  - Updates Beads status
  - **Total: <30s**

- **"create PR"** → create-pull-request skill
  - Asks: "Is work complete?"
  - If YES: Closes issue, syncs JSONL, pushes (atomic merge)
  - If NO: Creates draft PR (issue stays open)
  - Creates PR with gh, links to Beads
  - **Total: <15s**

- **"fix the PR"** → fix-pr-feedback skill
  - Reads PR comments and CI status
  - Creates child Beads issues for discoveries
  - Fixes simple issues automatically
  - Commits fixes with Feature-Key trailers
  - **Total: <2min per issue**

- **"create skill"** → skill-creator skill
  - Classifies skill type (workflow/specialist/meta)
  - Generates SKILL.md following V3 patterns
  - Adds auto-activation rules
  - Updates documentation
  - **Total: <5min**

**No waiting, no complex validation.**

**How skills work:** Skills activate via semantic understanding of their descriptions, not regex patterns. See context-dx-meta for activation details.

---

### Slash Commands (Execute These)

**When user says `/command "args"` → YOU execute the command:**

#### Command Execution Flow
1. **User says:** `/search "V3"`
2. **You read:** `.claude/commands/search.md`
3. **You follow instructions:** Use `mcp__serena__search_for_pattern` with the args
4. **You execute:** Call the specified tool with the pattern
5. **You return:** Results to the user

#### Available Commands
- `/search "pattern"` — Code search (uses mcp__serena__search_for_pattern)
- `/overview file.py` — Symbol overview (uses mcp__serena__get_symbols_overview)
- `/find SymbolName` — Locate symbols (uses mcp__serena__find_symbol)
- `/refs Symbol file.py` — Find references (uses mcp__serena__find_referencing_symbols)
- `/tree dir/` — List directory (uses mcp__serena__list_dir)
- `/help-dx` — Show V3 workflow guide

**Command files are INSTRUCTIONS, not just documentation.** They tell you exactly which tools to call and with what parameters.

**Example:**
```
User: /search "V3"
Me: Read .claude/commands/search.md
    → Sees: "Use mcp__serena__search_for_pattern with pattern from args"
    → Execute: mcp__serena__search_for_pattern(substring_pattern="V3")
    → Return: List of files containing "V3"
```

---

### V3 Daily Loop

**Simple, fast, no waiting:**

1. **Session start:** Check context
   ```bash
   scripts/bd-context
   ```

2. **Work on feature:** Code normally with Serena tools

3. **Save progress:**
   ```
   User: "commit my work"
   Agent: [25s] ✅ Committed
   ```

4. **Open PR:**
   ```
   User: "create PR"
   Agent: [Asks] Is work complete? (y/n)
   User: y
   Agent: [15s] ✅ Issue closed, PR#147 created (JSONL in PR), CI running
   ```

5. **Fix PR feedback (if needed):**
   ```
   User: "fix the PR"
   Agent: [2min] ✅ Created 3 child issues, fixed 2, CI re-running
   ```

6. **Test in dev:** dev.yourapp.com/pr-147 (auto-deploys)

7. **Merge when ready:**
   ```
   User: "merge it"
   Agent: ✅ Verified issue closed, ready to merge
   Human: Merge via GitHub web UI
   Agent: ✅ Cleanup complete (after merge)
   ```

**No complex validation. Environments handle safety.**

---

## 🔧 Core Tools

### Beads Quick Reference

**Beads** is our AI-first issue tracking system. Agents use the `bd` CLI to manage epics, features, bugs, and tasks with automatic git-sync.

**🚨 CRITICAL: ALWAYS Use `bd` CLI, NEVER Use MCP Tools 🚨**

**Why this matters:**
- ❌ **WRONG:** `mcp__plugin_beads_beads__create(...)` → Type errors, slow, unreliable
- ✅ **CORRECT:** `bd create "..." --type feature` → Fast, documented, stable

**Tool Choice:** Use **bd CLI** (via Bash) instead of MCP tools for reliability:
- ✅ CLI: Better documented, faster, no type errors
- ⚠️ MCP: Type validation issues, slower, less documented
- MCP only for: User-facing slash commands (`/bd-ready`)

#### Essential Workflow

**Note:** Skills automate this workflow - commands shown for reference.

```bash
# Create epic with phases
bd create "FEATURE_NAME" --type epic --priority 1
bd create "Research" --type task --assignee claude-code  # Gets bd-xyz.1
bd create "Implementation" --type task --assignee claude-code  # Gets bd-xyz.2
bd dep add bd-xyz.2 bd-xyz.1 --type blocks

# Work on task
bd update bd-xyz.1 --status in_progress

# Discover bug during work
bd create "Bug: X" --type bug --priority 1 --assignee claude-code  # Gets bd-xyz.1.1
bd dep add bd-xyz.1.1 bd-xyz.1 --type discovered-from
bd close bd-xyz.1.1 --reason "Fixed"

# Complete phase
bd close bd-xyz.1 --reason "Research complete"
bd update bd-xyz.2 --status in_progress  # Start next

# Session end (CRITICAL)
bd sync  # Force export to git
```

#### Quick Commands (via scripts)

- `scripts/bd-context` — Show current Beads context
- `scripts/bd-what <id>` — Quick lookup: "what is bd-xyz?" (e.g., `bd-what 7vu`)
- `scripts/bd-link-pr <number>` — Link PR to feature
- `scripts/bd-retroactive` — Create Beads issue from untracked commits

#### Key Concepts

- **Hierarchical IDs:** bd-xyz → bd-xyz.1 → bd-xyz.1.1 (auto-assigned)
- **Dependencies:** Create natural work queues (blocks, discovered-from, parent-child)
- **Issue-First:** Create issue BEFORE coding (captures design intent)
- **Ready work:** `ready(priority=1)` shows unblocked tasks
- **Session sync:** Always `bd sync` at session end (guarantees persistence)
- **Atomic merge pattern:** Issues close at PR creation, JSONL merges with code (no post-merge mutations)

**Multi-developer workflow:** See context-dx-meta for parallel work, git hooks, and conflict resolution.

#### Issue Lifecycle & PR Integration

**When issues close:**

| Issue Type | Closed By | When | Why |
|------------|-----------|------|-----|
| Feature | create-pull-request | PR creation (if work complete) | JSONL merges atomically with code |
| Task | create-pull-request | PR creation (if work complete) | Prevents post-merge hook conflicts |
| Bug | create-pull-request | PR creation (if work complete) | Clean feature branch deletion |
| Epic | finish-feature | All children closed | Long-lived, spans multiple PRs |

**Workflow:**
```
1. Code feature on feature-bd-xyz branch
2. "commit my work" → sync-feature-branch (commits code)
3. "create PR" → create-pull-request
   ├─ Asks: "Is work complete?"
   ├─ If YES: bd close → bd sync → git push → create PR
   └─ Result: JSONL + code in same PR ✅
4. "merge it" → merge-pr
   ├─ Verifies issue already closed ✅
   └─ Guides human to merge via web UI
5. Human merges → JSONL merges atomically ✅
```

**Why atomic merge matters:**
- ✅ No post-merge Beads operations needed
- ✅ No hook conflicts on master
- ✅ Clean feature branch deletion
- ✅ JSONL is just another file (merges with code)

**📖 Full Guide:** See [BEADS.md](BEADS.md) for automation patterns, common mistakes, and MCP tool reference
**🔗 Official Docs:** https://github.com/steveyegge/beads/blob/main/AGENTS.md

---

### Serena Quick Reference

#### Token-Efficient Reading
- `get_symbols_overview` → top-level symbols (use first!)
- `find_symbol("name_path", include_body=True)` → specific class/function
- `find_referencing_symbols` → who uses this code?
- `search_for_pattern` → find patterns across project

#### Code Editing Workflow
1. `find_symbol("name_path", include_body=True)` → locate target
2. `replace_symbol_body(...)` → replace full definition
3. `insert_after_symbol` / `insert_before_symbol` → add code
4. `rename_symbol` → refactor across codebase

#### Search Capabilities
- `search_for_pattern` replaces bash grep/find
  - Supports: .gitignore, context lines, glob exclusions
  - File-grouped results, multiline patterns (DOTALL mode)
- `list_dir(..., recursive=True)` replaces bash find
  - Better metadata, file sizes, types, timestamps
- `find_file("*.md", "docs/")` for exact file matching

**Reference:** Full docs at https://github.com/oraios/serena/blob/main/README.md

---

### TodoWrite vs Beads

**Default:** Use Beads for almost everything (Issue-First pattern).

**Rule:** Code work or multi-session work → Beads. Ephemeral execution tracking → TodoWrite.

**Full decision tree:** See context-dx-meta for details.

---

### Context Skills: Navigate Codebase & Track Epics

**Two-tier system:**
- **Static skills** (14): Long-term codebase areas - activate when working on specific domain
- **Dynamic epic context** (N): Auto-created per epic, updated on push

**Static skills include:** context-plaid-integration, context-database-schema, context-dx-meta, context-testing-infrastructure, and 10 others. Skills self-describe and activate semantically.

**Dynamic epic lifecycle:**
1. Create epic → `epic-context-create.sh bd-xyz` (or via issue-first skill)
2. Work → Commits auto-update work log (GitHub Action)
3. Resume → Invoke `context-epic-bd-xyz` for complete history
4. Finish → `epic-context-archive.sh bd-xyz` archives to docs/

**External docs:** Use docs-create skill to cache API docs into epic context.

**Full guide:** See `docs/DX_CONTEXT_SKILLS.md`

---

## 🏗️ Environment & Setup

### Railway Environment

| Operation Type | Railway Required? | Examples |
|----------------|-------------------|----------|
| 🟢 **Code/Git** | NO | Serena, Beads, git operations, file edits |
| 🔴 **Database** | YES | migrations, seeding, introspection, schema changes |
| 🔴 **External APIs** | YES | EODHD, Plaid (requires credentials) |

**Beads:** Works everywhere (warns about production DB - expected and safe).

**⚠️ CRITICAL: Always verify Railway environment before database operations**

```bash
# Check if in Railway shell
echo $RAILWAY_ENVIRONMENT

# If empty → You're NOT in Railway shell
# Database operations WILL FAIL

# Enter Railway shell first:
railway shell
```

**Why:** Database credentials only available in `railway shell` (interactive session with persistent env). `railway run` = one-off commands (no state).

---

### Database Access

**Prerequisites:** Must be in `railway shell` (see Railway Environment above).

**Common Queries:**

```bash
# List users
psql "$DATABASE_URL" -c "SELECT id, email, created_at FROM users ORDER BY created_at DESC LIMIT 10;"

# Find specific user
psql "$DATABASE_URL" -c "SELECT * FROM users WHERE email = 'user@example.com';"

# List accounts for user
psql "$DATABASE_URL" -c "SELECT id, user_id, account_type, created_at FROM accounts WHERE user_id = 'user_xxx';"

# View holdings
psql "$DATABASE_URL" -c "SELECT * FROM holdings WHERE account_id = 'acc_xxx';"

# Check schema
psql "$DATABASE_URL" -c "\dt"  # List tables
psql "$DATABASE_URL" -c "\d users"  # Describe users table
```

**Using Python Scripts:**

```bash
# Inside railway shell
poetry run python scripts/db-query.py --user user@example.com
poetry run python scripts/seed-dev-users.py
```

**Running Migrations:**

```bash
# Push local migrations to dev database
cd supabase
supabase db push  # See DB migration health check below

# Generate migration from schema changes
supabase db diff -f migration_name

# Reset dev database (DESTRUCTIVE)
supabase db reset
```

**Troubleshooting:**

| Error | Solution |
|-------|----------|
| `connection refused` | Not in railway shell - run `railway shell` first |
| `$DATABASE_URL: not set` | Not in railway shell - check `echo $RAILWAY_ENVIRONMENT` |
| `permission denied` | Check Railway project/environment selected |

### DB Migration Health Check (bd-k1c)

When working on schema changes or new Supabase migrations:

- **Always** run a dry health check in dev before merging:
  ```bash
  cd supabase
  supabase db push
  ```
- If it fails on **old** migrations (e.g. “relation already exists”, duplicate trigger):
  - Root cause: schema was bootstrapped via `golden_schema.sql` / `all_migrations.sql` / manual SQL and the migration registry is behind.
  - Do **not** “fix” by running ad‑hoc DDL.
  - Instead:
    - Repair the registry (mark historical versions as applied; see `supabase/scripts/fix_migration_registry_bd_k1c.sql` for the bd-k1c repair), **or**
    - Make historical migrations idempotent (wrap `CREATE TRIGGER` / DDL in `IF NOT EXISTS` blocks), then rerun `supabase db push --include-all`.
- Only after `supabase db push` is clean in dev should new migrations be added/merged.

**Agent checklist for schema work (Railway dev shell):**

1. `supabase db push` (dev)
   - Fix any **old migration** failures via registry repair or idempotent DDL (never ad‑hoc DDL) and rerun until clean.
2. `make schema:generate` from repo root
   - Updates `supabase/types/database.types.ts`, `supabase/generated/schema_manifest.json`, and `backend/schemas/generated/**`.
3. `cd backend && PYTHONPATH=. poetry run python ../scripts/verify_generated_schemas.py`
   - Must pass locally before you open a PR.
4. Commit **all** schema‑related files together in a feature branch:
   - `supabase/migrations/**`, `supabase/schemas/**`, generated types/manifests, and Pydantic models.

**Migration hygiene rules:**

- **Dev/test-data migrations** must live under `supabase/dev_migrations/`, NOT `supabase/migrations/`
- **Schema migrations** (DDL, RLS, indexes, FKs) go in `supabase/migrations/`
- **Test-data seeding** goes in `scripts/db-commands/` or `supabase/dev_migrations/`
- For **new migrations you add from now on**, use a **unique timestamp prefix** per file. Historical migrations (pre‑bd-k1c) already have duplicate prefixes and must not be renamed.
- **Do not use `supabase db push --include-all`** on historical migrations; treat it as debugging tool only
- See `supabase/dev_migrations/README.md` for manual dev/test-data script usage

This keeps Supabase migration history, live schema, and generated artifacts in lockstep and avoids the drift we saw during bd-k1c, while acknowledging that some early migrations use shared prefixes for legacy reasons.

---

### Zero-to-Feature (Agent Onboarding)

#### Discovery Mode (outside Railway)
```bash
serena_activate_project
make slash-help
make branch-status
```

Read area maps: docs/ANALYTICS/INDEX.md, docs/SECURITY_RESOLVER/INDEX.md

#### Protected Mode (inside Railway shell)
```bash
railway shell
echo $RAILWAY_ENVIRONMENT  # Verify non-empty
make setup-git-hooks
make
make workspace-refresh
gh auth status
```

**V3 Workflow:**
```bash
# Create Beads issue
bd create "YOUR_FEATURE" --type feature

# Code feature with Serena tools
# Use /search, /overview, /find for navigation

# When ready to save
User: "commit my work"
# Agent auto-invokes sync-feature-branch skill

# When ready for review
User: "create PR"
# Agent auto-invokes create-pull-request skill

# CI runs async, test in dev environment
# When CI passes and ready to merge
User: "merge it"
```

---

### Repository Layout

| Path | Purpose | Key Subdirs |
|------|---------|-------------|
| **backend/** | FastAPI service | api/, services/, brokers/, tests/ |
| **frontend/** | React app | src/, components/, services/, tests/ |
| **supabase/** | Database | migrations/, schemas/public/, functions/ |
| **scripts/** | Workflows | commands/, cli/, lib/, db-commands/ |
| **docs/** | Documentation | DX_*.md, <FEATURE_KEY>/, systems/ |
| **.claude/**, **.opencode/** | Agent commands | commands/ (parity maintained) |
| **.github/** | CI/PR | workflows/, CODEOWNERS, templates/ |

**Feature Asset Placement:**
```
docs/<KEY>/          → PRD, design docs, test runs
tests/features/<KEY>/ → Feature-specific tests
scripts/<KEY>/       → Feature-specific automation
```

**Rules:**
- ✅ Extend canonical DX_*.md OR create feature folder
- ❌ No new DX one-offs
- ❌ No worktrees in agent workflows
- ❌ Never invoke prompts from shell (use CC/OC)

---

## 🔒 Rules & Conventions

### Commit & Branch Conventions

#### Commit Format (Required Trailers)
```
<type>: <subject>

<body>

Feature-Key: bd-xyz
Agent: <environment-id>
Role: <role-name>
```

**Agent trailer policy:**
- `Agent: codex-cli` (Codex CLI)
- `Agent: claude-code` (Claude Code / CC web)
- `Agent: antigravity` (Antigravity IDE)
- `Role`: keep your active role (backend-engineer, frontend-engineer, etc.)

**Note:** Feature-Key should be the Beads issue ID (bd-xyz format)

#### Branch Naming (Recommended)
- `feature-bd-xyz` — new features (use Beads issue ID)
- `fix-bd-xyz`, `hotfix-bd-xyz` — bug fixes
- `feature-DESCRIPTIVE_NAME` — OK if no Beads issue yet

**Examples:**
- `feature-bd-7vu` → Links to bd-7vu (GUARD_TASK_TOOL_ENFORCEMENT)
- `feature-ANALYTICS` → Descriptive name (create Beads issue later)

**Human-readable lookup:**
```bash
scripts/bd-what 7vu  # Shows: bd-7vu: GUARD_TASK_TOOL_ENFORCEMENT
```

**Deprecated:** `feature/<KEY>` (slash), Worktrees for agents

---

### Branch Protection (GitHub Rulesets)

**Targets:**
- `master` (main branch)
- `release/*` (future releases)

**Rules:**
- All merges via PRs; direct pushes blocked; force-pushes restricted
- Required checks: docbot, danger (comment-only initially), CI Lite linters/tests
- Reviews: min 1 approval; CODEOWNERS required on high-risk paths (migrations/**, workflows/**)
- PRs must include Feature Key + Docs/Tests/Scripts paths (template enforces)

---

### Trunk Workflow (Lean, 2025 Best Practices)

**Default approach:**
- Small changes (<100 lines): Commit directly to master
- Large/risky changes: Create feature branch + PR for review
- All PRs target `master`

**Beads tracking:**
- Retroactive tracking OK (use `scripts/bd-retroactive`)
- Feature-Key helpful but not required for tiny fixes
- Post-commit hook reminds if missing

**Safety:**
- CI validates every push
- Fast rollback via `git revert`
- Railway environments provide deployment safety

---

### Do Not

- Edit the old Markdown feature registry (replaced by Beads)
- Run commands outside Railway for protected operations
- Bypass Serena for code edits (use Serena-first for symbol-level operations)
- Introduce schema changes without validating with Beads Schema Impact field
- Use `railway run` — always use `railway shell` for interactive sessions
- Push directly to master (create PR instead)

---

## 📚 Reference & Links

### Core Docs

**When to Read:**
- **AGENTS.md** (this file): Daily workflows, commands, constraints
- **ARCHITECTURE.md**: System design, stack overview (read when: onboarding, planning refactors)
- **PATTERNS.md**: Code patterns, integration examples (reference when: implementing features, debugging)

**Reference Guides:**
- Local environment: docs/DX_LOCAL_ENV_SETUP.md
- Common workflows: docs/DX_WORKFLOWS.md
- Docs process: docs/DX_DOCS_PROCESS.md
- Command optimization: docs/DX_COMMAND_OPTIMIZATION.md

---

### External Guides

- **Claude Code:** https://docs.claude.com/en/docs/claude-code/
  - Sub-agents: /sub-agents
  - Skills: /skills
  - Plugins: /plugins
  - Hooks: /hooks-guide
  - GitHub Actions: /github-actions
- **OpenCode:** https://opencode.ai/docs/
  - Agents: /agents/
  - Commands: /commands/
  - Custom tools: /custom-tools/
  - GitHub: /github/
  - Plugins: /plugins/
- **Beads:** https://github.com/steveyegge/beads, https://github.com/steveyegge/beads/blob/main/AGENTS.md
- **Serena:** https://github.com/oraios/serena/blob/main/README.md

---

### CI/Automation Quick Reference

| System | What It Does | Agent Action |
|--------|--------------|--------------|
| **Claude Code** | Automated PR reviews + ChatOps | @claude mentions trigger, review comments auto-posted |
| **Danger** | Comment-only nudges | Read hints, paste suggested commands |
| **PR Template** | Required checkboxes | Feature Key, Docs path, Beads link, Railway |
| **Labeler** | Auto-labels paths | migrations/**, workflows/**, scripts/**, docs/** |
| **CODEOWNERS** | Required review | 1 approval on: migrations/**, workflows/**, scripts/commands/** |
| **Actions** | Concurrency groups | Superseded runs auto-cancelled |

**Claude Code Details:** See `docs/DX_GITHUB_ACTIONS.md` for workflow configuration, troubleshooting, and OpenCode migration.

**Multi-VM Policy:**
- Default: 1 active feature per VM
- Use commit trailers: Feature-Key, Agent, Role
- 2+ features on same VM → CI posts soft warning

---

### Problem-Solving Philosophy

**When something breaks → Answer 3 questions before fixing:**

| Question | If NO → STOP |
|----------|--------------|
| 1. **Why** did this happen? | You're treating symptom, not root cause |
| 2. **Will** this happen again? | You haven't prevented recurrence |
| 3. **How** do I fix systemically? | You're not fixing the pattern |

**Full details:** See PATTERNS.md "Problem-Solving Philosophy" section

---

### Troubleshooting & Recovery

#### Tool Violations

**Symptom:** Hook error "You used [WRONG TOOL]" or manual detection

**Quick Fix:**
1. Check if hook fired: Search transcript for `PreToolUse:... hook error`
2. Classify: hook didn't fire | I ignored it | unclear instructions
3. If needed: Run `/tool-violation-i --tool [WRONG] --should-use [RIGHT]`
4. Test: Try same operation again (verify fix)

**Note:** Tool violations are rare if following "My Frequent Mistakes" table. Most hook errors resolve by simply retrying with correct tool.

#### Common Issues

| Problem | Solution |
|---------|----------|
| **Beads warns about production DB** | Expected warning outside Railway - safe to proceed for normal operations |
| **bd sync fails: "JSONL is newer than database"** | Run `bd export --force` then `bd sync` - Happens when daemon auto-exports between your changes and sync (timestamp skew, not real conflict) |
| **bd sync fails: "Missing Feature-Key trailer"** | Fixed in commit 3f9d044 - Hook now exempts Beads auto-commits. If still occurring, check `.githooks/commit-msg` has the exemption (line 15) |
| **bd sync fails on master: "Pushing directly to master is blocked"** | Expected - pre-push hook protects master. Use `bd export --force` to export JSONL without push, or only run `bd sync` on feature branches. See bd-ecl for upstream fix. |
| **Git hooks not executable / losing permissions** | Remove `core.hooksPath`, use standard `.git/hooks/`. Run `bd hooks install` to reinstall. Hooks should stay executable. If custom hooks needed, merge into Beads hooks (see `.git/hooks/pre-push` for example). |
| **Divergent branches error on git pull** | Run `git pull --rebase` to rebase local commits on top of remote. Or set default: `git config pull.rebase true` for linear history. |
| **Serena can't find symbol** | Check `relative_path` parameter, try `substring_matching=True`, or use `/search` first |
| **Skill doesn't trigger** | Check exact phrase match in skill description (e.g., "commit my work" not "commit changes") |
| **Git hook blocks commit** | Read error message - usually missing Feature-Key or branch naming issue |
| **CI fails on PR** | Check Danger comments for specific guidance, run suggested commands locally |

**Pro-Tip: Meta-Skills for Epic-Specific Context**

CONSIDER creating generic skill-creators (i.e., `docs-{epic}` via the docs-create skill). THINK LOTS about extending this pattern to other custom skills specific to an epic:
- External docs caching (`/docs-create bd-xyz <url1> <url2>`)
- Epic-specific test suites (`/tests-create bd-xyz`)
- Custom validation rules (`/validators-create bd-xyz`)
- Domain-specific tools (`/tools-create bd-xyz`)

Pattern: Meta-skill generates epic-scoped skill → Auto-activates on epic context → Archives when epic completes

**Full troubleshooting guide:** docs/DX_TROUBLESHOOTING.md (TODO: create this)

---

### Deprecated

- **V2 DX System:** All `/sync-i`, `/merge-i`, `/guardrails-i`, `/feature-*-i` commands removed (replaced by V3 natural language skills)
- **sync-coordination-v2** script (replaced by sync-feature-branch skill)
- **feature/<KEY>** branch naming (use `feature-<KEY>` with dash instead)
- **Worktrees for agents** (humans may still use for ergonomics)
- **agent-coordination branch** (fully removed; all references updated to `master`)

---

### Claude Code Operating Contract

**Core Operating Principles:**
- **Issue-First** - Create Beads issue BEFORE any implementation work
  - Tiny edits (<10 lines, obvious fix): Optional
  - Everything else: Required (task/bug/feature/epic/chore)
  - Pattern: Classify → Create → Implement → Commit → Close
  - Hook enforces via issue-first skill auto-activation
- **Serena‑first** for search, code navigation, and symbolic edits
- **Beads** for feature tracking and issue management (bd create/update/close)
- **Natural language skills** for all VCS/PR operations ("commit my work", "create PR")
- **High‑risk paths protected** via git hooks; do not modify hooks/commands/settings in‑session
- **CI validates async**: Trust environments (dev/staging/prod) for testing and deployment

**Mandatory Workflows:**
- Implementation work → Use issue-first skill BEFORE coding (creates Beads tracking issue)
- Git operations → Say "commit my work" (sync-feature-branch skill) or "create PR" (create-pull-request skill)
- Search operations → mcp__serena__search_for_pattern or mcp__serena__list_dir
- Feature tracking → `bd create|update|close` with proper feature keys
- Protected edits → Create PR via skills; git hooks enforce repo policy

---

**Last Updated:** 2025-01-10
**Optimized for:** AI agents (Claude Code, OpenCode)
**Line Count:** ~380 lines (30% reduction from 542, improved hierarchy)
