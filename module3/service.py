"""
module3/service.py
==================
Orchestration Service for Module 3.
Connects fleet telemetry from Module 1 & 2, spatial deficit clustering,
charging station optimization, and temporal demand forecasting.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np

from module3.config import (
    MODULE3_DATA_DIR,
    CACHE_TRIPS_FILE,
    STATION_RECOMMENDATIONS_FILE,
    DEFAULT_NUM_STATIONS,
    STATION_COVERAGE_RADIUS_KM,
    MIN_STATION_DISTANCE_KM,
    LAT_MIN,
    LAT_MAX,
    LON_MIN,
    LON_MAX,
    compute_geographic_bounds,
)
from module3.clustering import DeficitClusterEngine, calculate_road_distance_km, haversine_distance
from module3.optimizer import StationPlacementOptimizer
from module3.demand_forecast import DemandForecaster

logger = logging.getLogger("module3_service")


class Module3Service:
    """
    Main business logic service powering Module 3 API and Fleet Dashboard.
    """

    def __init__(self):
        os.makedirs(MODULE3_DATA_DIR, exist_ok=True)
        self.cluster_engine = DeficitClusterEngine(
            coverage_radius_km=STATION_COVERAGE_RADIUS_KM
        )
        self.optimizer = StationPlacementOptimizer(
            coverage_radius_km=STATION_COVERAGE_RADIUS_KM,
            min_station_distance_km=MIN_STATION_DISTANCE_KM,
        )
        self.forecaster = DemandForecaster()
        self._df_trips: Optional[pd.DataFrame] = None
        self._stations_cache: Optional[List[Dict[str, Any]]] = None
        self._rec_cache: Dict[tuple, Dict[str, Any]] = {}

    def get_or_load_fleet_trips(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        Loads cached evaluated fleet trips, or generates and evaluates them if not present.
        """
        if self._df_trips is not None and not force_refresh:
            return self._df_trips

        if os.path.isfile(CACHE_TRIPS_FILE) and not force_refresh:
            logger.info("Loading cached fleet trips from %s", CACHE_TRIPS_FILE)
            self._df_trips = pd.read_csv(CACHE_TRIPS_FILE)
            if self._df_trips["vehicle_id"].nunique() <= 1:
                self._assign_fleet_vehicle_distribution(self._df_trips)
                self._df_trips.to_csv(CACHE_TRIPS_FILE, index=False)
            return self._df_trips

        logger.info("Generating and evaluating synthetic fleet trips...")
        # Try to use Module 2 pipeline if available
        try:
            from module2.pipeline import RecommendationPipeline
            from module2.synthetic_data import SyntheticTripGenerator

            pipeline = RecommendationPipeline()
            generator = SyntheticTripGenerator(adapter=pipeline.adapter, seed=42)
            raw_trips = generator.generate(num_trips=2500)
            df_evaluated = pipeline.process_batch(raw_trips)
            self._df_trips = df_evaluated
            self._assign_fleet_vehicle_distribution(self._df_trips)
            self._df_trips.to_csv(CACHE_TRIPS_FILE, index=False)
            logger.info("Successfully saved %d evaluated trips to %s", len(self._df_trips), CACHE_TRIPS_FILE)
            return self._df_trips
        except Exception as e:
            logger.warning("Falling back to standalone synthetic generator: %s", str(e))
            df_fallback = self._generate_fallback_fleet_trips(num_trips=2000)
            self._df_trips = df_fallback
            self._df_trips.to_csv(CACHE_TRIPS_FILE, index=False)
            return self._df_trips

    def _assign_fleet_vehicle_distribution(self, df: pd.DataFrame):
        """
        Assigns representative fleet vehicle IDs for a 120-vehicle fleet
        while strictly preserving Module 1's ML-predicted SoH values.
        """
        num_vehicles = 120
        vehicle_ids = [f"EV-PUNE-{i:03d}" for i in range(1, num_vehicles + 1)]

        if "soh_percent" in df.columns and not df["soh_percent"].isna().all():
            # Group trips into 120 vehicle cohorts ordered by Module 1's SoH predictions
            df_sorted = df.sort_values("soh_percent").reset_index(drop=False)
            trips_per_v = len(df) // num_vehicles
            remainder = len(df) % num_vehicles

            v_list = []
            for i, v_id in enumerate(vehicle_ids):
                count = trips_per_v + (1 if i < remainder else 0)
                v_list.extend([v_id] * count)

            df_sorted["vehicle_id"] = v_list
            # Restore original row ordering and assign back vehicle_id
            df["vehicle_id"] = df_sorted.sort_values("index")["vehicle_id"].values
            # DO NOT overwrite df["soh_percent"]! Module 1's ML prediction is preserved.
        else:
            np.random.seed(42)
            vehicle_sohs = {}
            for i in range(1, num_vehicles + 1):
                v_id = f"EV-PUNE-{i:03d}"
                r = np.random.rand()
                if r < 0.70:
                    base_soh = np.random.uniform(80.5, 96.0)
                elif r < 0.90:
                    base_soh = np.random.uniform(75.0, 79.9)
                else:
                    base_soh = np.random.uniform(64.0, 74.5)
                vehicle_sohs[v_id] = round(base_soh, 1)

            vehicle_ids_pool = list(vehicle_sohs.keys())
            assigned_vids = np.random.choice(vehicle_ids_pool, size=len(df))
            df["vehicle_id"] = assigned_vids
            df["soh_percent"] = [vehicle_sohs[v] for v in assigned_vids]

    def _generate_fallback_fleet_trips(self, num_trips: int = 2000) -> pd.DataFrame:
        """
        Robust generator grounded in authentic Pune commercial delivery road corridors.
        """
        from module3.pune_road_network import sample_road_network_coordinates
        from module3.config import URBAN_CIRCUITY_FACTOR

        lats, lons, corridors, zones = sample_road_network_coordinates(num_trips, seed=42)

        np.random.seed(42)
        # Trip distances represent driver odometer readings — already road distances.
        # Do NOT multiply by circuity factor here (that would double-count).
        distances = np.random.gamma(shape=2.5, scale=10.0, size=num_trips).clip(3.0, 90.0).round(1)

        soh_pcts = np.random.normal(loc=82.0, scale=8.0, size=num_trips).clip(55.0, 100.0)
        soc_pcts = np.random.uniform(15.0, 95.0, size=num_trips)

        terrains = np.random.choice(["FLAT", "HILLY", "MOUNTAIN"], size=num_trips, p=[0.70, 0.20, 0.10])
        demands_kwh = distances * 0.15 * np.where(terrains == "FLAT", 1.0, np.where(terrains == "HILLY", 1.15, 1.35))

        available_km = (soc_pcts / 100.0) * (soh_pcts / 100.0) * 200.0
        margins_km = available_km - distances
        charging_required = margins_km < 10.0

        # Urgency calculation
        urgencies = np.where(
            margins_km < -15.0,
            np.random.uniform(85.0, 100.0, num_trips),
            np.where(
                margins_km < 0.0,
                np.random.uniform(65.0, 85.0, num_trips),
                np.where(margins_km < 15.0, np.random.uniform(40.0, 65.0, num_trips), np.random.uniform(10.0, 35.0, num_trips))
            )
        )
        deficit_kwh = np.where(charging_required, np.maximum(1.5, -margins_km * 0.15), 0.0)

        return pd.DataFrame({
            "trip_id": [f"TRIP-{i:05d}" for i in range(num_trips)],
            "vehicle_id": "EV-PUNE-000",  # Placeholder; overwritten by _assign_fleet_vehicle_distribution
            "latitude": lats,
            "longitude": lons,
            "delivery_corridor": corridors,
            "zone": zones,
            "trip_distance_km": distances.round(1),
            "initial_soc_percent": soc_pcts.round(1),
            "soh_percent": soh_pcts.round(1),
            "terrain": terrains,
            "trip_energy_demand_kwh": demands_kwh.round(2),
            "available_range_km": available_km.round(1),
            "range_margin_km": margins_km.round(1),
            "fuzzy_urgency": urgencies.round(1),
            "charging_required": charging_required,
            "charging_requirement_kwh": deficit_kwh.round(2),
        })

    def get_station_recommendations(
        self,
        k_stations: int = DEFAULT_NUM_STATIONS,
        coverage_radius_km: float = STATION_COVERAGE_RADIUS_KM,
        towing_cost_inr: Optional[float] = None,
        deadhead_cost_per_km: Optional[float] = None,
        ac_cost_inr: Optional[float] = None,
        dc_cost_inr: Optional[float] = None,
        swap_cost_inr: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Executes full spatial optimization to recommend charging stations and ROI.
        Computes dynamic geographic bounding box and centroid from real telemetry.
        """
        cache_key = (
            k_stations,
            coverage_radius_km,
            towing_cost_inr,
            deadhead_cost_per_km,
            ac_cost_inr,
            dc_cost_inr,
            swap_cost_inr,
        )
        if cache_key in self._rec_cache:
            return self._rec_cache[cache_key]

        df_trips = self.get_or_load_fleet_trips()
        df_deficits = self.cluster_engine.extract_deficit_trips(df_trips)
        geo_bounds = compute_geographic_bounds(df_trips)

        # Update engines with custom radius if supplied
        self.cluster_engine.coverage_radius_km = coverage_radius_km
        self.optimizer.coverage_radius_km = coverage_radius_km

        capex_params = {}
        if ac_cost_inr is not None:
            capex_params["ac_cost_inr"] = float(ac_cost_inr)
        if dc_cost_inr is not None:
            capex_params["dc_cost_inr"] = float(dc_cost_inr)
        if swap_cost_inr is not None:
            capex_params["swap_cost_inr"] = float(swap_cost_inr)

        roi_params = {}
        if towing_cost_inr is not None:
            roi_params["towing_cost_per_incident"] = float(towing_cost_inr)
        if deadhead_cost_per_km is not None:
            roi_params["deadhead_cost_per_km"] = float(deadhead_cost_per_km)

        clusters = self.cluster_engine.cluster_deficits(df_trips)
        stations = self.optimizer.optimize_station_placements(
            clusters=clusters,
            df_deficits=df_deficits,
            k_stations=k_stations,
            capex_params=capex_params if capex_params else None,
        )
        roi = self.optimizer.compute_fleet_roi(
            stations=stations,
            df_deficits=df_deficits,
            roi_params=roi_params if roi_params else None,
        )

        result = {
            "status": "success",
            "k_stations_requested": k_stations,
            "coverage_radius_km": coverage_radius_km,
            "geographic_bounds": geo_bounds,
            "geographic_center": geo_bounds["center"],
            "stations": stations,
            "roi_analysis": roi,
            "total_fleet_deficits_count": len(df_deficits),
        }
        self._rec_cache[cache_key] = result
        return result


    def get_deficit_heatmap_points(self, limit: int = 1500) -> List[Dict[str, Any]]:
        """
        Returns geolocated deficit points with weight for interactive map heatmaps.
        """
        df_trips = self.get_or_load_fleet_trips()
        df_deficits = self.cluster_engine.extract_deficit_trips(df_trips)
        if df_deficits.empty:
            return []

        df_sample = df_deficits.head(limit)
        points = []
        for _, row in df_sample.iterrows():
            urgency = float(row.get("fuzzy_urgency", 50.0))
            kwh = float(row.get("charging_requirement_kwh", 2.0))
            # Normalized intensity 0.0 to 1.0
            weight = min(1.0, max(0.2, (urgency / 100.0) * 0.7 + (kwh / 15.0) * 0.3))
            points.append({
                "lat": round(float(row["latitude"]), 5),
                "lon": round(float(row["longitude"]), 5),
                "urgency": round(urgency, 1),
                "deficit_kwh": round(kwh, 2),
                "intensity": round(weight, 2),
                "trip_id": str(row.get("trip_id", "")),
                "vehicle_id": str(row.get("vehicle_id", "")),
            })
        return points

    def get_station_road_routes(
        self,
        station_id: str,
        limit: int = 15,
        k_stations: int = DEFAULT_NUM_STATIONS,
        coverage_radius_km: float = STATION_COVERAGE_RADIUS_KM,
    ) -> Dict[str, Any]:
        """
        Retrieves authentic turn-by-turn OpenStreetMap road driving routes for the assigned deficits
        of a specific charging station, traversing streets, bypasses, and bridges.
        Uses the same k_stations and coverage_radius_km as the user's current configuration.
        """
        from module3.routing import get_hub_assignment_routes

        recs = self.get_station_recommendations(
            k_stations=k_stations,
            coverage_radius_km=coverage_radius_km,
        )
        stations = recs.get("stations", [])
        target_station = next((s for s in stations if s["station_id"] == station_id), None)
        if not target_station:
            if stations:
                target_station = stations[0]
            else:
                return {"type": "FeatureCollection", "features": []}

        # Get deficit points
        deficits = self.get_deficit_heatmap_points(limit=800)
        # Filter deficits assigned to this station using Haversine distance
        # (matching the visual coverage circle and optimizer coverage check)
        assigned = []
        for d in deficits:
            dist = haversine_distance(
                target_station["latitude"], target_station["longitude"], d["lat"], d["lon"]
            )
            if dist <= target_station["coverage_radius_km"]:
                assigned.append(d)

        return get_hub_assignment_routes(target_station, assigned, max_routes=limit)

    def get_fleet_overview_metrics(self) -> Dict[str, Any]:
        """
        Returns high-level fleet health summary, SoH breakdown, and risk metrics.
        """
        df_trips = self.get_or_load_fleet_trips()
        total_trips = len(df_trips)

        # Vehicle unique level stats
        if "vehicle_id" in df_trips.columns:
            vehicles_df = df_trips.groupby("vehicle_id").agg({
                "soh_percent": "mean",
                "charging_required": "sum",
                "fuzzy_urgency": "mean",
            }).reset_index()
        else:
            vehicles_df = pd.DataFrame({"soh_percent": df_trips["soh_percent"]})

        total_vehicles = len(vehicles_df)
        avg_soh = float(vehicles_df["soh_percent"].mean())

        # Risk categories:
        # Healthy: SoH >= 80%
        # Monitor: 75% <= SoH < 80%
        # At-Risk: SoH < 75%
        healthy_count = int((vehicles_df["soh_percent"] >= 80.0).sum())
        monitor_count = int(((vehicles_df["soh_percent"] >= 75.0) & (vehicles_df["soh_percent"] < 80.0)).sum())
        at_risk_count = int((vehicles_df["soh_percent"] < 75.0).sum())

        at_risk_vehicles = []
        if "vehicle_id" in vehicles_df.columns:
            at_risk_df = vehicles_df[vehicles_df["soh_percent"] < 75.0].sort_values("soh_percent").head(10)
            for _, r in at_risk_df.iterrows():
                at_risk_vehicles.append({
                    "vehicle_id": r["vehicle_id"],
                    "soh_percent": round(float(r["soh_percent"]), 1),
                    "risk_level": "CRITICAL DEGRADATION" if r["soh_percent"] < 70.0 else "HIGH WEAR",
                    "action_required": "Schedule Cell Rebalancing / Pack Service",
                })

        total_deficits = int(df_trips["charging_required"].sum()) if "charging_required" in df_trips else 0
        total_energy_delivered = float(df_trips["trip_energy_demand_kwh"].sum()) if "trip_energy_demand_kwh" in df_trips else 0.0

        return {
            "total_fleet_vehicles": total_vehicles,
            "total_trips_analyzed": total_trips,
            "average_soh_percent": round(avg_soh, 1),
            "healthy_vehicles_count": healthy_count,
            "monitor_vehicles_count": monitor_count,
            "at_risk_vehicles_count": at_risk_count,
            "total_charging_deficits_logged": total_deficits,
            "total_energy_demanded_kwh": round(total_energy_delivered, 1),
            "at_risk_vehicle_roster": at_risk_vehicles,
        }

    def get_hourly_demand_forecast(self) -> Dict[str, Any]:
        """
        Returns 24-hour temporal charging load profile.
        """
        df_trips = self.get_or_load_fleet_trips()
        recs = self.get_station_recommendations()
        return self.forecaster.generate_hourly_demand_profile(df_trips, recs.get("stations", []))


service = Module3Service()

