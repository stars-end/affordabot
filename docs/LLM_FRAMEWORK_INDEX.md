# LLM Framework Documentation - Master Index

**Version:** 1.0
**Date:** 2025-12-01
**Status:** Complete - Ready for Implementation

---

## 📖 Documentation Overview

This directory contains a comprehensive specification for implementing a shared LLM framework between `affordabot` and `prime-radiant-ai`. The documentation is designed to be implementable by a junior developer with clear, step-by-step instructions.

---

## 📚 Core Documents

### 1. [Implementation Summary](./LLM_FRAMEWORK_SUMMARY.md) ⭐ **START HERE**
**Purpose:** Quick start guide for junior developers

**Contents:**
- What you're building and why
- 4-week implementation roadmap
- Key design decisions explained
- Success criteria and metrics
- Common issues and solutions

**Read this first** to get oriented.

---

### 2. [Product Requirements Document (PRD)](./LLM_FRAMEWORK_PRD.md)
**Purpose:** Define what we're building

**Contents:**
- Functional requirements (FR-1 through FR-8)
- User stories for both projects
- Success metrics and KPIs
- Cost analysis and budget targets
- Non-functional requirements (performance, reliability)

**Use this to:** Understand the "what" and "why"

---

### 3. [Technical Specification](./LLM_FRAMEWORK_TECHNICAL_SPEC.md)
**Purpose:** Define how we're building it

**Contents:**
- Architecture diagrams
- Complete API reference with code examples
- Database schema with SQL migrations
- Testing strategy (unit, integration, manual)
- Implementation details for all classes

**Use this to:** Understand the "how" (architecture and code)

---

### 4. [Migration Plan](./LLM_FRAMEWORK_MIGRATION.md)
**Purpose:** Step-by-step migration instructions

**Contents:**
- Week-by-week timeline
- Affordabot migration steps (8 steps)
- Prime-Radiant-AI migration steps (5 steps)
- Database migration scripts
- Feature flag strategy
- Rollback procedures

**Use this to:** Execute the migration safely

---

### 5. [Original Research](./LLM_FRAMEWORK_PLAN.md)
**Purpose:** Background research and analysis

**Contents:**
- Framework comparison (LiteLLM vs LangChain vs Custom)
- z.ai integration analysis
- Cost-benefit analysis
- Initial recommendations

**Use this to:** Understand the research that led to these decisions

---

## 🗺️ Reading Path

### For Junior Developers (Implementing)
1. **Start:** [Implementation Summary](./LLM_FRAMEWORK_SUMMARY.md)
2. **Understand Requirements:** [PRD](./LLM_FRAMEWORK_PRD.md)
3. **Learn Architecture:** [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md)
4. **Execute Migration:** [Migration Plan](./LLM_FRAMEWORK_MIGRATION.md)

### For Stakeholders (Reviewing)
1. **Start:** [Implementation Summary](./LLM_FRAMEWORK_SUMMARY.md)
2. **Review Requirements:** [PRD](./LLM_FRAMEWORK_PRD.md)
3. **Approve Architecture:** [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md) (high-level sections)

### For Technical Leads (Deep Dive)
1. **Review All Documents** in order
2. **Focus on:** Technical Spec (API design, database schema)
3. **Validate:** Migration Plan (rollback procedures, testing)

---

## 📦 What's Being Built

### Shared Package: `llm-common`
A lightweight library (~300 lines) providing:
- **Multi-Provider LLM Client** (LiteLLM wrapper)
- **Web Search with Caching** (z.ai + Postgres)
- **Cost Tracking** (budget enforcement)
- **Structured Outputs** (Pydantic models)

### Affordabot Integration
- **AnalysisPipeline** (~200 lines): Research → Generate → Review → Refine
- **LegislationSearchService**: Domain-specific search queries
- **Model Comparison Dashboard**: Track performance by model

### Prime-Radiant-AI Integration
- **ConversationMemory** (~100 lines): Persist chat history
- **FinanceSearchService**: Tax rules, retirement accounts, fund prospectuses
- **Context Injection**: Page-specific context (portfolio, tax planning)

---

## 🎯 Key Metrics

### Code Reduction
- **Before:** 1,250 lines (custom implementations)
- **After:** 600 lines (shared + domain-specific)
- **Savings:** 52% reduction

### Cost Savings
- **Before:** $600/month (no caching)
- **After:** $240/month (80% cache hit rate)
- **Savings:** $360/month (60% reduction)

### Performance Targets
- **Pipeline Latency:** P95 < 10s
- **Cache Hit Rate:** ≥ 80%
- **Error Rate:** < 1%
- **Test Coverage:** ≥ 80%

---

## 🚀 Implementation Timeline

| Week | Focus | Deliverables |
|------|-------|--------------|
| **1** | `llm-common` package | LLMClient, WebSearchClient, CostTracker, Tests |
| **2** | Affordabot migration | AnalysisPipeline, Feature flag, Integration tests |
| **3** | Prime-Radiant-AI migration | ConversationMemory, Finance search, Integration tests |
| **4** | Cleanup & optimization | Remove old code, Documentation, Model experiments |

