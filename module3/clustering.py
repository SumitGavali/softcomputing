"""
module3/clustering.py
=====================
Spatial Deficit Clustering Engine for Module 3.
Groups fleet battery deficits, range margin shortages, and high charging urgency events
into dense spatial clusters to identify critical charging hub hotspots.
"""

import math
from typing import List, Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN, KMeans
try:
    import skfuzzy as fuzz
    HAS_SKFUZZY = True
except ImportError:
    HAS_SKFUZZY = False

from module3.config import (
    STATION_COVERAGE_RADIUS_KM,
    PUNE_LANDMARKS,
    MIN_CLUSTER_DEFICIT_KWH,
    URBAN_CIRCUITY_FACTOR,
    PUNE_RIVER_PENALTY_KM,
)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth in kilometers.
    """
    R = 6371.0  # Earth's radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def is_cross_river_route(lat1: float, lon1: float, lat2: float, lon2: float) -> bool:
    """
    Topological GIS check: Detects whether a straight-line route crosses the
    Mula or Mutha river corridors, requiring an unavoidable detour via a bridge.
    Models both rivers as multi-segment polylines through Pune.
    """
    # Mula river: flows W→E through Aundh/Baner area then turns SE toward confluence
    # Mutha river: flows NW→SE through Kothrud/Deccan then meets Mula at Sangam Bridge
    # Combined: flows NE from Sangam through Yerawada/Bund Garden
    _RIVER_SEGMENTS = [
        # Mula: Baner → Aundh → Sangvi → near Sangam
        ((18.562, 73.792), (18.548, 73.818)),
        ((18.548, 73.818), (18.535, 73.845)),
        ((18.535, 73.845), (18.527, 73.858)),
        # Mutha: Kothrud → Deccan → Sangam
        ((18.505, 73.808), (18.510, 73.832)),
        ((18.510, 73.832), (18.518, 73.852)),
        ((18.518, 73.852), (18.527, 73.858)),
        # Combined downstream: Sangam → Bund Garden → Yerawada
        ((18.527, 73.858), (18.538, 73.880)),
        ((18.538, 73.880), (18.548, 73.900)),
        ((18.548, 73.900), (18.555, 73.920)),
    ]

    def _segments_intersect(p1, p2, p3, p4):
        """Returns True if segment p1→p2 crosses segment p3→p4."""
        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        d1 = cross(p3, p4, p1)
        d2 = cross(p3, p4, p2)
        d3 = cross(p1, p2, p3)
        d4 = cross(p1, p2, p4)

        if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
           ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
            return True
        return False

    route_p1 = (lat1, lon1)
    route_p2 = (lat2, lon2)
    for seg_start, seg_end in _RIVER_SEGMENTS:
        if _segments_intersect(route_p1, route_p2, seg_start, seg_end):
            return True
    return False


def calculate_road_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculates realistic urban driving distance along the road network.
    Incorporates the empirical Pune Urban Circuity Factor (tau = 1.32) and bridge detour penalties.
    """
    d_air = haversine_distance(lat1, lon1, lat2, lon2)
    d_road = d_air * URBAN_CIRCUITY_FACTOR
    if is_cross_river_route(lat1, lon1, lat2, lon2):
        d_road += PUNE_RIVER_PENALTY_KM
    return round(d_road, 2)


import urllib.request
import json
from functools import lru_cache


@lru_cache(maxsize=256)
def _reverse_geocode_nominatim(lat_round: float, lon_round: float) -> Optional[Dict[str, str]]:
    """
    Reverse geocodes coordinate via OpenStreetMap Nominatim with tight timeout.
    Returns human-friendly locality/neighbourhood name and district.
    """
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat_round}&lon={lon_round}&format=json&zoom=14&addressdetails=1"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "RangeIntelligence-EVFleet/1.0 (fleet-placement-optimizer)"}
        )
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                addr = data.get("address", {})
                name = (
                    addr.get("suburb")
                    or addr.get("neighbourhood")
                    or addr.get("commercial")
                    or addr.get("industrial")
                    or addr.get("residential")
                    or addr.get("city_district")
                    or addr.get("town")
                    or addr.get("city")
                )
                district = addr.get("city") or addr.get("state_district") or "Metro"
                if name:
                    return {"landmark_name": f"{name} Hub", "zone": district}
    except Exception:
        pass
    return None


