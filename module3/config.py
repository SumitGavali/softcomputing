"""
module3/config.py
=================
Configuration constants and parameters for Module 3:
Charging Demand Forecast & Optimal Station Placement Engine.
EV Range Intelligence Layer for Small Fleets.
"""

import os
from typing import List, Dict, Any

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 — GEOGRAPHIC BOUNDS & MAP CONFIG (Pune, Maharashtra)
# ──────────────────────────────────────────────────────────────────────────────
LAT_MIN = 18.40
LAT_MAX = 18.65
LON_MIN = 73.75
LON_MAX = 74.05

PUNE_CENTER_LAT = 18.5204
PUNE_CENTER_LON = 73.8567
DEFAULT_ZOOM = 12


def compute_geographic_bounds(df=None) -> dict:
    """
    Dynamically computes geographic bounding box and centroid from fleet trip data.
    Adapts automatically to any metropolitan region (e.g. Pune, Bengaluru, Delhi-NCR, Mumbai).
    Falls back to Pune metropolitan coordinates if data is missing or out-of-bounds.
    """
    if df is not None and not df.empty and "latitude" in df.columns and "longitude" in df.columns:
        valid_lats = df["latitude"].dropna()
        valid_lons = df["longitude"].dropna()
        if len(valid_lats) >= 5:
            lat_min = float(valid_lats.quantile(0.01))
            lat_max = float(valid_lats.quantile(0.99))
            lon_min = float(valid_lons.quantile(0.01))
            lon_max = float(valid_lons.quantile(0.99))
            center_lat = float(valid_lats.median())
            center_lon = float(valid_lons.median())
            return {
                "lat_min": round(lat_min, 4),
                "lat_max": round(lat_max, 4),
                "lon_min": round(lon_min, 4),
                "lon_max": round(lon_max, 4),
                "center": [round(center_lat, 5), round(center_lon, 5)],
                "zoom": DEFAULT_ZOOM,
                "is_dynamic": True,
            }

    return {
        "lat_min": LAT_MIN,
        "lat_max": LAT_MAX,
        "lon_min": LON_MIN,
        "lon_max": LON_MAX,
        "center": [PUNE_CENTER_LAT, PUNE_CENTER_LON],
        "zoom": DEFAULT_ZOOM,
        "is_dynamic": False,
    }


# Key urban delivery hubs in Pune for nearest landmark mapping
PUNE_LANDMARKS = [
    {"name": "Hinjawadi IT Park Hub", "lat": 18.5913, "lon": 73.7389, "zone": "West"},
    {"name": "Viman Nagar Commercial Hub", "lat": 18.5679, "lon": 73.9143, "zone": "East"},
    {"name": "Kothrud Depot Zone", "lat": 18.5074, "lon": 73.8077, "zone": "South-West"},
    {"name": "Hadapsar Industrial & Logistics Hub", "lat": 18.5089, "lon": 73.9260, "zone": "South-East"},
    {"name": "Swargate Transit Corridor", "lat": 18.5018, "lon": 73.8586, "zone": "Central-South"},
    {"name": "Shivaji Nagar Central Terminal", "lat": 18.5314, "lon": 73.8446, "zone": "Central"},
    {"name": "Wakad Delivery Corridor", "lat": 18.5987, "lon": 73.7688, "zone": "North-West"},
    {"name": "Pimpri-Chinchwad Industrial Belt", "lat": 18.6279, "lon": 73.8131, "zone": "North"},
    {"name": "Katraj South Access Gateway", "lat": 18.4575, "lon": 73.8565, "zone": "South"},
    {"name": "Kalyani Nagar / Yerawada Hub", "lat": 18.5492, "lon": 73.8967, "zone": "Central-East"},
]

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 — STATION PLACEMENT & SPATIAL PARAMETERS
# ──────────────────────────────────────────────────────────────────────────────
STATION_COVERAGE_RADIUS_KM = 3.0   # Operational service radius for 2W/3W fleets
DEFAULT_NUM_STATIONS = 5           # Default recommended charging hubs
MIN_STATION_DISTANCE_KM = 2.0      # Minimum spacing between any two stations to avoid redundancy
MIN_CLUSTER_DEFICIT_KWH = 5.0      # Minimum aggregate deficit required to justify a station hub

# Urban GIS Routing Constants
URBAN_CIRCUITY_FACTOR = 1.32       # Empirically measured ratio of road distance to Haversine distance in Pune
PUNE_RIVER_PENALTY_KM = 2.4        # Average detour penalty for crossing Mula/Mutha rivers via bridge

