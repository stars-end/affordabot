#!/usr/bin/env python3
"""Read-only database inspection helper for Affordabot."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from collections.abc import Sequence
from typing import Any
from urllib.parse import quote, urlparse, urlunparse


READ_ONLY_PREFIXES = ("select", "with", "show")
FORBIDDEN_SQL_TOKENS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "create",
    "grant",
    "revoke",
    "copy",
    "vacuum",
    "analyze",
    "comment",
)


def resolve_database_url(target: str) -> str:
    if target not in {"primary", "default"}:
        raise ValueError(f"Unsupported database target: {target}")

    pg_host = os.getenv("PGHOST")
    pg_port = os.getenv("PGPORT")
    pg_user = os.getenv("PGUSER")
    pg_password = os.getenv("PGPASSWORD")
    pg_database = os.getenv("PGDATABASE")
    if pg_host and pg_port and pg_user and pg_password and pg_database:
        proxy_domain = os.getenv("RAILWAY_TCP_PROXY_DOMAIN")
        proxy_port = os.getenv("RAILWAY_TCP_PROXY_PORT")
        if pg_host.endswith(".railway.internal") and proxy_domain and proxy_port:
            pg_host = proxy_domain
            pg_port = proxy_port
        return (
            f"postgresql://{quote(pg_user)}:{quote(pg_password)}@{pg_host}:{pg_port}/{pg_database}"
        )

    url = (
        os.getenv("DATABASE_URL")
        or os.getenv("DATABASE_URL_PUBLIC")
        or os.getenv("RAILWAY_DATABASE_URL")
    )
    if not url:
        raise RuntimeError("DATABASE_URL is not configured for Affordabot DB access")
    return url


def normalize_host_for_host_side_execution(url: str) -> str:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    proxy_domain = os.getenv("RAILWAY_TCP_PROXY_DOMAIN")
    proxy_port = os.getenv("RAILWAY_TCP_PROXY_PORT")
    if not hostname.endswith(".railway.internal") or not proxy_domain or not proxy_port:
        return url

    username = quote(parsed.username or "")
    password = quote(parsed.password or "")
    auth = username
    if parsed.password is not None:
        auth += f":{password}"
    if auth:
        auth += "@"

    rewritten = parsed._replace(netloc=f"{auth}{proxy_domain}:{proxy_port}")
    return urlunparse(rewritten)


def to_async_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def ensure_read_only_sql(sql: str) -> str:
    normalized = sql.strip().rstrip(";")
    if not normalized:
        raise ValueError("Query is empty")

    lowered = normalized.lower()
    if not lowered.startswith(READ_ONLY_PREFIXES):
        raise ValueError("Only read-only SELECT/WITH/SHOW queries are allowed")

    for token in FORBIDDEN_SQL_TOKENS:
        if re.search(rf"\b{re.escape(token)}\b", lowered):
            raise ValueError(f"Forbidden SQL token in read-only mode: {token}")

    return normalized


def _quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _positive_int(value: int) -> int:
    if value <= 0:
        raise ValueError("limit must be > 0")
    return value


def make_engine(target: str) -> tuple[str, Any]:
    from sqlalchemy.ext.asyncio import create_async_engine

    database_url = normalize_host_for_host_side_execution(resolve_database_url(target))
    return database_url, create_async_engine(
        to_async_database_url(database_url), echo=False, future=True
    )


async def run_query(target: str, sql: str) -> dict[str, Any]:
    from sqlalchemy import text

    query = ensure_read_only_sql(sql)
    database_url, engine = make_engine(target)
    parsed = urlparse(database_url)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = [dict(row) for row in result.mappings().all()]
            return {
                "database": target,
                "database_host": parsed.hostname,
                "row_count": len(rows),
                "rows": rows,
            }
    finally:
        await engine.dispose()


async def inspect_tables(target: str, schema: str) -> dict[str, Any]:
    return await run_query(
        target,
        """
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = """
        + _quote_literal(schema)
        + """
        ORDER BY table_name
        """,
    )


async def describe_table(target: str, table: str, schema: str) -> dict[str, Any]:
    return await run_query(
        target,
        """
        SELECT
          column_name,
          data_type,
          is_nullable,
          column_default
        FROM information_schema.columns
        WHERE table_schema = """
        + _quote_literal(schema)
        + """
          AND table_name = """
        + _quote_literal(table)
        + """
        ORDER BY ordinal_position
        """,
    )


async def jurisdiction_summary(target: str, limit: int) -> dict[str, Any]:
    limit = _positive_int(limit)
    return await run_query(
        target,
        """
        SELECT
          j.id,
          j.name,
          j.type,
          COUNT(DISTINCT s.id) AS source_count,
          COUNT(rs.id) AS raw_scrape_count,
          MAX(rs.created_at) AS last_scrape_at
        FROM jurisdictions j
        LEFT JOIN sources s ON s.jurisdiction_id::uuid = j.id
        LEFT JOIN raw_scrapes rs ON rs.source_id = s.id
        GROUP BY j.id, j.name, j.type
        ORDER BY j.name
        LIMIT """
        + str(limit),
    )


async def pipeline_runs(target: str, limit: int) -> dict[str, Any]:
    limit = _positive_int(limit)
    return await run_query(
        target,
        """
        SELECT
          id,
          bill_id,
          jurisdiction,
          status,
          started_at,
          completed_at
        FROM pipeline_runs
        ORDER BY started_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT """
        + str(limit),
    )


async def raw_scrapes_recent(target: str, hours: int, limit: int) -> dict[str, Any]:
    hours = _positive_int(hours)
    limit = _positive_int(limit)
    return await run_query(
        target,
        """
        SELECT
          rs.id,
          rs.created_at,
          rs.processed,
          rs.error_message,
          s.name AS source_name,
          j.name AS jurisdiction_name
        FROM raw_scrapes rs
        LEFT JOIN sources s ON rs.source_id = s.id
        LEFT JOIN jurisdictions j ON s.jurisdiction_id::uuid = j.id
        WHERE rs.created_at >= NOW() - INTERVAL """
        + _quote_literal(f"{hours} hours")
        + """
        ORDER BY rs.created_at DESC
        LIMIT """
        + str(limit),
    )


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default="primary",
        choices=["primary", "default"],
        help="Database target (default: primary)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    tables = subparsers.add_parser("tables", help="List tables in a schema")
    tables.add_argument("--schema", default="public")

    describe = subparsers.add_parser("describe", help="Describe a table")
    describe.add_argument("table")
    describe.add_argument("--schema", default="public")

    summary = subparsers.add_parser(
        "jurisdiction-summary", help="Summary counts by jurisdiction"
    )
    summary.add_argument("--limit", type=int, default=25)

    runs = subparsers.add_parser("pipeline-runs", help="Recent pipeline run rows")
    runs.add_argument("--limit", type=int, default=25)

    scrapes = subparsers.add_parser(
        "raw-scrapes", help="Recent raw_scrapes rows with source/jurisdiction context"
    )
    scrapes.add_argument("--hours", type=int, default=24)
    scrapes.add_argument("--limit", type=int, default=25)

    query = subparsers.add_parser("query", help="Run read-only SQL")
    query.add_argument("--sql", required=True, help="Read-only SELECT/WITH/SHOW query")

    return parser.parse_args(argv)


async def main_async(argv: Sequence[str]) -> int:
    args = parse_args(argv)

    if args.command == "tables":
        payload = await inspect_tables(args.db, args.schema)
    elif args.command == "describe":
        payload = await describe_table(args.db, args.table, args.schema)
    elif args.command == "jurisdiction-summary":
        payload = await jurisdiction_summary(args.db, args.limit)
    elif args.command == "pipeline-runs":
        payload = await pipeline_runs(args.db, args.limit)
    elif args.command == "raw-scrapes":
        payload = await raw_scrapes_recent(args.db, args.hours, args.limit)
    else:
        payload = await run_query(args.db, args.sql)

    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return asyncio.run(main_async(argv or []))
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(
            json.dumps({"error": str(exc), "read_only_contract": True}, indent=2),
            file=os.sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main(os.sys.argv[1:]))
