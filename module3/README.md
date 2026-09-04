# Module 3 — Charging Demand Forecasting & Optimal Station Placement Engine

## Range Intelligence Layer for Small EV Fleets

### Executive Summary

Small EV fleet operators (50–2,000 two-wheelers and three-wheelers in delivery, grocery, and logistics) operate without dedicated data science teams. They suffer severe financial losses from:
1. **Mid-route battery dropouts & rescue towing:** Sudden 0% State-of-Charge (SoC) strandings that cost ₹1,500+ per tow incident and cause lost delivery revenue.
2. **Deadhead mileage waste:** Riders detouring 6–10 km back to a distant central depot to recharge instead of accessing strategically positioned in-route hubs.
3. **Guesswork in charging station placement:** Placing chargers based on generic footfall rather than actual fleet battery deficit hot zones.

**Module 3** consumes aggregated telemetry and evaluated trip deficits from **Module 1** (Battery State-of-Health & degradation modeling) and **Module 2** (trip physics & fuzzy charging urgency) to provide:
* **Spatial Deficit Clustering:** Identifies recurrent battery deficit corridors across the fleet's operating network.
* **Optimal Charging Station Placement & Sizing:** Recommends high-impact station coordinates, priority rankings, and equipment port sizing (AC Slow, DC Fast, Battery Swap Bays).
* **Fleet Operational ROI Engine:** Quantifies monthly deadhead distance saved, towing incidents averted, and direct rupee cost savings.
* **24-Hour Temporal Demand Forecasting:** Models hourly simultaneous power loads (kW) and energy demand (kWh) to enable peak-shaving and TOU tariff savings.
* **Interactive Fleet Dashboard:** A modern React + Vite application featuring interactive geospatial mapping, fleet battery health monitoring, and a pre-trip dispatch simulator.

---

## Technical Architecture

```
                               ┌─────────────────────────────┐
                               │  Module 1: Battery SoH      │
                               │  Degraded Usable Range (km) │
                               └──────────────┬──────────────┘
                                              │
                               ┌──────────────▼──────────────┐
                               │  Module 2: Trip Energy      │
                               │  Physics & Fuzzy Urgency    │
                               └──────────────┬──────────────┘
                                              │ Aggregated Trip Logs
                                              │ (GPS, Deficits, Margins)
                               ┌──────────────▼──────────────┐
                               │         MODULE 3            │
                               ├─────────────────────────────┤
                               │ 1. Deficit Spatial Cluster  │
                               │    (DBSCAN + Fuzzy C-Means) │
                               │                             │
                               │ 2. Maximum Coverage Engine  │
                               │    (Greedy Capacitated FLP) │
                               │                             │
                               │ 3. Station Equipment Sizer  │
                               │    (AC, DC Fast, Swap Bays) │
                               │                             │
                               │ 4. Fleet ROI & Impact Model │
                               │                             │
                               │ 5. 24h Temporal Forecaster  │
                               └──────────────┬──────────────┘
                                              │
                    ┌─────────────────────────┴─────────────────────────┐
                    │                                                   │
     ┌──────────────▼──────────────┐                     ┌──────────────▼──────────────┐
     │      FastAPI Backend        │                     │   React + Vite Dashboard    │
     │  /module3/stations/...      │ ◄─── REST Proxy ─── │  Leaflet Map + Carto Dark   │
     │  /module3/heatmap/...       │                     │  Sora & Manrope Typography  │
     │  /module3/demand/...        │                     │  Midnight Emerald Palette   │
     └─────────────────────────────┘                     └─────────────────────────────┘
```

---

## Core Algorithms & Formulations

### 1. Spatial Deficit Clustering
Filters trips meeting any shortage criterion:
$$\text{Deficit Condition} = (\text{charging\_required} == \text{True}) \lor (\text{fuzzy\_urgency} \ge 60) \lor (\text{range\_margin\_km} < 0)$$

