from __future__ import annotations

import argparse
import json
import re
from typing import Any

from sqlalchemy import text

from app.db.database import engine

from scripts.fetch_character_data import scrape_last_6mo_character_usage

def get_character_decoder_template() -> dict[str, tuple[float, str]]:
    decoder_int: dict[str, tuple[int, str]] = {
        "A1302": (1, "Mario"),
        "A1280": (2, "Donkey Kong"),
        "A1296": (3, "Link"),
        "A1328": (4, "Samus"), 
        "A1408": (4.1, "Dark Samus"),
        "A1338": (5, "Yoshi"),
        "A1295": (6, "Kirby"), 
        "A1286": (7, "Fox"),
        "A1319": (8, "Pikachu"),
        "A1301": (9, "Luigi"),
        "A1313": (10, "Ness"),
        "A1274": (11, "Captain Falcon"),
        "A1293": (12, "Jigglypuff"),
        "A1317": (13, "Peach"),
        "A1277": (13.1, "Daisy"),
        "A1273": (14, "Bowser"),
        "A1290": (15, "Ice Climbers"),
        "A1329": (16, "Sheik"),
        "A1340": (17, "Zelda"),
        "A1282": (18, "Dr. Mario"),
        "A1318": (19, "Pichu"),
        "A1285": (20, "Falco"),
        "A1304": (21, "Marth"),
        "A1300": (21.1, "Lucina"),
        "A1339": (22, "Young Link"),
        "A1287": (23, "Ganondorf"),
        "A1310": (24, "Mewtwo"),
        "A1326": (25, "Roy"), #img to here
        "A1332": (25.1, "Chrom"),
        "A1338": (26, "Mr. Game and Watch"),
        "A1323": (27, "Meta Knight"),
        "A1332": (28, "Pit"),
        "A1338": (28.1, "Dark Pit"),
        "A1323": (29, "Zero Suit Samus"),
        "A1338": (30, "Wario"),
        "A1405": (31, "Snake"),
        "A1332": (32, "Ike"),
        "A1323": (33, "Pokemon Trainer"),
        "A1338": (36, "Diddy Kong"),
        "A1323": (37, "Lucas"),
        "A1338": (38, "Sonic"),
        "A1332": (39, "King Dedede"),
        "A1323": (40, "Olimar"),
        "A1338": (41, "Lucario"),
        "A1323": (42, "R.O.B."),
        "A1338": (43, "Toon Link"),
        "A1405": (44, "Wolf"),
        "A1332": (45, "Villager"),
        "A1323": (46, "Mega Man"),
        "A1338": (47, "Wii Fit Trainer"),
        "A1405": (48, "Rosalina & Luma"),
        "A1332": (49, "Little Mac"),
        "A1323": (50, "Greninja"),
        "A1338": (51, "Mii Brawler"),
        "A1405": (52, "Mii Swordfighter"),
        "A1332": (53, "Mii Gunner"),
        "A1323": (54, "Palutena"),
        "A1338": (55, "Pac-Man"),
        "A1405": (56, "Robin"),
        "A1332": (57, "Shulk"),
        "A1323": (58, "Bowser Jr."),
        "A1338": (59, "Duck Hunt"),
        "A1405": (60, "Ryu"),
        "A1332": (60.1, "Ken"),
        "A1323": (61, "Cloud"),
        "A1338": (62, "Corrin"),
        "A1405": (63, "Bayonetta"),
        "A1332": (64, "Inkling"),
        "A1323": (65, "Ridley"),
        "A1338": (66, "Simon"),
        "A1323": (66.1, "Richter"),
        "A1405": (67, "King K. Rool"),
        "A1332": (68, "Isabelle"),
        "A1323": (69, "Incineroar"),
        "A1338": (70, "Pirhana Plant"),
        "A1405": (71, "Joker"),
        "A1332": (72, "Hero"),
        "A1323": (73, "Banjo & Kazooie"),
        "A1338": (74, "Terry"),
        "A1405": (75, "Byleth"),
        "A1332": (76, "Min Min"),
        "A1323": (77, "Steve"),
        "A1338": (78, "Sephiroth"),
        "A1405": (79, "Pyra/Mythra"),
        "A1323": (81, "Kazuya"),
        "A1338": (82, "Sora"),
    }

    return {k: (float(v[0]), v[1]) for k, v in decoder_int.items()}

def decode_character(image_identifier: str) -> tuple[float, str]:
    decoder = get_character_decoder_template()
    if image_identifier in decoder:
        char_id, char_name = decoder[image_identifier]
        return char_id, char_name

    m = re.fullmatch(r"A(\d+(?:\.\d+)?)", image_identifier)
    if m:
        return float(m.group(1)), "Unknown (fill decoder template)"

    raise ValueError(f"Unexpected character image identifier format: {image_identifier}")


def _insert_character_usage(
    conn,
    *,
    snapshot_id: int,
    player_id: int,
    play_percent: int,
    games_played: int,
    character_id: float,
    character_name: str,
) -> None:
    columns = [
        "snapshot_id",
        "player_id",
        "play_percent",
        "games_played",
        "character_id",
        "character_name",
    ]

    values: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "player_id": player_id,
        "play_percent": play_percent,
        "games_played": games_played,
        "character_id": character_id,
        "character_name": character_name,
    }

    conflict_target = "(snapshot_id, player_id, character_id)"

    update_sets = [
        "play_percent = EXCLUDED.play_percent",
        "games_played = EXCLUDED.games_played",
    ]
    update_sets += [
        "character_id = EXCLUDED.character_id",
        "character_name = EXCLUDED.character_name",
    ]

    sql = text(
        f"""
        INSERT INTO character_usage ({", ".join(columns)})
        VALUES ({", ".join([f":{c}" for c in columns])})
        ON CONFLICT {conflict_target}
        DO UPDATE SET {", ".join(update_sets)}
        """
    )
    conn.execute(sql, values)


def import_for_snapshot(snapshot_id: int) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "players_processed": 0,
        "character_rows_written": 0,
        "errors": [],
    }

    with engine.begin() as conn:
        players = conn.execute(
            text(
                """
                SELECT DISTINCT
                    re.player_id,
                    p.current_tag,
                    p.supermajor_player_id
                FROM ranking_entries re
                JOIN players p ON p.id = re.player_id
                WHERE re.snapshot_id = :snapshot_id
                ORDER BY re.rank ASC
                """
            ),
            {"snapshot_id": snapshot_id},
        ).all()

        for (player_id, current_tag, supermajor_player_id) in players:
            summary["players_processed"] += 1
            try:
                usages = scrape_last_6mo_character_usage(current_tag, supermajor_player_id)
                for u in usages:
                    character_id, character_name = decode_character(u.image_identifier)
                    _insert_character_usage(
                        conn,
                        snapshot_id=snapshot_id,
                        player_id=player_id,
                        play_percent=u.play_percent,
                        games_played=u.games_played,
                        character_id=character_id,
                        character_name=character_name,
                    )
                    summary["character_rows_written"] += 1
            except Exception as exc:  # noqa: BLE001
                summary["errors"].append(
                    {
                        "player_id": player_id,
                        "current_tag": current_tag,
                        "supermajor_player_id": supermajor_player_id,
                        "error": str(exc),
                    }
                )

    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Import character usage (top 4) for a snapshot.")
    parser.add_argument("snapshot_id", type=int, help="ranking_snapshots.id")
    args = parser.parse_args()

    summary = import_for_snapshot(args.snapshot_id)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

