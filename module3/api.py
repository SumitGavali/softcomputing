"""
module3/api.py
==============
FastAPI Endpoints for Module 3:
Charging Demand Forecast & Optimal Station Placement Engine.
"""

from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field

from module3.service import Module3Service
from module3.config import FLEET_VEHICLE_SPECS, compute_thermal_derate_multiplier

router = APIRouter(prefix="/module3", tags=["Module 3 - Station Placement & Fleet Intelligence"])
service = Module3Service()


class PlacementSimulationRequest(BaseModel):
    k_stations: int = Field(5, ge=1, le=15, description="Number of candidate charging stations to place")
    coverage_radius_km: float = Field(3.0, ge=1.0, le=10.0, description="Service coverage radius in km")
    towing_cost_inr: Optional[float] = Field(None, ge=500.0, le=10000.0, description="Emergency towing rescue cost per incident")
    deadhead_cost_per_km: Optional[float] = Field(None, ge=0.5, le=20.0, description="Deadhead cost per km")
    ac_cost_inr: Optional[float] = Field(None, ge=10000.0, le=200000.0, description="AC Slow 3.3kW charger unit capex")
    dc_cost_inr: Optional[float] = Field(None, ge=50000.0, le=1000000.0, description="DC Fast 15kW charger unit capex")
    swap_cost_inr: Optional[float] = Field(None, ge=50000.0, le=1000000.0, description="Battery swap bay unit capex")


class PreTripSimRequest(BaseModel):
    trip_distance_km: float = Field(25.0, ge=1.0, le=150.0)
    initial_soc_percent: float = Field(50.0, ge=10.0, le=100.0)
    soh_percent: float = Field(82.0, ge=40.0, le=100.0)
    ambient_temperature_c: float = Field(30.0, ge=5.0, le=50.0)
    terrain: str = Field("FLAT", description="FLAT, HILLY, or MOUNTAIN")
    load_kg: float = Field(150.0, ge=70.0, le=350.0)


@router.get("/health")
def health_check():
    return {
        "status": "online",
        "module": "Module 3 - Charging Demand Forecast & Station Placement",
        "version": "1.0.0",
    }


@router.get("/fleet/overview")
def get_fleet_overview():
    """
    Returns fleet health distribution, average SoH, at-risk vehicle count and details.
    """
    try:
        return service.get_fleet_overview_metrics()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stations/recommendations")
