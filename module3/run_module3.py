"""
run_module3.py
==============
CLI Verification & Execution Runner for Module 3:
Charging Demand Forecast & Optimal Station Placement Engine.

Usage:
  python run_module3.py --report     # Generate full station placement & ROI report
  python run_module3.py --demo       # Run quick interactive verification
  python run_module3.py --api        # Start unified FastAPI backend server
"""

import os
import sys
import argparse
import logging
from typing import Dict, Any

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from module3.service import Module3Service

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def print_banner(title: str):
    sep = "=" * 75
    print("\n" + sep)
    print(title.center(75))
    print(sep)


def run_demo():
    print_banner("MODULE 3: CHARGING DEMAND & STATION PLACEMENT DEMO")
    service = Module3Service()

    print("\n[1/4] Loading fleet trips and detecting battery deficits...")
    overview = service.get_fleet_overview_metrics()
    print(f"      Total Fleet Vehicles        : {overview['total_fleet_vehicles']}")
    print(f"      Total Trips Evaluated       : {overview['total_trips_analyzed']}")
    print(f"      Fleet Average Battery SoH   : {overview['average_soh_percent']}%")
    print(f"      Healthy Vehicles (>=80% SoH): {overview['healthy_vehicles_count']}")
    print(f"      At-Risk Vehicles (<75% SoH) : {overview['at_risk_vehicles_count']}")
    print(f"      Total Deficits Logged       : {overview['total_charging_deficits_logged']}")

    print("\n[2/4] Optimizing charging station placement (k=5 stations, radius=3.0 km)...")
    rec_result = service.get_station_recommendations(k_stations=5, coverage_radius_km=3.0)
    stations = rec_result["stations"]
    roi = rec_result["roi_analysis"]

    print(f"\n      Selected {len(stations)} Optimal Charging Hubs in Pune:")
    for idx, s in enumerate(stations, 1):
        eq = s["equipment"]
        print(f"      {idx}. [{s['station_id']}] {s['name']} ({s['zone']})")
        print(f"         Location  : {s['latitude']} N, {s['longitude']} E (Radius: {s['coverage_radius_km']} km)")
        print(f"         Coverage  : {s['covered_trips_count']} trips | {s['covered_deficit_kwh']:.1f} kWh deficit | Priority: {s['priority_label']}")
        print(f"         Hardware  : {eq['ac_slow_ports']}x AC Slow, {eq['dc_fast_ports']}x DC Fast, {eq['battery_swap_bays']}x Swap Bays ({eq['total_simultaneous_capacity_kw']} kW)")

    print("\n[3/4] Fleet Operational Impact & ROI Analysis:")
    print(f"      Fleet Deficit Coverage      : {roi['fleet_deficit_coverage_percent']}%")
    print(f"      Monthly Deadhead Saved      : {roi['monthly_deadhead_km_saved']:,.0f} km (Savings: INR {roi['monthly_deadhead_savings_inr']:,.0f})")
    print(f"      Stranded Rescues Averted    : {roi['monthly_stranded_events_averted']} events (Savings: INR {roi['monthly_towing_savings_inr']:,.0f})")
    print(f"      Fleet Uptime Gained         : {roi['monthly_fleet_uptime_hours_gained']} productive hours/month")
    print(f"      TOTAL MONTHLY FLEET SAVINGS : INR {roi['total_monthly_fleet_savings_inr']:,.0f}")
    print(f"      ANNUALIZED SAVINGS IMPACT   : INR {roi['annualized_fleet_savings_inr']:,.0f}")

    print("\n[4/4] 24-Hour Fleet Charging Demand Forecast:")
    demand = service.get_hourly_demand_forecast()
    print(f"      Total Daily Energy Need     : {demand['total_daily_charging_kwh']:.1f} kWh")
    print(f"      Peak Power Demand Window    : {demand['peak_window']} @ {demand['peak_power_demand_kw']:.1f} kW")
    print(f"      Base Power Demand           : {demand['base_power_demand_kw']:.1f} kW")
    print(f"      Recommended Off-Peak Shift  : {demand['recommended_off_peak_shift_kwh']:.1f} kWh (Night trickle)")

    print_banner("DEMO COMPLETED SUCCESSFULLY")


def run_api(port: int = 8000, reload: bool = False):
    import uvicorn
    print_banner(f"STARTING UNIFIED RANGE INTELLIGENCE API ON PORT {port}")
    print(f"Interactive Swagger Documentation available at: http://localhost:{port}/docs")
    uvicorn.run("module2.Build.api:app", host="0.0.0.0", port=port, reload=reload)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Module 3 Runner")
    parser.add_argument("--demo", action="store_true", help="Run interactive verification demo")
    parser.add_argument("--report", action="store_true", help="Generate full station placement & ROI report")
    parser.add_argument("--api", action="store_true", help="Launch FastAPI server")
    parser.add_argument("--port", type=int, default=8000, help="Port for FastAPI server")
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn hot reloading")
    args = parser.parse_args()

    if args.api:
        run_api(port=args.port, reload=args.reload)
    else:
        run_demo()
