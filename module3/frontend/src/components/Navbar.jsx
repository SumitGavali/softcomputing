import React from 'react';
import {
  IconBrandLogo,
  IconStationMap,
  IconFleetHealth,
  IconDemandForecast,
  IconTripSimulator,
  IconSun,
  IconMoon,
} from './Icons.jsx';

export default function Navbar({ activeTab, setActiveTab, theme, setTheme }) {
  const tabs = [
    { id: 'stations', label: 'Station Placement & Map', IconComponent: IconStationMap },
    { id: 'fleet', label: 'Fleet Health & At-Risk', IconComponent: IconFleetHealth },
    { id: 'demand', label: '24h Grid & Power Load', IconComponent: IconDemandForecast },
    { id: 'simulator', label: 'Pre-Trip Simulator', IconComponent: IconTripSimulator },
  ];

  const toggleTheme = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(nextTheme);
  };

  return (
    <header className="top-header">
      <div className="brand-badge">
        <div className="brand-logo-glow">
          <IconBrandLogo size={28} />
        </div>
        <div>
          <div className="brand-title">
            RANGE INTELLIGENCE
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            Small EV Fleet Battery & Charging Network Optimization
          </div>
        </div>
      </div>

      <nav className="nav-tabs">
        {tabs.map((tab) => {
          const Icon = tab.IconComponent;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              className={`tab-btn ${isActive ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={16} color={isActive ? 'var(--emerald-400)' : 'var(--text-secondary)'} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Sleek Integrated Theme Switcher in Very Right Corner */}
      <div style={{ display: 'flex', alignItems: 'center' }}>
        <button
          type="button"
          onClick={toggleTheme}
          className={`theme-toggle-switch ${theme === 'light' ? 'is-light' : 'is-dark'}`}
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          aria-label="Toggle Theme"
        >
          <span className="track-icon track-icon-moon">
            <IconMoon size={13} color={theme === 'dark' ? 'rgba(34, 211, 238, 0.25)' : '#0284C7'} />
          </span>
          <span className="track-icon track-icon-sun">
            <IconSun size={13} color={theme === 'dark' ? '#F59E0B' : 'rgba(245, 158, 11, 0.25)'} />
          </span>
          <span className="theme-toggle-knob">
            {theme === 'dark' ? (
              <IconMoon size={12} color="#22D3EE" />
            ) : (
              <IconSun size={12} color="#F59E0B" />
            )}
          </span>
        </button>
      </div>
    </header>
  );
}
