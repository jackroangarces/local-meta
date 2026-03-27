from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]  # py-backend/
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.compute_upsets import compute_and_fill_upsets, _resolve_latest_snapshot_id  # type: ignore
from scripts.import_rankings import import_csv, parse_date_from_filename  # type: ignore
from sqlalchemy import text

from app.db.database import engine


def _region_slug_to_name(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.replace("-", " ").split())


def _pick_most_recent_csv(csv_paths: list[Path]) -> Path | None:
    if not csv_paths:
        return None

    def key(p: Path):
        return parse_date_from_filename(p.name)

    return sorted(csv_paths, key=key)[-1]


def _get_existing_upsets_count(snapshot_id: int) -> int:
    with engine.connect() as conn:
        return int(
            conn.execute(
                text("SELECT count(*) FROM upsets WHERE snapshot_id = :snapshot_id"),
                {"snapshot_id": int(snapshot_id)},
            ).scalar()
            or 0
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import latest reviewed rankings per region and populate upsets cache."
    )
    parser.add_argument("--rankings-root", default=str(ROOT / "data" / "reviewed" / "rankings"))
    parser.add_argument("--set-limit", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=6)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute upsets even if cached upsets already exist for the snapshot.",
    )
    args = parser.parse_args()

    print(
        "[note] this pipeline expects `upsets` and `head_to_heads` tables to exist in the database."
    )

    rankings_root = Path(args.rankings_root)
    if not rankings_root.exists():
        raise SystemExit(f"rankings_root does not exist: {rankings_root}")

    region_dirs = [p for p in rankings_root.iterdir() if p.is_dir()]
    if not region_dirs:
        raise SystemExit(f"No region folders found under: {rankings_root}")

    for region_dir in sorted(region_dirs, key=lambda p: p.name):
        region_slug = region_dir.name
        region_name = _region_slug_to_name(region_slug)

        csv_paths = sorted(region_dir.glob("*.csv"))
        most_recent_csv = _pick_most_recent_csv(csv_paths)
        if most_recent_csv is None:
            print(f"[skip] {region_slug}: no csv files found")
            continue

        ranking_date = parse_date_from_filename(most_recent_csv.name)
        print(f"[import] {region_name} ({region_slug}) <- {most_recent_csv.name}")
        import_csv(
            csv_path=most_recent_csv,
            region_slug=region_slug,
            region_name=region_name,
            ranking_date=ranking_date,
        )

        snapshot_id = _resolve_latest_snapshot_id(region_name=region_name)
        if not args.force:
            existing = _get_existing_upsets_count(snapshot_id)
            if existing > 0:
                print(f"[skip upsets] {region_name}: snapshot_id={snapshot_id} already has upsets ({existing})")
                continue

        print(f"[compute upsets] {region_name}: snapshot_id={snapshot_id}")
        summary = compute_and_fill_upsets(
            snapshot_id=snapshot_id,
            set_limit=int(args.set_limit),
            batch_size=int(args.batch_size),
            force=bool(args.force),
        )
        print(summary)


if __name__ == "__main__":
    main()

