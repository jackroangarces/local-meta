from __future__ import annotations

import argparse
import sys
from pathlib import Path
import re
from typing import Any

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.database import engine
from app.services.startgg.startgg import get_players_recent_sets_with_results_batch


def _normalize_player_tag(tag: str) -> str:
    """
    Normalize tags to improve matching between StartGG displayScore tags and
    stored ranking `current_tag`.
    """
    s = str(tag or "").strip()
    if "|" in s:
        s = s.rsplit("|", 1)[-1].strip()
    return re.sub(r"\s+", " ", s).casefold()


def _resolve_latest_snapshot_id(*, region_name: str) -> int:
    sql = """
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
        ORDER BY rs.ranking_date DESC, rs.id DESC
        LIMIT 1;
    """
    with engine.connect() as conn:
        snapshot_id = conn.execute(text(sql), {"region_name": region_name}).scalar()
    if snapshot_id is None:
        raise ValueError(f"No snapshot found for region_name={region_name!r}")
    return int(snapshot_id)


def compute_and_fill_upsets(
    *,
    snapshot_id: int,
    set_limit: int,
    batch_size: int,
    force: bool = False,
    insert_batch_size: int = 250,
) -> dict[str, Any]:
    with engine.begin() as conn:
        existing_upsets_count = conn.execute(
            text("SELECT count(*) FROM upsets WHERE snapshot_id = :snapshot_id"),
            {"snapshot_id": int(snapshot_id)},
        ).scalar()
        existing_h2h_count = conn.execute(
            text("SELECT count(*) FROM head_to_heads WHERE snapshot_id = :snapshot_id"),
            {"snapshot_id": int(snapshot_id)},
        ).scalar()

        if (
            not bool(force)
            and int(existing_upsets_count or 0) > 0
            and int(existing_h2h_count or 0) > 0
        ):
            return {
                "snapshot_id": int(snapshot_id),
                "set_limit": int(set_limit),
                "batch_size": int(batch_size),
                "skipped": True,
                "existing_upsets_count": int(existing_upsets_count or 0),
                "existing_head_to_heads_count": int(existing_h2h_count or 0),
            }

        if bool(force):
            conn.execute(
                text("DELETE FROM upsets WHERE snapshot_id = :snapshot_id"),
                {"snapshot_id": int(snapshot_id)},
            )
            conn.execute(
                text("DELETE FROM head_to_heads WHERE snapshot_id = :snapshot_id"),
                {"snapshot_id": int(snapshot_id)},
            )

        ranked_rows = conn.execute(
            text(
                """
                SELECT
                    re.player_id,
                    re.rank,
                    p.current_tag,
                    p.startgg_player_id
                FROM ranking_entries re
                JOIN players p ON p.id = re.player_id
                WHERE re.snapshot_id = :snapshot_id
                """
            ),
            {"snapshot_id": int(snapshot_id)},
        ).all()

        top100_by_tag_norm: dict[str, dict[str, Any]] = {}
        ranked_by_tag_norm: dict[str, dict[str, Any]] = {}
        evaluated: list[dict[str, Any]] = []

        for r in ranked_rows:
            if r.current_tag is None or r.rank is None:
                continue

            tag_norm = _normalize_player_tag(str(r.current_tag))
            ranked_by_tag_norm[tag_norm] = {
                "player_id": int(r.player_id),
                "rank": int(r.rank),
                "current_tag": str(r.current_tag),
            }

            if int(r.rank) <= 100:
                top100_by_tag_norm[tag_norm] = {
                    "player_id": int(r.player_id),
                    "rank": int(r.rank),
                    "current_tag": str(r.current_tag),
                }

            if r.startgg_player_id is not None:
                evaluated.append(
                    {
                        "player_id": int(r.player_id),
                        "rank": int(r.rank),
                        "current_tag": str(r.current_tag),
                        "tag_norm": tag_norm,
                        "startgg_player_id": int(r.startgg_player_id),
                    }
                )

        startgg_ids = [e["startgg_player_id"] for e in evaluated]

        sets_by_startgg_id = get_players_recent_sets_with_results_batch(
            player_ids=startgg_ids,
            limit_per_player=int(set_limit),
            page=1,
            batch_size=int(batch_size),
        )

        insert_rows: list[dict[str, Any]] = []
        h2h_by_pair: dict[tuple[int, int], dict[str, Any]] = {}
        seen_ranked_set_ids: set[int] = set()
        upsets_inserted = 0
        upsets_considered = 0

        for meta in evaluated:
            startgg_id = meta["startgg_player_id"]
            self_rank = meta["rank"]
            self_tag_norm = meta["tag_norm"]

            for s in sets_by_startgg_id.get(int(startgg_id), []):
                winner_tag_norm = _normalize_player_tag(str(s.get("winner_tag") or ""))
                loser_tag_norm = _normalize_player_tag(str(s.get("loser_tag") or ""))
                set_id = s.get("set_id")
                if set_id is not None:
                    set_id = int(set_id)

                # Head-to-head cache: any ranked-vs-ranked set counts (not only upsets).
                winner_ranked = ranked_by_tag_norm.get(winner_tag_norm)
                loser_ranked = ranked_by_tag_norm.get(loser_tag_norm)
                if (
                    set_id is not None
                    and winner_ranked is not None
                    and loser_ranked is not None
                    and int(winner_ranked["player_id"]) != int(loser_ranked["player_id"])
                    and set_id not in seen_ranked_set_ids
                ):
                    seen_ranked_set_ids.add(set_id)
                    winner_id = int(winner_ranked["player_id"])
                    loser_id = int(loser_ranked["player_id"])
                    p1_id, p2_id = (winner_id, loser_id) if winner_id < loser_id else (loser_id, winner_id)
                    pair_key = (p1_id, p2_id)
                    pair_row = h2h_by_pair.get(pair_key)
                    if pair_row is None:
                        p1_meta = winner_ranked if int(winner_ranked["player_id"]) == p1_id else loser_ranked
                        p2_meta = loser_ranked if int(loser_ranked["player_id"]) == p2_id else winner_ranked
                        pair_row = {
                            "snapshot_id": int(snapshot_id),
                            "player1_id": int(p1_id),
                            "player2_id": int(p2_id),
                            "player1_tag": str(p1_meta["current_tag"]),
                            "player2_tag": str(p2_meta["current_tag"]),
                            "player1_rank": int(p1_meta["rank"]),
                            "player2_rank": int(p2_meta["rank"]),
                            "player1_wins": 0,
                            "player2_wins": 0,
                            "total_sets": 0,
                        }
                        h2h_by_pair[pair_key] = pair_row

                    pair_row["total_sets"] = int(pair_row["total_sets"]) + 1
                    if winner_id == p1_id:
                        pair_row["player1_wins"] = int(pair_row["player1_wins"]) + 1
                    else:
                        pair_row["player2_wins"] = int(pair_row["player2_wins"]) + 1

                if winner_tag_norm != self_tag_norm:
                    continue

                loser = top100_by_tag_norm.get(loser_tag_norm)
                if loser is None:
                    continue

                loser_rank = int(loser["rank"])
                if loser_rank >= self_rank:
                    continue

                if set_id is None:
                    continue

                upsets_considered += 1
                upset_factor = int(self_rank - loser_rank)
                insert_rows.append(
                    {
                        "snapshot_id": int(snapshot_id),
                        "winner_player_id": int(meta["player_id"]),
                        "defeated_player_id": int(loser["player_id"]),
                        "set_id": int(set_id),
                        "winner_tag": str(meta["current_tag"]),
                        "defeated_tag": str(loser["current_tag"]),
                        "winner_rank": int(self_rank),
                        "defeated_rank": int(loser_rank),
                        "upset_factor": int(upset_factor),
                    }
                )

                if len(insert_rows) >= int(insert_batch_size):
                    _do_upsert(conn, insert_rows)
                    upsets_inserted += len(insert_rows)
                    insert_rows = []

        if insert_rows:
            _do_upsert(conn, insert_rows)
            upsets_inserted += len(insert_rows)

        h2h_rows = list(h2h_by_pair.values())
        _do_upsert_head_to_heads(conn, h2h_rows)

        return {
            "snapshot_id": int(snapshot_id),
            "set_limit": int(set_limit),
            "players_total_in_snapshot": int(len(ranked_rows)),
            "players_evaluated": int(len(evaluated)),
            "upsets_considered": int(upsets_considered),
            "upsets_rows_attempted_insert": int(upsets_inserted),
            "head_to_heads_rows_upserted": int(len(h2h_rows)),
        }


