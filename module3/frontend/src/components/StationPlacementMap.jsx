import React, { useEffect, useRef, useState, useMemo } from 'react';
import L from 'leaflet';
import {
  IconStationMap,
  IconSliders,
  IconBolt,
  IconDownload,
  IconLayers,
  IconRefresh,
  IconMaximize,
  IconX,
} from './Icons.jsx';
import TermTooltip from './TermTooltip.jsx';

// React-based intelligent collision-clamped station hover modal
// Eliminates all Leaflet popup clipping at all 4 corners (top-left, top-right, bottom-left, bottom-right)
function StationHoverModal({
  station,
  pt,
  containerWidth = 800,
  containerHeight = 490,
  onMouseEnter,
  onMouseLeave,
}) {
  const cardRef = useRef(null);
  const [measuredHeight, setMeasuredHeight] = useState(230);

  useEffect(() => {
    if (cardRef.current) {
      const h = cardRef.current.offsetHeight;
      if (h && Math.abs(h - measuredHeight) > 4) {
        setMeasuredHeight(h);
      }
    }
  }, [station]);

  if (!station || !pt) return null;

  const modalWidth = 330;
  const modalHeight = measuredHeight || 230;

  // Decide whether to place above or below the marker
  // If marker is within modalHeight + 25px of the top edge, place below to prevent top clipping
  const placeBelow = pt.y < modalHeight + 25;
  let top = placeBelow ? pt.y + 22 : pt.y - modalHeight - 16;
  // Strict vertical clamping: strictly within [10px, containerHeight - modalHeight - 10px]
  top = Math.max(10, Math.min(top, containerHeight - modalHeight - 10));

  // Strict horizontal clamping: centered on marker, but strictly within [12px, containerWidth - modalWidth - 12px]
  let left = pt.x - modalWidth / 2;
  left = Math.max(12, Math.min(left, containerWidth - modalWidth - 12));

  // The arrow dynamically tracks the marker's actual X position relative to the clamped modal card
  const arrowLeft = Math.max(22, Math.min(modalWidth - 22, pt.x - left));

  const eq = station.equipment || {};
  const priorityScore = station.priority_score || 4;
  const badgeColor = priorityScore >= 5 ? 'var(--crimson-400)' : 'var(--emerald-400)';
  const badgeBg = priorityScore >= 5 ? 'rgba(239, 68, 68, 0.14)' : 'rgba(16, 185, 129, 0.14)';
  const badgeBorder = priorityScore >= 5 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(16, 185, 129, 0.3)';

  return (
    <div
      ref={cardRef}
      className="station-floating-hover-card"
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      style={{
        position: 'absolute',
        top: `${Math.round(top)}px`,
        left: `${Math.round(left)}px`,
        width: `${modalWidth}px`,
        zIndex: 1050,
      }}
    >
      {/* Dynamic tracking arrow */}
      <div
        className={`station-modal-arrow ${placeBelow ? 'arrow-top' : 'arrow-bottom'}`}
        style={{ left: `${Math.round(arrowLeft)}px` }}
      />

      <div className="station-modal-card">
        <div className="smc-header">
          <div className="smc-hub-id">{station.station_id}</div>
          <span
            className="smc-badge"
            style={{ background: badgeBg, color: badgeColor, border: `1px solid ${badgeBorder}` }}
          >
            {station.priority_label || 'RECOMMENDED HUB'}
          </span>
        </div>

        <div className="smc-title">{station.name}</div>
        {station.address && (
          <div style={{ fontSize: '11px', color: 'var(--cyan-400)', marginBottom: '4px', lineHeight: 1.3 }}>
            📍 {station.address}
          </div>
        )}
        <div className="smc-zone">
          Zone: <strong>{station.zone}</strong> &bull; Site: <strong>{station.site_type || 'Commercial Hub'}</strong> &bull; Catchment:{' '}
          <strong style={{ color: 'var(--emerald-400)' }}>{station.coverage_radius_km} km</strong>
        </div>

        <div className="smc-metrics-grid">
          <div className="smc-metric-cell">
            <div className="smc-cell-label">Covered Deficit</div>
            <div className="smc-cell-val" style={{ color: 'var(--emerald-400)' }}>
              {station.covered_deficit_kwh} <small>kWh</small>
            </div>
          </div>
          <div className="smc-metric-cell">
            <div className="smc-cell-label">Covered Trips</div>
            <div className="smc-cell-val">
              {station.covered_trips_count} <small>trips</small>
            </div>
          </div>
          <div className="smc-metric-cell">
            <div className="smc-cell-label">Rescues Averted</div>
            <div className="smc-cell-val" style={{ color: 'var(--crimson-400)' }}>
              {station.critical_shortages_covered} <small>dropouts</small>
            </div>
          </div>
          <div className="smc-metric-cell">
            <div className="smc-cell-label">Grid Peak Cap.</div>
            <div className="smc-cell-val" style={{ color: 'var(--cyan-400)' }}>
              {eq.total_simultaneous_capacity_kw || 0} <small>kW</small>
            </div>
          </div>
        </div>

        <div className="smc-hw-row">
          <span>Hardware: </span>
          <strong>
            {eq.ac_slow_ports || 0}x AC (3.3kW) &bull; {eq.dc_fast_ports || 0}x DC Fast (15kW)
            {eq.battery_swap_bays > 0 ? ` &bull; ${eq.battery_swap_bays}x Swap Bay` : ''}
          </strong>
        </div>
      </div>
    </div>
  );
}

