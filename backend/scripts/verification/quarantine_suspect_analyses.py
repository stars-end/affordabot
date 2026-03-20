"""
Quarantine suspect analyses (bd-tytc.7).

Marks analyses that were produced under the broken pipeline
as suspect so they are not presented as valid.

Usage:
  python backend/scripts/verification/quarantine_suspect_analyses.py --jurisdiction california --dry-run
  python backend/scripts/verification/quarantine_suspect_analyses.py --jurisdiction california
  python backend/scripts/verification/quarantine_suspect_analyses.py --all-jurisdictions --dry-run
  python backend/scripts/verification/quarantine_suspect_analyses.py --all-jurisdictions
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(BACKEND_ROOT))


async def quarantine_jurisdiction(db, jurisdiction: str, dry_run: bool = False) -> dict:
    """Quarantine all analyses for a jurisdiction that lack source text or provenance."""
    query = """
        UPDATE legislation SET analysis_status = 'quarantined'
        WHERE jurisdiction_id = (
            SELECT id FROM jurisdictions WHERE LOWER(name) = LOWER($1)
        )
        AND (
            (analysis_status IS NULL AND sufficiency_state IS NULL)
            OR analysis_status = 'pending'
            OR (sufficiency_state IN ('research_incomplete', 'insufficient_evidence')
                AND analysis_status != 'quarantined')
        )
        RETURNING id, bill_number, title, analysis_status, sufficiency_state, total_impact_p50
    """

    if dry_run:
        check_query = query.replace(
            "UPDATE legislation SET analysis_status = 'quarantined'",
            "SELECT id, bill_number, title, analysis_status, sufficiency_state, total_impact_p50",
        )
        rows = await db._fetch(check_query, jurisdiction)
        return {
            "jurisdiction": jurisdiction,
            "dry_run": True,
            "would_quarantine": len(rows),
            "records": [
                {
                    "id": str(r["id"]),
                    "bill_number": r["bill_number"],
                    "title": r["title"],
                    "previous_status": r.get("analysis_status"),
                    "sufficiency_state": r.get("sufficiency_state"),
                }
                for r in rows
            ],
        }

    rows = await db._fetch(query, jurisdiction)
    return {
        "jurisdiction": jurisdiction,
        "dry_run": False,
        "quarantined": len(rows),
        "records": [
            {
                "id": str(r["id"]),
                "bill_number": r["bill_number"],
                "title": r["title"],
            }
            for r in rows
        ],
    }


async def quarantine_all(db, dry_run: bool = False) -> dict:
    """Quarantine suspect analyses across all jurisdictions."""
    all_jurisdictions = await db._fetch(
        "SELECT id, name FROM jurisdictions ORDER BY name"
    )
    results = {}
    for jur in all_jurisdictions:
        jur_name = jur["name"]
        results[jur_name] = await quarantine_jurisdiction(db, jur_name, dry_run)
    total = sum(
        r.get("would_quarantine", r.get("quarantined", 0)) for r in results.values()
    )
    return {"total_quarantined": total, "by_jurisdiction": results}


async def main():
    parser = argparse.ArgumentParser(description="Quarantine suspect analyses")
    parser.add_argument("--jurisdiction", default=None)
    parser.add_argument("--all-jurisdictions", action="store_true")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without changes"
    )
    args = parser.parse_args()

    if not args.jurisdiction and not args.all_jurisdictions:
        parser.error("Must provide --jurisdiction or --all-jurisdictions")

    from db.postgres_client import PostgresDB

    db = PostgresDB()
    await db.connect()

    try:
        if args.all_jurisdictions:
            result = await quarantine_all(db, dry_run=args.dry_run)
        else:
            result = await quarantine_jurisdiction(
                db, args.jurisdiction, dry_run=args.dry_run
            )

        print(json.dumps(result, indent=2, default=str))
    finally:
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
