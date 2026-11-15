import React, { useState, useRef, useMemo } from 'react';
import { Scenario, AlarmLevel } from './domain';
import { samples } from './mock';

export interface LiveMotionChartProps {
  scenario: Scenario;
  tick: number;
  height?: number;
  offline?: boolean;
  warningDeg?: number;
  tripDeg?: number;
  onHoverSample?: (s: { roll: number; pitch: number; t: number } | null) => void;
  alarms?: { id: string; level: AlarmLevel; title: string; seq?: number }[];
}

export function LiveMotionChart({
  scenario,
  tick,
  height = 240,
  offline = false,
  warningDeg = 15.0,
  tripDeg = 22.0,
  onHoverSample,
  alarms = [],
}: LiveMotionChartProps) {
  const [timeRange, setTimeRange] = useState<'10s' | '30s' | '1m' | '5m'>('30s');
  const [zoom, setZoom] = useState<number>(1.0);
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const [isFrozen, setIsFrozen] = useState<boolean>(false);
  const [frozenTick, setFrozenTick] = useState<number>(tick);
  const containerRef = useRef<HTMLDivElement>(null);

  // Toggle freeze frame
  const handleToggleFreeze = () => {
    if (!isFrozen) {
      setFrozenTick(tick);
      setIsFrozen(true);
    } else {
      setIsFrozen(false);
    }
  };

  const activeTick = isFrozen ? frozenTick : tick;

  const sampleCount = useMemo(() => {
    switch (timeRange) {
      case '10s': return 24;
      case '30s': return 48;
      case '1m': return 80;
      case '5m': return 120;
    }
  }, [timeRange]);

  const rawData = useMemo(() => {
    return samples(scenario, activeTick, sampleCount);
  }, [scenario, activeTick, sampleCount]);

  const w = 700;
  const h = height;
  const padY = 22;
  const padX = 38;

  // Maximum scale degree based on zoom
  const maxDeg = useMemo(() => {
    const base = Math.max(25, tripDeg * 1.15);
    return Math.max(10, base / zoom);
  }, [tripDeg, zoom]);

  const scaleY = (deg: number) => {
    return h / 2 - (deg / maxDeg) * ((h - 2 * padY) / 2);
  };

  const scaleX = (idx: number) => {
    return padX + (idx / Math.max(1, rawData.length - 1)) * (w - padX - 10);
  };

  const rollPoly = useMemo(() => {
    return rawData.map((d, i) => `${scaleX(i).toFixed(1)},${scaleY(d.roll).toFixed(1)}`).join(' ');
  }, [rawData, maxDeg]);

  const pitchPoly = useMemo(() => {
    return rawData.map((d, i) => `${scaleX(i).toFixed(1)},${scaleY(d.pitch).toFixed(1)}`).join(' ');
  }, [rawData, maxDeg]);

  const rollArea = useMemo(() => {
    if (!rawData.length) return '';
    const points = rawData.map((d, i) => `${scaleX(i).toFixed(1)},${scaleY(d.roll).toFixed(1)}`);
    const zeroY = (h / 2).toFixed(1);
    const startX = scaleX(0).toFixed(1);
    const endX = scaleX(rawData.length - 1).toFixed(1);
    return `M ${startX} ${zeroY} L ${points.join(' L ')} L ${endX} ${zeroY} Z`;
  }, [rawData, maxDeg]);

  // Pointer move handler for interactive scrubbing / tooltip
  const handlePointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (offline || !rawData.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const chartW = rect.width;
    const normX = Math.max(0, Math.min(1, (clientX - (padX / w) * chartW) / ((w - padX - 10) / w * chartW)));
    const idx = Math.round(normX * (rawData.length - 1));
    if (idx >= 0 && idx < rawData.length) {
      setHoverIdx(idx);
      if (onHoverSample) {
        onHoverSample(rawData[idx]);
      }
    }
  };

  const handlePointerLeave = () => {
    setHoverIdx(null);
    if (onHoverSample) {
      onHoverSample(null);
    }
  };

  const activeSample = hoverIdx !== null && rawData[hoverIdx] ? rawData[hoverIdx] : rawData[rawData.length - 1];
  const activeSampleIdx = hoverIdx !== null ? hoverIdx : rawData.length - 1;

  // Find peak roll point in current window
  const peakSample = useMemo(() => {
    if (!rawData.length) return null;
    let max = rawData[0];
    let maxIdx = 0;
    for (let i = 1; i < rawData.length; i++) {
      if (Math.abs(rawData[i].roll) > Math.abs(max.roll)) {
        max = rawData[i];
        maxIdx = i;
      }
    }
    return { ...max, idx: maxIdx };
  }, [rawData]);

  return (
    <div className="live-motion-chart-container" ref={containerRef} style={{ background: 'var(--panel-bg)', borderRadius: 8, padding: 12, border: '1px solid var(--border-color)', boxShadow: 'var(--card-shadow)' }}>
      {/* Top Chart Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 10, paddingBottom: 8, borderBottom: '1px solid var(--border-subtle)' }}>
        {/* Time Window Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Cửa sổ (Buffer):</span>
          <div style={{ display: 'flex', background: 'var(--panel-alt)', borderRadius: 6, padding: 2, border: '1px solid var(--border-color)' }}>
            {(['10s', '30s', '1m', '5m'] as const).map(tr => (
              <button
                key={tr}
                type="button"
                onClick={() => setTimeRange(tr)}
                style={{
                  padding: '3px 9px',
                  fontSize: '0.72rem',
                  fontWeight: timeRange === tr ? 700 : 500,
                  color: timeRange === tr ? 'var(--sidebar-active-text)' : 'var(--text-muted)',
                  background: timeRange === tr ? 'var(--sidebar-active-bg)' : 'transparent',
                  border: 'none',
                  borderRadius: 4,
                  boxShadow: timeRange === tr ? '0 1px 3px rgba(0,0,0,0.1)' : 'none',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
              >
                {tr}
              </button>
            ))}
          </div>
        </div>

        {/* Zoom & Freeze Deck */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            type="button"
            onClick={handleToggleFreeze}
            style={{
              padding: '3px 10px',
              fontSize: '0.72rem',
              fontWeight: 700,
              background: isFrozen ? 'var(--status-amber-text)' : 'var(--secondary-btn-bg)',
              color: isFrozen ? '#FFFFFF' : 'var(--secondary-btn-color)',
              border: isFrozen ? '1px solid var(--status-amber-text)' : '1px solid var(--border-color)',
              borderRadius: 4,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 4,
            }}
            title={isFrozen ? 'Tiếp tục luồng dữ liệu thời gian thực' : 'Dừng khung hình để soi biên độ'}
          >
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: isFrozen ? '#FFFFFF' : 'var(--accent-color)' }} />
            {isFrozen ? 'PAUSED (GIỮ KHUNG)' : 'FREEZE FRAME'}
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: 3, background: 'var(--panel-alt)', borderRadius: 6, padding: 2, border: '1px solid var(--border-color)' }}>
            <button
              type="button"
              onClick={() => setZoom(z => Math.min(2.5, +(z + 0.25).toFixed(2)))}
              style={{ padding: '3px 8px', fontSize: '0.72rem', fontWeight: 700, background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-main)' }}
              title="Phóng to trục độ nghiêng"
            >
              +
            </button>
            <span style={{ fontSize: '0.7rem', fontWeight: 700, color: 'var(--text-muted)', minWidth: 26, textAlign: 'center' }}>{zoom}x</span>
            <button
              type="button"
              onClick={() => setZoom(z => Math.max(0.6, +(z - 0.25).toFixed(2)))}
              style={{ padding: '3px 8px', fontSize: '0.72rem', fontWeight: 700, background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-main)' }}
              title="Thu nhỏ trục độ nghiêng"
            >
              −
            </button>
            <button
              type="button"
              onClick={() => setZoom(1.0)}
              style={{ padding: '2px 6px', fontSize: '0.65rem', fontWeight: 600, background: 'var(--secondary-btn-bg)', border: 'none', borderRadius: 3, cursor: 'pointer', color: 'var(--secondary-btn-color)' }}
              title="Đặt lại zoom mặc định 1x"
            >
              1x
            </button>
          </div>

          <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: 'var(--note-info-bg)', color: 'var(--note-info-text)', border: '1px solid var(--note-info-border)' }}>
            DEMO SIMULATION
          </span>
        </div>
      </div>

      {/* Main SVG Oscilloscope Viewport */}
      <div style={{ position: 'relative', width: '100%', minHeight: height, overflow: 'hidden' }}>
        {offline ? (
          <div style={{ height, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'var(--note-danger-bg)', border: '1.5px dashed var(--note-danger-border)', borderRadius: 6, padding: 20 }}>
            <b style={{ color: 'var(--note-danger-text)', fontSize: '0.95rem', letterSpacing: '0.5px' }}>NO LIVE TELEMETRY STREAM</b>
            <p style={{ color: 'var(--note-danger-text)', fontSize: '0.78rem', margin: '6px 0 0', textAlign: 'center', maxWidth: 460 }}>
              {scenario === 'OFFLINE'
                ? 'Mất kết nối MQTT (>30s). Hệ thống không tự tạo dữ liệu thay thế; dữ liệu cảm biến đang được lưu vào bộ đệm Flash ngoại tuyến.'
                : 'Mất liên lạc cảm biến MPU6050 (I2C NACK). Góc nghiêng không khả dụng, không suy diễn trạng thái NORMAL.'}
            </p>
          </div>
        ) : (
          <>
            <svg
              viewBox={`0 0 ${w} ${h}`}
              preserveAspectRatio="none"
              width="100%"
              height={h}
              style={{ cursor: 'crosshair', display: 'block' }}
              onPointerMove={handlePointerMove}
              onPointerLeave={handlePointerLeave}
              aria-label="Biểu đồ tương tác dao động Roll và Pitch theo thời gian thực"
            >
              <defs>
                <linearGradient id="rollAreaGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                  <stop offset="0%" stopColor="#0284C7" stopOpacity="0.22" />
                  <stop offset="50%" stopColor="#0284C7" stopOpacity="0.05" />
                  <stop offset="100%" stopColor="#0284C7" stopOpacity="0.22" />
                </linearGradient>
              </defs>

              {/* Background Rect */}
              <rect x="0" y="0" width={w} height={h} fill="#FBFDFF" />

              {/* Horizontal Degree Gridlines & Y-Axis Labels */}
              {[-20, -10, 0, 10, 20].map(deg => {
                if (Math.abs(deg) > maxDeg) return null;
                const y = scaleY(deg);
                const isZero = deg === 0;
                return (
                  <g key={deg}>
                    <line
                      x1={padX}
                      y1={y}
                      x2={w}
                      y2={y}
                      stroke={isZero ? '#183E65' : '#DCE5EE'}
                      strokeWidth={isZero ? 1.4 : 0.8}
                      strokeDasharray={isZero ? undefined : '3 4'}
                    />
                    <text
                      x={padX - 6}
                      y={y + 3.5}
                      textAnchor="end"
                      fill={isZero ? '#102B49' : '#718EA6'}
                      fontSize="9"
                      fontFamily="monospace"
                      fontWeight={isZero ? 'bold' : 'normal'}
                    >
                      {deg > 0 ? `+${deg}°` : `${deg}°`}
                    </text>
                  </g>
                );
              })}

              {/* Warning Threshold Lines (Amber Dashed) */}
              {warningDeg <= maxDeg && (
                <>
                  <line
                    x1={padX}
                    y1={scaleY(warningDeg)}
                    x2={w}
                    y2={scaleY(warningDeg)}
                    stroke="#D97706"
                    strokeWidth={1.2}
                    strokeDasharray="5 4"
                    opacity={0.85}
                  />
                  <line
                    x1={padX}
                    y1={scaleY(-warningDeg)}
                    x2={w}
                    y2={scaleY(-warningDeg)}
                    stroke="#D97706"
                    strokeWidth={1.2}
                    strokeDasharray="5 4"
                    opacity={0.85}
                  />
                  <text x={w - 6} y={scaleY(warningDeg) - 4} textAnchor="end" fill="#D97706" fontSize="8.5" fontFamily="monospace" fontWeight="bold">
                    WARN +{warningDeg}°
                  </text>
                  <text x={w - 6} y={scaleY(-warningDeg) + 11} textAnchor="end" fill="#D97706" fontSize="8.5" fontFamily="monospace" fontWeight="bold">
                    WARN -{warningDeg}°
                  </text>
                </>
              )}

              {/* Trip Threshold Lines (Red Dashed) */}
              {tripDeg <= maxDeg && (
                <>
                  <line
                    x1={padX}
                    y1={scaleY(tripDeg)}
                    x2={w}
                    y2={scaleY(tripDeg)}
                    stroke="#DC2626"
                    strokeWidth={1.4}
                    strokeDasharray="4 3"
                    opacity={0.9}
                  />
                  <line
                    x1={padX}
                    y1={scaleY(-tripDeg)}
                    x2={w}
                    y2={scaleY(-tripDeg)}
                    stroke="#DC2626"
                    strokeWidth={1.4}
                    strokeDasharray="4 3"
                    opacity={0.9}
                  />
                  <text x={w - 6} y={scaleY(tripDeg) - 4} textAnchor="end" fill="#DC2626" fontSize="8.5" fontFamily="monospace" fontWeight="bold">
                    TRIP +{tripDeg}°
                  </text>
                  <text x={w - 6} y={scaleY(-tripDeg) + 11} textAnchor="end" fill="#DC2626" fontSize="8.5" fontFamily="monospace" fontWeight="bold">
                    TRIP -{tripDeg}°
                  </text>
                </>
              )}

              {/* Roll Area Fill Gradient */}
              <path d={rollArea} fill="url(#rollAreaGrad)" />

              {/* Pitch Curve (Amber) */}
              <polyline
                points={pitchPoly}
                fill="none"
                stroke="#D97706"
                strokeWidth={2.0}
                vectorEffect="non-scaling-stroke"
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={0.85}
              />

              {/* Roll Curve (Cyan/Blue Telemetry) */}
              <polyline
                points={rollPoly}
                fill="none"
                stroke="#0284C7"
                strokeWidth={2.8}
                vectorEffect="non-scaling-stroke"
                strokeLinecap="round"
                strokeLinejoin="round"
              />

              {/* Peak Roll Marker Highlight */}
              {peakSample && Math.abs(peakSample.roll) >= warningDeg && (
                <g>
                  <circle
                    cx={scaleX(peakSample.idx)}
                    cy={scaleY(peakSample.roll)}
                    r="5"
                    fill={Math.abs(peakSample.roll) >= tripDeg ? '#DC2626' : '#D97706'}
                    stroke="#FFFFFF"
                    strokeWidth="1.5"
                  />
                  <line
                    x1={scaleX(peakSample.idx)}
                    y1={scaleY(peakSample.roll)}
                    x2={scaleX(peakSample.idx)}
                    y2={h / 2}
                    stroke={Math.abs(peakSample.roll) >= tripDeg ? '#DC2626' : '#D97706'}
                    strokeWidth="1"
                    strokeDasharray="2 2"
                  />
                  {alarms.length > 0 && (
                    <text
                      x={scaleX(peakSample.idx) + 6}
                      y={scaleY(peakSample.roll) - 6}
                      fill={Math.abs(peakSample.roll) >= tripDeg ? '#DC2626' : '#D97706'}
                      fontSize="8.5"
                      fontFamily="monospace"
                      fontWeight="bold"
                    >
                      {alarms.find(a => a.level === 'CRITICAL' || a.level === 'WARNING')?.id || 'ALM'}
                    </text>
                  )}
                </g>
              )}

              {/* Interactive Scrub / Hover Crosshair Cursor */}
              {activeSample && (
                <g>
                  <line
                    x1={scaleX(activeSampleIdx)}
                    y1={0}
                    x2={scaleX(activeSampleIdx)}
                    y2={h}
                    stroke={hoverIdx !== null ? '#183E65' : '#0284C7'}
                    strokeWidth={hoverIdx !== null ? 1.5 : 1.2}
                    strokeDasharray={hoverIdx !== null ? '3 3' : undefined}
                    opacity={0.9}
                  />
                  {/* Point Dots on Curves */}
                  <circle
                    cx={scaleX(activeSampleIdx)}
                    cy={scaleY(activeSample.roll)}
                    r="4.5"
                    fill="#0284C7"
                    stroke="#FFFFFF"
                    strokeWidth="1.5"
                  />
                  <circle
                    cx={scaleX(activeSampleIdx)}
                    cy={scaleY(activeSample.pitch)}
                    r="4"
                    fill="#D97706"
                    stroke="#FFFFFF"
                    strokeWidth="1.5"
                  />
                </g>
              )}
            </svg>

            {/* Floating Telemetry HUD Tag (Top Right of Viewport) */}
            <div
              style={{
                position: 'absolute',
                top: 8,
                right: 12,
                background: 'var(--panel-bg)',
                border: '1px solid var(--border-color)',
                borderRadius: 6,
                padding: '5px 9px',
                fontSize: '0.72rem',
                fontFamily: 'monospace',
                color: 'var(--text-main)',
                boxShadow: 'var(--card-shadow)',
                display: 'flex',
                alignItems: 'center',
                gap: 10,
                pointerEvents: 'none',
              }}
            >
              <div>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}>{hoverIdx !== null ? 'POINT (SCRUB):' : 'LIVE HEAD:'}</span>{' '}
                <b style={{ color: 'var(--text-main)' }}>T+{activeSample ? activeSample.t * 5 : 0}s</b>
              </div>
              <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: 8 }}>
                <span style={{ color: 'var(--accent-color)', fontWeight: 'bold' }}>
                  ROLL: {activeSample ? (activeSample.roll > 0 ? `+${activeSample.roll.toFixed(1)}°` : `${activeSample.roll.toFixed(1)}°`) : '—'}
                  <small style={{ marginLeft: 3, fontSize: '0.65rem' }}>{activeSample && activeSample.roll > 0 ? 'STBD' : activeSample && activeSample.roll < 0 ? 'PORT' : 'MID'}</small>
                </span>
              </div>
              <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: 8 }}>
                <span style={{ color: 'var(--status-amber-text)', fontWeight: 'bold' }}>
                  PITCH: {activeSample ? (activeSample.pitch > 0 ? `+${activeSample.pitch.toFixed(1)}°` : `${activeSample.pitch.toFixed(1)}°`) : '—'}
                  <small style={{ marginLeft: 3, fontSize: '0.65rem' }}>{activeSample && activeSample.pitch > 0 ? 'BOW UP' : 'BOW DOWN'}</small>
                </span>
              </div>
              {peakSample && (
                <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: 8 }}>
                  <span style={{ color: Math.abs(peakSample.roll) >= tripDeg ? 'var(--status-red-text)' : 'var(--status-amber-text)', fontWeight: 'bold' }}>
                    PEAK: {Math.abs(peakSample.roll).toFixed(1)}°
                  </span>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Timeline X-Axis Time Markers */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.7rem', fontFamily: 'monospace', color: 'var(--text-muted)', marginTop: 6, padding: '0 8px 0 38px' }}>
        <span>-{timeRange}</span>
        <span>-{timeRange === '5m' ? '2.5m' : timeRange === '1m' ? '30s' : timeRange === '30s' ? '15s' : '5s'}</span>
        <span style={{ color: 'var(--accent-color)', fontWeight: 'bold' }}>0s (NOW)</span>
      </div>

      {/* Legend & Quick Status Footer */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10, marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border-subtle)', fontSize: '0.72rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--text-main)', fontWeight: 600 }}>
            <span style={{ width: 10, height: 3, background: 'var(--accent-color)', borderRadius: 1 }} />
            Roll / Lắc ngang (°)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--text-main)', fontWeight: 600 }}>
            <span style={{ width: 10, height: 3, background: 'var(--status-amber-text)', borderRadius: 1 }} />
            Pitch / Lắc dọc (°)
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--status-amber-text)' }}>
            <span style={{ width: 10, height: 0, borderTop: '1.5px dashed var(--status-amber-text)' }} />
            Warn ±{warningDeg}°
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--status-red-text)' }}>
            <span style={{ width: 10, height: 0, borderTop: '1.5px dashed var(--status-red-text)' }} />
            Trip ±{tripDeg}°
          </span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontSize: '0.68rem', fontStyle: 'italic' }}>
          Di chuột trên biểu đồ để xem chi tiết từng mẫu • Đồng bộ trực tiếp với mô hình tàu 2D
        </div>
      </div>
    </div>
  );
}