// 100% Free, Official OpenStreetMap Tiles (Zero Watermarks, Zero Auth Keys Required)
const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

// Network distance helper applying Pune urban circuity factor (tau = 1.32)
function calculateDistanceKm(lat1, lon1, lat2, lon2) {
  const dLat = (lat2 - lat1) * 110.574;
  const dLon = (lon2 - lon1) * 111.32 * Math.cos((lat1 * Math.PI) / 180);
  return Math.sqrt(dLat * dLat + dLon * dLon) * 1.32;
}

function createStationDivIcon(idx, isSelected) {
  const markerHtml = `
    <div style="
      background: ${isSelected ? 'linear-gradient(135deg, #34D399, #22D3EE)' : 'linear-gradient(135deg, #10B981, #06B6D4)'};
      width: ${isSelected ? '36px' : '32px'};
      height: ${isSelected ? '36px' : '32px'};
      border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      color: #000; font-family: 'Sora', sans-serif; font-weight: 800;
      font-size: ${isSelected ? '14px' : '13px'};
      box-shadow: ${isSelected ? '0 0 24px rgba(52, 211, 153, 0.9), 0 0 0 3px #ffffff' : '0 0 16px rgba(16, 185, 129, 0.6), 0 0 0 2px #fff'};
      cursor: pointer;
      transition: all 0.2s ease;
    ">
      ${idx}
    </div>
  `;
  return L.divIcon({
    html: markerHtml,
    className: 'station-icon-marker',
    iconSize: [32, 32],
    iconAnchor: [16, 16],
    popupAnchor: [0, -18],
  });
}

