import React, { useState, useEffect } from 'react';
import Navbar from './components/Navbar.jsx';
import StationPlacementMap from './components/StationPlacementMap.jsx';
import FleetHealthView from './components/FleetHealthView.jsx';
import DemandForecastView from './components/DemandForecastView.jsx';
import TripSimulatorModal from './components/TripSimulatorModal.jsx';

export default function App() {
  const [activeTab, setActiveTab] = useState('stations');
  const [theme, setTheme] = useState(() => localStorage.getItem('range_theme') || 'dark');
  const [apiOnline, setApiOnline] = useState(false);
  const [loading, setLoading] = useState(false);

  const [kStations, setKStations] = useState(5);
  const [coverageRadius, setCoverageRadius] = useState(3.0);

  // Sync theme to root DOM element and localStorage
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('range_theme', theme);
  }, [theme]);


  const [stationsData, setStationsData] = useState(null);
  const [heatPoints, setHeatPoints] = useState([]);
  const [fleetData, setFleetData] = useState(null);
  const [demandData, setDemandData] = useState(null);

// High-fidelity fallback dataset for instant offline exploration & demo presentation
const FALLBACK_STATIONS_DATA = {
  status: 'success',
  k_stations_requested: 5,
  coverage_radius_km: 3.0,
  stations: [
    {
      station_id: 'CS-PUNE-01',
      name: 'Viman Nagar Commercial Hub Hub',
      zone: 'East',
      latitude: 18.58646,
      longitude: 73.90558,
      coverage_radius_km: 3.0,
      covered_trips_count: 46,
      covered_deficit_kwh: 182.7,
      critical_shortages_covered: 8,
      priority_score: 5,
      priority_label: 'CRITICAL HUB',
      equipment: { ac_slow_ports: 4, dc_fast_ports: 2, battery_swap_bays: 1, total_simultaneous_capacity_kw: 53.2 },
    },
    {
      station_id: 'CS-PUNE-02',
      name: 'Katraj South Access Gateway Hub',
      zone: 'South',
      latitude: 18.46158,
      longitude: 73.89492,
      coverage_radius_km: 3.0,
      covered_trips_count: 26,
      covered_deficit_kwh: 114.3,
      critical_shortages_covered: 5,
      priority_score: 4,
      priority_label: 'HIGH PRIORITY',
      equipment: { ac_slow_ports: 3, dc_fast_ports: 2, battery_swap_bays: 1, total_simultaneous_capacity_kw: 49.9 },
    },
    {
      station_id: 'CS-PUNE-03',
      name: 'Hadapsar Industrial & Logistics Hub Hub',
      zone: 'South-East',
      latitude: 18.52014,
      longitude: 73.99336,
      coverage_radius_km: 3.0,
      covered_trips_count: 39,
      covered_deficit_kwh: 173.8,
      critical_shortages_covered: 7,
      priority_score: 4,
      priority_label: 'HIGH PRIORITY',
      equipment: { ac_slow_ports: 4, dc_fast_ports: 2, battery_swap_bays: 1, total_simultaneous_capacity_kw: 53.2 },
    },
    {
      station_id: 'CS-PUNE-04',
      name: 'Hinjawadi IT Park Hub Hub',
      zone: 'West',
      latitude: 18.59130,
      longitude: 73.73890,
      coverage_radius_km: 3.0,
      covered_trips_count: 35,
      covered_deficit_kwh: 162.4,
      critical_shortages_covered: 6,
      priority_score: 4,
      priority_label: 'HIGH PRIORITY',
      equipment: { ac_slow_ports: 4, dc_fast_ports: 2, battery_swap_bays: 1, total_simultaneous_capacity_kw: 53.2 },
    },
    {
      station_id: 'CS-PUNE-05',
      name: 'Kothrud Depot Zone Hub',
      zone: 'South-West',
      latitude: 18.50740,
      longitude: 73.80770,
      coverage_radius_km: 3.0,
      covered_trips_count: 31,
      covered_deficit_kwh: 138.5,
      critical_shortages_covered: 5,
      priority_score: 4,
      priority_label: 'HIGH PRIORITY',
      equipment: { ac_slow_ports: 3, dc_fast_ports: 2, battery_swap_bays: 1, total_simultaneous_capacity_kw: 49.9 },
    },
  ],
  roi_analysis: {
    total_stations_recommended: 5,
    fleet_deficit_coverage_percent: 17.9,
    total_covered_trips: 177,
    monthly_deadhead_km_saved: 776,
    monthly_deadhead_savings_inr: 1940,
    monthly_stranded_events_averted: 141.4,
    monthly_towing_savings_inr: 212160,
    monthly_fleet_uptime_hours_gained: 212.2,
    total_monthly_fleet_savings_inr: 214100,
    annualized_fleet_savings_inr: 2569200,
  },
  total_fleet_deficits_count: 1050,
};

