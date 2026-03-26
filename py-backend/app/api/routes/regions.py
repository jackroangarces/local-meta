import csv
import json
import re
from pathlib import Path

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


@router.get("/latest-snapshot")
def latest_snapshot(
    region_name: str = Query(..., description="Region `name` as shown in the regions dropdown"),
):
    """
    Return latest ranking snapshot id/date for the given region name.
    """
    order_by = "rs.ranking_date DESC, rs.id DESC"
    sql = f"""
        WITH target_region AS (
            SELECT id
            FROM regions
            WHERE name = :region_name
            ORDER BY id DESC
            LIMIT 1
        )
        SELECT rs.id, rs.ranking_date
        FROM ranking_snapshots rs
        JOIN target_region tr ON rs.region_id = tr.id
        ORDER BY {order_by}
        LIMIT 1;
    """

    with engine.connect() as conn:
        row = conn.execute(text(sql), {"region_name": region_name}).fetchone()

    if row is None:
        return {"snapshot_id": None, "ranking_date": None}

    return {"snapshot_id": int(row.id), "ranking_date": row.ranking_date.isoformat()}


def _query_most_mained_characters(region_name: str, *, limit: int | None = 10) -> list[dict[str, object]]:
    order_by = "rs.ranking_date DESC, rs.id DESC"
    limit_sql = "" if limit is None else f"LIMIT {int(limit)}"

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
                cu.player_id,
                cu.character_id,
                cu.character_name
            FROM character_usage cu
            JOIN latest_snapshot ls ON cu.snapshot_id = ls.id
            JOIN player_max pm
                ON pm.player_id = cu.player_id
                AND cu.play_percent = pm.max_play_percent
        ),
        player_ranks AS (
            SELECT
                re.player_id,
                re.rank
            FROM ranking_entries re
            JOIN latest_snapshot ls ON re.snapshot_id = ls.id
        )
        ,
        character_main_counts AS (
            SELECT
                ptc.character_id,
                ptc.character_name,
                COUNT(*)::int AS main_count
            FROM player_top_characters ptc
            GROUP BY ptc.character_id, ptc.character_name
        ),
        top_characters AS (
            SELECT *
            FROM character_main_counts
            ORDER BY main_count DESC, character_name ASC
            {limit_sql}
        )
        SELECT
            tc.character_id,
            tc.character_name,
            tc.main_count,
            COALESCE(
                jsonb_agg(
                    jsonb_build_object(
                        'player_id', ptc.player_id,
                        'current_tag', p.current_tag,
                        'rank', pr.rank
                    )
                    ORDER BY pr.rank ASC, p.current_tag ASC
                ),
                '[]'::jsonb
            ) AS mains_players
        FROM top_characters tc
        JOIN player_top_characters ptc
            ON ptc.character_id = tc.character_id
        JOIN players p
            ON p.id = ptc.player_id
        LEFT JOIN player_ranks pr
            ON pr.player_id = ptc.player_id
        GROUP BY tc.character_id, tc.character_name, tc.main_count
        ORDER BY tc.main_count DESC, tc.character_name ASC;
    """

    with engine.connect() as conn:
        rows = conn.execute(text(sql), {"region_name": region_name}).all()

    return [
        {
            "character_id": float(r.character_id),
            "character_name": str(r.character_name),
            "main_count": int(r.main_count),
            "mains_players": (
                r.mains_players
                if isinstance(r.mains_players, list)
                else json.loads(r.mains_players)
                if isinstance(r.mains_players, str) and r.mains_players
                else []
            ),
        }
        for r in rows
    ]


@router.get("/most-mained-characters")
def most_mained_characters(
    region_name: str = Query(..., description="Region `name` as shown in the regions dropdown"),
    limit: int = Query(20, ge=1, le=200),
):
    return {"most_mained_characters": _query_most_mained_characters(region_name, limit=limit)}


def _normalize_char_name(name: str) -> str:
    s = name.lower().replace("&", "and").replace("/", "").replace(".", "")
    s = re.sub(r"\(.*?\)", "", s)
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


def _best_matchup_aliases(normalized_name: str) -> list[str]:
    aliases: dict[str, list[str]] = {
        "samus": ["samusanddarksamus"],
        "darksamus": ["samusanddarksamus"],
        "peach": ["peachanddaisy"],
        "daisy": ["peachanddaisy"],
        "lucina": ["lucinaecho"],
        "chrom": ["chromecho"],
        "pit": ["pitanddarkpit"],
        "darkpit": ["pitanddarkpit"],
        "miibrawler": ["miifighterbrawler"],
        "miiswordfighter": ["miifighterswordfighter"],
        "miigunner": ["miifightergunner"],
        "ken": ["kenecho"],
        "simon": ["simonandrichter"],
        "richter": ["simonandrichter"],
        "banjoandkazooie": ["banjo"],
        "pyramythra": ["aegis"],
    }
    return aliases.get(normalized_name, [])


def _resolve_csv_character_key(name: str, csv_keys: set[str]) -> str | None:
    normalized = _normalize_char_name(name)
    for candidate in [normalized, *_best_matchup_aliases(normalized)]:
        if candidate in csv_keys:
            return candidate
    return None


def _parse_percent_cell(cell: str) -> float | None:
    raw = (cell or "").strip().replace("%", "").replace(",", ".")
    if raw == "":
        return None
    try:
        return float(raw) / 100.0
    except ValueError:
        return None


def _load_winrate_matrix() -> tuple[list[str], dict[str, dict[str, float]]]:
    csv_path = Path(__file__).resolve().parents[3] / "data" / "reviewed" / "winrates.csv"
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))

    if len(rows) < 3:
        return [], {}

    defender_names = [c.strip() for c in rows[0][2:]]
    defender_keys = [_normalize_char_name(n) for n in defender_names]

    matrix: dict[str, dict[str, float]] = {}
    for row in rows[2:]:
        if not row or not row[0].strip():
            continue
        attacker_key = _normalize_char_name(row[0].strip())
        values = row[2:]
        row_map: dict[str, float] = {}
        for idx, defender_key in enumerate(defender_keys):
            if idx >= len(values):
                break
            parsed = _parse_percent_cell(values[idx])
            if parsed is not None:
                row_map[defender_key] = parsed
        matrix[attacker_key] = row_map

    return defender_keys, matrix


@router.get("/best-matchups")
def best_matchups(
    region_name: str = Query(..., description="Region `name` as shown in the regions dropdown"),
    limit: int = Query(20, ge=1, le=200),
):
    all_mains = _query_most_mained_characters(region_name, limit=None)
    if not all_mains:
        return {"best_matchups": []}

    _, matrix = _load_winrate_matrix()
    if not matrix:
        return {"best_matchups": []}

    csv_keys = set(matrix.keys())

    defender_weights: dict[str, int] = {}
    for row in all_mains:
        char_name = str(row["character_name"])
        main_count = int(row["main_count"])
        defender_key = _resolve_csv_character_key(char_name, csv_keys)
        if defender_key is None:
            continue
        defender_weights[defender_key] = defender_weights.get(defender_key, 0) + main_count

    total_weight = sum(defender_weights.values())
    if total_weight <= 0:
        return {"best_matchups": []}

    decoder = get_character_decoder_template()
    id_by_name: dict[str, float] = {}
    for char_id, char_name in decoder.values():
        n = str(char_name)
        id_by_name[n] = min(float(char_id), id_by_name.get(n, float(char_id)))

    scored: list[dict[str, object]] = []
    for char_name, char_id in id_by_name.items():
        attacker_key = _resolve_csv_character_key(char_name, csv_keys)
        if attacker_key is None:
            continue

        row = matrix.get(attacker_key, {})
        weighted_sum = 0.0
        used_weight = 0
        for defender_key, weight in defender_weights.items():
            winrate = row.get(defender_key)
            if winrate is None:
                continue
            weighted_sum += winrate * weight
            used_weight += weight

        if used_weight == 0:
            continue

        efficiency = weighted_sum / used_weight
        scored.append(
            {
                "character_id": float(char_id),
                "character_name": char_name,
                "efficiency": efficiency,
            }
        )

    scored.sort(key=lambda x: (-float(x["efficiency"]), str(x["character_name"])))
    return {"best_matchups": scored[:limit]}


@router.get("/most-battled-characters")
def most_battled_characters(
    region_name: str = Query(..., description="Region `name` as shown in the regions dropdown"),
    limit: int = Query(20, ge=1, le=200),
):
    """
    For the latest ranking snapshot in the given region:
    - Aggregate `games_played` across all rows in `character_usage` for that snapshot
    - Return the top 10 characters by total games_played.
    """
    order_by = "rs.ranking_date DESC, rs.id DESC"

    limit_sql = f"LIMIT {int(limit)}"
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
        {limit_sql};
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
    limit: int = Query(20, ge=1, le=200),
):
    
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
    sql_usage = """
        SELECT
            cu.character_id,
            cu.character_name,
            SUM(cu.games_played)::int AS games_played_sum
        FROM character_usage cu
        WHERE cu.snapshot_id = :snapshot_id
        GROUP BY cu.character_id, cu.character_name
    """

    with engine.connect() as conn:
        snapshot_id = conn.execute(text(sql_snapshot_id), {"region_name": region_name}).scalar()
        if snapshot_id is None:
            return {"least_appearances_characters": []}
        rows = conn.execute(text(sql_usage), {"snapshot_id": snapshot_id}).all()

    def norm_id(v: float) -> float:
        return round(float(v), 1)

    decoder = get_character_decoder_template()
    by_id: dict[float, dict[str, object]] = {}
    for char_id, char_name in decoder.values():
        n = norm_id(char_id)
        if n in by_id:
            continue
        by_id[n] = {
            "character_id": float(char_id),
            "character_name": str(char_name),
            "games_played_sum": 0,
        }

    for r in rows:
        n = norm_id(r.character_id)
        existing = by_id.get(n)
        if existing is None:
            by_id[n] = {
                "character_id": float(r.character_id),
                "character_name": str(r.character_name),
                "games_played_sum": int(r.games_played_sum),
            }
        else:
            existing["games_played_sum"] = int(r.games_played_sum)
            existing["character_name"] = str(r.character_name)

    combined = list(by_id.values())
    combined.sort(key=lambda x: (int(x["games_played_sum"]), str(x["character_name"])))

    return {"least_appearances_characters": combined[: int(limit)]}


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
