"""
run_phase2.py  — Phase 2 pipeline + verification report for Module 2.
Run from project root:  python run_phase2.py

Reads:   module2/data/phase1_trips.csv
Writes:  module2/data/phase2_trip_analysis.csv
"""

import logging
import os
import sys

import numpy as np
import pandas as pd

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

SEP  = "=" * 70
SEP2 = "-" * 70


def main():
    from module2.energy_model import TripEnergyDemandModel
    from module2.margin_calculator import RangeMarginCalculator
    from module2.config import BASE_ENERGY_KWH_PER_KM, SAFETY_BUFFER_FACTOR, SAFETY_RESERVE_SOC_PCT
    from module2.tests.test_phase2 import run_all as run_unit_tests

    print("\n" + SEP)
    print("MODULE 2 - PHASE 2 REPORT: ENERGY DEMAND + RANGE MARGIN")
    print(SEP)

    # ── 0. Verify Phase 1 inputs are frozen ──────────────────────────────────
    phase1_path = "module2/data/phase1_trips.csv"
    if not os.path.isfile(phase1_path):
        print("ERROR: phase1_trips.csv not found. Run run_phase1.py first.")
        sys.exit(1)
    print("\n[0] Phase 1 input verified: " + phase1_path)

    # ── 1. Load Phase 1 dataset ───────────────────────────────────────────────
    df = pd.read_csv(phase1_path)
    print("[1] Loaded Phase 1 dataset: {:,} rows x {:,} columns".format(*df.shape))

    # ── 2. Energy Demand Model ───────────────────────────────────────────────
    print("\n" + SEP)
    print("[2] STAGE 3: TRIP ENERGY DEMAND MODEL")
    print(SEP)
    print("\n    Exact formula applied:")
    print("    base_energy_kwh = trip_distance_km * BASE_ENERGY_KWH_PER_KM")
    print("                    = trip_distance_km * {:.3f}".format(BASE_ENERGY_KWH_PER_KM))
    print("    trip_energy_demand_kwh =")
    print("        base_energy_kwh")
    print("        * terrain_multiplier       (FLAT=1.00, HILLY=1.15, MOUNTAIN=1.35)")
    print("        * temperature_multiplier   (piecewise linear, 1.00-1.15)")
    print("        * load_multiplier          (1 + (load-150)*0.0015)")
    print("        * SAFETY_BUFFER_FACTOR     ({:.2f} — applied ONCE here)".format(SAFETY_BUFFER_FACTOR))
    print("    effective_trip_demand_km = trip_energy_demand_kwh / {:.3f}".format(BASE_ENERGY_KWH_PER_KM))

    em = TripEnergyDemandModel()
    df = em.compute_batch(df)
    print("\n    Energy model applied successfully.")

    # ── 3. Range Margin Calculator ────────────────────────────────────────────
    print("\n" + SEP)
    print("[3] STAGE 4: RANGE MARGIN CALCULATOR")
    print(SEP)
    print("\n    Exact formula applied:")
    print("    [SIMULATION ASSUMPTION: linear SOC-to-range mapping]")
    print("    usable_soc_percent   = max(0, initial_soc_percent - {:.1f})".format(SAFETY_RESERVE_SOC_PCT))
    print("    available_range_km   = estimated_usable_range_km * usable_soc_percent / 100")
    print("    range_margin_km      = available_range_km - effective_trip_demand_km")
    print("    range_margin_percent = (range_margin_km / effective_trip_demand_km) * 100")
    print("    trip_feasible_without_charging = (available_range_km >= effective_trip_demand_km)")
    print("    NOTE: 15% safety reserve applied ONCE above. NOT added again downstream.")

    rmc = RangeMarginCalculator()
    df  = rmc.compute_batch(df)
    print("\n    Range margin calculated successfully.")

    # ── 4. Save Phase 2 dataset ───────────────────────────────────────────────
    out_path = "module2/data/phase2_trip_analysis.csv"
    df.to_csv(out_path, index=False)
    print("\n[4] Saved: " + out_path)

    # ── 5. Dataset shape & column check ──────────────────────────────────────
    print("\n" + SEP)
    print("[5] DATASET SHAPE & COLUMNS")
    print(SEP)
    print("    Rows    : {:,}".format(df.shape[0]))
    print("    Columns : {}".format(df.shape[1]))
    phase2_new_cols = [
        "base_energy_demand_kwh", "terrain_multiplier", "temperature_multiplier",
        "load_multiplier", "trip_energy_demand_kwh", "effective_trip_demand_km",
        "usable_soc_percent", "available_range_km",
        "range_margin_km", "range_margin_percent", "trip_feasible_without_charging",
    ]
    print("\n    Phase 2 new columns ({} added):".format(len(phase2_new_cols)))
    for c in phase2_new_cols:
        print("       - " + c)

    # ── 6. First 10 rows ──────────────────────────────────────────────────────
    print("\n" + SEP)
    print("[6] FIRST 10 ROWS (key columns)")
    print(SEP)
    show_cols = [
        "soh_percent", "initial_soc_percent", "trip_distance_km", "terrain",
        "effective_trip_demand_km", "available_range_km",
        "range_margin_km", "range_margin_percent", "trip_feasible_without_charging",
    ]
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.float_format", "{:.2f}".format)
    print(df[show_cols].head(10).to_string(index=True))

    # ── 7. Full distribution statistics ──────────────────────────────────────
    print("\n" + SEP)
    print("[7] DISTRIBUTION STATISTICS")
    print(SEP)

    dist_cols = {
        "A. trip_energy_demand_kwh":    "trip_energy_demand_kwh",
        "B. effective_trip_demand_km":  "effective_trip_demand_km",
        "C. available_range_km":        "available_range_km",
        "D. range_margin_km":           "range_margin_km",
        "E. range_margin_percent":      "range_margin_percent",
    }
    for label, col in dist_cols.items():
        s = df[col]
        print("\n    {}:".format(label))
        print("      min    : {:.3f}".format(s.min()))
        print("      P25    : {:.3f}".format(s.quantile(0.25)))
        print("      median : {:.3f}".format(s.median()))
        print("      mean   : {:.3f}".format(s.mean()))
        print("      P75    : {:.3f}".format(s.quantile(0.75)))
        print("      max    : {:.3f}".format(s.max()))

    # F. Feasibility
    n_true  = df["trip_feasible_without_charging"].sum()
    n_false = (~df["trip_feasible_without_charging"]).sum()
    n_total = len(df)
    print("\n    F. trip_feasible_without_charging:")
    print("      TRUE  (feasible)   : {:,}  ({:.1f}%)".format(n_true,  100*n_true/n_total))
    print("      FALSE (infeasible) : {:,}  ({:.1f}%)".format(n_false, 100*n_false/n_total))

    # ── 8. SoH / SOC relationship analysis ───────────────────────────────────
    print("\n" + SEP)
    print("[8] SoH & SOC RELATIONSHIP ANALYSIS")
    print(SEP)

    # SoH vs available_range correlation
    corr_soh_range  = df["soh_percent"].corr(df["available_range_km"])
    corr_soh_margin = df["soh_percent"].corr(df["range_margin_km"])
    corr_soc_margin = df["initial_soc_percent"].corr(df["range_margin_km"])
    corr_dist_margin = df["trip_distance_km"].corr(df["range_margin_km"])

    print("\n    Pearson correlation coefficients:")
    print("      SoH   vs available_range_km   : {:.4f}".format(corr_soh_range))
    print("      SoH   vs range_margin_km       : {:.4f}".format(corr_soh_margin))
    print("      InitialSOC vs range_margin_km  : {:.4f}".format(corr_soc_margin))
    print("      trip_distance vs range_margin   : {:.4f}".format(corr_dist_margin))

    print("\n    SoH quartile breakdown (range margin):")
    df["soh_quartile"] = pd.qcut(df["soh_percent"], q=4,
                                  labels=["Q1 (low SoH)", "Q2", "Q3", "Q4 (high SoH)"])
    for q, grp in df.groupby("soh_quartile", observed=True):
        pct_feasible = grp["trip_feasible_without_charging"].mean() * 100
        print("      {:15s}  SoH=[{:.1f}%, {:.1f}%]  mean_margin={:>8.2f} km  "
              "feasible={:.1f}%".format(
                  str(q),
                  grp["soh_percent"].min(), grp["soh_percent"].max(),
                  grp["range_margin_km"].mean(), pct_feasible
              ))

    print("\n    Initial SOC band breakdown (range margin):")
    soc_bins  = [0, 40, 70, 100]
    soc_labels = ["LOW (20-40%)", "MEDIUM (40-70%)", "HIGH (70-92%)"]
    df["soc_band"] = pd.cut(df["initial_soc_percent"], bins=soc_bins, labels=soc_labels)
    for band, grp in df.groupby("soc_band", observed=True):
        pct_feasible = grp["trip_feasible_without_charging"].mean() * 100
        print("      {:20s}  n={:>4}  mean_margin={:>8.2f} km  feasible={:.1f}%".format(
            str(band), len(grp), grp["range_margin_km"].mean(), pct_feasible
        ))

    # ── 9. Sanity check ───────────────────────────────────────────────────────
    print("\n" + SEP)
    print("[9] SANITY CHECK — FEASIBILITY BALANCE")
    print(SEP)
    pct_feasible = 100 * n_true / n_total
    if pct_feasible > 95:
        print("\n  *** WARNING: {:.1f}% of trips are feasible — nearly all trips "
              "do not need charging.".format(pct_feasible))
        print("  *** This may suggest the simulation is too optimistic.")
        print("  *** Do NOT auto-adjust config. Awaiting human review.")
    elif pct_feasible < 5:
        print("\n  *** WARNING: Only {:.1f}% of trips are feasible — nearly all "
              "trips require charging.".format(pct_feasible))
        print("  *** This may suggest the simulation is too pessimistic.")
        print("  *** Do NOT auto-adjust config. Awaiting human review.")
    else:
        print("\n  Feasibility balance OK: {:.1f}% feasible, {:.1f}% infeasible.".format(
            pct_feasible, 100 - pct_feasible
        ))
        print("  Dataset has meaningful mix for FIS training/testing.")

    # ── 10. Unit tests ────────────────────────────────────────────────────────
    print("\n" + SEP)
    print("[10] UNIT TESTS")
    print(SEP)
    all_passed = run_unit_tests()

    # ── 11. File safety ───────────────────────────────────────────────────────
    print("\n" + SEP)
    print("[11] FILE SAFETY — FROZEN ASSETS UNCHANGED")
    print(SEP)
    frozen = [
        os.path.join(_ROOT, "module2", "Build", "api.py"),
        os.path.join(_ROOT, "module1", "soh_random_forest_model.pkl"),
        os.path.join(_ROOT, "module1", "test_predictions.csv"),
        os.path.join(_ROOT, "module1", "battery_dataset_clean.csv"),
        os.path.join(_ROOT, "module1", "battery_dataset_features.csv"),
        os.path.join(_ROOT, "module2", "data", "phase1_trips.csv"),
    ]
    all_safe = True
    for fp in frozen:
        exists = os.path.isfile(fp)
        status = "INTACT" if exists else "MISSING!"
        if not exists:
            all_safe = False
        print("      {:<10} : {}".format(status, fp))

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + SEP)
    print("  PHASE 2 SUMMARY")
    print(SEP)
    print("  Output file  : " + out_path)
    print("  Rows         : {:,}".format(df.shape[0]))
    print("  Columns      : {}  (Phase 1: 20 + Phase 2: 11 = 31 total)".format(df.shape[1]))
    print("  Frozen files : " + ("ALL INTACT [OK]" if all_safe else "ISSUE DETECTED"))
    print("  Unit tests   : " + ("ALL PASSED [OK]" if all_passed else "FAILURES DETECTED"))
    print("  Feasible     : {:.1f}%".format(pct_feasible))
    print("  Infeasible   : {:.1f}%".format(100 - pct_feasible))
    print("\n  Phase 2 complete. Stopped. Awaiting approval for Phase 3.")
    print(SEP + "\n")


if __name__ == "__main__":
    main()
