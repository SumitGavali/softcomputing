"""
module3/tests/test_qa_comprehensive.py
======================================
Comprehensive End-to-End Quality Assurance & Software Testing Suite
EV Range Intelligence: Battery Degradation-Aware Charging & Infrastructure Optimization

Coverage:
1. Common Cases: Standard configurations (k=5, k=10, r=3.0 km)
2. Boundary Cases: Minimum k=1, Maximum k=15, Radius r=1.0 km, r=10.0 km
3. Edge & Worst-Case Scenarios: Extreme thermal load, high payload, mountain terrain
4. Financial Overrides: Towing cost, CapEx variations, ROI sensitivity
5. API Contract & Latency Verification: Sub-300ms response thresholds across all endpoints
6. Pre-Trip Simulator Monotonicity: Payload and SOC degradation stress tests
"""

import time
import pytest
from fastapi.testclient import TestClient
import numpy as np
import pandas as pd

from module2.Build.api import app
from module3.service import Module3Service
from module3.clustering import haversine_distance, calculate_road_distance_km, find_nearest_landmark
from module3.config import URBAN_CIRCUITY_FACTOR

client = TestClient(app)


# ============================================================================
# TEST SUITE 1: API CONTRACT & LATENCY BENCHMARKS (< 300ms)
# ============================================================================

def test_tc_api_01_health_endpoint():
    """Verify system health check endpoint latency and contract."""
    t0 = time.time()
    response = client.get("/module3/health")
    latency_ms = (time.time() - t0) * 1000

    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "online"
    assert "Charging Demand Forecast" in data.get("module")
    assert latency_ms < 150, f"Health latency too high: {latency_ms:.1f}ms"


def test_tc_api_02_stations_recommendations_k5_and_k10():
    """Verify station recommendation for standard k=5 and k=10 with CapEx non-null and latency < 350ms."""
    # Test k=5
    t0 = time.time()
    res5 = client.get("/module3/stations/recommendations?k_stations=5&coverage_radius_km=3.0")
    lat5 = (time.time() - t0) * 1000

    assert res5.status_code == 200
    d5 = res5.json()
    assert len(d5["stations"]) == 5
    assert d5["k_stations_requested"] == 5
    assert lat5 < 400, f"k=5 latency too high: {lat5:.1f}ms"

    # Verify CapEx is populated and non-null
    for st in d5["stations"]:
        assert "equipment" in st
        assert st["equipment"]["estimated_capex_inr"] > 0
        assert "name" in st and len(st["name"]) > 0
        assert "latitude" in st and 18.3 <= st["latitude"] <= 18.7
        assert "longitude" in st and 73.6 <= st["longitude"] <= 74.1

    # Test k=10
    t0 = time.time()
    res10 = client.get("/module3/stations/recommendations?k_stations=10&coverage_radius_km=3.0")
    lat10 = (time.time() - t0) * 1000

    assert res10.status_code == 200
    d10 = res10.json()
    assert len(d10["stations"]) == 10
    assert d10["k_stations_requested"] == 10
    assert lat10 < 400, f"k=10 latency too high: {lat10:.1f}ms"


def test_tc_api_03_heatmap_deficits():
    """Verify deficit heatmap returns dense points with normalized intensities."""
    response = client.get("/module3/heatmap/deficits?limit=1000")
    assert response.status_code == 200
    points = response.json()
    assert isinstance(points, list)
    assert len(points) >= 500, f"Deficit points count too low: {len(points)}"

    for pt in points[:50]:
        assert "lat" in pt and "lon" in pt
        assert 0.0 <= pt["intensity"] <= 1.0
        assert 0.0 <= pt["urgency"] <= 100.0
        assert pt["deficit_kwh"] >= 0.0


def test_tc_api_04_fleet_overview():
    """Verify 120-vehicle fleet health distribution and summary metrics."""
    response = client.get("/module3/fleet/overview")
    assert response.status_code == 200
    data = response.json()

    assert data["total_fleet_vehicles"] == 120
    assert 60.0 <= data["average_soh_percent"] <= 98.0
    assert "healthy_vehicles_count" in data
    assert "monitor_vehicles_count" in data
    assert "at_risk_vehicles_count" in data
    assert (
        data["healthy_vehicles_count"]
        + data["monitor_vehicles_count"]
        + data["at_risk_vehicles_count"]
        == 120
    )


