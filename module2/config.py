"""
module2/config.py
=================
Module 2 — Trip-Level Charging Recommendation Engine
EV Range Intelligence Project

ALL values in this file are SIMULATION ASSUMPTIONS for a research/course prototype.
They are NOT measured real-world fleet telemetry and must NOT be presented as such.

Classification tags used in comments:
  [FIXED]        — Hard-coded vehicle/physics constant; not intended to change
  [CONFIGURABLE] — Tunable parameter; safe to adjust for sensitivity analysis
  [DERIVED]      — Computed from other fixed values; must stay consistent
"""

import os

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 1 — VEHICLE SPECIFICATION
# ──────────────────────────────────────────────────────────────────────────────
# Simulation vehicle: Compact Urban Fleet EV
# vehicle_id "URBAN_EV_30" is a fictional representative configuration.
# It is NOT the specification of any real manufacturer or model.

VEHICLE_ID              = "URBAN_EV_30"   # [FIXED]  Simulation vehicle identifier
VEHICLE_TYPE            = "Compact Urban Fleet EV"  # [FIXED]  Descriptive label only

BATTERY_CAPACITY_KWH    = 30.0            # [FIXED]  Usable battery capacity (kWh)
RATED_RANGE_KM          = 200.0           # [FIXED]  Full-charge range at baseline conditions (km)
BASE_ENERGY_KWH_PER_KM  = 0.150          # [DERIVED] = BATTERY_CAPACITY_KWH / RATED_RANGE_KM
                                           #           30.0 / 0.150 = 200.0  ✓ Verified consistent

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 2 — SAFETY PARAMETERS
# ──────────────────────────────────────────────────────────────────────────────

SAFETY_RESERVE_SOC_PCT   = 15.0           # [CONFIGURABLE] Minimum SOC kept in reserve (%)
                                           # Applied in available_range_km calculation:
                                           #   usable_soc = max(0, soc - SAFETY_RESERVE_SOC_PCT)
                                           #   available_range = usable_soc/100 * estimated_usable_range
                                           # NOT added again in the recommendation engine.

MAX_CHARGE_SOC_PCT       = 92.0           # [CONFIGURABLE] BMS upper SOC charge limit (%)
                                           # Avoids full-charge cell degradation.

CHARGING_EFFICIENCY      = 0.90           # [CONFIGURABLE] Grid-to-battery AC Level 2 efficiency
                                           # Source: IEA Global EV Outlook 2023 (85-92% typical)
                                           # Used to convert battery_energy_required -> grid_energy:
                                           #   charging_energy_kwh = battery_kwh / CHARGING_EFFICIENCY

SAFETY_BUFFER_FACTOR     = 1.10           # [CONFIGURABLE] Applied ONCE in the energy model only.
                                           # Accounts for: driving style variation, auxiliary loads
                                           # (lights, infotainment), route deviations, wind resistance.
                                           # NOT applied again downstream.

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 3 — TERRAIN MULTIPLIERS
# ──────────────────────────────────────────────────────────────────────────────
# Multiplier applied to base energy consumption per km.
# Source: Genikomsakis & Mitrentsis (2017) — EV energy consumption models
# for urban and hilly terrain. Values are simulation approximations.

TERRAIN_MULTIPLIERS = {
    "FLAT":     1.00,   # [FIXED] Baseline — level urban roads
    "HILLY":    1.15,   # [FIXED] ~15% increase — moderate grades (4-6%)
    "MOUNTAIN": 1.35,   # [FIXED] ~35% increase — sustained steep grades (>8%)
                         #  Regen braking partially offsets downhill cost;
                         #  net penalty of 35% is a conservative mid-point.
}

TERRAIN_PROBABILITIES = {
    "FLAT":     0.70,   # [CONFIGURABLE] Pune city core — largely flat road network
    "HILLY":    0.20,   # [CONFIGURABLE] Pune outskirts, Katraj, Sinhagad Road
    "MOUNTAIN": 0.10,   # [CONFIGURABLE] Lonavala / Western Ghats access routes
}

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 4 — TEMPERATURE MULTIPLIERS
# ──────────────────────────────────────────────────────────────────────────────
# Piecewise-linear temperature-to-multiplier mapping.
# Source: Pesaran (NREL 2002) — Li-ion efficiency vs temperature curves.
# ~15% efficiency reduction below 15°C; ~10-15% increase above 38°C from HVAC.
#
# Format: list of (temp_c_upper_bound, multiplier_at_or_below_bound)
# Linear interpolation is used between breakpoints.

TEMP_BREAKPOINTS = [
    (12,  1.15),   # [FIXED] Very cold — reduced Li-ion kinetics + heater load
    (18,  1.15),   # [FIXED] Cold upper edge
    (22,  1.00),   # [FIXED] Transition to normal
    (32,  1.00),   # [FIXED] Normal upper edge — optimal battery zone
    (38,  1.08),   # [FIXED] Warm — AC load begins
    (42,  1.15),   # [FIXED] Hot — high AC + thermal management overhead
    (50,  1.15),   # [FIXED] Cap — multiplier does not increase further
]

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 5 — LOAD MODEL
# ──────────────────────────────────────────────────────────────────────────────

