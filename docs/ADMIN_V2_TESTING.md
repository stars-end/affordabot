# Admin Dashboard V2 - Endpoint Testing Guide

**Last Updated**: 2025-11-30 07:18 PST  
**Status**: Testing Phase

## Prerequisites

### Environment Variables
Ensure these are set in your environment:
```bash
export SUPABASE_URL="https://jqcnqlgbbcfwfpmvzbqi.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="<your-service-role-key>"
```

### Start Backend Server
```bash
cd backend
uvicorn main:app --reload --port 8000
```

## Endpoint Tests

### 1. Model Management

#### Get Model Configs
```bash
curl -X GET "http://localhost:8000/admin/models" \
  -H "Content-Type: application/json" | jq
```

**Expected Response**:
```json
[
  {
    "provider": "openrouter",
    "model_name": "x-ai/grok-beta",
    "priority": 1,
    "enabled": true,
    "use_case": "generation"
  },
  {
    "provider": "zai",
    "model_name": "glm-4.6",
    "priority": 1,
    "enabled": true,
    "use_case": "review"
  }
]
```

#### Update Model Configs
```bash
curl -X POST "http://localhost:8000/admin/models" \
  -H "Content-Type: application/json" \
  -d '{
    "models": [
      {
        "provider": "openrouter",
        "model_name": "x-ai/grok-beta",
        "priority": 1,
        "enabled": true,
        "use_case": "generation"
      },
      {
        "provider": "zai",
        "model_name": "glm-4.6",
        "priority": 2,
        "enabled": true,
        "use_case": "review"
      }
    ]
  }' | jq
```

**Expected Response**:
```json
{
  "message": "Model configuration updated",
  "count": 2
}
```

### 2. Prompt Management

#### Get Active Generation Prompt
```bash
curl -X GET "http://localhost:8000/admin/prompts/generation" \
  -H "Content-Type: application/json" | jq
```

**Expected Response**:
```json
{
  "prompt_type": "generation",
  "system_prompt": "You are an expert policy analyst...",
  "updated_at": "2025-11-30T07:00:00Z",
  "updated_by": "admin"
}
```

#### Update Prompt (Creates New Version)
```bash
curl -X POST "http://localhost:8000/admin/prompts" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_type": "generation",
    "system_prompt": "You are an expert policy analyst specializing in local government legislation. Analyze bills with precision and cite specific sections."
  }' | jq
```

**Expected Response**:
```json
{
  "message": "Prompt updated for generation",
  "version": 2,
  "updated_at": "2025-11-30T07:18:00Z"
}
```

### 3. Scraping Operations

#### Trigger Manual Scrape
```bash
curl -X POST "http://localhost:8000/admin/scrape" \
  -H "Content-Type: application/json" \
  -d '{
    "jurisdiction": "san_jose",
    "force": false
  }' | jq
```

**Expected Response**:
```json
{
  "task_id": "550e8400-e29b-41d4-a716-446655440000",
  "jurisdiction": "san_jose",
  "status": "started",
  "message": "Scraping task started for san_jose"
}
```

#### Get Scrape History
```bash
# All scrapes
curl -X GET "http://localhost:8000/admin/scrapes?limit=10" \
  -H "Content-Type: application/json" | jq

# Filter by jurisdiction
curl -X GET "http://localhost:8000/admin/scrapes?jurisdiction=san_jose&limit=5" \
  -H "Content-Type: application/json" | jq
```

**Expected Response**:
```json
[
  {
    "id": "uuid-here",
    "jurisdiction": "san_jose",
    "timestamp": "2025-11-30T07:15:00Z",
    "bills_found": 0,
    "status": "success",
    "error": null
  }
]
```

### 4. Analysis Pipeline

#### Trigger Analysis Step
```bash
curl -X POST "http://localhost:8000/admin/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "jurisdiction": "san_jose",
    "bill_id": "SB-123",
    "step": "research",
    "model_override": null
  }' | jq
```

