"""
Phase 1 - Step 5: FastAPI Wrapper
------------------------------------
Exposes the trained model as a real API endpoint:
POST /predict/soh
  Input:  battery telemetry (JSON)
  Output: SoH% + estimated usable range

Run with:  uvicorn 05_api:app --reload --port 8000
Test with: curl -X POST http://localhost:8000/predict/soh -H "Content-Type: application/json" -d '{...}'
"""
from fastapi import FastAPI
from pydantic import BaseModel, Field
import joblib
import pandas as pd

from fastapi.middleware.cors import CORSMiddleware
from module2.api import router as module2_router
from module3.api import router as module3_router

app = FastAPI(title="Range Intelligence API - EV Fleet Battery & Station Engine", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(module2_router)
app.include_router(module3_router)

import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_MODEL_PATH = os.path.join(_ROOT, "module1", "soh_random_forest_model.pkl")
if not os.path.isfile(_MODEL_PATH):
    _MODEL_PATH = "soh_random_forest_model.pkl"

# Load the trained model ONCE at startup (not per-request - would be slow)
model = joblib.load(_MODEL_PATH)

# -------------------------------------------------------------
# Define the shape of an incoming request using Pydantic.
# This gives you automatic validation - if a client sends a
# string where a number is expected, FastAPI rejects it before
# your code even runs.
# -------------------------------------------------------------
class BatteryTelemetry(BaseModel):
    # NOTE: bounds below are set from the ACTUAL range seen in training data
    # (NASA PCoE, 32 batteries). Inputs outside these ranges are rejected
    # with a 422 error rather than silently producing an unreliable
    # extrapolated prediction - the model has never seen those conditions.
    discharge_index: int = Field(..., ge=1, le=250,
        description="Cycle count / age of battery in discharges (training range: 1-197)")
    ambient_temperature: float = Field(..., ge=0, le=50,
        description="Ambient temp in Celsius (training range: 4-44C)")
    max_temp_reached: float = Field(..., ge=0, le=80,
        description="Peak temp reached during discharge (training range: 7-70C)")
    charge_rate_proxy: float = Field(..., ge=0, le=30,
        description="Voltage drop rate proxy, V/sec*1000 (training range: 0.2-23.4)")
    time_since_reset_cycles: float = Field(..., ge=0, le=20,
        description="Cycles since last impedance/reset check (training range: 0-13)")
    internal_resistance_re: float = Field(..., ge=0.01, le=0.3,
        description="Internal electrolyte resistance in ohms (training range: 0.028-0.156)")
    rated_range_km: float = Field(300.0, gt=0, le=1000,
        description="Vehicle's rated full-battery range in km")

class SoHPrediction(BaseModel):
    soh_percent: float
    estimated_usable_range_km: float
    model_error_margin_note: str

# -------------------------------------------------------------
# The actual endpoint
# -------------------------------------------------------------
@app.post("/predict/soh", response_model=SoHPrediction)
def predict_soh(telemetry: BatteryTelemetry):
    # Build a single-row dataframe matching the exact column order
    # the model was trained on - order and names MUST match training.
    input_row = pd.DataFrame([{
        "Discharge_Index": telemetry.discharge_index,
        "Ambient_Temperature": telemetry.ambient_temperature,
        "Max_Temp_Reached": telemetry.max_temp_reached,
        "Charge_Rate_Proxy": telemetry.charge_rate_proxy,
        "Time_Since_Reset_Cycles": telemetry.time_since_reset_cycles,
        "Internal_Resistance_Re": telemetry.internal_resistance_re,
    }])

    predicted_soh = model.predict(input_row)[0]  # returns a value between 0 and 1
    soh_percent = round(predicted_soh * 100, 2)

    # Simple range heuristic (documented in project brief as OK for Phase 1):
    # usable_range = rated_range * (SoH/100)
    usable_range = round(telemetry.rated_range_km * predicted_soh, 1)

    return SoHPrediction(
        soh_percent=soh_percent,
        estimated_usable_range_km=usable_range,
        model_error_margin_note="Baseline model MAE ~7%, RMSE ~12% on unseen batteries "
                                 "(worse on extreme hot/cold conditions - see validation report)"
    )

@app.get("/")
def root():
    return {"message": "Battery SoH API is running. POST to /predict/soh"}

@app.get("/health")
def health():
    # Simple liveness/readiness check - confirms the model is loaded
    # and the service can actually serve predictions, not just that
    # the process is running.
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "model_type": type(model).__name__
    }