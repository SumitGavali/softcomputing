import React from 'react';
import {
  IconDemandForecast,
  IconBolt,
  IconAlertTriangle,
} from './Icons.jsx';
import TermTooltip from './TermTooltip.jsx';

export default function FleetHealthView({ fleetData }) {
  const data = fleetData || {};
  const atRiskList = data.at_risk_vehicle_roster || [];

  const healthyPct = data.total_fleet_vehicles ? Math.round((data.healthy_vehicles_count / data.total_fleet_vehicles) * 100) : 0;
  const monitorPct = data.total_fleet_vehicles ? Math.round((data.monitor_vehicles_count / data.total_fleet_vehicles) * 100) : 0;
  const atRiskPct = data.total_fleet_vehicles ? Math.round((data.at_risk_vehicles_count / data.total_fleet_vehicles) * 100) : 0;

  return (
    <div>
      {/* Fleet Overview KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">
            <span>Fleet Average Battery SoH</span>
            <TermTooltip text="State of Health (SoH) measures battery capacity retention: 100% is brand new, below 75% indicates end-of-first-life." />
          </div>
          <div className="kpi-value accent-emerald">
            {data.average_soh_percent || 0}%
          </div>
          <div className="kpi-subtext">Across {data.total_fleet_vehicles || 0} monitored EV delivery units</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            <span>Healthy Cohort (&ge; 80%)</span>
            <TermTooltip text="Vehicles retaining prime battery capacity, optimal for long-distance and heavy payload delivery runs." />
          </div>
          <div className="kpi-value accent-emerald">
            {data.healthy_vehicles_count || 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>({healthyPct}%)</span>
          </div>
          <div className="kpi-subtext">Operating within nominal manufacturer warranty bounds</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            <span>Monitor Cohort (75% &ndash; 80%)</span>
            <TermTooltip text="Batteries undergoing progressive capacity loss; best assigned to shorter, flat urban routes." />
          </div>
          <div className="kpi-value accent-amber">
            {data.monitor_vehicles_count || 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>({monitorPct}%)</span>
          </div>
          <div className="kpi-subtext">Gradual capacity fade &ndash; recommend avoiding high-load routes</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            <span>At-Risk Cohort (&lt; 75%)</span>
            <TermTooltip text="Batteries prone to premature voltage sag and unexpected shutdowns; recommended for maintenance or cell rebalancing." />
          </div>
          <div className="kpi-value accent-crimson">
            {data.at_risk_vehicles_count || 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>({atRiskPct}%)</span>
          </div>
          <div className="kpi-subtext">High risk of mid-route dropout &ndash; service required</div>
        </div>
      </div>

      {/* Fleet Distribution Bar & Health Insight */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '10px', marginBottom: '10px' }}>
        <div className="glass-panel">
          <div className="panel-header" style={{ padding: '14px 18px' }}>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <IconDemandForecast size={17} color="var(--emerald-400)" />
              <span>Fleet Degradation Distribution</span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>120 Active Delivery EVs</span>
          </div>
          <div className="panel-body" style={{ padding: '18px' }}>
            {/* Multi-segment distribution bar */}
            <div style={{ display: 'flex', height: '26px', borderRadius: '8px', overflow: 'hidden', marginBottom: '14px', background: 'var(--bg-track)' }}>
              <div style={{ width: `${healthyPct}%`, background: 'var(--emerald-500)', transition: 'width 0.5s ease' }} title={`Healthy: ${healthyPct}%`}></div>
              <div style={{ width: `${monitorPct}%`, background: 'var(--amber-500)', transition: 'width 0.5s ease' }} title={`Monitor: ${monitorPct}%`}></div>
              <div style={{ width: `${atRiskPct}%`, background: 'var(--crimson-500)', transition: 'width 0.5s ease' }} title={`At-Risk: ${atRiskPct}%`}></div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', flexWrap: 'wrap', gap: '8px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--emerald-500)' }}></span>
                <span>Healthy ({data.healthy_vehicles_count || 0} EVs &bull; {healthyPct}%)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--amber-500)' }}></span>
                <span>Monitor ({data.monitor_vehicles_count || 0} EVs &bull; {monitorPct}%)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ width: '10px', height: '10px', borderRadius: '50%', background: 'var(--crimson-500)' }}></span>
                <span>At-Risk ({data.at_risk_vehicles_count || 0} EVs &bull; {atRiskPct}%)</span>
              </div>
            </div>

            <div style={{ marginTop: '20px', padding: '14px', borderRadius: '10px', background: 'var(--bg-inset)', border: '1px solid var(--border-subtle)', fontSize: '12px', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
              <strong style={{ color: 'var(--emerald-500)', display: 'inline-flex', alignItems: 'center', gap: '4px', marginRight: '6px' }}>
                Degradation Physics Rule:
                <TermTooltip text="Non-linear battery degradation rule based on NASA Li-ion battery lifecycle experiments." pos="top" align="left" />
              </strong>
              Li-ion battery health does not decay linearly. Internal resistance (R_e) accelerates rapidly after 200+ discharge cycles or repeated operations in summer heat (&gt;35&deg;C). Vehicles flagged as At-Risk experience up to <strong>35% higher voltage drop</strong> under payload, leading to sudden unexpected BMS shutoffs.
            </div>
          </div>
        </div>

        {/* Fleet Energy Metrics */}
        <div className="glass-panel">
          <div className="panel-header" style={{ padding: '14px 18px' }}>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <IconBolt size={17} color="var(--cyan-400)" />
              <span>Energy Consumption Profile</span>
            </div>
          </div>
          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '18px' }}>
            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>Total Trip Energy Logged</span>
                <TermTooltip text="Total cumulative kilowatt-hours (kWh) drawn by fleet delivery trips." pos="top" align="right" />
              </div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {data.total_energy_demanded_kwh ? Number(data.total_energy_demanded_kwh).toLocaleString() : 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>kWh</span>
              </div>
            </div>

            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>Charging Deficits Detected</span>
                <TermTooltip text="Events where a vehicle's battery dropped below 15% charge before reaching a charger." pos="top" align="right" />
              </div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: '22px', fontWeight: 700, color: 'var(--crimson-400)' }}>
                {data.total_charging_deficits_logged || 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>events</span>
              </div>
            </div>

            <div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span>Fleet Base Degradation Rate</span>
                <TermTooltip text="Average loss in battery capacity retention per 1,000 km driven under normal ambient conditions." pos="top" align="right" />
              </div>
              <div style={{ fontFamily: 'var(--font-display)', fontSize: '18px', fontWeight: 700, color: 'var(--cyan-400)' }}>
                ~0.08% <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>SoH loss / 1,000 km</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Flagged At-Risk Vehicles Table */}
      <div className="glass-panel">
        <div className="panel-header" style={{ padding: '14px 18px' }}>
          <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <IconAlertTriangle size={17} color="var(--crimson-400)" />
            <span>Flagged At-Risk Vehicles Roster</span>
          </div>
          <span style={{ fontSize: '12px', color: 'var(--crimson-400)', fontWeight: 600 }}>
            Immediate Maintenance Recommended
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Vehicle Identifier</th>
                <th>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    Measured SoH%
                    <TermTooltip text="State of Health: Battery capacity retention compared to its factory-new state." pos="top" align="center" />
                  </span>
                </th>
                <th>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    Degradation Category
                    <TermTooltip text="Health classification: Healthy (≥80%), Monitor (75-80%), or Critical (<75%)." pos="top" align="center" />
                  </span>
                </th>
                <th>Recommended Fleet Action</th>
                <th>Operational Status</th>
              </tr>
            </thead>
            <tbody>
              {atRiskList.map((v) => (
                <tr key={v.vehicle_id}>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)' }}>
                    {v.vehicle_id}
                  </td>
                  <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, color: 'var(--crimson-400)' }}>
                    {v.soh_percent}%
                  </td>
                  <td>
                    <span className="badge badge-critical">{v.risk_level}</span>
                  </td>
                  <td style={{ color: 'var(--text-primary)', fontWeight: 500 }}>
                    {v.action_required}
                  </td>
                  <td>
                    <span style={{ fontSize: '12px', color: 'var(--amber-400)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--amber-500)' }}></span>
                      Restrict to Flat/Low-Payload Routes
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