def get_station_recommendations(
    k_stations: int = Query(5, ge=1, le=15, description="Target number of stations to place"),
    coverage_radius_km: float = Query(3.0, ge=1.0, le=10.0, description="Service radius in km"),
    towing_cost_inr: Optional[float] = Query(None, description="Custom towing rescue cost per event in INR"),
    deadhead_cost_per_km: Optional[float] = Query(None, description="Custom deadhead transit cost per km in INR"),
    ac_cost_inr: Optional[float] = Query(None, description="Custom AC Slow charger unit capex in INR"),
    dc_cost_inr: Optional[float] = Query(None, description="Custom DC Fast charger unit capex in INR"),
    swap_cost_inr: Optional[float] = Query(None, description="Custom Battery Swap bay capex in INR"),
):
    """
    Computes optimal station placements, port allocations, and fleet ROI impact.
    Supports dynamic geographic centering and custom capex / operational cost rates.
    """
    try:
        return service.get_station_recommendations(
            k_stations=k_stations,
            coverage_radius_km=coverage_radius_km,
            towing_cost_inr=towing_cost_inr,
            deadhead_cost_per_km=deadhead_cost_per_km,
            ac_cost_inr=ac_cost_inr,
            dc_cost_inr=dc_cost_inr,
            swap_cost_inr=swap_cost_inr,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/heatmap/deficits")
def get_deficit_heatmap(limit: int = Query(1500, ge=1, le=5000)):
    """
    Returns geolocated deficit points with intensity weights for map overlays.
    """
    try:
        return service.get_deficit_heatmap_points(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/demand/hourly")
def get_hourly_demand():
    """
    Returns 24-hour fleet charging load profile, peak power demand, and recommended off-peak shift.
    """
    try:
        return service.get_hourly_demand_forecast()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/routes/hub-assignment")
def get_hub_routes(
    station_id: str = "CS-OPT-01",
    limit: int = 15,
    k_stations: int = Query(5, ge=1, le=15, description="Must match the k used in station recommendations"),
    coverage_radius_km: float = Query(3.0, ge=1.0, le=10.0, description="Must match the radius used in station recommendations"),
):
    """
    Returns authentic turn-by-turn GeoJSON road driving routes from OpenStreetMap OSRM
    connecting the specified station to its assigned delivery deficit points across Pune streets and bridges.
    """
    try:
        return service.get_station_road_routes(
            station_id=station_id,
            limit=limit,
            k_stations=k_stations,
            coverage_radius_km=coverage_radius_km,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/simulate/placement")
def simulate_placement(req: PlacementSimulationRequest):
    """
    Interactive placement simulation with custom k_stations, coverage radius, and custom financial parameters.
    """
    try:
        return service.get_station_recommendations(
            k_stations=req.k_stations,
            coverage_radius_km=req.coverage_radius_km,
            towing_cost_inr=req.towing_cost_inr,
            deadhead_cost_per_km=req.deadhead_cost_per_km,
            ac_cost_inr=req.ac_cost_inr,
            dc_cost_inr=req.dc_cost_inr,
            swap_cost_inr=req.swap_cost_inr,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



_m2_pipeline = None


def _get_m2_pipeline():
    global _m2_pipeline
    if _m2_pipeline is None:
        try:
            from module2.pipeline import RecommendationPipeline
            _m2_pipeline = RecommendationPipeline()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Module 2 pipeline not initialized: %s", e)
    return _m2_pipeline


@router.post("/simulate/trip")
def simulate_trip(req: PreTripSimRequest):
    """
    Evaluates pre-trip energy demand, range margin, and fuzzy urgency
    via Module 2's RecommendationPipeline and Soft Computing Fuzzy Inference Engine.
    """
    pipeline = _get_m2_pipeline()
    if pipeline is not None:
        try:
            from module2.config import RATED_RANGE_KM
            soh = float(req.soh_percent)
            trip_dict = {
                "trip_distance_km": float(req.trip_distance_km),
                "initial_soc_percent": float(req.initial_soc_percent),
                "soh_percent": soh,
                "estimated_usable_range_km": (soh / 100.0) * RATED_RANGE_KM,
                "ambient_temperature_c": float(req.ambient_temperature_c),
                "terrain": str(req.terrain),
                "load_kg": float(req.load_kg),
                "vehicle_id": "EV-PUNE-001",
                "trip_id": "sim-dispatch",
            }
            res = pipeline.process_single(trip_dict)

            urgency = round(float(res.get("fuzzy_urgency", 50.0)), 1)
            margin_km = round(float(res.get("range_margin_km", 0.0)), 1)
            charging_req = bool(res.get("charging_required", False))
            rec_soc = round(float(res.get("recommended_soc_percent", 50.0)), 1)
            charging_needed = round(float(res.get("charging_requirement_kwh", 0.0)), 2)

            if urgency >= 75.0:
                urgency_label = "CRITICAL DEFICIT"
            elif urgency >= 50.0:
                urgency_label = "DEFICIT WARNING"
            elif urgency >= 25.0:
                urgency_label = "MODERATE MARGIN"
            else:
                urgency_label = "SAFE MARGIN"

            return {
                "status": "success",
                "trip_distance_km": req.trip_distance_km,
                "effective_demand_km": round(float(res.get("effective_trip_demand_km", req.trip_distance_km)), 1),
                "energy_demand_kwh": round(float(res.get("trip_energy_demand_kwh", 0.0)), 2),
                "available_range_km": round(float(res.get("available_range_km", 0.0)), 1),
                "range_margin_km": margin_km,
                "charging_required": charging_req,
                "fuzzy_urgency": urgency,
                "urgency_label": urgency_label,
                "charging_needed_kwh": charging_needed,
                "recommended_min_starting_soc": rec_soc,
                "recommendation_text": str(res.get("recommendation", "")),
            }
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning("Module 2 live simulation failed, falling back: %s", e)

    # Fallback to analytical physics if Module 2 pipeline is unavailable
    terrain_mult = 1.0 if req.terrain == "FLAT" else (1.15 if req.terrain == "HILLY" else 1.35)
    temp_mult = compute_thermal_derate_multiplier(req.ambient_temperature_c)
    load_mult = 1.0 + (req.load_kg - 150.0) * 0.0015

    base_kwh_per_km = FLEET_VEHICLE_SPECS["consumption_kwh_per_km"]
    factory_nominal_range = FLEET_VEHICLE_SPECS["factory_nominal_range_km"]
    safety_reserve_soc = FLEET_VEHICLE_SPECS["safety_reserve_soc_percent"]

    effective_demand_km = req.trip_distance_km * terrain_mult * temp_mult * load_mult
    energy_demand_kwh = effective_demand_km * base_kwh_per_km

    usable_range_full = (req.soh_percent / 100.0) * factory_nominal_range
    usable_soc = max(0.0, req.initial_soc_percent - safety_reserve_soc)
    available_range_km = (usable_soc / 100.0) * usable_range_full

    range_margin_km = available_range_km - effective_demand_km
    charging_required = range_margin_km < 0.0

    if range_margin_km < -20.0:
        fuzzy_urgency = 95.0
        urgency_label = "CRITICAL DEFICIT"
    elif range_margin_km < 0.0:
        fuzzy_urgency = 82.0
        urgency_label = "DEFICIT WARNING"
    elif range_margin_km < 15.0:
        fuzzy_urgency = 52.0
        urgency_label = "MODERATE MARGIN"
    else:
        fuzzy_urgency = 18.0
        urgency_label = "SAFE MARGIN"

    charging_needed_kwh = abs(range_margin_km) * base_kwh_per_km if charging_required else 0.0
    recommended_min_soc = min(92.0, max(20.0, ((effective_demand_km / usable_range_full) * 100.0) + safety_reserve_soc))

    return {
        "status": "success",
        "trip_distance_km": req.trip_distance_km,
        "effective_demand_km": round(effective_demand_km, 1),
        "energy_demand_kwh": round(energy_demand_kwh, 2),
        "available_range_km": round(available_range_km, 1),
        "range_margin_km": round(range_margin_km, 1),
        "charging_required": charging_required,
        "fuzzy_urgency": fuzzy_urgency,
        "urgency_label": urgency_label,
        "charging_needed_kwh": round(charging_needed_kwh, 2),
        "recommended_min_starting_soc": round(recommended_min_soc, 1),
        "recommendation_text": (
            f"CHARGE IMMEDIATELY: Deficit of {abs(range_margin_km):.1f} km ({charging_needed_kwh:.1f} kWh). Start trip with at least {recommended_min_soc:.0f}% SOC."
            if charging_required
            else f"SAFE TO DISPATCH: Sufficient margin of +{range_margin_km:.1f} km remaining after reserve."
        ),
    }
