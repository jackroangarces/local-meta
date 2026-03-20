from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List

BASE_URL = "https://www.supermajor.gg"

@dataclass
class CharacterUsage:
    image_identifier: str
    play_percent: int
    games_played: int

def build_player_url(current_tag: str, supermajor_id: int | str) -> str:
    return f"{BASE_URL}/ultimate/player/{current_tag}?id=S{supermajor_id}"

def fetch_player_html(current_tag: str, supermajor_id: int | str) -> str:
    import requests

    url = build_player_url(current_tag, supermajor_id)
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

def _extract_last_6mo_block(html_text: str) -> str:
    """
    Return only the object body for "Last 6 Mo": { ... }.
    This ensures we don't accidentally read "All Time" stats.
    """
    start_match = re.search(r'(?:\\"|")Last 6 Mo(?:\\"|")\s*:\s*\{', html_text)
    if not start_match:
        raise ValueError('Could not find "Last 6 Mo" block start.')

    # Index of the opening "{"
    start_brace = html_text.find("{", start_match.start())
    if start_brace == -1:
        raise ValueError('Could not find opening "{" for "Last 6 Mo" block.')

    depth = 0
    for idx in range(start_brace, len(html_text)):
        ch = html_text[idx]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return html_text[start_brace + 1 : idx]

    raise ValueError('Could not find closing "}" for "Last 6 Mo" block.')

def extract_top_four_ids(html_text: str) -> list[str]:
    """
    Extract top character ids from either escaped or plain JSON-ish payload.
    """
    last_6mo_block = _extract_last_6mo_block(html_text)
    order_match = re.search(
        r'(?:\\"|")order(?:\\"|")\s*:\s*\[(.*?)\]',
        last_6mo_block,
        flags=re.DOTALL,
    )
    if not order_match:
        raise ValueError('Could not find "Last 6 Mo" order array.')

    order_blob = order_match.group(1)
    char_ids = re.findall(r'(?:\\"|")(A\d+)(?:\\"|")', order_blob)
    if len(char_ids) < 4:
        raise ValueError(f"Expected at least 4 character IDs, found {len(char_ids)}.")

    return char_ids[:4]

def extract_character_stats(html_text: str, char_id: str) -> tuple[int, int]:
    """
    Find stats near each occurrence of char_id in the payload.
    This avoids broad cross-document matching that can return the same numbers for every id.
    """
    last_6mo_block = _extract_last_6mo_block(html_text)

    # Support both escaped and plain quoted forms and common key naming variants.
    id_pattern = re.compile(rf'(?:\\"|"){re.escape(char_id)}(?:\\"|")')
    games_pattern = re.compile(r'(?:\\"|")(?:num_games|numGames)(?:\\"|")\s*:\s*(\d+)')
    usage_pattern = re.compile(r'(?:\\"|")(?:usage_rate|usageRate)(?:\\"|")\s*:\s*([0-9.]+)')

    for id_match in id_pattern.finditer(last_6mo_block):
        window = last_6mo_block[id_match.start() : id_match.start() + 12000]
        games_match = games_pattern.search(window)
        usage_match = usage_pattern.search(window)
        if games_match and usage_match:
            games_played = int(games_match.group(1))
            usage_rate = float(usage_match.group(1))
            play_percent = round(usage_rate * 100)
            return play_percent, games_played

    raise ValueError(f'Could not parse num_games/usage_rate for "{char_id}".')

def scrape_last_6mo_character_usage(current_tag: str, supermajor_id: int | str) -> List[CharacterUsage]:
    html_text = fetch_player_html(current_tag, supermajor_id)

    top_four_ids = extract_top_four_ids(html_text)

    results: List[CharacterUsage] = []
    for char_id in top_four_ids:
        play_percent, games_played = extract_character_stats(html_text, char_id)
        results.append(
            CharacterUsage(
                image_identifier=char_id,
                play_percent=play_percent,
                games_played=games_played,
            )
        )

    return results


def _default_output_path(current_tag: str, supermajor_id: int | str) -> Path:
    safe_tag = re.sub(r"[^A-Za-z0-9._-]+", "-", current_tag).strip("-") or "player"
    out_dir = Path("data") / "player-character-usage"
    return out_dir / f"{safe_tag}-S{supermajor_id}.json"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch Last 6 Mo top-4 character usage for a supermajor.gg player."
    )
    parser.add_argument("current_tag", help="Player current_tag (e.g. Clune)")
    parser.add_argument("supermajor_id", type=int, help="supermajor numeric id (without leading S)")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output JSON file path (default: data/player-character-usage/<tag>-S<id>.json)",
    )
    args = parser.parse_args()

    data = scrape_last_6mo_character_usage(args.current_tag, args.supermajor_id)
    payload = [asdict(row) for row in data]

    output_path = args.output or _default_output_path(args.current_tag, args.supermajor_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(output_path)

    