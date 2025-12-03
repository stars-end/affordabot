# TECH_PLAN: Affordabot Scraping Scalability & RAG-Ready Ingestion

**Epic**: affordabot-i0x  
**Priority**: P2  
**Status**: Planning

## Goal

Study and harden Affordabot's web scraping and ingestion for 100+ jurisdictions, incorporate patterns from City Bureau's city-scrapers project, and ensure all scraped artifacts are RAG-ready (chunked + embedded) for future LLM/RAG use.

## Background

Affordabot currently has basic scrapers for a few jurisdictions (San Jose, California State, Santa Clara County, Saratoga). To scale to 100+ jurisdictions, we need:
1. Standardized scraper architecture
2. Patterns from proven projects (city-scrapers)
3. RAG-ready data pipeline (chunking, embedding)

## Research Phase

### Study city-scrapers
- [ ] Clone and review [City Bureau/city-scrapers](https://github.com/City-Bureau/city-scrapers)
- [ ] Document their scraper patterns
- [ ] Identify reusable abstractions
- [ ] Note testing strategies

### Current State Analysis
- [ ] Audit existing scrapers (`backend/services/scraper/`)
- [ ] Document current architecture
- [ ] Identify pain points and inconsistencies
- [ ] List jurisdictions to support

## Implementation Phases

### Phase 1: Standardize Scraper Architecture
- [ ] Define `BaseScraper` interface (already exists, may need enhancement)
- [ ] Create scraper factory/registry
- [ ] Standardize error handling
- [ ] Add health checks for all scrapers
- [ ] Implement retry logic

### Phase 2: RAG-Ready Ingestion Pipeline
- [ ] Design chunking strategy for legislation text
- [ ] Add embedding generation (via llm-common)
- [ ] Create vector storage schema in Supabase
- [ ] Implement ingestion pipeline:
  - Scrape → Parse → Chunk → Embed → Store

### Phase 3: Scalability Improvements
- [ ] Add rate limiting
- [ ] Implement caching layer
- [ ] Add monitoring/observability
- [ ] Create scraper health dashboard

## Database Schema Changes

**New tables needed**:
```sql
-- Chunked legislation for RAG
CREATE TABLE legislation_chunks (
  id UUID PRIMARY KEY,
  legislation_id UUID REFERENCES legislation(id),
  chunk_index INT,
  chunk_text TEXT,
  embedding VECTOR(1536),  -- OpenAI ada-002 dimension
  metadata JSONB
);

-- Scraper health tracking
CREATE TABLE scraper_health (
  id UUID PRIMARY KEY,
  jurisdiction_id UUID REFERENCES jurisdictions(id),
  last_success_at TIMESTAMPTZ,
  last_failure_at TIMESTAMPTZ,
  error_message TEXT,
  success_rate FLOAT
);
```

## Verification

- [ ] All existing scrapers migrated to new architecture
- [ ] city-scrapers patterns documented
- [ ] RAG pipeline produces valid embeddings
- [ ] Health monitoring dashboard functional
- [ ] Performance benchmarks met (e.g., 100 jurisdictions in <1hr)

## Risks

- **Schema changes**: Need careful migration planning
- **Embedding costs**: OpenAI API costs for 100+ jurisdictions
- **Rate limits**: External sites may block aggressive scraping

## Success Criteria

- ✅ Standardized scraper architecture
- ✅ city-scrapers patterns integrated
- ✅ RAG-ready data pipeline operational
- ✅ 10+ jurisdictions scraped and embedded
- ✅ Health monitoring in place
