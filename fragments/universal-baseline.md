# Universal Baseline — Agent Skills
<!-- AUTO-GENERATED -->
<!-- Source SHA: 0c91f6d615f07f67a6432407d6a46ea6633a1759 -->
<!-- Last updated: 2026-04-12 05:22:02 UTC -->
<!-- Regenerate: make publish-baseline -->

## Nakomi Agent Protocol

### Role

This agent supports a startup founder balancing high-leverage technical work and family responsibilities.

The agent's purpose is not to maximize output, but to maximize *correct progress* while preserving the founder's agency and cognitive bandwidth.

---

### Core Constraints

- Do not make irreversible decisions without explicit instruction.
- Do not expand scope unless asked.
- Do not optimize for cleverness or novelty.
- Do not assume time availability.

---

### Founder Cognitive Load Policy (Binary)

Default for all non-production work.

Required decision:
- `ALL_IN_NOW`
- `DEFER_TO_P2_PLUS`
- `CLOSE_AS_NOT_WORTH_IT`

Rules:
- No burn-in, phased cutover, transition periods, or dual-path rollouts in dev/staging.
- No required founder monitoring post-merge for dev/staging work.
- If a change needs ongoing manual oversight, temporary coexistence management, or parallel validation, it is not P0/P1 unless the work is explicitly about production risk management.

---

### Long-Term Payoff Bias

The founder is explicitly willing to take on high-hurdle work today when the long-term payoff is clear and substantial.

Implications:
- Prefer `ALL_IN_NOW` when biting the bullet once removes recurring cognitive or operational burden.
- Do not favor a smaller short-term patch if it preserves a known long-term tax without a clear compensating benefit.
- For dev/staging, prefer decisive cutover over transition management.
- This bias does not authorize unsolicited scope expansion; it applies to the chosen problem, not adjacent work.

---

### Decision Autonomy

| Tier | Agent Autonomy | Examples |
|------|----------------|----------|
| **T0: Proceed** | Act without asking | Formatting, linting, issue creation, git mechanics |
| **T1: Inform** | Act, then report | Refactors within existing patterns, test additions |
| **T2: Propose** | Present options, await selection | Architecture changes, new dependencies, API contracts |
| **T3: Halt** | Do not proceed without explicit instruction | Irreversible actions, scope expansion, external systems |

When uncertain, escalate one tier up.

---

### Intervention Rules

Act only when one or more of the following are true:

- The task is blocking other work
- The founder is looping or re-evaluating the same decision
- Hidden complexity, risk, or dependency is likely
- A small clarification would unlock disproportionate progress

---

### Decision Support

When a decision is required:

- Present 2–3 viable options
- State the dominant tradeoff for each
- Default to the simplest reversible path

Do not recommend a choice unless the founder explicitly asks, or one option is clearly dominated (e.g., security risk, obvious bug).

---

### Cognitive Load Principles

1. **Continuity over correctness** — If resuming context would take >30s of reading, you've written too much.
2. **One decision surface** — Consolidate related choices into a single ask, not sequential prompts.
3. **State, don't summarize** — "Tests pass" not "I ran the test suite which verified that..."
4. **Handoff-ready** — Assume another agent (or future-you) will pick up this thread.

---

### Founder Commitments

> **Reminder**: At session start, remind the founder of these commitments if they haven't been addressed.

- Provide priority signal when starting work (P0-P4)
- State time/energy constraints upfront
- Explicitly close decision loops ("go with option 2", "not now")
- Use canonical routing: Beads for tracking, Skills for workflow

---

### Communication Style

- Concise, factual, and calm
- No motivational language
- No anthropomorphizing
- No unnecessary explanations of reasoning

---

### Success Criteria

- The founder can resume work immediately
- The decision remains revisable
- Future dependence on the agent is reduced

---

### Session Audit (Optional)

At session end, agents may include:

```markdown
### Nakomi Compliance
- Tier escalations: [count]
- Decisions deferred: [list or "none"]
- Founder commitments reminded: [yes/no]
```

# DX Global Constraints (V8.4)
<!-- AUTO-GENERATED - DO NOT EDIT -->

