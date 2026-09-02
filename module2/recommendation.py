import pandas as pd
from module2.config import BASE_ENERGY_KWH_PER_KM, SAFETY_RESERVE_SOC_PCT, CHARGING_EFFICIENCY

def get_recommendation(
    trip_id,
    vehicle_id,
    soh_percent,
    initial_soc_percent,
    battery_capacity_kwh,
    trip_energy_demand_kwh,
    effective_trip_demand_km,
    available_range_km,
    estimated_usable_range_km,
    range_margin_km,
    fuzzy_urgency,
    trip_feasible_without_charging=None
):
    # 2. PHYSICAL FEASIBILITY
    if trip_feasible_without_charging is not None:
        charging_required = not trip_feasible_without_charging
    else:
        charging_required = range_margin_km < 0

    # 3. ENERGY DEFICIT
    # Use Module 1 range model as authoritative
    range_deficit_km = max(0.0, effective_trip_demand_km - available_range_km)
    energy_deficit_kwh = range_deficit_km * BASE_ENERGY_KWH_PER_KM
    
    # Calculate degraded battery capacity in kWh based on Module 1's estimated range at 100% SOC
    degraded_battery_capacity_kwh = estimated_usable_range_km * BASE_ENERGY_KWH_PER_KM
    
    # The maximum energy that can physically be added to the battery in a single pre-trip charge
    max_addable_battery_energy_kwh = degraded_battery_capacity_kwh * ((100.0 - initial_soc_percent) / 100.0)
    
    # FULL CHARGE SUFFICIENT CHECK
    tol = 1e-4
    full_charge_sufficient = energy_deficit_kwh <= max_addable_battery_energy_kwh + tol
    
    # Cap the battery energy deficit to what the battery can actually hold right now
    capped_energy_deficit_kwh = min(energy_deficit_kwh, max_addable_battery_energy_kwh)
    
    # 4. CHARGING ENERGY REQUIRED
    if capped_energy_deficit_kwh <= 0:
        charging_requirement_kwh = 0.0
    else:
        charging_requirement_kwh = capped_energy_deficit_kwh / CHARGING_EFFICIENCY
        
    # 5. RECOMMENDED SOC
    # SOC needed for trip derived from the authoritative Module 1 degraded usable range model
    if estimated_usable_range_km > 0:
        soc_needed_for_trip = (effective_trip_demand_km / estimated_usable_range_km) * 100.0
    else:
        soc_needed_for_trip = 0.0
        
    recommended_soc_percent = soc_needed_for_trip + SAFETY_RESERVE_SOC_PCT
    recommended_soc_percent = max(SAFETY_RESERVE_SOC_PCT, min(100.0, recommended_soc_percent))
    
    # If full charge is not sufficient, explicitly max out the recommendation
    if not full_charge_sufficient:
        recommended_soc_percent = 100.0
        
    # 6. ADDITIONAL SOC REQUIRED
    additional_soc_required = max(0.0, recommended_soc_percent - initial_soc_percent)
    
    # 8. COMBINE PHYSICAL FEASIBILITY + FUZZY URGENCY
    charging_recommended = False
    recommendation_text = ""
    
    if charging_required: # CASE A (covers range_margin_km < 0)
        charging_recommended = True
        if not full_charge_sufficient:
            recommendation_text = "Even at full charge, the planned trip exceeds the vehicle's usable range. Use an intermediate charging stop, reduce trip demand, or select an alternative route."
        elif fuzzy_urgency >= 85:
            recommendation_text = "CRITICAL: Charge before starting the trip."
        elif fuzzy_urgency >= 60:
            recommendation_text = "HIGH: Charging is required before the trip."
        else:
            recommendation_text = "CHARGE: Available range is insufficient for the planned trip."
    else:
        if fuzzy_urgency < 40: # CASE B
            charging_recommended = False
            recommendation_text = "No charging required. Current battery state is sufficient for the planned trip."
        elif fuzzy_urgency < 60: # CASE C
            charging_recommended = True
            recommendation_text = "MEDIUM: Trip is feasible, but partial charging is recommended as a precaution."
        else: # CASE D
            charging_recommended = True
            recommendation_text = "HIGH: Trip is currently feasible, but charging is strongly recommended before departure."
            
    return {
        "trip_id": trip_id,
        "vehicle_id": vehicle_id,
        "fuzzy_urgency": fuzzy_urgency,
        "charging_required": charging_required,
        "charging_recommended": charging_recommended,
        "full_charge_sufficient": full_charge_sufficient,
        "energy_deficit_kwh": energy_deficit_kwh, # We output the full deficit as requested
        "charging_requirement_kwh": charging_requirement_kwh, # We output the grid charging requirement (capped)
        "recommended_soc_percent": recommended_soc_percent,
        "additional_soc_required": additional_soc_required,
        "range_margin_km": range_margin_km,
        "recommendation": recommendation_text,
        "max_addable_battery_energy_kwh": max_addable_battery_energy_kwh
    }