def find_nearest_landmark(lat: float, lon: float) -> Dict[str, Any]:
    """
    Dynamically identifies human-readable station and zone naming:
    1. Fast-path reverse geocoding via Nominatim (with LRU caching).
    2. Local landmark library (if coordinates are within 8 km of known hubs).
    3. Cardinal sector geometric fallback (for arbitrary cities or offline operation).
    """
    # 1. Attempt dynamic geocoding
    geo_res = _reverse_geocode_nominatim(round(lat, 3), round(lon, 3))
    if geo_res:
        return {
            "landmark_name": geo_res["landmark_name"],
            "zone": geo_res["zone"],
            "distance_km": 0.0,
            "source": "geocoded",
        }

    # 2. Check predefined landmarks
    closest = None
    min_dist = float("inf")
    for lm in PUNE_LANDMARKS:
        dist = haversine_distance(lat, lon, lm["lat"], lm["lon"])
        if dist < min_dist:
            min_dist = dist
            closest = lm

    if closest and min_dist <= 8.0:
        return {
            "landmark_name": closest["name"],
            "zone": closest["zone"],
            "distance_km": round(min_dist, 2),
            "source": "landmark_match",
        }

    # 3. Geometric sector fallback for arbitrary coordinates
    # Using 18.52 / 73.85 reference or generic quadrant
    d_lat = lat - 18.5204
    d_lon = lon - 73.8567
    ns = "North" if d_lat >= 0 else "South"
    ew = "East" if d_lon >= 0 else "West"
    sector = f"{ns}-{ew}" if abs(d_lat) > 0.02 and abs(d_lon) > 0.02 else (ns if abs(d_lat) >= abs(d_lon) else ew)

    return {
        "landmark_name": f"{sector} Transit Sector",
        "zone": f"{sector} Corridor",
        "distance_km": round(min_dist, 2) if closest else 0.0,
        "source": "sector_fallback",
    }



