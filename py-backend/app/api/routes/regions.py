from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.database import engine, get_db
from app.db.models import Region

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
