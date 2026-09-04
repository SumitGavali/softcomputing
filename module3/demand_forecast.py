"""
module3/demand_forecast.py
==========================
Temporal Charging Demand Forecasting Engine for Module 3.
Models 24-hour fleet charging load curves, peak demand spikes,
and grid load-shifting opportunities.
"""

from typing import List, Dict, Any
import numpy as np
import pandas as pd


class DemandForecaster:
    """
    Simulates and forecasts 24-hour fleet charging demand profiles (kW and kWh).
    """

    def __init__(self, seed: int = 42):
        self.seed = seed
        np.random.seed(seed)

    def generate_hourly_demand_profile(
        self, df_trips: pd.DataFrame, stations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generates 24-hour charging load profile based on fleet trip dispatch times.
        """
        # Base prior: 24-hour urban delivery dispatch probability curve (last-mile shifts)
        prior_weights = np.array([
            0.02, 0.02, 0.02, 0.03, 0.04, 0.05,  # 00:00 - 05:00 (overnight depot trickle)
            0.03, 0.02, 0.04, 0.06, 0.07, 0.08,  # 06:00 - 11:00 (morning shift dispatch)
            0.09, 0.11, 0.09, 0.07, 0.06, 0.08,  # 12:00 - 17:00 (midday delivery top-up)
            0.10, 0.12, 0.09, 0.06, 0.04, 0.03   # 18:00 - 23:00 (evening return surge)
        ])
        prior_weights = prior_weights / prior_weights.sum()

        # Check for empirical timestamp/hour data in telemetry
        empirical_weights = None
        for time_col in ["timestamp", "datetime", "start_time", "hour", "dispatch_hour"]:
            if time_col in df_trips.columns and not df_trips[time_col].dropna().empty:
                try:
                    if time_col in ["hour", "dispatch_hour"]:
                        hrs = pd.to_numeric(df_trips[time_col], errors="coerce").dropna().astype(int)
                    else:
                        hrs = pd.to_datetime(df_trips[time_col], errors="coerce").dt.hour.dropna().astype(int)
                    
                    if len(hrs) >= 20:
                        counts = np.bincount(hrs.clip(0, 23), minlength=24).astype(float)
                        if counts.sum() > 0:
                            empirical_weights = counts / counts.sum()
                            break
                except Exception:
                    pass

        if empirical_weights is not None:
            # Bayesian blend: 75% empirical observation + 25% smooth operational prior
            hourly_weights = 0.75 * empirical_weights + 0.25 * prior_weights
            hourly_weights = hourly_weights / hourly_weights.sum()
        else:
            hourly_weights = prior_weights

        total_trips = len(df_trips) if not df_trips.empty else 1000
        total_energy_kwh = float(df_trips["trip_energy_demand_kwh"].sum()) if "trip_energy_demand_kwh" in df_trips else 12500.0
        
        # Aggregate deficit energy specifically
        deficit_trips = df_trips[
            (df_trips.get("charging_required", pd.Series([False]*len(df_trips))) == True) |
            (df_trips.get("fuzzy_urgency", pd.Series([0]*len(df_trips))) >= 60)
        ]
        total_deficit_kwh = float(deficit_trips["charging_requirement_kwh"].sum()) if not deficit_trips.empty and "charging_requirement_kwh" in deficit_trips else total_energy_kwh * 0.28


        hours = list(range(24))
        hourly_records = []

        for h in hours:
            weight = hourly_weights[h]
            hour_kwh = total_deficit_kwh * weight
            hour_kw = hour_kwh * 1.25  # Power factor / concurrency multiplier

            # Classify operational state
            if h in [12, 13, 18, 19]:
                period_type = "PEAK_SURGE"
                status_color = "#EF4444"  # Crimson
            elif h in [9, 10, 11, 14, 15, 16, 17, 20]:
                period_type = "ACTIVE_DISPATCH"
                status_color = "#06B6D4"  # Cyan
            else:
                period_type = "OFF_PEAK_BASE"
                status_color = "#10B981"  # Emerald

            hourly_records.append({
                "hour": h,
                "hour_label": f"{h:02d}:00",
                "energy_demand_kwh": round(hour_kwh, 1),
                "power_demand_kw": round(hour_kw, 1),
                "active_charging_vehicles": int(round(hour_kw / 4.5)),
                "period_type": period_type,
                "status_color": status_color,
            })

        peak_record = max(hourly_records, key=lambda x: x["power_demand_kw"])
        min_record = min(hourly_records, key=lambda x: x["power_demand_kw"])

        return {
            "hourly_profile": hourly_records,
            "total_daily_charging_kwh": round(total_deficit_kwh, 1),
            "peak_power_demand_kw": peak_record["power_demand_kw"],
            "peak_window": f"{peak_record['hour_label']} ({peak_record['period_type']})",
            "base_power_demand_kw": min_record["power_demand_kw"],
            "recommended_off_peak_shift_kwh": round(total_deficit_kwh * 0.35, 1),
        }
