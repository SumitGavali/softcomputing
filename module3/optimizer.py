"""
module3/optimizer.py
====================
Charging Station Placement & Hardware Sizing Optimizer for Module 3.
Implements greedy maximum coverage optimization, equipment port sizing,
and fleet ROI / operational impact calculations.
"""

from typing import List, Dict, Any, Optional
import math
import numpy as np
import pandas as pd

from module3.config import (
    STATION_COVERAGE_RADIUS_KM,
    DEFAULT_NUM_STATIONS,
    MIN_STATION_DISTANCE_KM,
    CHARGER_SPECS,
    ROI_CONSTANTS,
    FLEET_VEHICLE_SPECS,
    PUNE_CANDIDATE_PARCELS,
    URBAN_CIRCUITY_FACTOR,
)
from module3.clustering import (
    haversine_distance,
    calculate_road_distance_km,
    find_nearest_landmark,
)


class StationPlacementOptimizer:
    """
    Solves optimal candidate station location selection and sizing for small EV delivery fleets.
    Snaps clusters to verified commercial parcels on Pune road network with verified electrical access.
    """

    def __init__(
        self,
        coverage_radius_km: float = STATION_COVERAGE_RADIUS_KM,
        min_station_distance_km: float = MIN_STATION_DISTANCE_KM,
    ):
        self.coverage_radius_km = coverage_radius_km
        self.min_station_distance_km = min_station_distance_km

    def optimize_station_placements(
        self,
        clusters: List[Dict[str, Any]],
        df_deficits: pd.DataFrame,
        k_stations: int = DEFAULT_NUM_STATIONS,
        capex_params: Optional[Dict[str, float]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Selects top k station locations maximizing coverage while respecting minimum spacing.
        Snaps mathematical centroids to real physical commercial candidate parcels with road access.
        """
        if not clusters or df_deficits.empty:
            return []

        deficit_records = df_deficits.to_dict(orient="records")
        selected_stations: List[Dict[str, Any]] = []
        available_parcels = list(PUNE_CANDIDATE_PARCELS)

        # Sort candidate clusters by total deficit kWh
        sorted_candidates = sorted(clusters, key=lambda c: c["total_deficit_kwh"], reverse=True)

        for candidate in sorted_candidates:
            if len(selected_stations) >= k_stations:
                break

            raw_lat = candidate["latitude"]
            raw_lon = candidate["longitude"]

            # Snap centroid to nearest verified physical candidate parcel on road network
            best_parcel = None
            min_parcel_dist = float("inf")
            for p in available_parcels:
                dist = calculate_road_distance_km(raw_lat, raw_lon, p["lat"], p["lon"])
                if dist < min_parcel_dist:
                    min_parcel_dist = dist
                    best_parcel = p

            if best_parcel and min_parcel_dist <= 6.0:
                c_lat = best_parcel["lat"]
                c_lon = best_parcel["lon"]
                station_name = best_parcel["name"]
                station_zone = best_parcel["zone"]
                station_address = best_parcel["address"]
                site_type = best_parcel["site_type"]
                grid_cap_kw = best_parcel.get("grid_capacity_kw", 250.0)
                available_parcels.remove(best_parcel)
            else:
                landmark_info = find_nearest_landmark(raw_lat, raw_lon)
                from module3.pune_road_network import find_nearest_road_node
                snapped_lat, snapped_lon, corridor_name = find_nearest_road_node(raw_lat, raw_lon)
                c_lat = snapped_lat
                c_lon = snapped_lon
                station_name = f"{landmark_info['landmark_name']}"
                station_zone = landmark_info["zone"]
                station_address = f"{corridor_name} Road Forecourt, {landmark_info['landmark_name']}"
                site_type = "Road-Frontage Mobility Forecourt"
                grid_cap_kw = 200.0

            # Check minimum road distance from already selected stations
            too_close = False
            for s in selected_stations:
                dist = calculate_road_distance_km(c_lat, c_lon, s["latitude"], s["longitude"])
                if dist < self.min_station_distance_km:
                    too_close = True
                    break

            if too_close:
                continue

            # Calculate covered deficits using Haversine distance (as-the-crow-flies)
            # This matches the visual L.circle on the frontend which draws a Haversine radius.
            # Road distance (with circuity) is used for station spacing, not coverage catchment.
            covered_trips = []
            covered_kwh = 0.0
            critical_count = 0

            for d in deficit_records:
                air_dist = haversine_distance(c_lat, c_lon, d["latitude"], d["longitude"])
                if air_dist <= self.coverage_radius_km:
                    covered_trips.append(d)
                    covered_kwh += float(d.get("charging_requirement_kwh", 3.0))
                    if float(d.get("fuzzy_urgency", 0.0)) >= 80.0 or float(d.get("range_margin_km", 0.0)) < -10.0:
                        critical_count += 1

            # Hardware equipment sizing based on demand and custom capex rates
            ports_config = self._size_station_equipment(
                covered_kwh, len(covered_trips), capex_params=capex_params
            )

            # Priority score: 1 (Lowest) to 5 (Critical Hub)
            if covered_kwh > 200 or critical_count > 40:
                priority = 5
                priority_label = "CRITICAL HUB"
            elif covered_kwh > 100 or critical_count > 20:
                priority = 4
                priority_label = "HIGH PRIORITY"
            elif covered_kwh > 50:
                priority = 3
                priority_label = "MEDIUM PRIORITY"
            else:
                priority = 2
                priority_label = "SUPPORT STATION"

            station_info = {
                "station_id": f"CS-OPT-{len(selected_stations) + 1:02d}",
                "name": station_name,
                "zone": station_zone,
                "address": station_address,
                "site_type": site_type,
                "latitude": round(c_lat, 5),
                "longitude": round(c_lon, 5),
                "coverage_radius_km": self.coverage_radius_km,
                "covered_trips_count": len(covered_trips),
                "covered_deficit_kwh": round(covered_kwh, 2),
                "critical_shortages_covered": critical_count,
                "priority_score": priority,
                "priority_label": priority_label,
                "equipment": ports_config,
                "grid_capacity_kw": grid_cap_kw,
            }
            selected_stations.append(station_info)

        # If deficit clusters were fewer than k_stations, supplement from remaining high-potential candidate parcels
        if len(selected_stations) < k_stations:
            for p in list(available_parcels):
                if len(selected_stations) >= k_stations:
                    break

                c_lat = p["lat"]
                c_lon = p["lon"]

                too_close = False
                for s in selected_stations:
                    dist = calculate_road_distance_km(c_lat, c_lon, s["latitude"], s["longitude"])
                    if dist < self.min_station_distance_km:
                        too_close = True
                        break
                if too_close:
                    continue

                covered_trips = []
                covered_kwh = 0.0
                critical_count = 0
                for d in deficit_records:
                    air_dist = haversine_distance(c_lat, c_lon, d["latitude"], d["longitude"])
                    if air_dist <= self.coverage_radius_km:
                        covered_trips.append(d["trip_id"])
                        covered_kwh += float(d.get("charging_requirement_kwh", 3.0))
                        if float(d.get("fuzzy_urgency", 0.0)) >= 80.0 or float(d.get("range_margin_km", 0.0)) < -10.0:
                            critical_count += 1

                ports_config = self._size_station_equipment(
                    covered_kwh, len(covered_trips), capex_params=capex_params
                )

                if covered_kwh > 200 or critical_count > 40:
                    priority = 5
                    priority_label = "CRITICAL HUB"
                elif covered_kwh > 100 or critical_count > 20:
                    priority = 4
                    priority_label = "HIGH PRIORITY"
                elif covered_kwh > 50:
                    priority = 3
                    priority_label = "MEDIUM PRIORITY"
                else:
                    priority = 2
                    priority_label = "SUPPORT STATION"

                station_info = {
                    "station_id": f"CS-OPT-{len(selected_stations) + 1:02d}",
                    "name": p["name"],
                    "zone": p["zone"],
                    "address": p["address"],
                    "site_type": p["site_type"],
                    "latitude": round(c_lat, 5),
                    "longitude": round(c_lon, 5),
                    "coverage_radius_km": self.coverage_radius_km,
                    "covered_trips_count": len(covered_trips),
                    "covered_deficit_kwh": round(covered_kwh, 2),
                    "critical_shortages_covered": critical_count,
                    "priority_score": priority,
                    "priority_label": priority_label,
                    "equipment": ports_config,
                    "grid_capacity_kw": p.get("grid_capacity_kw", 200.0),
                }
                selected_stations.append(station_info)
                available_parcels.remove(p)

        return selected_stations

    def _size_station_equipment(
        self,
        total_kwh: float,
        trip_count: int,
        capex_params: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Sizes ports and chargers based on daily energy demand, throughput, and customizable capex costs.
        """
        # Estimated peak hourly energy = ~15% of total deficit
        peak_hour_kwh = total_kwh * 0.15

        # Base AC slow chargers (Level 2, 3.3kW) for rest/depot charging
        ac_ports = max(2, min(8, math.ceil(total_kwh / 50.0)))

        # DC Fast Chargers (15kW) for rapid 30-min turnarounds
        dc_ports = max(1, min(4, math.ceil(peak_hour_kwh / 15.0)))

        # Quick Battery Swap Bay: recommend if trip count is high
        swap_bays = 1 if trip_count >= 25 else 0

        ac_cost = capex_params.get("ac_cost_inr", CHARGER_SPECS["AC_SLOW_3KW"]["cost_estimate_inr"]) if capex_params else CHARGER_SPECS["AC_SLOW_3KW"]["cost_estimate_inr"]
        dc_cost = capex_params.get("dc_cost_inr", CHARGER_SPECS["DC_FAST_15KW"]["cost_estimate_inr"]) if capex_params else CHARGER_SPECS["DC_FAST_15KW"]["cost_estimate_inr"]
        swap_cost = capex_params.get("swap_cost_inr", CHARGER_SPECS["BATTERY_SWAP"]["cost_estimate_inr"]) if capex_params else CHARGER_SPECS["BATTERY_SWAP"]["cost_estimate_inr"]

        total_capex = (
            ac_ports * ac_cost
            + dc_ports * dc_cost
            + swap_bays * swap_cost
        )

        return {
            "ac_slow_ports": ac_ports,
            "dc_fast_ports": dc_ports,
            "battery_swap_bays": swap_bays,
            "total_simultaneous_capacity_kw": round(
                ac_ports * 3.3 + dc_ports * 15.0 + swap_bays * 10.0, 1
            ),
            "estimated_capex_inr": total_capex,
        }

    def compute_fleet_roi(
        self,
        stations: List[Dict[str, Any]],
        df_deficits: pd.DataFrame,
        total_fleet_size: int = FLEET_VEHICLE_SPECS["fleet_size"],
        roi_params: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """
        Calculates operational fleet ROI metrics with customizable towing and deadhead parameters.
        """
        total_covered_trips = sum(s["covered_trips_count"] for s in stations)
        total_covered_kwh = sum(s["covered_deficit_kwh"] for s in stations)
        total_critical = sum(s["critical_shortages_covered"] for s in stations)

        total_deficits_count = len(df_deficits)
        coverage_pct = round(
            (total_covered_trips / total_deficits_count * 100.0)
            if total_deficits_count > 0
            else 0.0,
            1,
        )

        # Operational financial constants with dynamic overrides
        deadhead_rate = roi_params.get("deadhead_cost_per_km", ROI_CONSTANTS["DEADHEAD_COST_PER_KM"]) if roi_params else ROI_CONSTANTS["DEADHEAD_COST_PER_KM"]
        towing_rate = roi_params.get("towing_cost_per_incident", ROI_CONSTANTS["TOWING_COST_PER_INCIDENT"]) if roi_params else ROI_CONSTANTS["TOWING_COST_PER_INCIDENT"]
        working_days = roi_params.get("working_days_per_month", ROI_CONSTANTS["WORKING_DAYS_PER_MONTH"]) if roi_params else ROI_CONSTANTS["WORKING_DAYS_PER_MONTH"]

        # 1. Deadhead kilometers saved (grounded in urban road circuity tau = 1.32):
        avg_deadhead_saved_km_per_event = round(3.5 * URBAN_CIRCUITY_FACTOR, 1)  # ~4.6 km actual road detour avoided per event
        total_deadhead_km_saved_monthly = (
            total_covered_trips
            * avg_deadhead_saved_km_per_event
            * (working_days / 30.0)
        )
        monthly_deadhead_cost_saved = total_deadhead_km_saved_monthly * deadhead_rate

        # 2. Stranded vehicle rescues averted:
        monthly_averted_towing = (
            total_critical
            * ROI_CONSTANTS["ESTIMATED_AVERTED_FAILURES_RATIO"]
            * (working_days / 30.0)
        )
        monthly_towing_cost_saved = monthly_averted_towing * towing_rate

        # 3. Fleet uptime recovery:
        hours_recovered_monthly = (
            monthly_averted_towing * ROI_CONSTANTS["DISPATCH_RECOVERY_HOURS_SAVED"]
        )

        total_monthly_savings_inr = round(monthly_deadhead_cost_saved + monthly_towing_cost_saved, 0)

        return {
            "total_stations_recommended": len(stations),
            "fleet_deficit_coverage_percent": coverage_pct,
            "total_covered_trips": total_covered_trips,
            "monthly_deadhead_km_saved": round(total_deadhead_km_saved_monthly, 0),
            "monthly_deadhead_savings_inr": round(monthly_deadhead_cost_saved, 0),
            "monthly_stranded_events_averted": round(monthly_averted_towing, 1),
            "monthly_towing_savings_inr": round(monthly_towing_cost_saved, 0),
            "monthly_fleet_uptime_hours_gained": round(hours_recovered_monthly, 1),
            "total_monthly_fleet_savings_inr": total_monthly_savings_inr,
            "annualized_fleet_savings_inr": round(total_monthly_savings_inr * 12, 0),
        }

