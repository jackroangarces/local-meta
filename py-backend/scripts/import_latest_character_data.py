from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]  # py-backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.database import engine
from scripts.import_character_data import import_for_snapshot


def _latest_snapshots_by_region() -> list[dict[str, Any]]:
    sql = """
        WITH ranked AS (
            SELECT
                r.id AS region_id,
                r.slug AS region_slug, 
                r.name AS region_name,
                rs.id AS snapshot_id,
                rs.ranking_date,
                ROW_NUMBER() OVER (
                    PARTITION BY r.id
                    ORDER BY rs.ranking_date DESC, rs.id DESC
                ) AS rn
            FROM regions r
            JOIN ranking_snapshots rs ON rs.region_id = r.id
        )
        SELECT
            region_id,
            region_slug,
            region_name,
            snapshot_id,
            ranking_date
        FROM ranked
        WHERE rn = 1
        ORDER BY region_name ASC;
    """
    with engine.connect() as conn:
        rows = conn.execute(text(sql)).all()

    return [
        {
            "region_id": int(r.region_id),
            "region_slug": str(r.region_slug),
            "region_name": str(r.region_name),
            "snapshot_id": int(r.snapshot_id),
            "ranking_date": r.ranking_date.isoformat() if r.ranking_date is not None else None,
        }
        for r in rows
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import character usage for the latest snapshot of every region."
    )
    parser.add_argument(
        "--region-name",
        dest="region_name",
        default=None,
        help="Optional: run for one specific region name only.",
    )
    args = parser.parse_args()

    latest = _latest_snapshots_by_region()
    if args.region_name:
        latest = [r for r in latest if r["region_name"] == args.region_name]

    if not latest:
        print(json.dumps({"regions_processed": 0, "results": []}, indent=2))
        return

    results: list[dict[str, Any]] = []
    for r in latest:
        snapshot_id = int(r["snapshot_id"])
        print(
            f"[import character data] {r['region_name']} "
            f"(snapshot_id={snapshot_id}, ranking_date={r['ranking_date']})"
        )
        summary = import_for_snapshot(snapshot_id)
        results.append(
            {
                "region_name": r["region_name"],
                "region_slug": r["region_slug"],
                "snapshot_id": snapshot_id,
                "ranking_date": r["ranking_date"],
                "import_summary": summary,
            }
        )

    print(
        json.dumps(
            {
                "regions_processed": len(results),
                "results": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

