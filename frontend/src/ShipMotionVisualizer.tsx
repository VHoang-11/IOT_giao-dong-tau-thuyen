import { useEffect, useState, useRef } from 'react';
import type { AlarmLevel, RFClass, Scenario } from './domain';
import { getRFClassNameVi, getAlarmLevelNameVi } from './i18n/vi';

export interface ShipMotionVisualizerProps {
  rollDeg: number | null | undefined;
  pitchDeg: number | null | undefined;
  mai: number | null | undefined;
  alarmLevel?: AlarmLevel;
  scenario?: Scenario;
  classRf?: RFClass;
  sourceMode?: 'SIMULATION' | 'SENSOR';
  sensorOk?: boolean;
  compact?: boolean;
  variant?: 'standalone' | 'split';
  warningDeg?: number;
  tripDeg?: number;
  hoveredSample?: { roll: number; pitch: number; t: number; mai?: number; class_rf?: string } | null;
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
  variant = 'standalone',
  warningDeg = 15.0,
  tripDeg = 22.0,
  hoveredSample = null,
}: ShipMotionVisualizerProps) {
  const [activeTab, setActiveTab] = useState<'iso' | 'front' | 'side'>('iso');
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(540);

  useEffect(() => {
    if (!containerRef.current) return;
    const update = () => {
      if (containerRef.current) {
        const cw = containerRef.current.clientWidth;
        if (cw > 0) setContainerWidth(cw);
      }
    };
    update();
    const ro = new ResizeObserver(entries => {
      for (const entry of entries) {
        if (entry.contentRect.width > 0) {
          setContainerWidth(Math.round(entry.contentRect.width));
        }
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  const w = Math.max(460, containerWidth);
  const cx = Math.round(w / 2);

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
  const isAvailable = !isOffline && !isSensorFault && rollDeg !== null && pitchDeg !== null && rollDeg !== undefined && pitchDeg !== undefined;

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
      ? '#64748B'
      : alarmLevel === 'CRITICAL'
      ? '#EF4444'
      : alarmLevel === 'WARNING'
      ? '#F59E0B'
      : alarmLevel === 'CAUTION'
      ? '#0284C7'
      : '#10B981';

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
    validRoll < -0.1 ? 'Mạn trái' : validRoll > 0.1 ? 'Mạn phải' : 'Cân bằng';
  const bowStern =
    validPitch > 0.1 ? 'Ngóc mũi' : validPitch < -0.1 ? 'Chúi mũi' : 'Mức chuẩn';

  const maiPct = Math.min(100, Math.max(0, validMai));
  const maiColor =
    maiPct >= 70
      ? 'var(--status-red-text)'
      : maiPct >= 35
      ? 'var(--status-amber-text)'
      : 'var(--status-green-text)';

  const height = compact ? 220 : 310;

  // Needle angle: points to Roll list in 3D/Front view, or Pitch trim in Side view
  const needleAngle = activeTab === 'side' ? clampedPitch : clampedRoll;

  return (
    <div
      ref={containerRef}
      className={`vessel-visualizer ${compact ? 'compact' : ''}`}
      style={{
        border: '1px solid var(--border-color)',
        borderRadius: 12,
        background: 'var(--panel-bg)',
        boxShadow: 'var(--card-shadow)',
        overflow: 'hidden',
        position: 'relative',
      }}
    >
      {/* Top Header Bar */}
      <div className="digital-twin-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span
            style={{
              fontFamily: "'Be Vietnam Pro', sans-serif",
              fontSize: '0.82rem',
              fontWeight: 600,
              color: 'var(--text-main)',
            }}
          >
            Mô hình số hóa • Tàu container MV SVMG-01
          </span>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: '0.65rem',
              fontFamily: "'Be Vietnam Pro', sans-serif",
              fontWeight: 500,
              background: '#153D64',
              color: '#FFFFFF',
            }}
          >
            {sourceMode === 'SIMULATION' ? 'Đang mô phỏng' : 'Cảm biến trực tiếp'}
          </span>
          <span
            style={{
              padding: '2px 8px',
              borderRadius: 4,
              fontSize: '0.65rem',
              fontFamily: "'Be Vietnam Pro', sans-serif",
              fontWeight: 700,
              background: severityBg,
              color: severityColor,
              border: `1px solid ${severityColor}`,
            }}
          >
            {isAvailable ? getAlarmLevelNameVi(alarmLevel) : isOffline ? 'Mất kết nối' : 'Lỗi cảm biến'}
          </span>
          {isAvailable && classRf && (
            <span
              style={{
                padding: '2px 7px',
                borderRadius: 4,
                fontSize: '0.65rem',
                fontFamily: "'Be Vietnam Pro', sans-serif",
                fontWeight: 600,
                background: 'var(--panel-alt)',
                color: 'var(--text-muted)',
                border: '1px solid var(--border-subtle)',
              }}
            >
              {getRFClassNameVi(classRf)}
            </span>
          )}
        </div>

        {/* View Toggle Tabs */}
        <div style={{ display: 'flex', gap: 4 }}>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'iso' ? 'active' : ''}`}
            onClick={() => setActiveTab('iso')}
            style={{ fontSize: '0.7rem', padding: '3px 8px', borderRadius: 4 }}
          >
            Góc phối cảnh (Isometric)
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'front' ? 'active' : ''}`}
            onClick={() => setActiveTab('front')}
            style={{ fontSize: '0.7rem', padding: '3px 8px', borderRadius: 4 }}
          >
            Mặt cắt ngang (Roll)
          </button>
          <button
            type="button"
            className={`tab-btn ${activeTab === 'side' ? 'active' : ''}`}
            onClick={() => setActiveTab('side')}
            style={{ fontSize: '0.7rem', padding: '3px 8px', borderRadius: 4 }}
          >
            Mặt cắt dọc (Pitch)
          </button>
        </div>
      </div>

      {/* Main SVG Visualization Canvas (Clean Body: No floating overlays) */}
      <div className="digital-twin-canvas-wrap" style={{ height }}>
        <svg
          viewBox={`0 0 ${w} ${height}`}
          width="100%"
          height={height}
          style={{ display: 'block' }}
          aria-label="Mô hình số hóa thân tàu bán 3D Isometric cùng môi trường biển"
        >
          <defs>
            {/* Tech Glow Filters */}
            <filter id="vesselCyanGlow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
            <filter id="vesselSoftShadow" x="-15%" y="-15%" width="130%" height="130%">
              <feDropShadow dx="0" dy="7" stdDeviation="9" floodOpacity="0.22" />
            </filter>
            <filter id="waterBlur" x="-10%" y="-10%" width="120%" height="120%">
              <feGaussianBlur stdDeviation="2.5" />
            </filter>

            {/* Atmosphere Sky Gradient */}
            <linearGradient id="oceanSkyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="var(--ocean-sky-top)" />
              <stop offset="100%" stopColor="var(--ocean-sky-bottom)" />
            </linearGradient>

            {/* Deep Ocean Surface Gradient (Multi-layer Ocean Base) */}
            <linearGradient id="oceanSeaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="var(--ocean-sea-top)" stopOpacity="0.8" />
              <stop offset="26%" stopColor="var(--ocean-sea-mid)" stopOpacity="0.88" />
              <stop offset="70%" stopColor="var(--ocean-sea-deep)" stopOpacity="0.95" />
              <stop offset="100%" stopColor="#021B35" stopOpacity="0.98" />
            </linearGradient>

            {/* Stern Wake Gradient (Trailing dispersion behind vessel) */}
            <linearGradient id="sternWakeGrad" x1="100%" y1="0%" x2="0%" y2="50%">
              <stop offset="0%" stopColor="var(--ocean-wave-light)" stopOpacity="0.85" />
              <stop offset="50%" stopColor="var(--ocean-wave-subtle)" stopOpacity="0.45" />
              <stop offset="100%" stopColor="var(--ocean-wave-subtle)" stopOpacity="0.0" />
            </linearGradient>

            {/* Propeller / Screw Churn Wash Radial Gradient */}
            <radialGradient id="propWashGrad" cx="65%" cy="50%" r="50%">
              <stop offset="0%" stopColor="var(--ocean-wave-light)" stopOpacity="0.65" />
              <stop offset="50%" stopColor="var(--ocean-wave-subtle)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="var(--ocean-wave-subtle)" stopOpacity="0.0" />
            </radialGradient>

            {/* Hull Water Reflection Fade Gradient */}
            <linearGradient id="reflectionFadeGrad" x1="0%" y1="0%" x2="0%" y2="100%">
              <stop offset="0%" stopColor="#0F172A" stopOpacity="0.45" />
              <stop offset="45%" stopColor="#0369A1" stopOpacity="0.2" />
              <stop offset="100%" stopColor="#0369A1" stopOpacity="0.0" />
            </linearGradient>

            {/* Hull Materials Gradients */}
            <linearGradient id="hullTopsidesGrad" x1="0%" y1="0%" x2="100%" y2="80%">
              <stop offset="0%" stopColor="#1E293B" />
              <stop offset="50%" stopColor="#0F172A" />
              <stop offset="100%" stopColor="#090D16" />
            </linearGradient>
            <linearGradient id="hullBootTopGrad" x1="0%" y1="0%" x2="100%" y2="50%">
              <stop offset="0%" stopColor="#DC2626" />
              <stop offset="60%" stopColor="#991B1B" />
              <stop offset="100%" stopColor="#7F1D1D" />
            </linearGradient>
            <linearGradient id="deckPlaneGrad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#475569" />
              <stop offset="100%" stopColor="#334155" />
            </linearGradient>
          </defs>

          {/* ================================================================= */}
          {/* LAYER 0: ATMOSPHERE SKY & FIXED HORIZON DATUM (FULL WIDTH)        */}
          {/* ================================================================= */}
          <rect x="0" y="0" width={w} height="146" fill="url(#oceanSkyGrad)" />

          {/* ================================================================= */}
          {/* LAYER 1: DEEP OCEAN SURFACE BODY (FULL WIDTH PERSPECTIVE PLANE)   */}
          {/* ================================================================= */}
          <polygon points={`0,146 ${w},146 ${w},${height} 0,${height}`} fill="url(#oceanSeaGrad)" />

          {/* Fixed Horizon Reference Line (Remains horizontal regardless of vessel roll/pitch) */}
          <line
            x1="0"
            y1="146"
            x2={w}
            y2="146"
            stroke="var(--ocean-horizon-line)"
            strokeWidth="1.2"
            strokeDasharray="6 3"
            opacity="0.75"
          />
          <text
            x="14"
            y="141"
            fill="var(--ocean-horizon-line)"
            fontSize="7.5"
            fontWeight="600"
            fontFamily="'Be Vietnam Pro', sans-serif"
          >
            Đường chân trời • Chuẩn thăng bằng biển (Horizon Datum)
          </text>

          {/* Ocean Depth Perspective Contours (Spanning full container width) */}
          <g opacity="0.45">
            <line x1="0" y1="160" x2={w} y2="160" stroke="var(--ocean-wave-subtle)" strokeWidth="0.8" strokeDasharray="4 6" />
            <line x1="0" y1="182" x2={w} y2="182" stroke="var(--ocean-wave-subtle)" strokeWidth="0.8" strokeDasharray="6 8" />
            <line x1="0" y1="214" x2={w} y2="214" stroke="var(--ocean-wave-subtle)" strokeWidth="1" strokeDasharray="8 10" />
            <line x1="0" y1="254" x2={w} y2="254" stroke="var(--ocean-wave-subtle)" strokeWidth="1.2" strokeDasharray="10 12" />
          </g>

          {/* ================================================================= */}
          {/* LAYER 2: DISTANT SLOW AMBIENT WAVES (BEHIND VESSEL - FIXED DATUM) */}
          {/* ================================================================= */}
          <g id="distant-ambient-waves">
            {/* Wave Layer 1 (Far background wave - slow 12s harmonic drift) */}
            <path
              className="wave-ambient-far"
              d={`M -40 154 Q 30 152 100 155 T 240 154 T 380 155 T 520 154 T 660 155 T 800 154 T ${w + 40} 155`}
              fill="none"
              stroke="var(--ocean-wave-subtle)"
              strokeWidth="0.9"
              opacity="0.45"
            />
            {/* Wave Layer 2 (Mid-back background wave - slow 9.5s harmonic drift) */}
            <path
              className="wave-ambient-mid-back"
              d={`M -30 166 Q 50 163 130 167 T 290 166 T 450 167 T 610 166 T 770 167 T ${w + 40} 166`}
              fill="none"
              stroke="var(--ocean-wave-subtle)"
              strokeWidth="1"
              opacity="0.55"
            />
          </g>

          {/* ================================================================= */}
          {/* INCLINOMETER OVERHEAD ARC (STATIC REFERENCE GAUGE AT TOP)         */}
          {/* ================================================================= */}
          <g id="inclinometer-arc" transform={`translate(${cx - 270}, 0)`}>
            {/* Arc Track (Radius 120 from pivot 270, 160) */}
            <path
              d="M 185 75 A 120 120 0 0 1 355 75"
              fill="none"
              stroke="var(--border-subtle)"
              strokeWidth="2.5"
            />

            {activeTab === 'side' ? (
              <>
                {/* Safe zone (-8° to +8°) */}
                <path d="M 226 50 A 120 120 0 0 1 314 50" fill="none" stroke="#10B981" strokeWidth="3" opacity="0.85" />
                {/* Warning sectors (±8° to ±12°) */}
                <path d="M 208 59 A 120 120 0 0 1 226 50" fill="none" stroke="#F59E0B" strokeWidth="3" />
                <path d="M 314 50 A 120 120 0 0 1 332 59" fill="none" stroke="#F59E0B" strokeWidth="3" />
                {/* Trip sectors (> ±12°) */}
                <path d="M 185 75 A 120 120 0 0 1 208 59" fill="none" stroke="#EF4444" strokeWidth="3" />
                <path d="M 332 59 A 120 120 0 0 1 355 75" fill="none" stroke="#EF4444" strokeWidth="3" />

                <line x1="270" y1="40" x2="270" y2="48" stroke="var(--text-main)" strokeWidth="1.8" />
                <text x="270" y="36" fill="var(--text-main)" fontSize="8.5" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">0°</text>

                <line x1="242" y1="44" x2="244" y2="52" stroke="var(--status-green-text)" strokeWidth="1.2" />
                <text x="236" y="40" fill="var(--text-muted)" fontSize="7" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">-5°</text>

                <line x1="298" y1="44" x2="296" y2="52" stroke="var(--status-green-text)" strokeWidth="1.2" />
                <text x="304" y="40" fill="var(--text-muted)" fontSize="7" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">+5°</text>

                <line x1="218" y1="55" x2="222" y2="62" stroke="#F59E0B" strokeWidth="1.4" />
                <text x="210" y="52" fill="#F59E0B" fontSize="7" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">-10°</text>

                <line x1="322" y1="55" x2="318" y2="62" stroke="#F59E0B" strokeWidth="1.4" />
                <text x="330" y="52" fill="#F59E0B" fontSize="7" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">+10°</text>
              </>
            ) : (
              <>
                {/* Safe zone (-15° to +15°) */}
                <path d="M 215 54 A 120 120 0 0 1 325 54" fill="none" stroke="#10B981" strokeWidth="3" opacity="0.85" />
                {/* Warning sectors (±15° to ±22°) */}
                <path d="M 198 64 A 120 120 0 0 1 215 54" fill="none" stroke="#F59E0B" strokeWidth="3" />
                <path d="M 325 54 A 120 120 0 0 1 342 64" fill="none" stroke="#F59E0B" strokeWidth="3" />
                {/* Trip sectors (> ±22°) */}
                <path d="M 185 75 A 120 120 0 0 1 198 64" fill="none" stroke="#EF4444" strokeWidth="3" />
                <path d="M 342 64 A 120 120 0 0 1 355 75" fill="none" stroke="#EF4444" strokeWidth="3" />

                {/* Degree ticks & technical labels */}
                <line x1="270" y1="40" x2="270" y2="48" stroke="var(--text-main)" strokeWidth="1.8" />
                <text x="270" y="36" fill="var(--text-main)" fontSize="8.5" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">
                  0°
                </text>

                <line x1="228" y1="48" x2="232" y2="55" stroke="var(--status-green-text)" strokeWidth="1.2" />
                <text x="220" y="44" fill="var(--text-muted)" fontSize="7.5" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">
                  -10°
                </text>

                <line x1="312" y1="48" x2="308" y2="55" stroke="var(--status-green-text)" strokeWidth="1.2" />
                <text x="320" y="44" fill="var(--text-muted)" fontSize="7.5" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">
                  +10°
                </text>

                <line x1="198" y1="64" x2="204" y2="70" stroke="#F59E0B" strokeWidth="1.4" />
                <text x="188" y="60" fill="#F59E0B" fontSize="7.5" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">
                  -{Math.round(warningDeg)}°
                </text>

                <line x1="342" y1="64" x2="336" y2="70" stroke="#F59E0B" strokeWidth="1.4" />
                <text x="352" y="60" fill="#F59E0B" fontSize="7.5" fontWeight="600" textAnchor="middle" fontFamily="'JetBrains Mono', monospace">
                  +{Math.round(warningDeg)}°
                </text>
              </>
            )}

            {/* Dynamic Electronic Needle */}
            <g transform={`rotate(${needleAngle}, 270, 160)`} style={{ transition: motionTransition }}>
              <line x1="270" y1="44" x2="270" y2="70" stroke={severityColor} strokeWidth="2" strokeLinecap="round" />
              <polygon points="270,41 267,47 273,47" fill={severityColor} />
            </g>
          </g>

          {/* ================================================================= */}
          {/* VIEW 1: SEMI-3D / ISOMETRIC DIGITAL TWIN VESSEL (DEFAULT VIEW)    */}
          {/* ================================================================= */}
          {activeTab === 'iso' && (
            <g id="iso-vessel-view" transform={`translate(${cx - 270}, 0)`}>
              {/* 1. VESSEL UNDERWATER REFLECTION (Mirrored on water surface) */}
              <g
                id="vessel-water-reflection"
                transform={`rotate(${-clampedRoll * 0.75}, 270, 185) translate(${(clampedPitch * 0.4).toFixed(1)}, ${(clampedPitch * 0.2).toFixed(1)})`}
                style={{ transition: motionTransition }}
                opacity="var(--ocean-reflection-opacity)"
                filter="url(#waterBlur)"
              >
                {/* Scaled-up reflection footprint */}
                <g transform="translate(270, 160) scale(1.28) translate(-270, -160)">
                  <path
                    d="M 125 158 L 380 188 C 415 192 432 186 438 180 C 430 206 390 226 350 220 L 135 186 Z"
                    fill="url(#reflectionFadeGrad)"
                  />
                  <ellipse cx="434" cy="188" rx="14" ry="7" fill="#0369A1" opacity="0.3" />
                </g>
              </g>

              {/* 2. STERN WAKE & DISPLACEMENT TRAIL (FIXED WATER PLANE, BEHIND SHIP) */}
              <g id="stern-wake-group" className="stern-wake-flow">
                {/* Propeller churning wash oval aft of rudder/stern */}
                <ellipse cx="80" cy="173" rx="24" ry="6.5" fill="url(#propWashGrad)" />

                {/* V-shaped trailing wake feather lines (Port & Starboard trails) */}
                <path
                  d="M 104 168 C 74 165 44 165 14 166"
                  fill="none"
                  stroke="url(#sternWakeGrad)"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                />
                <path
                  d="M 112 177 C 82 183 52 191 20 200"
                  fill="none"
                  stroke="url(#sternWakeGrad)"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                />
                <path
                  d="M 94 173 C 66 175 38 177 12 179"
                  fill="none"
                  stroke="var(--ocean-wave-light)"
                  strokeWidth="1.2"
                  strokeDasharray="6 4"
                  opacity="0.6"
                />
                {/* Secondary wake displacement arcs */}
                <path
                  d="M 42 168 Q 54 177 46 188"
                  fill="none"
                  stroke="var(--ocean-wave-subtle)"
                  strokeWidth="1"
                  strokeLinecap="round"
                  opacity="0.5"
                />
                <path
                  d="M 72 169 Q 84 177 76 186"
                  fill="none"
                  stroke="var(--ocean-wave-subtle)"
                  strokeWidth="1.1"
                  strokeLinecap="round"
                  opacity="0.55"
                />
              </g>

              {/* 3. DYNAMIC TELEMETRY VESSEL MODEL (Scaled up by 28% to fill view) */}
              <g
                id="vessel-digital-twin-model"
                transform={`rotate(${clampedRoll}, 270, 160) translate(${(clampedPitch * 0.9).toFixed(1)}, ${(clampedPitch * 0.5).toFixed(1)})`}
                style={{
                  transition: motionTransition,
                  willChange: 'transform',
                }}
                opacity={isAvailable ? 1 : 0.35}
                filter="url(#vesselSoftShadow)"
              >
                {/* 28% Proportional Scale Envelope */}
                <g transform="translate(270, 160) scale(1.28) translate(-270, -160)">
                  {/* A. Hull Bottom Oxide Red Anti-Fouling (Lower 3D Facet) */}
                  <path
                    d="M 125 158 
                       L 380 188 
                       C 415 192 432 186 438 180 
                       C 428 196 405 204 375 202 
                       L 135 174 
                       L 125 158 Z"
                    fill="url(#hullBootTopGrad)"
                    stroke="#7F1D1D"
                    strokeWidth="1"
                  />

                  {/* Bulbous Bow 3D Shell */}
                  <ellipse cx="434" cy="184" rx="8" ry="4.5" fill="#B91C1C" stroke="#7F1D1D" strokeWidth="1" />

                  {/* B. Hull Topsides Main Body (Starboard & Forward 3D Facet) */}
                  <path
                    d="M 120 142 
                       L 375 172 
                       C 408 176 430 178 440 174 
                       L 438 180 
                       C 415 192 380 188 125 158 
                       L 115 146 
                       Z"
                    fill="url(#hullTopsidesGrad)"
                    stroke="#0F172A"
                    strokeWidth="1.2"
                  />

                  {/* Dynamic Waterline Stripe Accent (Cyan / Tech Glow line) */}
                  <path
                    d="M 125 158 L 380 188 C 412 192 430 186 438 180"
                    fill="none"
                    stroke="#38BDF8"
                    strokeWidth="1.4"
                    opacity="0.85"
                  />

                  {/* C. Main Deck Plane (Isometric Quadrilateral) */}
                  <path
                    d="M 120 142 
                       L 155 128 
                       L 410 158 
                       C 428 163 438 170 440 174 
                       C 430 178 408 176 375 172 
                       Z"
                    fill="url(#deckPlaneGrad)"
                    stroke="#1E293B"
                    strokeWidth="1"
                  />

                  {/* Hatch Coamings & Cargo Guides on Deck */}
                  <line x1="162" y1="133" x2="368" y2="157" stroke="#64748B" strokeWidth="0.8" strokeDasharray="4 2" />

                  {/* D. ISOMETRIC 3D CONTAINER STACKS (Multiple bays & tiers with 3 visible facets) */}

                  {/* BAY 4 (AFT): Cobalt Blue & Deep Red */}
                  <g id="bay-4-t1">
                    <polygon points="170,147 195,150 195,136 170,133" fill="#1E3A8A" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="195,150 215,143 215,129 195,136" fill="#1D4ED8" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="170,133 195,136 215,129 190,126" fill="#60A5FA" stroke="#0F172A" strokeWidth="0.8" />
                  </g>
                  <g id="bay-4-t2">
                    <polygon points="170,133 195,136 195,122 170,119" fill="#991B1B" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="195,136 215,129 215,115 195,122" fill="#DC2626" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="170,119 195,122 215,115 190,112" fill="#F87171" stroke="#0F172A" strokeWidth="0.8" />
                  </g>

                  {/* BAY 3 (MID-AFT): Safety Orange & Ocean Blue */}
                  <g id="bay-3-t1">
                    <polygon points="220,153 248,156 248,142 220,139" fill="#B45309" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="248,156 268,149 268,135 248,142" fill="#D97706" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="220,139 248,142 268,135 240,132" fill="#FBBF24" stroke="#0F172A" strokeWidth="0.8" />
                  </g>
                  <g id="bay-3-t2">
                    <polygon points="220,139 248,142 248,128 220,125" fill="#0369A1" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="248,142 268,135 268,121 248,128" fill="#0284C7" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="220,125 248,128 268,121 240,118" fill="#38BDF8" stroke="#0F172A" strokeWidth="0.8" />
                  </g>
                  <g id="bay-3-t3">
                    <polygon points="220,125 248,128 248,114 220,111" fill="#047857" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="248,128 268,121 268,107 248,114" fill="#059669" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="220,111 248,114 268,107 240,104" fill="#34D399" stroke="#0F172A" strokeWidth="0.8" />
                  </g>

                  {/* BAY 2 (MID-FORWARD): Evergreen & Signal Red */}
                  <g id="bay-2-t1">
                    <polygon points="274,159 304,162 304,148 274,145" fill="#047857" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="304,162 324,155 324,141 304,148" fill="#10B981" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="274,145 304,148 324,141 294,138" fill="#6EE7B7" stroke="#0F172A" strokeWidth="0.8" />
                  </g>
                  <g id="bay-2-t2">
                    <polygon points="274,145 304,148 304,134 274,131" fill="#991B1B" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="304,148 324,141 324,127 304,134" fill="#EF4444" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="274,131 304,134 324,127 294,124" fill="#FCA5A5" stroke="#0F172A" strokeWidth="0.8" />
                  </g>
                  <g id="bay-2-t3">
                    <polygon points="274,131 304,134 304,120 274,117" fill="#1E3A8A" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="304,134 324,127 324,113 304,120" fill="#2563EB" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="274,117 304,120 324,113 294,110" fill="#93C5FD" stroke="#0F172A" strokeWidth="0.8" />
                  </g>

                  {/* BAY 1 (BOW): Ocean Blue & Yellow */}
                  <g id="bay-1-t1">
                    <polygon points="330,165 358,168 358,154 330,151" fill="#0369A1" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="358,168 376,162 376,148 358,154" fill="#0284C7" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="330,151 358,154 376,148 348,145" fill="#7DD3FC" stroke="#0F172A" strokeWidth="0.8" />
                  </g>
                  <g id="bay-1-t2">
                    <polygon points="330,151 358,154 358,140 330,137" fill="#B45309" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="358,154 376,148 376,134 358,140" fill="#D97706" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="330,137 358,140 376,134 348,131" fill="#FDE68A" stroke="#0F172A" strokeWidth="0.8" />
                  </g>

                  {/* E. AFT SUPERSTRUCTURE / NAVIGATION BRIDGE CASTLE */}
                  <g id="deckhouse-bridge">
                    {/* Lower Castle Tier */}
                    <polygon points="126,143 154,146 154,116 126,113" fill="#E2E8F0" stroke="#0F172A" strokeWidth="1" />
                    <polygon points="154,146 166,141 166,111 154,116" fill="#CBD5E1" stroke="#0F172A" strokeWidth="1" />
                    <polygon points="126,113 154,116 166,111 138,108" fill="#F8FAFC" stroke="#0F172A" strokeWidth="1" />

                    {/* Bridge Wheelhouse (Top Tier) */}
                    <polygon points="130,113 152,115 152,98 130,96" fill="#F1F5F9" stroke="#0F172A" strokeWidth="1" />
                    <polygon points="152,115 163,111 163,94 152,98" fill="#E2E8F0" stroke="#0F172A" strokeWidth="1" />
                    <polygon points="130,96 152,98 163,94 141,92" fill="#FFFFFF" stroke="#0F172A" strokeWidth="1" />

                    {/* Panoramic Bridge Windows (Cyan illuminated glass) */}
                    <polygon points="132,106 150,108 150,101 132,99" fill="#38BDF8" opacity="0.9" filter="url(#vesselCyanGlow)" />
                    <polygon points="150,108 160,104 160,97 150,101" fill="#0284C7" opacity="0.9" />

                    {/* Radar Mast & Antenna Tower */}
                    <line x1="145" y1="92" x2="145" y2="68" stroke="#1E293B" strokeWidth="2" />
                    <line x1="138" y1="76" x2="152" y2="76" stroke="#1E293B" strokeWidth="1.5" />
                    {/* Nav Light Beacon */}
                    <circle cx="145" cy="67" r="2.5" fill={severityColor} filter="url(#vesselCyanGlow)" />

                    {/* Twin Exhaust Funnel / Chimney */}
                    <polygon points="125,112 133,113 133,90 125,89" fill="#DC2626" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="133,113 137,111 137,88 133,90" fill="#991B1B" stroke="#0F172A" strokeWidth="0.8" />
                    <polygon points="125,89 133,90 137,88 129,87" fill="#1E293B" stroke="#0F172A" strokeWidth="0.8" />
                  </g>

                  {/* Bow Mooring Mast */}
                  <line x1="410" y1="168" x2="410" y2="148" stroke="#1E293B" strokeWidth="1.8" />
                  <circle cx="410" cy="146" r="2" fill="#38BDF8" />

                  {/* F. Dynamic Stability Callout Markers: Metacenter (M) & Center of Gravity (G) */}
                  <g id="stability-points" opacity="0.9">
                    <line x1="270" y1="92" x2="270" y2="182" stroke="#38BDF8" strokeWidth="1" strokeDasharray="3 3" opacity="0.6" />
                    <circle cx="270" cy="100" r="3" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="1" />
                    <text x="276" y="103" fill="#0284C7" fontSize="7.5" fontWeight="bold">M</text>
                    <circle cx="270" cy="130" r="3" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="1" />
                    <text x="276" y="133" fill="#D97706" fontSize="7.5" fontWeight="bold">G</text>
                  </g>
                </g>
              </g>

              {/* 4. WATERLINE CONTACT RIPPLES & BOW WAKE (IN FRONT OF / AROUND VESSEL) */}
              <g id="hull-waterline-contact-zone">
                {/* Continuous water-contact boundary seam */}
                <path
                  d="M 96 175 C 180 188 310 198 420 197 C 455 197 480 191 488 185"
                  fill="none"
                  stroke="var(--ocean-wave-light)"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  opacity="0.85"
                />

                {/* Subtle expanding contact ripple pulsing gently against hull */}
                <path
                  className="hull-ripple-pulse"
                  d="M 90 179 C 176 193 310 204 424 203 C 458 202 486 196 494 189"
                  fill="none"
                  stroke="var(--ocean-wave-subtle)"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                  opacity="0.65"
                />

                {/* Foam micro-accents lapping along midship */}
                <path
                  d="M 160 185 L 200 188 M 240 192 L 280 195 M 330 197 L 370 197 M 405 196 L 435 194"
                  fill="none"
                  stroke="#FFFFFF"
                  strokeWidth="1.2"
                  strokeLinecap="round"
                  strokeDasharray="4 6"
                  opacity="0.75"
                />

                {/* Bow Wave Peeling Plumes (Cutting through ocean) */}
                <g className="bow-wake-drift">
                  <path
                    d="M 480 188 C 500 192 522 198 538 206"
                    fill="none"
                    stroke="var(--ocean-wave-light)"
                    strokeWidth="1.6"
                    strokeLinecap="round"
                    opacity="0.85"
                  />
                  <path
                    d="M 470 192 C 492 198 514 206 530 217"
                    fill="none"
                    stroke="var(--ocean-wave-subtle)"
                    strokeWidth="1.2"
                    strokeLinecap="round"
                    opacity="0.6"
                  />
                </g>
              </g>

              {/* 5. FOREGROUND ANIMATED AMBIENT WAVES (Layering depth below ship) */}
              <g id="foreground-waves">
                {/* Mid-front ambient wave (8.5s) */}
                <path
                  className="wave-ambient-mid-front"
                  d={`M -40 220 Q 50 216 140 221 T 320 220 T 500 221 T 680 220 T ${w + 40} 221`}
                  fill="none"
                  stroke="var(--ocean-wave-light)"
                  strokeWidth="1.4"
                  opacity="0.7"
                />
                {/* Fore ambient wave (7s) */}
                <path
                  className="wave-ambient-fore"
                  d={`M -30 244 Q 60 239 150 245 T 330 244 T 510 245 T 690 244 T ${w + 40} 245`}
                  fill="none"
                  stroke="var(--ocean-wave-subtle)"
                  strokeWidth="1.2"
                  opacity="0.5"
                />
                {/* Deep swell wave (10s) */}
                <path
                  className="wave-ambient-deep"
                  d={`M -50 266 Q 50 262 150 267 T 350 266 T 550 267 T 750 266 T ${w + 40} 267`}
                  fill="none"
                  stroke="var(--ocean-wave-subtle)"
                  strokeWidth="1"
                  opacity="0.35"
                />
              </g>
            </g>
          )}

          {/* ================================================================= */}
          {/* VIEW 2: FRONT CROSS-SECTION (ROLL INCLINOMETER VIEW)              */}
          {/* ================================================================= */}
          {activeTab === 'front' && (
            <g id="front-roll-view">
              {/* Prominent Waterline Datum Reference Line */}
              <line
                x1="20"
                y1="160"
                x2={w - 20}
                y2="160"
                stroke="var(--ocean-horizon-line)"
                strokeWidth="2"
                strokeDasharray="6 4"
                opacity="0.85"
              />
              <text
                x="25"
                y="152"
                fill="var(--ocean-horizon-line)"
                fontSize="8.5"
                fontWeight="600"
                fontFamily="'Be Vietnam Pro', sans-serif"
              >
                Đường mực nước tham chiếu • 0.0° Cân bằng (Waterline Datum)
              </text>

              {/* Animated water ripples at waterline */}
              <path
                className="wave-ambient-mid-front"
                d={`M -30 162 Q 50 160 130 163 T 290 162 T 450 163 T 610 162 T ${w + 30} 162`}
                fill="none"
                stroke="var(--ocean-wave-light)"
                strokeWidth="1.4"
                opacity="0.75"
              />

              {/* Rotating Hull Group centered at cx */}
              <g transform={`translate(${cx - 270}, 0)`}>
                <g
                  id="rotating-roll-hull"
                  transform={`rotate(${clampedRoll}, 270, 160)`}
                  style={{ transition: motionTransition, willChange: 'transform' }}
                  opacity={isAvailable ? 1 : 0.35}
                  filter="url(#vesselSoftShadow)"
                >
                  {/* 20% Proportional Scale Envelope */}
                  <g transform="translate(270, 160) scale(1.2) translate(-270, -160)">
                    {/* Mast vertical datum */}
                    <line x1="270" y1="40" x2="270" y2="210" stroke="#183E65" strokeWidth="1" strokeDasharray="3 3" opacity="0.5" />

                    {/* Hull Shell */}
                    <path
                      d="M 180 120 L 360 120 L 345 185 C 335 206 295 212 270 212 C 245 212 205 206 195 185 Z"
                      fill="url(#hullTopsidesGrad)"
                      stroke="#0F172A"
                      strokeWidth="2"
                    />
                    <path
                      d="M 205 185 L 335 185 C 325 206 295 212 270 212 C 245 212 215 206 205 185 Z"
                      fill="url(#hullBootTopGrad)"
                    />

                    {/* Deck line */}
                    <line x1="180" y1="120" x2="360" y2="120" stroke="#38BDF8" strokeWidth="1.5" />

                    {/* Bridge Tower */}
                    <rect x="235" y="80" width="70" height="40" fill="#F8FAFC" stroke="#0F172A" strokeWidth="1.5" rx="3" />
                    <rect x="242" y="87" width="56" height="10" fill="#38BDF8" rx="2" />
                    <line x1="270" y1="80" x2="270" y2="52" stroke="#1E293B" strokeWidth="2.5" />
                    <circle cx="270" cy="50" r="3.5" fill={severityColor} />

                    {/* Containers Stacks */}
                    <rect x="195" y="100" width="34" height="20" fill="#EF4444" stroke="#0F172A" strokeWidth="1" rx="1" />
                    <rect x="311" y="100" width="34" height="20" fill="#0284C7" stroke="#0F172A" strokeWidth="1" rx="1" />
                    <rect x="197" y="80" width="30" height="20" fill="#10B981" stroke="#0F172A" strokeWidth="1" rx="1" />
                    <rect x="313" y="80" width="30" height="20" fill="#F59E0B" stroke="#0F172A" strokeWidth="1" rx="1" />

                    {/* Stability points M and G */}
                    <circle cx="270" cy="110" r="3.5" fill="#38BDF8" stroke="#FFFFFF" strokeWidth="1.5" />
                    <text x="278" y="113" fill="#0284C7" fontSize="8" fontWeight="bold">M</text>
                    <circle cx="270" cy="150" r="3.5" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="1.5" />
                    <text x="278" y="153" fill="#D97706" fontSize="8" fontWeight="bold">G</text>
                  </g>
                </g>

                {/* Water displacement ripples at hull flanks */}
                <ellipse className="hull-ripple-pulse" cx="205" cy="164" rx="22" ry="4.5" fill="none" stroke="var(--ocean-wave-light)" strokeWidth="1.2" opacity="0.75" />
                <ellipse className="hull-ripple-pulse" cx="335" cy="164" rx="22" ry="4.5" fill="none" stroke="var(--ocean-wave-light)" strokeWidth="1.2" opacity="0.75" />
              </g>
            </g>
          )}

          {/* ================================================================= */}
          {/* VIEW 3: SIDE PROFILE (PITCH TRIM VIEW)                            */}
          {/* ================================================================= */}
          {activeTab === 'side' && (
            <g id="side-pitch-view">
              {/* Prominent Waterline Datum Reference Line */}
              <line
                x1="20"
                y1="160"
                x2={w - 20}
                y2="160"
                stroke="var(--ocean-horizon-line)"
                strokeWidth="2"
                strokeDasharray="6 4"
                opacity="0.85"
              />
              <text
                x={w - 25}
                y="152"
                fill="var(--ocean-horizon-line)"
                fontSize="8.5"
                fontWeight="600"
                textAnchor="end"
                fontFamily="'Be Vietnam Pro', sans-serif"
              >
                Đường mực nước tham chiếu • 0.0° Mức chuẩn (Waterline Datum)
              </text>

              {/* Animated water ripples at waterline */}
              <path
                className="wave-ambient-mid-front"
                d={`M -30 162 Q 50 160 130 163 T 290 162 T 450 163 T 610 162 T ${w + 30} 162`}
                fill="none"
                stroke="var(--ocean-wave-light)"
                strokeWidth="1.4"
                opacity="0.75"
              />

              {/* Rotating Hull Group centered at cx */}
              <g transform={`translate(${cx - 270}, 0)`}>
                <g
                  id="rotating-pitch-hull"
                  transform={`rotate(${clampedPitch}, 270, 160)`}
                  style={{ transition: motionTransition, willChange: 'transform' }}
                  opacity={isAvailable ? 1 : 0.35}
                  filter="url(#vesselSoftShadow)"
                >
                  {/* 20% Proportional Scale Envelope */}
                  <g transform="translate(270, 160) scale(1.2) translate(-270, -160)">
                    {/* Hull Silhouette Profile: Stern (Left), Bow (Right) */}
                    <path
                      d="M 100 138 
                         L 400 138 
                         C 425 142 445 152 460 160 
                         C 445 178 425 186 395 186 
                         L 120 186 
                         L 100 166 
                         Z"
                      fill="url(#hullTopsidesGrad)"
                      stroke="#0F172A"
                      strokeWidth="2"
                    />
                    <circle cx="454" cy="162" r="6" fill="#B91C1C" stroke="#7F1D1D" strokeWidth="1" />

                    {/* Container Bays along deck */}
                    <rect x="230" y="104" width="46" height="34" fill="#EF4444" stroke="#0F172A" strokeWidth="1" rx="1" />
                    <rect x="230" y="72" width="46" height="32" fill="#2563EB" stroke="#0F172A" strokeWidth="1" rx="1" />
                    <rect x="282" y="104" width="46" height="34" fill="#10B981" stroke="#0F172A" strokeWidth="1" rx="1" />
                    <rect x="282" y="72" width="46" height="32" fill="#F59E0B" stroke="#0F172A" strokeWidth="1" rx="1" />
                    <rect x="334" y="110" width="44" height="28" fill="#0284C7" stroke="#0F172A" strokeWidth="1" rx="1" />

                    {/* Bridge Tower at Aft */}
                    <rect x="125" y="74" width="60" height="64" fill="#F8FAFC" stroke="#0F172A" strokeWidth="1.5" rx="3" />
                    <rect x="135" y="82" width="40" height="9" fill="#38BDF8" rx="2" />
                    <path d="M 142 74 L 148 54 L 160 54 L 160 74 Z" fill="#DC2626" stroke="#0F172A" strokeWidth="1" />
                    <line x1="410" y1="138" x2="410" y2="105" stroke="#1E293B" strokeWidth="2.5" />
                    <circle cx="410" cy="102" r="3.5" fill="#38BDF8" />
                  </g>
                </g>

                {/* Bow and stern wave wake displacement */}
                <g className="bow-wake-drift">
                  <ellipse cx="460" cy="164" rx="22" ry="4" fill="none" stroke="var(--ocean-wave-light)" strokeWidth="1.4" opacity="0.8" />
                  <path d="M 465 164 C 485 167 505 172 525 180" fill="none" stroke="var(--ocean-wave-subtle)" strokeWidth="1.2" opacity="0.6" />
                </g>
                <g className="stern-wake-flow">
                  <ellipse cx="110" cy="164" rx="18" ry="3.5" fill="none" stroke="var(--ocean-wave-light)" strokeWidth="1.2" opacity="0.7" />
                  <path d="M 105 164 C 80 166 55 170 25 176" fill="none" stroke="var(--ocean-wave-subtle)" strokeWidth="1.3" opacity="0.6" />
                </g>
              </g>
            </g>
          )}

          {/* ================================================================= */}
          {/* OVERLAY FOR SENSOR FAULT OR OFFLINE                               */}
          {/* ================================================================= */}
          {!isAvailable && (
            <g id="fault-overlay" transform={`translate(${cx - 270}, 0)`}>
              <rect x="90" y="95" width="360" height="90" rx="10" fill="var(--panel-bg)" stroke={severityColor} strokeWidth="1.5" />
              <text x="270" y="132" fill={severityColor} fontSize="13" fontWeight="700" textAnchor="middle" fontFamily="'Be Vietnam Pro', sans-serif">
                {isOffline ? 'OFFLINE • MẤT KẾT NỐI HỆ THỐNG' : 'SENSOR FAULT • MẤT LIÊN LẠC CẢM BIẾN MPU6050'}
              </text>
              <text x="270" y="156" fill="var(--text-muted)" fontSize="9" fontWeight="500" textAnchor="middle" fontFamily="'Be Vietnam Pro', sans-serif">
                {isOffline
                  ? 'Thiết bị ngắt liên lạc MQTT (>30s). Dữ liệu đóng băng, không hiển thị góc giả tạo.'
                  : 'Cảm biến I2C trả về lỗi NACK. Kiểm tra nguồn cấp và dây bus phần cứng.'}
              </text>
            </g>
          )}
        </svg>
      </div>

      {/* Footer Info: Split View (Compact Status Bar) vs Standalone View (5 Info Cards) */}
      {variant === 'split' ? (
        <div className="dt-compact-bar">
          {hoveredSample ? (
            <div className="dt-freeze-banner">
              <span>❄ SOI MẪU LỊCH SỬ T+{hoveredSample.t}s:</span>
              <strong>Lắc ngang {hoveredSample.roll > 0 ? '+' : ''}{hoveredSample.roll.toFixed(1)}°</strong>
              <span>•</span>
              <strong>Chúi dọc {hoveredSample.pitch > 0 ? '+' : ''}{hoveredSample.pitch.toFixed(1)}°</strong>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--text-muted)' }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: isAvailable ? 'var(--status-green-text)' : 'var(--status-amber-text)' }} />
              <span style={{ fontWeight: 500 }}>
                {isAvailable ? 'Luồng viễn trắc trực tiếp (Đang mô phỏng)' : isOffline ? 'Thiết bị mất kết nối' : 'Lỗi cảm biến I2C'}
              </span>
            </div>
          )}

          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>
              {activeTab === 'side' ? bowStern : portStbd}
            </span>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem', borderLeft: '1px solid var(--border-subtle)', paddingLeft: 10 }}>
              Tâm nghiêng M=2.4m, Trọng tâm G=1.8m • MPU6050
            </span>
          </div>
        </div>
      ) : (
        <div className="digital-twin-footer-grid">
          {/* Card 1: Roll Angle */}
          <div className="dt-info-card">
            <div className="dt-card-header">
              <span>Góc lắc ngang (Roll)</span>
              <span style={{ fontSize: '0.62rem', opacity: 0.75 }}>Chuẩn ±{Math.round(warningDeg)}°</span>
            </div>
            <div
              className="dt-card-value"
              style={{
                color:
                  Math.abs(validRoll) >= tripDeg
                    ? 'var(--status-red-text)'
                    : Math.abs(validRoll) >= warningDeg
                    ? 'var(--status-amber-text)'
                    : '#0284C7',
              }}
            >
              {isAvailable ? `${validRoll > 0 ? '+' : ''}${validRoll.toFixed(1)}°` : '—'}
            </div>
            <div className="dt-card-sub">
              <span
                style={{
                  padding: '1px 6px',
                  borderRadius: 4,
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  background: Math.abs(validRoll) > 0.1 ? 'rgba(37, 99, 166, 0.1)' : 'var(--border-subtle)',
                  color: Math.abs(validRoll) > 0.1 ? 'var(--color-metric-tech)' : 'var(--text-muted)',
                }}
              >
                {isAvailable ? portStbd : '—'}
              </span>
            </div>
          </div>

          {/* Card 2: Pitch Angle */}
          <div className="dt-info-card">
            <div className="dt-card-header">
              <span>Góc chúi dọc (Pitch)</span>
              <span style={{ fontSize: '0.62rem', opacity: 0.75 }}>Chuẩn ±8°</span>
            </div>
            <div
              className="dt-card-value"
              style={{
                color: Math.abs(validPitch) >= 8 ? 'var(--status-red-text)' : 'var(--color-status-caution)',
              }}
            >
              {isAvailable ? `${validPitch > 0 ? '+' : ''}${validPitch.toFixed(1)}°` : '—'}
            </div>
            <div className="dt-card-sub">
              <span
                style={{
                  padding: '1px 6px',
                  borderRadius: 4,
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  background: Math.abs(validPitch) > 0.1 ? 'rgba(217, 119, 6, 0.1)' : 'var(--border-subtle)',
                  color: Math.abs(validPitch) > 0.1 ? 'var(--color-status-caution)' : 'var(--text-muted)',
                }}
              >
                {isAvailable ? bowStern : '—'}
              </span>
            </div>
          </div>

          {/* Card 3: MAI Progress Bar Card */}
          <div className="dt-info-card">
            <div className="dt-card-header">
              <span>Bất thường động học (MAI)</span>
              <strong style={{ color: maiColor, fontFamily: "'JetBrains Mono', monospace", fontVariantNumeric: 'tabular-nums' }}>
                {isAvailable ? `${maiPct} / 100` : '—'}
              </strong>
            </div>
            <div
              style={{
                width: '100%',
                height: 6,
                background: 'var(--border-color)',
                borderRadius: 3,
                overflow: 'hidden',
                margin: '6px 0',
              }}
            >
              <div
                style={{
                  width: `${maiPct}%`,
                  height: '100%',
                  background: maiColor,
                  transition: 'width 0.3s ease-out',
                  borderRadius: 3,
                }}
              />
            </div>
            <div className="dt-card-sub">
              <span style={{ fontSize: '0.65rem' }}>
                {maiPct < 35 ? 'Mức bình thường (< 35)' : maiPct < 70 ? 'Cảnh giác biến động (35–70)' : 'Báo động nguy cơ (≥ 70)'}
              </span>
            </div>
          </div>

          {/* Card 4: TinyML State Recognition */}
          <div className="dt-info-card">
            <div className="dt-card-header">
              <span>Nhận dạng mô hình TinyML</span>
              <span style={{ fontSize: '0.62rem', opacity: 0.75 }}>Random Forest</span>
            </div>
            <div className="dt-card-value" style={{ color: severityColor, fontSize: '16px', fontWeight: 600 }}>
              {isAvailable ? getRFClassNameVi(classRf) : 'Chưa xác định'}
            </div>
            <div className="dt-card-sub">
              <span
                style={{
                  padding: '1px 6px',
                  borderRadius: 4,
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  background: severityBg,
                  color: severityColor,
                  border: `1px solid ${severityColor}`,
                }}
              >
                {isAvailable ? getAlarmLevelNameVi(alarmLevel) : isOffline ? 'Mất kết nối' : 'Lỗi cảm biến'}
              </span>
            </div>
          </div>

          {/* Card 5: Scenario & Orientation */}
          <div className="dt-info-card">
            <div className="dt-card-header">
              <span>Kịch bản & Góc nhìn</span>
              <span style={{ fontSize: '0.62rem', opacity: 0.75 }}>
                {activeTab === 'iso' ? 'Phối cảnh Isometric' : activeTab === 'front' ? 'Mặt cắt ngang' : 'Mặt cắt dọc'}
              </span>
            </div>
            <div className="dt-card-value" style={{ color: 'var(--text-main)', fontSize: '16px', fontWeight: 600 }}>
              {scenario}
            </div>
            <div className="dt-card-sub">
              <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}>
                {activeTab === 'side' ? bowStern : portStbd}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
