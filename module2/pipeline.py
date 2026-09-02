import pandas as pd
from typing import Dict, Any

from module2.adapter import Module1Adapter
from module2.energy_model import TripEnergyDemandModel
from module2.margin_calculator import RangeMarginCalculator
from module2.fuzzy_system import build_fuzzy_system, get_urgency
from module2.recommendation import get_recommendation
from module2.config import VEHICLE_ID, BATTERY_CAPACITY_KWH, RATED_RANGE_KM

class RecommendationPipeline:
    def __init__(self):
        self.adapter = Module1Adapter()
        self.energy_model = TripEnergyDemandModel()
        self.margin_calc = RangeMarginCalculator()
        self.simulator, _, _, _, _, _, _ = build_fuzzy_system()

    def process_batch(self, df_phase1: pd.DataFrame) -> pd.DataFrame:
        """
        Process a batch of trips starting from Phase 1 inputs.
        """
        # Step 2: Energy Demand Model
        df = self.energy_model.compute_batch(df_phase1)
        
        # Step 3: Range Margin Calculator
        df = self.margin_calc.compute_batch(df)
        
        # Step 4 & 5: Fuzzy System and Recommendation Engine
        recommendations = []
        for _, row in df.iterrows():
            urg = get_urgency(
                self.simulator, 
                row['soh_percent'], 
                row['initial_soc_percent'], 
                row['effective_trip_demand_km'], 
                row['range_margin_km']
            )
            
            rec = get_recommendation(
                trip_id=row['trip_id'],
                vehicle_id=row['vehicle_id'],
                soh_percent=row['soh_percent'],
                initial_soc_percent=row['initial_soc_percent'],
                battery_capacity_kwh=row['battery_capacity_kwh'],
                trip_energy_demand_kwh=row['trip_energy_demand_kwh'],
                effective_trip_demand_km=row['effective_trip_demand_km'],
                available_range_km=row['available_range_km'],
                estimated_usable_range_km=row['estimated_usable_range_km'],
                range_margin_km=row['range_margin_km'],
                fuzzy_urgency=urg,
                trip_feasible_without_charging=row['trip_feasible_without_charging']
            )
            recommendations.append(rec)
            
        rec_df = pd.DataFrame(recommendations)
        
        # Combine all columns, avoiding duplication
        cols_to_add = [c for c in rec_df.columns if c not in df.columns]
        for col in cols_to_add:
            df[col] = rec_df[col]
            
        if 'fuzzy_urgency' not in df.columns and 'fuzzy_urgency' in rec_df.columns:
            df['fuzzy_urgency'] = rec_df['fuzzy_urgency']
            
        return df

    def process_single(self, trip_request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single trip request.
        """
        # Module 1 adapter check for soh and estimated range
        if 'soh_percent' not in trip_request:
            df_tel = pd.DataFrame([trip_request])
            preds = self.adapter.predict_batch(df_tel, RATED_RANGE_KM)
            trip_request['soh_percent'] = float(preds.iloc[0]['soh_percent'])
            trip_request['estimated_usable_range_km'] = float(preds.iloc[0]['estimated_usable_range_km'])
            
        # Energy Demand
        energy = self.energy_model.compute_single(
            trip_distance_km=trip_request['trip_distance_km'],
            ambient_temperature_c=trip_request['ambient_temperature_c'],
            terrain=trip_request['terrain'],
            load_kg=trip_request['load_kg']
        )
        trip_request.update(energy)
        
        # Range Margin
        margin = self.margin_calc.compute_single(
            estimated_usable_range_km=trip_request['estimated_usable_range_km'],
            initial_soc_percent=trip_request['initial_soc_percent'],
            effective_trip_demand_km=trip_request['effective_trip_demand_km']
        )
        trip_request.update(margin)
        
        # Fuzzy Urgency
        urg = get_urgency(
            self.simulator,
            trip_request['soh_percent'],
            trip_request['initial_soc_percent'],
            trip_request['effective_trip_demand_km'],
            trip_request['range_margin_km']
        )
        
        # Recommendation
        rec = get_recommendation(
            trip_id=trip_request.get('trip_id', 'single-trip'),
            vehicle_id=trip_request.get('vehicle_id', VEHICLE_ID),
            soh_percent=trip_request['soh_percent'],
            initial_soc_percent=trip_request['initial_soc_percent'],
            battery_capacity_kwh=trip_request.get('battery_capacity_kwh', BATTERY_CAPACITY_KWH),
            trip_energy_demand_kwh=trip_request['trip_energy_demand_kwh'],
            effective_trip_demand_km=trip_request['effective_trip_demand_km'],
            available_range_km=trip_request['available_range_km'],
            estimated_usable_range_km=trip_request['estimated_usable_range_km'],
            range_margin_km=trip_request['range_margin_km'],
            fuzzy_urgency=urg,
            trip_feasible_without_charging=trip_request['trip_feasible_without_charging']
        )
        
        result = trip_request.copy()
        result.update(rec)
        return result
