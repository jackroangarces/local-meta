from collections.abc import Iterable

from fastapi import APIRouter, HTTPException, Query

from app.services.startgg.startgg import (
    get_upcoming_tournaments_by_state,
    get_upcoming_tournaments_near_location,
)

router = APIRouter(prefix="/tournaments", tags=["tournaments"])

# "state": fetch by one or more US states (addrState on Start.gg)
# "radius": fetch by geo radius around a lat/lng center
# "hybrid": union of state queries and radius queries
#
# Non-US regions use radius (or multiple queries) only. Coordinates are approximate
# population centers; radii are tuned for metro / country coverage without huge overlap.
REGION_UPCOMING_CONFIG: dict[str, dict] = {
    "Alabama": {"type": "state", "states": ["AL"]},
    "Alaska": {"type": "state", "states": ["AK"]},
    "Arizona": {"type": "state", "states": ["AZ"]},
    "Arkansas": {"type": "state", "states": ["AR"]},
    "Austria": {
        "type": "radius",
        "queries": [
            {"latitude": 48.2082, "longitude": 16.3738, "radius": "150mi"},
            {"latitude": 47.8095, "longitude": 13.0550, "radius": "100mi"},
        ],
    },
    "Belgium": {
        "type": "radius",
        "queries": [
            {"latitude": 50.8503, "longitude": 4.3517, "radius": "90mi"},
        ],
    },
    "Canada": {
        "type": "radius",
        "queries": [
            {"latitude": 43.6532, "longitude": -79.3832, "radius": "130mi"},
            {"latitude": 49.2827, "longitude": -123.1207, "radius": "120mi"},
            {"latitude": 45.5017, "longitude": -73.5673, "radius": "250mi"},
            {"latitude": 51.0447, "longitude": -114.0719, "radius": "200mi"},
        ],
    },
    "Chile": {
        "type": "radius",
        "queries": [
            {"latitude": -33.4489, "longitude": -70.6693, "radius": "150mi"},
        ],
    },
    "Colombia": {
        "type": "radius",
        "queries": [
            {"latitude": 4.7110, "longitude": -74.0721, "radius": "150mi"},
            {"latitude": 6.2476, "longitude": -75.5658, "radius": "120mi"},
        ],
    },
    "Colorado": {"type": "state", "states": ["CO"]},
    "Connecticut": {"type": "state", "states": ["CT"]},
    "Delaware": {"type": "state", "states": ["DE"]},
    "Ecuador": {
        "type": "radius",
        "queries": [
            {"latitude": -0.2299, "longitude": -78.5249, "radius": "150mi"},
            {"latitude": -2.1704, "longitude": -79.9224, "radius": "120mi"},
        ],
    },
    "Florida": {"type": "state", "states": ["FL"]},
    "Georgia": {"type": "state", "states": ["GA"]},
    "Germany": {
        "type": "radius",
        "queries": [
            {"latitude": 52.5200, "longitude": 13.4050, "radius": "150mi"},
            {"latitude": 48.1351, "longitude": 11.5820, "radius": "120mi"},
            {"latitude": 53.5511, "longitude": 9.9937, "radius": "100mi"},
        ],
    },
    "Hawaii": {"type": "state", "states": ["HI"]},
    "Illinois": {"type": "state", "states": ["IL"]},
    "Indiana": {"type": "state", "states": ["IN"]},
    "Italy": {
        "type": "radius",
        "queries": [
            {"latitude": 41.9028, "longitude": 12.4964, "radius": "180mi"},
            {"latitude": 45.4642, "longitude": 9.1900, "radius": "140mi"},
        ],
    },
    "Kansas": {"type": "state", "states": ["KS"]},
    "Kentucky": {"type": "state", "states": ["KY"]},
    "Las Vegas": {
        "type": "radius",
        "queries": [
            {"latitude": 36.1699, "longitude": -115.1398, "radius": "120mi"},
        ],
    },
    "London": {
        "type": "radius",
        "queries": [
            {"latitude": 51.5074, "longitude": -0.1278, "radius": "80mi"},
        ],
    },
    "Louisiana": {"type": "state", "states": ["LA"]},
    "Maine": {"type": "state", "states": ["ME"]},
    "Massachusetts": {"type": "state", "states": ["MA"]},
    "Mexico": {
        "type": "radius",
        "queries": [
            {"latitude": 19.4326, "longitude": -99.1332, "radius": "200mi"},
            {"latitude": 20.6597, "longitude": -103.3496, "radius": "150mi"},
            {"latitude": 25.6866, "longitude": -100.3161, "radius": "150mi"},
        ],
    },
    "Mexico City": {
        "type": "radius",
        "queries": [
            {"latitude": 19.4326, "longitude": -99.1332, "radius": "100mi"},
        ],
    },
    "Michigan": {"type": "state", "states": ["MI"]},
    "Midwest": {
        "type": "state",
        "states": [
            "IL",
            "IN",
            "IA",
            "KS",
            "MI",
            "MN",
            "MO",
            "NE",
            "ND",
            "OH",
            "SD",
            "WI",
        ],
    },
    "Minnesota": {"type": "state", "states": ["MN"]},
    "Mississippi": {"type": "state", "states": ["MS"]},
    "Missouri": {"type": "state", "states": ["MO"]},
    "Nebraska": {"type": "state", "states": ["NE"]},
    "Norcal": {
        "type": "radius",
        "queries": [
            {"latitude": 37.7749, "longitude": -122.4194, "radius": "180mi"},
            {"latitude": 38.5816, "longitude": -121.4944, "radius": "160mi"},
        ],
    },
    "Nordics": {
        "type": "radius",
        "queries": [
            {"latitude": 59.3293, "longitude": 18.0686, "radius": "140mi"},
            {"latitude": 59.9139, "longitude": 10.7522, "radius": "150mi"},
            {"latitude": 55.6761, "longitude": 12.5683, "radius": "120mi"},
            {"latitude": 60.1699, "longitude": 24.9384, "radius": "150mi"},
        ],
    },
    "North Carolina": {"type": "state", "states": ["NC"]},
    "Ohio": {"type": "state", "states": ["OH"]},
    "Oregon": {"type": "state", "states": ["OR"]},
    "Pacific Northwest": {
        "type": "hybrid",
        "states": ["WA", "OR", "ID"],
        "queries": [
            {"latitude": 49.2827, "longitude": -123.1207, "radius": "60mi"},
        ],
    },
    "Philadelphia": {
        "type": "radius",
        "queries": [
            {"latitude": 39.9526, "longitude": -75.1652, "radius": "70mi"},
        ],
    },
    "Quebec": {
        "type": "radius",
        "queries": [
            {"latitude": 45.5017, "longitude": -73.5673, "radius": "220mi"},
            {"latitude": 46.8139, "longitude": -71.2080, "radius": "200mi"},
        ],
    },
    "Reno": {
        "type": "radius",
        "queries": [
            {"latitude": 39.5296, "longitude": -119.8138, "radius": "120mi"},
        ],
    },
    "San Diego": {
        "type": "radius",
        "queries": [
            {"latitude": 32.7157, "longitude": -117.1611, "radius": "60mi"},
        ],
    },
    "Scotland": {
        "type": "radius",
        "queries": [
            {"latitude": 55.9533, "longitude": -3.1883, "radius": "120mi"},
            {"latitude": 55.8642, "longitude": -4.2518, "radius": "80mi"},
        ],
    },
    "Socal": {
        "type": "radius",
        "queries": [
            {"latitude": 34.0522, "longitude": -118.2437, "radius": "110mi"},
            {"latitude": 32.7157, "longitude": -117.1611, "radius": "60mi"},
        ],
    },
    "Spain": {
        "type": "radius",
        "queries": [
            {"latitude": 40.4168, "longitude": -3.7038, "radius": "200mi"},
            {"latitude": 41.3851, "longitude": 2.1734, "radius": "150mi"},
        ],
    },
    "Switzerland": {
        "type": "radius",
        "queries": [
            {"latitude": 47.3769, "longitude": 8.5417, "radius": "100mi"},
            {"latitude": 46.2044, "longitude": 6.1432, "radius": "90mi"},
        ],
    },
    "Tennessee": {"type": "state", "states": ["TN"]},
    "Texas": {"type": "state", "states": ["TX"]},
    "The Netherlands": {
        "type": "radius",
        "queries": [
            {"latitude": 52.3676, "longitude": 4.9041, "radius": "90mi"},
        ],
    },
    "Tijuana": {
        "type": "radius",
        "queries": [
            {"latitude": 32.5149, "longitude": -117.0382, "radius": "50mi"},
        ],
    },
    "Upstate New York": {
        "type": "radius",
        "queries": [
            {"latitude": 42.6526, "longitude": -73.7562, "radius": "140mi"},
            {"latitude": 42.8864, "longitude": -78.8784, "radius": "130mi"},
            {"latitude": 43.0481, "longitude": -76.1474, "radius": "90mi"},
        ],
    },
    "Utah": {"type": "state", "states": ["UT"]},
    "Vermont": {"type": "state", "states": ["VT"]},
    "Virginia": {"type": "state", "states": ["VA"]},
    "West Florida": {
        "type": "radius",
        "queries": [
            {"latitude": 27.9506, "longitude": -82.4572, "radius": "150mi"},
            {"latitude": 30.4213, "longitude": -87.2169, "radius": "120mi"},
        ],
    },
    "Western Washington": {
        "type": "radius",
        "queries": [
            {"latitude": 47.5, "longitude": -123.0, "radius": "110mi"},
        ],
    },
    "Wisconsin": {"type": "state", "states": ["WI"]},
}


