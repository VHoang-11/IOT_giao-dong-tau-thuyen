/**
 * Chuyển phản hồi Backend → kiểu dữ liệu của giao diện mobile.
 * Quy tắc: giá trị Backend không có thì để null/'—', KHÔNG điền số giả và KHÔNG lấy từ mock.
 */
import {
  Alarm,
  AlarmLevel,
  Command,
  CommandStatus,
  Connection,
  DeviceConfig,
  DeviceHealth,
  LinkStatus,
  ModelInfo,
  ReplayPoint,
  RFClass,
  Role,
  Telemetry,
  Voyage,
} from '../types/domain';
import {
  ApiAgreement,
  ApiAlarm,
  ApiCommand,
  ApiConfig,
  ApiDevice,
  ApiDrift,
  ApiHealthSummary,
  ApiReplay,
  ApiReportSummary,
  ApiTelemetry,
  ApiVoyage,
} from './liveApi';

/** ISO từ backend có múi giờ; nếu thiếu thì coi là UTC. */
export function parseTime(iso?: string | null): number {
  if (!iso) return NaN;
  return Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(iso) ? iso : `${iso}Z`);
}

export function formatUtc(iso?: string | null): string {
  const t = parseTime(iso);
  if (!Number.isFinite(t)) return '—';
  const d = new Date(t);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getUTCHours())}:${p(d.getUTCMinutes())}:${p(d.getUTCSeconds())} UTC`;
}

export function formatDateTimeUtc(iso?: string | null): string {
  const t = parseTime(iso);
  if (!Number.isFinite(t)) return '—';
  const d = new Date(t);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(d.getUTCDate())} ${p(d.getUTCHours())}:${p(
    d.getUTCMinutes()
  )} UTC`;
}

export function mapRole(role: string): Role {
  const r = role.toUpperCase();
  if (r === 'ADMIN') return 'Admin';
  if (r === 'SUPERVISOR') return 'Supervisor';
  return 'Operator';
}

// ---------------------------------------------------------------------------------------------
// Kết nối / độ tươi dữ liệu

export interface LinkInfo extends LinkStatus {
  latest: ApiTelemetry | null;
  /** Mẫu mới nhất chỉ khi dữ liệu còn tươi; null khi mất kết nối/cũ (không coi là thời gian thực). */
  fresh: ApiTelemetry | null;
}

/** Ngưỡng cũ = max(30 s, 3 × chu kỳ gửi trung vị quan sát được) — cùng quy tắc với dashboard web. */
export function computeLink(
  rows: ApiTelemetry[] | null,
  apiError: string,
  healthStale: boolean | null,
  now: number
): LinkInfo {
  const latest = rows && rows.length ? rows[0] : null;
  const gaps: number[] = [];
  for (let i = 0; rows && i < Math.min(rows.length - 1, 20); i++) {
    if (rows[i].boot_id !== rows[i + 1].boot_id) break;
    const g = (parseTime(rows[i].server_rx_time) - parseTime(rows[i + 1].server_rx_time)) / 1000;
    if (Number.isFinite(g) && g > 0) gaps.push(g);
  }
  gaps.sort((a, b) => a - b);
  const staleAfterS = Math.max(30, 3 * (gaps.length ? gaps[Math.floor(gaps.length / 2)] : 0));
  const t = parseTime(latest?.server_rx_time);
  const ageS = Number.isFinite(t) ? Math.max(0, Math.round((now - t) / 1000)) : null;

  if (apiError) {
    return { state: 'API_ERROR', label: 'MẤT KẾT NỐI BACKEND', ageS, error: apiError, latest, fresh: null };
  }
  if (!latest) {
    return { state: 'NO_DATA', label: 'CHƯA CÓ TELEMETRY', ageS, latest, fresh: null };
  }
  if (ageS === null || ageS > staleAfterS || healthStale === true) {
    return {
      state: 'STALE',
      label: `THIẾT BỊ OFFLINE / DỮ LIỆU CŨ (${ageS ?? '?'}s)`,
      ageS,
      latest,
      fresh: null,
    };
  }
  if (!latest.sensor_ok) {
    return { state: 'SENSOR_FAULT', label: 'LỖI CẢM BIẾN (sensor_ok=false)', ageS, latest, fresh: latest };
  }
  return { state: 'ONLINE', label: '● TRỰC TUYẾN (LIVE)', ageS, latest, fresh: latest };
}