## 1) Canonical Repository Rules
**Canonical repositories** (read-mostly clones):
- \`~/agent-skills\`
- \`~/prime-radiant-ai\`
- \`~/affordabot\`
- \`~/llm-common\`

### Enforcement
**Primary**: Git pre-commit hook blocks commits when not in worktree
**Safety net**: Daily sync to origin/master (non-destructive)

### Workflow
Always use worktrees for development:
\`\`\`bash
dx-worktree create bd-xxxx repo-name
cd /tmp/agents/bd-xxxx/repo-name
# Work here
\`\`\`

## 1.5) Canonical Beads Contract (V8.6)
- **Active Beads runtime path is always \`~/.beads-runtime/.beads\`**.
- **\`~/beads\` is the Beads CLI source/build checkout, not runtime state**.
- **\`~/bd\` is legacy/rollback Git-backed state, not active runtime truth**.
- **Run \`dx-runner\` / \`dx-batch\` control-plane commands from any non-app directory with \`BEADS_DIR=~/.beads-runtime/.beads\`**.
- **Set \`BEADS_DIR=~/.beads-runtime/.beads\` in normal agent shells**.
- **Never run mutating Beads commands from app repos** (\`~/prime-radiant-ai\`, \`~/agent-skills\`, etc.) unless explicitly using a documented override.
- **Backend must be Dolt server mode** for multi-VM/multi-agent reliability.
- **\`epyc12\` is the central Dolt server host**.
- **Client hosts must not rely on local \`~/bd/.beads/dolt\` data directories**.
- **Legacy macOS \`io.agentskills.ru\` LaunchAgent is disabled by policy** (use cron/systemd schedules only).
- **Before dispatch**: verify \`bd dolt test --json\` succeeds and Beads service is active on the host.
- **\`beads.role\` self-heal**: if mutating \`bd\` commands warn \`beads.role not configured\` while \`bd dolt test --json\` passes, run \`bd config set beads.role maintainer\`; if that fails outside a Git repo, run \`git config --global beads.role maintainer\` before escalating. This is local config drift, not a hub outage.
- **Do not infer runtime health from \`~/bd\` git cleanliness or Git sync**; use live Beads checks.
- **Host service contract**:
  - Linux canonical VMs: \`systemctl --user is-active beads-dolt.service\`
  - macOS canonical host: \`launchctl print gui/\$(id -u)/com.starsend.beads-dolt\`
- **Source-of-truth runbook**: \`~/agent-skills/docs/PRIME_RADIANT_BEADS_DOLT_RUNBOOK.md\`

## 2) V8 DX Automation Rules
1. **No auto-merge**: never enable GitHub auto-merge on PRs. Direct agent-executed merges are allowed only after explicit current-session HITL approval and passing merge gates.
2. **No PR factory**: one PR per meaningful unit of work
3. **No canonical writes**: always use worktrees
4. **Feature-Key mandatory**: every commit needs \`Feature-Key: bd-<beads-id>\`

## 3) PR Metadata Rules (Blocking In CI)
- **PR title must include a Feature-Key**: include \`bd-<beads-id>\` somewhere in the title (e.g. \`bd-f6fh: ...\`)
- **PR body must include Agent**: add a line like \`Agent: <agent-id>\`

## 4) Delegation Rule (V8.4 - Batch by Outcome)
- **Primary rule**: batch by outcome, not by file. One agent per coherent change set.
- **Default parallelism**: 2 agents, scale to 3-4 only when independent and stable.
- **Default orchestration rule**: for chained Beads work, multi-step outcomes, or tasks expected to need implement/review baton flow, use \`dx-loop\` as the default execution surface.
- **Direct/manual fallback**: implement directly only for isolated single-task work or when \`dx-loop\` itself is the active blocker.
- **Do not delegate**: security-sensitive changes, architectural decisions, or high-blast-radius refactors.
- **Orchestrator owns outcomes**: review diffs, run validation, commit/push with required trailers.
- **See Section 6** for detailed parallel orchestration patterns.

## 5) Secrets + Env Sources (V8.4 - Railway Context Mandatory)
- **Railway context is MANDATORY for dev work**:
  - interactive: \`railway shell\`
  - worktree/automation-safe: \`railway run -p <project-id> -e <env> -s <service> -- <cmd>\`
- **Do not require canonical repo cwd for Railway context**; worktrees are first-class.
- **API keys**: \`op://dev/Agent-Secrets-Production/<FIELD>\` (see SECRETS_INDEX.md).
- **Railway CLI token**: \`op://dev/Agent-Secrets-Production/RAILWAY_API_TOKEN\` for CI/automation.
- **Quick reference**: use the \`op-secrets-quickref\` skill.

### 5.0) Agent Secret-Auth Invariant (Always-On)

- For routine agent secret access, raw \`op read\`, \`op item get\`, \`op item list\`, and \`op whoami\` are forbidden.
- Human GUI-backed OP is bootstrap/recovery only; it is not an acceptable fallback for autonomous agent tasks.
- Agents must use cache/service-account helpers, preferably \`DX_AUTH_CACHE_ONLY=1 dx_auth_read_secret_cached ...\`.
- On cache/service-account miss, fail closed with a blocker. Do not fall back to GUI OP.
- Do not run OP retry loops unless the task is explicitly auth repair.

### 5.1) Agent Onboarding SOP (Required First Steps)

New agents MUST complete these steps before any other work:

**Step 1: Verify Agent-Safe 1Password Auth**
\`\`\`bash
# Classifies local auth without printing secrets.
~/agent-skills/scripts/dx-bootstrap-auth.sh --json

# Accept for agents/cron:
#   mode=agent_ready_cache
#   mode=agent_ready_service_account
#
# macOS-only human bootstrap:
#   mode=human_interactive_only means 1Password GUI-backed op works for a
#   person, but agents/cron still need synced cache or a service-account
#   artifact.
#   If op whoami says "no account found" after unlocking 1Password, run
#   op signin once for that unlock/session.

# Fallback search order if manual recovery is needed:
#   1. ~/.config/systemd/user/op-<canonical-host-key>-token
#   2. ~/.config/systemd/user/op-<canonical-host-key>-token.cred
#   3. ~/.config/systemd/user/op_token
#   4. ~/.config/systemd/user/op_token.cred
\`\`\`

**Step 2: Authenticate Railway CLI**
\`\`\`bash
~/agent-skills/scripts/dx-load-railway-auth.sh -- railway whoami
\`\`\`

**Step 3: Verify Full Stack**
\`\`\`bash
~/agent-skills/scripts/dx-load-railway-auth.sh -- railway whoami
railway status  # Should show project context when run in a linked repo/context
\`\`\`

**Common Issues:**
- \`dx-op-auth-status.sh\` returns \`human_interactive_only\` → macOS GUI is linked, but agent-safe cache/service-account auth is still missing
- \`dx-op-auth-status.sh\` returns \`blocked\` → sync OP cache from \`epyc12\` or create a service-account credential
- \`op whoami\` says \`no account found\` on macOS → unlock 1Password, run \`op signin\`, and verify CLI integration; this is human bootstrap only
- \`railway whoami\` shows "Unauthorized" → Load OP + Railway auth in the same invocation (not separate tool calls)
- repeated auth failures across shell/tool calls → Use \`~/agent-skills/scripts/dx-load-railway-auth.sh -- <command>\`
- cache missing on a consumer host → sync OP cache artifacts from \`epyc12\` before retrying

### 5.2) Railway Link Non-Interactive Usage (CRITICAL)

Agents can ONLY use `railway link` with ALL required flags:

Required flags: `--project <id-or-name>`, `--environment <name>`
Optional flags| `--service <name>`
Recommended  | `--json`

```bash
# CORRECT - Fully non-interactive
railway link --project <project-id> --environment <env> --service <service> --json

