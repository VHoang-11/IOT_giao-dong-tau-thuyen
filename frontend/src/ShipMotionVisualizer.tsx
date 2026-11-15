import { useEffect, useState } from 'react';
import type { AlarmLevel, RFClass, Scenario } from './domain';

interface ShipMotionVisualizerProps {
  rollDeg: number | null;
  pitchDeg: number | null;
  mai: number | null;
  alarmLevel: AlarmLevel;
  scenario: Scenario;
  classRf?: RFClass;
  sourceMode?: 'SIMULATION' | 'SENSOR';
  sensorOk?: boolean;
  compact?: boolean;
}

export function ShipMotionVisualizer({
  rollDeg,
  pitchDeg,
  mai = 0,
  alarmLevel = 'NORMAL',
  scenario = 'S0',
  classRf = 'NORMAL',
  sourceMode = 'SIMULATION',
  sensorOk = true,
  compact = false,
}: ShipMotionVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'front' | 'side'>('front');

  // Accessibility: detect and honor OS/browser prefers-reduced-motion
  const [prefersReducedMotion, setPrefersReducedMotion] = useState<boolean>(() => {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    return false;
  });

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return;
    const mediaQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    const updateMotion = (e: MediaQueryListEvent) => setPrefersReducedMotion(e.matches);
    if (mediaQuery.addEventListener) {
      mediaQuery.addEventListener('change', updateMotion);
      return () => mediaQuery.removeEventListener('change', updateMotion);
    } else if (mediaQuery.addListener) {
      mediaQuery.addListener(updateMotion);
      return () => mediaQuery.removeListener(updateMotion);
    }
  }, []);

  const isOffline = scenario === 'OFFLINE';
  const isSensorFault = scenario === 'SENSOR_FAULT' || sensorOk === false;
  const isAvailable = !isOffline && !isSensorFault && rollDeg !== null && pitchDeg !== null;

  // Real telemetry angles; clamped to 0 when OFFLINE or SENSOR_FAULT to prevent fake motion
  const validRoll = isAvailable ? rollDeg : 0;
  const validPitch = isAvailable ? pitchDeg : 0;
  const validMai = isAvailable ? (mai ?? 0) : 0;

  // Clamped rotation for smooth SVG render (-35° to +35° for Roll, -15° to +15° for Pitch)
  const clampedRoll = Math.max(-35, Math.min(35, validRoll));
  const clampedPitch = Math.max(-15, Math.min(15, validPitch));

  const motionTransition = prefersReducedMotion
    ? 'none'
    : 'transform 0.35s cubic-bezier(0.2, 0.9, 0.3, 1)';

  // Severity colors matching Maritime White & Navy
  const severityColor =
    !isAvailable
      ? '#475569'
      : alarmLevel === 'CRITICAL'
      ? '#B91C1C'
      : alarmLevel === 'WARNING'
      ? '#92400E'
      : alarmLevel === 'CAUTION'
      ? '#026AA0'
      : '#047857';

  const severityBg =
    !isAvailable
      ? 'var(--panel-alt)'
      : alarmLevel === 'CRITICAL'
      ? 'var(--note-danger-bg)'
      : alarmLevel === 'WARNING'
      ? 'var(--note-warn-bg)'
      : alarmLevel === 'CAUTION'
      ? 'var(--note-info-bg)'
      : 'var(--note-success-bg)';

  const portStbd =
    validRoll < -0.1 ? 'PORT (TRÁI)' : validRoll > 0.1 ? 'STBD (PHẢI)' : 'EVEN KEEL (CÂN BẰNG)';
  const bowStern =
    validPitch > 0.1 ? 'BOW UP (NGÓC MŨI)' : validPitch < -0.1 ? 'BOW DOWN (CHÚI MŨI)' : 'LEVEL KEEL (MỨC)';

  const maiPct = Math.min(100, Math.max(0, validMai));
  const maiColor = maiPct >= 70 ? 'var(--status-red-text)' : maiPct >= 35 ? 'var(--status-amber-text)' : 'var(--status-green-text)';

  const height = compact ? 190 : 255;

  return (
    <div
      className={`vessel-visualizer ${compact ? 'compact' : ''}`}
      style={{
        border: '1.5px solid var(--border-color, #183E65)',
        borderRadius: 8,
        background: 'var(--panel-bg, #FFFFFF)',
        boxShadow: 'var(--card-shadow, 0 2px 8px rgba(16,43,73,0.06))',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Top Header Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '8px 14px',
          borderBottom: '1px solid var(--border-subtle, #D0DDEB)',
          background: 'var(--panel-alt, #F0F4F8)',
          gap: 8,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span
            style={{
              fontFamily: "'IBM Plex Mono', monospace",
              fontSize: '0.72rem',
              fontWeight: 800,
              letterSpacing: '0.06em',
              color: 'var(--text-main, #102B49)',
            }}
          >
            2D VESSEL DYNAMICS
          </span>
          <span
            style={{
              padding: '2px 7px',
              borderRadius: 4,
              fontSize: '0.62rem',
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 800,
              background: '#153D64',
              color: '#FFFFFF',
              letterSpacing: '0.04em',
            }}
          >
            {sourceMode === 'SIMULATION' ? 'DEMO / SIMULATION' : 'LIVE / SENSOR'}
          </span>
        </div>

        {/* View Toggle Tabs */}
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            type="button"
            onClick={() => setActiveTab('front')}
            style={{
              padding: '4px 10px',
              fontSize: '0.68rem',
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 700,
              borderRadius: 4,
              border: '1.5px solid var(--border-color, #183E65)',
              background: activeTab === 'front' ? 'var(--primary-btn-bg, #153D64)' : '#FFFFFF',
              color: activeTab === 'front' ? '#FFFFFF' : 'var(--text-main, #102B49)',
              cursor: 'pointer',
              transition: 'all 0.12s ease',
            }}
          >
            MẶT CẮT NGANG (ROLL)
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('side')}
            style={{
              padding: '4px 10px',
              fontSize: '0.68rem',
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 700,
              borderRadius: 4,
              border: '1.5px solid var(--border-color, #183E65)',
              background: activeTab === 'side' ? 'var(--primary-btn-bg, #153D64)' : '#FFFFFF',
              color: activeTab === 'side' ? '#FFFFFF' : 'var(--text-main, #102B49)',
              cursor: 'pointer',
              transition: 'all 0.12s ease',
            }}
          >
            HÌNH CHIẾU MẠN (PITCH)
          </button>
        </div>
      </div>

      {/* Main SVG Visualization Canvas */}
      <div
        style={{
          position: 'relative',
          width: '100%',
          height,
          background: 'linear-gradient(180deg, #F8FAFC 0%, #EBF3FB 65%, #E2EDF8 100%)',
        }}
      >
        <svg
          viewBox="0 0 320 195"
          preserveAspectRatio="xMidYMid meet"
          width="100%"
          height={height}
          style={{ display: 'block' }}
        >
          <defs>
            {/* Water gradient */}
            <linearGradient id="waterGradLight" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#0284C7" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#0369A1" stopOpacity="0.5" />
            </linearGradient>
            {/* Sky horizon */}
            <linearGradient id="skyGradLight" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0.9" />
              <stop offset="100%" stopColor="#EBF4FD" stopOpacity="0.4" />
            </linearGradient>
          </defs>

          {/* Background Sky & Water Planes */}
          <rect x="0" y="0" width="320" height="128" fill="url(#skyGradLight)" />
          <rect x="0" y="128" width="320" height="67" fill="url(#waterGradLight)" />

          {/* Horizon & Waterline Datum */}
          <line x1="0" y1="128" x2="320" y2="128" stroke="#0284C7" strokeWidth="1.5" strokeDasharray="5 3" />
          <text x="8" y="124" fill="#0369A1" fontSize="7.5" fontWeight="700" fontFamily="'IBM Plex Mono', monospace">
            MỰC NƯỚC CHUẨN (WATERLINE DATUM)
          </text>

          {/* VIEW 1: FRONT CROSS-SECTION (ROLL AXIS) */}
          {activeTab === 'front' && (
            <g id="front-roll-view">
              {/* Roll Scale Arc & Graduation */}
              <path
                d="M 60 75 A 110 110 0 0 1 260 75"
                fill="none"
                stroke="#183E65"
                strokeDasharray="2 3"
                strokeWidth="1.2"
                opacity="0.5"
              />
              {/* Safety colored zones on arc */}
              <path d="M 135 22 A 110 110 0 0 1 185 22" fill="none" stroke="#10B981" strokeWidth="4" />
              <path d="M 112 28 A 110 110 0 0 1 135 22" fill="none" stroke="#D97706" strokeWidth="4" />
              <path d="M 185 22 A 110 110 0 0 1 208 28" fill="none" stroke="#D97706" strokeWidth="4" />
              <path d="M 85 43 A 110 110 0 0 1 112 28" fill="none" stroke="#DC2626" strokeWidth="4" />
              <path d="M 208 28 A 110 110 0 0 1 235 43" fill="none" stroke="#DC2626" strokeWidth="4" />

              {/* Ticks and degree labels */}
              <line x1="160" y1="12" x2="160" y2="24" stroke="#102B49" strokeWidth="2" />
              <text x="160" y="8" fill="#102B49" fontSize="8.5" fontWeight="800" textAnchor="middle" fontFamily="'IBM Plex Mono', monospace">0°</text>

              <line x1="135" y1="22" x2="138" y2="30" stroke="#10B981" strokeWidth="1.5" />
              <text x="128" y="16" fill="#065F46" fontSize="7.5" fontWeight="700" textAnchor="middle" fontFamily="'IBM Plex Mono', monospace">-10°</text>

              <line x1="185" y1="22" x2="182" y2="30" stroke="#10B981" strokeWidth="1.5" />
              <text x="192" y="16" fill="#065F46" fontSize="7.5" fontWeight="700" textAnchor="middle" fontFamily="'IBM Plex Mono', monospace">+10°</text>

              <line x1="112" y1="28" x2="116" y2="35" stroke="#D97706" strokeWidth="1.5" />
              <text x="103" y="24" fill="#92400E" fontSize="7.5" fontWeight="700" textAnchor="middle" fontFamily="'IBM Plex Mono', monospace">-20°</text>

              <line x1="208" y1="28" x2="204" y2="35" stroke="#D97706" strokeWidth="1.5" />
              <text x="217" y="24" fill="#92400E" fontSize="7.5" fontWeight="700" textAnchor="middle" fontFamily="'IBM Plex Mono', monospace">+20°</text>

              {/* Rotating Hull Group (Roll Axis - Driven directly by telemetry.roll_deg) */}
              <g
                id="rotating-roll-hull"
                className="vessel-rotating-element vessel-roll-hull"
                transform={`rotate(${clampedRoll}, 160, 128)`}
                style={{
                  transition: motionTransition,
                  willChange: 'transform',
                }}
                opacity={isAvailable ? 1 : 0.25}
              >
                {/* Keel Mast Line */}
                <line x1="160" y1="35" x2="160" y2="162" stroke="#183E65" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />

                {/* Cargo Vessel Cross Section (Front View) */}
                {/* Hull Main Shell */}
                <path
                  d="M 100 98 L 220 98 L 210 146 C 205 160 178 164 160 164 C 142 164 115 160 110 146 Z"
                  fill="#102B49"
                  stroke="#183E65"
                  strokeWidth="2"
                />
                {/* Deck line */}
                <line x1="100" y1="98" x2="220" y2="98" stroke="#183E65" strokeWidth="1.5" />
                {/* Double bottom / internal tank divider */}
                <path d="M 115 146 L 205 146" stroke="#55728D" strokeWidth="1" strokeDasharray="2 2" />

                {/* Bridge Tower / Navigation Deck House (White cabin on navy hull) */}
                <rect x="135" y="70" width="50" height="28" fill="#FFFFFF" stroke="#183E65" strokeWidth="1.5" rx="2" />
                {/* Bridge Windows */}
                <rect x="140" y="75" width="40" height="7" fill="#0284C7" rx="1" />
                {/* Radar Mast & Antenna */}
                <line x1="160" y1="70" x2="160" y2="50" stroke="#183E65" strokeWidth="2" />
                <line x1="152" y1="56" x2="168" y2="56" stroke="#183E65" strokeWidth="1.5" />
                <circle cx="160" cy="48" r="3" fill="#0284C7" stroke="#183E65" strokeWidth="1" />

                {/* Container Stacks on Deck */}
                {/* Tier 1 Containers */}
                <rect x="108" y="83" width="23" height="15" fill="#DC2626" stroke="#102B49" strokeWidth="1" rx="1" />
                <rect x="189" y="83" width="23" height="15" fill="#1D4ED8" stroke="#102B49" strokeWidth="1" rx="1" />
                {/* Tier 2 Containers */}
                <rect x="110" y="68" width="21" height="15" fill="#16A34A" stroke="#102B49" strokeWidth="1" rx="1" />
                <rect x="191" y="68" width="21" height="15" fill="#D97706" stroke="#102B49" strokeWidth="1" rx="1" />

                {/* Metacenter M & Center of Gravity G markers */}
                <circle cx="160" cy="90" r="3" fill="#0284C7" stroke="#FFFFFF" strokeWidth="1" />
                <text x="166" y="93" fill="#0284C7" fontSize="7.5" fontWeight="bold">M</text>
                <circle cx="160" cy="118" r="3" fill="#D97706" stroke="#FFFFFF" strokeWidth="1" />
                <text x="166" y="121" fill="#D97706" fontSize="7.5" fontWeight="bold">G</text>
              </g>

              {/* Static Reference Center Pointer */}
              <polygon points="160,26 155,20 165,20" fill={severityColor} stroke="#183E65" strokeWidth="0.8" />
            </g>
          )}

          {/* VIEW 2: SIDE PROFILE (PITCH AXIS) */}
          {activeTab === 'side' && (
            <g id="side-pitch-view">
              {/* Pitch Angle Datum Line */}
              <line x1="20" y1="128" x2="300" y2="128" stroke="#183E65" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
              <text x="275" y="122" fill="#55728D" fontSize="7.5" fontWeight="700" fontFamily="'IBM Plex Mono', monospace">0° PITCH</text>

              {/* Pitch Rotating Group (Pitch Axis - Driven directly by telemetry.pitch_deg) */}
              <g
                id="rotating-pitch-hull"
                className="vessel-rotating-element vessel-pitch-hull"
                transform={`rotate(${clampedPitch}, 160, 128)`}
                style={{
                  transition: motionTransition,
                  willChange: 'transform',
                }}
                opacity={isAvailable ? 1 : 0.25}
              >
                {/* Cargo Vessel Profile Silhouette */}
                {/* Main Hull Body: Stern (Left), Bow (Right) */}
                <path
                  d="M 50 113 
                     L 245 113 
                     C 260 116 275 123 285 128 
                     C 275 140 265 146 245 146 
                     L 65 146 
                     L 50 133 
                     Z"
                  fill="#102B49"
                  stroke="#183E65"
                  strokeWidth="2"
                />

                {/* Bulbous Bow highlight */}
                <circle cx="282" cy="130" r="4.5" fill="#0284C7" stroke="#183E65" strokeWidth="1" />

                {/* Cargo Container Bays along Main Deck */}
                <rect x="135" y="90" width="30" height="23" fill="#DC2626" stroke="#102B49" strokeWidth="1" rx="1" />
                <rect x="135" y="68" width="30" height="22" fill="#1D4ED8" stroke="#102B49" strokeWidth="1" rx="1" />
                <rect x="170" y="90" width="30" height="23" fill="#16A34A" stroke="#102B49" strokeWidth="1" rx="1" />
                <rect x="170" y="68" width="30" height="22" fill="#D97706" stroke="#102B49" strokeWidth="1" rx="1" />
                <rect x="205" y="94" width="28" height="19" fill="#0284C7" stroke="#102B49" strokeWidth="1" rx="1" />

                {/* Aft Superstructure & Bridge Tower (White cabin) */}
                <rect x="68" y="70" width="38" height="43" fill="#FFFFFF" stroke="#183E65" strokeWidth="1.5" rx="2" />
                <rect x="74" y="75" width="26" height="6" fill="#0284C7" rx="1" />
                {/* Funnel (Exhaust Pipe) */}
                <path d="M 80 70 L 84 56 L 92 56 L 92 70 Z" fill="#DC2626" stroke="#183E65" strokeWidth="1" />
                <rect x="83" y="56" width="9" height="3" fill="#102B49" />

                {/* Bow Mast */}
                <line x1="255" y1="113" x2="255" y2="90" stroke="#183E65" strokeWidth="2" />
                <circle cx="255" cy="88" r="2.5" fill="#0284C7" />

                {/* Propeller & Rudder indication at Stern */}
                <path d="M 46 140 L 52 146 L 48 150 Z" fill="#55728D" />
              </g>

              {/* Water displacement ripples */}
              <ellipse cx="275" cy="136" rx="14" ry="3" fill="none" stroke="#0284C7" strokeWidth="1.2" opacity="0.6" />
              <ellipse cx="55" cy="140" rx="12" ry="2.5" fill="none" stroke="#0284C7" strokeWidth="1.2" opacity="0.5" />
            </g>
          )}

          {/* OVERLAY FOR SENSOR FAULT OR OFFLINE */}
          {!isAvailable && (
            <g id="fault-overlay">
              <rect x="30" y="55" width="260" height="70" rx="8" fill="#FFFFFF" stroke={severityColor} strokeWidth="2" />
              <text x="160" y="85" fill={severityColor} fontSize="12" fontWeight="800" textAnchor="middle" fontFamily="'IBM Plex Mono', monospace">
                {isOffline ? 'OFFLINE • MẤT KẾT NỐI' : 'SENSOR FAULT • LỖI CẢM BIẾN I2C'}
              </text>
              <text x="160" y="105" fill="#55728D" fontSize="8.5" fontWeight="600" textAnchor="middle" fontFamily="'IBM Plex Mono', monospace">
                {isOffline ? 'Thiết bị ngắt kết nối. Không hiển thị góc giả tạo.' : 'Dữ liệu MPU6050 không khả dụng. Kiểm tra kết nối cảm biến.'}
              </text>
            </g>
          )}
        </svg>

        {/* Floating Telemetry HUD Badges */}
        <div
          style={{
            position: 'absolute',
            bottom: 8,
            left: 10,
            right: 10,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            pointerEvents: 'none',
          }}
        >
          {/* Left indicator: Roll & Pitch numbers */}
          <div
            style={{
              background: 'rgba(255, 255, 255, 0.95)',
              padding: '5px 10px',
              borderRadius: 6,
              border: '1px solid var(--border-color)',
              boxShadow: 'var(--card-shadow)',
            }}
          >
            <div style={{ display: 'flex', gap: 12 }}>
              <span style={{ fontSize: '0.72rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700, color: 'var(--text-main, #102B49)' }}>
                ROLL:{' '}
                <strong style={{ color: Math.abs(validRoll) >= 18 ? 'var(--status-red-text)' : Math.abs(validRoll) >= 10 ? 'var(--status-amber-text)' : 'var(--status-cyan-text)' }}>
                  {isAvailable ? `${validRoll > 0 ? '+' : ''}${validRoll.toFixed(1)}°` : '—'}
                </strong>
                <small style={{ color: 'var(--text-muted, #55728D)', marginLeft: 4 }}>
                  {isAvailable ? (validRoll < -0.1 ? 'PORT' : validRoll > 0.1 ? 'STBD' : 'EVEN') : ''}
                </small>
              </span>
              <span style={{ fontSize: '0.72rem', fontFamily: "'IBM Plex Mono', monospace", fontWeight: 700, color: 'var(--text-main, #102B49)' }}>
                PITCH:{' '}
                <strong style={{ color: Math.abs(validPitch) >= 8 ? 'var(--status-amber-text)' : 'var(--status-cyan-text)' }}>
                  {isAvailable ? `${validPitch > 0 ? '+' : ''}${validPitch.toFixed(1)}°` : '—'}
                </strong>
                <small style={{ color: 'var(--text-muted, #55728D)', marginLeft: 4 }}>
                  {isAvailable ? (validPitch > 0.1 ? 'UP' : validPitch < -0.1 ? 'DOWN' : 'LVL') : ''}
                </small>
              </span>
            </div>
          </div>

          {/* Right indicator: Alarm Severity Pill */}
          <div
            style={{
              background: severityBg,
              color: severityColor,
              border: `1.5px solid ${severityColor}`,
              padding: '4px 10px',
              borderRadius: 5,
              fontSize: '0.7rem',
              fontFamily: "'IBM Plex Mono', monospace",
              fontWeight: 800,
              letterSpacing: '0.04em',
              boxShadow: '0 2px 6px rgba(16,43,73,0.08)',
            }}
          >
            {isAvailable ? alarmLevel : isOffline ? 'OFFLINE' : 'FAULT'}
          </div>
        </div>
      </div>

      {/* Footer Info Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: compact ? '1fr 1fr' : '1.2fr 1fr 1.2fr',
          padding: '8px 14px',
          background: 'var(--panel-alt, #F0F4F8)',
          borderTop: '1px solid var(--border-subtle, #D0DDEB)',
          gap: 12,
          alignItems: 'center',
          fontSize: '0.7rem',
          fontFamily: "'IBM Plex Mono', monospace",
        }}
      >
        {/* MAI Metric bar */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
            <span style={{ color: 'var(--text-muted, #55728D)', fontWeight: 600 }}>CHỈ SỐ BẤT THƯỜNG (MAI):</span>
            <strong style={{ color: maiColor, fontWeight: 800 }}>{isAvailable ? `${maiPct} / 100` : '—'}</strong>
          </div>
          <div style={{ width: '100%', height: 6, background: 'var(--border-color)', borderRadius: 3, overflow: 'hidden' }}>
            <div
              style={{
                width: `${maiPct}%`,
                height: '100%',
                background: maiColor,
                transition: 'width 0.3s ease-out',
              }}
            />
          </div>
        </div>

        {/* State Classification / RF */}
        <div>
          <span style={{ color: 'var(--text-muted, #55728D)', display: 'block', fontWeight: 600 }}>TRẠNG THÁI PHÂN LOẠI:</span>
          <strong style={{ color: severityColor, fontWeight: 800 }}>
            {isAvailable ? classRf : 'UNKNOWN'}
          </strong>
        </div>

        {/* Scenario and Kinematic Direction */}
        {!compact && (
          <div style={{ textAlign: 'right' }}>
            <span style={{ color: 'var(--text-muted, #55728D)', display: 'block', fontWeight: 600 }}>KỊCH BẢN / ĐỘNG HỌC:</span>
            <span style={{ color: 'var(--text-main, #102B49)', fontWeight: 700 }}>
              {scenario} • {activeTab === 'front' ? portStbd : bowStern}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
