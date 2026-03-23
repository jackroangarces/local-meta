from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.database import engine, get_db
from app.db.models import Region
from scripts.import_character_data import get_character_decoder_template

router = APIRouter(prefix="/regions", tags=["regions"])


@router.get("/names")
def list_region_names(db: Session = Depends(get_db)):
    stmt = select(Region.name).order_by(Region.name)
    names = list(db.scalars(stmt).all())
    return {"names": names}

@router.get("/top-players/current-tags")
def top_players_current_tags(
    region_name: str = Query(..., description="Region `name` as shown in the regions dropdown"),
):
    order_by = "rs.ranking_date DESC, rs.id DESC"

    sql = f"""
        WITH target_region AS (
            SELECT id
            FROM regions
            WHERE name = :region_name
            ORDER BY id DESC
            LIMIT 1
        ),
        latest_snapshot AS (
            SELECT rs.id
            FROM ranking_snapshots rs
            JOIN target_region tr ON rs.region_id = tr.id
            ORDER BY {order_by}
            LIMIT 1
        )
        SELECT re.rank, p.current_tag, p.supermajor_player_id
        FROM ranking_entries re
        JOIN latest_snapshot ls ON re.snapshot_id = ls.id
        JOIN players p ON p.id = re.player_id
        ORDER BY re.rank ASC
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"region_name": region_name}).all()

    top_players = [
        {
            "current_tag": str(r.current_tag),
            "supermajor_player_id": int(r.supermajor_player_id),
        }
        for r in rows
        if r.current_tag is not None and r.supermajor_player_id is not None
    ]
    return {"top_players": top_players}


@router.get("/most-mained-characters")
def most_mained_characters(
    region_name: str = Query(..., description="Region `name` as shown in the regions dropdown"),
):
    """
    For the latest ranking snapshot in the given region:
    - For each player, find their max `play_percent` across `character_usage`.
    - Count every character tied for first place per player.
    - Return the top 10 characters by number of appearances across players.
    """
    order_by = "rs.ranking_date DESC, rs.id DESC"

    sql = f"""
        WITH target_region AS (
            SELECT id
            FROM regions
            WHERE name = :region_name
            ORDER BY id DESC
            LIMIT 1
        ),
        latest_snapshot AS (
            SELECT rs.id
            FROM ranking_snapshots rs
            JOIN target_region tr ON rs.region_id = tr.id
            ORDER BY {order_by}
            LIMIT 1
        ),
        player_max AS (
            SELECT
                cu.player_id,
                MAX(cu.play_percent) AS max_play_percent
            FROM character_usage cu
            JOIN latest_snapshot ls ON cu.snapshot_id = ls.id
            GROUP BY cu.player_id
        ),
        player_top_characters AS (
            SELECT
                cu.character_id,
                cu.character_name
            FROM character_usage cu
            JOIN latest_snapshot ls ON cu.snapshot_id = ls.id
            JOIN player_max pm
                ON pm.player_id = cu.player_id
                AND cu.play_percent = pm.max_play_percent
        )
        SELECT
            ptc.character_id,
            ptc.character_name,
            COUNT(*)::int AS main_count
        FROM player_top_characters ptc
        GROUP BY ptc.character_id, ptc.character_name
        ORDER BY main_count DESC, ptc.character_name ASC
        LIMIT 10;
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"region_name": region_name}).all()

    return {
        "most_mained_characters": [
            {
                "character_id": float(r.character_id),
                "character_name": str(r.character_name),
                "main_count": int(r.main_count),
            }
            for r in rows
        ]
    }


