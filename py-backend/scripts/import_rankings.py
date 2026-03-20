from pathlib import Path
from datetime import date
import csv
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from datetime import datetime

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

engine = create_engine(DATABASE_URL)

def import_csv(csv_path: Path, region_slug: str, region_name: str, ranking_date: date):
    with engine.begin() as conn:
        region_row = conn.execute(
            text("""
                INSERT INTO regions (slug, name)
                VALUES (:slug, :name)
                ON CONFLICT (slug) DO UPDATE
                SET name = EXCLUDED.name
                RETURNING id
            """),
            {"slug": region_slug, "name": region_name},
        ).fetchone()

        region_id = region_row[0]

        snapshot_row = conn.execute(
            text("""
                INSERT INTO ranking_snapshots (region_id, source, ranking_date)
                VALUES (:region_id, :source, :ranking_date)
                ON CONFLICT (region_id, ranking_date) DO UPDATE
                SET source = EXCLUDED.source
                RETURNING id
            """),
            {
                "region_id": region_id,
                "source": "patreon_csv",
                "ranking_date": ranking_date,
            },
        ).fetchone()

        snapshot_id = snapshot_row[0]

        with csv_path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)

            next(reader, None)

            for row in reader:
                if not row:
                    continue
                # rank, tag, rating, character, supermajor_id
                if len(row) < 5:
                    print(f"Skipping malformed row: {row}")
                    continue

                rank = int(row[0].strip())

                if rank > 100:
                    break

                tag = row[1].strip()
                power_rating = float(row[2].strip())
                supermajor_player_id = int(row[4].strip())

                player_row = conn.execute(
                    text("""
                        INSERT INTO players (supermajor_player_id, current_tag)
                        VALUES (:supermajor_player_id, :current_tag)
                        ON CONFLICT (supermajor_player_id) DO UPDATE
                        SET current_tag = EXCLUDED.current_tag
                        RETURNING id
                    """),
                    {
                        "supermajor_player_id": int(supermajor_player_id),
                        "current_tag": tag,
                    },
                ).fetchone()

                player_id = player_row[0]

                conn.execute(
                    text("""
                        INSERT INTO ranking_entries (
                            snapshot_id,
                            player_id,
                            rank,
                            power_rating,
                            raw_tag
                        )
                        VALUES (
                            :snapshot_id,
                            :player_id,
                            :rank,
                            :power_rating,
                            :raw_tag
                        )
                        ON CONFLICT (snapshot_id, rank) DO UPDATE
                        SET
                            player_id = EXCLUDED.player_id,
                            power_rating = EXCLUDED.power_rating,
                            raw_tag = EXCLUDED.raw_tag
                    """),
                    {
                        "snapshot_id": snapshot_id,
                        "player_id": player_id,
                        "rank": rank,
                        "power_rating": power_rating,
                        "raw_tag": tag,
                    },
                )

    print(f"Imported {csv_path} for {region_slug} on {ranking_date}")

def parse_date_from_filename(filename: str):
    # remove .csv
    name = filename.replace(".csv", "")
    return datetime.strptime(name, "%B %d, %Y").date()

if __name__ == "__main__":
    csv_path = Path("data/reviewed/rankings/western-washington/March 16, 2026.csv")
    import_csv(
        csv_path=csv_path,
        region_slug="western-washington",
        region_name="Western Washington",
        ranking_date=parse_date_from_filename(csv_path.name),
    )