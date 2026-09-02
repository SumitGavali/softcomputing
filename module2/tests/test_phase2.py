"""
module2/tests/test_phase2.py
============================
Deterministic unit tests for Phase 2:
  - TripEnergyDemandModel
  - RangeMarginCalculator

Run from project root:  python -m pytest module2/tests/test_phase2.py -v
or:                     python module2/tests/test_phase2.py
"""

import sys
import os
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from module2.energy_model import TripEnergyDemandModel
from module2.margin_calculator import RangeMarginCalculator
from module2.config import (
    BASE_ENERGY_KWH_PER_KM,
    TERRAIN_MULTIPLIERS,
    REFERENCE_LOAD_KG,
    LOAD_PENALTY_FRACTION_PER_KG,
    SAFETY_BUFFER_FACTOR,
    SAFETY_RESERVE_SOC_PCT,
)

em  = TripEnergyDemandModel()
rmc = RangeMarginCalculator()

PASS = "[PASS]"
FAIL = "[FAIL]"
results = []


def check(name: str, condition: bool, detail: str = ""):
    icon = PASS if condition else FAIL
    msg = f"  {icon}  {name}"
    if detail:
        msg += f"\n         {detail}"
    print(msg)
    results.append((name, condition))
    return condition


# ── Baseline reference values ────────────────────────────────────────────────
FLAT_NORMAL_REF = em.compute_single(
    trip_distance_km=50.0,
    ambient_temperature_c=27.0,   # inside NORMAL band → multiplier = 1.00
    terrain="FLAT",
    load_kg=REFERENCE_LOAD_KG,    # 150 kg → multiplier = 1.00
)

# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 — Flat terrain, normal temperature, reference load
# ─────────────────────────────────────────────────────────────────────────────
def test_01_baseline():
    """Flat + normal temp + reference load → all multipliers should be 1.0."""
    r = FLAT_NORMAL_REF
    ok = (
        abs(r["terrain_multiplier"]     - 1.00) < 1e-5 and
        abs(r["temperature_multiplier"] - 1.00) < 1e-5 and
        abs(r["load_multiplier"]        - 1.00) < 1e-5
    )
    expected_energy = 50.0 * BASE_ENERGY_KWH_PER_KM * SAFETY_BUFFER_FACTOR
    energy_ok = abs(r["trip_energy_demand_kwh"] - expected_energy) < 1e-4
    check(
        "TEST 01 — Baseline: all multipliers = 1.0, energy = dist*base*buffer",
        ok and energy_ok,
        f"terrain={r['terrain_multiplier']}, temp={r['temperature_multiplier']}, "
        f"load={r['load_multiplier']}, energy={r['trip_energy_demand_kwh']:.4f} kWh "
        f"(expected {expected_energy:.4f})",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 — Hilly terrain > flat terrain (same everything else)
# ─────────────────────────────────────────────────────────────────────────────
def test_02_hilly_gt_flat():
    flat_r  = em.compute_single(50.0, 27.0, "FLAT",  REFERENCE_LOAD_KG)
    hilly_r = em.compute_single(50.0, 27.0, "HILLY", REFERENCE_LOAD_KG)
    check(
        "TEST 02 — HILLY energy > FLAT energy (same distance/temp/load)",
        hilly_r["trip_energy_demand_kwh"] > flat_r["trip_energy_demand_kwh"],
        f"FLAT={flat_r['trip_energy_demand_kwh']:.4f}, HILLY={hilly_r['trip_energy_demand_kwh']:.4f}",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 — Mountain terrain > hilly terrain (same everything else)
# ─────────────────────────────────────────────────────────────────────────────
def test_03_mountain_gt_hilly():
    hilly_r    = em.compute_single(50.0, 27.0, "HILLY",    REFERENCE_LOAD_KG)
    mountain_r = em.compute_single(50.0, 27.0, "MOUNTAIN", REFERENCE_LOAD_KG)
    check(
        "TEST 03 — MOUNTAIN energy > HILLY energy (same distance/temp/load)",
        mountain_r["trip_energy_demand_kwh"] > hilly_r["trip_energy_demand_kwh"],
        f"HILLY={hilly_r['trip_energy_demand_kwh']:.4f}, MOUNTAIN={mountain_r['trip_energy_demand_kwh']:.4f}",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 — Higher load does not decrease energy
# ─────────────────────────────────────────────────────────────────────────────
def test_04_higher_load_more_energy():
    low_load  = em.compute_single(50.0, 27.0, "FLAT", 100.0)
    high_load = em.compute_single(50.0, 27.0, "FLAT", 300.0)
    check(
        "TEST 04 — Higher load => higher or equal energy demand",
        high_load["trip_energy_demand_kwh"] >= low_load["trip_energy_demand_kwh"],
        f"load=100kg: {low_load['trip_energy_demand_kwh']:.4f}, "
        f"load=300kg: {high_load['trip_energy_demand_kwh']:.4f}",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 — Higher temperature penalty does not decrease energy
# ─────────────────────────────────────────────────────────────────────────────
def test_05_higher_temp_penalty_more_energy():
    normal_temp = em.compute_single(50.0, 27.0, "FLAT", REFERENCE_LOAD_KG)  # 1.00
    cold_temp   = em.compute_single(50.0, 15.0, "FLAT", REFERENCE_LOAD_KG)  # 1.15
    hot_temp    = em.compute_single(50.0, 40.0, "FLAT", REFERENCE_LOAD_KG)  # 1.15
    check(
        "TEST 05 — Cold temp (15C) energy >= normal temp (27C) energy",
        cold_temp["trip_energy_demand_kwh"] >= normal_temp["trip_energy_demand_kwh"],
        f"normal={normal_temp['trip_energy_demand_kwh']:.4f}, "
        f"cold={cold_temp['trip_energy_demand_kwh']:.4f}",
    )
    check(
        "TEST 05b — Hot temp (40C) energy >= normal temp (27C) energy",
        hot_temp["trip_energy_demand_kwh"] >= normal_temp["trip_energy_demand_kwh"],
        f"normal={normal_temp['trip_energy_demand_kwh']:.4f}, "
        f"hot={hot_temp['trip_energy_demand_kwh']:.4f}",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 — Longer trip does not decrease energy
# ─────────────────────────────────────────────────────────────────────────────
def test_06_longer_trip_more_energy():
    short = em.compute_single(20.0, 27.0, "FLAT", REFERENCE_LOAD_KG)
    long_ = em.compute_single(80.0, 27.0, "FLAT", REFERENCE_LOAD_KG)
    check(
        "TEST 06 — Longer trip => higher energy demand",
        long_["trip_energy_demand_kwh"] > short["trip_energy_demand_kwh"],
        f"20km: {short['trip_energy_demand_kwh']:.4f}, 80km: {long_['trip_energy_demand_kwh']:.4f}",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 — Higher initial SOC does not decrease available range
# ─────────────────────────────────────────────────────────────────────────────
def test_07_higher_soc_more_range():
    low_soc  = rmc.compute_single(30.0, 150.0, 20.0)
    high_soc = rmc.compute_single(80.0, 150.0, 20.0)
    check(
        "TEST 07 — Higher initial SOC => higher available_range_km",
        high_soc["available_range_km"] > low_soc["available_range_km"],
        f"SOC=30%: {low_soc['available_range_km']:.2f} km, "
        f"SOC=80%: {high_soc['available_range_km']:.2f} km",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 — Higher usable range does not decrease available range
# ─────────────────────────────────────────────────────────────────────────────
def test_08_higher_usable_range():
    low_range  = rmc.compute_single(60.0, 100.0, 20.0)
    high_range = rmc.compute_single(60.0, 200.0, 20.0)
    check(
        "TEST 08 — Higher estimated_usable_range => higher available_range_km",
        high_range["available_range_km"] > low_range["available_range_km"],
        f"range=100km: {low_range['available_range_km']:.2f}, "
        f"range=200km: {high_range['available_range_km']:.2f}",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 9 — Negative margin means insufficient range
# ─────────────────────────────────────────────────────────────────────────────
def test_09_negative_margin_infeasible():
    # SOC=20%, estimated range=100km => usable_soc=5%, available=5km
    # effective demand = 50km (much larger)
    r = rmc.compute_single(20.0, 100.0, 50.0)
    check(
        "TEST 09 — Negative range_margin_km => trip_feasible_without_charging=False",
        r["range_margin_km"] < 0 and not r["trip_feasible_without_charging"],
        f"available={r['available_range_km']:.2f}, demand=50km, "
        f"margin={r['range_margin_km']:.2f}",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 10 — Positive margin means sufficient range
# ─────────────────────────────────────────────────────────────────────────────
def test_10_positive_margin_feasible():
    # SOC=92%, estimated range=200km => usable_soc=77%, available=154km
    # effective demand = 10km
    r = rmc.compute_single(92.0, 200.0, 10.0)
    check(
        "TEST 10 — Positive range_margin_km => trip_feasible_without_charging=True",
        r["range_margin_km"] > 0 and r["trip_feasible_without_charging"],
        f"available={r['available_range_km']:.2f}, demand=10km, "
        f"margin={r['range_margin_km']:.2f}",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 11 — Safety reserve applied exactly once
# ─────────────────────────────────────────────────────────────────────────────
def test_11_safety_reserve_once():
    soc = 50.0
    est_range = 200.0
    r = rmc.compute_single(soc, est_range, 0.0)

    expected_usable_soc = max(0.0, soc - SAFETY_RESERVE_SOC_PCT)   # 35%
    expected_available  = est_range * expected_usable_soc / 100.0   # 70 km

    usable_ok    = abs(r["usable_soc_percent"]  - expected_usable_soc) < 1e-4
    available_ok = abs(r["available_range_km"]   - expected_available)  < 1e-4
    check(
        "TEST 11 — Safety reserve of 15% deducted once from SOC (not twice)",
        usable_ok and available_ok,
        f"SOC={soc}%, reserve={SAFETY_RESERVE_SOC_PCT}%, "
        f"usable_soc={r['usable_soc_percent']}% (expected {expected_usable_soc}%), "
        f"available={r['available_range_km']:.2f} km (expected {expected_available:.2f})",
    )

# ─────────────────────────────────────────────────────────────────────────────
# TEST 12 — No NaN or infinite values
# ─────────────────────────────────────────────────────────────────────────────
def test_12_no_nan_inf():
    import pandas as pd
    import numpy as np

    try:
        phase1 = pd.read_csv("module2/data/phase1_trips.csv")
        energy_df = em.compute_batch(phase1)
        result_df = rmc.compute_batch(energy_df)

        numeric_cols = [
            "base_energy_demand_kwh", "terrain_multiplier",
            "temperature_multiplier", "load_multiplier",
            "trip_energy_demand_kwh", "effective_trip_demand_km",
            "usable_soc_percent", "available_range_km",
            "range_margin_km", "range_margin_percent",
        ]
        has_nan = result_df[numeric_cols].isna().any().any()
        has_inf = np.isinf(result_df[numeric_cols].select_dtypes("number")).any().any()
        check(
            "TEST 12a — No NaN values in calculated numeric columns",
            not has_nan,
            "NaN count: " + str(result_df[numeric_cols].isna().sum().sum()),
        )
        check(
            "TEST 12b — No infinite values in calculated numeric columns",
            not has_inf,
        )
    except FileNotFoundError:
        check("TEST 12 — phase1_trips.csv not found", False, "Run run_phase1.py first.")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────
def run_all():
    print("\n" + "=" * 70)
    print("MODULE 2 PHASE 2 — UNIT TESTS")
    print("=" * 70)

    test_01_baseline()
    test_02_hilly_gt_flat()
    test_03_mountain_gt_hilly()
    test_04_higher_load_more_energy()
    test_05_higher_temp_penalty_more_energy()
    test_06_longer_trip_more_energy()
    test_07_higher_soc_more_range()
    test_08_higher_usable_range()
    test_09_negative_margin_infeasible()
    test_10_positive_margin_feasible()
    test_11_safety_reserve_once()
    test_12_no_nan_inf()

    passed = sum(1 for _, ok in results if ok)
    total  = len(results)
    print("\n" + "=" * 70)
    print(f"  RESULT: {passed}/{total} tests passed")
    print("=" * 70 + "\n")
    return passed == total


if __name__ == "__main__":
    ok = run_all()
    sys.exit(0 if ok else 1)
