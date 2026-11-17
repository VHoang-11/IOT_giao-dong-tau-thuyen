import React, { useState } from 'react';
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

  const w = 700;
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
        <b style={{ color: 'var(--note-danger-text)', fontSize: '0.9rem' }}>MAI TELEMETRY UNAVAILABLE</b>
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
    <div style={{ position: 'relative', background: 'var(--panel-bg)', borderRadius: 8, padding: 12, border: '1px solid var(--border-color)', boxShadow: 'var(--card-shadow)' }}>
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8, paddingBottom: 6, borderBottom: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase' }}>
            MOTION ANOMALY INDEX (MAI) TIMELINE & SỰ KIỆN CẢNH BÁO
          </span>
          <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: 'var(--note-info-bg)', color: 'var(--note-info-text)', border: '1px solid var(--note-info-border)' }}>
            FR03 / FR15
          </span>
        </div>
        <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
          Nhấp biểu tượng cảnh báo để mở chi tiết
        </div>
      </div>

      {/* SVG Canvas */}
      <div style={{ position: 'relative', width: '100%', height: h }}>
        <svg
          viewBox={`0 0 ${w} ${h}`}
          preserveAspectRatio="none"
          width="100%"
          height={h}
          style={{ cursor: 'crosshair', display: 'block' }}
          onPointerMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const clientX = e.clientX - rect.left;
            const normX = Math.max(0, Math.min(1, (clientX - (padX / w) * rect.width) / (((w - padX - 10) / w) * rect.width)));
            const idx = Math.round(normX * (data.length - 1));
            if (idx >= 0 && idx < data.length) setHoverIndex(idx);
          }}
          onPointerLeave={() => setHoverIndex(null)}
        >
          <defs>
            <linearGradient id="maiGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#DC2626" stopOpacity="0.25" />
              <stop offset="35%" stopColor="#D97706" stopOpacity="0.18" />
              <stop offset="70%" stopColor="#10B981" stopOpacity="0.10" />
              <stop offset="100%" stopColor="#10B981" stopOpacity="0.02" />
            </linearGradient>
          </defs>

          {/* Background Zones */}
          {/* Critical zone: 70-100 */}
          <rect
            x={padX}
            y={scaleY(100)}
            width={w - padX - 10}
            height={scaleY(thresholdCritical) - scaleY(100)}
            fill="#FEF2F2"
            opacity={0.6}
          />
          {/* Caution zone: 35-70 */}
          <rect
            x={padX}
            y={scaleY(thresholdCritical)}
            width={w - padX - 10}
            height={scaleY(thresholdCaution) - scaleY(thresholdCritical)}
            fill="#FFFBEB"
            opacity={0.6}
          />
          {/* Normal zone: 0-35 */}
          <rect
            x={padX}
            y={scaleY(thresholdCaution)}
            width={w - padX - 10}
            height={scaleY(0) - scaleY(thresholdCaution)}
            fill="#F0FDF4"
            opacity={0.6}
          />

          {/* Threshold Lines */}
          <line
            x1={padX}
            y1={scaleY(thresholdCritical)}
            x2={w - 10}
            y2={scaleY(thresholdCritical)}
            stroke="#DC2626"
            strokeWidth={1.2}
            strokeDasharray="4 3"
          />
          <text x={w - 14} y={scaleY(thresholdCritical) - 3} textAnchor="end" fill="#DC2626" fontSize="8.5" fontFamily="monospace" fontWeight="bold">
            CRITICAL ({thresholdCritical})
          </text>

          <line
            x1={padX}
            y1={scaleY(thresholdCaution)}
            x2={w - 10}
            y2={scaleY(thresholdCaution)}
            stroke="#D97706"
            strokeWidth={1.2}
            strokeDasharray="4 3"
          />
          <text x={w - 14} y={scaleY(thresholdCaution) - 3} textAnchor="end" fill="#D97706" fontSize="8.5" fontFamily="monospace" fontWeight="bold">
            CAUTION ({thresholdCaution})
          </text>

          {/* Grid lines and Y labels */}
          {[0, 35, 70, 100].map(v => (
            <g key={v}>
              <line x1={padX} y1={scaleY(v)} x2={w - 10} y2={scaleY(v)} stroke="#CBD5E1" strokeWidth={0.8} />
              <text x={padX - 6} y={scaleY(v) + 3.5} textAnchor="end" fill="#64748B" fontSize="9" fontFamily="monospace">
                {v}
              </text>
            </g>
          ))}

          {/* MAI Area & Line */}
          <path d={areaPoints} fill="url(#maiGradient)" />
          <polyline
            points={polyPoints}
            fill="none"
            stroke="#102B49"
            strokeWidth={2.4}
            vectorEffect="non-scaling-stroke"
          />

          {/* Alarm Event Markers */}
          {data.map((d, i) => {
            if (!d.alarm_id) return null;
            const x = scaleX(i);
            const y = scaleY(d.mai);
            const col = d.alarm_level === 'CRITICAL' ? '#DC2626' : d.alarm_level === 'WARNING' ? '#D97706' : '#0284C7';
            return (
              <g
                key={d.alarm_id + i}
                onClick={() => onSelectAlarm && onSelectAlarm(d.alarm_id!)}
                style={{ cursor: 'pointer' }}
              >
                <line x1={x} y1={0} x2={x} y2={h - padY} stroke={col} strokeWidth={1.5} strokeDasharray="2 3" opacity={0.8} />
                <circle cx={x} cy={y} r={6} fill={col} stroke="#FFFFFF" strokeWidth={2} />
                <rect x={x - 22} y={10} width={44} height={16} rx={3} fill={col} />
                <text x={x} y={21} textAnchor="middle" fill="#FFFFFF" fontSize="8" fontFamily="monospace" fontWeight="bold">
                  {d.alarm_id}
                </text>
              </g>
            );
          })}

          {/* Interactive Scrub Line */}
          {activePoint && (
            <g>
              <line
                x1={scaleX(activeIdx)}
                y1={padY}
                x2={scaleX(activeIdx)}
                y2={h - padY}
                stroke="#183E65"
                strokeWidth={1.2}
                strokeDasharray="2 2"
              />
              <circle
                cx={scaleX(activeIdx)}
                cy={scaleY(activePoint.mai)}
                r={4.5}
                fill={activePoint.mai >= thresholdCritical ? '#DC2626' : activePoint.mai >= thresholdCaution ? '#D97706' : '#10B981'}
                stroke="#FFFFFF"
                strokeWidth={1.5}
              />
            </g>
          )}
        </svg>

        {/* Floating Readout */}
        <div
          style={{
            position: 'absolute',
            top: 8,
            right: 12,
            background: 'var(--panel-bg)',
            border: '1px solid var(--border-color)',
            borderRadius: 6,
            padding: '4px 10px',
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
          <span>MỐC: <b>T+{activePoint.t_sim_s}s</b></span>
          <span style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: 8 }}>
            MAI:{' '}
            <b
              style={{
                color: activePoint.mai >= thresholdCritical ? 'var(--status-red-text)' : activePoint.mai >= thresholdCaution ? 'var(--status-amber-text)' : 'var(--status-green-text)',
              }}
            >
              {activePoint.mai} / 100
            </b>
          </span>
          <span style={{ borderLeft: '1px solid var(--border-color)', paddingLeft: 8 }}>
            RỦI RO:{' '}
            <b style={{ color: activePoint.mai >= thresholdCritical ? 'var(--status-red-text)' : activePoint.mai >= thresholdCaution ? 'var(--status-amber-text)' : 'var(--status-green-text)' }}>
              {activePoint.mai >= thresholdCritical ? 'CRITICAL RISK' : activePoint.mai >= thresholdCaution ? 'ELEVATED' : 'SAFE'}
            </b>
          </span>
        </div>
      </div>

      {/* Footer Legend */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8, paddingTop: 6, borderTop: '1px solid var(--border-subtle)', fontSize: '0.72rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--status-green-text)', fontWeight: 600 }}>
            <span style={{ width: 10, height: 10, background: 'var(--note-success-bg)', border: '1px solid var(--note-success-border)', borderRadius: 2 }} />
            Bình thường (&lt; {thresholdCaution})
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--status-amber-text)', fontWeight: 600 }}>
            <span style={{ width: 10, height: 10, background: 'var(--note-warn-bg)', border: '1px solid var(--note-warn-border)', borderRadius: 2 }} />
            Cảnh giác ({thresholdCaution} - {thresholdCritical})
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--status-red-text)', fontWeight: 600 }}>
            <span style={{ width: 10, height: 10, background: 'var(--note-danger-bg)', border: '1px solid var(--note-danger-border)', borderRadius: 2 }} />
            Nguy cấp (≥ {thresholdCritical})
          </span>
        </div>
        <div style={{ color: 'var(--text-muted)', fontStyle: 'italic', fontSize: '0.68rem' }}>
          Dựa trên Motion Anomaly Index được tính toán bởi thuật toán TinyML
        </div>
      </div>
    </div>
  );
}