def _do_upsert(conn, rows: list[dict[str, Any]]) -> None:
    sql = text(
        """
        INSERT INTO upsets (
            snapshot_id,
            winner_player_id,
            defeated_player_id,
            set_id,
            winner_tag,
            defeated_tag,
            winner_rank,
            defeated_rank,
            upset_factor
        )
        VALUES (
            :snapshot_id,
            :winner_player_id,
            :defeated_player_id,
            :set_id,
            :winner_tag,
            :defeated_tag,
            :winner_rank,
            :defeated_rank,
            :upset_factor
        )
        ON CONFLICT (snapshot_id, set_id) DO NOTHING;
        """
    )
    if not rows:
        return
    conn.execute(sql, rows)


def _do_upsert_head_to_heads(conn, rows: list[dict[str, Any]]) -> None:
    sql = text(
        """
        INSERT INTO head_to_heads (
            snapshot_id,
            player1_id,
            player2_id,
            player1_tag,
            player2_tag,
            player1_rank,
            player2_rank,
            player1_wins,
            player2_wins,
            total_sets
        )
        VALUES (
            :snapshot_id,
            :player1_id,
            :player2_id,
            :player1_tag,
            :player2_tag,
            :player1_rank,
            :player2_rank,
            :player1_wins,
            :player2_wins,
            :total_sets
        )
        ON CONFLICT (snapshot_id, player1_id, player2_id)
        DO UPDATE SET
            player1_tag = EXCLUDED.player1_tag,
            player2_tag = EXCLUDED.player2_tag,
            player1_rank = EXCLUDED.player1_rank,
            player2_rank = EXCLUDED.player2_rank,
            player1_wins = EXCLUDED.player1_wins,
            player2_wins = EXCLUDED.player2_wins,
            total_sets = EXCLUDED.total_sets,
            updated_at = NOW();
        """
    )
    if not rows:
        return
    conn.execute(sql, rows)