// ---------------------------------------------------------------------------------------------
// Telemetry

function toRf(c: string | null | undefined): RFClass {
  switch (c) {
    case 'NORMAL':
    case 'HIGH_ROLL':
    case 'PERSISTENT_OFFSET':
    case 'AMPLITUDE_GROWTH':
    case 'FAULT':
      return c;
    default:
      return 'UNKNOWN';
  }
}

function toLevel(l: string | null | undefined): AlarmLevel {
  switch (l) {
    case 'NORMAL':
    case 'CAUTION':
    case 'WARNING':
    case 'CRITICAL':
      return l;
    default:
      return 'UNKNOWN';
  }
}

function connectionOf(link: LinkInfo): Connection {
  switch (link.state) {
    case 'ONLINE':
      return 'ONLINE';
    case 'SENSOR_FAULT':
      return 'SENSOR_FAULT';
    case 'API_ERROR':
    case 'NO_DATA':
      return 'UNKNOWN';
    default:
      return 'OFFLINE';
  }
}

/**
 * Góc/MAI chỉ hiển thị khi dữ liệu còn tươi và cảm biến tốt (như dashboard web): ngược lại là null → "—".
 * Cấp cảnh báo của mẫu cũ cũng không được coi là trạng thái hiện tại.
 */
export function mapTelemetry(link: LinkInfo, device: ApiDevice | null): Telemetry {
  const sample = link.latest;
  const connection = connectionOf(link);
  const modelVersion = device?.model_version ?? '—';
  if (!sample) {
    return {
      device_id: device?.device_id ?? '—',
      boot_id: device?.boot_id ?? '—',
      seq: 0,
      t_sim_s: 0,
      source_mode: device?.source_mode ?? 'SIMULATION',
      synthetic: device?.source_mode !== 'SENSOR',
      roll_deg: null,
      pitch_deg: null,
      rms_roll_deg: null,
      heel_offset_deg: null,
      trend_rms_deg_per_min: null,
      class_rf: 'UNKNOWN',
      class_baseline_b: 'UNKNOWN',
      mai: null,
      alarm_level: 'UNKNOWN',
      sensor_ok: false,
      model_version: modelVersion,
      config_version: device?.config_version ?? null,
      connection,
    };
  }
  const usable = link.state === 'ONLINE';
  return {
    device_id: sample.device_id,
    boot_id: sample.boot_id,
    seq: sample.seq,
    t_sim_s: sample.t_sim_s,
    source_mode: sample.source_mode,
    synthetic: sample.source_mode !== 'SENSOR',
    roll_deg: usable ? sample.roll_deg : null,
    pitch_deg: usable ? sample.pitch_deg : null,
    rms_roll_deg: usable ? sample.rms_roll_deg : null,
    heel_offset_deg: null,
    trend_rms_deg_per_min: null,
    class_rf: usable ? toRf(sample.class_rf) : 'UNKNOWN',
    class_baseline_b: usable ? toRf(sample.class_baseline_b) : 'UNKNOWN',
    mai: usable ? sample.mai : null,
    alarm_level: usable ? toLevel(sample.alarm_level) : 'UNKNOWN',
    sensor_ok: link.state === 'ONLINE',
    model_version: modelVersion,
    config_version: device?.config_version ?? null,
    connection,
    utc_time: formatUtc(sample.server_rx_time),
  };
}

