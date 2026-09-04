"""
module3/tests/test_module3.py
=============================
Unit and Integration Tests for Module 3:
Charging Demand Forecast & Optimal Station Placement Engine.
"""

import pytest
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from module2.Build.api import app
from module3.clustering import haversine_distance, find_nearest_landmark, DeficitClusterEngine
from module3.optimizer import StationPlacementOptimizer
from module3.demand_forecast import DemandForecaster
from module3.service import Module3Service

client = TestClient(app)


def test_haversine_distance():
    # Same point should be 0.0
    dist_zero = haversine_distance(18.5204, 73.8567, 18.5204, 73.8567)
    assert dist_zero == 0.0

    # Distance between Pune Center and Hinjawadi (~15 km)
    dist_hinjawadi = haversine_distance(18.5204, 73.8567, 18.5913, 73.7389)
    assert 12.0 < dist_hinjawadi < 18.0

    # Symmetry
    assert abs(dist_hinjawadi - haversine_distance(18.5913, 73.7389, 18.5204, 73.8567)) < 1e-5


def test_find_nearest_landmark():
    landmark = find_nearest_landmark(18.5910, 73.7390)
    assert "landmark_name" in landmark
    assert "Hinjawadi" in landmark["landmark_name"]
    assert landmark["distance_km"] < 1.0


def test_deficit_cluster_engine():
    engine = DeficitClusterEngine(eps_km=2.5, min_samples=2)

    # Synthetic sample deficits
    sample_df = pd.DataFrame({
        "trip_id": [f"T-{i}" for i in range(10)],
        "vehicle_id": [f"V-{i}" for i in range(10)],
        "latitude": [18.52, 18.521, 18.522, 18.58, 18.581, 18.582, 18.45, 18.451, 18.62, 18.621],
        "longitude": [73.85, 73.851, 73.852, 73.74, 73.741, 73.742, 73.85, 73.851, 73.81, 73.811],
        "charging_required": [True] * 10,
        "fuzzy_urgency": [85.0] * 10,
        "charging_requirement_kwh": [5.0] * 10,
        "range_margin_km": [-15.0] * 10,
    })

    clusters = engine.cluster_deficits(sample_df)
    assert len(clusters) >= 2
    for c in clusters:
        assert "latitude" in c
        assert "longitude" in c
        assert c["total_deficit_kwh"] > 0
        assert c["trip_count"] >= 2


def test_station_placement_optimizer():
    optimizer = StationPlacementOptimizer(coverage_radius_km=3.0, min_station_distance_km=2.0)

    clusters = [
        {"latitude": 18.52, "longitude": 73.85, "total_deficit_kwh": 150.0},
        {"latitude": 18.521, "longitude": 73.851, "total_deficit_kwh": 140.0},  # Too close to #1
        {"latitude": 18.59, "longitude": 73.74, "total_deficit_kwh": 110.0},  # Far away
        {"latitude": 18.50, "longitude": 73.92, "total_deficit_kwh": 90.0},   # Far away
    ]

    sample_df = pd.DataFrame({
        "trip_id": [f"T-{i}" for i in range(4)],
        "latitude": [18.52, 18.521, 18.59, 18.50],
        "longitude": [73.85, 73.851, 73.74, 73.92],
        "charging_requirement_kwh": [10.0, 10.0, 10.0, 10.0],
        "fuzzy_urgency": [85.0, 80.0, 75.0, 70.0],
        "range_margin_km": [-10.0, -8.0, -5.0, -12.0],
    })

    stations = optimizer.optimize_station_placements(clusters, sample_df, k_stations=3)
    # Station #2 should be skipped due to minimum spacing from #1
    assert len(stations) <= 3
    assert len(stations) >= 2

    # Check minimum distance constraint
    for i in range(len(stations)):
        for j in range(i + 1, len(stations)):
            dist = haversine_distance(
                stations[i]["latitude"], stations[i]["longitude"],
                stations[j]["latitude"], stations[j]["longitude"]
            )
            assert dist >= 1.95  # Within tolerance


def test_fleet_roi_calculations():
    optimizer = StationPlacementOptimizer()
    stations = [{
        "station_id": "CS-01",
        "covered_trips_count": 50,
        "covered_deficit_kwh": 200.0,
        "critical_shortages_covered": 15,
    }]
    df_deficits = pd.DataFrame({"charging_requirement_kwh": [4.0] * 50})

    roi = optimizer.compute_fleet_roi(stations, df_deficits)
    assert roi["monthly_deadhead_savings_inr"] > 0
    assert roi["monthly_towing_savings_inr"] > 0
    assert roi["total_monthly_fleet_savings_inr"] > 0
    assert roi["annualized_fleet_savings_inr"] == roi["total_monthly_fleet_savings_inr"] * 12


def test_demand_forecaster():
    forecaster = DemandForecaster()
    df_trips = pd.DataFrame({
        "trip_energy_demand_kwh": [10.0] * 20,
        "charging_requirement_kwh": [4.0] * 20,
        "charging_required": [True] * 20,
        "fuzzy_urgency": [80.0] * 20,
    })
    result = forecaster.generate_hourly_demand_profile(df_trips, stations=[])
    assert len(result["hourly_profile"]) == 24
    assert result["peak_power_demand_kw"] > 0
    assert result["total_daily_charging_kwh"] > 0


def test_api_health():
    res = client.get("/module3/health")
    assert res.status_code == 200
    assert res.json()["status"] == "online"


def test_api_fleet_overview():
    res = client.get("/module3/fleet/overview")
    assert res.status_code == 200
    data = res.json()
    assert "average_soh_percent" in data
    assert "total_fleet_vehicles" in data


def test_api_station_recommendations():
    res = client.get("/module3/stations/recommendations?k_stations=4&coverage_radius_km=3.0")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["stations"]) <= 4
    assert "roi_analysis" in data


def test_api_hourly_demand():
    res = client.get("/module3/demand/hourly")
    assert res.status_code == 200
    data = res.json()
    assert "hourly_profile" in data
    assert len(data["hourly_profile"]) == 24


def test_api_simulate_trip():
    payload = {
        "trip_distance_km": 35.0,
        "initial_soc_percent": 30.0,
        "soh_percent": 80.0,
        "ambient_temperature_c": 35.0,
        "terrain": "HILLY",
        "load_kg": 180.0,
    }
    res = client.post("/module3/simulate/trip", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "effective_demand_km" in data
    assert "fuzzy_urgency" in data
    assert "recommendation_text" in data