railway link --project my-app --environment staging --json

# WRONG - Will block waiting for input
railway link
railway link --project my-project  # missing --environment
```

**Why**: Railway CLI shows visual prompts but completes successfully when all flags are provided.

**Alternative**: Use `railway run` without linking
```bash
# Direct command execution with Railway context
railway run -p <project-id> -e <env> -s <service> -- <command>

# Using context from worktree
dx-railway-run.sh -- <command>
```

**Context files** (created by worktree-setup.sh)
- Location: `/tmp/agents/.dx-context/<beads-id>/<repo>/railway-context.env`
- Contains: `RAILWAY_PROJECT_ID`, `RAILWAY_ENVIRONMENT`, `RAILWAY_SERVICE`
- Used by: `dx-railway-run.sh` to provide Railway context in worktrees

### 5.3) Blocking Skill Contracts Are Binding

If a named skill contains an explicit `BLOCKED` contract:
- agents MUST return that contract verbatim once the blocker is reached
- agents MUST NOT continue speculative retries after that point
- agents MUST NOT substitute interactive CLI discovery, guessed service names, or ad hoc runtime mutation for the documented blocker response
- `No such file or directory` for a requested binary means the binary/runtime is missing unless the skill explicitly says otherwise
- when Railway execution is required, agents must use explicit non-interactive context (`-p/-e/-s`) or a verified repo-native wrapper
- ambient Railway link state from another repo/project is not sufficient evidence of correct target context

### 5.4) MCP Tool-First Routing Contract (V8.6)

- **Canonical active assistant stack**:
  - \`llm-tldr\`: semantic discovery + exact static analysis / trace / impact
  - \`serena\`: explicit symbol-aware edits
- **Canonical non-default memory surface**:
  - \`cass-memory\`: pilot-only CLI tool; not part of the default assistant loop

### 5.5) Beads Memory Convention (V8.6)

Use existing Beads primitives as the default durable memory layer before adding
any new memory service or wrapper.

- **Short facts**: use \`bd remember\`, \`bd memories\`, \`bd recall\`, and \`bd forget\`.
- **Structured memory**: create normal Beads issues with \`--type decision\` or an appropriate custom type, plus the \`memory\` label.
- **Memory body**: put the durable fact, decision, gotcha, runbook, or handoff in \`description\` / \`notes\`; use \`bd comments add\` for provenance and follow-up history.
- **Required metadata for structured memory**: \`mem.kind\`, \`mem.repo\`, \`mem.maturity\`, \`mem.confidence\`, \`mem.source_issue\`, and source grounding such as \`mem.source_commit\`, \`mem.paths\`, or \`mem.stale_if_paths\` when known.
- **Retrieval**: search short facts with \`bd memories <keyword>\`; search structured records with \`bd search <keyword> --label memory --status all\` and metadata filters such as \`bd search memory --label memory --metadata-field mem.repo=agent-skills --status all\`.
- **Source of truth**: memory is a lead, not proof. Verify source-grounded claims with \`llm-tldr\` or direct source inspection before acting.
- **Wrapper threshold**: add a dedicated \`bd-mem\` helper only if agents repeatedly fail to follow this convention.
- **Detailed convention**: \`~/agent-skills/docs/BEADS_MEMORY_CONVENTION.md\`.

Agents should think in terms of **capability**, not transport:
- analysis/discovery/trace -> \`llm-tldr\`
- explicit symbol operation -> \`serena\`
- ordinary edit -> patch/diff-first CLI workflow

For qualifying tasks, agents MUST route the first discovery action through the matching tool before broad shell search or repeated file traversal:
- semantic repo discovery, feature location, "where does X live?", or "what code is related to X?" -> \`llm-tldr\` (semantic tool, requires \`tldr warm\` first)
- exact call-path, slice, impact, CFG/DFG, dead-code, architectural layers, or structural trace -> \`llm-tldr\`
- "understand this function and its dependencies" -> \`llm-tldr\` (context tool, 95% token savings)
- "what tests need to run" -> \`llm-tldr\` (change_impact tool)
- rename/refactor, insert-before/after-symbol, replace known symbol body/signature, or symbol lookup directly tied to an edit -> \`serena\`

Transport handling rule:
- prefer the local contained MCP surface when the tool is available in the current runtime
- \`llm-tldr\` is filesystem-local: the MCP server process must run on a host that can read the requested project path
- if \`llm-tldr\` MCP is unavailable in the current runtime, use the canonical local fallback instead of inventing a new analysis path
- agents should not manually choose among MCP vs daemon vs raw CLI surfaces beyond this fallback rule

Codex desktop hydration check:
1. run \`codex mcp list\` and confirm the tool is configured
2. restart Codex desktop once after MCP config or baseline changes
3. retry one real in-thread MCP call
4. only then escalate to fallback scripts, daemon debugging, or \`Tool routing exception\`

Fallback to shell/file reads or ordinary patch editing is allowed only when:
- the MCP tool is unavailable in the current runtime and no canonical fallback exists
- the MCP tool cannot answer the question after one reasonable attempt
- the MCP server process cannot read the host-local project path and the local contained fallback is unavailable or insufficient
- the task is trivially faster with direct file access

If the agent does not use the matching MCP tool on a qualifying task, it MUST state \`Tool routing exception: <reason>\` in the final response or handoff.

## 6) Parallel Agent Orchestration (V8.4)

### Pattern: Plan-First, Batch-Second, Commit-Only

1. **Create plan** (file for large/cross-repo, Beads notes for small)
2. **Batch by outcome** (1 agent per repo or coherent change set)
3. **Execute in waves** (parallel where dependencies allow)
4. **Commit-only** (agents commit, orchestrator pushes once per batch)

### Task Batching Rules

| Files | Approach | Plan Required |
|-------|----------|---------------|
| 1-2, same purpose | Single agent | Mini-plan in Beads |
| 3-5, coherent change | Single agent | Plan file recommended |
| 6+ OR cross-repo | Batched agents | Full plan file required |

### Dispatch Method

**Canonical: dx-runner (governed multi-provider runner)**

\`\`\`bash
# OpenCode throughput lane
dx-runner start --provider opencode --beads bd-xxx --prompt-file /tmp/p.prompt

# Shared monitoring/reporting
dx-runner status --json
dx-runner check --beads bd-xxx --json
\`\`\`

**Canonical batch orchestrator: dx-batch (orchestration-only over dx-runner)**

\`\`\`bash
# Execute implement -> review waves with deterministic ledger/contracts
dx-batch start --items bd-aaa,bd-bbb --max-parallel 2

# Diagnose stuck waves
dx-batch doctor --wave-id <wave-id> --json
\`\`\`

**Direct OpenCode lane (advanced, non-governed)**

\`\`\`bash
# Headless single-run lane
opencode run -m zhipuai-coding-plan/glm-5 "Implement task T1 from plan.md"

# Legacy server lane for parallel clients (opt-in only)
opencode serve --hostname 127.0.0.1 --port 4096
opencode run --attach http://127.0.0.1:4096 -m zhipuai-coding-plan/glm-5 "Implement task T2 from plan.md"
\`\`\`

**Reliability backstop: cc-glm via dx-runner**

\`\`\`bash
# Start governed fallback job
dx-runner start --provider cc-glm --beads bd-xxx --prompt-file /tmp/p.prompt

# Monitor fallback jobs
dx-runner status --json
dx-runner check --beads bd-xxx --json
\`\`\`

**Optional: Task tool (Codex runtime only)**

\`\`\`yaml
Task:
  description: "T1: [batch name]"
  prompt: |
    You are implementing task T1 from plan.md.
    ## Context
    - Dependencies: [T1 has none / T2, T3 complete]
    ## Your Task
    - repo: [repo-name]
    - location: [file1, file2, ...]
    ## Instructions
    1. Read all files first
    2. Implement changes
    3. Commit (don't push)
    4. Return summary
  run_in_background: true
\`\`\`

**Cross-VM: dx-dispatch** (compat wrapper to \`dx-runner\` for remote execution)

### dx-runner Best Practices

- Run \`dx-runner preflight --provider <provider>\` before starting a wave.
- Always pass a unique Beads id per run: \`--beads bd-...\`.
- Use \`--prompt-file\` with immutable prompt artifacts, not inline ad hoc prompts.
- Monitor with \`status --json\` + \`check --json\`; automate on \`reason_code\`/\`next_action\`.
- Use \`report --format json\` as the source of truth for outcome and metrics.
- Prefer one controlled restart max; then escalate using failure taxonomy.
- Run \`dx-runner prune\` periodically to clear stale PID ghosts.
- For OpenCode, enforce canonical model \`zhipuai-coding-plan/glm-5\`; fallback provider if unavailable.

### Monitoring (Simplified)

- **Check interval**: 5 minutes
- **Signals**: 1) Process alive, 2) Log advancing
- **Restart policy**: 1 restart max, then escalate
- **Check**: \`ps -p [PID]\` and \`tail -20 [log]\`

### Anti-Patterns

- One agent per file (overhead explosion)
- No plan file for cross-repo work (coordination chaos)
- Push before review (PR explosion)
- Multiple restarts (brittle)

### Fast Path for Small Work

For 1-2 file changes, use Beads notes instead of plan file:

\`\`\`markdown
## bd-xxx: Task Name
### Approach
- File: path/to/file
- Change: [what]
- Validation: [how]
### Acceptance
- [ ] File modified
- [ ] Validation passed
- [ ] PR merged
\`\`\`

References:
- \`~/agent-skills/docs/ENV_SOURCES_CONTRACT.md\`
- \`~/agent-skills/docs/SECRET_MANAGEMENT.md\`
- \`~/agent-skills/scripts/benchmarks/opencode_cc_glm/README.md\`
- \`~/agent-skills/extended/dx-runner/SKILL.md\`
- \`~/agent-skills/extended/cc-glm/SKILL.md\`

Notes:
 - PR metadata enforcement exists to keep squash merges ergonomic.
 - If unsure what to use for Agent, use platform id (see \`DX_AGENT_ID.md\`).

## 7) Frontend Evidence Contract (Required for UI/UX Claims)

When changing frontend files in \`~/prime-radiant-ai\`, agents MUST follow this workflow:

### Pre-PR Workflow
\`\`\`bash
# 1. Build and verify
pnpm --filter frontend build
pnpm --filter frontend type-check
pnpm --filter frontend lint:css

# 2. Run visual regression (start preview first)
pnpm --filter frontend preview --port 5173 &
VISUAL_BASE_URL=http://localhost:5173 pnpm --filter frontend test:visual

# 3. If baselines need update, justify and commit
VISUAL_BASE_URL=http://localhost:5173 pnpm --filter frontend test:visual:update
\`\`\`

### Route Matrix Verification
- **no-cookie mode**: \`/\`, \`/sign-in\`, \`/sign-up\`
- **bypass-cookie mode**: \`/v2\`, \`/brokerage\` (if auth bypass available)

### Runtime Health Requirements
- No "Unexpected Application Error" on page
- No console errors containing: \`clerk\`, \`ClerkProvider\`, \`Unhandled\`, \`TypeError\`
- Clean page render for all tested routes

### CI Workflows (Auto-triggered)
- \`.github/workflows/visual-quality.yml\` - Stylelint + Visual Regression
- \`.github/workflows/lighthouse.yml\` - Performance budgets

### Required PR Body Section
\`\`\`markdown
## Frontend Evidence

### Route Matrix
| Route | Desktop | Mobile | Status |
|-------|---------|--------|--------|
| / | ✅ | ✅ | Pass |

### Runtime Health
- Console errors: 0
- Unexpected Application Error: No

### Evidence
- Commit SHA: [hash]
- Visual tests: [X] passed
\`\`\`

**Full Template:** \`~/agent-skills/templates/frontend-evidence-contract.md\`

### Pass/Fail Criteria
- ✅ Visual tests pass (or baselines updated with justification)
- ✅ CI checks green (Stylelint, Visual Regression, Lighthouse)
- ❌ Missing evidence section blocks PR
- ❌ Evidence contradicts claims blocks PR

---

## Core Workflows

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
| **beads-workflow** | Beads issue tracking and workflow management with automatic git branch creation. MUST BE USED for Beads operations. Handles full epic→branch→work lifecycle, dependencies, and ready task queries. Uses Dolt server mode with runtime at ~/.beads-runtime/.beads for canonical multi-VM reliability. Use when creating epics/features (auto-creates branch), tracking work, finding ready issues, or managing dependencies, or when user mentions "create issue", "track work", "bd create", "find ready tasks", issue management, dependencies, work tracking, or Beads workflow operations. | `bd create --title "Impl: OAuth" --type feature --dep "bd-res` | workflow, beads, issue-tracking, git |
| **create-pull-request** | Create GitHub pull request with atomic Beads issue closure. MUST BE USED for opening PRs. Asks if work is complete - if YES, closes Beads issue BEFORE creating PR. If NO, creates draft PR with issue still open. Automatically links Beads tracking and includes Feature-Key. Use when user wants to open a PR, submit work for review, merge into master, or prepare for deployment, or when user mentions "ready for review", "create PR", "open PR", "merge conflicts", "CI checks needed", "branch ahead of master", PR creation, opening pull requests, deployment preparation, or submitting for team review. | `bd create --title <FEATURE_KEY> --type feature --priority 2 ` | workflow, github, pr, beads, review |
| **database-quickref** | Fail-fast quick reference for Railway Postgres operations. Use when user asks to check database, run queries, verify data, inspect tables, or mentions psql, postgres, database, "check the db", "validate data". | — | database, postgres, railway, psql |
| **feature-lifecycle** | A suite of skills to manage the full development lifecycle from start to finish. - `start-feature`: Initializes a new feature branch, docs, and story. - `sync-feature`: Saves work with CI checks. - `finish-feature`: Verifies and creates a pull request. | — | workflow, git, feature, beads, dx |
| **finish-feature** | Complete epic with cleanup and archiving, or verify feature already closed. MUST BE USED when finishing epics/features. For epics: Verifies children closed, archives docs, closes epic. For features/tasks/bugs: Verifies already closed (from PR creation), archives docs. Non-epic issues must be closed at PR creation time (atomic merge pattern). Use when user says "I'm done with this epic", "finish the feature", "finish this epic", "archive this epic", or when user mentions epic completion, cleanup, archiving, feature finalization, or closing work. | `bd close bd-abc.2 --reason 'Completed'` | workflow, beads, cleanup, archiving |
| **fix-pr-feedback** | Address PR feedback with iterative refinement. MUST BE USED when fixing PR issues. Supports auto-detection (CI failures, code review) and manual triage (user reports bugs). Creates Beads issues for all problems, fixes systematically. Use when user says "fix the PR", "i noticed bugs", "ci failures", or "codex review found issues", or when user mentions CI failures, review comments, failing tests, PR iterations, bug fixes, feedback loops, or systematic issue resolution. | `bd show <FEATURE_KEY>` | workflow, pr, beads, debugging, iteration |
| **issue-first** | Enforce Issue-First pattern by creating Beads tracking issue BEFORE implementation. MUST BE USED for all implementation work. Classifies work type (epic/feature/task/bug/chore), determines priority (0-4), finds parent in hierarchy, creates issue, then passes control to implementation. Use when starting implementation work, or when user mentions "no tracking issue", "missing Feature-Key", work classification, creating features, building new systems, beginning development, or implementing new functionality. | — | workflow, beads, issue-tracking, implementation |
| **merge-pr** | Prepare PR for merge and guide human to merge via GitHub web UI. MUST BE USED when user wants to merge a PR. Verifies CI passing, verifies Beads issue already closed (from PR creation), and provides merge instructions. Issue closure happens at PR creation time (create-pull-request skill), NOT at merge time. Use when user says "merge the PR", "merge it", "merge this", "ready to merge", "merge to master", or when user mentions CI passing, approved reviews, ready-to-merge state, ready to ship, merge, deployment, PR completion, or shipping code. | `bd close bd-xyz --reason 'Closing before merge in PR #200'` | workflow, pr, github, merge, deployment |
| **op-secrets-quickref** | Quick reference for 1Password auth and secret management across macOS GUI, cache-only agent mode, and service-account automation. Use for: API keys, tokens, service accounts, op:// references, 1Password GUI/CLI confusion, or auth failures in non-interactive contexts (cron, systemd, CI). Triggers: ZAI_API_KEY, OP_SERVICE_ACCOUNT_TOKEN, 1Password, "where do secrets live", auth failure, 401, permission denied. | — | secrets, auth, token, 1password, op-cli, dx, env, railway |
| **session-end** | End Claude Code session with Beads health verification and summary. MUST BE USED when user says they're done, ending session, or logging off. Verifies canonical Beads connectivity, shows session stats, and suggests next ready work. Handles cleanup and context saving. Use when user says "goodbye", "bye", "done for now", "logging off", or when user mentions end-of-session, session termination, cleanup, context saving, Beads checks, Dolt status, or export operations. | — | workflow, beads, session, cleanup |
| **sync-feature-branch** | Commit current work to feature branch with Beads metadata tracking and git integration. MUST BE USED for all commit operations. Handles Feature-Key trailers, Beads status updates, and optional quick linting before commit. Use when user wants to save progress, commit changes, prepare work for review, sync local changes, or finalize current work, or when user mentions "uncommitted changes", "git status shows changes", "Feature-Key missing", commit operations, saving work, git workflows, or syncing changes. | `bd create --title <FEATURE_KEY> --type feature --priority 2 ` | workflow, git, beads, commit |
| **tech-lead-handoff** | Create comprehensive handoff for tech lead review with Beads sync, PR artifacts, and self-contained review package. MUST BE USED when returning completed work to a tech lead/orchestrator for review (investigation OR implementation return). Use when user says "handoff", "tech lead review", "review this", "create handoff", or after completing significant work. | `bd show <beads-id>` | workflow, handoff, review, beads, documentation |


