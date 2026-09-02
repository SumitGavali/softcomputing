"""
module2/schemas.py
==================
Module 2 — Trip-Level Charging Recommendation Engine
EV Range Intelligence Project

Defines all Pydantic input/output models used across Module 2 stages.

IMPORTANT:
- BatteryTelemetryM1 mirrors the frozen Module 1 BatteryTelemetry schema
  from api.py. It must NOT be modified to match Module 1's validation bounds.
- Module 1's /predict/soh endpoint and api.py are NOT imported or modified.
"""

from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# MODULE 1 MIRROR SCHEMA
# ──────────────────────────────────────────────────────────────────────────────

class BatteryTelemetryM1(BaseModel):
    """
    Read-only mirror of Module 1's frozen BatteryTelemetry Pydantic model.
    Source: api.py lines 28-46.

    Used ONLY as structured input to Module1Adapter.
    Module 1's api.py is NOT imported, modified, or called for batch processing.
    Validation bounds match those in the frozen api.py exactly.
    """
    discharge_index: int = Field(..., ge=1, le=250,
        description="Cycle count / discharge age of battery (training range: 1-197)")
    ambient_temperature: float = Field(..., ge=0.0, le=50.0,
        description="Ambient temperature in Celsius (training range: 4-44°C)")
    max_temp_reached: float = Field(..., ge=0.0, le=80.0,
        description="Peak temperature during discharge (training range: 7-70°C)")
    charge_rate_proxy: float = Field(..., ge=0.0, le=30.0,
        description="Voltage drop-rate proxy V/sec*1000 (training range: 0.2-23.4)")
    time_since_reset_cycles: float = Field(..., ge=0.0, le=20.0,
        description="Cycles since last impedance/reset check (training range: 0-13)")
    internal_resistance_re: float = Field(..., ge=0.01, le=0.3,
        description="Internal electrolyte resistance in ohms (training range: 0.028-0.156)")


# ──────────────────────────────────────────────────────────────────────────────
# MODULE 1 ADAPTER OUTPUT
# ──────────────────────────────────────────────────────────────────────────────

class Module1Output(BaseModel):
    """Output returned by Module1Adapter for a single battery telemetry reading."""
    soh_percent: float = Field(..., description="Predicted State of Health (0-100%)")
    estimated_usable_range_km: float = Field(...,
        description="Estimated full-SOC usable range = rated_range * (soh/100)")


# ──────────────────────────────────────────────────────────────────────────────
# TRIP REQUEST (full pipeline input for a single trip)
# ──────────────────────────────────────────────────────────────────────────────

class TripRequest(BaseModel):
    """
    Complete input to the Module 2 pipeline for one trip.
    Produced by SyntheticTripGenerator or submitted via the Module 2 API.
    """
    # Identity & geography
    trip_id: str = Field(..., description="Unique trip identifier")
    vehicle_id: str = Field(..., description="Vehicle identifier; must exist in VEHICLE_REGISTRY")
    latitude: float = Field(..., ge=-90.0, le=90.0,
        description="WGS-84 latitude of trip origin (synthetic for Module 2)")
    longitude: float = Field(..., ge=-180.0, le=180.0,
        description="WGS-84 longitude of trip origin (synthetic for Module 2)")

    # Trip context — randomized simulation inputs
    initial_soc_percent: float = Field(..., ge=20.0, le=92.0,
        description="Battery SOC at trip start (%)")
    trip_distance_km: float = Field(..., ge=5.0, le=150.0,
        description="Planned one-way trip distance (km)")

    # Environmental / load inputs — consumed by energy model, NOT by FIS directly
    ambient_temperature_c: float = Field(..., ge=12.0, le=42.0,
        description="Ambient air temperature (°C)")
    terrain: str = Field(..., description="Terrain type: FLAT | HILLY | MOUNTAIN")
    load_kg: float = Field(..., ge=70.0, le=350.0,
        description="Total vehicle + occupant + cargo mass (kg)")

    # Module 1 battery telemetry — forwarded to Module1Adapter
    battery_telemetry: BatteryTelemetryM1


# ──────────────────────────────────────────────────────────────────────────────
# PHASE 1 INTERMEDIATE OUTPUT RECORD
# ──────────────────────────────────────────────────────────────────────────────

class Phase1Record(BaseModel):
    """
    Output of Phase 1 (Stages 1-2 combined).
    Contains all trip inputs + Module 1 outputs.
    Energy model and recommendation fields will be added in later phases.
    """
    # Identity
    trip_id: str
    vehicle_id: str

    # Geography (synthetic, for Module 3)
    latitude: float
    longitude: float

    # Module 1 outputs — from frozen model via adapter
    soh_percent: float
    estimated_usable_range_km: float

    # Raw trip inputs (will feed into energy model in Phase 2)
    initial_soc_percent: float
    trip_distance_km: float
    ambient_temperature_c: float
    terrain: str
    load_kg: float

    # Vehicle spec (from config)
    battery_capacity_kwh: float
    rated_range_km: float

    # Telemetry fields (preserved for traceability / SoH grounding audit)
    source_battery_id: str            # Which NASA battery row was sampled
    discharge_index: int
    telemetry_ambient_temp: float     # NASA telemetry temp (different from trip temp)
    max_temp_reached: float
    charge_rate_proxy: float
    time_since_reset_cycles: float
    internal_resistance_re: float


# ──────────────────────────────────────────────────────────────────────────────
# FULL MODULE 2 OUTPUT RECORD (final schema, Phase 4+)
# ──────────────────────────────────────────────────────────────────────────────

class ChargingRecommendationRecord(BaseModel):
    """
    Complete Module 2 output record. Populated progressively across phases.
    Fields from Phase 2 onwards are Optional until those phases are implemented.
    """
    # Phase 1 fields
    trip_id: str
    vehicle_id: str
    latitude: float
    longitude: float
    soh_percent: float
    estimated_usable_range_km: float
    initial_soc_percent: float
    trip_distance_km: float
    ambient_temperature_c: float
    terrain: str
    load_factor: float
    battery_capacity_kwh: float
    rated_range_km: float

    # Phase 2 fields (energy model)
    trip_energy_demand_kwh: Optional[float] = None
    effective_trip_demand_km: Optional[float] = None

    # Phase 2 fields (margin calculator)
    available_range_km: Optional[float] = None
    range_margin_km: Optional[float] = None
    range_margin_percent: Optional[float] = None

    # Phase 3 fields (FIS + recommendation)
    charging_requirement: Optional[str] = None     # LOW | MEDIUM | HIGH | CRITICAL
    charging_required: Optional[bool] = None
    charging_requirement_kwh: Optional[float] = None
    recommended_soc_percent: Optional[float] = Field(None, description="minimum recommended starting SOC")
    additional_soc_required: Optional[float] = None
    recommendation: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# MODULE 3 HANDOFF RECORD
# ──────────────────────────────────────────────────────────────────────────────

class ChargingEventRecord(BaseModel):
    """
    Module 3 handoff schema.
    Written to charging_events.csv — contains ONLY trips where charging_required==True.
    Module 3 will aggregate these geographically to find demand hotspots.
    """
    trip_id: str
    vehicle_id: str
    latitude: float
    longitude: float
    charging_requirement: str          # LOW | MEDIUM | HIGH | CRITICAL
    charging_requirement_kwh: float
    recommended_soc_percent: float
