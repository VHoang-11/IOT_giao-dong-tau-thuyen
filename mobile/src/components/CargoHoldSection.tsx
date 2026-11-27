import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  View,
} from 'react-native';
import {
  ApiCargoConfig,
  ApiCargoMetric,
  ApiCargoNodeStatus,
  CargoMetricState,
} from '../data/liveApi';
import { C, SHADOWS } from '../theme';
import { CargoLiveContext, Session } from '../types/domain';
import { ActionBtn, MetricCard, Panel, Pill, TwoCol } from './UI';

const METRIC_VI: Record<string, string> = {
  WATER: 'Nước xâm nhập',
  TEMPERATURE: 'Nhiệt độ không khí hầm',
  HUMIDITY: 'Độ ẩm không khí hầm',
};

const REASON_VI: Record<string, string> = {
  NO_DATA: 'chưa có dữ liệu',
  STALE: 'dữ liệu cũ / mất kết nối',
  SENSOR_FAULT: 'lỗi cảm biến DHT22',
  VALUE_MISSING: 'thiếu giá trị',
  OUT_OF_RANGE: 'giá trị ngoài khoảng hợp lệ',
  NOT_CONFIGURED: 'chưa cấu hình hầm hàng',
};

const DATA_CLASS_VI: Record<string, string> = {
  SIMULATION: 'MÔ PHỎNG',
  SENSOR_UNCALIBRATED: 'CẢM BIẾN CHƯA HIỆU CHUẨN',
  SENSOR_CALIBRATED: 'CẢM BIẾN ĐÃ HIỆU CHUẨN',
};

const FIELD_VI: Record<string, string> = {
  cargo_hold_depth_mm: 'Chiều sâu hầm hàng (mm)',
  water_sensor_full_scale_mm: 'Thang đo cảm biến nước (mm)',
};

function stateColor(s: CargoMetricState): string {
  if (s === 'CRITICAL') return C.red;
  if (s === 'WARNING') return C.amber;
  if (s === 'NORMAL') return C.green;
  return C.cyan;
}

function metricValue(m?: ApiCargoMetric): string {
  if (!m || m.value === null || m.value === undefined) return '—';
  return `${m.value.toFixed(m.unit === 'mm' ? 0 : 1)} ${m.unit}`;
}

function metricNote(m?: ApiCargoMetric): string {
  if (!m) return 'UNKNOWN: chưa có dữ liệu';
  if (m.state === 'UNKNOWN') {
    return `UNKNOWN: ${REASON_VI[m.reason ?? ''] ?? m.reason ?? 'không đánh giá được'}`;
  }
  return `${m.state} • W ≥ ${m.warning ?? '—'} • C ≥ ${m.critical ?? '—'} ${m.unit}`;
}

function primaryNode(cargo: CargoLiveContext): ApiCargoNodeStatus | null {
  const ns = cargo.status?.nodes ?? [];
  if (!ns.length) return null;
  return [...ns].sort((a, b) => {
    const ta = a.last_sample_at ? Date.parse(a.last_sample_at) || 0 : 0;
    const tb = b.last_sample_at ? Date.parse(b.last_sample_at) || 0 : 0;
    return tb - ta;
  })[0];
}

