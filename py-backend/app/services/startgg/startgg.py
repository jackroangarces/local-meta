import os
import re
import time
from collections import deque
from pathlib import Path

import requests
from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"
load_dotenv(dotenv_path=str(ENV_PATH))

STARTGG_API_URL = "https://api.start.gg/gql/alpha"
API_KEY = os.getenv("STARTGG_API_KEY")
STARTGG_SMASH_ULTIMATE_ID = 1386
STARTGG_MAX_REQUESTS_PER_MINUTE = 70
STARTGG_REQUEST_WINDOW_SECONDS = 60

_REQUEST_TIMESTAMPS: deque[float] = deque()


def _throttle_startgg_requests() -> None:
    """
    Keep request rate below start.gg public limit to avoid 429s.
    """
    now = time.time()
    window_start = now - STARTGG_REQUEST_WINDOW_SECONDS
    while _REQUEST_TIMESTAMPS and _REQUEST_TIMESTAMPS[0] < window_start:
        _REQUEST_TIMESTAMPS.popleft()

    if len(_REQUEST_TIMESTAMPS) >= STARTGG_MAX_REQUESTS_PER_MINUTE:
        sleep_for = STARTGG_REQUEST_WINDOW_SECONDS - (now - _REQUEST_TIMESTAMPS[0]) + 0.05
        if sleep_for > 0:
            time.sleep(sleep_for)
        # clean stale entries after sleeping
        now = time.time()
        window_start = now - STARTGG_REQUEST_WINDOW_SECONDS
        while _REQUEST_TIMESTAMPS and _REQUEST_TIMESTAMPS[0] < window_start:
            _REQUEST_TIMESTAMPS.popleft()

    _REQUEST_TIMESTAMPS.append(time.time())

def startgg_request(query: str, variables: dict = None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}",
    }

    max_attempts = 6
    for attempt in range(1, max_attempts + 1):
        _throttle_startgg_requests()
        response = requests.post(
            STARTGG_API_URL,
            json={
                "query": query,
                "variables": variables or {},
            },
            headers=headers,
            timeout=30,
        )
        if response.status_code == 429 and attempt < max_attempts:
            # Exponential backoff on rate-limit response.
            time.sleep(min(2 ** attempt, 30))
            continue

        response.raise_for_status()
        data = response.json()
        break

    if "errors" in data:
        raise Exception(data["errors"])

    return data["data"]

def get_startgg_player_id_for_user_slug(*, user_slug: str) -> int | None:
    query = """
    query GetPlayerForUser($userSlug: String!) {
      user(slug: $userSlug) {
        id
        player {
          id
          gamerTag
          prefix
        }
      }
    }
    """
    data = startgg_request(query, {"userSlug": user_slug})
    user = data.get("user")
    if not user:
        return None
    player = user.get("player")
    if not player or player.get("id") is None:
        return None
    return int(player["id"])

def get_upcoming_tournaments_near_location(
    *,
    latitude: float,
    longitude: float,
    radius: str = "50mi",
    per_page: int = 10,
):
    query = """
    query TournamentsByLocation(
      $perPage: Int!,
      $distanceFrom: String!,
      $distance: String!,
      $videogameId: ID!
    ) {
      tournaments(
        query: {
          perPage: $perPage
          page: 1
          sortBy: "startAt asc"
          filter: {
            upcoming: true
            videogameIds: [$videogameId]
            location: {
              distanceFrom: $distanceFrom
              distance: $distance
            }
          }
        }
      ) {
        nodes {
          id
          name
          city
          addrState
          startAt
          slug
        }
      }
    }
    """

    variables = {
        "perPage": per_page,
        "distanceFrom": f"{latitude},{longitude}",
        "distance": radius,
        "videogameId": STARTGG_SMASH_ULTIMATE_ID,
    }

    data = startgg_request(query, variables)
    return data["tournaments"]["nodes"]

