import { useEffect, useState } from 'react';
import { ApiError, apiRequest } from '../api';
import type { CargoConfigIn, CargoConfigOut, SourceMode } from '../api';
import type { Session } from '../domain';
import { getRoleNameVi } from '../i18n/vi';
import { Button, Pill } from '../ui';

const FIELD_VI: Record<string, string> = {
  cargo_hold_depth_mm: 'Chiều sâu hầm hàng (mm)',
  water_sensor_full_scale_mm: 'Thang đo tối đa cảm biến nước (mm)',
};

export function CargoConfigModal({
  open,
  cargoId,
  sourceMode,
  token,
  session,
  onClose,
  onSaved,
  onUnauthorized,
  notify,
}: {
  open: boolean;
  cargoId: string;
  sourceMode?: SourceMode | null;
  token: string;
  session: Session;
  onClose: () => void;
  onSaved: () => void;
  onUnauthorized: () => void;
  notify: (msg: string) => void;
}) {
  const canEdit = session.role !== 'Operator';
  const isSim = sourceMode === 'SIMULATION';

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [cfg, setCfg] = useState<CargoConfigOut | null>(null);

  const [vesselType, setVesselType] = useState('');
  const [cargoType, setCargoType] = useState('');
  const [depthStr, setDepthStr] = useState('');
  const [scaleStr, setScaleStr] = useState('');
  const [calibrated, setCalibrated] = useState(false);

  const syncForm = (c: CargoConfigOut) => {
    setVesselType(c.vessel_type ?? '');
    setCargoType(c.cargo_type ?? '');
    setDepthStr(c.cargo_hold_depth_mm != null ? String(c.cargo_hold_depth_mm) : '');
    setScaleStr(c.water_sensor_full_scale_mm != null ? String(c.water_sensor_full_scale_mm) : '');
    setCalibrated(Boolean(c.sensor_calibrated));
  };

  useEffect(() => {
    if (!open) return;
    let alive = true;
    setLoading(true);
    setError(null);
    setSuccess(null);
    apiRequest<CargoConfigOut>(token, `/api/v1/devices/${encodeURIComponent(cargoId)}/cargo/config`)
      .then((res) => {
        if (!alive) return;
        setCfg(res);
        syncForm(res);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 401) {
          onUnauthorized();
          return;
        }
        setError(e instanceof Error ? e.message : 'Không tải được cấu hình hầm hàng.');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [open, cargoId, token, onUnauthorized]);

  if (!open) return null;

  const parsedDepth = depthStr.trim() === '' ? null : Number(depthStr);
  const parsedScale = scaleStr.trim() === '' ? null : Number(scaleStr);
  const hasValidCalibrationBasis =
    parsedDepth !== null &&
    Number.isFinite(parsedDepth) &&
    parsedDepth > 0 &&
    parsedDepth <= 100000 &&
    parsedScale !== null &&
    Number.isFinite(parsedScale) &&
    parsedScale > 0 &&
    parsedScale <= parsedDepth;

  const canMarkCalibrated = canEdit && !isSim && hasValidCalibrationBasis;

  const handleSave = async () => {
    setError(null);
    setSuccess(null);

    if (depthStr.trim() !== '') {
      if (parsedDepth === null || !Number.isFinite(parsedDepth) || parsedDepth <= 0 || parsedDepth > 100000) {
        setError('Chiều sâu hầm hàng phải nằm trong khoảng (0, 100.000] mm.');
        return;
      }
    }
    if (scaleStr.trim() !== '') {
      if (parsedScale === null || !Number.isFinite(parsedScale) || parsedScale <= 0) {
        setError('Thang đo tối đa cảm biến nước phải lớn hơn 0 mm.');
        return;
      }
      if (parsedDepth !== null && Number.isFinite(parsedDepth) && parsedScale > parsedDepth) {
        setError('Thang đo cảm biến nước không được lớn hơn chiều sâu hầm hàng.');
        return;
      }
    }
    if (calibrated && !hasValidCalibrationBasis) {
      setError('Không thể đánh dấu đã hiệu chuẩn khi chưa khai báo đủ chiều sâu hầm hàng và thang đo cảm biến nước hợp lệ.');
      return;
    }
    if (calibrated && isSim) {
      setError('Thiết bị đang ở chế độ SIMULATION (mô phỏng), không đánh dấu hiệu chuẩn cảm biến thực tế.');
      return;
    }

    const body: CargoConfigIn = {
      vessel_type: vesselType.trim() || null,
      cargo_type: cargoType.trim() || null,
      cargo_hold_depth_mm: parsedDepth,
      water_sensor_full_scale_mm: parsedScale,
      sensor_calibrated: isSim ? false : calibrated,
    };

    setSaving(true);
    try {
      const updated = await apiRequest<CargoConfigOut>(
        token,
        `/api/v1/devices/${encodeURIComponent(cargoId)}/cargo/config`,
        { method: 'PUT', body: JSON.stringify(body) }
      );
      setCfg(updated);
      syncForm(updated);
      setSuccess(`Đã lưu cấu hình hầm hàng phiên bản v${updated.version}. Ngưỡng cảnh báo đã được backend tính lại.`);
      notify(`Đã cập nhật cấu hình hầm hàng ${cargoId} (v${updated.version})`);
      onSaved();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.status === 401) {
        onUnauthorized();
        return;
      }
      setError(e instanceof Error ? e.message : 'Lưu cấu hình hầm hàng thất bại.');
    } finally {
      setSaving(false);
    }
  };

  const w = cfg?.effective_thresholds.water;
  const temp = cfg?.effective_thresholds.temperature;
  const hum = cfg?.effective_thresholds.humidity;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Cấu hình thông số hầm hàng"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1000,
        background: 'rgba(15, 32, 51, 0.52)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
      }}
      onClick={onClose}
    >
      <div
        className="modal-card"
        style={{
          background: 'var(--panel-bg)',
          color: 'var(--text-main)',
          borderRadius: 12,
          border: '1px solid var(--border-color)',
          width: '100%',
          maxWidth: 720,
          maxHeight: '90vh',
          overflowY: 'auto',
          padding: 22,
          boxShadow: '0 20px 48px rgba(15, 32, 51, 0.25)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
          <div>
            <h3 style={{ margin: 0, color: 'var(--color-title)' }}>Cấu hình thông số hầm hàng</h3>
            <div style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 4 }}>
              Cargo Node: <b>{cargoId}</b> • Chế độ dữ liệu:{' '}
              <Pill kind={isSim ? 'caution' : 'normal'}>
                {isSim ? 'SIMULATION (MÔ PHỎNG)' : 'REAL / SENSOR (CẢM BIẾN THỰC TẾ)'}
              </Pill>
            </div>
          </div>
          <Button kind="ghost" onClick={onClose}>Đóng</Button>
        </div>

        {!canEdit && (
          <div className="note warning" style={{ marginBottom: 12 }}>
            Tài khoản <b>{session.username} ({getRoleNameVi(session.role)})</b> chỉ có quyền xem thông số. Chỉ <b>Supervisor</b> hoặc <b>Admin</b> mới được phép chỉnh sửa cấu hình hầm hàng.
          </div>
        )}

        {loading && <div className="note" style={{ marginBottom: 12 }}>Đang tải cấu hình hầm hàng từ Backend…</div>}
        {error && <div className="note offline" style={{ marginBottom: 12 }}><b>Lỗi:</b> {error}</div>}
        {success && <div className="note" style={{ marginBottom: 12, borderLeftColor: 'var(--color-status-positive)' }}><b>Thành công:</b> {success}</div>}

        {cfg && (
          <>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14, fontSize: 13 }}>
              <Pill kind={cfg.configured ? 'normal' : 'caution'}>
                {cfg.configured ? `Đã cấu hình • v${cfg.version}` : 'Chưa cấu hình (v0)'}
              </Pill>
              <Pill kind="neutral">{cfg.threshold_version}</Pill>
              <Pill kind={cfg.sensor_calibrated ? 'normal' : 'caution'}>
                {isSim ? 'SIMULATION (không áp dụng hiệu chuẩn thật)' : cfg.sensor_calibrated ? 'Cảm biến đã hiệu chuẩn' : 'Cảm biến chưa hiệu chuẩn'}
              </Pill>
            </div>

            {cfg.missing_fields.length > 0 && (
              <div className="note warning" style={{ marginBottom: 14 }}>
                <b>Thông tin còn thiếu ({cfg.missing_fields.length}):</b>{' '}
                {cfg.missing_fields.map((f) => FIELD_VI[f] ?? f).join(', ')}.
                <div style={{ marginTop: 4, fontSize: 12 }}>
                  Khi chưa đủ thông tin, hệ thống giữ trạng thái nước xâm nhập là <b>UNKNOWN (NOT_CONFIGURED)</b> và không tự giả định kích thước hầm.
                </div>
              </div>
            )}

            {cfg.errors.length > 0 && (
              <div className="note offline" style={{ marginBottom: 14 }}>
                <b>Cấu hình lỗi:</b> {cfg.errors.join('; ')}
              </div>
            )}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 12, marginBottom: 14 }}>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                <span>Loại tàu (<code>vessel_type</code>)</span>
                <input
                  type="text"
                  value={vesselType}
                  disabled={!canEdit || saving}
                  placeholder="vd: Tàu chở hàng rời"
                  onChange={(e) => setVesselType(e.target.value)}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                <span>Loại hàng (<code>cargo_type</code>)</span>
                <input
                  type="text"
                  value={cargoType}
                  disabled={!canEdit || saving}
                  placeholder="vd: Nông sản khô"
                  onChange={(e) => setCargoType(e.target.value)}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                <span>Chiều sâu hầm hàng (mm) *</span>
                <input
                  type="number"
                  min={1}
                  max={100000}
                  step="any"
                  value={depthStr}
                  disabled={!canEdit || saving}
                  placeholder="vd: 10000"
                  onChange={(e) => {
                    setDepthStr(e.target.value);
                    if (e.target.value.trim() === '') setCalibrated(false);
                  }}
                />
              </label>
              <label style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 13 }}>
                <span>Thang đo tối đa cảm biến nước (mm) *</span>
                <input
                  type="number"
                  min={1}
                  max={100000}
                  step="any"
                  value={scaleStr}
                  disabled={!canEdit || saving}
                  placeholder="vd: 3000"
                  onChange={(e) => {
                    setScaleStr(e.target.value);
                    if (e.target.value.trim() === '') setCalibrated(false);
                  }}
                />
              </label>
            </div>

            <div style={{ padding: '10px 12px', borderRadius: 8, background: 'var(--panel-alt)', border: '1px solid var(--border-color)', marginBottom: 14 }}>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, fontWeight: 600, cursor: canMarkCalibrated ? 'pointer' : 'not-allowed' }}>
                <input
                  type="checkbox"
                  checked={isSim ? false : calibrated}
                  disabled={!canMarkCalibrated || saving}
                  onChange={(e) => setCalibrated(e.target.checked)}
                />
                <span>Đánh dấu cảm biến thực tế đã hiệu chuẩn (<code>sensor_calibrated</code>)</span>
              </label>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
                {isSim
                  ? 'Thiết bị đang ở chế độ SIMULATION (mô phỏng), không dùng cờ hiệu chuẩn cảm biến thực tế.'
                  : hasValidCalibrationBasis
                  ? 'Đã có căn cứ cấu hình chiều sâu hầm và thang đo cảm biến nước.'
                  : 'Chỉ được đánh dấu đã hiệu chuẩn sau khi khai báo đầy đủ chiều sâu hầm hàng và thang đo cảm biến nước hợp lệ.'}
              </div>
            </div>

            <div style={{ padding: 12, borderRadius: 8, border: '1px solid var(--border-color)', marginBottom: 14 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: 'var(--color-title)', marginBottom: 8 }}>
                Ngưỡng hiệu lực do Backend tính toán
              </div>
              <dl className="kv" style={{ margin: 0 }}>
                <dt>Nước xâm nhập ({w?.unit ?? 'mm'})</dt>
                <dd>
                  WARNING ≥ <b>{w?.warning_mm ?? '—'}</b> {w?.unit} • CRITICAL ≥{' '}
                  <b>{w?.critical_mm != null ? w.critical_mm : 'Chưa xác định (thiếu chiều sâu hầm)'}</b>{' '}
                  {w?.critical_mm != null ? w.unit : ''}
                </dd>
                <dt>Nhiệt độ không khí ({temp?.unit ?? '°C'})</dt>
                <dd>WARNING ≥ <b>{temp?.warning ?? '—'}</b> • CRITICAL ≥ <b>{temp?.critical ?? '—'}</b> {temp?.unit}</dd>
                <dt>Độ ẩm không khí ({hum?.unit ?? '%RH'})</dt>
                <dd>WARNING ≥ <b>{hum?.warning ?? '—'}</b> • CRITICAL ≥ <b>{hum?.critical ?? '—'}</b> {hum?.unit}</dd>
                <dt>Nguồn tham chiếu (nước)</dt>
                <dd style={{ fontSize: 12 }}>{w?.reference.join(' • ') ?? '—'}</dd>
                <dt>Cập nhật lần cuối</dt>
                <dd style={{ fontSize: 12 }}>
                  {cfg.updated_by ? `${cfg.updated_by} • ${cfg.updated_at ? new Date(cfg.updated_at).toLocaleString('vi-VN') : '—'}` : 'Chưa lưu cấu hình'}
                </dd>
              </dl>
              <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>{cfg.disclaimer}</div>
            </div>
          </>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
          <Button kind="ghost" onClick={onClose} disabled={saving}>Đóng</Button>
          {canEdit && (
            <Button onClick={handleSave} disabled={loading || saving || !cfg}>
              {saving ? 'Đang lưu cấu hình…' : 'Lưu cấu hình hầm hàng'}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
