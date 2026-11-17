import { Voyage } from './domain';

export interface VoyageAnalyticsChartsProps {
  voyage: Voyage;
}

export function VoyageKinematicDistributionChart({ voyage }: VoyageAnalyticsChartsProps) {
  const metrics = [
    { label: 'Max Abs Roll', value: voyage.maxAbsRollDeg, unit: '°', max: 25, color: voyage.maxAbsRollDeg > 15 ? '#DC2626' : '#0284C7', threshold: 15.0, note: 'Ngưỡng cảnh báo: 15°' },
    { label: 'RMS Roll (T11)', value: voyage.rmsRollDeg, unit: '°', max: 25, color: '#0284C7', note: 'Độ lệch chuẩn lắc ngang' },
    { label: 'P95 Abs Roll', value: voyage.p95AbsRollDeg, unit: '°', max: 25, color: '#0369A1', note: 'Phân vị 95% biên độ' },
    { label: 'Max Abs Pitch', value: voyage.maxAbsPitchDeg, unit: '°', max: 10, color: '#D97706', note: 'Góc chúi cực đại' },
    { label: 'RMS Pitch', value: voyage.rmsPitchDeg, unit: '°', max: 10, color: '#B45309', note: 'Độ lệch chuẩn lắc dọc' },
  ];

  return (
    <div style={{ background: 'var(--panel-bg)', borderRadius: 8, padding: 14, border: '1px solid var(--border-color)', boxShadow: 'var(--card-shadow)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, paddingBottom: 6, borderBottom: '1px solid var(--border-subtle)' }}>
        <div>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase' }}>
            PHÂN PHỐI THỐNG KÊ ĐỘNG HỌC (T11 SPECIFICATION)
          </span>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Khớp chính xác với báo cáo kiểm toán {voyage.id}</div>
        </div>
        <span style={{ fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: 3, background: 'var(--note-info-bg)', color: 'var(--note-info-text)', border: '1px solid var(--note-info-border)' }}>
          {voyage.sampleCount} MẪU (5s/mẫu)
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {metrics.map(m => {
          const pct = Math.min(100, (m.value / m.max) * 100);
          return (
            <div key={m.label} style={{ fontSize: '0.72rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
                <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{m.label}</span>
                <span style={{ fontFamily: 'monospace', fontWeight: 700, color: m.color, fontSize: '0.82rem' }}>
                  {m.value.toFixed(2)}{m.unit}{' '}
                  <small style={{ color: 'var(--text-muted)', fontWeight: 'normal', fontSize: '0.65rem' }}>({m.note})</small>
                </span>
              </div>
              <div style={{ height: 10, background: 'var(--panel-alt)', borderRadius: 5, overflow: 'hidden', position: 'relative', border: '1px solid var(--border-color)' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${pct}%`,
                    background: m.color,
                    borderRadius: 5,
                    transition: 'width 0.4s ease',
                  }}
                />
                {m.threshold && (
                  <div
                    style={{
                      position: 'absolute',
                      left: `${(m.threshold / m.max) * 100}%`,
                      top: 0,
                      bottom: 0,
                      width: 2,
                      background: '#DC2626',
                    }}
                    title={`Ngưỡng cảnh báo: ${m.threshold}°`}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12, paddingTop: 8, borderTop: '1px solid #E2E8F0', fontSize: '0.68rem', color: '#55728D' }}>
        <span>Đường kẻ đỏ: Ngưỡng cảnh báo lắc ngang mô phỏng 15.0°</span>
        <span>RMS Roll chuẩn T11: 7.083967°</span>
      </div>
    </div>
  );
}

export function VoyageRfDistributionChart({ voyage }: VoyageAnalyticsChartsProps) {
  const dist = voyage.rfDistribution;
  const segments = [
    { label: 'Normal (Bình thường)', pct: dist.normalPct, color: '#0284C7', desc: 'Trạng thái ổn định theo Baseline B' },
    { label: 'High Roll (Lắc ngang lớn)', pct: dist.highRollPct, color: '#D97706', desc: 'Góc nghiêng vượt biên độ an toàn' },
    { label: 'Persistent Offset (Nghiêng lệch)', pct: dist.persistentOffsetPct, color: '#EAB308', desc: 'Lệch mạn tĩnh kéo dài (>8°)' },
    { label: 'Amplitude Growth (Cộng hưởng)', pct: dist.amplitudeGrowthPct, color: '#DC2626', desc: 'Biên độ dao động tăng liên tục theo thời gian' },
  ];

  return (
    <div style={{ background: 'var(--panel-bg)', borderRadius: 8, padding: 14, border: '1px solid var(--border-color)', boxShadow: 'var(--card-shadow)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10, paddingBottom: 6, borderBottom: '1px solid var(--border-subtle)' }}>
        <div>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-main)', textTransform: 'uppercase' }}>
            PHÂN BỐ TRẠNG THÁI NHẬN DẠNG RANDOM FOREST
          </span>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Hành trình {voyage.id}</div>
        </div>
        <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--status-green-text)', background: 'var(--note-success-bg)', padding: '2px 8px', borderRadius: 4, border: '1px solid var(--note-success-border)' }}>
          ✓ {voyage.agreementPercent}% Đồng thuận
        </span>
      </div>

      {/* Multi-Segment Stacked Bar */}
      <div style={{ height: 22, display: 'flex', borderRadius: 5, overflow: 'hidden', border: '1px solid var(--border-color)', marginBottom: 12, boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.1)' }}>
        {segments.map(s => (
          <div
            key={s.label}
            style={{
              width: `${s.pct}%`,
              background: s.color,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FFFFFF',
              fontSize: '0.68rem',
              fontWeight: 700,
              fontFamily: 'monospace',
              minWidth: s.pct > 5 ? 'auto' : 0,
            }}
            title={`${s.label}: ${s.pct}%`}
          >
            {s.pct >= 10 ? `${s.pct}%` : ''}
          </div>
        ))}
      </div>

      {/* Breakdown Legend List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.72rem' }}>
        {segments.map(s => (
          <div key={s.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 6px', background: 'var(--panel-alt)', borderRadius: 4, border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 8, height: 8, borderRadius: '50%', background: s.color }} />
              <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{s.label}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.65rem' }}>— {s.desc}</span>
            </div>
            <span style={{ fontFamily: 'monospace', fontWeight: 700, color: s.color, fontSize: '0.8rem' }}>
              {s.pct.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: 'var(--text-muted)' }}>
        <span>Mô hình: TinyML Random Forest (RF-DEMO-v1)</span>
        <span>Đối chiếu: Baseline B Shadow</span>
      </div>
    </div>
  );
}