def get_upcoming_tournaments_by_state(
    *,
    state: str,
    per_page: int = 10,
):
    query = """
    query TournamentsByState(
      $perPage: Int!,
      $state: String!,
      $videogameId: ID!
    ) {
      tournaments(
        query: {
          perPage: $perPage
          page: 1
          sortBy: "startAt asc"
          filter: {
            upcoming: true
            videogameIds: [$videogameId]
            addrState: $state
          }
        }
      ) {
        nodes {
          id
          name
          city
          addrState
          startAt
          slug
        }
      }
    }
    """

    variables = {
        "perPage": per_page,
        "state": state,
        "videogameId": STARTGG_SMASH_ULTIMATE_ID,
    }

    data = startgg_request(query, variables)
    return data["tournaments"]["nodes"]


def get_player_recent_set_ids(
    *,
    player_id: int,
    window_start_unix: int,
    window_end_unix: int,
    per_page: int = 50,
    max_pages: int = 60,
) -> list[int]:
    query = """
    query PlayerSetsPage($playerId: ID!, $perPage: Int!, $page: Int!) {
      player(id: $playerId) {
        sets(perPage: $perPage, page: $page) {
          pageInfo {
            totalPages
          }
          nodes {
            id
            event {
              videogame {
                id
              }
              tournament {
                startAt
              }
            }
          }
        }
      }
    }
    """

    set_ids: list[int] = []
    seen: set[int] = set()
    page = 1
    total_pages = 1

    while page <= total_pages and page <= max_pages:
        data = startgg_request(
            query,
            {
                "playerId": player_id,
                "perPage": per_page,
                "page": page,
            },
        )
        player = data.get("player")
        if not player:
            break
        sets_obj = player.get("sets") or {}
        page_info = sets_obj.get("pageInfo") or {}
        total_pages = int(page_info.get("totalPages") or 1)
        nodes = sets_obj.get("nodes") or []
        if not nodes:
            break
        page_all_older_than_window = True

        for node in nodes:
            sid = node.get("id")
            event = node.get("event") or {}
            videogame = event.get("videogame") or {}
            tournament = event.get("tournament") or {}
            vg_id = videogame.get("id")
            start_at = tournament.get("startAt")

            if sid is None or start_at is None:
                continue
            if int(vg_id or 0) != STARTGG_SMASH_ULTIMATE_ID:
                continue

            start_at_int = int(start_at)
            if start_at_int >= window_start_unix:
                page_all_older_than_window = False
            if start_at_int < window_start_unix or start_at_int > window_end_unix:
                continue

            sid_int = int(sid)
            if sid_int in seen:
                continue
            seen.add(sid_int)
            set_ids.append(sid_int)

        if page_all_older_than_window:
            break
        page += 1

    return set_ids


def get_set_selection_values_for_player(*, set_id: int, player_id: int) -> list[int]:
    query = """
    query SetWithSelections($setId: ID!) {
      set(id: $setId) {
        games {
          selections {
            entrant {
              participants {
                player {
                  id
                }
              }
            }
            selectionValue
          }
        }
      }
    }
    """
    data = startgg_request(query, {"setId": set_id})
    set_obj = data.get("set")
    if not set_obj:
        return []

    values: list[int] = []
    for game in set_obj.get("games") or []:
        for selection in game.get("selections") or []:
            val = selection.get("selectionValue")
            if val is None:
                continue

            entrant = selection.get("entrant") or {}
            participants = entrant.get("participants") or []
            belongs_to_player = any(
                int((p.get("player") or {}).get("id") or -1) == int(player_id) for p in participants
            )
            if not belongs_to_player:
                continue
            values.append(int(val))

    return values