class DeficitClusterEngine:
    """
    Extracts fleet charging shortages and groups them using spatial clustering algorithms.
    """

    def __init__(
        self,
        eps_km: float = 2.0,
        min_samples: int = 5,
        coverage_radius_km: float = STATION_COVERAGE_RADIUS_KM,
    ):
        self.eps_km = eps_km
        self.min_samples = min_samples
        self.coverage_radius_km = coverage_radius_km

    def extract_deficit_trips(self, df_trips: pd.DataFrame) -> pd.DataFrame:
        """
        Filter trips that experienced battery deficit or high charging urgency.
        """
        if df_trips.empty:
            return pd.DataFrame()

        # Conditions indicating charging need
        cond_charging_req = df_trips.get("charging_required", pd.Series([False] * len(df_trips))) == True
        cond_urgency = df_trips.get("fuzzy_urgency", pd.Series([0.0] * len(df_trips))) >= 60.0
        cond_margin = df_trips.get("range_margin_km", pd.Series([0.0] * len(df_trips))) < 0.0

        deficit_mask = cond_charging_req | cond_urgency | cond_margin
        df_deficits = df_trips[deficit_mask].copy()

        # Ensure fallback for required columns
        if "charging_requirement_kwh" not in df_deficits.columns:
            df_deficits["charging_requirement_kwh"] = df_deficits.get(
                "trip_energy_demand_kwh", 5.0
            ) * 0.5

        if "fuzzy_urgency" not in df_deficits.columns:
            df_deficits["fuzzy_urgency"] = 75.0

        return df_deficits

    def cluster_deficits(self, df_trips: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Identifies spatial clusters of battery deficits using DBSCAN and calculates cluster metrics.
        """
        df_deficits = self.extract_deficit_trips(df_trips)
        if df_deficits.empty or len(df_deficits) < 3:
            return []

        coords = df_deficits[["latitude", "longitude"]].values
        # Convert eps from km to radians for haversine metric in DBSCAN
        kms_per_radian = 6371.0088
        epsilon = self.eps_km / kms_per_radian

        db = DBSCAN(
            eps=epsilon,
            min_samples=self.min_samples,
            metric="haversine",
        )
        # DBSCAN expects coordinates in radians (lat, lon)
        labels = db.fit_predict(np.radians(coords))
        df_deficits = df_deficits.copy()
        df_deficits["cluster_label"] = labels

        clusters = []
        unique_labels = set(labels)
        # Exclude noise (-1) from primary clusters
        valid_labels = [lbl for lbl in unique_labels if lbl != -1]

        for lbl in valid_labels:
            cluster_rows = df_deficits[df_deficits["cluster_label"] == lbl]
            c_lat = float(cluster_rows["latitude"].mean())
            c_lon = float(cluster_rows["longitude"].mean())
            total_kwh = float(cluster_rows["charging_requirement_kwh"].sum())
            avg_urgency = float(cluster_rows["fuzzy_urgency"].mean())
            avg_soh = float(cluster_rows.get("soh_percent", pd.Series([80.0])).mean())
            trip_count = int(len(cluster_rows))

            # Calculate cluster radius (max distance of points from centroid)
            distances = [
                haversine_distance(c_lat, c_lon, r["latitude"], r["longitude"])
                for _, r in cluster_rows.iterrows()
            ]
            radius_km = max(distances) if distances else 1.0

            landmark_info = find_nearest_landmark(c_lat, c_lon)

            clusters.append({
                "cluster_id": int(lbl),
                "latitude": round(c_lat, 5),
                "longitude": round(c_lon, 5),
                "trip_count": trip_count,
                "total_deficit_kwh": round(total_kwh, 2),
                "avg_urgency": round(avg_urgency, 1),
                "avg_soh_percent": round(avg_soh, 1),
                "radius_km": round(radius_km, 2),
                "nearest_landmark": landmark_info["landmark_name"],
                "zone": landmark_info["zone"],
                "trips": cluster_rows[["trip_id", "vehicle_id", "latitude", "longitude", "charging_requirement_kwh", "fuzzy_urgency"]].to_dict(orient="records") if "trip_id" in cluster_rows else [],
            })

        # If DBSCAN produces fewer than 3 clusters on large distributed spatial datasets,
        # supplement with K-Means centroids on the deficit points to ensure comprehensive network coverage
        if len(clusters) < 3 and len(coords) >= 20:
            n_kmeans = min(8, len(coords))
            km = KMeans(n_clusters=n_kmeans, random_state=42, n_init=10)
            km_labels = km.fit_predict(coords)
            df_deficits = df_deficits.copy()
            df_deficits["cluster_label"] = km_labels

            clusters = []
            for lbl in range(n_kmeans):
                cluster_rows = df_deficits[df_deficits["cluster_label"] == lbl]
                if cluster_rows.empty:
                    continue
                c_lat = float(cluster_rows["latitude"].mean())
                c_lon = float(cluster_rows["longitude"].mean())
                total_kwh = float(cluster_rows["charging_requirement_kwh"].sum())
                avg_urgency = float(cluster_rows["fuzzy_urgency"].mean())
                avg_soh = float(cluster_rows.get("soh_percent", pd.Series([80.0])).mean())
                trip_count = int(len(cluster_rows))

                distances = [
                    haversine_distance(c_lat, c_lon, r["latitude"], r["longitude"])
                    for _, r in cluster_rows.iterrows()
                ]
                radius_km = max(distances) if distances else 1.0
                landmark_info = find_nearest_landmark(c_lat, c_lon)

                clusters.append({
                    "cluster_id": int(lbl),
                    "latitude": round(c_lat, 5),
                    "longitude": round(c_lon, 5),
                    "trip_count": trip_count,
                    "total_deficit_kwh": round(total_kwh, 2),
                    "avg_urgency": round(avg_urgency, 1),
                    "avg_soh_percent": round(avg_soh, 1),
                    "radius_km": round(radius_km, 2),
                    "nearest_landmark": landmark_info["landmark_name"],
                    "zone": landmark_info["zone"],
                })

        # Sort clusters by total deficit kWh descending
        clusters.sort(key=lambda x: x["total_deficit_kwh"], reverse=True)
        return clusters

    def compute_fuzzy_memberships(
        self, points: np.ndarray, centroids: np.ndarray, m: float = 2.0
    ) -> np.ndarray:
        """
        Soft Computing Fuzzy C-Means (FCM) partition matrix calculation:
        Computes soft degree of membership u_ij for each point i to station centroid j.
        """
        num_points = len(points)
        num_centroids = len(centroids)
        if num_centroids == 0 or num_points == 0:
            return np.empty((0, 0))

        memberships = np.zeros((num_points, num_centroids))

        for i in range(num_points):
            p_lat, p_lon = points[i]
            dists = [
                max(haversine_distance(p_lat, p_lon, c[0], c[1]), 0.05)
                for c in centroids
            ]
            # FCM standard membership equation
            denom_sum = sum((1.0 / (d ** (2.0 / (m - 1.0)))) for d in dists)
            for j in range(num_centroids):
                memberships[i, j] = (1.0 / (dists[j] ** (2.0 / (m - 1.0)))) / denom_sum

        return memberships