**Expected Response**:
```json
{
  "task_id": "uuid-here",
  "step": "research",
  "status": "started",
  "result": null,
  "error": null
}
```

#### Get Analysis History
```bash
# All analyses
curl -X GET "http://localhost:8000/admin/analyses?limit=10" \
  -H "Content-Type: application/json" | jq

# Filter by jurisdiction and step
curl -X GET "http://localhost:8000/admin/analyses?jurisdiction=san_jose&step=research" \
  -H "Content-Type: application/json" | jq

# Filter by bill
curl -X GET "http://localhost:8000/admin/analyses?bill_id=SB-123" \
  -H "Content-Type: application/json" | jq
```

**Expected Response**:
```json
[
  {
    "id": "uuid-here",
    "jurisdiction": "san_jose",
    "bill_id": "SB-123",
    "step": "research",
    "model_used": "zai/glm-4.6",
    "timestamp": "2025-11-30T07:16:00Z",
    "status": "success",
    "result": {...},
    "error": null
  }
]
```

### 5. Health Monitoring

#### Get Detailed Health Status
```bash
curl -X GET "http://localhost:8000/admin/health/detailed" \
  -H "Content-Type: application/json" | jq
```

**Expected Response**:
```json
{
  "research": {
    "status": "healthy",
    "latency_ms": 150
  },
  "analysis": {
    "status": "healthy",
    "models_available": 2
  },
  "database": {
    "status": "healthy"
  },
  "scrapers": {
    "san_jose": {
      "status": "healthy",
      "last_scrape": null
    }
  }
}
```

## Test Results

### Test Execution Log

**Date**: 2025-11-30  
**Tester**: Automated Testing

| Endpoint | Method | Status | Response Time | Notes |
|----------|--------|--------|---------------|-------|
| `/admin/models` | GET | ⏳ | - | Pending |
| `/admin/models` | POST | ⏳ | - | Pending |
| `/admin/prompts/{type}` | GET | ⏳ | - | Pending |
| `/admin/prompts` | POST | ⏳ | - | Pending |
| `/admin/scrape` | POST | ⏳ | - | Pending |
| `/admin/scrapes` | GET | ⏳ | - | Pending |
| `/admin/analyze` | POST | ⏳ | - | Pending |
| `/admin/analyses` | GET | ⏳ | - | Pending |
| `/admin/health/detailed` | GET | ⏳ | - | Pending |

### Known Issues

1. **Background Tasks**: Currently simulate operations (TODO: integrate actual scrapers)
2. **Authentication**: No auth checks yet (RLS policies are placeholder)
3. **Rate Limiting**: Not implemented for admin endpoints

### Next Steps

1. ✅ Document test procedures
2. ⏳ Execute tests and record results
3. ⏳ Fix any issues found
4. ⏳ Build frontend UI
5. ⏳ End-to-end testing

## Automated Testing Script

Create `backend/test_admin_endpoints.sh`:

```bash
#!/bin/bash

BASE_URL="http://localhost:8000/admin"

echo "Testing Admin Dashboard V2 Endpoints..."
echo "========================================"

# Test 1: Get Models
echo -e "\n1. GET /admin/models"
curl -s -X GET "$BASE_URL/models" | jq '.'

# Test 2: Get Generation Prompt
echo -e "\n2. GET /admin/prompts/generation"
curl -s -X GET "$BASE_URL/prompts/generation" | jq '.'

# Test 3: Get Scrape History
echo -e "\n3. GET /admin/scrapes"
curl -s -X GET "$BASE_URL/scrapes?limit=5" | jq '.'

# Test 4: Get Analysis History
echo -e "\n4. GET /admin/analyses"
curl -s -X GET "$BASE_URL/analyses?limit=5" | jq '.'

# Test 5: Health Check
echo -e "\n5. GET /admin/health/detailed"
curl -s -X GET "$BASE_URL/health/detailed" | jq '.'

echo -e "\n========================================"
echo "Tests complete!"
```

Run with:
```bash
chmod +x backend/test_admin_endpoints.sh
./backend/test_admin_endpoints.sh
```
