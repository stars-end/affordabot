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

# Test 3: Get Review Prompt
echo -e "\n3. GET /admin/prompts/review"
curl -s -X GET "$BASE_URL/prompts/review" | jq '.'

# Test 4: Get Scrape History
echo -e "\n4. GET /admin/scrapes"
curl -s -X GET "$BASE_URL/scrapes?limit=5" | jq '.'

# Test 5: Get Analysis History
echo -e "\n5. GET /admin/analyses"
curl -s -X GET "$BASE_URL/analyses?limit=5" | jq '.'

# Test 6: Health Check
echo -e "\n6. GET /admin/health/detailed"
curl -s -X GET "$BASE_URL/health/detailed" | jq '.'

# Test 7: Trigger Manual Scrape
echo -e "\n7. POST /admin/scrape (san_jose)"
curl -s -X POST "$BASE_URL/scrape" \
  -H "Content-Type: application/json" \
  -d '{"jurisdiction": "san_jose", "force": false}' | jq '.'

echo -e "\n========================================"
echo "Tests complete!"