def _normalize_tournament_rows(rows: Iterable[dict]) -> list[dict]:
    out: list[dict] = []
    for t in rows:
        slug = t.get("slug")
        out.append(
            {
                "id": int(t.get("id")) if t.get("id") is not None else None,
                "name": str(t.get("name") or "Untitled tournament"),
                "city": t.get("city"),
                "addr_state": t.get("addrState"),
                "start_at": int(t.get("startAt")) if t.get("startAt") is not None else None,
                "slug": slug,
                "url": f"https://www.start.gg/{slug}" if slug else None,
            }
        )
    return out


def _sort_and_dedupe_tournaments(rows: Iterable[dict]) -> list[dict]:
    normalized = _normalize_tournament_rows(rows)

    # De-dupe by tournament id when available, otherwise by slug/name fallback.
    deduped: dict[str, dict] = {}
    for t in normalized:
        key = (
            f"id:{t['id']}"
            if t.get("id") is not None
            else f"slug:{t.get('slug') or ''}|name:{t.get('name') or ''}"
        )
        deduped[key] = t

    return sorted(
        deduped.values(),
        key=lambda t: (
            t.get("start_at") is None,
            t.get("start_at") or 0,
            str(t.get("name") or ""),
        ),
    )


@router.get("/nearby")
def nearby_tournaments(
    lat: float = Query(...),
    lng: float = Query(...),
    radius: str = Query("50mi"),
    per_page: int = Query(10, ge=1, le=100),
):
    tournaments = get_upcoming_tournaments_near_location(
        latitude=lat,
        longitude=lng,
        radius=radius,
        per_page=per_page,
    )
    return {"tournaments": _sort_and_dedupe_tournaments(tournaments)}


