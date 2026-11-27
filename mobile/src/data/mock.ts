import {
  Alarm,
  AlarmLevel,
  DeviceHealth,
  ModelInfo,
  ReplayPoint,
  RFClass,
  Role,
  Scenario,
  Session,
  Telemetry,
  Voyage,
  Vessel,
} from '../types/domain';
import {
  FEATURE_NAME_LIST,
  mapToFeatureItems,
  TOTAL_FEATURES,
} from '../featureRegistry';

export const DEMO_VESSEL: Vessel = {
  id: 'vessel-demo-01',
  name: 'Tàu MV SVMG-01',
  imo: 'IMO-9876543',
  sourceMode: 'SIMULATION',
};

export function hashPassword(password: string): string {
  let h1 = 0xdeadbeef ^ 0;
  let h2 = 0x41c6ce57 ^ 0;
  for (let i = 0; i < password.length; i++) {
    const ch = password.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return 'h_' + (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16);
}

export const DEMO_USERS: Record<string, { passwordHash: string; role: Role; displayName: string }> = {
  operator: { passwordHash: hashPassword('demo123'), role: 'Operator', displayName: 'Sĩ quan trực ca' },
  supervisor: { passwordHash: hashPassword('demo123'), role: 'Supervisor', displayName: 'Giám sát viên' },
  admin: { passwordHash: hashPassword('demo123'), role: 'Admin', displayName: 'Quản trị viên' },
};

export function mockLogin(username: string, password: string): Session | null {
  const key = username.trim().toLowerCase();
  const account = DEMO_USERS[key];
  return account && account.passwordHash === hashPassword(password)
    ? { username: key, role: account.role, displayName: account.displayName, demo: true }
    : null;
}

export function mockRegister(
  username: string,
  password: string,
  displayName: string
): { success: boolean; message: string; error?: string } {
  const u = username.trim().toLowerCase();
  if (!u || !password) {
    return { success: false, message: '', error: 'Vui lòng điền đầy đủ Tên đăng nhập và Mật khẩu.' };
  }
  if (DEMO_USERS[u]) {
    return { success: false, message: '', error: `Tài khoản "${u}" đã tồn tại trong danh bạ hệ thống.` };
  }
  DEMO_USERS[u] = {
    passwordHash: hashPassword(password),
    role: 'Operator', // Quyền cố định theo Bảng 3.1
    displayName: displayName.trim() || u,
  };
  return {
    success: true,
    message: `[AUTH_SERVICE_PENDING] Đăng ký tài khoản nội bộ "${u}" thành công ở chế độ mô phỏng. Quyền hạn: Sĩ quan trực ca (Bảng 3.1). Dịch vụ xác thực qua máy chủ Backend đang chờ cấu hình, tài khoản có thể đăng nhập ngay trong phiên thử nghiệm này.`,
  };
}

export function mockForgotPassword(identifier: string): { success: boolean; message: string; error?: string } {
  const id = identifier.trim();
  if (!id) {
    return { success: false, message: '', error: 'Vui lòng nhập Tên đăng nhập hoặc Email sĩ quan.' };
  }
  return {
    success: true,
    message: `[AUTH_SERVICE_PENDING] Đã tiếp nhận yêu cầu đặt lại mật khẩu cho "${id}". Do dịch vụ xác thực Backend / SMTP chưa được cấu hình ở môi trường mô phỏng, email liên kết đặt lại mật khẩu thực tế chưa được gửi. Vui lòng liên hệ Quản trị viên để được hỗ trợ.`,
  };
}

const CLASS_BY_SCENARIO: Record<Scenario, RFClass> = {
  S0: 'NORMAL',
  S0b: 'NORMAL',
  S1: 'HIGH_ROLL',
  S2: 'PERSISTENT_OFFSET',
  S3: 'AMPLITUDE_GROWTH',
  H1: 'HIGH_ROLL',
  OFFLINE: 'UNKNOWN',
  UNKNOWN: 'UNKNOWN',
  SENSOR_FAULT: 'FAULT',
};

export const SCENARIOS: { id: Scenario; label: string; desc: string }[] = [
  { id: 'S0', label: 'Biển êm', desc: 'Roll < 3.5°, dao động điều hòa ổn định' },
  { id: 'S0b', label: 'Nghiêng rồi hồi phục', desc: 'Gió giật nghiêng tạm thời và tự cân bằng' },
  { id: 'S1', label: 'Lắc ngang lớn', desc: 'Biên độ roll > 12° do sóng ngang' },
  { id: 'S2', label: 'Nghiêng lệch kéo dài', desc: 'Lệch tâm 8.2° do xô lệch hàng hoặc dằn' },
  { id: 'S3', label: 'Biên độ tăng dần', desc: 'Cộng hưởng tham số, biên độ mở rộng' },
  { id: 'H1', label: 'Kết hợp nguy hiểm', desc: 'Lắc lớn kết hợp nghiêng góc tĩnh' },
  { id: 'OFFLINE', label: 'Mất kết nối', desc: 'Mất tín hiệu viễn trắc từ thiết bị' },
  { id: 'SENSOR_FAULT', label: 'Lỗi cảm biến', desc: 'Lỗi truyền thông I2C MPU6050' },
];

export function waveform(s: Scenario, t: number) {
  const base = Math.sin(t * 0.32);
  const growth = Math.min(15, 2 + (t % 90) * 0.16);
  const roll =
    s === 'S0'
      ? base * 2.2
      : s === 'S0b'
      ? (t % 120 < 25 ? 4.8 : 0) + base * 2.3
      : s === 'S1'
      ? base * 13.5
      : s === 'S2'
      ? 8.2 + base * 1.8
      : s === 'S3'
      ? base * growth
      : s === 'H1'
      ? 6.0 + base * 14.2
      : 0;
  const pitch = Math.sin(t * 0.23 + 0.7) * 2.6;
  return { roll: +roll.toFixed(2), pitch: +pitch.toFixed(2) };
}

export function createTelemetry(scenario: Scenario, tick: number): Telemetry {
  const invalid = scenario === 'OFFLINE' || scenario === 'UNKNOWN' || scenario === 'SENSOR_FAULT';
  const faulty = scenario === 'SENSOR_FAULT';
  const { roll, pitch } = waveform(scenario === 'SENSOR_FAULT' ? 'S0' : scenario, tick);

  const maiBase: Record<Scenario, number> = {
    S0: 14,
    S0b: 24,
    S1: 73,
    S2: 65,
    S3: 88,
    H1: 94,
    OFFLINE: 0,
    UNKNOWN: 0,
    SENSOR_FAULT: 0,
  };

  const level: Telemetry['alarm_level'] = invalid
    ? scenario === 'SENSOR_FAULT'
      ? 'CAUTION'
      : 'UNKNOWN'
    : scenario === 'S0' || scenario === 'S0b'
    ? 'NORMAL'
    : scenario === 'S2'
    ? 'WARNING'
    : scenario === 'S3' || scenario === 'H1'
    ? 'CRITICAL'
    : 'WARNING';

  const now = new Date();
  const utcString = `${String(now.getUTCHours()).padStart(2, '0')}:${String(
    now.getUTCMinutes()
  ).padStart(2, '0')}:${String(now.getUTCSeconds()).padStart(2, '0')} UTC`;

  return {
    device_id: 'vessel-demo-01',
    boot_id: 'mock-boot-01',
    seq: tick,
    t_sim_s: tick * 5,
    source_mode: 'SIMULATION',
    synthetic: true,
    roll_deg: invalid ? null : roll,
    pitch_deg: invalid ? null : pitch,
    rms_roll_deg: invalid ? null : +(Math.abs(roll) * 0.72).toFixed(2),
    heel_offset_deg: scenario === 'S2' ? 8.2 : 0,
    trend_rms_deg_per_min: scenario === 'S3' ? 1.15 : 0,
    class_rf: CLASS_BY_SCENARIO[scenario],
    class_baseline_b: faulty ? 'UNKNOWN' : scenario === 'S0b' ? 'HIGH_ROLL' : CLASS_BY_SCENARIO[scenario],
    mai: invalid ? null : maiBase[scenario],
    alarm_level: level,
    sensor_ok: !invalid,
    model_version: 'RF-DEMO-v1',
    config_version: 7,
    connection:
      scenario === 'OFFLINE'
        ? 'OFFLINE'
        : scenario === 'SENSOR_FAULT'
        ? 'SENSOR_FAULT'
        : scenario === 'UNKNOWN'
        ? 'UNKNOWN'
        : 'ONLINE',
    utc_time: utcString,
  };
}

export const INITIAL_ALARMS: Alarm[] = [
  {
    id: 'ALM-8492',
    title: 'Biên độ dao động tăng dần',
    level: 'CRITICAL',
    status: 'RAISED',
    at: '14:28:12 UTC',
    detail: 'Biên độ lắc ngang tăng liên tục > 2.1° mỗi chu kỳ, vượt ngưỡng cộng hưởng an toàn.',
    peakVector: '24.2° Mạn trái',
    anomalyIndex: 0.88,
    utcTime: '14:28:12 UTC',
    relativeTime: '3 phút trước',
    notes: 'Đã đổi hướng 15° sang mạn trái',
  },
  {
    id: 'ALM-8488',
    title: 'Nghiêng lệch kéo dài',
    level: 'WARNING',
    status: 'ACKED',
    at: '14:15:03 UTC',
    detail: 'Góc nghiêng tĩnh lệch > 6.5° mạn trái duy trì trên 180 giây. Kiểm tra xô lệch hàng hoặc dằn tàu.',
    peakVector: '+6.8° Mạn trái',
    anomalyIndex: 0.65,
    utcTime: '14:15:03 UTC',
    relativeTime: '16 phút trước',
    notes: 'Đang kích hoạt bơm dằn số 2',
  },
  {
    id: 'ALM-8450',
    title: 'Lắc ngang mạnh',
    level: 'WARNING',
    status: 'RAISED',
    at: '14:02:30 UTC',
    detail: 'Gia tốc ngang tăng đột biến khi gặp sóng ngang mạn phải.',
    peakVector: '15.8° Mạn phải',
    anomalyIndex: 0.72,
    utcTime: '14:02:30 UTC',
    relativeTime: '28 phút trước',
  },
  {
    id: 'ALM-8441',
    title: 'Dao động bất thường mức cảnh giác',
    level: 'CAUTION',
    status: 'CLEARED',
    at: '13:42:50 UTC',
    detail: 'Biên độ dao động tăng nhẹ tạm thời và đã tự ổn định về ngưỡng bình thường.',
    peakVector: '11.4° Mạn phải',
    anomalyIndex: 0.38,
    utcTime: '13:42:50 UTC',
    relativeTime: '48 phút trước',
    notes: 'Đã qua vùng sóng ngang',
  },
];

export const MOCK_VOYAGES: Voyage[] = [
  {
    id: 'V-2026-001',
    name: 'Hải trình mẫu 01 (Chuyến kiểm thử T11/T15)',
    route: 'Cửa sổ giám sát 10 phút (S0 → S1 → S2 → S3 → S0)',
    durationMinutes: 10,
    durationHours: 10 / 60,
    startTime: '2026-11-12T08:00:00Z',
    endTime: '2026-11-12T08:10:00Z',
    sourceMode: 'SIMULATION',
    deviceId: 'vessel-demo-01',
    modelVersion: 'RF-DEMO-v1',
    configVersion: 7,
    sampleCount: 121,
    maxAbsRollDeg: 14.85,
    rmsRollDeg: 7.08,
    p95AbsRollDeg: 13.36,
    maxAbsPitchDeg: 2.60,
    rmsPitchDeg: 1.84,
    maiMax: 88,
    maiAvg: 46.2,
    maiCautionMinutes: 3.2,
    alarms: 4,
    mttaSeconds: 72,
    rfDistribution: {
      normalPct: 38.0,
      highRollPct: 24.8,
      persistentOffsetPct: 20.7,
      amplitudeGrowthPct: 16.5,
    },
    agreementPercent: 96.2,
  },
  {
    id: 'V-2026-002',
    name: 'Hải trình mẫu 02 (Biển êm)',
    route: 'Hải Phòng → Đà Nẵng (Trạng thái bình thường)',
    durationMinutes: 10,
    durationHours: 10 / 60,
    startTime: '2026-11-12T06:00:00Z',
    endTime: '2026-11-12T06:10:00Z',
    sourceMode: 'SIMULATION',
    deviceId: 'vessel-demo-01',
    modelVersion: 'RF-DEMO-v1',
    configVersion: 7,
    sampleCount: 121,
    maxAbsRollDeg: 2.20,
    rmsRollDeg: 1.56,
    p95AbsRollDeg: 2.15,
    maxAbsPitchDeg: 2.58,
    rmsPitchDeg: 1.80,
    maiMax: 14,
    maiAvg: 12.5,
    maiCautionMinutes: 0.0,
    alarms: 0,
    mttaSeconds: 0,
    rfDistribution: {
      normalPct: 100.0,
      highRollPct: 0.0,
      persistentOffsetPct: 0.0,
      amplitudeGrowthPct: 0.0,
    },
    agreementPercent: 100.0,
  },
  {
    id: 'V-2026-003',
    name: 'Hải trình mẫu 03 (Sóng lớn kết hợp)',
    route: 'Vũng Tàu → Singapore (Thời tiết xấu)',
    durationMinutes: 10,
    durationHours: 10 / 60,
    startTime: '2026-11-11T22:00:00Z',
    endTime: '2026-11-11T22:10:00Z',
    sourceMode: 'SIMULATION',
    deviceId: 'vessel-demo-01',
    modelVersion: 'RF-DEMO-v1',
    configVersion: 7,
    sampleCount: 121,
    maxAbsRollDeg: 20.20,
    rmsRollDeg: 10.42,
    p95AbsRollDeg: 18.60,
    maxAbsPitchDeg: 2.60,
    rmsPitchDeg: 1.84,
    maiMax: 94,
    maiAvg: 68.4,
    maiCautionMinutes: 6.5,
    alarms: 5,
    mttaSeconds: 65,
    rfDistribution: {
      normalPct: 15.0,
      highRollPct: 55.0,
      persistentOffsetPct: 10.0,
      amplitudeGrowthPct: 20.0,
    },
    agreementPercent: 92.5,
  },
];

export const DEMO_VOYAGE: Voyage = MOCK_VOYAGES[0];

export const REPLAY_POINTS: ReplayPoint[] = Array.from({ length: 121 }, (_, i) => {
  const s: Scenario = i < 20 ? 'S0' : i < 40 ? 'S1' : i < 65 ? 'S2' : i < 95 ? 'S3' : 'S0';
  const { roll, pitch } = waveform(s, i);
  const class_rf: RFClass =
    i < 20
      ? 'NORMAL'
      : i < 40
      ? 'HIGH_ROLL'
      : i < 65
      ? 'PERSISTENT_OFFSET'
      : i < 95
      ? 'AMPLITUDE_GROWTH'
      : 'NORMAL';
  const class_baseline_b: RFClass =
    i < 20
      ? 'NORMAL'
      : i < 40
      ? 'HIGH_ROLL'
      : i < 65
      ? 'PERSISTENT_OFFSET'
      : i < 95
      ? 'HIGH_ROLL'
      : 'NORMAL';
  const mai = i < 20 ? 14 : i < 40 ? 74 : i < 65 ? 65 : i < 95 ? 88 : 12;
  const alarm_level: AlarmLevel =
    i < 20 ? 'NORMAL' : i < 40 ? 'WARNING' : i < 65 ? 'WARNING' : i < 95 ? 'CRITICAL' : 'NORMAL';
  const alarm_id =
    i === 12
      ? 'ALM-8441'
      : i === 30
      ? 'ALM-8450'
      : i === 64
      ? 'ALM-8488'
      : i === 85
      ? 'ALM-8492'
      : undefined;

  return {
    seq: i,
    t_sim_s: i * 5,
    roll,
    pitch,
    class_rf,
    class_baseline_b,
    mai,
    alarm_level,
    alarm_id,
    source_mode: 'SIMULATION' as const,
    synthetic: true as const,
  };
});

export const DEMO_HEALTH: DeviceHealth = {
  sensor: 'OK',
  sensorOk: true,
  i2cErrors: 0,
  lastI2cError: undefined,
  rssiDbm: -62,
  uptimeS: 16500,
  uptimeMinutes: 275,
  freeHeapKb: 151,
  minFreeHeapKb: 114,
  heapFragmentationPct: 6.2,
  inferenceMs: 12.4,
  mqttReconnects: 0,
  bufferUsed: 0,
  bufferCapacity: 1000,
  bufferStatus: 'EMPTY',
  queueLatencyMs: 14,
  lastPacketUtc: 'Vừa nhận (< 2s)',
  packetGapS: 1.2,
  healthScore: 100,
  healthStatus: 'HEALTHY',
};

export function computeHealth(scenario: Scenario, tick: number): DeviceHealth {
  const isOffline = scenario === 'OFFLINE';
  const isSensorFault = scenario === 'SENSOR_FAULT';
  const isUnknown = scenario === 'UNKNOWN';

  const sensor: DeviceHealth['sensor'] = isSensorFault ? 'FAULT' : isOffline || isUnknown ? 'UNKNOWN' : 'OK';
  const sensorOk = sensor === 'OK';
  const i2cErrors = isSensorFault ? 3 : 0;
  const lastI2cError = isSensorFault ? 'I2C NACK tại 0x68 (MPU6050 timeout)' : undefined;
  const rssiDbm = isOffline ? null : isSensorFault ? -65 : -62;
  const uptimeS = 16500 + tick * 5;
  const uptimeMinutes = Math.round(uptimeS / 60);
  const freeHeapKb = isOffline ? 146 : isSensorFault ? 150 : 151;
  const minFreeHeapKb = 114;
  const heapFragmentationPct = isOffline ? 8.4 : 6.2;
  const inferenceMs = isOffline || isSensorFault ? 0 : 12.4;
  const mqttReconnects = isOffline ? 2 : 0;
  const bufferUsed = isOffline ? Math.min(1000, 24 + (tick % 50)) : 0;
  const bufferCapacity = 1000;
  const bufferStatus: DeviceHealth['bufferStatus'] = isOffline ? 'BUFFERING' : 'EMPTY';
  const queueLatencyMs = isOffline ? 450 : 14;
  const lastPacketUtc = isOffline ? 'Mất tín hiệu (> 30s)' : 'Vừa nhận (< 2s)';
  const packetGapS = isOffline ? 38 : 1.2;
  const healthScore = isOffline ? 15 : isSensorFault ? 45 : 100;
  const healthStatus: DeviceHealth['healthStatus'] = isOffline
    ? 'CRITICAL'
    : isSensorFault
    ? 'DEGRADED'
    : 'HEALTHY';

  return {
    sensor,
    sensorOk,
    i2cErrors,
    lastI2cError,
    rssiDbm,
    uptimeS,
    uptimeMinutes,
    freeHeapKb,
    minFreeHeapKb,
    heapFragmentationPct,
    inferenceMs,
    mqttReconnects,
    bufferUsed,
    bufferCapacity,
    bufferStatus,
    queueLatencyMs,
    lastPacketUtc,
    packetGapS,
    healthScore,
    healthStatus,
  };
}

const initialMapped = mapToFeatureItems();

export const DEMO_MODEL: ModelInfo = {
  active: 'Random Forest (Mô hình chính)',
  activeModelId: 'RF',
  baseline: 'Baseline B (Mô hình đối chiếu)',
  baselineModelId: 'BASELINE_B',
  version: 'RF-DEMO-v1',
  algorithm: 'Tập hợp 10 cây quyết định (TinyML mã C)',
  featuresCount: TOTAL_FEATURES,
  features: FEATURE_NAME_LIST,
  featureItems: initialMapped.items,
  featureSummary: initialMapped.summary,
  inferenceMs: 12.4,
  flashKb: 42.6,
  ramKb: 8.2,
  agreementPercent: 96.2,
  psi: 0.038,
  psiStatus: 'Ổn định (< 0.10 - Không lệch phân phối)',
  concordanceBreakdown: {
    normal: 100.0,
    highRoll: 92.4,
    persistentOffset: 98.1,
    amplitudeGrowth: 94.3,
  },
};

export function computeModelInfo(
  activeModelId: 'RF' | 'BASELINE_B',
  scenario?: Scenario,
  sensorOk?: boolean
): ModelInfo {
  const isRf = activeModelId === 'RF';
  const isOffline = scenario === 'OFFLINE' || scenario === 'UNKNOWN';
  const isFault = scenario === 'SENSOR_FAULT' || sensorOk === false;
  const mapped = mapToFeatureItems(null, {
    isOffline,
    isSensorOk: !isFault,
    source: 'SAMPLE',
  });

  return {
    active: isRf ? 'Random Forest (Mô hình chính)' : 'Baseline B (Quy tắc ngưỡng)',
    activeModelId,
    baseline: isRf ? 'Baseline B (Mô hình đối chiếu)' : 'Random Forest (Mô hình đối chiếu)',
    baselineModelId: isRf ? 'BASELINE_B' : 'RF',
    version: isRf ? 'RF-DEMO-v1' : 'Baseline-B-v1.1',
    algorithm: isRf ? 'Tập hợp 10 cây quyết định (TinyML mã C)' : 'Quy chuẩn động học IMO (Ngưỡng tức thời)',
    featuresCount: TOTAL_FEATURES,
    features: FEATURE_NAME_LIST,
    featureItems: mapped.items,
    featureSummary: mapped.summary,
    inferenceMs: isRf ? 12.4 : 1.8,
    flashKb: isRf ? 42.6 : 8.4,
    ramKb: isRf ? 8.2 : 1.5,
    agreementPercent: 96.2,
    psi: isOffline || isFault ? null : 0.038,
    psiStatus: isOffline || isFault ? 'Không khả dụng khi mất dữ liệu' : 'Ổn định (< 0.10 - Không lệch phân phối)',
    concordanceBreakdown: {
      normal: 100.0,
      highRoll: 92.4,
      persistentOffset: 98.1,
      amplitudeGrowth: 94.3,
    },
  };
}

export function fakeWavePoints(
  scenario: Scenario,
  tick: number,
  count = 48
): { roll: number[]; pitch: number[] } {
  const roll: number[] = [];
  const pitch: number[] = [];
  for (let i = 0; i < count; i++) {
    const t = tick - count + i;
    const { roll: r, pitch: p } = waveform(scenario, t);
    roll.push(r);
    pitch.push(p);
  }
  return { roll, pitch };
}
