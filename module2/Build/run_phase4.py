import os
import sys
import pandas as pd
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from module2.recommendation import get_recommendation
from module2.fuzzy_system import build_fuzzy_system, get_urgency
import time

def main():
    print("Loading Phase 2 data...")
    data_path = os.path.join(_ROOT, "module2", "data", "phase2_trip_analysis.csv")
    df = pd.read_csv(data_path)
    
    print("Building FIS...")
    simulator, _, _, _, _, _, _ = build_fuzzy_system()
    
    recommendations = []
    
    print(f"Processing {len(df)} trips...")
    start_time = time.time()
    for idx, row in df.iterrows():
        if idx > 0 and idx % 500 == 0:
            print(f"Processed {idx} / {len(df)} trips...")
            
        soh = row['soh_percent']
        soc = row['initial_soc_percent']
        demand = row['effective_trip_demand_km'] 
        margin = row['range_margin_km']
        
        urg = get_urgency(simulator, soh, soc, demand, margin)
        
        rec = get_recommendation(
            trip_id=row['trip_id'],
            vehicle_id=row['vehicle_id'],
            soh_percent=soh,
            initial_soc_percent=soc,
            battery_capacity_kwh=row['battery_capacity_kwh'],
            trip_energy_demand_kwh=row['trip_energy_demand_kwh'],
            effective_trip_demand_km=demand,
            available_range_km=row['available_range_km'],
            estimated_usable_range_km=row['estimated_usable_range_km'],
            range_margin_km=margin,
            fuzzy_urgency=urg,
            trip_feasible_without_charging=row['trip_feasible_without_charging']
        )
        recommendations.append(rec)
        
    print(f"Processed in {time.time() - start_time:.1f}s")
    
    rec_df = pd.DataFrame(recommendations)
    
    new_cols = ['fuzzy_urgency', 'charging_required', 'charging_recommended', 'full_charge_sufficient',
                'energy_deficit_kwh', 'charging_requirement_kwh', 
                'recommended_soc_percent', 'additional_soc_required', 'recommendation']
                
    for col in new_cols:
        df[col] = rec_df[col]
        
    # We also keep max_addable_battery_energy_kwh to test invariants easily
    df['max_addable_battery_energy_kwh'] = rec_df['max_addable_battery_energy_kwh']
        
    output_path = "module2/data/phase4_recommendations.csv"
    
    # Save but without max_addable_battery_energy_kwh since it was not requested
    cols_to_save = list(df.columns)
    cols_to_save.remove('max_addable_battery_energy_kwh')
    df[cols_to_save].to_csv(output_path, index=False)
    print(f"Saved {output_path}")
    
    # Validation Invariants
    print("\n--- Invariant Validations ---")
    
    t1 = ((df['range_margin_km'] < 0) & (~df['charging_required'])).sum()
    t1_2 = ((df['range_margin_km'] < 0) & (df['energy_deficit_kwh'] > 0) & (df['charging_requirement_kwh'] <= 0)).sum()
    print(f"TEST 1 Violations: {t1 + t1_2} (Expected 0)")
    
    t2 = ((df['range_margin_km'] >= 0) & (df['charging_required'])).sum()
    print(f"TEST 2 Violations: {t2} (Expected 0)")
    
    t3 = ((~df['charging_required']) & (~df['charging_recommended']) & (df['charging_requirement_kwh'] != 0)).sum()
    print(f"TEST 3 Violations: {t3} (Expected 0)")
    
    t4 = (df['charging_requirement_kwh'] < 0).sum()
    print(f"TEST 4 Violations: {t4} (Expected 0)")
    
    t5 = ((df['recommended_soc_percent'] < 15) | (df['recommended_soc_percent'] > 100)).sum()
    print(f"TEST 5 Violations: {t5} (Expected 0)")
    
    t6 = (df['additional_soc_required'] < 0).sum()
    print(f"TEST 6 Violations: {t6} (Expected 0)")

    tol = 1e-4
    t7 = ((df['energy_deficit_kwh'] <= df['max_addable_battery_energy_kwh'] + tol) & (~df['full_charge_sufficient'])).sum()
    print(f"TEST 7 Violations: {t7} (Expected 0)")
    
    t8 = ((df['energy_deficit_kwh'] > df['max_addable_battery_energy_kwh'] + tol) & (df['full_charge_sufficient'])).sum()
    print(f"TEST 8 Violations: {t8} (Expected 0)")
    
    t9 = ((~df['full_charge_sufficient']) & (df['recommended_soc_percent'] != 100)).sum()
    print(f"TEST 9 Violations: {t9} (Expected 0)")
    
    t10 = ((~df['charging_required']) & (~df['full_charge_sufficient'])).sum()
    print(f"TEST 10 Violations: {t10} (Expected 0)")

    # Validations Output
    print("\n--- Validation Report ---")
    print(f"1. Total trips: {len(df)}")
    
    req_count = df['charging_required'].sum()
    print(f"2. Charging-required count: {req_count}")
    
    rec_count = df['charging_recommended'].sum()
    print(f"3. Charging-recommended count: {rec_count}")
    
    no_charge_count = len(df) - rec_count
    print(f"4. No-charging count: {no_charge_count}")
    
    print(f"5. Mean charging energy (grid-side): {df['charging_requirement_kwh'].mean():.2f}")
    print(f"6. Median charging energy (grid-side): {df['charging_requirement_kwh'].median():.2f}")
    print(f"7. Maximum charging energy (grid-side): {df['charging_requirement_kwh'].max():.2f}")
    
    print(f"8. Mean recommended SOC: {df['recommended_soc_percent'].mean():.2f}")
    print(f"9. Median recommended SOC: {df['recommended_soc_percent'].median():.2f}")
    
    c10 = ((df['charging_required'] == True) & (df['charging_requirement_kwh'] == 0)).sum()
    print(f"10. Number of charging-required rows with zero charging energy: {c10}")
    
    c11 = ((df['charging_required'] == True) & (df['range_margin_km'] >= 0)).sum()
    print(f"11. Number of rows where charging_required = True AND range_margin_km >= 0: {c11}")
    
    c12 = ((df['charging_required'] == True) & (df['charging_requirement_kwh'] <= 0)).sum()
    print(f"12. Number of rows where charging_required = True AND charging_requirement_kwh <= 0: {c12}")
    
    fc_true = df['full_charge_sufficient'].sum()
    fc_false = (~df['full_charge_sufficient']).sum()
    print(f"Count of full_charge_sufficient = True: {fc_true}")
    print(f"Count of full_charge_sufficient = False: {fc_false}")
    print(f"Percentage of trips where full charge is insufficient: {fc_false / len(df) * 100:.2f}%")
    
    if fc_false > 0:
        print("\nExamples of full-charge-insufficient cases:")
        insuf_df = df[~df['full_charge_sufficient']]
        cols_to_show = ['trip_id', 'soh_percent', 'initial_soc_percent', 'effective_trip_demand_km', 'available_range_km', 'range_margin_km', 'energy_deficit_kwh', 'recommendation']
        print(insuf_df[cols_to_show].head(3).to_string(index=False))
        
        print(f"Maximum effective demand among those cases: {insuf_df['effective_trip_demand_km'].max():.2f} km")
        print(f"Minimum range margin among those cases: {insuf_df['range_margin_km'].min():.2f} km")

if __name__ == '__main__':
    main()