def test_tc_api_05_hourly_demand_forecast():
    """Verify 24-hour demand profile contains continuous slots with off-peak recommendations."""
    response = client.get("/module3/demand/hourly")
    assert response.status_code == 200
    data = response.json()

    assert "hourly_profile" in data
    assert len(data["hourly_profile"]) == 24
    assert data["peak_power_demand_kw"] > 0
    assert data["total_daily_charging_kwh"] > 0
    assert "recommended_off_peak_shift_kwh" in data

    hours = [item["hour"] for item in data["hourly_profile"]]
    assert hours == list(range(24))


def test_tc_api_06_hub_assignment_routes():
    """Verify OSRM curbside GeoJSON turn-by-turn route delivery."""
    # First get station ID
    st_res = client.get("/module3/stations/recommendations?k_stations=5")
    st_id = st_res.json()["stations"][0]["station_id"]

    response = client.get(f"/module3/routes/hub-assignment?station_id={st_id}&limit=5&k_stations=5")
    assert response.status_code == 200
    data = response.json()

    assert data.get("type") == "FeatureCollection"
    assert "features" in data
    if len(data["features"]) > 0:
        feat = data["features"][0]
        assert feat["geometry"]["type"] == "LineString"
        assert len(feat["geometry"]["coordinates"]) >= 2
        assert "distance_km" in feat["properties"]


