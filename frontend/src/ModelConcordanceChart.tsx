import React, { useState } from 'react';
import { RFClass } from './domain';

export interface ModelConcordancePoint {
  seq: number;
  t_sim_s: number;
  rf: RFClass;
  baseline: RFClass;
  roll: number;
  agree: boolean;
  note?: string;
}

export interface ModelConcordanceChartProps {
  scenario?: string;
  height?: number;
}

export function ModelConcordanceChart({ scenario = 'S0', height = 210 }: ModelConcordanceChartProps) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  // Generate 40 representative sequence points comparing RF vs Baseline B
  const points: ModelConcordancePoint[] = React.useMemo(() => {
    return Array.from({ length: 40 }, (_, i) => {
      const t = i * 5;
      let rf: RFClass = 'NORMAL';
      let baseline: RFClass = 'NORMAL';
      let roll = Math.sin(i * 0.3) * 3;
      let note: string | undefined = undefined;

      if (scenario === 'S0b') {
        // Deliberate disagreement: wind gust event around i = 12..18
        if (i >= 12 && i <= 18) {
          roll = 5.2 + Math.sin(i * 0.4) * 2;
          baseline = 'HIGH_ROLL'; // Instantaneous threshold triggered
          rf = 'NORMAL'; // RF knows recovery damping dynamics
          note = 'Gió giật cục bộ: Baseline B kích hoạt ngưỡng tức thời, trong khi RF nhận diện chuyển động tự hồi phục góc nghiêng chuẩn xác.';
        }
      } else if (scenario === 'S1') {
        roll = Math.sin(i * 0.3) * 14;
        rf = 'HIGH_ROLL';
        baseline = 'HIGH_ROLL';
      } else if (scenario === 'S2') {
        roll = 8.2 + Math.sin(i * 0.3) * 2;
        rf = 'PERSISTENT_OFFSET';
        baseline = 'PERSISTENT_OFFSET';
      } else if (scenario === 'S3') {
        roll = Math.sin(i * 0.3) * (2 + i * 0.3);
        rf = i > 15 ? 'AMPLITUDE_GROWTH' : 'NORMAL';
        baseline = i > 15 ? 'HIGH_ROLL' : 'NORMAL';
        if (i > 15) {
          note = 'Cộng hưởng tăng dần: RF nhận diện chính xác AMPLITUDE_GROWTH thay vì chỉ HIGH_ROLL thông thường.';
        }
      } else if (scenario === 'H1') {
        roll = 6.0 + Math.sin(i * 0.3) * 14;
        rf = 'AMPLITUDE_GROWTH';
        baseline = 'HIGH_ROLL';
      }

      const agree = rf === baseline;
      return { seq: i, t_sim_s: t, rf, baseline, roll, agree, note };
    });
  }, [scenario]);

  const totalPoints = points.length;
  const agreeCount = points.filter(p => p.agree).length;
  const agreementPct = ((agreeCount / totalPoints) * 100).toFixed(1);

  const w = 700;
  const h = height;
  const padX = 40;
  const padY = 25;

  const scaleX = (i: number) => {
    return padX + (i / Math.max(1, points.length - 1)) * (w - padX - 15);
  };

  const active = hoverIndex !== null && points[hoverIndex] ? points[hoverIndex] : points[points.length - 1];

  const classColor = (c: RFClass) => {
    switch (c) {
      case 'NORMAL': return '#10B981';
      case 'HIGH_ROLL': return '#D97706';
      case 'PERSISTENT_OFFSET': return '#EAB308';
      case 'AMPLITUDE_GROWTH': return '#DC2626';
      default: return '#64748B';
    }
  };

  return (
    <div style={{ background: 'var(--panel-bg)', borderRadius: 8, padding: 14, border: '1px solid var(--border-color)', boxShadow: 'var(--card-shadow)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, paddingBottom: 6, borderBottom: '1px solid var(--border-subtle)' }}>
        <div>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase' }}>
            ĐỐI CHIẾU DỰ ĐOÁN THEO THỜI GIAN: RANDOM FOREST (CHÍNH) VS BASELINE B (SHADOW)
          </span>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>
            Kịch bản: <b>{scenario}</b> • Chuỗi 40 mẫu tuần tự • Không suy luận AI ở Frontend (FR04/FR20)
          </div>
        </div>
        <span
          style={{
            fontSize: '0.72rem',
            fontWeight: 700,
            padding: '2px 8px',
            borderRadius: 4,
            background: +agreementPct >= 90 ? 'var(--note-success-bg)' : 'var(--note-warn-bg)',
            color: +agreementPct >= 90 ? 'var(--status-green-text)' : 'var(--status-amber-text)',
            border: `1px solid ${+agreementPct >= 90 ? 'var(--note-success-border)' : 'var(--note-warn-border)'}`,
          }}
        >
          {agreementPct}% ĐỒNG THUẬN ({agreeCount}/{totalPoints})
        </span>
      </div>

      {/* SVG Concordance Stream Canvas */}
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
            const normX = Math.max(0, Math.min(1, (clientX - (padX / w) * rect.width) / (((w - padX - 15) / w) * rect.width)));
            const idx = Math.round(normX * (points.length - 1));
            if (idx >= 0 && idx < points.length) setHoverIndex(idx);
          }}
          onPointerLeave={() => setHoverIndex(null)}
        >
          {/* Row Labels */}
          <text x={padX - 8} y={padY + 12} textAnchor="end" fill="#0284C7" fontSize="9" fontFamily="monospace" fontWeight="bold">
            RF (Active)
          </text>
          <text x={padX - 8} y={padY + 48} textAnchor="end" fill="#D97706" fontSize="9" fontFamily="monospace" fontWeight="bold">
            Baseline B
          </text>
          <text x={padX - 8} y={padY + 84} textAnchor="end" fill="#102B49" fontSize="9" fontFamily="monospace" fontWeight="bold">
            Đồng thuận
          </text>

          {/* Row Guide Lines */}
          <line x1={padX} y1={padY + 8} x2={w - 15} y2={padY + 8} stroke="#E2E8F0" strokeWidth={1} />
          <line x1={padX} y1={padY + 44} x2={w - 15} y2={padY + 44} stroke="#E2E8F0" strokeWidth={1} />
          <line x1={padX} y1={padY + 80} x2={w - 15} y2={padY + 80} stroke="#E2E8F0" strokeWidth={1} />

          {/* Stream Points */}
          {points.map((p, i) => {
            const x = scaleX(i);
            const isHover = hoverIndex === i;
            return (
              <g key={i}>
                {/* Column highlight on hover */}
                {isHover && (
                  <rect
                    x={x - 6}
                    y={padY - 4}
                    width={12}
                    height={100}
                    fill="#E0F2FE"
                    opacity={0.6}
                    rx={3}
                  />
                )}

                {/* RF Point */}
                <circle
                  cx={x}
                  cy={padY + 8}
                  r={isHover ? 5 : 3.5}
                  fill={classColor(p.rf)}
                  stroke="#FFFFFF"
                  strokeWidth={1}
                />

                {/* Baseline B Point */}
                <circle
                  cx={x}
                  cy={padY + 44}
                  r={isHover ? 5 : 3.5}
                  fill={classColor(p.baseline)}
                  stroke="#FFFFFF"
                  strokeWidth={1}
                />

                {/* Concordance status marker */}
                <circle
                  cx={x}
                  cy={padY + 80}
                  r={isHover ? 4.5 : 3}
                  fill={p.agree ? '#10B981' : '#D97706'}
                />

                {/* Vertical connection if disagree */}
                {!p.agree && (
                  <line
                    x1={x}
                    y1={padY + 8}
                    x2={x}
                    y2={padY + 80}
                    stroke="#D97706"
                    strokeWidth={1.2}
                    strokeDasharray="2 2"
                    opacity={0.7}
                  />
                )}
              </g>
            );
          })}
        </svg>

        {/* Floating Readout */}
        <div
          style={{
            position: 'absolute',
            bottom: 4,
            left: padX,
            right: 15,
            background: 'var(--panel-bg)',
            border: '1px solid var(--border-color)',
            borderRadius: 6,
            padding: '6px 12px',
            fontSize: '0.72rem',
            color: 'var(--text-main)',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            boxShadow: 'var(--card-shadow)',
          }}
        >
          <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
            <span>MẪU #{active.seq} (T+{active.t_sim_s}s):</span>
            <span>
              RF:{' '}
              <b style={{ color: classColor(active.rf) }}>{active.rf}</b>
            </span>
            <span>
              Baseline B:{' '}
              <b style={{ color: classColor(active.baseline) }}>{active.baseline}</b>
            </span>
            <span>
              Góc Roll:{' '}
              <b style={{ color: 'var(--accent-color)' }}>{active.roll > 0 ? `+${active.roll.toFixed(1)}°` : `${active.roll.toFixed(1)}°`}</b>
            </span>
          </div>
          <div>
            <span
              style={{
                fontWeight: 700,
                color: active.agree ? 'var(--status-green-text)' : 'var(--status-amber-text)',
              }}
            >
              {active.agree ? '✓ ĐỒNG THUẬN (CONCORDANT)' : '⚠ BẤT ĐỒNG (DISCREPANCY)'}
            </span>
          </div>
        </div>
      </div>

      {/* Disagreement Callout Note */}
      {scenario === 'S0b' && (
        <div
          style={{
            marginTop: 10,
            padding: '8px 12px',
            background: 'var(--note-warn-bg)',
            border: '1px solid var(--note-warn-border)',
            borderRadius: 6,
            fontSize: '0.72rem',
            color: 'var(--note-warn-text)',
          }}
        >
          <b>GIẢI TRÌNH BẤT ĐỒNG CÓ CHỦ ĐÍCH (KỊCH BẢN S0b):</b> Tại các mẫu bị gió giật cục bộ, Baseline B vượt ngưỡng biên độ tức thời nên gắn nhãn <code>HIGH_ROLL</code>; trong khi thuật toán Random Forest phân tích đặc trưng chu kỳ dao động tự hồi phục nên giữ nhãn <code>NORMAL</code>, giúp tránh cảnh báo giả trên tàu thực.
        </div>
      )}

      {/* Legend */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 10, paddingTop: 6, borderTop: '1px solid var(--border-subtle)', fontSize: '0.7rem' }}>
        <div style={{ display: 'flex', gap: 10 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text-main)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10B981' }} />
            NORMAL
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text-main)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#D97706' }} />
            HIGH_ROLL
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text-main)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#EAB308' }} />
            PERSISTENT_OFFSET
          </span>
          <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--text-main)' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#DC2626' }} />
            AMPLITUDE_GROWTH
          </span>
        </div>
        <div style={{ color: 'var(--text-muted)' }}>
          Màu xanh lá: Đồng thuận (Agree) • Màu cam: Bất đồng (Discrepancy)
        </div>
      </div>
    </div>
  );
}