export default function StationPlacementMap({
  stationsData,
  heatPoints,
  kStations,
  setKStations,
  coverageRadius,
  setCoverageRadius,
  loading,
  onRecalculate,
  theme = 'dark',
}) {
  const mapContainerRef = useRef(null);
  const mapWrapperRef = useRef(null);
  const mapRef = useRef(null);
  const layerGroupRef = useRef(null);
  const spiderwebGroupRef = useRef(null);
  const markersMapRef = useRef(new Map());
  const circlesMapRef = useRef(new Map());

  const [showDeficits, setShowDeficits] = useState(true);
  const [showRadii, setShowRadii] = useState(true);
  const [showSpiderweb, setShowSpiderweb] = useState(true);
  const [selectedStationId, setSelectedStationId] = useState(null);
  const selectedStationIdRef = useRef(selectedStationId);
  const [roadRoutesGeoJson, setRoadRoutesGeoJson] = useState(null);
  const [routesLoading, setRoutesLoading] = useState(false);

  const [hoveredStation, setHoveredStation] = useState(null);
  const hoveredStationRef = useRef(null);
  const hoverTimerRef = useRef(null);

  // Fetch real OpenStreetMap OSRM road routes when a station is selected
  useEffect(() => {
    if (!selectedStationId) {
      setRoadRoutesGeoJson(null);
      return;
    }

    let isCancelled = false;
    setRoutesLoading(true);

    const params = new URLSearchParams({
      station_id: selectedStationId,
      limit: '15',
      k_stations: String(kStations),
      coverage_radius_km: String(coverageRadius),
    });

    fetch(`/module3/routes/hub-assignment?${params}`, {
      signal: AbortSignal.timeout(6000),
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!isCancelled && data && data.features) {
          setRoadRoutesGeoJson(data);
        }
      })
      .catch((err) => {
        console.warn('Could not load OSRM road routes:', err);
      })
      .finally(() => {
        if (!isCancelled) setRoutesLoading(false);
      });

    return () => {
      isCancelled = true;
    };
  }, [selectedStationId, kStations, coverageRadius]);

  useEffect(() => {
    selectedStationIdRef.current = selectedStationId;
  }, [selectedStationId]);

  useEffect(() => {
    hoveredStationRef.current = hoveredStation;
  }, [hoveredStation]);

  const stations = stationsData?.stations || [];

  // Compute spatial assignments: assign each deficit point to its closest station
  const deficitAssignments = useMemo(() => {
    if (!stations.length || !heatPoints || !heatPoints.length) return [];
    return heatPoints.slice(0, 450).map((pt) => {
      let closestStation = stations[0];
      let minDistance = Infinity;

      for (const st of stations) {
        const d = calculateDistanceKm(pt.lat, pt.lon, st.latitude, st.longitude);
        if (d < minDistance) {
          minDistance = d;
          closestStation = st;
        }
      }

      return {
        point: pt,
        stationId: closestStation.station_id,
        stationCoords: [closestStation.latitude, closestStation.longitude],
        distanceKm: minDistance,
      };
    });
  }, [stations, heatPoints]);

  // 1. Initialize Leaflet Map (Robust, zero-auth, zero-watermark)
  useEffect(() => {
    if (!mapContainerRef.current) return;

    if (mapRef.current) {
      try {
        mapRef.current.remove();
      } catch (e) {}
      mapRef.current = null;
    }
    if (mapContainerRef.current) {
      mapContainerRef.current.innerHTML = '';
    }

    const centerLat = stationsData?.geographic_center ? stationsData.geographic_center[0] : 18.5204;
    const centerLon = stationsData?.geographic_center ? stationsData.geographic_center[1] : 73.8567;

    const map = L.map(mapContainerRef.current, {
      center: [centerLat, centerLon],
      zoom: 12,
      zoomControl: false,
    });

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    L.tileLayer(OSM_TILE_URL, {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
      maxZoom: 19,
    }).addTo(map);

    const spiderwebGroup = L.layerGroup().addTo(map);
    const layerGroup = L.layerGroup().addTo(map);

    mapRef.current = map;
    layerGroupRef.current = layerGroup;
    spiderwebGroupRef.current = spiderwebGroup;

    // Real-time hover modal tracking on map drag or zoom
    const handleMapMove = () => {
      if (!hoveredStationRef.current) return;
      const st = hoveredStationRef.current.station;
      const pt = map.latLngToContainerPoint([st.latitude, st.longitude]);
      const width = mapContainerRef.current?.clientWidth || 800;
      const height = mapContainerRef.current?.clientHeight || 490;
      // Auto-hide if panned completely off screen
      if (pt.x < -60 || pt.x > width + 60 || pt.y < -60 || pt.y > height + 60) {
        setHoveredStation(null);
        return;
      }
      setHoveredStation({ station: st, pt });
    };

    map.on('move', handleMapMove);
    map.on('zoom', handleMapMove);

    const handleResize = () => {
      if (mapRef.current) mapRef.current.invalidateSize();
    };
    window.addEventListener('resize', handleResize);

    setTimeout(() => {
      if (mapRef.current) mapRef.current.invalidateSize();
    }, 200);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (mapRef.current) {
        try {
          map.off('move', handleMapMove);
          map.off('zoom', handleMapMove);
          mapRef.current.remove();
        } catch (e) {}
        mapRef.current = null;
      }
    };
  }, []);

  // 2. Render Markers, Coverage Circles, and Deficit Heat Points
  useEffect(() => {
    if (!mapRef.current || !layerGroupRef.current) return;

    const layer = layerGroupRef.current;
    layer.clearLayers();
    markersMapRef.current.clear();

    // Render Battery Deficit Heat Points
    if (showDeficits && heatPoints && heatPoints.length > 0) {
      heatPoints.slice(0, 800).forEach((pt) => {
        const circle = L.circleMarker([pt.lat, pt.lon], {
          radius: 4,
          fillColor: pt.urgency >= 80 ? '#EF4444' : '#F59E0B',
          color: 'transparent',
          fillOpacity: 0.38,
        });
        circle.bindTooltip(`Deficit: ${pt.deficit_kwh} kWh &bull; Urgency: ${pt.urgency}%`, {
          className: 'leaflet-tooltip-dark',
        });
        layer.addLayer(circle);
      });
    }

    // Render Recommended Charging Stations & Catchment Circles
    if (stations.length > 0) {
      circlesMapRef.current.clear();

      stations.forEach((st, idx) => {
        const isSelected = selectedStationId === st.station_id;

        if (showRadii) {
          const coverageCircle = L.circle([st.latitude, st.longitude], {
            radius: st.coverage_radius_km * 1000,
            color: isSelected ? '#34D399' : '#10B981',
            weight: isSelected ? 2.5 : 1.5,
            dashArray: '4, 6',
            fillColor: '#10B981',
            fillOpacity: isSelected ? 0.14 : 0.07,
          });
          circlesMapRef.current.set(st.station_id, coverageCircle);
          layer.addLayer(coverageCircle);
        }

        const customIcon = createStationDivIcon(idx + 1, isSelected);
        const marker = L.marker([st.latitude, st.longitude], { icon: customIcon });

        // 1. Mouseover: Show React hover modal ONLY if this station is NOT currently selected
        marker.on('mouseover', () => {
          if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
          if (selectedStationIdRef.current === st.station_id) return;

          const map = mapRef.current;
          if (!map) return;
          const pt = map.latLngToContainerPoint([st.latitude, st.longitude]);
          setHoveredStation({ station: st, pt });
        });

        // 2. Mouseout: Automatically close after debounce so user can move cursor to card
        marker.on('mouseout', () => {
          if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
          hoverTimerRef.current = setTimeout(() => {
            setHoveredStation((prev) => (prev?.station?.station_id === st.station_id ? null : prev));
          }, 120);
        });

        // 3. Click: Toggle selection (shows connecting lines) and NEVER show hover modal
        marker.on('click', () => {
          if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
          setHoveredStation(null);
          setSelectedStationId((prev) => (prev === st.station_id ? null : st.station_id));
        });

        markersMapRef.current.set(st.station_id, marker);
        layer.addLayer(marker);
      });

      // Auto-fit bounds with generous top headroom for unclipped popups
      const latLngs = stations.map((s) => [s.latitude, s.longitude]);
      try {
        mapRef.current.fitBounds(L.latLngBounds(latLngs), {
          paddingTopLeft: [50, 140],
          paddingBottomRight: [50, 50],
          maxZoom: 13,
        });
      } catch (e) {}
    }
  }, [stationsData, heatPoints, showDeficits, showRadii]);

  // 3. Dynamic styling when selectedStationId changes (without destroying markers)
  useEffect(() => {
    stations.forEach((st, idx) => {
      const isSelected = selectedStationId === st.station_id;
      const marker = markersMapRef.current.get(st.station_id);
      if (marker) {
        marker.setIcon(createStationDivIcon(idx + 1, isSelected));
      }
      const circle = circlesMapRef.current.get(st.station_id);
      if (circle) {
        circle.setStyle({
          color: isSelected ? '#34D399' : '#10B981',
          weight: isSelected ? 2.5 : 1.5,
          fillOpacity: isSelected ? 0.14 : 0.07,
        });
      }
    });

    if (hoveredStationRef.current && hoveredStationRef.current.station.station_id === selectedStationId) {
      setHoveredStation(null);
    }
  }, [selectedStationId, stations]);

  // 3. Render Spiderweb Deficit Assignment Lines or Turn-by-Turn OSRM Road Routes
  useEffect(() => {
    if (!mapRef.current || !spiderwebGroupRef.current) return;

    const spiderLayer = spiderwebGroupRef.current;
    spiderLayer.clearLayers();

    // If a station is selected and we have authentic road routes GeoJSON from OSRM:
    if (selectedStationId && roadRoutesGeoJson && roadRoutesGeoJson.features && roadRoutesGeoJson.features.length > 0) {
      const geoJsonLayer = L.geoJSON(roadRoutesGeoJson, {
        style: (feature) => {
          const props = feature.properties || {};
          const isCritical = Boolean(props.is_critical);
          return {
            color: isCritical ? '#EF4444' : '#10B981',
            weight: 3.5,
            opacity: 0.9,
            dashArray: isCritical ? '6, 6' : undefined,
            lineJoin: 'round',
            lineCap: 'round',
          };
        },
        onEachFeature: (feature, layer) => {
          const props = feature.properties || {};
          const isCritical = Boolean(props.is_critical);
          const distKm = props.distance_km != null ? Number(props.distance_km).toFixed(1) : '?';
          const durMin = props.duration_min != null ? Number(props.duration_min).toFixed(0) : '?';
          const street = props.street_name || 'Pune Delivery Corridor';
          const kwh = props.deficit_kwh != null ? Number(props.deficit_kwh).toFixed(1) : '';

          layer.bindTooltip(
            `
            <div style="font-family: Inter, sans-serif; font-size: 11px; padding: 2px 4px; line-height: 1.4;">
              <div style="font-weight: 700; color: ${isCritical ? '#EF4444' : '#10B981'}; display: flex; align-items: center; gap: 4px;">
                <span>${isCritical ? '🚨 CRITICAL RESCUE ROUTE' : '🛣️ ROAD ACCESS ROUTE'}</span>
              </div>
              <div style="color: #E2E8F0; margin-top: 2px;">${street}</div>
              <div style="color: #94A3B8; font-size: 10px; margin-top: 1px;">
                Road Distance: <strong style="color: #F8FAFC;">${distKm} km</strong> &bull; Drive Time: <strong style="color: #F8FAFC;">${durMin} min</strong>
                ${kwh ? ` &bull; Deficit: <strong style="color: #F59E0B;">${kwh} kWh</strong>` : ''}
              </div>
            </div>
            `,
            {
              className: 'leaflet-tooltip-dark',
              sticky: true,
            }
          );
        },
      });
      spiderLayer.addLayer(geoJsonLayer);
      return;
    }

    // Default spiderweb overview lines if no specific road routes or while loading
    if (!showSpiderweb || !deficitAssignments.length) return;

    deficitAssignments.forEach((item) => {
      const isStationSelected = selectedStationId === item.stationId;
      const isAnySelected = Boolean(selectedStationId);

      // If a station is selected, only emphasize its assigned dropouts
      if (isAnySelected && !isStationSelected) return;

      const line = L.polyline(
        [
          [item.point.lat, item.point.lon],
          item.stationCoords,
        ],
        {
          color: isStationSelected ? '#10B981' : 'rgba(6, 182, 212, 0.4)',
          weight: isStationSelected ? 2 : 1,
          opacity: isStationSelected ? 0.85 : 0.25,
          dashArray: isStationSelected ? '2, 4' : '3, 6',
        }
      );
      spiderLayer.addLayer(line);
    });
  }, [deficitAssignments, showSpiderweb, selectedStationId, roadRoutesGeoJson]);

  const roi = stationsData?.roi_analysis || {};

  const handleStationRowClick = (st) => {
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    setHoveredStation(null);
    setSelectedStationId((prev) => (prev === st.station_id ? null : st.station_id));
    if (mapRef.current) {
      mapRef.current.flyTo([st.latitude, st.longitude], 13, { duration: 0.8 });
    }
  };

  const handleResetView = () => {
    if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
    setHoveredStation(null);
    if (!mapRef.current || !stations.length) return;
    const latLngs = stations.map((s) => [s.latitude, s.longitude]);
    try {
      mapRef.current.fitBounds(L.latLngBounds(latLngs), {
        paddingTopLeft: [50, 140],
        paddingBottomRight: [50, 50],
        maxZoom: 13,
      });
    } catch (e) {}
  };

  const handleExportCSV = () => {
    if (!stations || stations.length === 0) return;
    const headers = [
      'Station ID',
      'Name',
      'Zone',
      'Address',
      'Site Type',
      'Latitude',
      'Longitude',
      'Radius (km)',
      'Covered Trips',
      'Deficit kWh',
      'Critical Averted',
      'AC Ports',
      'DC Ports',
      'Swap Bays',
      'Capacity kW',
    ];
    const rows = stations.map((s) => [
      s.station_id,
      `"${s.name}"`,
      `"${s.zone}"`,
      `"${s.address || 'Pune Commercial Corridor'}"`,
      `"${s.site_type || 'Commercial Hub'}"`,
      s.latitude,
      s.longitude,
      s.coverage_radius_km,
      s.covered_trips_count,
      s.covered_deficit_kwh,
      s.critical_shortages_covered,
      s.equipment?.ac_slow_ports || 0,
      s.equipment?.dc_fast_ports || 0,
      s.equipment?.battery_swap_bays || 0,
      s.equipment?.total_simultaneous_capacity_kw || 0,
    ]);
    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [headers.join(','), ...rows.map((e) => e.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `pune_ev_stations_k${kStations}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div>
      {/* Fleet ROI Impact Summary Banner - Compact Spacing */}
      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">
            <span>Deficit Fleet Coverage</span>
            <TermTooltip text="Percentage of delivery energy deficits successfully covered and relieved by the recommended charging network." />
          </div>
          <div className="kpi-value accent-emerald">
            {roi.fleet_deficit_coverage_percent || 0}%
          </div>
          <div className="kpi-subtext">Across {roi.total_covered_trips || 0} fleet delivery trips</div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            <span>Deadhead Distance Saved</span>
            <TermTooltip text="Kilometers saved monthly from delivery drivers avoiding long off-route detours to find distant commercial chargers." />
          </div>
          <div className="kpi-value accent-cyan">
            {roi.monthly_deadhead_km_saved ? Number(roi.monthly_deadhead_km_saved).toLocaleString() : 0}{' '}
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>km</span>
          </div>
          <div className="kpi-subtext">
            Saves ₹{roi.monthly_deadhead_savings_inr ? Number(roi.monthly_deadhead_savings_inr).toLocaleString() : 0} in wasted transit
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            <span>Stranded Rescues Averted</span>
            <TermTooltip text="Breakdown towing events prevented where battery would have dropped below the 20% emergency reserve." />
          </div>
          <div className="kpi-value accent-amber">
            {roi.monthly_stranded_events_averted || 0}{' '}
            <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>events/mo</span>
          </div>
          <div className="kpi-subtext">
            Saves ₹{roi.monthly_towing_savings_inr ? Number(roi.monthly_towing_savings_inr).toLocaleString() : 0} in towing
          </div>
        </div>

        <div className="kpi-card">
          <div className="kpi-label">
            <span>Total Monthly Fleet ROI</span>
            <TermTooltip text="Estimated monthly operational cost savings combining avoided towing fees and deadhead transit miles." />
          </div>
          <div className="kpi-value accent-emerald">
            ₹{roi.total_monthly_fleet_savings_inr ? Number(roi.total_monthly_fleet_savings_inr).toLocaleString() : 0}
          </div>
          <div className="kpi-subtext">
            Annualized: ₹{roi.annualized_fleet_savings_inr ? Number(roi.annualized_fleet_savings_inr).toLocaleString() : 0}
          </div>
        </div>
      </div>

      {/* Map & Interactive Controls Panel */}
      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '10px', marginBottom: '10px' }}>
        {/* Controls Sidebar with Button at Top & Compact Form */}
        <div className="glass-panel" style={{ height: '490px', display: 'flex', flexDirection: 'column' }}>
          <div className="panel-header" style={{ padding: '12px 16px' }}>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <IconSliders size={18} color="var(--emerald-400)" />
              <span>Optimizer Controls</span>
            </div>
            {loading && <span style={{ fontSize: '11px', color: 'var(--emerald-400)' }}>Computing...</span>}
          </div>

          <div className="panel-body" style={{ padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: '11px', flex: 1, overflowY: 'auto' }}>
            {/* Primary Action Button Prominently at Top */}
            <button
              className="btn-primary"
              style={{ width: '100%', justifyContent: 'center', padding: '10px 16px', gap: '8px' }}
              onClick={onRecalculate}
              disabled={loading}
            >
              {loading ? (
                <IconRefresh size={15} className="spin-animation" />
              ) : (
                <IconBolt size={16} />
              )}
              <span>{loading ? 'Optimizing Placements...' : 'Re-Optimize Placements'}</span>
            </button>

            {/* Slider 1: Number of Hubs */}
            <div className="slider-control">
              <div className="slider-label-row">
                <span style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  Number of Hubs (k):
                  <TermTooltip text="Number of charging stations to strategically deploy across the urban network." position="bottom" align="left" />
                </span>
                <span className="slider-val" style={{ fontSize: '12px' }}>{kStations} Stations</span>
              </div>
              <input
                type="range"
                min="1"
                max="10"
                value={kStations}
                onChange={(e) => setKStations(parseInt(e.target.value))}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Target charging station locations to deploy
              </span>
            </div>

            {/* Slider 2: Service Radius */}
            <div className="slider-control">
              <div className="slider-label-row">
                <span style={{ fontSize: '12px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                  Coverage Service Radius:
                  <TermTooltip text="Maximum service radius within which a charging hub captures and services passing fleet trips." position="bottom" align="left" />
                </span>
                <span className="slider-val" style={{ fontSize: '12px' }}>{coverageRadius.toFixed(1)} km</span>
              </div>
              <input
                type="range"
                min="1.0"
                max="6.0"
                step="0.5"
                value={coverageRadius}
                onChange={(e) => setCoverageRadius(parseFloat(e.target.value))}
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Maximum diversion tolerance for 2W/3W drivers
              </span>
            </div>

            {/* Map Layer Toggles */}
            <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-secondary)' }}>
                Map Layer Overlays
              </div>

              <label style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '12px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={showDeficits}
                  onChange={(e) => setShowDeficits(e.target.checked)}
                  style={{ accentColor: 'var(--crimson-500)', width: '15px', height: '15px' }}
                />
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  Battery Deficit Dropouts ({heatPoints?.length || 0})
                  <TermTooltip text="Historical GPS locations where electric delivery vehicles reached critical low charge (<15%)." position="bottom" align="left" />
                </span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '12px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={showRadii}
                  onChange={(e) => setShowRadii(e.target.checked)}
                  style={{ accentColor: 'var(--emerald-500)', width: '15px', height: '15px' }}
                />
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  Service Catchment Rings ({coverageRadius}km)
                  <TermTooltip text="The geographical area covered around each hub based on chosen service radius." position="bottom" align="left" />
                </span>
              </label>

              <label style={{ display: 'flex', alignItems: 'center', gap: '9px', fontSize: '12px', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={showSpiderweb}
                  onChange={(e) => setShowSpiderweb(e.target.checked)}
                  style={{ accentColor: 'var(--cyan-500)', width: '15px', height: '15px' }}
                />
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  Deficit Assignment Network (Spiderweb)
                  <TermTooltip text="Direct connection lines showing which hub services each individual battery deficit location." position="bottom" align="left" />
                </span>
              </label>
            </div>

            {/* Optimization Insights Box (Eliminates Empty Space) */}
            <div
              style={{
                marginTop: 'auto',
                padding: '12px 14px',
                borderRadius: '8px',
                background: 'var(--bg-inset)',
                border: '1px solid var(--border-subtle)',
                fontSize: '11px',
                lineHeight: 1.5,
              }}
            >
              <div style={{ fontWeight: 700, color: 'var(--emerald-500)', marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <IconStationMap size={14} color="var(--emerald-500)" />
                <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                  Spatial Clustering Health
                  <TermTooltip text="Real-time check verifying hubs are spaced logically without redundant clustering or dead zones." position="top" align="left" />
                </span>
              </div>
              <div style={{ color: 'var(--text-secondary)' }}>
                {selectedStationId ? (
                  <>
                    Active Focus: <strong style={{ color: 'var(--cyan-400)' }}>{selectedStationId}</strong>. Showing dedicated deficit assignments.
                  </>
                ) : (
                  <>
                    {stations.length} hubs deployed across Pune. Click any station or row below to isolate its assigned deficit catchment.
                  </>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Map Viewport Container - Isolated stacking context so map elements never bleed over sticky header */}
        <div
          ref={mapWrapperRef}
          className="glass-panel"
          style={{
            height: '490px',
            position: 'relative',
            overflow: 'hidden',
            isolation: 'isolate',
            zIndex: 1,
          }}
        >
          {/* Active Engine & Selection Badges - Positioned at bottom-left so the top is 100% free of popup obstructions */}
          <div
            style={{
              position: 'absolute',
              bottom: '12px',
              left: '12px',
              zIndex: 30,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              flexWrap: 'wrap',
              pointerEvents: 'none',
            }}
          >
            <div className="osm-status-tag">
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: 'var(--emerald-500)',
                  boxShadow: '0 0 8px var(--emerald-500)',
                }}
              ></span>
              <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <IconLayers size={13} color="var(--emerald-400)" />
                <span>OpenStreetMap</span>
              </span>
            </div>

            {selectedStationId && (
              <div
                className="osm-status-tag"
                style={{
                  background: 'rgba(16, 185, 129, 0.12)',
                  borderColor: 'rgba(16, 185, 129, 0.3)',
                  color: 'var(--emerald-400)',
                }}
              >
                <span>🛣️ {routesLoading ? 'Routing via OSRM...' : 'OSRM Road Routes Active'}</span>
              </div>
            )}

            {/* High-Visibility Tactile Clear Focus Button */}
            {selectedStationId && (
              <button
                onClick={() => {
                  setSelectedStationId(null);
                  setHoveredStation(null);
                }}
                className="clear-hub-focus-btn"
                title={`Reset focus to all ${stations.length} hubs`}
              >
                <IconX size={12} color="currentColor" />
                <span>Clear Focus</span>
                <span className="clear-focus-station-chip">{selectedStationId}</span>
              </button>
            )}

            {/* Quick Map Action: Fit Territory */}
            <button
              onClick={handleResetView}
              className="map-action-pill-btn"
              title="Fit all stations & Pune territory"
            >
              <IconMaximize size={12} color="var(--cyan-400)" />
              <span>Fit Territory</span>
            </button>
          </div>

          {/* Intelligently Clamped Station Hover Modal - 100% visible at all 4 corners & edges */}
          {hoveredStation && (
            <StationHoverModal
              station={hoveredStation.station}
              pt={hoveredStation.pt}
              containerWidth={mapWrapperRef.current?.clientWidth || mapContainerRef.current?.clientWidth || 800}
              containerHeight={mapWrapperRef.current?.clientHeight || mapContainerRef.current?.clientHeight || 490}
              onMouseEnter={() => {
                if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
              }}
              onMouseLeave={() => {
                if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
                hoverTimerRef.current = setTimeout(() => {
                  setHoveredStation(null);
                }, 120);
              }}
            />
          )}

          <div ref={mapContainerRef} className="map-viewport" style={{ height: '100%', width: '100%' }}></div>
        </div>
      </div>

      {/* Recommended Stations Data Table - Enhanced Design */}
      <div className="glass-panel">
        <div className="panel-header" style={{ padding: '16px 20px' }}>
          <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <IconStationMap size={18} color="var(--emerald-400)" />
            <span>Recommended Charging Hubs Specification ({stations.length} Placements)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Ranked by Deficit Severity & Vehicle Throughput
            </span>
            <button
              onClick={handleExportCSV}
              disabled={!stations.length}
              style={{
                background: 'rgba(16, 185, 129, 0.12)',
                border: '1px solid var(--emerald-500)',
                color: 'var(--emerald-400)',
                padding: '6px 14px',
                borderRadius: '6px',
                fontSize: '11px',
                fontWeight: 600,
                cursor: stations.length ? 'pointer' : 'not-allowed',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                transition: 'all 0.2s ease',
              }}
            >
              <IconDownload size={13} />
              <span>Export CSV</span>
            </button>
          </div>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Hub Identifier</th>
                <th>Location & Zone</th>
                <th>GPS Coordinates</th>
                <th>Priority</th>
                <th>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    Covered Deficit
                    <TermTooltip text="Historical low-battery vehicle stops successfully covered and relieved by this hub." pos="top" align="center" />
                  </span>
                </th>
                <th>Hardware Specification</th>
                <th>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                    CapEx Est.
                    <TermTooltip text="Estimated Capital Expenditure for AC/DC fast chargers, grid hookup, and civil work." pos="top" align="right" />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              {stations.map((s, idx) => {
                const eq = s.equipment || {};
                const isSelected = selectedStationId === s.station_id;
                return (
                  <tr
                    key={s.station_id}
                    onClick={() => handleStationRowClick(s)}
                    style={{
                      cursor: 'pointer',
                      background: isSelected ? 'rgba(16, 185, 129, 0.08)' : undefined,
                    }}
                    title="Click to focus on this hub in the map"
                  >
                    <td style={{ fontWeight: 800, color: 'var(--emerald-400)' }}>#{idx + 1}</td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {s.station_id}
                    </td>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{s.name}</div>
                      {s.address && (
                        <div style={{ fontSize: '11px', color: 'var(--cyan-400)', marginTop: '2px' }}>
                          📍 {s.address}
                        </div>
                      )}
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        Zone: {s.zone} &bull; Type: {s.site_type || 'Commercial Hub'}
                      </div>
                    </td>
                    <td style={{ fontFamily: 'var(--font-mono)', fontSize: '11px' }}>
                      {s.latitude}, {s.longitude}
                    </td>
                    <td>
                      <span
                        className={`badge ${
                          s.priority_score >= 5
                            ? 'badge-critical'
                            : s.priority_score >= 4
                            ? 'badge-high'
                            : 'badge-medium'
                        }`}
                      >
                        {s.priority_label}
                      </span>
                    </td>
                    <td>
                      <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{s.covered_deficit_kwh} kWh</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {s.covered_trips_count} trips ({s.critical_shortages_covered} critical)
                      </div>
                    </td>
                    <td>
                      <div style={{ fontSize: '12px', color: 'var(--emerald-400)', fontWeight: 600 }}>
                        {eq.ac_slow_ports}x AC (3.3kW) • {eq.dc_fast_ports}x DC Fast (15kW){' '}
                        {eq.battery_swap_bays > 0 ? `• ${eq.battery_swap_bays}x Swap Bay` : ''}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        Capacity: {eq.total_simultaneous_capacity_kw} kW
                      </div>
                    </td>
                    <td style={{ fontWeight: 600, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                      ₹{eq.estimated_capex_inr ? Number(eq.estimated_capex_inr).toLocaleString() : 'N/A'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