def get_set_selection_values_for_player_batch(
    *,
    set_ids: list[int],
    player_id: int,
    batch_size: int = 12,
) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {int(sid): [] for sid in set_ids}
    if not set_ids:
        return out

    for start in range(0, len(set_ids), batch_size):
        chunk = [int(sid) for sid in set_ids[start : start + batch_size]]

        variables: dict[str, int] = {}
        aliases: list[str] = []
        for idx, sid in enumerate(chunk):
            var = f"setId{idx}"
            alias = f"s{idx}"
            variables[var] = sid
            aliases.append(
                f"""
                {alias}: set(id: ${var}) {{
                  id
                  games {{
                    selections {{
                      entrant {{
                        participants {{
                          player {{
                            id
                          }}
                        }}
                      }}
                      selectionValue
                    }}
                  }}
                }}
                """
            )

        query = (
            "query BatchedSetSelections("
            + ", ".join([f"${k}: ID!" for k in variables])
            + ") {\n"
            + "\n".join(aliases)
            + "\n}"
        )

        data = startgg_request(query, variables)

        for idx, sid in enumerate(chunk):
            set_obj = data.get(f"s{idx}")
            if not set_obj:
                continue
            values: list[int] = []
            for game in set_obj.get("games") or []:
                for selection in game.get("selections") or []:
                    val = selection.get("selectionValue")
                    if val is None:
                        continue
                    entrant = selection.get("entrant") or {}
                    participants = entrant.get("participants") or []
                    belongs_to_player = any(
                        int((p.get("player") or {}).get("id") or -1) == int(player_id) for p in participants
                    )
                    if not belongs_to_player:
                        continue
                    values.append(int(val))
            out[sid] = values

    return out


def _strip_tag_prefix(tag: str) -> str:
    s = str(tag or "").strip()
    if "|" in s:
        s = s.rsplit("|", 1)[-1].strip()
    return s


def _parse_display_score(display_score: str) -> tuple[str, int, str, int] | None:
    raw = str(display_score or "").strip()
    if not raw:
        return None

    # Common non-numeric outcomes are ignored for upset scoring.
    if any(token in raw.upper() for token in ("DQ", "LFF", "WFF")):
        return None

    parts = raw.split(" - ", 1)
    if len(parts) != 2:
        return None

    left = _strip_tag_prefix(parts[0])
    right = _strip_tag_prefix(parts[1])

    left_match = re.match(r"^(?P<tag>.+?)\s+(?P<score>\d+)$", left)
    right_match = re.match(r"^(?P<tag>.+?)\s+(?P<score>\d+)$", right)
    if not left_match or not right_match:
        return None

    left_tag = left_match.group("tag").strip()
    right_tag = right_match.group("tag").strip()
    left_score = int(left_match.group("score"))
    right_score = int(right_match.group("score"))

    if not left_tag or not right_tag:
        return None

    return left_tag, left_score, right_tag, right_score