/** Chuỗi roll/pitch từ telemetry thật (API trả mới nhất trước) — chỉ lấy cùng một lần khởi động. */
export function buildSeries(rows: ApiTelemetry[] | null) {
  return (count: number, endSeq?: number): { roll: number[]; pitch: number[] } => {
    if (!rows || !rows.length) return { roll: [], pitch: [] };
    const boot = rows[0].boot_id;
    const same = rows.filter((r) => r.boot_id === boot && (endSeq === undefined || r.seq <= endSeq));
    const slice = same.slice(0, count).reverse();
    return { roll: slice.map((r) => r.roll_deg), pitch: slice.map((r) => r.pitch_deg) };
  };
}

// ---------------------------------------------------------------------------------------------
// Alarms

function alarmStatus(s: ApiAlarm['state']): Alarm['status'] {
  return s === 'ACTIVE' ? 'RAISED' : s;
}

function reviewOf(label: ApiAlarm['label']): Alarm['review'] {
  if (label === 'TRUE_ALARM') return 'TRUE';
  if (label === 'FALSE_ALARM') return 'FALSE';
  if (label === 'UNCLEAR') return 'UNCERTAIN';
  return undefined;
}

export function mapAlarm(a: ApiAlarm): Alarm {
  const cls = a.motion_class ?? 'UNKNOWN';
  const parts = [
    `Nguồn ${a.source_mode}`,
    `Lớp RF: ${cls}`,
    a.max_level !== a.level ? `Mức cao nhất: ${a.max_level}` : null,
    a.escalated ? 'Đã leo thang (quá hạn ACK)' : null,
    a.acked_by ? `ACK bởi ${a.acked_by}` : null,
    a.time_to_ack_s !== null ? `Thời gian tới ACK: ${Math.round(a.time_to_ack_s)}s` : null,
    a.cleared_at ? `Giải tỏa lúc ${formatUtc(a.cleared_at)}` : null,
    a.boot_current === false ? 'Thuộc lần khởi động trước của thiết bị (lịch sử)' : null,
  ].filter(Boolean);
  const level = a.level === 'NORMAL' && a.state !== 'CLEARED' ? a.max_level : a.level;
  return {
    id: String(a.id),
    pk: a.id,
    title: `${a.alarm_id} — ${cls}`,
    level,
    status: alarmStatus(a.state),
    at: formatUtc(a.opened_at),
    utcTime: formatUtc(a.opened_at),
    detail: parts.join(' • '),
    review: reviewOf(a.label),
    timeline: [
      { time: formatUtc(a.opened_at), text: `Mở cảnh báo ${a.alarm_id} (mức ${a.level}, lớp RF ${cls})`, tone: 'trigger' as const },
      ...(a.max_level !== a.level
        ? [{ time: '—', text: `Mức cao nhất đạt được: ${a.max_level}`, tone: 'info' as const }]
        : []),
      ...(a.escalated ? [{ time: '—', text: 'Đã leo thang do quá hạn ACK', tone: 'info' as const }] : []),
      ...(a.acked_at
        ? [{ time: formatUtc(a.acked_at), text: `ACK bởi ${a.acked_by ?? '—'}`, tone: 'info' as const }]
        : []),
      ...(a.cleared_at ? [{ time: formatUtc(a.cleared_at), text: 'Cảnh báo được giải tỏa (CLEARED)', tone: 'ok' as const }] : []),
    ],
  };
}

// ---------------------------------------------------------------------------------------------
// Commands / config

function describeCommand(c: ApiCommand): string {
  switch (c.state) {
    case 'SENT':
      return 'Đã phát lên MQTT, chờ thiết bị nhận.';
    case 'DELIVERED':
      return 'Thiết bị đã nhận lệnh, đang xử lý.';
    case 'APPLIED':
      return 'Thiết bị đã thực thi (ACK APPLIED).';
    case 'REJECTED':
      return `Thiết bị/Backend từ chối${c.reason ? `: ${c.reason}` : '.'}`;
    case 'TIMEOUT':
      return `Quá hạn TTL ${c.ttl_s}s không có ACK${c.reason ? ` (${c.reason})` : ''}.`;
  }
}