REFERENCE_LOAD_KG            = 150.0    # [FIXED]        Driver 75 kg + cargo 75 kg
MIN_LOAD_KG                  = 70.0    # [CONFIGURABLE] Solo driver, no cargo
MAX_LOAD_KG                  = 350.0   # [CONFIGURABLE] Driver + cargo at vehicle capacity limit
LOAD_PENALTY_FRACTION_PER_KG = 0.0015  # [CONFIGURABLE] Energy increase per extra kg above reference
                                         # = 0.15% per kg. Derived from rolling-resistance
                                         # approximation for urban stop-start driving.
                                         # load_mult = 1.0 + (load_kg - REF_LOAD) * PENALTY

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 6 — SOC DISTRIBUTION (for synthetic trip generation)
# ──────────────────────────────────────────────────────────────────────────────

SOC_BANDS = [
    {"label": "LOW",    "min": 20.0, "max": 40.0, "prob": 0.25},
    {"label": "MEDIUM", "min": 40.0, "max": 70.0, "prob": 0.45},
    {"label": "HIGH",   "min": 70.0, "max": 92.0, "prob": 0.30},
]
# 25% LOW creates a meaningful fraction of charging-required trips.
# 45% MEDIUM represents overnight partial charge.
# 30% HIGH represents fully-charged fleet vehicles.
# Min SOC 20%: below this the BMS restricts power (treated as empty).
# Max SOC 92%: BMS avoids 100% for cell longevity.

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 7 — TRIP DISTANCE DISTRIBUTION
# ──────────────────────────────────────────────────────────────────────────────

TRIP_DISTANCE_BANDS = [
    {"label": "SHORT",  "min":  5.0, "max":  30.0, "prob": 0.65},
    {"label": "MEDIUM", "min": 30.0, "max":  80.0, "prob": 0.25},
    {"label": "LONG",   "min": 80.0, "max": 150.0, "prob": 0.10},
]
# Source: NITI Aayog EV Report 2022 — average urban delivery trip 8-25 km.
# 65% SHORT reflects last-mile delivery dominance.
# 150 km hard cap = 75% of rated range; prevents unrealistic generation.

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 8 — AMBIENT TEMPERATURE DISTRIBUTION (Pune, India)
# ──────────────────────────────────────────────────────────────────────────────

TEMP_BANDS = [
    {"label": "COOL",   "min": 12.0, "max": 22.0, "prob": 0.15},
    {"label": "NORMAL", "min": 22.0, "max": 32.0, "prob": 0.65},
    {"label": "HOT",    "min": 32.0, "max": 42.0, "prob": 0.20},
]
# Represents Pune seasonal climate:
#   COOL  — monsoon/winter mornings (Oct–Feb)
#   NORMAL — year-round typical (Mar, Jun–Sep)
#   HOT    — summer peak (Mar–May)

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 9 — GEOGRAPHIC BOUNDS (Pune, Maharashtra) — SYNTHETIC LOCATIONS
# ──────────────────────────────────────────────────────────────────────────────
# Coordinates are generated uniformly within the Pune metropolitan bounding box.
# These are SYNTHETIC simulation locations, not real GPS trip traces.
# Module 3 may later snap them to the actual OSM road network.

LAT_MIN = 18.40    # [FIXED] Southern boundary
LAT_MAX = 18.65    # [FIXED] Northern boundary
LON_MIN = 73.75    # [FIXED] Western boundary
LON_MAX = 74.05    # [FIXED] Eastern boundary

# ──────────────────────────────────────────────────────────────────────────────
# SECTION 10 — MODULE 1 FILE REFERENCES (READ-ONLY)
# ──────────────────────────────────────────────────────────────────────────────
# These paths point to FROZEN Module 1 artefacts.
# Absolutely nothing in module2/ may modify these files.

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)  # project root (cp/)

M1_MODEL_PATH       = os.path.join(_ROOT, "soh_random_forest_model.pkl")
M1_PREDICTIONS_PATH = os.path.join(_ROOT, "test_predictions.csv")

# Exact feature column order the frozen Module 1 model was trained on.
# Sourced directly from api.py lines 61-67. DO NOT CHANGE.
M1_FEATURE_COLUMNS = [
    "Discharge_Index",
    "Ambient_Temperature",
    "Max_Temp_Reached",
    "Charge_Rate_Proxy",
    "Time_Since_Reset_Cycles",
    "Internal_Resistance_Re",
]

# Columns from test_predictions.csv that map to M1_FEATURE_COLUMNS
M1_TELEMETRY_SOURCE_COLUMNS = [
    "Discharge_Index",
    "Ambient_Temperature",
    "Max_Temp_Reached",
    "Charge_Rate_Proxy",
    "Time_Since_Reset_Cycles",
    "Internal_Resistance_Re",
]