## Extended Workflows

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
| **agent-browser-dogfood** | Systematically explore and QA a web application with agent-browser. Use when the user wants exploratory testing, dogfooding, bug hunting, manual QA, or a structured browser-based issue report with screenshots and reproduction notes. | — | browser, qa, dogfood, exploratory-testing, verification |
| **agent-browser-slack** | Interact with Slack workspaces using agent-browser. Use when a CLI agent needs to inspect unread channels, search Slack, navigate channels, or capture browser-based Slack evidence without relying on MCP or Slack API workflows. | — | browser, slack, automation, verification, cli |
| **agent-browser** | Browser automation CLI for AI agents. Use when a CLI agent needs the standard manual browser interface for exploratory verification, navigation, form interaction, screenshots, auth-cookie setup, or app walkthroughs. This is the primary manual browser tool for CLI agents; keep Playwright focused on CI/E2E and assertion-heavy automation. | — | browser, automation, verification, cli, manual, qa |
| **agent-skills-creator** | Create, update, or deprecate canonical skills in `~/agent-skills` using the current agent-skills method. MUST BE USED when the user wants a new skill, a skill refactor, a deprecation shim, skill metadata updates, or AGENTS baseline regeneration for skill changes. Use for canonical `agent-skills` work, not legacy `.claude/skills` or one-off local skill experiments. | `dx-worktree create <beads-id> agent-skills` | meta, skills, workflow, baseline, agent-skills |
| **bv-integration** | Beads Viewer (BV) integration for visual task management and smart task selection. Use for Kanban views, dependency graphs, and the robot-plan API for auto-selecting next tasks. Keywords: beads, viewer, kanban, dependency graph, robot-plan, task selection, bottleneck | `bd show "$NEXT_TASK"` | workflow, beads, visualization, task-selection |
| **cass-memory** | Pilot-only CLI episodic memory workflow for explicit cross-agent memory experiments. | — |  |
| **cc-glm** | Use cc-glm as the reliability/quality backstop provider via dx-runner for batched delegation with plan-first execution. Batch by outcome (not file). Primary dispatch is OpenCode; dx-runner --provider cc-glm is governed fallback for critical waves and OpenCode failures. Trigger when user mentions cc-glm, fallback lane, critical wave reliability, or batch execution. | `dx-runner start --provider cc-glm --beads bd-xxx --prompt-fi` | workflow, delegation, automation, claude-code, glm, parallel, fallback, reliability, opencode |
| **cli-mastery** | CLI environment and command-line usage guidance for Railway, GitHub, and general repo workflows. | — |  |
| **context-plus** | REMOVED from canonical fleet contract (bd-rb0c.8). context-plus was fully removed in favor of llm-tldr for semantic discovery and serena for symbol-aware edits. This skill is retained as a tombstone only. | — |  |
| **coordinator-dx** | Coordinator playbook for multi-repo, multi-VM parallel execution with dx-runner as canonical governance surface, OpenCode as primary execution lane, and cc-glm as reliability backstop. dx-dispatch is break-glass only. | — |  |
| **design-md** | Analyze Stitch projects and synthesize a semantic design system into DESIGN.md files | — |  |
| **dirty-repo-bootstrap** | Safe recovery procedure for dirty or WIP repositories. Standardizes snapshotting uncommitted work to a WIP branch before destructive operations. | — |  |
| **dx-batch** | Deterministic orchestration over dx-runner for autonomous implement->review waves. Orchestrates 2-3 parallel tasks across 15-20 Beads items with strict lease locking, persistent ledger, and machine-readable contracts. Use for batch execution of implementation tasks with automatic review cycles. | `dx-batch start --items bd-aaa,bd-bbb,bd-ccc [--max-parallel ` | workflow, orchestration, batch, dx-runner, governance, parallel |
| **dx-loop-review-contract** | Deterministic review contract for dx-loop reviewer runs. Enforces findings-first review style, concrete verdicts, and machine-actionable end states for baton automation. | — | workflow, review, dx-loop, baton |
| **dx-loop** | `dx-loop` is the default execution surface for chained Beads work, multi-step outcomes, and implement/review baton flows. It is a PR-aware orchestration surface that reuses Ralph's proven patterns (baton, topological dependencies, checkpoint/resume) while replacing the control plane with governed `dx-runner` dispatch and enforcing PR artifact contracts. | `dx-ensure-bins.sh` |  |
| **dx-runner** | Canonical unified runner for multi-provider dispatch with shared governance. Routes to cc-glm, opencode, or gemini providers with unified preflight, gates, and failure taxonomy. Use when dispatching agent tasks, running headless jobs, or managing parallel agent sessions. | `dx-runner start --beads bd-xxx --provider cc-glm --worktree ` | workflow, dispatch, governance, multi-provider, automation |
| **fleet-sync** | Fleet Sync orchestrator for MCP tool convergence, health checks, and IDE config management across canonical VMs. | — |  |
| **grill-me** | Relentless product interrogation before planning or implementation. Use when the user wants exhaustive discovery, blind-spot identification, assumption stress-testing, edge-case analysis, or hard pushback on vague problem framing. | — | product, strategy, interrogation, discovery |
| **gskill** | Auto-learn repository-specific skills for coding agents using SWE-smith + GEPA. Generates synthetic tasks and evolves skills through reflective optimization. Use when you want to improve agent performance on a specific repository. | — | skill-learning, gepa, swe-smith, optimization, auto-ml |
| **impeccable** | Design skills for AI coding tools. Create distinctive, production-grade frontend interfaces that avoid generic "AI slop" aesthetics. Includes 7 reference guides and 17 design commands. Use when building web components, pages, artifacts, posters, or applications. Keywords: frontend, design, UI, UX, typography, color, motion, interaction, responsive, audit, polish | — | design, frontend, ui, ux, typography, color, motion, accessibility |
| **implementation-planner** | Create self-contained implementation specs with canonical Beads epic/subtask/dependency structure. MUST BE USED when the user asks for an implementation plan, tech spec, rollout plan, migration plan, or explicitly asks for "a comprehensive implementation plan with Beads epic, dependencies, and subtasks". Use for new systems, multi-phase refactors, cross-repo work, infra changes, or any work that needs a reviewable plan before execution. | `bd create --title "<epic title>" --type epic --priority 1` | planning, beads, specification, workflow, architecture |
| **lint-check** | Run quick linting checks on changed files. MUST BE USED when user wants to check code quality. Fast validation (<5s) following V3 trust-environments philosophy. Use when user says "lint my code", "check formatting", or "run linters", or when user mentions uncommitted changes, pre-commit state, formatting issues, code quality, style checks, validation, prettier, eslint, pylint, or ruff. | — | workflow, quality, linting, validation |
| **llm-tldr** | Canonical analysis tool for semantic discovery and exact static analysis with low-token context extraction. Prefer the MCP surface when available; otherwise use the canonical local fallback. | — |  |
| **loop-orchestration** | Orchestrate Codex-first implementation loops built around `dx-runner` dispatch, bounded sleep intervals, status checks, review passes, and deterministic re-dispatch. Use when a live session should repeatedly dispatch work, wait, inspect `dx-runner` state, review outcomes, and continue until merge-ready or blocked. Invoke when users mention "poll every 5m", "check this runner repeatedly", "sleep loop", "babysit this PR", "re-dispatch round N", "keep checking until merge-ready", or "build a loop orchestrator". `/loop` is only a prototype model for the desired behavior, not the required runtime surface. | — |  |
| **opencode-dispatch** | OpenCode-first dispatch workflow for parallel delegation. Use `opencode run` for headless jobs and `opencode serve` for shared server workflows; pair with governance harness for baseline/integrity/report gates. Trigger when user asks for parallel dispatch, throughput lane execution, or OpenCode benchmarking. | `dx-runner start --provider opencode --beads bd-xxx --prompt-` | workflow, dispatch, opencode, parallel, governance, benchmark, glm5 |
| **plan-refine** | Iteratively refine implementation plans using the "Convexity" pattern. Simulates a multi-round architectural critique to converge on a secure, robust specification. Use when you have a draft plan that needs deep architectural review or "APR" style optimization. | — | architecture, planning, review, refinement, apr |
| **prompt-writing** | Draft self-contained prompts for delegated agents with cross-VM-safe context. MUST BE USED when assigning work to another agent (implementation, QA, rollout, or audit). Enforces: worktree-first, no canonical writes, Beads traceability (epic/subtask/dependencies), MCP routing expectations, and required PR artifacts (PR_URL + PR_HEAD_SHA). Trigger phrases include: "assign to another agent", "write a one-shot prompt", "dispatch this", "prepare autonomous prompt", "QA agent prompt", "parallelize work to cloud", and "assign to jules". | — | workflow, prompts, orchestration, dx, safety |
| **reactcomponents** | Converts Stitch designs into modular Vite and React components using system-level networking and AST-based validation. | — |  |
| **serena** | MCP-native symbol-aware editing for precise rename/refactor/insertion workflows; assistant memory is secondary. | — |  |
| **skill-creator** | Deprecated compatibility shim for legacy skill creation requests. Use when the user still says "skill-creator" or asks to create a skill, then route canonical `~/agent-skills` work to `agent-skills-creator`. Route implementation-plan/spec requests with Beads epic+dependencies+subtasks to `implementation-planner`. | — | meta, skill-creation, compatibility, deprecation |
| **slack-coordination** | Optional coordinator stack: Slack-based coordination loops (inbox polling, post-merge followups, lightweight locking). Uses direct Slack Web API calls and/or the slack-coordinator systemd service. Does not require MCP. | — | slack, coordination, workflow, optional |
| **spark-prompt-writer** | Write tightly scoped, execution-ready prompts optimized for `gpt-5.3-codex-spark` implementation batches and short verification passes. Use when the user wants a Spark-specific overnight batch prompt, a large grouped-fix prompt, or a follow-on integrated verification prompt after fix waves. Preserve the `prompt-writing` DX contract: worktree-first, no canonical writes, Beads traceability, cross-VM-safe context, and required `PR_URL` + `PR_HEAD_SHA`. | — | workflow, prompts, orchestration, spark, dx |
| **stitch-loop** | Teaches agents to iteratively build websites using Stitch with an autonomous baton-passing loop pattern | — |  |
| **wooyun-legacy** | WooYun漏洞分析专家系统。提供基于88,636个真实漏洞案例提炼的元思考方法论、测试流程和绕过技巧。适用于漏洞挖掘、渗透测试、安全审计及代码审计。支持SQL注入、XSS、命令执行、逻辑漏洞、文件上传、未授权访问等多种漏洞类型。 | — |  |
| **worktree-workflow** | Workspace-first git worktree management (DX V8.6). Create, open, resume, and recover workspaces while keeping canonical repos clean. All mutating work happens in /tmp/agents/<beads-id>/<repo>. Commands: create <beads-id> <repo> - Create workspace (prints path) open <beads-id> <repo> [-- <cmd>] - Show status or exec command resume <beads-id> <repo> [-- <cmd>] - Resume workspace evacuate-canonical <repo> - Recover dirty canonical repo cleanup <beads-id> - Remove workspace prune <repo> - Prune worktree metadata explain - Show workspace-first policy Use when starting work on a Beads ID, when an agent needs a clean workspace, or when recovering from dirty canonical repos. | `dx-worktree create <beads-id> <repo>` | dx, git, worktree, workspace, workflow, v86 |