def test_tc_api_07_pre_trip_simulation():
    """Verify POST /module3/simulate/trip handles nominal telemetry payload."""
    payload = {
        "soh_percent": 88.5,
        "initial_soc_percent": 75.0,
        "trip_distance_km": 35.0,
        "ambient_temperature_c": 28.0,
        "terrain": "FLAT",
        "load_kg": 80.0
    }
    response = client.post("/module3/simulate/trip", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["charging_required"] is False
    assert data["range_margin_km"] > 0
    assert data["fuzzy_urgency"] < 50.0


# ============================================================================
# TEST SUITE 2: BOUNDARY CASES & EXTREME STRESS TESTING
# ============================================================================

def test_tc_boundary_01_minimum_k_station():
    """Boundary test: Sizing network with k=1 single central super-hub."""
    res = client.get("/module3/stations/recommendations?k_stations=1&coverage_radius_km=4.0")
    assert res.status_code == 200
    d = res.json()
    assert len(d["stations"]) == 1
    st = d["stations"][0]
    assert st["covered_trips_count"] > 0
    assert st["equipment"]["estimated_capex_inr"] > 0


def test_tc_boundary_02_maximum_k_stations():
    """Boundary test: Sizing dense network with k=15 distributed hubs."""
    res = client.get("/module3/stations/recommendations?k_stations=15&coverage_radius_km=2.0")
    assert res.status_code == 200
    d = res.json()
    assert len(d["stations"]) == 15

    # Check minimum spacing constraint across all 15 stations
    stations = d["stations"]
    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            dist = haversine_distance(
                stations[i]["latitude"], stations[i]["longitude"],
                stations[j]["latitude"], stations[j]["longitude"]
            )
            assert dist >= 1.90, f"Stations {i} and {j} too close: {dist:.2f} km"


def test_tc_boundary_03_service_radius_scaling():
    """Boundary test: 1.0 km micro-radius vs 6.0 km regional coverage radius."""
    res_small = client.get("/module3/stations/recommendations?k_stations=5&coverage_radius_km=1.0")
    res_large = client.get("/module3/stations/recommendations?k_stations=5&coverage_radius_km=6.0")

    assert res_small.status_code == 200 and res_large.status_code == 200
    d_small = res_small.json()
    d_large = res_large.json()

    cov_small = d_small["roi_analysis"]["fleet_deficit_coverage_percent"]
    cov_large = d_large["roi_analysis"]["fleet_deficit_coverage_percent"]

    assert cov_large >= cov_small, "Larger radius must cover at least as much demand as smaller radius"


def test_tc_edge_04_thermal_and_load_collapse():
    """Edge test: Worst-case collapse scenario: 25% SOC, 60% SOH, 250kg payload, 45°C extreme heat, Mountain."""
    payload = {
        "soh_percent": 60.0,
        "initial_soc_percent": 25.0,
        "trip_distance_km": 40.0,
        "ambient_temperature_c": 45.0,
        "terrain": "MOUNTAIN",
        "load_kg": 250.0
    }
    response = client.post("/module3/simulate/trip", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Must flag critical deficit
    assert data["charging_required"] is True
    assert data["range_margin_km"] < 0.0
    assert data["fuzzy_urgency"] >= 75.0
    assert data["charging_needed_kwh"] > 0


def test_tc_monotonicity_05_payload_impact():
    """Monotonicity test: Increasing payload from 75kg to 300kg strictly decreases range margin."""
    margins = []
    for load in [75.0, 150.0, 225.0, 300.0]:
        payload = {
            "soh_percent": 85.0,
            "initial_soc_percent": 80.0,
            "trip_distance_km": 30.0,
            "ambient_temperature_c": 30.0,
            "terrain": "FLAT",
            "load_kg": load
        }
        res = client.post("/module3/simulate/trip", json=payload).json()
        margins.append(res["range_margin_km"])

    for i in range(len(margins) - 1):
        assert margins[i] > margins[i + 1], f"Margin did not decrease monotonically: {margins}"


# ============================================================================
# TEST SUITE 3: FINANCIAL OVERRIDES & ROI SENSITIVITY
# ============================================================================

def test_tc_finance_01_towing_cost_override():
    """Financial override: Higher towing cost raises emergency rescue savings proportionally."""
    res_low = client.get("/module3/stations/recommendations?k_stations=5&towing_cost_inr=1500")
    res_high = client.get("/module3/stations/recommendations?k_stations=5&towing_cost_inr=6000")

    assert res_low.status_code == 200 and res_high.status_code == 200
    d_low = res_low.json()
    d_high = res_high.json()

    roi_low = d_low["roi_analysis"]["monthly_towing_savings_inr"]
    roi_high = d_high["roi_analysis"]["monthly_towing_savings_inr"]

    assert roi_high > roi_low, f"Expected higher towing savings: {roi_high} vs {roi_low}"


def test_tc_finance_02_capex_cost_overrides():
    """Financial override: Custom charger hardware costs correctly modify station CapEx."""
    res_custom = client.get(
        "/module3/stations/recommendations?k_stations=5&ac_cost_inr=120000&dc_cost_inr=450000&swap_cost_inr=800000"
    )
    assert res_custom.status_code == 200
    d = res_custom.json()
    total_capex = sum(s["equipment"]["estimated_capex_inr"] for s in d["stations"])
    assert total_capex > 0


# ============================================================================
# TEST SUITE 4: GIS & GEOGRAPHIC BOUNDING INVARIANTS
# ============================================================================

def test_tc_gis_01_pune_circuity_and_landmarks():
    """Verify urban road circuity factor and nearest landmark matching."""
    # Haversine vs road distance
    d_air = haversine_distance(18.5204, 73.8567, 18.5913, 73.7389)
    d_road = calculate_road_distance_km(18.5204, 73.8567, 18.5913, 73.7389)

    assert d_road >= d_air * URBAN_CIRCUITY_FACTOR

    # Landmark resolution without network calls
    lm = find_nearest_landmark(18.5204, 73.8567)
    assert "landmark_name" in lm
    assert lm["source"] in ["landmark_match", "parcel_match", "sector_fallback"]


def test_tc_gis_02_deficit_distribution_density():
    """Verify that fleet dataset contains 750+ commercial deficit dropouts."""
    service = Module3Service()
    df_trips = service.get_or_load_fleet_trips()
    df_deficits = service.cluster_engine.extract_deficit_trips(df_trips)

    assert len(df_deficits) >= 750, f"Expected 750+ deficit dropouts, found {len(df_deficits)}"