@router.get("/by-state")
def tournaments_by_state(
    state: str = Query(..., min_length=2, max_length=2),
    per_page: int = Query(10, ge=1, le=100),
):
    tournaments = get_upcoming_tournaments_by_state(
        state=state.upper(),
        per_page=per_page,
    )
    return {"tournaments": _sort_and_dedupe_tournaments(tournaments)}


@router.get("/upcoming-events")
def upcoming_events_for_region(
    region_name: str = Query(..., description="Region name from UI dropdown"),
    per_source_limit: int = Query(12, ge=1, le=100),
    limit: int = Query(20, ge=1, le=100),
):
    config = REGION_UPCOMING_CONFIG.get(region_name)
    if config is None:
        raise HTTPException(status_code=400, detail=f"No upcoming-events config for region: {region_name}")

    collected: list[dict] = []
    strategy = config.get("type")

    if strategy in {"state", "hybrid"}:
        for state in config.get("states", []):
            collected.extend(
                get_upcoming_tournaments_by_state(
                    state=state,
                    per_page=per_source_limit,
                )
            )

    if strategy in {"radius", "hybrid"}:
        for q in config.get("queries", []):
            collected.extend(
                get_upcoming_tournaments_near_location(
                    latitude=float(q["latitude"]),
                    longitude=float(q["longitude"]),
                    radius=str(q.get("radius", "50mi")),
                    per_page=per_source_limit,
                )
            )

    tournaments = _sort_and_dedupe_tournaments(collected)[:limit]
    return {"tournaments": tournaments}