---

## 🔧 Technology Stack

| Component | Technology | Justification |
|-----------|-----------|---------------|
| LLM Client | **LiteLLM** | Multi-provider, battle-tested, 3M+ downloads/month |
| Structured Outputs | **instructor** | Type-safe Pydantic models, 11k+ stars |
| Web Search | **z.ai API** | Intelligent search, legislation-optimized |
| Caching | **Postgres + In-Memory** | 2-tier caching, 80% hit rate |
| Database | **Postgres (PostgreSQL)** | Already in use, supports JSONB |
| Package Management | **Git Submodule** | Solo dev, no CI/CD overhead |

---

## 📊 Database Schema

### New Tables (5 total)

**Shared:**
1. `web_search_cache` - Persistent cache (24hr TTL)
2. `cost_tracking` - LLM and search costs

**Affordabot:**
3. `pipeline_runs` - Track analysis runs for model comparison
4. `pipeline_steps` - Log individual steps (debugging)

**Prime-Radiant-AI:**
5. `conversations` - Conversation history (90-day TTL)

---

## 🧪 Testing Strategy

### Unit Tests (80% coverage)
- `llm-common`: All core classes
- Mock external APIs (OpenRouter, z.ai)

### Integration Tests
- Full pipeline (affordabot)
- Conversation memory (prime-radiant-ai)
- Cache hit rate validation

### Manual Tests
- Model comparison (3+ models)
- Cost tracking (verify budgets)
- UI testing (admin dashboard, chat)

---

## 🎓 Learning Objectives

By implementing this, you will learn:

1. **Multi-Provider LLM Integration**
   - LiteLLM for provider abstraction
   - Fallback chains and retry logic
   - Cost tracking and budgets

2. **Caching Strategies**
   - 2-tier caching (memory + database)
   - Cache invalidation and TTLs
   - Cost optimization

3. **Workflow Orchestration**
   - Sequential pipelines
   - Conditional branching
   - State management

4. **Structured Outputs**
   - `instructor` for type-safe responses
   - Pydantic model validation
   - Error handling

5. **Database Design**
   - Schema design for LLM tracking
   - JSONB for flexible storage
   - Performance optimization

---

## ✅ Success Criteria

Implementation is complete when:

1. ✅ All tests pass (unit + integration)
2. ✅ Both projects use `llm-common`
3. ✅ Cache hit rate ≥ 80%
4. ✅ Cost < $300/month
5. ✅ Pipeline latency P95 < 10s
6. ✅ Old code removed
7. ✅ Documentation updated

---

## 🚨 Risk Mitigation

### Migration Risks
- **Production Breakage:** Feature flags + gradual rollout (10% → 50% → 100%)
- **Performance Degradation:** Benchmarking before/after, rollback plan
- **Cost Overruns:** Budget limits, daily/monthly alerts
- **Cache Misses:** Monitor hit rate, tune TTLs

### Rollback Plan
- Disable feature flag
- Revert code (git revert)
- Drop new tables (if needed)

---

## 📞 Getting Started

### Step 1: Read the Summary
Start with [Implementation Summary](./LLM_FRAMEWORK_SUMMARY.md) to get oriented.

### Step 2: Review Requirements
Read [PRD](./LLM_FRAMEWORK_PRD.md) to understand what you're building.

### Step 3: Study Architecture
Read [Technical Spec](./LLM_FRAMEWORK_TECHNICAL_SPEC.md) to understand how it works.

### Step 4: Execute Migration
Follow [Migration Plan](./LLM_FRAMEWORK_MIGRATION.md) step-by-step.

---

## 🤝 Support

### Questions?
1. Check the relevant document (see Reading Path above)
2. Read code examples in `llm-common/examples/`
3. Run tests to see how things work
4. Ask specific questions with document references

### Common Issues
- **Import errors:** Install submodule (`pip install -e packages/llm-common`)
- **API key errors:** Set environment variables (see Migration Plan)
- **Cache not working:** Check Postgres connection, verify schema
- **Tests failing:** Check mock setup, verify API keys

---

## 📈 Next Steps

1. ✅ **Review this index** to understand the documentation structure
2. ✅ **Read the Summary** to get oriented
3. ✅ **Review the PRD** with stakeholders
4. ✅ **Approve the Technical Spec** (architecture, database schema)
5. ✅ **Begin Week 1** (create `llm-common` package)

---

## 📝 Document Status

| Document | Status | Last Updated |
|----------|--------|--------------|
| Master Index | ✅ Complete | 2025-12-01 |
| Implementation Summary | ✅ Complete | 2025-12-01 |
| PRD | ✅ Complete | 2025-12-01 |
| Technical Spec | ✅ Complete | 2025-12-01 |
| Migration Plan | ✅ Complete | 2025-12-01 |
| Original Research | ✅ Complete | 2025-11-30 |

---

## 🎉 Ready to Begin!

All documentation is complete and ready for implementation. Start with the [Implementation Summary](./LLM_FRAMEWORK_SUMMARY.md) and follow the 4-week roadmap.

**Good luck! 🚀**