* **DBSCAN (Density-Based Spatial Clustering of Applications with Noise):** Uses Haversine distance metric with $\epsilon = 2.0\text{ km}$ and $\text{min\_samples} = 5$ to detect core charging bottleneck corridors while discarding isolated random dropouts.
* **Fuzzy C-Means (FCM) Soft Computing Partition:** Computes degrees of membership $u_{ij}$ of deficit $i$ to station centroid $j$:
$$u_{ij} = \frac{1}{\sum_{k=1}^{C} \left(\frac{d(x_i, c_j)}{d(x_i, c_k)}\right)^{\frac{2}{m-1}}}$$
where $m = 2.0$ is the fuzzifier, reflecting that delivery routes near boundary areas can access overlapping hubs.

### 2. Charging Station Placement Optimizer
* **Greedy Maximum Coverage Formulation:** Selects top $K$ station locations from discovered candidate clusters subject to a minimum inter-station spacing constraint ($\ge 2.0\text{ km}$) to prevent redundant co-location.
* **Service Catchment Radius:** Default $R = 3.0\text{ km}$ (the operational tolerance limit for last-mile delivery riders).

### 3. Equipment Hardware Sizing
For each candidate hub, equipment is sized based on aggregate daily and peak hourly kWh throughput:
* **Standard AC Level-2 (3.3 kW):** Sized for steady overnight/shift-end rest charging.
* **DC Fast Charger (15 kW):** Sized for rapid 30–35 min mid-shift battery replenishment.
* **Battery Swap Bay (10 kW):** Recommended when trip density exceeds threshold, providing instantaneous 2-minute pack swaps.

### 4. Fleet Operational ROI Model
Quantifies real business value created for the fleet operator:
* **Deadhead Transit Saved:** Diverting to an in-route hub within 3 km vs returning 6+ km to base saves an average of 4.5 km per charging event:
$$\text{Monthly Savings}_{\text{deadhead}} = \text{Covered Trips} \times 4.5\text{ km} \times ₹2.50/\text{km}$$
* **Stranded Rescue Towing Averted:** Strategic charging access resolves ~85% of critical deficit dropouts:
$$\text{Monthly Savings}_{\text{towing}} = \text{Critical Shortages Covered} \times 0.85 \times ₹1,500/\text{incident}$$
* **Fleet Uptime Gained:** Avoids an average of 1.5 dispatch downtime hours per averted breakdown.

---

## API Reference

All endpoints are hosted on the unified FastAPI server:

| Method | Endpoint | Description | Query / Body Parameters |
|---|---|---|---|
| `GET` | `/module3/health` | Service health and liveness | None |
| `GET` | `/module3/fleet/overview` | Fleet-wide SoH distribution, healthy/monitor/at-risk vehicle counts, at-risk roster | None |
| `GET` | `/module3/stations/recommendations` | Ranked candidate charging station coordinates, coverage, hardware specs, and ROI metrics | `k_stations` (default 5), `coverage_radius_km` (default 3.0) |
| `GET` | `/module3/heatmap/deficits` | Geolocated battery deficit points with intensity weights for map overlays | `limit` (default 1500) |
| `GET` | `/module3/demand/hourly` | 24-hour simultaneous power demand (kW) and energy demand (kWh) profile | None |
| `POST` | `/module3/simulate/placement` | Dynamic placement simulation | JSON `{ "k_stations": int, "coverage_radius_km": float }` |
| `POST` | `/module3/simulate/trip` | Instant pre-trip dispatch simulator bridge | JSON `{ "trip_distance_km", "initial_soc_percent", "soh_percent", "ambient_temperature_c", "terrain", "load_kg" }` |

---

## How to Run & Verify

### 1. Run Automated Unit & Integration Tests
```powershell
py -3.11 -m pytest module3/tests/test_module3.py -v
```
All 11 unit and integration tests validate Haversine math, clustering engines, station placement optimizers, ROI formulas, demand forecasters, and API endpoints.

### 2. Run Module 3 CLI Demo
```powershell
py -3.11 run_module3.py --demo
```
Prints the full verification report including discovered charging hubs in Pune, hardware configurations, ROI rupee calculations, and 24-hour demand spikes.

### 3. Start the FastAPI Backend
```powershell
py -3.11 run_module3.py --api --port 8000
```
Interactive Swagger API documentation will be available at: `http://localhost:8000/docs`.

### 4. Start the React + Vite Dashboard
In a separate terminal:
```powershell
cd frontend
npm run dev
```
Open `http://localhost:3000` to interact with the Range Intelligence Dashboard.
