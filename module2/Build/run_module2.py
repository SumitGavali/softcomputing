import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

def run_demo():
    print("=" * 50)
    print("MODULE 2 DEMO")
    print("=" * 50)
    
    from module2.pipeline import RecommendationPipeline
    
    req = {
        "trip_id": "demo-trip-001",
        "vehicle_id": "URBAN_EV_30",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "initial_soc_percent": 80.0,
        "trip_distance_km": 120.0,
        "ambient_temperature_c": 35.0,
        "terrain": "HILLY",
        "load_kg": 200.0,
        "battery_telemetry": {
            "discharge_index": 50,
            "ambient_temperature": 35.0,
            "max_temp_reached": 45.0,
            "charge_rate_proxy": 5.0,
            "time_since_reset_cycles": 2.0,
            "internal_resistance_re": 0.08
        }
    }
    
    pipeline = RecommendationPipeline()
    
    flat_req = req.copy()
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
            
    res = pipeline.process_single(flat_req)
    
    print(f"\nTrip ID:\n{res['trip_id']}")
    print(f"Vehicle ID:\n{res['vehicle_id']}")
    
    print("\nBattery Health")
    print(f"SoH:\n{res['soh_percent']:.2f}%")
    print(f"Estimated usable range:\n{res['estimated_usable_range_km']:.2f} km")
    
    print("\nTrip")
    print(f"Distance:\n{req['trip_distance_km']} km")
    print(f"Terrain:\n{req['terrain']}")
    print(f"Temperature:\n{req['ambient_temperature_c']} C")
    print(f"Load:\n{req['load_kg']} kg")
    print(f"Initial SOC:\n{req['initial_soc_percent']}%")
    
    print("\nAnalysis")
    print(f"Energy demand:\n{res['trip_energy_demand_kwh']:.2f} kWh")
    print(f"Effective demand:\n{res['effective_trip_demand_km']:.2f} km")
    print(f"Available range:\n{res['available_range_km']:.2f} km")
    print(f"Range margin:\n{res['range_margin_km']:.2f} km")
    
    print("\nFuzzy Intelligence")
    print(f"Charging urgency:\n{res['fuzzy_urgency']:.2f}")
    
    print("\nRecommendation")
    print(f"Charging required:\n{res['charging_required']}")
    print(f"Charging recommended:\n{res['charging_recommended']}")
    print(f"Charging requirement:\n{res['charging_requirement_kwh']:.2f} kWh")
    print(f"Minimum recommended starting SOC:\n{res['recommended_soc_percent']:.2f}%")
    print(f"Additional SOC required:\n{res['additional_soc_required']:.2f}%")
    print(f"Full charge sufficient:\n{res['full_charge_sufficient']}")
    
    print(f"\nFINAL RECOMMENDATION:\n{res['recommendation']}")
    print("\n" + "=" * 50)


def run_batch():
    print("=" * 50)
    print("MODULE 2 BATCH PIPELINE")
    print("=" * 50)
    from module2.pipeline import RecommendationPipeline
    from module2.synthetic_data import SyntheticTripGenerator
    
    pipeline = RecommendationPipeline()
    generator = SyntheticTripGenerator(pipeline.adapter, seed=42)
    
    print("\nGenerating 5,000 synthetic trips...")
    df_phase1 = generator.generate(5000)
    
    print("Running integrated batch pipeline...")
    start = time.time()
    df_result = pipeline.process_batch(df_phase1)
    runtime = time.time() - start
    
    out_path = "module2/data/phase5_full_pipeline.csv"
    cols_to_save = [c for c in df_result.columns if c != 'max_addable_battery_energy_kwh']
    df_result[cols_to_save].to_csv(out_path, index=False)
    print(f"Saved dataset to {out_path}\n")
    
    req_count = df_result['charging_required'].sum()
    rec_count = df_result['charging_recommended'].sum()
    no_charge = len(df_result) - rec_count
    fc_insuf = (~df_result['full_charge_sufficient']).sum()
    
    print(f"- total trips: {len(df_result)}")
    print(f"- charging required: {req_count}")
    print(f"- charging recommended: {rec_count}")
    print(f"- no charging: {no_charge}")
    print(f"- full-charge insufficient: {fc_insuf}")
    print(f"- mean charging energy: {df_result['charging_requirement_kwh'].mean():.2f} kWh")
    print(f"- median charging energy: {df_result['charging_requirement_kwh'].median():.2f} kWh")
    print(f"- mean recommended SOC: {df_result['recommended_soc_percent'].mean():.2f}%")
    print(f"- median recommended SOC: {df_result['recommended_soc_percent'].median():.2f}%")
    
    print(f"\nCompleted in {runtime:.2f}s")
    print("=" * 50)


def run_validate():
    print("=" * 50)
    print("MODULE 2 VALIDATION")
    print("=" * 50 + "\n")
    
    scripts = {
        "Phase 1": "run_phase1.py",
        "Phase 2": "run_phase2.py",
        "Phase 3": "validate_fuzzy.py",
        "Phase 4": "run_phase4.py",
        "Phase 5": "run_phase5.py",
        "Phase 6": "run_phase6.py"
    }
    
    all_passed = True
    for phase, script in scripts.items():
        if not os.path.exists(script):
            print(f"{phase:<13} FAIL (Script missing: {script})")
            all_passed = False
            continue
            
        # Run subprocess
        res = subprocess.run([sys.executable, script], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"{phase:<13} PASS")
        else:
            print(f"{phase:<13} FAIL")
            print(f"\nFAILED:\n{phase}")
            print(f"\nERROR:\n{res.stderr.strip() or res.stdout.strip()}\n")
            all_passed = False
            break

    print("\nOverall:")
    if all_passed:
        print("MODULE 2 VALIDATION PASSED")
    else:
        print("MODULE 2 VALIDATION FAILED")


def run_api():
    print("=" * 50)
    print("MODULE 2 API")
    print("=" * 50)
    print("\nServer starting...")
    print("\nSwagger:\nhttp://127.0.0.1:8000/docs")
    print("\nHealth:\nhttp://127.0.0.1:8000/module2/health")
    print("\nTrip prediction:\nPOST /module2/predict/trip-charging\n")
    
    try:
        # Since the user integrated the router into api.py, we run api:app
        uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=False)
    except ModuleNotFoundError as e:
        if "uvicorn" in str(e) or "fastapi" in str(e):
            print("Error: FastAPI/Uvicorn not found. Please install the required dependencies.")
        else:
            raise


def print_help():
    print("=" * 50)
    print("EV RANGE INTELLIGENCE — MODULE 2")
    print("=" * 50)
    print("\nUsage:")
    print("\npython run_module2.py demo")
    print("    Run one example trip")
    print("\npython run_module2.py batch")
    print("    Run the 5,000-trip integrated pipeline")
    print("\npython run_module2.py validate")
    print("    Run the complete validation suite")
    print("\npython run_module2.py api")
    print("    Start the FastAPI server")
    print("\n" + "=" * 50)


def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)
        
    command = sys.argv[1].lower()
    
    try:
        if command == "demo":
            run_demo()
        elif command == "batch":
            run_batch()
        elif command == "validate":
            run_validate()
        elif command == "api":
            run_api()
        else:
            print_help()
            sys.exit(0)
    except ImportError as e:
        print(f"Error: Missing dependency. {e}")
        print("Please ensure all requirements (fastapi, uvicorn, scikit-fuzzy, pandas, etc.) are installed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
