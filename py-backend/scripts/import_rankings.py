import csv
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

import requests

_PY_ROOT = Path(__file__).resolve().parent.parent
if str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from app.services.startgg.startgg import get_startgg_player_id_for_user_slug

load_dotenv()

SUPERMAJOR_BASE_URL = "https://www.supermajor.gg"


def _build_supermajor_player_url(current_tag: str, supermajor_id: int | str) -> str:
    path_tag = quote(current_tag, safe="")
    return f"{SUPERMAJOR_BASE_URL}/ultimate/player/{path_tag}?id=S{supermajor_id}&offline"


def _extract_startgg_user_id(html_text: str) -> str | None:
    m = re.search(r"https?://(?:www\.)?start\.gg/user/([a-zA-Z0-9]+)", html_text)
    return m.group(1) if m else None


def _fetch_supermajor_player_html(current_tag: str, supermajor_id: int | str) -> str:
    url = _build_supermajor_player_url(current_tag, supermajor_id)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set")

engine = create_engine(DATABASE_URL)


def _scrape_startgg_user_id(tag: str, supermajor_player_id: int) -> str | None:
    try:
        html = _fetch_supermajor_player_html(tag, supermajor_player_id)
        return _extract_startgg_user_id(html)
    except Exception as exc:
        print(f"Could not fetch start.gg user id for {tag!r} (S{supermajor_player_id}): {exc}")
        return None


def _resolve_startgg_player_id(startgg_user_hex: str | None) -> int | None:
    if not startgg_user_hex:
        return None
    slug = f"user/{startgg_user_hex}"
    try:
        return get_startgg_player_id_for_user_slug(user_slug=slug)
    except Exception as exc:
        print(f"Could not resolve start.gg player id for {slug}: {exc}")
        return None


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

                startgg_user_id = _scrape_startgg_user_id(tag, supermajor_player_id)
                startgg_player_id = _resolve_startgg_player_id(startgg_user_id)

                player_row = conn.execute(
                    text("""
                        INSERT INTO players (
                            supermajor_player_id,
                            current_tag,
                            startgg_user_id,
                            startgg_player_id
                        )
                        VALUES (
                            :supermajor_player_id,
                            :current_tag,
                            :startgg_user_id,
                            :startgg_player_id
                        )
                        ON CONFLICT (supermajor_player_id) DO UPDATE
                        SET
                            current_tag = EXCLUDED.current_tag,
                            startgg_user_id = COALESCE(EXCLUDED.startgg_user_id, players.startgg_user_id),
                            startgg_player_id = COALESCE(EXCLUDED.startgg_player_id, players.startgg_player_id)
                        RETURNING id
                    """),
                    {
                        "supermajor_player_id": int(supermajor_player_id),
                        "current_tag": tag,
                        "startgg_user_id": startgg_user_id,
                        "startgg_player_id": startgg_player_id,
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
    name = filename.replace(".csv", "").strip()
    m = re.match(r"^(.+,\s*\d{4})", name)
    if m:
        name = m.group(1).strip()
    return datetime.strptime(name, "%B %d, %Y").date()

if __name__ == "__main__":
    csv_path = Path("data/reviewed/rankings/western-washington/March 16, 2026.csv")
    region_slug = csv_path.parent.name
    region_name = " ".join(word.capitalize() for word in region_slug.replace("-", " ").split())
    import_csv(
        csv_path=csv_path,
        region_slug=region_slug,
        region_name=region_name,
        ranking_date=parse_date_from_filename(csv_path.name),
    )