export function CargoHoldSection({
  cargo,
  session,
}: {
  cargo?: CargoLiveContext | null;
  session: Session | null;
}) {
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [cfg, setCfg] = useState<ApiCargoConfig | null>(null);

  const [vesselType, setVesselType] = useState('');
  const [cargoType, setCargoType] = useState('');
  const [depthStr, setDepthStr] = useState('');
  const [scaleStr, setScaleStr] = useState('');
  const [calibrated, setCalibrated] = useState(false);

  const node = cargo ? primaryNode(cargo) : null;
  const canEdit = session !== null && session.role !== 'Operator';
  const isSim = node?.source_mode === 'SIMULATION';

  const syncForm = (c: ApiCargoConfig) => {
    setVesselType(c.vessel_type ?? '');
    setCargoType(c.cargo_type ?? '');
    setDepthStr(c.cargo_hold_depth_mm != null ? String(c.cargo_hold_depth_mm) : '');
    setScaleStr(c.water_sensor_full_scale_mm != null ? String(c.water_sensor_full_scale_mm) : '');
    setCalibrated(Boolean(c.sensor_calibrated));
  };

  useEffect(() => {
    if (!modalOpen || !cargo || !node) return;
    let alive = true;
    setLoading(true);
    setError(null);
    setSuccess(null);
    cargo
      .getConfig(node.device_id)
      .then((res) => {
        if (!alive) return;
        setCfg(res);
        syncForm(res);
      })
      .catch((e: unknown) => {
        if (!alive) return;
        setError(e instanceof Error ? e.message : 'Không tải được cấu hình hầm hàng.');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [modalOpen, node?.device_id]);

  if (!cargo) return null;

  const st = cargo.status;
  const water = node?.metrics.find((m) => m.metric === 'WATER');
  const temp = node?.metrics.find((m) => m.metric === 'TEMPERATURE');
  const hum = node?.metrics.find((m) => m.metric === 'HUMIDITY');
  const openAlerts = cargo.alerts.filter((a) => a.state !== 'CLEARED');

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
    if (!node) return;
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
        setError('Thang đo cảm biến nước phải lớn hơn 0 mm.');
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

    setSaving(true);
    try {
      const updated = await cargo.saveConfig(node.device_id, {
        vessel_type: vesselType.trim() || null,
        cargo_type: cargoType.trim() || null,
        cargo_hold_depth_mm: parsedDepth,
        water_sensor_full_scale_mm: parsedScale,
        sensor_calibrated: isSim ? false : calibrated,
      });
      setCfg(updated);
      syncForm(updated);
      setSuccess(`Đã lưu cấu hình v${updated.version}. Ngưỡng cảnh báo đã được backend tính lại.`);
      cargo.onSaved();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Lưu cấu hình hầm hàng thất bại.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Panel title="GIÁM SÁT HẦM HÀNG (CARGO NODE)" tag={node ? node.device_id : 'CHƯA GẮN'}>
        {cargo.statusError ? (
          <View style={s.warnBox}>
            <Text style={s.warnTitle}>Không đọc được trạng thái hầm hàng</Text>
            <Text style={s.warnBody}>{cargo.statusError}</Text>
          </View>
        ) : !st ? (
          <Text style={s.mutedText}>Đang tải trạng thái hầm hàng từ Backend…</Text>
        ) : st.link === 'NO_NODE' ? (
          <View style={s.warnBox}>
            <Text style={s.warnTitle}>CHƯA GẮN CARGO NODE (UNKNOWN)</Text>
            <Text style={s.warnBody}>
              Admin gắn Cargo Node bằng PATCH /api/v1/devices/{'{cargo_id}'} với parent_device_id.
            </Text>
          </View>
        ) : (
          <>
            <View style={s.statusRow}>
              <Pill
                label={
                  st.link === 'ONLINE'
                    ? `TRỰC TUYẾN • ${st.state}`
                    : st.link === 'STALE'
                    ? `DỮ LIỆU CŨ (${node?.age_s != null ? Math.round(node.age_s) : '?'}s)`
                    : 'CHƯA CÓ DỮ LIỆU'
                }
                level={st.state === 'CRITICAL' ? 'CRITICAL' : st.state === 'WARNING' ? 'WARNING' : 'NORMAL'}
              />
              {node?.data_class && (
                <Pill
                  label={DATA_CLASS_VI[node.data_class] ?? node.data_class}
                  level={node.data_class === 'SENSOR_CALIBRATED' ? 'NORMAL' : 'CAUTION'}
                />
              )}
            </View>

            {node && node.missing_config.length > 0 && (
              <View style={s.warnBox}>
                <Text style={s.warnTitle}>UNKNOWN (NOT_CONFIGURED) — Thiếu cấu hình hầm hàng</Text>
                <Text style={s.warnBody}>
                  Còn thiếu: {node.missing_config.map((f) => FIELD_VI[f] ?? f).join(', ')}. Nhấn "Cấu hình hầm hàng" bên dưới để bổ sung.
                </Text>
              </View>
            )}

            <TwoCol>
              <MetricCard
                label={METRIC_VI.WATER}
                value={metricValue(water)}
                subtext={metricNote(water)}
                color={stateColor(water?.state ?? 'UNKNOWN')}
              />
              <MetricCard
                label={METRIC_VI.TEMPERATURE}
                value={metricValue(temp)}
                subtext={metricNote(temp)}
                color={stateColor(temp?.state ?? 'UNKNOWN')}
              />
            </TwoCol>

            <View style={{ marginTop: 8 }}>
              <MetricCard
                label={METRIC_VI.HUMIDITY}
                value={metricValue(hum)}
                subtext={metricNote(hum)}
                color={stateColor(hum?.state ?? 'UNKNOWN')}
              />
            </View>

            {openAlerts.length > 0 && (
              <View style={s.alertList}>
                {openAlerts.map((a) => (
                  <Text key={a.id} style={s.alertItem}>
                    • [{a.level}] {METRIC_VI[a.metric] ?? a.metric}: {a.value.toFixed(a.unit === 'mm' ? 0 : 1)} {a.unit} ({a.state})
                  </Text>
                ))}
              </View>
            )}

            {node && (
              <View style={{ marginTop: 10 }}>
                <ActionBtn
                  label="Cấu hình hầm hàng"
                  onPress={() => setModalOpen(true)}
                  tone="secondary"
                />
              </View>
            )}
          </>
        )}
      </Panel>

      <Modal visible={modalOpen} animationType="slide" transparent onRequestClose={() => setModalOpen(false)}>
        <View style={s.backdrop}>
          <View style={s.sheet}>
            <View style={s.sheetHeader}>
              <View style={{ flex: 1 }}>
                <Text style={s.sheetTitle}>Cấu hình thông số hầm hàng</Text>
                <Text style={s.sheetSub}>
                  {node?.device_id ?? ''} • {isSim ? 'SIMULATION (MÔ PHỎNG)' : 'REAL / SENSOR (CẢM BIẾN THỰC TẾ)'}
                </Text>
              </View>
              <Pressable onPress={() => setModalOpen(false)} style={s.closeBtn}>
                <Text style={s.closeBtnText}>Đóng</Text>
              </Pressable>
            </View>

            <ScrollView style={{ maxHeight: 520 }} keyboardShouldPersistTaps="handled">
              {!canEdit && (
                <View style={s.warnBox}>
                  <Text style={s.warnTitle}>Chế độ chỉ xem (RBAC)</Text>
                  <Text style={s.warnBody}>
                    Tài khoản {session?.username ?? '—'} ({session?.role ?? 'Operator'}) không có quyền chỉnh sửa. Cần Supervisor hoặc Admin.
                  </Text>
                </View>
              )}

              {loading && <ActivityIndicator color={C.borderNavy} style={{ marginVertical: 12 }} />}
              {error && (
                <View style={s.errBox}>
                  <Text style={s.errText}>{error}</Text>
                </View>
              )}
              {success && (
                <View style={s.okBox}>
                  <Text style={s.okText}>{success}</Text>
                </View>
              )}

              {cfg && (
                <>
                  <Text style={s.metaText}>
                    Phiên bản: {cfg.configured ? `v${cfg.version}` : 'v0 (chưa cấu hình)'} • {cfg.threshold_version}
                  </Text>

                  {cfg.missing_fields.length > 0 && (
                    <View style={s.warnBox}>
                      <Text style={s.warnTitle}>Thiếu thông tin ({cfg.missing_fields.length})</Text>
                      <Text style={s.warnBody}>
                        {cfg.missing_fields.map((f) => FIELD_VI[f] ?? f).join(', ')}. Khi chưa đủ thông tin, hệ thống giữ trạng thái UNKNOWN (NOT_CONFIGURED).
                      </Text>
                    </View>
                  )}

                  <Text style={s.label}>Loại tàu (vessel_type)</Text>
                  <TextInput
                    style={[s.input, !canEdit && s.inputDisabled]}
                    editable={canEdit && !saving}
                    value={vesselType}
                    onChangeText={setVesselType}
                    placeholder="vd: Tàu chở hàng rời"
                    placeholderTextColor={C.muted}
                  />

                  <Text style={s.label}>Loại hàng (cargo_type)</Text>
                  <TextInput
                    style={[s.input, !canEdit && s.inputDisabled]}
                    editable={canEdit && !saving}
                    value={cargoType}
                    onChangeText={setCargoType}
                    placeholder="vd: Nông sản khô"
                    placeholderTextColor={C.muted}
                  />

                  <Text style={s.label}>Chiều sâu hầm hàng (mm) *</Text>
                  <TextInput
                    style={[s.input, !canEdit && s.inputDisabled]}
                    editable={canEdit && !saving}
                    keyboardType="numeric"
                    value={depthStr}
                    onChangeText={(v) => {
                      setDepthStr(v);
                      if (v.trim() === '') setCalibrated(false);
                    }}
                    placeholder="vd: 10000"
                    placeholderTextColor={C.muted}
                  />

                  <Text style={s.label}>Thang đo tối đa cảm biến nước (mm) *</Text>
                  <TextInput
                    style={[s.input, !canEdit && s.inputDisabled]}
                    editable={canEdit && !saving}
                    keyboardType="numeric"
                    value={scaleStr}
                    onChangeText={(v) => {
                      setScaleStr(v);
                      if (v.trim() === '') setCalibrated(false);
                    }}
                    placeholder="vd: 3000"
                    placeholderTextColor={C.muted}
                  />

                  <View style={s.switchRow}>
                    <View style={{ flex: 1, paddingRight: 10 }}>
                      <Text style={s.switchLabel}>Cảm biến thực tế đã hiệu chuẩn</Text>
                      <Text style={s.switchHint}>
                        {isSim
                          ? 'Chế độ SIMULATION không dùng cờ hiệu chuẩn cảm biến thực tế.'
                          : hasValidCalibrationBasis
                          ? 'Đã có căn cứ chiều sâu hầm và thang đo cảm biến.'
                          : 'Phải nhập hợp lệ chiều sâu hầm và thang đo cảm biến trước khi bật.'}
                      </Text>
                    </View>
                    <Switch
                      value={isSim ? false : calibrated}
                      disabled={!canMarkCalibrated || saving}
                      onValueChange={setCalibrated}
                    />
                  </View>

                  <View style={s.threshBox}>
                    <Text style={s.threshTitle}>Ngưỡng hiệu lực từ Backend</Text>
                    <Text style={s.threshLine}>
                      • Nước ({cfg.effective_thresholds.water.unit}): WARNING ≥ {cfg.effective_thresholds.water.warning_mm} • CRITICAL ≥{' '}
                      {cfg.effective_thresholds.water.critical_mm ?? 'Chưa xác định'}
                    </Text>
                    <Text style={s.threshLine}>
                      • Nhiệt độ ({cfg.effective_thresholds.temperature.unit}): WARNING ≥ {cfg.effective_thresholds.temperature.warning} • CRITICAL ≥{' '}
                      {cfg.effective_thresholds.temperature.critical}
                    </Text>
                    <Text style={s.threshLine}>
                      • Độ ẩm ({cfg.effective_thresholds.humidity.unit}): WARNING ≥ {cfg.effective_thresholds.humidity.warning} • CRITICAL ≥{' '}
                      {cfg.effective_thresholds.humidity.critical}
                    </Text>
                    <Text style={s.refText}>
                      Nguồn tham chiếu: {cfg.effective_thresholds.water.reference.join(' • ')}
                    </Text>
                    <Text style={s.refText}>
                      Cập nhật: {cfg.updated_by ? `${cfg.updated_by}` : 'Chưa lưu cấu hình'}
                    </Text>
                  </View>
                </>
              )}
            </ScrollView>

            <View style={s.sheetFooter}>
              {canEdit && (
                <ActionBtn
                  label={saving ? 'Đang lưu cấu hình…' : 'Lưu cấu hình hầm hàng'}
                  onPress={handleSave}
                  tone="primary"
                  disabled={loading || saving || !cfg}
                />
              )}
            </View>
          </View>
        </View>
      </Modal>
    </>
  );
}

const s = StyleSheet.create({
  statusRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 10 },
  mutedText: { fontSize: 12, color: C.muted },
  warnBox: {
    backgroundColor: '#FFFBEB',
    borderColor: '#F59E0B',
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginBottom: 10,
  },
  warnTitle: { fontSize: 12, fontWeight: '700', color: '#92400E', marginBottom: 2 },
  warnBody: { fontSize: 11, color: '#78350F', lineHeight: 16 },
  errBox: { backgroundColor: '#FEF2F2', borderColor: C.red, borderWidth: 1, borderRadius: 8, padding: 10, marginBottom: 10 },
  errText: { fontSize: 12, color: C.red, fontWeight: '600' },
  okBox: { backgroundColor: '#ECFDF5', borderColor: C.green, borderWidth: 1, borderRadius: 8, padding: 10, marginBottom: 10 },
  okText: { fontSize: 12, color: '#065F46', fontWeight: '600' },
  alertList: { marginTop: 10, paddingTop: 8, borderTopWidth: 1, borderTopColor: C.border },
  alertItem: { fontSize: 11, color: C.text, marginBottom: 4 },
  backdrop: { flex: 1, backgroundColor: 'rgba(15, 32, 51, 0.55)', justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: C.panel,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    padding: 16,
    ...SHADOWS.card,
  },
  sheetHeader: { flexDirection: 'row', alignItems: 'center', marginBottom: 10, gap: 8 },
  sheetTitle: { fontSize: 16, fontWeight: '700', color: C.borderNavy },
  sheetSub: { fontSize: 11, color: C.muted, marginTop: 2 },
  closeBtn: { paddingHorizontal: 10, paddingVertical: 6, borderRadius: 6, backgroundColor: '#F1F5F9' },
  closeBtnText: { fontSize: 12, fontWeight: '600', color: C.borderNavy },
  metaText: { fontSize: 11, color: C.muted, marginBottom: 8, fontWeight: '600' },
  label: { fontSize: 12, fontWeight: '600', color: C.borderNavy, marginBottom: 4, marginTop: 8 },
  input: {
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    color: C.text,
    backgroundColor: '#FFFFFF',
  },
  inputDisabled: { backgroundColor: '#F1F5F9', color: C.muted },
  switchRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 8,
    padding: 10,
    marginTop: 10,
  },
  switchLabel: { fontSize: 12, fontWeight: '700', color: C.borderNavy },
  switchHint: { fontSize: 11, color: C.muted, marginTop: 2 },
  threshBox: {
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 8,
    padding: 10,
    marginTop: 10,
    marginBottom: 8,
  },
  threshTitle: { fontSize: 12, fontWeight: '700', color: C.borderNavy, marginBottom: 4 },
  threshLine: { fontSize: 11, color: C.text, marginBottom: 2 },
  refText: { fontSize: 10, color: C.muted, marginTop: 4 },
  sheetFooter: { marginTop: 10 },
});
