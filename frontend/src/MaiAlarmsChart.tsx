import React, { useState, useRef, useEffect } from 'react';
import { Alarm } from './domain';

export interface MaiPoint {
  t_sim_s: number;
  mai: number;
  alarm_id?: string;
  alarm_level?: string;
}

export interface MaiAlarmsChartProps {
  points?: MaiPoint[];
  currentMai?: number;
  alarms?: Alarm[];
  thresholdCaution?: number; // default 35
  thresholdCritical?: number; // default 70
  onSelectAlarm?: (alarmId: string) => void;
  height?: number;
  offline?: boolean;
}

export function MaiAlarmsChart({
  points,
  currentMai = 12,
  alarms = [],
  thresholdCaution = 35,
  thresholdCritical = 70,
  onSelectAlarm,
  height = 190,
  offline = false,
}: MaiAlarmsChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number>(700);

  useEffect(() => {
    if (!containerRef.current) return;
    const update = () => {
      if (containerRef.current) {
        const cw = containerRef.current.clientWidth - 28;
        if (cw > 0) setContainerWidth(Math.round(cw));
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

  // Generate standard 60-point MAI timeline if points not provided
  const data: MaiPoint[] = React.useMemo(() => {
    if (points && points.length) return points;
    // synthesize 60 historical points leading to currentMai
    return Array.from({ length: 60 }, (_, i) => {
      const t = i * 5;
      // create realistic MAI variation
      const baseVariation = Math.sin(i * 0.15) * 8 + Math.cos(i * 0.3) * 5;
      const target = currentMai;
      const progress = i / 59;
      const mai = Math.max(0, Math.min(100, Math.round(target * progress + (1 - progress) * 20 + baseVariation)));
      const alm = alarms.length > 0 ? alarms[i % alarms.length] : undefined;
      const hasAlarm = (i === 15 || i === 36 || i === 52) && !!alm;
      const alarmAt = hasAlarm ? alm?.id : undefined;
      const level = hasAlarm ? alm?.level : undefined;
      return { t_sim_s: t, mai, alarm_id: alarmAt, alarm_level: level };
    });
  }, [points, currentMai, alarms]);

  const w = Math.max(340, containerWidth);
  const h = height;
  const padX = 38;
  const padY = 20;

  const scaleY = (mai: number) => {
    return h - padY - (mai / 100) * (h - 2 * padY);
  };

  const scaleX = (i: number) => {
    return padX + (i / Math.max(1, data.length - 1)) * (w - padX - 10);
  };

  if (offline) {
    return (
      <div style={{ height, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'var(--note-danger-bg)', border: '1.5px dashed var(--note-danger-border)', borderRadius: 6, padding: 16 }}>
        <b style={{ color: 'var(--note-danger-text)', fontSize: '0.9rem' }}>Không có tín hiệu viễn trắc MAI</b>
        <p style={{ color: 'var(--note-danger-text)', fontSize: '0.75rem', margin: '4px 0 0', textAlign: 'center' }}>
          Mất kết nối cảm biến hoặc thiết bị ngoại tuyến. Không tính toán chỉ số MAI giả định.
        </p>
      </div>
    );
  }

  const polyPoints = data.map((d, i) => `${scaleX(i).toFixed(1)},${scaleY(d.mai).toFixed(1)}`).join(' ');
  const areaPoints = `M ${scaleX(0).toFixed(1)} ${scaleY(0).toFixed(1)} L ${polyPoints} L ${scaleX(data.length - 1).toFixed(1)} ${scaleY(0).toFixed(1)} Z`;

  const activePoint = hoverIndex !== null && data[hoverIndex] ? data[hoverIndex] : data[data.length - 1];
  const activeIdx = hoverIndex !== null ? hoverIndex : data.length - 1;

  return (
    <div ref={containerRef} style={{ position: 'relative', background: 'var(--panel-bg)', borderRadius: 12, padding: 14, border: '1px solid var(--border-color)', boxShadow: 'var(--card-shadow)' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, paddingBottom: 8, borderBottom: '1px solid var(--border-subtle)', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-main)' }}>
            Diễn biến chỉ số bất thường chuyển động (MAI) & Sự kiện cảnh báo
          </span>
          <span style={{ fontSize: '0.65rem', fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: 'var(--note-info-bg)', color: 'var(--note-info-text)', border: '1px solid var(--note-info-border)' }}>
            Theo dõi MAI • TinyML
          </span>
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Nhấp thẻ mã sự kiện để mở chi tiết cảnh báo
        </div>
      </div>

      {/* SVG Canvas */}
      <div style={{ position: 'relative', width: '100%', height: h, overflow: 'hidden' }}>
        <svg
          viewBox={`0 0 ${w} ${h}`}
          width="100%"
          height={h}
          style={{ cursor: 'crosshair', display: 'block', touchAction: 'none' }}
          onPointerDown={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clientX = e.clientX - rect.left;
            const normX = Math.max(0, Math.min(1, (clientX - padX) / Math.max(1, rect.width - padX - 10)));
            const idx = Math.round(normX * (data.length - 1));
            if (idx >= 0 && idx < data.length) setHoverIndex(idx);
          }}
          onPointerMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clientX = e.clientX - rect.left;
            const normX = Math.max(0, Math.min(1, (clientX - padX) / Math.max(1, rect.width - padX - 10)));
            const idx = Math.round(normX * (data.length - 1));
            if (idx >= 0 && idx < data.length) setHoverIndex(idx);
          }}
          onPointerLeave={() => setHoverIndex(null)}
          aria-label="Biểu đồ Motion Anomaly Index theo thời gian và sự kiện cảnh báo"
        >
          <defs>
            <linearGradient id="maiGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#EF4444" stopOpacity="0.22" />
              <stop offset="35%" stopColor="#F59E0B" stopOpacity="0.16" />
              <stop offset="70%" stopColor="#10B981" stopOpacity="0.08" />
              <stop offset="100%" stopColor="#10B981" stopOpacity="0.01" />
            </linearGradient>
          </defs>

          {/* Background Canvas Rect */}
          <rect x="0" y="0" width={w} height={h} fill="var(--panel-bg)" rx={6} />

          {/* Background Severity Zones */}
          {/* Critical zone: 70-100 */}
          <rect
            x={padX}
            y={scaleY(100)}
            width={w - padX - 10}
            height={scaleY(thresholdCritical) - scaleY(100)}
            fill="#EF4444"
            fillOpacity={0.08}
          />
          {/* Caution zone: 35-70 */}
          <rect
            x={padX}
            y={scaleY(thresholdCritical)}
            width={w - padX - 10}
            height={scaleY(thresholdCaution) - scaleY(thresholdCritical)}
            fill="#F59E0B"
            fillOpacity={0.06}
          />
          {/* Normal zone: 0-35 */}
          <rect
            x={padX}
            y={scaleY(thresholdCaution)}
            width={w - padX - 10}
            height={scaleY(0) - scaleY(thresholdCaution)}
            fill="#10B981"
            fillOpacity={0.03}
          />

          {/* Horizontal Grid lines and Y labels */}
          {[0, 35, 70, 100].map(v => (
            <g key={v}>
              <line x1={padX} y1={scaleY(v)} x2={w - 10} y2={scaleY(v)} stroke="var(--border-subtle)" strokeWidth={0.8} />
              <text
                x={padX - 8}
                y={scaleY(v) + 3.5}
                textAnchor="end"
                fill="var(--text-muted)"
                fontSize="9"
                fontFamily="'Be Vietnam Pro', sans-serif"
                fontWeight="500"
              >
                {v}
              </text>
            </g>
          ))}

          {/* Threshold Boundary Lines */}
          <line
            x1={padX}
            y1={scaleY(thresholdCritical)}
            x2={w - 10}
            y2={scaleY(thresholdCritical)}
            stroke="#EF4444"
            strokeWidth={1.3}
            strokeDasharray="4 3"
          />
          <text
            x={w - 14}
            y={scaleY(thresholdCritical) - 4}
            textAnchor="end"
            fill="#EF4444"
            fontSize="8.5"
            fontFamily="'Be Vietnam Pro', sans-serif"
            fontWeight="600"
          >
            NGUY CẤP ({thresholdCritical})
          </text>

          <line
            x1={padX}
            y1={scaleY(thresholdCaution)}
            x2={w - 10}
            y2={scaleY(thresholdCaution)}
            stroke="#F59E0B"
            strokeWidth={1.3}
            strokeDasharray="4 3"
          />
          <text
            x={w - 14}
            y={scaleY(thresholdCaution) - 4}
            textAnchor="end"
            fill="#F59E0B"
            fontSize="8.5"
            fontFamily="'Be Vietnam Pro', sans-serif"
            fontWeight="600"
          >
            CẢNH GIÁC ({thresholdCaution})
          </text>

          {/* MAI Area & Line */}
          <path d={areaPoints} fill="url(#maiGradient)" />
          <polyline
            points={polyPoints}
            fill="none"
            stroke="#0284C7"
            strokeWidth={2.8}
            strokeLinecap="round"
            strokeLinejoin="round"
            vectorEffect="non-scaling-stroke"
          />

          {/* Alarm Beacon Markers (No concentric rings) */}
          {data.map((d, i) => {
            if (!d.alarm_id) return null;
            const x = scaleX(i);
            const y = scaleY(d.mai);
            const col = d.alarm_level === 'CRITICAL' ? '#EF4444' : d.alarm_level === 'WARNING' ? '#F59E0B' : '#0284C7';
            const isHover = hoverIndex === i;
            return (
              <g
                key={d.alarm_id + i}
                onClick={() => onSelectAlarm && onSelectAlarm(d.alarm_id!)}
                style={{ cursor: 'pointer' }}
                aria-label={`Sự kiện cảnh báo ${d.alarm_id}`}
              >
                {/* Subtle vertical slice highlight when hovered or normal */}
                {isHover && (
                  <rect
                    x={x - 10}
                    y={padY}
                    width={20}
                    height={h - 2 * padY}
                    fill={col}
                    fillOpacity={0.08}
                    rx={2}
                  />
                )}

                {/* Vertical tether drop-line connecting pill to data point */}
                <line
                  x1={x}
                  y1={25}
                  x2={x}
                  y2={y}
                  stroke={col}
                  strokeWidth={isHover ? 1.4 : 1}
                  strokeDasharray="2 2"
                  opacity={isHover ? 0.95 : 0.75}
                />

                {/* Single small solid dot on curve */}
                <circle
                  cx={x}
                  cy={y}
                  r={isHover ? 4 : 3.5}
                  fill={col}
                  stroke="var(--panel-bg)"
                  strokeWidth="1.5"
                />

                {/* Top Beacon Pill Badge */}
                <rect x={x - 24} y={8} width={48} height={16} rx={4} fill={col} />
                {/* Downward anchor tip */}
                <polygon points={`${x - 3},24 ${x + 3},24 ${x},26.5`} fill={col} />
                <text
                  x={x}
                  y={19.5}
                  textAnchor="middle"
                  fill="#FFFFFF"
                  fontSize="8"
                  fontFamily="'JetBrains Mono', monospace"
                  fontWeight="600"
                >
                  {d.alarm_id}
                </text>
              </g>
            );
          })}

          {/* Interactive Scrub Line with Vertical Slice & Single Solid Dot */}
          {activePoint && (
            <g>
              {/* Subtle vertical slice */}
              <rect
                x={scaleX(activeIdx) - 8}
                y={padY}
                width={16}
                height={h - 2 * padY}
                fill="var(--accent-color)"
                fillOpacity={0.05}
                rx={2}
              />
              <line
                x1={scaleX(activeIdx)}
                y1={padY}
                x2={scaleX(activeIdx)}
                y2={h - padY}
                stroke="var(--accent-color)"
                strokeWidth={1.2}
                opacity={0.75}
              />
              {/* Single small solid dot */}
              <circle
                cx={scaleX(activeIdx)}
                cy={scaleY(activePoint.mai)}
                r="3.5"
                fill={activePoint.mai >= thresholdCritical ? '#EF4444' : activePoint.mai >= thresholdCaution ? '#F59E0B' : '#10B981'}
                stroke="var(--panel-bg)"
                strokeWidth="1.5"
              />
            </g>
          )}
        </svg>

        {/* Dynamic Boundary-Clamped Floating Readout HUD */}
        {activePoint && (
          <div
            className="chart-tooltip"
            style={{
              top: 10,
              left: `${Math.max(16, Math.min(84, (scaleX(activeIdx) / w) * 100))}%`,
              transform: 'translateX(-50%)',
              display: 'flex',
              alignItems: 'center',
              gap: 12,
            }}
          >
            <div>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>Mốc thời gian:</span>{' '}
              <b style={{ color: 'var(--text-main)', fontVariantNumeric: 'tabular-nums' }}>
                T+{activePoint.t_sim_s}s
              </b>
            </div>
            <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: 8 }}>
              <span style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Chỉ số MAI:</span>{' '}
              <b
                style={{
                  fontSize: '0.85rem',
                  color:
                    activePoint.mai >= thresholdCritical
                      ? 'var(--status-red-text)'
                      : activePoint.mai >= thresholdCaution
                      ? 'var(--status-amber-text)'
                      : 'var(--status-green-text)',
                }}
              >
                {activePoint.mai} / 100
              </b>
            </div>
            <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: 8 }}>
              <span
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  padding: '2px 7px',
                  borderRadius: 4,
                  background:
                    activePoint.mai >= thresholdCritical
                      ? 'var(--note-danger-bg)'
                      : activePoint.mai >= thresholdCaution
                      ? 'var(--note-warn-bg)'
                      : 'var(--note-success-bg)',
                  color:
                    activePoint.mai >= thresholdCritical
                      ? 'var(--status-red-text)'
                      : activePoint.mai >= thresholdCaution
                      ? 'var(--status-amber-text)'
                      : 'var(--status-green-text)',
                }}
              >
                {activePoint.mai >= thresholdCritical
                  ? 'RỦI RO NGUY CẤP'
                  : activePoint.mai >= thresholdCaution
                  ? 'RỦI RO TĂNG CAO'
                  : 'TRẠNG THÁI AN TOÀN'}
              </span>
            </div>
            {activePoint.alarm_id && (
              <div style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: 8 }}>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Cảnh báo:</span>{' '}
                <b style={{ fontFamily: "'JetBrains Mono', monospace", color: 'var(--accent-color)', fontSize: '0.72rem' }}>
                  {activePoint.alarm_id}
                </b>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer Legend */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border-subtle)', fontSize: '0.72rem', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--status-green-text)', fontWeight: 500 }}>
            <span style={{ width: 10, height: 10, background: 'var(--note-success-bg)', border: '1px solid var(--note-success-border)', borderRadius: 3 }} />
            Bình thường (&lt; {thresholdCaution})
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--status-amber-text)', fontWeight: 500 }}>
            <span style={{ width: 10, height: 10, background: 'var(--note-warn-bg)', border: '1px solid var(--note-warn-border)', borderRadius: 3 }} />
            Cảnh giác ({thresholdCaution} – {thresholdCritical})
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--status-red-text)', fontWeight: 500 }}>
            <span style={{ width: 10, height: 10, background: 'var(--note-danger-bg)', border: '1px solid var(--note-danger-border)', borderRadius: 3 }} />
            Nguy cấp (≥ {thresholdCritical})
          </span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.68rem' }}>
          Được tính toán bởi thuật toán TinyML • Đồng bộ thời gian thực
        </div>
      </div>
    </div>
  );
}
