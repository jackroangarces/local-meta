from collections.abc import Iterable

from fastapi import APIRouter, HTTPException, Query

from app.services.startgg.startgg import (
    get_upcoming_tournaments_by_state,
    get_upcoming_tournaments_near_location,
)

router = APIRouter(prefix="/tournaments", tags=["tournaments"])

# "state": fetch by one or more US states
# "radius": fetch by geo radius around a lat/lng center
# "hybrid": union of state queries and radius queries
REGION_UPCOMING_CONFIG: dict[str, dict] = {
    "Western Washington": {
        "type": "radius",
        "queries": [
            {"latitude": 47.5, "longitude": -123.0, "radius": "110mi"},
        ],
    },
    "Georgia": {
        "type": "state",
        "states": ["GA"],
    },
    "Pacific Northwest": {
        "type": "hybrid",
        "states": ["WA", "OR", "ID"],
        "queries": [
            # Vancouver, BC
            {"latitude": 49.2827, "longitude": -123.1207, "radius": "60mi"},
        ],
    },
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