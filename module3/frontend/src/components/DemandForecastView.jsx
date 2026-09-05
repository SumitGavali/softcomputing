import React, { useState } from 'react';
import {
  IconDemandForecast,
  IconFleetHealth,
  IconShieldCheck,
} from './Icons.jsx';
import TermTooltip from './TermTooltip.jsx';

export default function DemandForecastView({ demandData }) {
  const data = demandData || {};
  const hourly = data.hourly_profile || [];
  const [hoveredHour, setHoveredHour] = useState(null);

  const maxPower = hourly.length ? Math.max(...hourly.map(h => h.power_demand_kw)) : 500;

  return (
    <div>
      {/* Grid Load Overview KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">
            <span>Daily Energy Requirement</span>
            <TermTooltip text="Aggregated electricity (kWh) needed each day to recharge all fleet delivery vehicles." />
          </div>
          <div className="kpi-value accent-cyan">
            {data.total_daily_charging_kwh ? Number(data.total_daily_charging_kwh).toLocaleString() : 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>kWh/day</span>
          </div>
          <div className="kpi-subtext">Aggregated across all fleet delivery routes</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            <span>Peak Grid Power Spike</span>
            <TermTooltip text="Highest simultaneous electricity draw (kW) on the utility grid during peak operational windows." />
          </div>
          <div className="kpi-value accent-crimson">
            {data.peak_power_demand_kw || 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>kW</span>
          </div>
          <div className="kpi-subtext">Peak window: {data.peak_window || 'N/A'}</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            <span>Base Night Load</span>
            <TermTooltip text="Steady overnight electrical draw (00:00 – 05:00) when vehicles trickle-charge on lower utility tariffs." />
          </div>
          <div className="kpi-value accent-emerald">
            {data.base_power_demand_kw || 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>kW</span>
          </div>
          <div className="kpi-subtext">Overnight steady trickle charging (00:00 &ndash; 05:00)</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            <span>Load-Shift Opportunity</span>
            <TermTooltip text="Portion of charging demand that can be rescheduled to cheap overnight hours to cut power costs by ~25%." />
          </div>
          <div className="kpi-value accent-emerald">
            {data.recommended_off_peak_shift_kwh || 0} <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>kWh</span>
          </div>
          <div className="kpi-subtext">Can be shifted to off-peak TOU tariffs (saves ~25% cost)</div>
        </div>
      </div>

      {/* 24-Hour Interactive Power & Grid Load Chart */}
      <div className="glass-panel" style={{ marginBottom: '10px', overflow: 'visible' }}>
        <div className="panel-header" style={{ padding: '14px 18px' }}>
          <div>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <IconDemandForecast size={17} color="var(--cyan-400)" />
              <span>24-Hour Fleet Power Load & Grid Profile (kW)</span>
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              Hourly simultaneous electrical load and grid draw across Pune urban charging hubs
            </div>
          </div>

          <div style={{ display: 'flex', gap: '14px', fontSize: '12px' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: 'var(--crimson-500)' }}></span>
              Peak Surge
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: 'var(--cyan-500)' }}></span>
              Active Dispatch
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', borderRadius: '2px', background: 'var(--emerald-500)' }}></span>
              Off-Peak Base
            </span>
          </div>
        </div>

        <div className="panel-body" style={{ padding: '18px 18px 22px', overflow: 'visible' }}>
          {/* Static Executive Load Summary Bar (Rock-solid, never jumps or flickers on hover) */}
          <div className="chart-static-summary">
            <div className="summary-pill-item">
              <span className="summary-pill-dot" style={{ background: 'var(--crimson-500)' }}></span>
              <span>Peak Power Spike: <strong>{data.peak_power_demand_kw || 0} kW</strong> ({data.peak_window || '18:00 – 22:00'})</span>
            </div>
            <div className="summary-pill-item">
              <span className="summary-pill-dot" style={{ background: 'var(--emerald-500)' }}></span>
              <span>Base Night Load: <strong>{data.base_power_demand_kw || 0} kW</strong> (Steady 00:00 – 05:00)</span>
            </div>
            <div className="summary-pill-item">
              <span className="summary-pill-dot" style={{ background: 'var(--cyan-500)' }}></span>
              <span>24h Daily Energy: <strong>{data.total_daily_charging_kwh ? Number(data.total_daily_charging_kwh).toLocaleString() : 0} kWh</strong></span>
            </div>
            <div className="summary-pill-item">
              <span className="summary-pill-dot" style={{ background: 'var(--amber-500)' }}></span>
              <span>Shiftable Off-Peak: <strong>{data.recommended_off_peak_shift_kwh || 0} kWh</strong></span>
            </div>
          </div>

          {/* Bar Chart Columns with Interactive Floating Hover Modal */}
          <div className="bar-chart-container">
            {hourly.map((h) => {
              const heightPct = Math.max(8, (h.power_demand_kw / maxPower) * 100);
              const isHovered = hoveredHour?.hour === h.hour;
              const nextHour = String((Number(h.hour) + 1) % 24).padStart(2, '0');

              // Responsive dynamic vertical positioning: anchors modal snugly above the bar crest
              const modalBottom = `calc(${Math.min(heightPct, 84)}% + 28px)`;

              return (
                <div
                  key={h.hour}
                  className={`bar-column ${isHovered ? 'is-hovered' : ''}`}
                  onMouseEnter={() => setHoveredHour(h)}
                  onMouseLeave={() => setHoveredHour(null)}
                >
                  {/* Sleek Floating UI Modal on Hover - Positioned Dynamically Above Bar */}
                  {isHovered && (
                    <div
                      className={`bar-hover-modal ${
                        h.hour <= 2 ? 'align-left' : h.hour >= 21 ? 'align-right' : 'align-center'
                      }`}
                      style={{ bottom: modalBottom }}
                    >
                      <div className="bhm-header">
                        <span className="bhm-hour">
                          {h.hour_label} &ndash; {nextHour}:00
                        </span>
                        <span
                          className="bhm-badge"
                          style={{
                            background: `${h.status_color}22`,
                            color: h.status_color,
                            border: `1px solid ${h.status_color}55`,
                          }}
                        >
                          {h.period_type === 'PEAK_SURGE'
                            ? 'Peak Surge'
                            : h.period_type === 'ACTIVE_DISPATCH'
                            ? 'Active Dispatch'
                            : 'Off-Peak Base'}
                        </span>
                      </div>

                      <div className="bhm-metrics">
                        <div className="bhm-metric-row">
                          <span className="bhm-label">Simultaneous Power:</span>
                          <span className="bhm-value" style={{ color: h.status_color }}>
                            {h.power_demand_kw} kW
                          </span>
                        </div>
                        <div className="bhm-metric-row">
                          <span className="bhm-label">Energy Draw:</span>
                          <span className="bhm-value">{h.energy_demand_kwh} kWh</span>
                        </div>
                        <div className="bhm-metric-row">
                          <span className="bhm-label">Active Charging EVs:</span>
                          <span className="bhm-value">~{h.active_charging_vehicles} vehicles</span>
                        </div>
                        <div className="bhm-metric-row bhm-tariff-row">
                          <span className="bhm-label">TOD Tariff:</span>
                          <span
                            className="bhm-value"
                            style={{
                              color:
                                h.period_type === 'PEAK_SURGE'
                                  ? 'var(--crimson-400)'
                                  : h.period_type === 'OFF_PEAK_BASE'
                                  ? 'var(--emerald-400)'
                                  : 'var(--cyan-400)',
                            }}
                          >
                            {h.period_type === 'PEAK_SURGE'
                              ? '₹12.50 / kWh (Peak)'
                              : h.period_type === 'OFF_PEAK_BASE'
                              ? '₹5.80 / kWh (Off-Peak)'
                              : '₹8.20 / kWh (Standard)'}
                          </span>
                        </div>
                      </div>

                      <div className="bhm-arrow" />
                    </div>
                  )}

                  <div
                    className="bar-fill"
                    style={{
                      height: `${heightPct}%`,
                      background: h.status_color,
                      boxShadow: isHovered ? `0 0 16px ${h.status_color}` : 'none',
                    }}
                  ></div>
                  <div className="bar-hour-label">{h.hour}h</div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Grid Load & CPO Partnership Strategy */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        <div className="glass-panel">
          <div className="panel-header" style={{ padding: '14px 18px' }}>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <IconFleetHealth size={17} color="var(--emerald-400)" />
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span>Peak Shaving & TOU Tariff Optimization</span>
                <TermTooltip text="Time-Of-Use (TOU) tariffs charge less for off-peak power. Peak shaving reschedules charging to avoid high rush-hour electricity rates." pos="top" align="left" />
              </span>
            </div>
          </div>
          <div className="panel-body" style={{ padding: '18px', fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            Urban commercial utility rates in Maharashtra follow time-of-day (TOD) tariff slabs:
            <ul style={{ marginLeft: '20px', marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <li><strong>Peak Window (18:00 - 22:00):</strong> ₹12.50 / kWh (High demand surcharge)</li>
              <li><strong>Standard Day (09:00 - 18:00):</strong> ₹8.20 / kWh</li>
              <li><strong>Off-Peak Night (22:00 - 06:00):</strong> ₹5.80 / kWh (Night concession)</li>
            </ul>
            <p style={{ marginTop: '12px' }}>
              By shifting <strong>{data.recommended_off_peak_shift_kwh || 0} kWh</strong> of nightly fleet charging into the 00:00 &ndash; 05:00 window, the fleet saves up to <strong>₹21,200 monthly</strong> on electrical power procurement alone.
            </p>
          </div>
        </div>

        <div className="glass-panel">
          <div className="panel-header" style={{ padding: '14px 18px' }}>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <IconShieldCheck size={17} color="var(--cyan-400)" />
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
                <span>CPO & Grid Interconnection Strategy</span>
                <TermTooltip text="Charge Point Operator (CPO) planning for substation transformers, power contracts, and battery swapping infrastructure." pos="top" align="left" />
              </span>
            </div>
          </div>
          <div className="panel-body" style={{ padding: '18px', fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)' }}>
            The 24-hour fleet power profile informs infrastructure right-sizing:
            <ul style={{ marginLeft: '20px', marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
              <li><strong>Contract Demand Sanctioning:</strong> Eliminates MSEDCL penalty surcharges by staying under <strong>{data.peak_power_demand_kw || 0} kW</strong>.</li>
              <li><strong>Transformer Sizing:</strong> Minimum 500 kVA dedicated step-down transformer required across key hubs.</li>
              <li><strong>Battery Swapping Advantage:</strong> Swap bays recharge depleted packs at steady 1C rate off-peak, reducing peak grid draw by <strong>~30%</strong>.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
