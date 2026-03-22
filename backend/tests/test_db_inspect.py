import pytest

import scripts.db_inspect as mod
from scripts.db_inspect import (
    ensure_read_only_sql,
    normalize_host_for_host_side_execution,
    parse_args,
    resolve_database_url,
    to_async_database_url,
)


def test_allows_select_queries() -> None:
    assert ensure_read_only_sql("SELECT * FROM users;") == "SELECT * FROM users"


def test_allows_with_queries() -> None:
    assert (
        ensure_read_only_sql("WITH x AS (SELECT 1) SELECT * FROM x")
        == "WITH x AS (SELECT 1) SELECT * FROM x"
    )


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM users",
        "UPDATE users SET email = 'x'",
        "INSERT INTO users(id) VALUES (1)",
        "ALTER TABLE users ADD COLUMN nope int",
    ],
)
def test_blocks_mutating_queries(sql: str) -> None:
    with pytest.raises(ValueError):
        ensure_read_only_sql(sql)


def test_resolve_database_url_prefers_pg_env_and_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PGHOST", "postgres.railway.internal")
    monkeypatch.setenv("PGPORT", "5432")
    monkeypatch.setenv("PGUSER", "postgres")
    monkeypatch.setenv("PGPASSWORD", "secret")
    monkeypatch.setenv("PGDATABASE", "railway")
    monkeypatch.setenv("RAILWAY_TCP_PROXY_DOMAIN", "maglev.proxy.rlwy.net")
    monkeypatch.setenv("RAILWAY_TCP_PROXY_PORT", "11747")

    assert (
        resolve_database_url("primary")
        == "postgresql://postgres:secret@maglev.proxy.rlwy.net:11747/railway"
    )


def test_resolve_database_url_falls_back_to_public_url_when_internal_host_has_no_proxy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PGHOST", "postgres.railway.internal")
    monkeypatch.setenv("PGPORT", "5432")
    monkeypatch.setenv("PGUSER", "postgres")
    monkeypatch.setenv("PGPASSWORD", "secret")
    monkeypatch.setenv("PGDATABASE", "railway")
    monkeypatch.delenv("RAILWAY_TCP_PROXY_DOMAIN", raising=False)
    monkeypatch.delenv("RAILWAY_TCP_PROXY_PORT", raising=False)
    monkeypatch.setenv(
        "DATABASE_URL_PUBLIC",
        "postgresql://public-user:public-secret@public.proxy.rlwy.net:15432/railway",
    )

    assert (
        resolve_database_url("primary")
        == "postgresql://public-user:public-secret@public.proxy.rlwy.net:15432/railway"
    )


def test_normalize_host_for_host_side_execution_rewrites_internal_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("RAILWAY_TCP_PROXY_DOMAIN", "maglev.proxy.rlwy.net")
    monkeypatch.setenv("RAILWAY_TCP_PROXY_PORT", "11747")

    assert (
        normalize_host_for_host_side_execution(
            "postgresql://postgres:secret@postgres.railway.internal:5432/railway"
        )
        == "postgresql://postgres:secret@maglev.proxy.rlwy.net:11747/railway"
    )


def test_async_database_url_uses_asyncpg_scheme() -> None:
    assert to_async_database_url("postgres://host/db") == "postgresql+asyncpg://host/db"
    assert (
        to_async_database_url("postgresql://host/db") == "postgresql+asyncpg://host/db"
    )


def test_parse_args_supports_affordabot_commands() -> None:
    args = parse_args(["tables"])
    assert args.command == "tables"
    assert args.schema == "public"

    args = parse_args(["describe", "legislation"])
    assert args.command == "describe"
    assert args.table == "legislation"

    args = parse_args(["jurisdiction-summary", "--limit", "5"])
    assert args.command == "jurisdiction-summary"
    assert args.limit == 5

    args = parse_args(["pipeline-runs", "--limit", "8"])
    assert args.command == "pipeline-runs"
    assert args.limit == 8

    args = parse_args(["raw-scrapes", "--hours", "48", "--limit", "12"])
    assert args.command == "raw-scrapes"
    assert args.hours == 48
    assert args.limit == 12


@pytest.mark.asyncio
async def test_jurisdiction_summary_uses_expected_projection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_query(target: str, sql: str) -> dict:
        assert target == "primary"
        assert "FROM jurisdictions j" in sql
        assert "s.jurisdiction_id::text = j.id::text" in sql
        assert "::uuid" not in sql
        return {
            "database": "primary",
            "row_count": 1,
            "rows": [
                {
                    "name": "San Jose",
                    "source_count": 3,
                    "raw_scrape_count": 120,
                }
            ],
        }

    monkeypatch.setattr(mod, "run_query", fake_run_query)
    result = await mod.jurisdiction_summary("primary", 10)

    assert result["row_count"] == 1
    assert result["rows"][0]["name"] == "San Jose"


@pytest.mark.asyncio
async def test_raw_scrapes_recent_avoids_uuid_cast_on_source_jurisdiction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_query(target: str, sql: str) -> dict:
        assert target == "primary"
        assert "FROM raw_scrapes rs" in sql
        assert "s.jurisdiction_id::text = j.id::text" in sql
        assert "::uuid" not in sql
        return {"database": "primary", "row_count": 0, "rows": []}

    monkeypatch.setattr(mod, "run_query", fake_run_query)
    result = await mod.raw_scrapes_recent("primary", 24, 25)
    assert result["row_count"] == 0


@pytest.mark.asyncio
async def test_pipeline_runs_orders_without_created_at(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_query(target: str, sql: str) -> dict:
        assert target == "primary"
        assert "FROM pipeline_runs" in sql
        assert "ORDER BY started_at DESC NULLS LAST, id DESC" in sql
        assert "created_at" not in sql
        return {"database": "primary", "row_count": 0, "rows": []}

    monkeypatch.setattr(mod, "run_query", fake_run_query)
    result = await mod.pipeline_runs("primary", 25)
    assert result["row_count"] == 0


@pytest.mark.asyncio
async def test_pipeline_runs_includes_trigger_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_query(target: str, sql: str) -> dict:
        assert "trigger_source" in sql
        return {"database": "primary", "row_count": 0, "rows": []}

    monkeypatch.setattr(mod, "run_query", fake_run_query)
    await mod.pipeline_runs("primary", 5)