export function mapCommand(c: ApiCommand, configVersion: number | null): Command {
  const params = c.params && Object.keys(c.params).length ? ` (${Object.values(c.params).join(', ')})` : '';
  return {
    id: c.cmd_id,
    name: `${c.cmd}${params}`,
    status: c.state as CommandStatus,
    at: formatUtc(c.created_at),
    detail: describeCommand(c),
    config_version: configVersion,
    issued_by: c.issued_by,
    reason: c.reason ?? undefined,
  };
}

const PROFILES = ['STANDARD', 'SENSITIVE', 'CONSERVATIVE'] as const;

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function configFrom(c: ApiConfig | null, device: ApiDevice | null): DeviceConfig {
  const p = c?.payload ?? {};
  const profile = PROFILES.find((x) => x === p.profile) ?? 'STANDARD';
  const maiCaution = num(p.mai_caution);
  return {
    profile,
    config_version: c?.config_version ?? device?.config_version ?? 0,
    // Backend chỉ có phi_hard_deg (ngưỡng roll cứng); không có ngưỡng "warning" riêng → null, không bịa.
    roll_warning_deg: null,
    roll_trip_deg: num(p.phi_hard_deg),
    mai_alert_threshold: maiCaution === null ? null : maiCaution / 100,
    source_mode: device?.source_mode ?? 'SIMULATION',
    timewarp: null,
    active_model: p.primary_model === 'RF' || p.primary_model === 'BASELINE_B' ? p.primary_model : null,
    scenario: 'UNKNOWN',
  };
}

/** Cấu hình hiện hành = phiên bản cao nhất đã APPLIED (nếu chưa có thì phiên bản cao nhất). Bản trước = APPLIED liền trước. */
export function mapConfigs(
  configs: ApiConfig[] | null,
  device: ApiDevice | null
): { config: DeviceConfig; previous: DeviceConfig | null; pendingVersion: number | null } {
  const list = [...(configs ?? [])].sort((a, b) => b.config_version - a.config_version);
  const applied = list.filter((c) => c.applied);
  const current = applied[0] ?? list[0] ?? null;
  const prev = applied.find((c) => current && c.config_version < current.config_version) ?? null;
  const newest = list[0] ?? null;
  const pendingVersion = newest && current && newest.config_version > current.config_version && !newest.applied
    ? newest.config_version
    : null;
  return {
    config: configFrom(current, device),
    previous: prev ? configFrom(prev, device) : null,
    pendingVersion,
  };
}

// ---------------------------------------------------------------------------------------------
// Health / model

function kb(bytes?: number | null): number | null {
  return typeof bytes === 'number' ? Math.round((bytes / 1024) * 10) / 10 : null;
}

export function mapHealth(h: ApiHealthSummary | null, link: LinkInfo): DeviceHealth {
  const l = h?.latest ?? null;
  const used = l?.buffer_used ?? null;
  const cap = l?.buffer_capacity ?? null;
  const sensorOk = l ? l.sensor_ok : link.latest ? link.latest.sensor_ok : false;
  const stale = h?.stale === true || link.state === 'STALE';
  let healthStatus: DeviceHealth['healthStatus'] = 'HEALTHY';
  if (link.state === 'API_ERROR' || link.state === 'NO_DATA' || stale || h?.state === 'offline') healthStatus = 'CRITICAL';
  else if (!sensorOk || (l?.i2c_errors ?? 0) > 0) healthStatus = 'DEGRADED';
  return {
    sensor: l || link.latest ? (sensorOk ? 'OK' : 'FAULT') : 'UNKNOWN',
    sensorOk,
    i2cErrors: l?.i2c_errors ?? null,
    rssiDbm: null, // Backend/thiết bị không báo RSSI
    uptimeS: l ? Math.round(l.uptime_ms / 1000) : null,
    uptimeMinutes: l ? Math.round(l.uptime_ms / 60000) : null,
    freeHeapKb: l ? kb(l.free_heap_bytes) : null,
    minFreeHeapKb: kb(l?.min_free_heap_bytes),
    heapFragmentationPct: null,
    inferenceMs: l?.inference_ms ?? null,
    mqttReconnects: l?.mqtt_reconnects ?? null,
    bufferUsed: used,
    bufferCapacity: cap,
    bufferStatus:
      used === null || cap === null ? 'UNKNOWN' : used >= cap && cap > 0 ? 'OVERFLOW' : used > 0 ? 'BUFFERING' : 'EMPTY',
    queueLatencyMs: null,
    lastPacketUtc: formatUtc(h?.last_seen ?? link.latest?.server_rx_time),
    packetGapS: h?.seconds_since_seen !== undefined && h.seconds_since_seen !== null ? Math.round(h.seconds_since_seen) : link.ageS,
    healthScore: null, // Backend không tính điểm sức khỏe tổng hợp
    healthStatus,
    lastCalibratedAt: h?.last_calibrated_at ?? null,
    lastCalibrationState: h?.last_calibration_state ?? null,
  };
}

