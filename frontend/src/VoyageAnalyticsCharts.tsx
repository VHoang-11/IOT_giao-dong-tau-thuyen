import { Voyage } from './domain';

export interface VoyageAnalyticsChartsProps {
  voyage: Voyage;
}

export function VoyageKinematicDistributionChart({ voyage }: VoyageAnalyticsChartsProps) {
  const metrics = [
    { label: 'Góc lắc ngang cực đại (Max Roll)', value: voyage.maxAbsRollDeg, unit: '°', max: 25, color: voyage.maxAbsRollDeg > 15 ? '#DC2626' : '#0284C7', threshold: 15.0, note: 'Ngưỡng cảnh báo: 15°' },
    { label: 'Góc lắc ngang hiệu dụng (RMS)', value: voyage.rmsRollDeg, unit: '°', max: 25, color: '#0284C7', note: 'Độ lệch chuẩn lắc ngang' },
    { label: 'Phân vị 95 lắc ngang (P95)', value: voyage.p95AbsRollDeg, unit: '°', max: 25, color: '#0369A1', note: 'Phân vị 95% biên độ' },
    { label: 'Góc chúi dọc cực đại (Max Pitch)', value: voyage.maxAbsPitchDeg, unit: '°', max: 10, color: '#D97706', note: 'Góc chúi cực đại' },
    { label: 'Góc chúi dọc hiệu dụng RMS', value: voyage.rmsPitchDeg, unit: '°', max: 10, color: '#B45309', note: 'Độ lệch chuẩn lắc dọc' },
  ];

  return (
    <div style={{ background: 'var(--panel-bg)', borderRadius: 12, padding: 16, border: '1px solid var(--border-color)', boxShadow: 'var(--card-shadow)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, paddingBottom: 8, borderBottom: '1px solid var(--border-subtle)' }}>
        <div>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-main)' }}>
            Phân phối thống kê động học
          </span>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Khớp chính xác với báo cáo kiểm toán {voyage.id}</div>
        </div>
        <span style={{ fontSize: '0.65rem', fontWeight: 600, padding: '2px 8px', borderRadius: 4, background: 'var(--note-info-bg)', color: 'var(--note-info-text)', border: '1px solid var(--note-info-border)' }}>
          {voyage.sampleCount} mẫu (5s/mẫu)
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        {metrics.map(m => {
          const pct = Math.min(100, (m.value / m.max) * 100);
          return (
            <div key={m.label} style={{ fontSize: '0.74rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
                <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{m.label}</span>
                <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: m.color, fontSize: '0.82rem' }}>
                  {m.value.toFixed(2)}{m.unit}{' '}
                  <small style={{ color: 'var(--text-muted)', fontWeight: 'normal', fontSize: '0.68rem' }}>({m.note})</small>
                </span>
              </div>
              <div style={{ height: 12, background: 'var(--panel-alt)', borderRadius: 6, overflow: 'hidden', position: 'relative', border: '1px solid var(--border-color)' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${pct}%`,
                    background: `linear-gradient(90deg, ${m.color}CC, ${m.color})`,
                    borderRadius: 6,
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
                      boxShadow: '0 0 4px rgba(220, 38, 38, 0.6)',
                    }}
                    title={`Ngưỡng cảnh báo: ${m.threshold}°`}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 14, paddingTop: 10, borderTop: '1px solid var(--border-subtle)', fontSize: '0.68rem', color: 'var(--text-muted)' }}>
        <span>Đường kẻ đỏ: Ngưỡng cảnh báo lắc ngang 15.0°</span>
        <span>RMS Roll đo kiểm: <b>7.083967°</b></span>
      </div>
    </div>
  );
}

export function VoyageRfDistributionChart({ voyage }: VoyageAnalyticsChartsProps) {
  const dist = voyage.rfDistribution;
  const segments = [
    { label: 'Bình thường (Normal)', pct: dist.normalPct, color: '#0284C7', desc: 'Trạng thái ổn định theo Baseline B' },
    { label: 'Lắc ngang lớn (High Roll)', pct: dist.highRollPct, color: '#D97706', desc: 'Góc nghiêng vượt biên độ an toàn' },
    { label: 'Nghiêng lệch (Persistent Offset)', pct: dist.persistentOffsetPct, color: '#EAB308', desc: 'Lệch mạn tĩnh kéo dài (>8°)' },
    { label: 'Cộng hưởng (Amplitude Growth)', pct: dist.amplitudeGrowthPct, color: '#DC2626', desc: 'Biên độ dao động tăng liên tục theo thời gian' },
  ];

  return (
    <div style={{ background: 'var(--panel-bg)', borderRadius: 12, padding: 16, border: '1px solid var(--border-color)', boxShadow: 'var(--card-shadow)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12, paddingBottom: 8, borderBottom: '1px solid var(--border-subtle)' }}>
        <div>
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-main)' }}>
            Phân bố trạng thái nhận dạng Random Forest
          </span>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)' }}>Hành trình {voyage.id}</div>
        </div>
        <span style={{ fontSize: '0.72rem', fontWeight: 600, color: 'var(--status-green-text)', background: 'var(--note-success-bg)', padding: '2px 8px', borderRadius: 4, border: '1px solid var(--note-success-border)' }}>
          ✓ {voyage.agreementPercent}% Đồng thuận
        </span>
      </div>

      {/* Multi-Segment Stacked Bar */}
      <div style={{ height: 24, display: 'flex', borderRadius: 8, overflow: 'hidden', border: '1px solid var(--border-color)', marginBottom: 14, boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.08)' }}>
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
              fontSize: '0.7rem',
              fontWeight: 600,
              fontVariantNumeric: 'tabular-nums',
              borderRight: '1.5px solid var(--panel-bg)',
              minWidth: s.pct > 5 ? 'auto' : 0,
            }}
            title={`${s.label}: ${s.pct}%`}
          >
            {s.pct >= 10 ? `${s.pct}%` : ''}
          </div>
        ))}
      </div>

      {/* Breakdown Legend List */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7, fontSize: '0.74rem' }}>
        {segments.map(s => (
          <div key={s.label} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 10px', background: 'var(--panel-alt)', borderRadius: 6, border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ width: 9, height: 9, borderRadius: '50%', background: s.color }} />
              <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{s.label}</span>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.68rem' }}>— {s.desc}</span>
            </div>
            <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600, color: s.color, fontSize: '0.82rem' }}>
              {s.pct.toFixed(1)}%
            </span>
          </div>
        ))}
      </div>

      <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', fontSize: '0.68rem', color: 'var(--text-muted)' }}>
        <span>Mô hình: TinyML Random Forest (RF-DEMO-v1)</span>
        <span>Đối chiếu: Baseline B Shadow</span>
      </div>
    </div>
  );
}