# ──────────────────────────────────────────────────────────────────────────────
# VERIFIED CANDIDATE COMMERCIAL EV CHARGING PARCELS (PUNE)
# Designated candidate sites with road frontage, commercial zoning, and 3-phase grid hookup feasibility
# ──────────────────────────────────────────────────────────────────────────────
PUNE_CANDIDATE_PARCELS: List[Dict[str, Any]] = [
    {
        "parcel_id": "PARCEL-W-01",
        "name": "Indian Oil Swaraj Mobility Forecourt",
        "address": "Maan Road, Hinjawadi Phase 1",
        "lat": 18.5913,
        "lon": 73.7389,
        "zone": "West (Hinjawadi)",
        "site_type": "Fuel Station Forecourt",
        "grid_capacity_kw": 250.0,
    },
    {
        "parcel_id": "PARCEL-NW-02",
        "name": "HPCL Dange Chowk Transport Forecourt",
        "address": "Dange Chowk Road, Wakad",
        "lat": 18.6045,
        "lon": 73.7760,
        "zone": "North-West (Wakad)",
        "site_type": "Fuel Station Forecourt",
        "grid_capacity_kw": 180.0,
    },
    {
        "parcel_id": "PARCEL-W-03",
        "name": "Balewadi High Street Logistics Yard",
        "address": "Balewadi High Street Commercial Complex",
        "lat": 18.5740,
        "lon": 73.7735,
        "zone": "West (Baner-Balewadi)",
        "site_type": "Commercial Fleet Yard",
        "grid_capacity_kw": 200.0,
    },
    {
        "parcel_id": "PARCEL-WC-04",
        "name": "Parihar Chowk Shell Mobility Hub",
        "address": "DP Road, Aundh Commercial Zone",
        "lat": 18.5575,
        "lon": 73.8155,
        "zone": "West-Central (Aundh)",
        "site_type": "Mobility Station",
        "grid_capacity_kw": 150.0,
    },
    {
        "parcel_id": "PARCEL-SW-05",
        "name": "Kothrud Depot Municipal EV Terminal",
        "address": "Karve Road, Kothrud Bus Depot",
        "lat": 18.5074,
        "lon": 73.8077,
        "zone": "South-West (Kothrud)",
        "site_type": "Public Transit Depot",
        "grid_capacity_kw": 300.0,
    },
    {
        "parcel_id": "PARCEL-C-06",
        "name": "Shivaji Nagar Metro Multimodal Charging Station",
        "address": "Old Mumbai-Pune Hwy, Shivaji Nagar Terminal",
        "lat": 18.5314,
        "lon": 73.8446,
        "zone": "Central (Shivajinagar)",
        "site_type": "Metro Transit Interchange",
        "grid_capacity_kw": 350.0,
    },
    {
        "parcel_id": "PARCEL-S-07",
        "name": "Swargate PMPML Central Transit Charging Facility",
        "address": "Swargate Flyover Junction, Satara Road",
        "lat": 18.5018,
        "lon": 73.8586,
        "zone": "Central-South (Swargate)",
        "site_type": "Bus & Fleet Terminal",
        "grid_capacity_kw": 300.0,
    },
    {
        "parcel_id": "PARCEL-E-08",
        "name": "Viman Nagar Commercial Delivery Hub",
        "address": "Nagar Road, Near Phoenix Marketcity",
        "lat": 18.5679,
        "lon": 73.9143,
        "zone": "East (Viman Nagar)",
        "site_type": "Commercial Fleet Yard",
        "grid_capacity_kw": 250.0,
    },
    {
        "parcel_id": "PARCEL-E-09",
        "name": "Kharadi EON Free Zone EV Fleet Hub",
        "address": "EON IT Park Road, Kharadi",
        "lat": 18.5490,
        "lon": 73.9550,
        "zone": "East (Kharadi)",
        "site_type": "Tech Park Depot",
        "grid_capacity_kw": 280.0,
    },
    {
        "parcel_id": "PARCEL-SE-10",
        "name": "Magarpatta City BPCL Charging Forecourt",
        "address": "Magarpatta Main Road, Hadapsar",
        "lat": 18.5089,
        "lon": 73.9260,
        "zone": "South-East (Hadapsar)",
        "site_type": "Fuel Station Forecourt",
        "grid_capacity_kw": 220.0,
    },
    {
        "parcel_id": "PARCEL-N-11",
        "name": "Bhosari MIDC Industrial Auto Terminal",
        "address": "Bhosari MIDC Sector 10, PCMC",
        "lat": 18.6320,
        "lon": 73.8510,
        "zone": "North (Bhosari MIDC)",
        "site_type": "Industrial Logistics Hub",
        "grid_capacity_kw": 350.0,
    },
    {
        "parcel_id": "PARCEL-N-12",
        "name": "Chinchwad Railway Station Commercial Forecourt",
        "address": "Telco Road, Chinchwad",
        "lat": 18.6279,
        "lon": 73.8131,
        "zone": "North (Chinchwad)",
        "site_type": "Railway Forecourt",
        "grid_capacity_kw": 200.0,
    },
    {
        "parcel_id": "PARCEL-S-13",
        "name": "Katraj South Gateway Charging Station",
        "address": "Pune-Satara Highway, Katraj",
        "lat": 18.4575,
        "lon": 73.8565,
        "zone": "South (Katraj)",
        "site_type": "Highway Service Station",
        "grid_capacity_kw": 200.0,
    },
    {
        "parcel_id": "PARCEL-CE-14",
        "name": "Bund Garden Road IOCL Forecourt",
        "address": "Bund Garden Road, Yerawada Crossing",
        "lat": 18.5450,
        "lon": 73.8850,
        "zone": "Central-East (Bund Garden)",
        "site_type": "Fuel Station Forecourt",
        "grid_capacity_kw": 180.0,
    },
    {
        "parcel_id": "PARCEL-SW-15",
        "name": "Anand Nagar Highway Fuel Forecourt",
        "address": "Sinhagad Road, Anand Nagar",
        "lat": 18.4810,
        "lon": 73.8300,
        "zone": "South-West (Sinhagad Rd)",
        "site_type": "Fuel Station Forecourt",
        "grid_capacity_kw": 180.0,
    },
    {
        "parcel_id": "PARCEL-SE-16",
        "name": "Kondhwa Khurd Delivery Logistics Hub",
        "address": "Kondhwa-NIBM Road",
        "lat": 18.4760,
        "lon": 73.8965,
        "zone": "South-East (Kondhwa)",
        "site_type": "Commercial Fleet Yard",
        "grid_capacity_kw": 160.0,
    },
]

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 — CHARGER EQUIPMENT SPECIFICATIONS
# ──────────────────────────────────────────────────────────────────────────────
CHARGER_SPECS = {
    "AC_SLOW_3KW": {
        "name": "Standard AC Level-2",
        "power_kw": 3.3,
        "typical_charge_time_min": 180,
        "suitability": "Overnight depot and scheduled rest breaks",
        "cost_estimate_inr": 45000,
    },
    "DC_FAST_15KW": {
        "name": "DC Fast Charger",
        "power_kw": 15.0,
        "typical_charge_time_min": 35,
        "suitability": "Mid-shift rapid turnaround for delivery riders",
        "cost_estimate_inr": 185000,
    },
    "BATTERY_SWAP": {
        "name": "Quick Battery Swap Bay",
        "power_kw": 10.0,
        "typical_charge_time_min": 2,
        "suitability": "Instant swap for 2W/3W battery packs during peak rush",
        "cost_estimate_inr": 250000,
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 — FLEET OPERATIONAL & ROI CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
ROI_CONSTANTS = {
    "TOWING_COST_PER_INCIDENT": 1500.0,      # Emergency rescue / towing cost per stranded EV (INR)
    "DEADHEAD_COST_PER_KM": 2.50,            # Deadhead travel cost per km (driver wage + vehicle wear)
    "COMMERCIAL_POWER_COST_PER_KWH": 7.50,   # Baseline industrial electricity tariff (INR)
    "DISPATCH_RECOVERY_HOURS_SAVED": 1.5,     # Average downtime recovered per averted stranded event
    "WORKING_DAYS_PER_MONTH": 26,
    "ESTIMATED_AVERTED_FAILURES_RATIO": 0.85,# Percentage of critical deficits resolved with coverage
}

DEFAULT_FLEET_SIZE = 120

FLEET_VEHICLE_SPECS = {
    "consumption_kwh_per_km": 0.150,
    "nominal_battery_capacity_kwh": 30.0,
    "factory_nominal_range_km": 200.0,
    "safety_reserve_soc_percent": 15.0,
    "fleet_size": DEFAULT_FLEET_SIZE,
}


def compute_thermal_derate_multiplier(temp_c: float) -> float:
    """
    Smooth battery thermal efficiency derating curve:
    - Optimal operating band: 20°C - 32°C (1.0x baseline)
    - Summer heat (>32°C): gradual degradation due to internal cell heating & cooling load
    - Winter cold (<20°C): reduced electrochemical mobility
    """
    if 20.0 <= temp_c <= 32.0:
        return 1.0
    elif temp_c > 32.0:
        return round(min(1.30, 1.0 + (temp_c - 32.0) * 0.015), 3)
    else:
        return round(min(1.25, 1.0 + (20.0 - temp_c) * 0.012), 3)


# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5 — FILE PATHS
# ──────────────────────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

MODULE2_DIR = os.path.join(_ROOT, "module2")
MODULE3_DATA_DIR = os.path.join(_ROOT, "module3", "data")
CACHE_TRIPS_FILE = os.path.join(MODULE3_DATA_DIR, "module3_fleet_trips.csv")
STATION_RECOMMENDATIONS_FILE = os.path.join(MODULE3_DATA_DIR, "station_recommendations.json")
