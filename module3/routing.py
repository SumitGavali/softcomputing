"""
module3/routing.py
==================
OpenStreetMap OSRM Turn-by-Turn Street Routing Engine for Module 3.
Fetches authentic driving routes along roads, bridges, and bypasses,
with LRU caching, timeout guards, and robust offline circuity fallback.
"""

import json
import logging
import math
import urllib.request
from functools import lru_cache
from typing import Dict, Any, List, Tuple, Optional

from module3.config import URBAN_CIRCUITY_FACTOR
from module3.clustering import haversine_distance, calculate_road_distance_km

logger = logging.getLogger(__name__)

OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"


def _generate_curved_road_waypoints(
    lat1: float, lon1: float, lat2: float, lon2: float, num_waypoints: int = 6
) -> List[List[float]]:
    """
    Offline fallback: Generates natural road-following GeoJSON coordinates [lon, lat]
    with realistic urban curve displacement when OSRM routing is unavailable.
    Amplitude scales with route length; longer routes use multi-harmonic curves.
    """
    coords = []
    dx = lon2 - lon1
    dy = lat2 - lat1
    norm = math.sqrt(dx * dx + dy * dy)
    perp_x = -dy / norm if norm > 0 else 0.0
    perp_y = dx / norm if norm > 0 else 0.0

    # Scale amplitude: ~3% of route length, clamped to [0.0002, 0.004] degrees
    # 0.0002° ≈ 22m (minimum visible curve), 0.004° ≈ 440m (maximum urban offset)
    base_amplitude = max(0.0002, min(0.004, norm * 0.03))

    for i in range(num_waypoints + 1):
        t = i / float(num_waypoints)
        # Primary curve (road winding)
        curve = math.sin(t * math.pi) * base_amplitude
        # Secondary harmonic for longer routes (>0.02° ≈ 2.2km) — adds realistic road undulation
        if norm > 0.02:
            curve += math.sin(t * 2.0 * math.pi) * base_amplitude * 0.25
        pt_lat = lat1 + t * (lat2 - lat1) + curve * perp_y
        pt_lon = lon1 + t * (lon2 - lon1) + curve * perp_x
        coords.append([round(pt_lon, 5), round(pt_lat, 5)])

    return coords


@lru_cache(maxsize=1024)
def get_street_route(
    lat1_round: float,
    lon1_round: float,
    lat2_round: float,
    lon2_round: float,
) -> Dict[str, Any]:
    """
    Fetches actual turn-by-turn driving route between two GPS coordinates using OpenStreetMap OSRM.
    Returns GeoJSON coordinates, driving distance in km, and estimated transit duration in minutes.
    Results are cached in-memory for instant sub-millisecond lookups.
    """
    # Round coordinates to ~11 meters to maximize cache hit rate
    url = f"{OSRM_BASE_URL}/{lon1_round},{lat1_round};{lon2_round},{lat2_round}?overview=full&geometries=geojson"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "RangeIntelligence-EVOptimizer/1.0 (fleet-urban-routing)",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=1.8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("code") == "Ok" and data.get("routes"):
                    route = data["routes"][0]
                    dist_km = round(route["distance"] / 1000.0, 2)
                    duration_min = round(route["duration"] / 60.0, 1)
                    geojson_coords = route["geometry"]["coordinates"]  # List of [lon, lat]
                    return {
                        "source": "osrm_live",
                        "distance_km": dist_km,
                        "duration_min": duration_min,
                        "coordinates": geojson_coords,
                    }
    except Exception as e:
        logger.debug("OSRM route fetch failed or timed out: %s; using circuity fallback", str(e))

    # Offline/timeout fallback: realistic circuity-adjusted road geometry
    dist_km = calculate_road_distance_km(lat1_round, lon1_round, lat2_round, lon2_round)
    duration_min = round((dist_km / 28.0) * 60.0, 1)  # Assuming 28 km/h urban average speed
    coords = _generate_curved_road_waypoints(lat1_round, lon1_round, lat2_round, lon2_round)

    return {
        "source": "circuity_model",
        "distance_km": dist_km,
        "duration_min": duration_min,
        "coordinates": coords,
    }


def get_hub_assignment_routes(
    station: Dict[str, Any],
    assigned_points: List[Dict[str, Any]],
    max_routes: int = 15,
) -> Dict[str, Any]:
    """
    Builds a GeoJSON FeatureCollection of turn-by-turn road driving routes
    from the station to its assigned delivery deficit points.
    """
    st_lat = station["latitude"]
    st_lon = station["longitude"]
    station_id = station.get("station_id", "STATION")

    features = []

    # Prioritize critical emergency deficits and highest kWh requirements
    sorted_points = sorted(
        assigned_points,
        key=lambda pt: (pt.get("urgency", 0) >= 80, pt.get("deficit_kwh", 0)),
        reverse=True,
    )[:max_routes]

    for pt in sorted_points:
        p_lat = pt.get("lat") or pt.get("latitude")
        p_lon = pt.get("lon") or pt.get("longitude")
        if not p_lat or not p_lon:
            continue

        route_info = get_street_route(
            round(p_lat, 4),
            round(p_lon, 4),
            round(st_lat, 4),
            round(st_lon, 4),
        )

        urgency = pt.get("urgency", 50)
        is_critical = urgency >= 80

        feature = {
            "type": "Feature",
            "properties": {
                "station_id": station_id,
                "trip_id": pt.get("trip_id", ""),
                "deficit_kwh": pt.get("deficit_kwh", 2.0),
                "urgency": urgency,
                "is_critical": is_critical,
                "distance_km": route_info["distance_km"],
                "duration_min": route_info["duration_min"],
                "routing_source": route_info["source"],
            },
            "geometry": {
                "type": "LineString",
                "coordinates": route_info["coordinates"],
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "station_id": station_id,
        "station_name": station.get("name", ""),
        "total_routes_computed": len(features),
        "features": features,
    }
