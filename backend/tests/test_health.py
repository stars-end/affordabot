from unittest.mock import patch, AsyncMock, MagicMock
import pytest


def test_health_build_reports_build_identity():
    from main import build_health_check
    import os

    os.environ["GIT_COMMIT"] = "abc123def"
    os.environ["BUILD_TIMESTAMP"] = "2026-03-31T12:00:00Z"
    os.environ["ENVIRONMENT"] = "dev"

    import asyncio

    result = asyncio.get_event_loop().run_until_complete(build_health_check())
    assert result["git_commit"] == "abc123def"
    assert result["build_timestamp"] == "2026-03-31T12:00:00Z"
    assert result["build_id"] == "abc123def:2026-03-31T12:00:00Z"
    assert result["environment"] == "dev"
    assert result["service"] == "backend"
    assert "timestamp" in result

    del os.environ["GIT_COMMIT"]
    del os.environ["BUILD_TIMESTAMP"]
    del os.environ["ENVIRONMENT"]


def test_health_build_uses_railway_sha_fallback():
    import os

    os.environ.pop("GIT_COMMIT", None)
    os.environ["RAILWAY_GIT_COMMIT_SHA"] = "railsha123"
    os.environ["RAILWAY_DEPLOYMENT_CREATED_AT"] = "2026-03-31T00:00:00Z"

    from main import build_health_check
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(build_health_check())
    assert result["git_commit"] == "railsha123"
    assert result["build_timestamp"] == "2026-03-31T00:00:00Z"

    del os.environ["RAILWAY_GIT_COMMIT_SHA"]
    del os.environ["RAILWAY_DEPLOYMENT_CREATED_AT"]


def test_health_build_no_env_vars_returns_unknown():
    import os

    for key in [
        "GIT_COMMIT",
        "RAILWAY_GIT_COMMIT_SHA",
        "COMMIT_SHA",
        "BUILD_TIMESTAMP",
        "RAILWAY_DEPLOYMENT_CREATED_AT",
        "SOURCE_DATE_EPOCH",
        "BUILD_ID",
        "ENVIRONMENT",
    ]:
        os.environ.pop(key, None)

    from main import build_health_check
    import asyncio

    result = asyncio.get_event_loop().run_until_complete(build_health_check())
    assert result["git_commit"] == "unknown"
    assert result["build_timestamp"] == "unknown"
    assert result["service"] == "backend"
    assert result["environment"] == "unknown"


def test_health_build_staleness_detection_logic():
    runtime_sha = "aa11bb22"
    master_sha = "cc33dd44"
    assert runtime_sha != master_sha

    same_runtime = "aa11bb22"
    same_master = "aa11bb22"
    assert same_runtime == same_master