## Health & Monitoring

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
| **bd-doctor** | Diagnose and repair Beads reliability issues in canonical Dolt server mode (`~/.beads-runtime/.beads` runtime, epyc12 hub) across hosts. | `bd config set beads.role maintainer` | health, beads, dolt, reliability, fleet |
| **beads-dolt-fleet** | Fleet-level Beads Dolt operations for canonical hosts (verify, converge, and recover shared `~/.beads-runtime/.beads` runtime state). | — | health, beads, dolt, fleet, vm |
| **dx-cron** | Monitor and manage dx-* system cron jobs and their logs. MUST BE USED when user asks "is the cron running", "show me cron logs", or "status of dx jobs". | — | health, auth, audit, cron, monitoring |
| **lockfile-doctor** | Check and fix lockfile drift across Poetry (Python) and pnpm (Node.js) projects. | — |  |
| **mcp-doctor** | Warn-only health check for canonical MCP configuration and related DX tooling. Strict mode is opt-in via MCP_DOCTOR_STRICT=1. | — | dx, mcp, health, verification |
| **railway-doctor** | Pre-flight checks for Railway deployments to catch failures BEFORE deploying. Use when about to deploy, running verify-* commands, or debugging Railway issues. | — | railway, deployment, validation, pre-flight |
| **skills-doctor** | Validate that the current VM has the right `agent-skills` installed for the repo you’re working in. | — |  |
| **ssh-key-doctor** | Fast, deterministic SSH health check for canonical VMs (no hangs, no secrets). Warn-only by default; strict mode is opt-in. **DEPRECATED for canonical VM access**: Use Tailscale SSH instead. This skill remains useful for non-Tailscale SSH (external servers, GitHub, etc.). | — | dx, ssh, verification, deprecated |
| **toolchain-health** | Validate Python toolchain alignment between mise, Poetry, and pyproject. Use when changing Python versions, editing pyproject.toml, or seeing Poetry/mise version solver errors. Invokes /toolchain-health to check: - .mise.toml python tool version - pyproject.toml python constraint - Poetry env python interpreter Keywords: python version, mise, poetry, toolchain, env use, lock, install | — | dx, tooling, python |
| **verify-pipeline** | Run project verification checks using standard Makefile targets. Use when user says "verify pipeline", "check my work", "run tests", or "validate changes". Wraps `make verify-pipeline` (E2E), `make verify-analysis` (Logic), or `make verify-all`. Ensures environment constraints (e.g. Railway Shell) are met. | — | workflow, testing, verification, makefile, railway |