# poetry run python scripts/compute_upsets.py --region-name "Western Washington"
def main() -> None:
    parser = argparse.ArgumentParser(description="Populate the `upsets` cache table for a ranking snapshot.")
    parser.add_argument("--region-name", dest="region_name", help="Region name (from UI dropdown).")
    parser.add_argument("--snapshot-id", dest="snapshot_id", type=int, help="ranking_snapshots.id to compute for.")
    parser.add_argument("--set-limit", dest="set_limit", type=int, default=100, help="How many recent sets per player.")
    parser.add_argument("--batch-size", dest="batch_size", type=int, default=6, help="Players per batched StartGG query.")
    parser.add_argument("--force", dest="force", action="store_true", help="Recompute even if upsets already exist for the snapshot.")
    args = parser.parse_args()

    if args.snapshot_id is None and not args.region_name:
        raise SystemExit("Provide either --snapshot-id or --region-name")

    snapshot_id = args.snapshot_id if args.snapshot_id is not None else _resolve_latest_snapshot_id(region_name=args.region_name)
    summary = compute_and_fill_upsets(
        snapshot_id=snapshot_id,
        set_limit=args.set_limit,
        batch_size=args.batch_size,
        force=bool(args.force),
    )
    print(summary)


if __name__ == "__main__":
    main()

