from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from module2.schemas import TripRequest
from module2.pipeline import RecommendationPipeline

router = APIRouter(
    prefix="/module2",
    tags=["Module 2 - Trip Charging"]
)

pipeline = RecommendationPipeline()

@router.post("/predict/trip-charging", description="Predict trip-level EV charging requirement using Module 1 battery health, energy demand modeling, range margin analysis, fuzzy charging urgency, and the Module 2 recommendation engine.")
def predict_trip_charging(request: TripRequest):
    try:
        # Convert to dictionary and flatten battery_telemetry for process_single
        req_dict = request.model_dump()
        
        flat_req = req_dict.copy()
        if 'battery_telemetry' in flat_req:
            tel = flat_req.pop('battery_telemetry')
            
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
            
        # The API is a thin wrapper over process_single
        result = pipeline.process_single(flat_req)
        
        return result
    except ValueError as e:
        # Catch known value errors from the pipeline (e.g. unknown terrain)
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # Hide full stack traces, provide meaningful message
        raise HTTPException(status_code=500, detail=f"Pipeline calculation failed: {str(e)}")

@router.get("/health")
def health_check():
    return {
        "status": "healthy",
        "module": "Module 2",
        "pipeline": "available"
    }