def get_player_recent_sets_with_results(
    *,
    player_id: int,
    limit: int = 100,
) -> list[dict]:
    # paginate to reach limit
    per_page = max(1, min(int(limit), 50))
    max_pages = max(1, int((int(limit) + per_page - 1) // per_page))
    query = """
    query PlayerSetsForUpsets($playerId: ID!, $perPage: Int!, $page: Int!) {
      player(id: $playerId) {
        sets(perPage: $perPage, page: $page) {
          nodes {
            id
            displayScore
            event {
              videogame {
                id
              }
            }
          }
        }
      }
    }
    """
    out: list[dict] = []
    seen_set_ids: set[int] = set()

    for page in range(1, max_pages + 1):
        data = startgg_request(
            query,
            {
                "playerId": int(player_id),
                "perPage": per_page,
                "page": page,
            },
        )

        player = data.get("player") or {}
        sets_obj = player.get("sets") or {}
        nodes = sets_obj.get("nodes") or []
        if not nodes:
            break

        for node in nodes:
            event = node.get("event") or {}
            videogame = event.get("videogame") or {}
            if int(videogame.get("id") or 0) != STARTGG_SMASH_ULTIMATE_ID:
                continue

            parsed = _parse_display_score(str(node.get("displayScore") or ""))
            if parsed is None:
                continue
            left_tag, left_score, right_tag, right_score = parsed

            if left_score == right_score:
                continue
            winner_tag = left_tag if left_score > right_score else right_tag
            loser_tag = right_tag if left_score > right_score else left_tag

            sid = node.get("id")
            sid_int = int(sid) if sid is not None else None
            if sid_int is not None:
                if sid_int in seen_set_ids:
                    continue
                seen_set_ids.add(sid_int)

            out.append(
                {
                    "set_id": sid_int,
                    "winner_tag": winner_tag,
                    "loser_tag": loser_tag,
                }
            )

            if len(out) >= int(limit):
                return out[: int(limit)]

    return out[: int(limit)]


def get_players_recent_sets_with_results_batch(
    *,
    player_ids: list[int],
    limit_per_player: int = 50,
    page: int = 1,
    batch_size: int = 12,
) -> dict[int, list[dict]]:
    """
    Batch-fetch recent sets (with parsed winner/loser tags) for many players in one StartGG request
    using GraphQL aliases.

    Returns {player_id: [{set_id, winner_tag, loser_tag}, ...]}
    """
    # Keep this low to avoid StartGG GraphQL "query complexity" failures.
    # We still reach `limit_per_player` via pagination across `page_num`.
    per_page = max(1, min(int(limit_per_player), 25))
    max_pages = max(1, int((int(limit_per_player) + per_page - 1) // per_page))

    out: dict[int, list[dict]] = {int(pid): [] for pid in player_ids}
    if not player_ids:
        return out

    query_tpl = """
    query BatchedPlayerSetsForUpsets({vars}) {{
    {aliases}
    }}
    """

    for start in range(0, len(player_ids), int(batch_size)):
        chunk = [int(pid) for pid in player_ids[start : start + int(batch_size)]]
        seen_set_ids_by_pid: dict[int, set[int]] = {pid: set() for pid in chunk}

        alias_blocks: list[str] = []
        var_parts: list[str] = ["$perPage: Int!", "$page: Int!"]
        variables_static: dict[str, int] = {"perPage": per_page, "page": int(page)}

        for idx, pid in enumerate(chunk):
            var_name = f"playerId{idx}"
            alias = f"p{idx}"
            variables_static[var_name] = int(pid)
            var_parts.append(f"${var_name}: ID!")
            alias_blocks.append(
                f"""
                {alias}: player(id: ${var_name}) {{
                  sets(perPage: $perPage, page: $page) {{
                    nodes {{
                      id
                      displayScore
                      event {{
                        videogame {{ id }}
                      }}
                    }}
                  }}
                }}
                """
            )

        query = query_tpl.format(vars=", ".join(var_parts), aliases="\n".join(alias_blocks))

        for page_num in range(int(page), int(page) + max_pages):
            variables: dict[str, int] = dict(variables_static)
            variables["page"] = int(page_num)

            data = startgg_request(query, variables)

            if all(len(out[int(pid)]) >= int(limit_per_player) for pid in chunk):
                break

            for idx, pid in enumerate(chunk):
                if len(out[int(pid)]) >= int(limit_per_player):
                    continue

                player_obj = data.get(f"p{idx}") or {}
                sets_obj = player_obj.get("sets") or {}
                nodes = sets_obj.get("nodes") or []

                for node in nodes:
                    event = node.get("event") or {}
                    videogame = event.get("videogame") or {}
                    if int(videogame.get("id") or 0) != STARTGG_SMASH_ULTIMATE_ID:
                        continue

                    parsed = _parse_display_score(str(node.get("displayScore") or ""))
                    if parsed is None:
                        continue
                    left_tag, left_score, right_tag, right_score = parsed
                    if left_score == right_score:
                        continue
                    winner_tag = left_tag if left_score > right_score else right_tag
                    loser_tag = right_tag if left_score > right_score else left_tag

                    sid = node.get("id")
                    sid_int = int(sid) if sid is not None else None
                    if sid_int is not None:
                        if sid_int in seen_set_ids_by_pid[int(pid)]:
                            continue
                        seen_set_ids_by_pid[int(pid)].add(sid_int)

                    out[int(pid)].append(
                        {
                            "set_id": sid_int,
                            "winner_tag": winner_tag,
                            "loser_tag": loser_tag,
                        }
                    )

                    if len(out[int(pid)]) >= int(limit_per_player):
                        break

    # Cap per player (safety).
    for pid in out:
        out[pid] = out[pid][: int(limit_per_player)]

    return out