## Infrastructure

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
| **canonical-targets** | Single source of truth for canonical VMs, canonical IDEs, and canonical trunk branch. Use this to keep dx-status, mcp-doctor, and setup scripts aligned across machines. | — | dx, ide, vm, canonical, targets |
| **devops-dx** | GitHub/Railway housekeeping for CI env/secret management and DX maintenance. Use when setting or auditing GitHub Actions variables/secrets, syncing Railway env → GitHub, or fixing CI failures due to missing env. | — | devops, github, auth, env, secrets, ci, railway |
| **dx-alerts** | Lightweight “news wire” for DX changes and breakages, posted to Slack (no MCP required). | — |  |
| **fleet-deploy** | Deploy changes across canonical VMs (macmini, homedesktop-wsl, epyc6, epyc12). MUST BE USED when deploying scripts, crontabs, or config changes to multiple VMs. Uses configs/fleet_hosts.yaml as authoritative source for SSH targets, with dx-runner governance. | `dx-runner start --provider opencode --beads bd-xyz --prompt-` | fleet, deploy, vm, canonical, dx-runner, ssh, infrastructure |
| **fleet-sync** | Canonical Fleet Sync skill for cross-VM tool convergence, client visibility testing, and runtime-truth documentation. Use when the work involves Fleet Sync architecture, canonical VM rollout, MCP tool restoration, or end-to-end validation across codex, claude, gemini, and opencode. | — | fleet, mcp, vm, ide, rollout, validation |
| **github-runner-setup** | GitHub Actions self-hosted runner setup and maintenance. Use when setting up dedicated runner users, migrating runners from personal accounts, troubleshooting runner issues, or implementing runner isolation. Covers systemd services, environment isolation, and skills plane integration. | — | github-actions, devops, runner, systemd, infrastructure |
| **vm-bootstrap** | Linux VM bootstrap verification skill. MUST BE USED when setting up new VMs or verifying environment. Supports modes: check (warn-only), install (operator-confirmed), strict (CI-ready). Enforces Linux-only + mise as canonical; honors preference brew→npm (with apt fallback). Verifies required tools: mise, node, pnpm, python, poetry, gh, railway, op, bd, dcg, ru, tmux, rg. Handles optional tools as warnings: tailscale, playwright, agent-browser, docker, bv. Never prints/seeds secrets; never stores tokens in repo/YAML; Railway vars only for app runtime env. Safe on dirty repos (refuses and points to dirty-repo-bootstrap skill, or snapshots WIP branch). Keywords: vm, bootstrap, setup, mise, toolchain, linux, environment, provision, verify, new vm | — | dx, tooling, setup, linux |
| **multi-agent-dispatch** | Cross-VM task dispatch with dx-runner as canonical governance runner and OpenCode as primary execution lane. dx-dispatch is a BREAK-GLASS compatibility shim for remote fanout when dx-runner is unavailable. EPYC6 is currently disabled - see enablement gate. | `dx-dispatch is a BREAK-GLASS compatibility shim for remote f` | workflow, dispatch, dx-runner, governance, cross-vm |


## Railway Deployment

| Skill | Description | Example | Tags |
|-------|-------------|---------|------|
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


---
**Discovery**: Skills auto-load from `~/agent-skills/{core,extended,health,infra,railway,dispatch}/*/SKILL.md`
**Details**: Each skill's SKILL.md contains full documentation
**Specification**: https://agentskills.io/specification
**Source**: Generated from agent-skills commit shown in header