export function mapModel(
  device: ApiDevice | null,
  config: DeviceConfig,
  agreement: ApiAgreement | null,
  drift: ApiDrift | null,
  inferenceMs: number | null
): ModelInfo {
  const rate = agreement?.agreement_rate;
  const classRate = (k: string): number | null => {
    const r = agreement?.by_rf_class?.[k]?.rate;
    return typeof r === 'number' ? Math.round(r * 1000) / 10 : null;
  };
  const note =
    agreement && agreement.status && agreement.status !== 'OK'
      ? agreement.status === 'MIXED_SOURCES'
        ? 'Dữ liệu trộn SENSOR và SIMULATION nên Backend không gộp tỉ lệ đồng thuận.'
        : 'Chưa đủ dữ liệu để đánh giá đồng thuận (cần cả RF và Baseline B có lớp phân loại hợp lệ).'
      : undefined;
  const features = drift?.expected_features ?? [];
  return {
    active: config.active_model === 'RF' ? 'Random Forest' : config.active_model === 'BASELINE_B' ? 'Baseline B' : '—',
    activeModelId: config.active_model,
    baseline: 'Baseline B',
    baselineModelId: 'BASELINE_B',
    version: device?.model_version ?? '—',
    algorithm: null,
    featuresCount: drift?.feature_count ?? (features.length || null),
    features,
    inferenceMs,
    flashKb: null,
    ramKb: null,
    agreementPercent: typeof rate === 'number' ? Math.round(rate * 1000) / 10 : null,
    psi: null,
    psiStatus: drift?.available ? 'Có dữ liệu drift' : drift?.reason ?? 'Backend chưa cung cấp drift PSI',
    concordanceBreakdown: {
      normal: classRate('NORMAL'),
      highRoll: classRate('HIGH_ROLL'),
      persistentOffset: classRate('PERSISTENT_OFFSET'),
      amplitudeGrowth: classRate('AMPLITUDE_GROWTH'),
    },
    note,
  };
}

// ---------------------------------------------------------------------------------------------
// Voyages / replay

/** Backend chỉ liệt kê các lớp có mẫu: có phân bố mà thiếu lớp = 0%; chưa có phân bố (chưa có mẫu) = null. */
const pct = (share: Record<string, number> | undefined, key: string): number | null => {
  if (!share || Object.keys(share).length === 0) return null;
  return typeof share[key] === 'number' ? Math.round(share[key] * 1000) / 10 : 0;
};

