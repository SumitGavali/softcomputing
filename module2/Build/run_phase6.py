import os
import sys
import time
import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from fastapi import FastAPI
from fastapi.testclient import TestClient
from module2.api import router
from module2.pipeline import RecommendationPipeline
import numpy as np

app = FastAPI(title="Module 2 API")
app.include_router(router)
client = TestClient(app)

pipeline = RecommendationPipeline()

def get_base_request():
    return {
        "trip_id": "test-123",
        "vehicle_id": "URBAN_EV_30",
        "latitude": 18.5,
        "longitude": 73.8,
        "initial_soc_percent": 90.0,
        "trip_distance_km": 5.0,
        "ambient_temperature_c": 25.0,
        "terrain": "FLAT",
        "load_kg": 150.0,
        "battery_telemetry": {
            "discharge_index": 50,
            "ambient_temperature": 25.0,
            "max_temp_reached": 30.0,
            "charge_rate_proxy": 5.0,
            "time_since_reset_cycles": 1.0,
            "internal_resistance_re": 0.05
        }
    }

def test_a_valid_trip():
    req = get_base_request()
    response = client.post("/module2/predict/trip-charging", json=req)
    assert response.status_code == 200
    data = response.json()
    assert "fuzzy_urgency" in data
    print("Test A Passed")

def test_b_invalid_soc():
    req = get_base_request()
    req["initial_soc_percent"] = 150.0  # Invalid > 92
    response = client.post("/module2/predict/trip-charging", json=req)
    assert response.status_code == 422
    print("Test B Passed")

def test_c_invalid_distance():
    req = get_base_request()
    req["trip_distance_km"] = -5.0
    response = client.post("/module2/predict/trip-charging", json=req)
    assert response.status_code == 422
    print("Test C Passed")

def test_d_invalid_coordinates():
    req = get_base_request()
    req["latitude"] = 200.0
    response = client.post("/module2/predict/trip-charging", json=req)
    assert response.status_code == 422
    print("Test D Passed")

def test_e_negative_margin():
    req = get_base_request()
    req["initial_soc_percent"] = 20.0
    req["trip_distance_km"] = 150.0 # Creates negative margin
    response = client.post("/module2/predict/trip-charging", json=req)
    assert response.status_code == 200
    assert response.json()["charging_required"] == True
    print("Test E Passed")

def test_f_positive_margin():
    req = get_base_request()
    response = client.post("/module2/predict/trip-charging", json=req)
    assert response.status_code == 200
    assert response.json()["charging_required"] == False
    print("Test F Passed")

def test_g_full_charge_insufficient():
    req = get_base_request()
    req["trip_distance_km"] = 150.0 
    req["battery_telemetry"]["internal_resistance_re"] = 0.25 # severely degraded
    response = client.post("/module2/predict/trip-charging", json=req)
    assert response.status_code == 200
    # Degraded battery + 150km trip should definitely be insufficient
    assert response.json()["full_charge_sufficient"] == False
    print("Test G Passed")

def test_h_all_fields_present():
    req = get_base_request()
    response = client.post("/module2/predict/trip-charging", json=req)
    assert response.status_code == 200
    data = response.json()
    expected_keys = [
        "trip_id", "vehicle_id", "soh_percent", "estimated_usable_range_km",
        "trip_energy_demand_kwh", "effective_trip_demand_km", "initial_soc_percent",
        "available_range_km", "range_margin_km", "fuzzy_urgency", "charging_required",
        "charging_recommended", "energy_deficit_kwh", "charging_requirement_kwh",
        "recommended_soc_percent", "additional_soc_required", "full_charge_sufficient",
        "recommendation", "latitude", "longitude"
    ]
    for key in expected_keys:
        assert key in data
    print("Test H Passed")

def test_i_api_vs_pipeline_consistency():
    req = get_base_request()
    api_resp = client.post("/module2/predict/trip-charging", json=req).json()
    
    flat_req = req.copy()
    tel = flat_req.pop("battery_telemetry")
    mapping = {
        "discharge_index": "Discharge_Index",
        "ambient_temperature": "Ambient_Temperature",
        "max_temp_reached": "Max_Temp_Reached",
        "charge_rate_proxy": "Charge_Rate_Proxy",
        "time_since_reset_cycles": "Time_Since_Reset_Cycles",
        "internal_resistance_re": "Internal_Resistance_Re"
    }
    for k, v in tel.items():
        if k in mapping:
            flat_req[mapping[k]] = v
        else:
            flat_req[k] = v
            
    pipe_resp = pipeline.process_single(flat_req)
    
    keys_to_check = [
        "soh_percent", "estimated_usable_range_km", "trip_energy_demand_kwh",
        "effective_trip_demand_km", "range_margin_km", "fuzzy_urgency",
        "charging_requirement_kwh", "recommended_soc_percent"
    ]
    
    max_diff = 0.0
    for key in keys_to_check:
        diff = abs(api_resp[key] - pipe_resp[key])
        if diff > max_diff:
            max_diff = diff
    
    assert max_diff < 1e-6
    assert api_resp["full_charge_sufficient"] == pipe_resp["full_charge_sufficient"]
    assert api_resp["recommendation"] == pipe_resp["recommendation"]
    
    print(f"Test I Passed (Max Numerical Difference: {max_diff})")
    return max_diff

def run_latency_test():
    latencies = []
    req = get_base_request()
    print("\nRunning 100-request latency test...")
    for _ in range(100):
        start = time.perf_counter()
        res = client.post("/module2/predict/trip-charging", json=req)
        end = time.perf_counter()
        assert res.status_code == 200
        latencies.append((end - start) * 1000) # ms
    
    print(f"  Mean latency: {np.mean(latencies):.2f} ms")
    print(f"  Median latency: {np.median(latencies):.2f} ms")
    print(f"  P95 latency: {np.percentile(latencies, 95):.2f} ms")
    print(f"  Minimum: {np.min(latencies):.2f} ms")
    print(f"  Maximum: {np.max(latencies):.2f} ms")

if __name__ == "__main__":
    print("--- API VALIDATION ---")
    test_a_valid_trip()
    test_b_invalid_soc()
    test_c_invalid_distance()
    test_d_invalid_coordinates()
    test_e_negative_margin()
    test_f_positive_margin()
    test_g_full_charge_insufficient()
    test_h_all_fields_present()
    test_i_api_vs_pipeline_consistency()
    
    run_latency_test()
    
    health = client.get("/module2/health")
    print(f"\nHealth endpoint status: {health.status_code}, Body: {health.json()}")
