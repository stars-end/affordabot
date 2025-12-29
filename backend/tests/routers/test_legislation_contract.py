import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))
import pytest
from httpx import AsyncClient
from fastapi.testclient import TestClient
from backend.main import app

@pytest.mark.asyncio
async def test_get_legislation_contract():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/legislation/san-jose")
    assert response.status_code == 200
    data = response.json()
    assert "jurisdiction" in data
    assert "count" in data
    assert "legislation" in data
    if data["count"] > 0:
        legislation = data["legislation"][0]
        assert "bill_number" in legislation
        assert "title" in legislation
        assert "jurisdiction" in legislation
        assert "status" in legislation
        assert "impacts" in legislation
        assert "total_impact_p50" in legislation
        assert "analysis_timestamp" in legislation
        assert "model_used" in legislation
        if legislation["impacts"]:
            impact = legislation["impacts"][0]
            assert "confidence" in impact
            assert "confidence_score" not in impact
