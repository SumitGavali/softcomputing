"""
run_phase1.py  — Phase 1 verification script for Module 2.
Run from project root:  python run_phase1.py
"""

import logging
import os
import sys

import pandas as pd
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("phase1_runner")


def main():
    from module2.adapter import Module1Adapter
    from module2.synthetic_data import SyntheticTripGenerator
    from module2.config import (
        M1_MODEL_PATH, M1_PREDICTIONS_PATH,
        BATTERY_CAPACITY_KWH, RATED_RANGE_KM,
        VEHICLE_ID, MIN_LOAD_KG, MAX_LOAD_KG,
        LAT_MIN, LAT_MAX, LON_MIN, LON_MAX,
        SAFETY_RESERVE_SOC_PCT,
    )

    SEP = "=" * 70

    print("\n" + SEP)
    print("MODULE 2 - PHASE 1 VERIFICATION REPORT")
    print(SEP)

    # 1 ── Adapter init
    print("\n[1/9] Initialising Module 1 Adapter ...")
    adapter = Module1Adapter()
    print("      Model type : " + adapter.model_type)
    m1_meta = adapter.verify_module1_files_unmodified()
    print("      PKL path   : " + str(m1_meta["path"]))
    print("      PKL size   : {:,} bytes".format(m1_meta["size_bytes"]))

    # 2 ── Generate
    print("\n[2/9] Generating 5,000 synthetic trips ...")
    generator = SyntheticTripGenerator(adapter=adapter, seed=42)
    df = generator.generate(num_trips=5000)

    os.makedirs("module2/data", exist_ok=True)
    out_path = "module2/data/phase1_trips.csv"
    df.to_csv(out_path, index=False)
    print("      Saved to   : " + out_path)

    # 3 ── Shape & columns
    print("\n" + SEP)
    print("[3/9] DATASET SHAPE & COLUMNS")
    print(SEP)
    print("      Rows    : {:,}".format(df.shape[0]))
    print("      Columns : {}".format(df.shape[1]))
    print("\n      Column list:")
    for i, col in enumerate(df.columns, 1):
        print("        {:>2}. {}".format(i, col))

    # 4 ── First 10 rows
    print("\n" + SEP)
    print("[4/9] FIRST 10 ROWS (selected columns)")
    print(SEP)
    preview_cols = [
        "trip_id", "vehicle_id", "soh_percent", "estimated_usable_range_km",
        "initial_soc_percent", "trip_distance_km", "ambient_temperature_c",
        "terrain", "load_kg", "source_battery_id",
    ]
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 200)
    pd.set_option("display.float_format", "{:.2f}".format)
    print(df[preview_cols].head(10).to_string(index=True))

    # 5 ── Descriptive stats
    print("\n" + SEP)
    print("[5/9] DESCRIPTIVE STATISTICS (numeric columns)")
    print(SEP)
    numeric_cols = [
        "soh_percent", "estimated_usable_range_km",
        "initial_soc_percent", "trip_distance_km",
        "ambient_temperature_c", "load_kg",
        "discharge_index", "internal_resistance_re",
    ]
    stats = df[numeric_cols].describe().T.round(3)
    print(stats.to_string())
    print("\n      Terrain distribution:")
    print(df["terrain"].value_counts().to_string())
    print("\n      Source battery distribution:")
    print(df["source_battery_id"].value_counts().to_string())

    # 6 ── SoH distribution
    print("\n" + SEP)
    print("[6/9] SoH DISTRIBUTION - source: test_predictions.csv")
    print(SEP)
    soh_dist = generator.soh_source_distribution()
    print("      Source column : " + soh_dist["source_column"])
    print("      Count         : " + str(soh_dist["count"]))
    print("      Min           : {:.2f}%".format(soh_dist["min_pct"]))
    print("      Max           : {:.2f}%".format(soh_dist["max_pct"]))
    print("      Mean          : {:.2f}%".format(soh_dist["mean_pct"]))
    print("      Median        : {:.2f}%".format(soh_dist["median_pct"]))
    print("      25th pct      : {:.2f}%".format(soh_dist["p25_pct"]))
    print("      75th pct      : {:.2f}%".format(soh_dist["p75_pct"]))
    print("\n      Generated dataset SoH (soh_percent column):")
    print("      Min    : {:.2f}%".format(df["soh_percent"].min()))
    print("      Max    : {:.2f}%".format(df["soh_percent"].max()))
    print("      Mean   : {:.2f}%".format(df["soh_percent"].mean()))
    print("      Median : {:.2f}%".format(df["soh_percent"].median()))
    print("      P25    : {:.2f}%".format(df["soh_percent"].quantile(0.25)))
    print("      P75    : {:.2f}%".format(df["soh_percent"].quantile(0.75)))

    # 7 ── Module 1 files unmodified
    print("\n" + SEP)
    print("[7/9] MODULE 1 FILES - UNMODIFIED VERIFICATION")
    print(SEP)
    _ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    frozen_files = [
        M1_MODEL_PATH, M1_PREDICTIONS_PATH,
        os.path.join(_ROOT, "module2", "Build", "api.py"),
        os.path.join(_ROOT, "module1", "battery_dataset_clean.csv"),
        os.path.join(_ROOT, "module1", "battery_dataset_features.csv"),
    ]
    all_ok = True
    for fp in frozen_files:
        exists = os.path.isfile(fp)
        status = "EXISTS (untouched)" if exists else "MISSING!"
        if not exists:
            all_ok = False
        print("      {:<25} : {}".format(status, fp))
    result_msg = "ALL FROZEN FILES INTACT [OK]" if all_ok else "WARNING - MISSING FILES!"
    print("\n      Result: " + result_msg)

    # 8 ── SoH grounding audit
    print("\n" + SEP)
    print("[8/9] SoH GROUNDING AUDIT - No independent SoH fabrication")
    print(SEP)
    src_ids = df["source_battery_id"].unique()
    valid_batteries = set(pd.read_csv(M1_PREDICTIONS_PATH)["Battery_ID"].unique())
    unknown = set(src_ids) - valid_batteries
    print("      Unique source batteries in generated set : {}".format(len(src_ids)))
    print("      Valid batteries in test_predictions.csv  : {}".format(len(valid_batteries)))
    print("      Unknown source batteries (should be 0)   : {}".format(len(unknown)))
    audit_msg = "GROUNDING VERIFIED [OK]" if len(unknown) == 0 else "AUDIT FAILED!"
    print("      Result: " + audit_msg)

    # 9 ── Bounds verification
    print("\n" + SEP)
    print("[9/9] BOUNDS VERIFICATION")
    print(SEP)

    checks = {
        "initial_soc_percent  in [20, 92]":
            df["initial_soc_percent"].between(20.0, 92.0).all(),
        "trip_distance_km     in [5, 150]":
            df["trip_distance_km"].between(5.0, 150.0).all(),
        "ambient_temp_c       in [12, 42]":
            df["ambient_temperature_c"].between(12.0, 42.0).all(),
        "load_kg              in [70, 350]":
            df["load_kg"].between(MIN_LOAD_KG, MAX_LOAD_KG).all(),
        "latitude             in Pune bbox":
            df["latitude"].between(LAT_MIN, LAT_MAX).all(),
        "longitude            in Pune bbox":
            df["longitude"].between(LON_MIN, LON_MAX).all(),
        "soh_percent          > 0":
            (df["soh_percent"] > 0).all(),
        "estimated_range_km   > 0":
            (df["estimated_usable_range_km"] > 0).all(),
        "terrain valid labels":
            df["terrain"].isin(["FLAT", "HILLY", "MOUNTAIN"]).all(),
        "vehicle_id consistent":
            (df["vehicle_id"] == VEHICLE_ID).all(),
        "battery_capacity_kwh consistent":
            (df["battery_capacity_kwh"] == BATTERY_CAPACITY_KWH).all(),
        "rated_range_km consistent":
            (df["rated_range_km"] == RATED_RANGE_KM).all(),
    }

    all_passed = True
    for check, passed in checks.items():
        icon = "[PASS]" if passed else "[FAIL]"
        if not passed:
            all_passed = False
        print("      {}  {}".format(icon, check))

    print("\n" + SEP)
    overall = "ALL CHECKS PASSED [OK]" if all_passed else "SOME CHECKS FAILED - REVIEW ABOVE"
    print("  PHASE 1 RESULT: " + overall)
    print(SEP + "\n")


if __name__ == "__main__":
    main()
