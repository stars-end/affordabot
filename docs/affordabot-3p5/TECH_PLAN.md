# TECH_PLAN: Job Scheduling Strategy (Prefect vs Cron)

**Epic**: affordabot-3p5  
**Priority**: P2  
**Status**: Planning

## Goal

Inventory Affordabot's scheduled workflows, evaluate Prefect vs cron/Railway for each category, and recommend a maintainable scheduling strategy with a small pilot migration.

## Background

Affordabot likely has several scheduled tasks:
- Periodic scraping of jurisdictions
- Scheduled analysis runs
- Data cleanup/maintenance
- Health checks

Current state unknown - need to inventory existing scheduling mechanisms.

## Research Phase

### Inventory Current Scheduling
- [ ] Find all cron jobs (if any)
- [ ] Check Railway scheduled tasks
- [ ] Identify ad-hoc scheduling code
- [ ] Document frequency and dependencies

### Evaluate Options

**Cron/Railway**:
- ✅ Simple, built-in
- ✅ No additional dependencies
- ❌ Limited observability
- ❌ No retry logic
- ❌ Hard to test locally

**Prefect**:
- ✅ Rich observability
- ✅ Built-in retries and error handling
- ✅ DAG visualization
- ✅ Easy local testing
- ❌ Additional infrastructure
- ❌ Learning curve

## Implementation Phases

### Phase 1: Inventory & Analysis
- [ ] Document all scheduled tasks
- [ ] Categorize by complexity:
  - Simple (single function, no dependencies)
  - Medium (multi-step, some dependencies)
  - Complex (DAG, many dependencies)
- [ ] Estimate effort for each option

### Phase 2: Recommendation
- [ ] Create decision matrix
- [ ] Recommend strategy per category:
  - Simple → cron/Railway
  - Medium/Complex → Prefect
- [ ] Document tradeoffs

### Phase 3: Pilot Migration
- [ ] Choose 1-2 medium-complexity tasks
- [ ] Implement with Prefect
- [ ] Deploy and monitor
- [ ] Document learnings

## Example Workflows

**Jurisdiction Scraping** (Medium complexity):
```python
# Prefect flow
@flow
def scrape_all_jurisdictions():
    jurisdictions = get_active_jurisdictions()
    for jur in jurisdictions:
        scrape_jurisdiction.submit(jur)  # Parallel tasks

@task(retries=3, retry_delay_seconds=60)
def scrape_jurisdiction(jur):
    # Scraping logic
    pass
```

**Daily Health Check** (Simple):
```bash
# Cron
0 8 * * * curl https://affordabot.com/api/health
```

## Infrastructure Needs

If choosing Prefect:
- [ ] Prefect server (self-hosted or cloud)
- [ ] Worker deployment
- [ ] Monitoring/alerting integration

## Verification

- [ ] All scheduled tasks inventoried
- [ ] Evaluation complete
- [ ] Recommendation documented
- [ ] Pilot migration successful
- [ ] Team aligned on strategy

## Risks

- **Migration effort**: Moving to Prefect may be significant
- **Infrastructure**: Prefect adds operational complexity
- **Learning curve**: Team needs to learn Prefect

## Success Criteria

- ✅ Complete inventory of scheduled tasks
- ✅ Clear recommendation per task category
- ✅ Pilot migration proves viability
- ✅ Documentation for future scheduling decisions