const FALLBACK_FLEET_DATA = {
  total_fleet_vehicles: 120,
  total_trips_analyzed: 2500,
  average_soh_percent: 83.9,
  healthy_vehicles_count: 86,
  monitor_vehicles_count: 21,
  at_risk_vehicles_count: 13,
  total_charging_deficits_logged: 1050,
  total_energy_demanded_kwh: 12480.0,
  at_risk_vehicle_roster: [
    { vehicle_id: 'EV-PUNE-014', soh_percent: 64.2, risk_level: 'CRITICAL DEGRADATION', action_required: 'Schedule Cell Rebalancing / Pack Service' },
    { vehicle_id: 'EV-PUNE-089', soh_percent: 66.8, risk_level: 'CRITICAL DEGRADATION', action_required: 'Schedule Cell Rebalancing / Pack Service' },
    { vehicle_id: 'EV-PUNE-043', soh_percent: 68.5, risk_level: 'CRITICAL DEGRADATION', action_required: 'Schedule Cell Rebalancing / Pack Service' },
    { vehicle_id: 'EV-PUNE-112', soh_percent: 71.0, risk_level: 'HIGH WEAR', action_required: 'Limit to low-payload flat routes' },
    { vehicle_id: 'EV-PUNE-005', soh_percent: 72.4, risk_level: 'HIGH WEAR', action_required: 'Avoid afternoon peak ambient dispatch' },
    { vehicle_id: 'EV-PUNE-077', soh_percent: 73.1, risk_level: 'HIGH WEAR', action_required: 'Monitor internal resistance' },
    { vehicle_id: 'EV-PUNE-032', soh_percent: 74.0, risk_level: 'HIGH WEAR', action_required: 'Perform deep cycle conditioning' },
  ],
};