@router.get("/most-battled-characters")
def most_battled_characters(
    region_name: str = Query(..., description="Region `name` as shown in the regions dropdown"),
):
    """
    For the latest ranking snapshot in the given region:
    - Aggregate `games_played` across all rows in `character_usage` for that snapshot
    - Return the top 10 characters by total games_played.
    """
    order_by = "rs.ranking_date DESC, rs.id DESC"

    sql = f"""
        WITH target_region AS (
            SELECT id
            FROM regions
            WHERE name = :region_name
            ORDER BY id DESC
            LIMIT 1
        ),
        latest_snapshot AS (
            SELECT rs.id
            FROM ranking_snapshots rs
            JOIN target_region tr ON rs.region_id = tr.id
            ORDER BY {order_by}
            LIMIT 1
        )
        SELECT
            cu.character_id,
            cu.character_name,
            SUM(cu.games_played)::int AS games_played_sum
        FROM character_usage cu
        JOIN latest_snapshot ls ON cu.snapshot_id = ls.id
        GROUP BY cu.character_id, cu.character_name
        ORDER BY games_played_sum DESC, cu.character_name ASC
        LIMIT 10;
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"region_name": region_name}).all()

    return {
        "most_battled_characters": [
            {
                "character_id": float(r.character_id),
                "character_name": str(r.character_name),
                "games_played_sum": int(r.games_played_sum),
            }
            for r in rows
        ]
    }


@router.get("/least-appearances-characters")
def least_appearances_characters(
    region_name: str = Query(..., description="Region `name` as shown in the regions dropdown"),
):
    """
    For the latest ranking snapshot in the given region:
    - Aggregate `games_played` across all rows in `character_usage` for that snapshot
    - Return the top 10 characters with the least total games_played.
    """
    order_by = "rs.ranking_date DESC, rs.id DESC"

    sql = f"""
        WITH target_region AS (
            SELECT id
            FROM regions
            WHERE name = :region_name
            ORDER BY id DESC
            LIMIT 1
        ),
        latest_snapshot AS (
            SELECT rs.id
            FROM ranking_snapshots rs
            JOIN target_region tr ON rs.region_id = tr.id
            ORDER BY {order_by}
            LIMIT 1
        )
        SELECT
            cu.character_id,
            cu.character_name,
            SUM(cu.games_played)::int AS games_played_sum
        FROM character_usage cu
        JOIN latest_snapshot ls ON cu.snapshot_id = ls.id
        GROUP BY cu.character_id, cu.character_name
        ORDER BY games_played_sum ASC, cu.character_name ASC
        LIMIT 10;
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"region_name": region_name}).all()

    return {
        "least_appearances_characters": [
            {
                "character_id": float(r.character_id),
                "character_name": str(r.character_name),
                "games_played_sum": int(r.games_played_sum),
            }
            for r in rows
        ]
    }


@router.get("/unused-characters")
def unused_characters(
    region_name: str = Query(..., description="Region `name` as shown in the regions dropdown"),
):
    """
    For the latest ranking snapshot in the given region:
    - Compare all decoder character IDs against character_usage rows in that snapshot
    - Return all characters that never appear (no rows) for that snapshot/region
    """
    order_by = "rs.ranking_date DESC, rs.id DESC"

    sql_snapshot_id = f"""
        WITH target_region AS (
            SELECT id
            FROM regions
            WHERE name = :region_name
            ORDER BY id DESC
            LIMIT 1
        )
        SELECT rs.id
        FROM ranking_snapshots rs
        JOIN target_region tr ON rs.region_id = tr.id
        ORDER BY {order_by}
        LIMIT 1;
    """

    sql_present_char_ids = """
        SELECT DISTINCT character_id
        FROM character_usage
        WHERE snapshot_id = :snapshot_id;
    """

    with engine.connect() as conn:
        snapshot_id = conn.execute(text(sql_snapshot_id), {"region_name": region_name}).scalar()
        if snapshot_id is None:
            return {"unused_characters": []}

        rows = conn.execute(text(sql_present_char_ids), {"snapshot_id": snapshot_id}).all()

    def norm_id(v) -> float:
        return round(float(v), 1)

    present_char_ids = {norm_id(r.character_id) for r in rows}

    decoder = get_character_decoder_template()
    unused: list[dict[str, object]] = []
    seen_norm_ids: set[float] = set()

    for char_id, char_name in decoder.values():
        n = norm_id(char_id)
        if n in seen_norm_ids:
            continue
        seen_norm_ids.add(n)
        if n not in present_char_ids:
            unused.append({"character_id": float(char_id), "character_name": str(char_name)})

    # Stable ordering so the UI doesn't jump around between runs
    unused.sort(key=lambda x: str(x["character_name"]))

    return {"unused_characters": unused}