export function mapVoyage(
  v: ApiVoyage,
  summary: ApiReportSummary | null,
  device: ApiDevice | null,
  configVersion: number | null
): Voyage {
  const s = summary && summary.voyage.voyage_id === v.voyage_id ? summary : null;
  const startMs = parseTime(v.started_at);
  const endMs = v.ended_at ? parseTime(v.ended_at) : NaN;
  const durS = s?.duration_s ?? (Number.isFinite(startMs) && Number.isFinite(endMs) ? (endMs - startMs) / 1000 : null);
  const share = s?.class_rf?.share;
  return {
    id: v.voyage_id,
    name: `Chuyến ${v.voyage_id}`,
    route: `Thiết bị ${v.device_id} • ${v.status === 'ACTIVE' ? 'ĐANG CHẠY' : 'ĐÃ KẾT THÚC'} • bắt đầu bởi ${v.started_by}`,
    durationMinutes: durS === null ? null : Math.round(durS / 60),
    durationHours: durS === null ? null : Math.round((durS / 3600) * 100) / 100,
    startTime: formatDateTimeUtc(v.started_at),
    endTime: v.ended_at ? formatDateTimeUtc(v.ended_at) : 'Đang chạy',
    sourceMode: v.source_mode,
    deviceId: v.device_id,
    modelVersion: device?.model_version ?? '—',
    configVersion,
    sampleCount: s ? s.data_quality.samples : null,
    maxAbsRollDeg: s?.motion.max_abs_roll_deg ?? null,
    rmsRollDeg: s?.motion.mean_rms_roll_deg ?? null,
    p95AbsRollDeg: s?.motion.p95_abs_roll_deg ?? null,
    maxAbsPitchDeg: s?.motion.max_abs_pitch_deg ?? null,
    rmsPitchDeg: null, // Backend không tổng hợp RMS pitch
    maiMax: null,
    maiAvg: null,
    maiCautionMinutes: null,
    alarms: s ? s.alarms.total : null,
    mttaSeconds: s?.alarms.mtta_s ?? null,
    rfDistribution: {
      normalPct: pct(share, 'NORMAL'),
      highRollPct: pct(share, 'HIGH_ROLL'),
      persistentOffsetPct: pct(share, 'PERSISTENT_OFFSET'),
      amplitudeGrowthPct: pct(share, 'AMPLITUDE_GROWTH'),
    },
    agreementPercent:
      typeof s?.rf_baseline_agreement_rate === 'number' ? Math.round(s.rf_baseline_agreement_rate * 1000) / 10 : null,
    provisional: s?.provisional ?? v.status === 'ACTIVE',
    metricsLoaded: s !== null,
  };
}

export function mapReplay(r: ApiReplay | null): ReplayPoint[] {
  if (!r) return [];
  const alarmBySeq = new Map<string, string>();
  for (const e of r.alarm_events) alarmBySeq.set(`${e.boot_id}:${e.seq}`, e.alarm_id);
  return r.telemetry
    .filter((t) => t.sensor_ok)
    .map((t) => ({
      seq: t.seq,
      t_sim_s: t.t_sim_s,
      roll: t.roll_deg,
      pitch: t.pitch_deg,
      class_rf: toRf(t.class_rf),
      class_baseline_b: toRf(t.class_baseline_b),
      mai: t.mai ?? null,
      alarm_level: toLevel(t.alarm_level),
      alarm_id: alarmBySeq.get(`${t.boot_id}:${t.seq}`),
      source_mode: t.source_mode,
      synthetic: t.source_mode !== 'SENSOR',
    }));
}

/** Chưa có chuyến đi nào trên Backend: mọi số liệu để trống (không dùng chuyến mock). */
export function noVoyage(deviceId: string | null): Voyage {
  return {
    id: '—',
    name: 'Chưa có chuyến đi',
    route: deviceId ? `Thiết bị ${deviceId}: Backend chưa có chuyến đi nào` : 'Chưa có thiết bị',
    durationMinutes: null,
    durationHours: null,
    startTime: '—',
    endTime: '—',
    sourceMode: 'SIMULATION',
    deviceId: deviceId ?? '—',
    modelVersion: '—',
    configVersion: null,
    sampleCount: null,
    maxAbsRollDeg: null,
    rmsRollDeg: null,
    p95AbsRollDeg: null,
    maxAbsPitchDeg: null,
    rmsPitchDeg: null,
    maiMax: null,
    maiAvg: null,
    maiCautionMinutes: null,
    alarms: null,
    mttaSeconds: null,
    rfDistribution: { normalPct: null, highRollPct: null, persistentOffsetPct: null, amplitudeGrowthPct: null },
    agreementPercent: null,
    metricsLoaded: false,
  };
}
