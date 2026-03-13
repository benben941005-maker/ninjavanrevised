"""
Navigation Route
Singapore OneMap API + Google Places for address search and routing
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os

router = APIRouter()

ONEMAP_BASE = "https://www.onemap.gov.sg/api"
GOOGLE_PLACES_BASE = "https://maps.googleapis.com/maps/api/place"

# OneMap token cache
_onemap_token = None
_token_expiry = 0


async def get_onemap_token() -> str:
    """Get or refresh OneMap authentication token"""
    global _onemap_token, _token_expiry
    import time

    if _onemap_token and time.time() < _token_expiry:
        return _onemap_token

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ONEMAP_BASE}/auth/post/getToken",
            json={
                "email": os.environ.get("ONEMAP_EMAIL"),
                "password": os.environ.get("ONEMAP_PASSWORD")
            }
        )
        data = response.json()
        _onemap_token = data["access_token"]
        _token_expiry = time.time() + data.get("expiry_timestamp", 3600)
        return _onemap_token


class AddressResult(BaseModel):
    address: str
    block: Optional[str] = None
    road: Optional[str] = None
    building: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: float
    longitude: float
    source: str = "onemap"


class RouteResult(BaseModel):
    total_time_seconds: int
    total_distance_meters: int
    start_address: str
    end_address: str
    geometry: Optional[str] = None  # Encoded polyline
    steps: List[dict] = []


@router.get("/search", response_model=List[AddressResult])
async def search_address(
    query: str = Query(..., description="Address or postal code to search"),
    limit: int = Query(5, description="Max results to return")
):
    """
    Search for Singapore addresses using OneMap API
    Supports postal codes, block numbers, street names
    """
    try:
        token = await get_onemap_token()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ONEMAP_BASE}/common/elastic/search",
                params={
                    "searchVal": query,
                    "returnGeom": "Y",
                    "getAddrDetails": "Y",
                    "pageNum": 1
                },
                headers={"Authorization": token}
            )
            data = response.json()

        results = []
        for item in data.get("results", [])[:limit]:
            results.append(AddressResult(
                address=item.get("ADDRESS", ""),
                block=item.get("BLK_NO", ""),
                road=item.get("ROAD_NAME", ""),
                building=item.get("BUILDING", ""),
                postal_code=item.get("POSTAL", ""),
                latitude=float(item.get("LATITUDE", 0)),
                longitude=float(item.get("LONGITUDE", 0)),
                source="onemap"
            ))

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Navigation search error: {str(e)}")


@router.get("/route", response_model=RouteResult)
async def get_route(
    start_lat: float = Query(...),
    start_lng: float = Query(...),
    end_lat: float = Query(...),
    end_lng: float = Query(...),
    mode: str = Query("drive", description="drive or walk")
):
    """
    Get route between two coordinates using OneMap Routing API
    """
    try:
        token = await get_onemap_token()

        route_type = "drive" if mode == "drive" else "walk"

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ONEMAP_BASE}/public/routingsvc/route",
                params={
                    "start": f"{start_lat},{start_lng}",
                    "end": f"{end_lat},{end_lng}",
                    "routeType": route_type,
                    "token": token
                }
            )
            data = response.json()

        route_summary = data.get("route_summary", {})

        # Extract turn-by-turn steps
        steps = []
        for leg in data.get("route_instructions", []):
            if isinstance(leg, list) and len(leg) >= 2:
                steps.append({
                    "instruction": leg[0] if leg else "",
                    "distance": leg[1] if len(leg) > 1 else ""
                })

        return RouteResult(
            total_time_seconds=int(route_summary.get("total_time", 0)),
            total_distance_meters=int(route_summary.get("total_distance", 0)),
            start_address=route_summary.get("start_point", ""),
            end_address=route_summary.get("end_point", ""),
            geometry=data.get("route_geometry", ""),
            steps=steps[:20]  # Limit to first 20 steps
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Route error: {str(e)}")


@router.get("/nearby")
async def find_nearby_places(
    lat: float = Query(...),
    lng: float = Query(...),
    place_type: str = Query("parking", description="Type: parking, shelter, atm, food"),
    radius: int = Query(500, description="Search radius in meters")
):
    """
    Find nearby places using Google Places API (parking, shelters, etc.)
    """
    try:
        api_key = os.environ.get("GOOGLE_PLACES_API_KEY")

        type_mapping = {
            "parking": "parking",
            "shelter": "shopping_mall",
            "atm": "atm",
            "food": "restaurant"
        }

        google_type = type_mapping.get(place_type, "point_of_interest")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GOOGLE_PLACES_BASE}/nearbysearch/json",
                params={
                    "location": f"{lat},{lng}",
                    "radius": radius,
                    "type": google_type,
                    "key": api_key
                }
            )
            data = response.json()

        places = []
        for place in data.get("results", [])[:5]:
            places.append({
                "name": place.get("name", ""),
                "address": place.get("vicinity", ""),
                "rating": place.get("rating", None),
                "open_now": place.get("opening_hours", {}).get("open_now", None),
                "latitude": place["geometry"]["location"]["lat"],
                "longitude": place["geometry"]["location"]["lng"]
            })

        return {"places": places, "type": place_type}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Places search error: {str(e)}")