const FALLBACK_DEMAND_DATA = {
  total_daily_charging_kwh: 4856.9,
  peak_power_demand_kw: 513.1,
  peak_window: '19:00 (PEAK_SURGE)',
  base_power_demand_kw: 85.5,
  recommended_off_peak_shift_kwh: 1699.9,
  hourly_profile: [
    { hour: 0, hour_label: '00:00', power_demand_kw: 85.5, energy_demand_kwh: 68.4, active_charging_vehicles: 19, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 1, hour_label: '01:00', power_demand_kw: 85.5, energy_demand_kwh: 68.4, active_charging_vehicles: 19, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 2, hour_label: '02:00', power_demand_kw: 85.5, energy_demand_kwh: 68.4, active_charging_vehicles: 19, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 3, hour_label: '03:00', power_demand_kw: 128.2, energy_demand_kwh: 102.6, active_charging_vehicles: 28, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 4, hour_label: '04:00', power_demand_kw: 171.0, energy_demand_kwh: 136.8, active_charging_vehicles: 38, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 5, hour_label: '05:00', power_demand_kw: 213.7, energy_demand_kwh: 171.0, active_charging_vehicles: 47, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 6, hour_label: '06:00', power_demand_kw: 128.2, energy_demand_kwh: 102.6, active_charging_vehicles: 28, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 7, hour_label: '07:00', power_demand_kw: 85.5, energy_demand_kwh: 68.4, active_charging_vehicles: 19, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 8, hour_label: '08:00', power_demand_kw: 171.0, energy_demand_kwh: 136.8, active_charging_vehicles: 38, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 9, hour_label: '09:00', power_demand_kw: 256.5, energy_demand_kwh: 205.2, active_charging_vehicles: 57, period_type: 'ACTIVE_DISPATCH', status_color: '#06B6D4' },
    { hour: 10, hour_label: '10:00', power_demand_kw: 299.3, energy_demand_kwh: 239.4, active_charging_vehicles: 66, period_type: 'ACTIVE_DISPATCH', status_color: '#06B6D4' },
    { hour: 11, hour_label: '11:00', power_demand_kw: 342.0, energy_demand_kwh: 273.6, active_charging_vehicles: 76, period_type: 'ACTIVE_DISPATCH', status_color: '#06B6D4' },
    { hour: 12, hour_label: '12:00', power_demand_kw: 384.8, energy_demand_kwh: 307.8, active_charging_vehicles: 86, period_type: 'PEAK_SURGE', status_color: '#EF4444' },
    { hour: 13, hour_label: '13:00', power_demand_kw: 470.3, energy_demand_kwh: 376.2, active_charging_vehicles: 105, period_type: 'PEAK_SURGE', status_color: '#EF4444' },
    { hour: 14, hour_label: '14:00', power_demand_kw: 384.8, energy_demand_kwh: 307.8, active_charging_vehicles: 86, period_type: 'ACTIVE_DISPATCH', status_color: '#06B6D4' },
    { hour: 15, hour_label: '15:00', power_demand_kw: 299.3, energy_demand_kwh: 239.4, active_charging_vehicles: 66, period_type: 'ACTIVE_DISPATCH', status_color: '#06B6D4' },
    { hour: 16, hour_label: '16:00', power_demand_kw: 256.5, energy_demand_kwh: 205.2, active_charging_vehicles: 57, period_type: 'ACTIVE_DISPATCH', status_color: '#06B6D4' },
    { hour: 17, hour_label: '17:00', power_demand_kw: 342.0, energy_demand_kwh: 273.6, active_charging_vehicles: 76, period_type: 'ACTIVE_DISPATCH', status_color: '#06B6D4' },
    { hour: 18, hour_label: '18:00', power_demand_kw: 427.5, energy_demand_kwh: 342.0, active_charging_vehicles: 95, period_type: 'PEAK_SURGE', status_color: '#EF4444' },
    { hour: 19, hour_label: '19:00', power_demand_kw: 513.1, energy_demand_kwh: 410.5, active_charging_vehicles: 114, period_type: 'PEAK_SURGE', status_color: '#EF4444' },
    { hour: 20, hour_label: '20:00', power_demand_kw: 384.8, energy_demand_kwh: 307.8, active_charging_vehicles: 86, period_type: 'ACTIVE_DISPATCH', status_color: '#06B6D4' },
    { hour: 21, hour_label: '21:00', power_demand_kw: 256.5, energy_demand_kwh: 205.2, active_charging_vehicles: 57, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 22, hour_label: '22:00', power_demand_kw: 171.0, energy_demand_kwh: 136.8, active_charging_vehicles: 38, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
    { hour: 23, hour_label: '23:00', power_demand_kw: 128.2, energy_demand_kwh: 102.6, active_charging_vehicles: 28, period_type: 'OFF_PEAK_BASE', status_color: '#10B981' },
  ],
};

const FALLBACK_ROAD_DEFICITS = [
  { lat: 18.5913, lon: 73.7389, urgency: 88.5, deficit_kwh: 6.2 },
  { lat: 18.5935, lon: 73.7312, urgency: 82.1, deficit_kwh: 5.4 },
  { lat: 18.5978, lon: 73.7225, urgency: 94.0, deficit_kwh: 8.9 },
  { lat: 18.6024, lon: 73.7145, urgency: 79.5, deficit_kwh: 4.8 },
  { lat: 18.6045, lon: 73.7760, urgency: 85.0, deficit_kwh: 7.1 },
  { lat: 18.6115, lon: 73.7845, urgency: 91.2, deficit_kwh: 9.3 },
  { lat: 18.5520, lon: 73.8050, urgency: 76.4, deficit_kwh: 4.2 },
  { lat: 18.5595, lon: 73.7920, urgency: 84.8, deficit_kwh: 6.5 },
  { lat: 18.5670, lon: 73.7810, urgency: 89.0, deficit_kwh: 7.8 },
  { lat: 18.5575, lon: 73.8155, urgency: 72.0, deficit_kwh: 3.9 },
  { lat: 18.5510, lon: 73.8240, urgency: 83.5, deficit_kwh: 5.9 },
  { lat: 18.5375, lon: 73.8320, urgency: 78.0, deficit_kwh: 4.5 },
  { lat: 18.5310, lon: 73.8310, urgency: 92.5, deficit_kwh: 9.0 },
  { lat: 18.5085, lon: 73.8260, urgency: 86.2, deficit_kwh: 6.8 },
  { lat: 18.5074, lon: 73.8077, urgency: 93.4, deficit_kwh: 8.5 },
  { lat: 18.5045, lon: 73.7950, urgency: 81.0, deficit_kwh: 5.1 },
  { lat: 18.5018, lon: 73.8586, urgency: 95.0, deficit_kwh: 10.2 },
  { lat: 18.4910, lon: 73.8582, urgency: 87.3, deficit_kwh: 6.9 },
  { lat: 18.4800, lon: 73.8578, urgency: 79.8, deficit_kwh: 4.7 },
  { lat: 18.4680, lon: 73.8572, urgency: 84.1, deficit_kwh: 5.8 },
  { lat: 18.4980, lon: 73.8440, urgency: 75.6, deficit_kwh: 3.8 },
  { lat: 18.4810, lon: 73.8300, urgency: 88.0, deficit_kwh: 7.4 },
  { lat: 18.5492, lon: 73.8967, urgency: 90.5, deficit_kwh: 8.1 },
  { lat: 18.5580, lon: 73.9170, urgency: 83.2, deficit_kwh: 5.6 },
  { lat: 18.5630, lon: 73.9280, urgency: 89.7, deficit_kwh: 7.9 },
  { lat: 18.5490, lon: 73.9550, urgency: 94.2, deficit_kwh: 9.5 },
  { lat: 18.5520, lon: 73.9630, urgency: 85.5, deficit_kwh: 6.4 },
  { lat: 18.5190, lon: 73.9285, urgency: 78.9, deficit_kwh: 4.6 },
  { lat: 18.5089, lon: 73.9260, urgency: 86.7, deficit_kwh: 7.0 },
  { lat: 18.5010, lon: 73.9310, urgency: 91.0, deficit_kwh: 8.7 },
];

  // Check health and initial data fetch with graceful offline fallback
  const fetchAllData = async (k = kStations, radius = coverageRadius) => {
    setLoading(true);
    let online = false;

    try {
      // 1. Health check
      const healthRes = await fetch('/module3/health', { signal: AbortSignal.timeout(2000) }).catch(() => null);
      if (healthRes && healthRes.ok) {
        online = true;
        setApiOnline(true);
      } else {
        setApiOnline(false);
      }

      // 2. Fetch Stations & ROI
      const stationsRes = await fetch(`/module3/stations/recommendations?k_stations=${k}&coverage_radius_km=${radius}`, { signal: AbortSignal.timeout(4000) }).catch(() => null);
      if (stationsRes && stationsRes.ok) {
        const sData = await stationsRes.json();
        setStationsData(sData);
      } else if (!stationsData) {
        setStationsData(FALLBACK_STATIONS_DATA);
      }

      // 3. Fetch Heatmap Deficits (Snapped directly to Pune road network)
      const heatRes = await fetch('/module3/heatmap/deficits?limit=1200', { signal: AbortSignal.timeout(4000) }).catch(() => null);
      if (heatRes && heatRes.ok) {
        const hData = await heatRes.json();
        setHeatPoints(hData);
      } else if (heatPoints.length === 0) {
        setHeatPoints(FALLBACK_ROAD_DEFICITS);
      }

      // 4. Fetch Fleet Overview
      const fleetRes = await fetch('/module3/fleet/overview', { signal: AbortSignal.timeout(4000) }).catch(() => null);
      if (fleetRes && fleetRes.ok) {
        const fData = await fleetRes.json();
        setFleetData(fData);
      } else if (!fleetData) {
        setFleetData(FALLBACK_FLEET_DATA);
      }

      // 5. Fetch Hourly Demand
      const demandRes = await fetch('/module3/demand/hourly', { signal: AbortSignal.timeout(4000) }).catch(() => null);
      if (demandRes && demandRes.ok) {
        const dData = await demandRes.json();
        setDemandData(dData);
      } else if (!demandData) {
        setDemandData(FALLBACK_DEMAND_DATA);
      }
    } catch (err) {
      console.warn('Backend connection warning; loaded local fallback demonstration data:', err);
      if (!stationsData) setStationsData(FALLBACK_STATIONS_DATA);
      if (!fleetData) setFleetData(FALLBACK_FLEET_DATA);
      if (!demandData) setDemandData(FALLBACK_DEMAND_DATA);
    } finally {
      setLoading(false);
    }
  };

  // Auto-reconnect loop: poll backend every 2.5 seconds if offline, and seamlessly fetch live data when ready
  useEffect(() => {
    if (apiOnline) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch('/module3/health', { signal: AbortSignal.timeout(1500) });
        if (res.ok) {
          setApiOnline(true);
          fetchAllData(kStations, coverageRadius);
        }
      } catch (e) {
        // Backend still initializing
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [apiOnline, kStations, coverageRadius]);

  useEffect(() => {
    fetchAllData();
  }, []);

  const handleRecalculate = () => {
    fetchAllData(kStations, coverageRadius);
  };

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        theme={theme}
        setTheme={setTheme}
      />

      <main className="dashboard-main">
        {activeTab === 'stations' && (
          <StationPlacementMap
            stationsData={stationsData}
            heatPoints={heatPoints}
            kStations={kStations}
            setKStations={setKStations}
            coverageRadius={coverageRadius}
            setCoverageRadius={setCoverageRadius}
            loading={loading}
            onRecalculate={handleRecalculate}
            theme={theme}
          />
        )}

        {activeTab === 'fleet' && (
          <FleetHealthView fleetData={fleetData} />
        )}

        {activeTab === 'demand' && (
          <DemandForecastView demandData={demandData} />
        )}

        {activeTab === 'simulator' && (
          <TripSimulatorModal />
        )}
      </main>

      <footer className="dashboard-footer">
        <div className="footer-left">
          <div className="footer-title">
            <strong>Range Intelligence</strong> &bull; Fleet Grid Load Intelligence & Optimal Station Placement
          </div>
          <div className="footer-subtitle">
            Small EV Fleet Battery & Charging Network Intelligence &bull; Frozen ML Core: RandomForestRegressor
          </div>
        </div>

        <div className="footer-right">
          <div className="api-status-pill">
            <span
              className="status-dot"
              style={{
                background: apiOnline ? 'var(--emerald-500)' : 'var(--amber-500)',
                boxShadow: `0 0 8px ${apiOnline ? 'var(--emerald-500)' : 'var(--amber-500)'}`,
              }}
            ></span>
            <span>{apiOnline ? 'FastAPI Online (Port 8000)' : 'Connecting to Backend...'}</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
