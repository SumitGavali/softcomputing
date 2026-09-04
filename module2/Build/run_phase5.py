import os
import sys
import time
import pandas as pd
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from module2.pipeline import RecommendationPipeline
from module2.synthetic_data import SyntheticTripGenerator

def main():
    SEED = 42
    
    print("--- RUNNING PHASE 5 PIPELINE ---")
    pipeline = RecommendationPipeline()
    generator = SyntheticTripGenerator(pipeline.adapter, seed=SEED)
    
    # 1. Batch mode
    print(f"Generating 5000 synthetic trips with seed: {SEED}")
    df_phase1 = generator.generate(5000)
    
    print("Running batch pipeline...")
    start_time = time.time()
    df_result = pipeline.process_batch(df_phase1)
    end_time = time.time()
    
    runtime = end_time - start_time
    avg_time = runtime / 5000 * 1000 # ms per trip
    
    print(f"Batch completed in {runtime:.2f}s ({avg_time:.2f}ms/trip)")
    
    out_path = "module2/data/phase5_full_pipeline.csv"
    
    cols_to_save = list(df_result.columns)
    if 'max_addable_battery_energy_kwh' in cols_to_save:
        cols_to_save.remove('max_addable_battery_energy_kwh')
        
    df_result[cols_to_save].to_csv(out_path, index=False)
    print(f"Saved dataset to {out_path} with shape {df_result[cols_to_save].shape}")
    
    # 2. Batch/Single consistency check & Validation
    print("\n--- VALIDATION TESTS ---")
    
    # Check shape
    print(f"A. Number of trips = {len(df_result)} (Expected 5000)")
    
    nan_count = df_result.isna().sum().sum()
    print(f"B. No NaN values in calculated outputs: {nan_count == 0}")
    
    inf_count = np.isinf(df_result.select_dtypes(include=[np.number])).sum().sum()
    print(f"C. No infinite values: {inf_count == 0}")
    
    test_d = ((df_result['range_margin_km'] < 0) & (~df_result['charging_required'])).sum() == 0
    print(f"D. charging_required == True whenever range_margin < 0: {test_d}")
    
    test_e = ((df_result['range_margin_km'] >= 0) & (df_result['charging_required'])).sum() == 0
    print(f"E. charging_required == False whenever range_margin >= 0: {test_e}")
    
    test_f = ((df_result['charging_required']) & (df_result['charging_requirement_kwh'] <= 0)).sum() == 0
    print(f"F. charging_required=True implies charging_requirement_kwh > 0: {test_f}")
    
    test_g = ((df_result['recommended_soc_percent'] < 15) | (df_result['recommended_soc_percent'] > 100)).sum() == 0
    print(f"G. recommended_soc_percent is between 15 and 100: {test_g}")
    
    test_h = (df_result['additional_soc_required'] < 0).sum() == 0
    print(f"H. additional_soc_required >= 0: {test_h}")
    
    tol = 1e-4
    test_i = ((df_result['energy_deficit_kwh'] <= df_result['max_addable_battery_energy_kwh'] + tol) & (~df_result['full_charge_sufficient'])).sum() == 0
    test_i2 = ((df_result['energy_deficit_kwh'] > df_result['max_addable_battery_energy_kwh'] + tol) & (df_result['full_charge_sufficient'])).sum() == 0
    print(f"I. full_charge_sufficient behaves according to Phase 4 invariants: {test_i and test_i2}")
    
    test_j = ((df_result['fuzzy_urgency'] < 0) | (df_result['fuzzy_urgency'] > 100)).sum() == 0
    print(f"J. fuzzy urgency remains between 0 and 100: {test_j}")
    
    # Cross Phase Consistency
    try:
        df_p4 = pd.read_csv("module2/data/phase4_recommendations.csv")
        diff_margin = (df_result['range_margin_km'] - df_p4['range_margin_km']).abs().max()
        diff_urgency = (df_result['fuzzy_urgency'] - df_p4['fuzzy_urgency']).abs().max()
        diff_rec = (df_result['recommendation'] != df_p4['recommendation']).sum()
        
        print("\n--- CROSS-PHASE CONSISTENCY ---")
        print(f"  Range margin max diff: {diff_margin:.6f} (Expected 0.0)")
        print(f"  Fuzzy urgency max diff: {diff_urgency:.6f} (Expected 0.0)")
        print(f"  Recommendation mismatches: {diff_rec} (Expected 0)")
    except Exception as e:
        print("Could not compare with Phase 4 data:", e)

    print("\n--- SINGLE TRIP TESTS ---")
    def run_single(name, req):
        print(f"\n[{name}]")
        res = pipeline.process_single(req)
        print(f"  Urgency: {res['fuzzy_urgency']:.1f}")
        print(f"  Margin: {res['range_margin_km']:.1f} km")
        print(f"  Charging Req: {res['charging_required']}")
        print(f"  Full Charge Sufficient: {res['full_charge_sufficient']}")
        print(f"  Rec SOC: {res['recommended_soc_percent']:.1f}%")
        print(f"  Msg: {res['recommendation']}")

    req_a = {
        'soh_percent': 95.0,
        'estimated_usable_range_km': 190.0,
        'initial_soc_percent': 90.0,
        'trip_distance_km': 10.0,
        'ambient_temperature_c': 25.0,
        'terrain': 'FLAT',
        'load_kg': 150.0
    }
    run_single("TEST A: Healthy battery + high SOC + short trip + large margin", req_a)

    req_b = {
        'soh_percent': 95.0,
        'estimated_usable_range_km': 190.0,
        'initial_soc_percent': 20.0,
        'trip_distance_km': 150.0,
        'ambient_temperature_c': 25.0,
        'terrain': 'FLAT',
        'load_kg': 150.0
    }
    run_single("TEST B: Healthy battery + low SOC + long trip + negative margin", req_b)
    
    req_c = {
        'soh_percent': 30.0,
        'estimated_usable_range_km': 60.0,
        'initial_soc_percent': 90.0,
        'trip_distance_km': 10.0,
        'ambient_temperature_c': 25.0,
        'terrain': 'FLAT',
        'load_kg': 150.0
    }
    run_single("TEST C: Severely degraded battery + high SOC + short trip", req_c)

    req_d = {
        'soh_percent': 30.0,
        'estimated_usable_range_km': 60.0,
        'initial_soc_percent': 90.0,
        'trip_distance_km': 100.0,
        'ambient_temperature_c': 25.0,
        'terrain': 'FLAT',
        'load_kg': 150.0
    }
    run_single("TEST D: Severely degraded battery + insufficient range even at full charge", req_d)
    
    req_e = {
        'soh_percent': 80.0,
        'estimated_usable_range_km': 160.0,
        'initial_soc_percent': 40.0,
        'trip_distance_km': 30.0, 
        'ambient_temperature_c': 25.0,
        'terrain': 'FLAT',
        'load_kg': 150.0
    }
    run_single("TEST E: Borderline positive range margin", req_e)

    print("\n--- REPRODUCIBILITY TEST ---")
    gen2 = SyntheticTripGenerator(pipeline.adapter, seed=999)
    df_p1_rep1 = gen2.generate(5)
    df_res_rep1 = pipeline.process_batch(df_p1_rep1)
    
    gen3 = SyntheticTripGenerator(pipeline.adapter, seed=999)
    df_p1_rep2 = gen3.generate(5)
    df_res_rep2 = pipeline.process_batch(df_p1_rep2)
    
    diff = (df_res_rep1['range_margin_km'] - df_res_rep2['range_margin_km']).abs().sum()
    print(f"Reproducibility test (same seed -> same 5 trips diff): {diff:.5f} (Expected 0.0)")

if __name__ == '__main__':
    main()
