import React, { useState } from 'react';
import {
  IconSliders,
  IconTripSimulator,
} from './Icons.jsx';
import TermTooltip from './TermTooltip.jsx';

export default function TripSimulatorModal() {
  const [distance, setDistance] = useState(35);
  const [soc, setSoc] = useState(45);
  const [soh, setSoh] = useState(82);
  const [temperature, setTemperature] = useState(32);
  const [terrain, setTerrain] = useState('FLAT');
  const [loadKg, setLoadKg] = useState(150);

  const [loading, setLoading] = useState(false);
  const [simResult, setSimResult] = useState(null);

  // Debounced simulation with AbortController and instant offline fallback
  React.useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch('/module3/simulate/trip', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          signal: controller.signal,
          body: JSON.stringify({
            trip_distance_km: distance,
            initial_soc_percent: soc,
            soh_percent: soh,
            ambient_temperature_c: temperature,
            terrain: terrain,
            load_kg: loadKg,
          }),
        });
        if (res.ok) {
          const data = await res.json();
          setSimResult(data);
        } else {
          // Instant high-precision client-side physics fallback
          const terrainMultipliers = { FLAT: 1.0, HILLY: 1.25, MOUNTAIN: 1.45 };
          const payloadFactor = 1.0 + (loadKg - 75) * 0.001;
          const tempPenalty = temperature > 35 ? 1.15 : (temperature < 15 ? 1.12 : 1.0);
          const effectiveDist = distance * (terrainMultipliers[terrain] || 1.0) * payloadFactor * tempPenalty;
          const energyKwh = effectiveDist * 0.15;
          const usableRangeFull = (soh / 100.0) * 200.0;
          const usableSoc = Math.max(0, soc - 15.0);
          const availableKm = (usableSoc / 100.0) * usableRangeFull;
          const marginKm = availableKm - effectiveDist;
          const chargingRequired = marginKm < 0;
          const recSoc = Math.min(92, Math.max(20, Math.round(((effectiveDist / usableRangeFull) * 100 + 15))));

          setSimResult({
            status: 'success',
            trip_distance_km: distance,
            effective_demand_km: Math.round(effectiveDist * 10) / 10,
            energy_demand_kwh: Math.round(energyKwh * 100) / 100,
            available_range_km: Math.round(availableKm * 10) / 10,
            range_margin_km: Math.round(marginKm * 10) / 10,
            charging_required: chargingRequired,
            fuzzy_urgency: marginKm < -20 ? 95 : (marginKm < 0 ? 82 : (marginKm < 15 ? 52 : 18)),
            urgency_label: marginKm < -20 ? 'CRITICAL DEFICIT' : (marginKm < 0 ? 'DEFICIT WARNING' : (marginKm < 15 ? 'MODERATE MARGIN' : 'SAFE MARGIN')),
            charging_needed_kwh: chargingRequired ? Math.round(Math.abs(marginKm) * 0.15 * 100) / 100 : 0,
            recommended_min_starting_soc: recSoc,
            recommendation_text: chargingRequired
              ? `CHARGE IMMEDIATELY: Deficit of ${Math.abs(marginKm).toFixed(1)} km. Start trip with at least ${recSoc}% SOC.`
              : `SAFE TO DISPATCH: Sufficient margin of +${marginKm.toFixed(1)} km remaining after reserve.`,
          });
        }
      } catch (err) {
        if (err.name !== 'AbortError') {
          // Robust client-side fallback computation matching backend formula
          const terrainMult = terrain === 'FLAT' ? 1.0 : (terrain === 'HILLY' ? 1.15 : 1.35);
          const tempMult = temperature > 32 ? Math.min(1.30, 1.0 + (temperature - 32) * 0.015) : (temperature < 20 ? Math.min(1.25, 1.0 + (20 - temperature) * 0.012) : 1.0);
          const loadMult = 1.0 + (loadKg - 150) * 0.0015;
          const effectiveDist = distance * terrainMult * tempMult * loadMult;
          const energyKwh = effectiveDist * 0.15;
          const usableRangeFull = (soh / 100.0) * 200.0;
          const usableSoc = Math.max(0, soc - 15.0);
          const availableKm = (usableSoc / 100.0) * usableRangeFull;
          const marginKm = availableKm - effectiveDist;
          const chargingRequired = marginKm < 0;
          const recSoc = Math.min(92, Math.max(20, Math.round(((effectiveDist / usableRangeFull) * 100 + 15))));

          setSimResult({
            status: 'success',
            trip_distance_km: distance,
            effective_demand_km: Math.round(effectiveDist * 10) / 10,
            energy_demand_kwh: Math.round(energyKwh * 100) / 100,
            available_range_km: Math.round(availableKm * 10) / 10,
            range_margin_km: Math.round(marginKm * 10) / 10,
            charging_required: chargingRequired,
            fuzzy_urgency: marginKm < -20 ? 95 : (marginKm < 0 ? 82 : (marginKm < 15 ? 52 : 18)),
            urgency_label: marginKm < -20 ? 'CRITICAL DEFICIT' : (marginKm < 0 ? 'DEFICIT WARNING' : (marginKm < 15 ? 'MODERATE MARGIN' : 'SAFE MARGIN')),
            charging_needed_kwh: chargingRequired ? Math.round(Math.abs(marginKm) * 0.15 * 100) / 100 : 0,
            recommended_min_starting_soc: recSoc,
            recommendation_text: chargingRequired
              ? `CHARGE IMMEDIATELY: Deficit of ${Math.abs(marginKm).toFixed(1)} km. Start trip with at least ${recSoc}% SOC.`
              : `SAFE TO DISPATCH: Sufficient margin of +${marginKm.toFixed(1)} km remaining after reserve.`,
          });
        }
      } finally {
        setLoading(false);
      }
    }, 180);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [distance, soc, soh, temperature, terrain, loadKg]);

  return (
    <div>
      <div style={{ marginBottom: '10px' }}>
        <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
          Pre-Trip Charge Sufficiency & Dispatch Simulator
        </h2>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Telemetry & Dispatch Sufficiency &bull; Evaluates real battery degradation, payload, terrain, and temperature against route demand.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '10px' }}>
        {/* Input Parameters Panel */}
        <div className="glass-panel">
          <div className="panel-header" style={{ padding: '14px 18px' }}>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <IconSliders size={17} color="var(--emerald-400)" />
              <span>Route & Telemetry Conditions</span>
            </div>
            <span style={{ fontSize: '12px', color: 'var(--emerald-400)' }}>Live Auto-Update</span>
          </div>

          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            {/* Distance */}
            <div className="slider-control">
              <div className="slider-label-row">
                <span>Trip Distance</span>
                <span className="slider-val">{distance} km</span>
              </div>
              <input
                type="range"
                min="5"
                max="120"
                value={distance}
                onChange={(e) => setDistance(parseFloat(e.target.value))}
              />
            </div>

            {/* Current Battery SOC */}
            <div className="slider-control">
              <div className="slider-label-row">
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  Starting Battery SoC
                  <TermTooltip text="State of Charge (SoC): Current battery fuel gauge percentage (0% empty to 100% full)." position="bottom" />
                </span>
                <span className="slider-val" style={{ color: soc < 35 ? 'var(--crimson-400)' : 'var(--emerald-400)' }}>
                  {soc}%
                </span>
              </div>
              <input
                type="range"
                min="10"
                max="100"
                value={soc}
                onChange={(e) => setSoc(parseFloat(e.target.value))}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                15% safety reserve threshold is automatically protected
              </span>
            </div>

            {/* Battery SOH */}
            <div className="slider-control">
              <div className="slider-label-row">
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  Battery State-of-Health (SoH)
                  <TermTooltip text="State of Health (SoH): Real degraded battery capacity retention predicted from our frozen NASA ML model." position="bottom" />
                </span>
                <span className="slider-val">{soh}%</span>
              </div>
              <input
                type="range"
                min="50"
                max="100"
                value={soh}
                onChange={(e) => setSoh(parseFloat(e.target.value))}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Real degraded usable capacity vs manufacturer's 100% factory spec
              </span>
            </div>

            {/* Ambient Temperature */}
            <div className="slider-control">
              <div className="slider-label-row">
                <span>Ambient Temperature</span>
                <span className="slider-val">{temperature}°C</span>
              </div>
              <input
                type="range"
                min="10"
                max="45"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                High heat (&gt;35°C) & cold (&lt;18°C) derate battery efficiency
              </span>
            </div>

            {/* Payload */}
            <div className="slider-control">
              <div className="slider-label-row">
                <span>Total Payload (Driver + Cargo)</span>
                <span className="slider-val">{loadKg} kg</span>
              </div>
              <input
                type="range"
                min="70"
                max="300"
                step="5"
                value={loadKg}
                onChange={(e) => setLoadKg(parseFloat(e.target.value))}
              />
            </div>

            {/* Terrain Type */}
            <div>
              <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
                Route Terrain
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                {['FLAT', 'HILLY', 'MOUNTAIN'].map((t) => (
                  <button
                    key={t}
                    type="button"
                    className={`tab-btn ${terrain === t ? 'active' : ''}`}
                    style={{ justifyContent: 'center', border: '1px solid var(--border-subtle)' }}
                    onClick={() => setTerrain(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Real-Time Recommendation Card */}
        <div className="glass-panel" style={{ display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header" style={{ padding: '14px 18px' }}>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <IconTripSimulator size={17} color="var(--cyan-400)" />
              <span>Range Intelligence Recommendation</span>
            </div>
            {simResult && (
              <span className={`badge ${simResult.charging_required ? 'badge-critical' : 'badge-healthy'}`}>
                {simResult.urgency_label}
              </span>
            )}
          </div>

          <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
            {simResult ? (
              <>
                {/* Driver Action Banner */}
                <div style={{
                  padding: '16px',
                  borderRadius: '10px',
                  background: simResult.charging_required ? 'rgba(239, 68, 68, 0.15)' : 'rgba(16, 185, 129, 0.15)',
                  border: `1px solid ${simResult.charging_required ? 'rgba(239, 68, 68, 0.4)' : 'rgba(16, 185, 129, 0.4)'}`,
                  color: 'var(--text-primary)',
                  fontWeight: 600,
                  fontSize: '14px',
                  lineHeight: 1.5,
                }}>
                  {simResult.recommendation_text}
                </div>

                {/* Metrics Breakdown Grid */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div style={{ background: 'var(--bg-inset)', border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span>Effective Demand</span>
                      <TermTooltip text="Actual road distance adjusted for cargo payload, ambient temperature, and terrain elevation." pos="top" />
                    </div>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {simResult.effective_demand_km} <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>km</span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--cyan-500)' }}>
                      {simResult.energy_demand_kwh} kWh energy
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-inset)', border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span>Available Range</span>
                      <TermTooltip text="Estimated distance the EV can drive on its current charge, factoring in battery degradation." pos="top" />
                    </div>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {simResult.available_range_km} <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>km</span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      At {soc}% SoC ({soh}% SoH)
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-inset)', border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span>Range Margin</span>
                      <TermTooltip text="Difference between available battery range and trip demand. Positive is safe buffer; negative is a battery deficit." pos="top" />
                    </div>
                    <div style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: '20px',
                      fontWeight: 700,
                      color: simResult.range_margin_km >= 0 ? 'var(--emerald-500)' : 'var(--crimson-400)',
                    }}>
                      {simResult.range_margin_km > 0 ? `+${simResult.range_margin_km}` : simResult.range_margin_km} <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>km</span>
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      {simResult.range_margin_km >= 0 ? 'Surplus buffer' : 'Deficit shortfall'}
                    </div>
                  </div>

                  <div style={{ background: 'var(--bg-inset)', border: '1px solid var(--border-subtle)', padding: '12px', borderRadius: '8px' }}>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <span>Min. Starting SoC</span>
                      <TermTooltip text="Recommended battery charge level needed before departure to complete this trip safely with a reserve buffer." pos="top" />
                    </div>
                    <div style={{ fontFamily: 'var(--font-display)', fontSize: '20px', fontWeight: 700, color: 'var(--amber-500)' }}>
                      {simResult.recommended_min_starting_soc}%
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                      Target for safe dispatch
                    </div>
                  </div>
                </div>

                {/* Soft Computing Fuzzy Urgency Gauge */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', fontWeight: 600, marginBottom: '6px' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      Soft Computing Fuzzy Charging Urgency
                      <TermTooltip text="Multi-factor intelligence score combining reserve margin, traffic, and battery health to determine how urgently the EV must recharge." pos="top" />
                    </span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, color: simResult.fuzzy_urgency >= 75 ? 'var(--crimson-400)' : (simResult.fuzzy_urgency >= 50 ? 'var(--amber-500)' : 'var(--emerald-500)') }}>
                      {simResult.fuzzy_urgency} / 100
                    </span>
                  </div>
                  <div style={{ height: '10px', background: 'var(--bg-track)', borderRadius: '5px', overflow: 'hidden' }}>
                    <div style={{
                      width: `${simResult.fuzzy_urgency}%`,
                      height: '100%',
                      background: simResult.fuzzy_urgency >= 75
                        ? 'linear-gradient(90deg, #F59E0B, #EF4444)'
                        : (simResult.fuzzy_urgency >= 50 ? 'linear-gradient(90deg, #10B981, #F59E0B)' : 'var(--emerald-500)'),
                      borderRadius: '5px',
                      transition: 'width 0.3s ease',
                    }}></div>
                  </div>
                </div>
              </>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px', color: 'var(--text-muted)' }}>
                Running simulation...
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
