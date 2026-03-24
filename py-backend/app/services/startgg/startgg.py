import os
import time
from collections import deque

import requests
from dotenv import load_dotenv

load_dotenv()

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
    """
    Return set ids for a player that are in the time window and Smash Ultimate events.
    Uses paginated player sets and filters by tournament start time + event videogame id.
    """
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
    """
    Return selectionValue entries from every game in a set for the specific player.
    """
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
    """
    Fetch selection values for many sets in batched alias queries.
    Returns {set_id: [selectionValue, ...]} for the provided player.
    """
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