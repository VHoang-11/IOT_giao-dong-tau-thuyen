import type {
  ApiCargoAlert,
  ApiCargoConfig,
  ApiCargoConfigIn,
  ApiCargoStatus,
} from '../data/liveApi';

export type Route =
  | 'Login' | 'Register' | 'ForgotPassword' | 'Overview' | 'LiveMotion' | 'Alarms' | 'AlarmDetail'
  | 'VoyageReports' | 'ReportDetails' | 'More' | 'ControlCenter'
  | 'ReplayReview' | 'DeviceHealth' | 'ModelMonitor';

export type MainTab = 'Overview' | 'LiveMotion' | 'Alarms' | 'VoyageReports' | 'More';
export type Role = 'Operator' | 'Supervisor' | 'Admin';
export type Scenario = 'S0' | 'S0b' | 'S1' | 'S2' | 'S3' | 'H1' | 'OFFLINE' | 'UNKNOWN' | 'SENSOR_FAULT';
export type RFClass = 'NORMAL' | 'HIGH_ROLL' | 'PERSISTENT_OFFSET' | 'AMPLITUDE_GROWTH' | 'UNKNOWN' | 'FAULT';
export type AlarmLevel = 'NORMAL' | 'CAUTION' | 'WARNING' | 'CRITICAL' | 'UNKNOWN';
export type AlarmStatus = 'RAISED' | 'ACKED' | 'CLEARED';
export type CommandStatus = 'SENT' | 'DELIVERED' | 'APPLIED' | 'REJECTED' | 'TIMEOUT';
export type Connection = 'ONLINE' | 'OFFLINE' | 'UNKNOWN' | 'SENSOR_FAULT';

export interface Session {
  username: string;
  displayName: string;
  role: Role;
  demo: boolean;
}

export interface Vessel {
  id: string;
  name: string;
  imo?: string;
  sourceMode: 'SENSOR' | 'SIMULATION';
}

export interface Telemetry {
  device_id: string;
  boot_id: string;
  seq: number;
  t_sim_s: number;
  source_mode: 'SENSOR' | 'SIMULATION';
  synthetic: boolean;
  roll_deg: number | null;
  pitch_deg: number | null;
  rms_roll_deg: number | null;
  heel_offset_deg: number | null;
  trend_rms_deg_per_min: number | null;
  class_rf: RFClass;
  class_baseline_b: RFClass;
  mai: number | null;
  alarm_level: AlarmLevel;
  sensor_ok: boolean;
  model_version: string;
  config_version: number | null;
  connection: Connection;
  utc_time?: string;
}

export interface Alarm {
  id: string;
  title: string;
  level: Exclude<AlarmLevel, 'UNKNOWN'>;
  status: AlarmStatus;
  at: string;
  detail: string;
  peakVector?: string;
  anomalyIndex?: number;
  utcTime?: string;
  relativeTime?: string;
  muted?: boolean;
  review?: 'TRUE' | 'FALSE' | 'UNCERTAIN';
  notes?: string;
  /** Chỉ LIVE: khóa chính trên Backend và trạng thái ACK của thiết bị. */
  pk?: number;
  deviceAck?: string;
  /** Chỉ LIVE: mốc thời gian thật của vòng đời cảnh báo. */
  timeline?: { time: string; text: string; tone: 'trigger' | 'info' | 'ok' }[];
}

export interface Command {
  id: string;
  name: string;
  status: CommandStatus;
  at: string;
  detail: string;
  config_version: number | null;
  issued_by?: string;
  reason?: string;
  is_test_utility?: boolean;
}

export interface ZeroCalibration {
  roll_offset_deg: number;
  pitch_offset_deg: number;
  std_dev_roll: number;
  duration_s: number;
  calibrated_at: string;
  is_static: boolean;
}

export interface MotionSnapshot {
  snapshot_id: string;
  timestamp: string;
  window_s: number;
  sample_count: number;
  roll_min: number;
  roll_max: number;
  pitch_min: number;
  pitch_max: number;
  rms_roll_deg: number;
  mai: number;
  triggered_by: string;
  source_scenario: Scenario;
}

export interface DeviceConfig {
  profile: 'STANDARD' | 'SENSITIVE' | 'CONSERVATIVE';
  config_version: number;
  /** null = Backend/thiết bị không có tham số này (không suy đoán). */
  roll_warning_deg: number | null;
  roll_trip_deg: number | null;
  mai_alert_threshold: number | null;
  source_mode: 'SIMULATION' | 'SENSOR';
  timewarp: number | null;
  active_model: 'RF' | 'BASELINE_B' | null;
  scenario: Scenario;
  zero_calibration?: ZeroCalibration | null;
}

export interface Voyage {
  id: string;
  name: string;
  route: string;
  durationMinutes: number | null;
  durationHours: number | null;
  startTime: string;
  endTime: string;
  sourceMode: 'SIMULATION' | 'SENSOR';
  deviceId: string;
  modelVersion: string;
  configVersion: number | null;
  sampleCount: number | null;
  maxAbsRollDeg: number | null;
  rmsRollDeg: number | null;
  p95AbsRollDeg: number | null;
  maxAbsPitchDeg: number | null;
  rmsPitchDeg: number | null;
  maiMax: number | null;
  maiAvg: number | null;
  maiCautionMinutes: number | null;
  alarms: number | null;
  mttaSeconds: number | null;
  rfDistribution: {
    normalPct: number | null;
    highRollPct: number | null;
    persistentOffsetPct: number | null;
    amplitudeGrowthPct: number | null;
  };
  agreementPercent: number | null;
  /** Chỉ LIVE: số liệu chuyến đang chạy là tạm thời; chuyến chưa tải được số liệu. */
  provisional?: boolean;
  metricsLoaded?: boolean;
}

export interface ReplayPoint {
  seq: number;
  t_sim_s: number;
  roll: number;
  pitch: number;
  class_rf: RFClass;
  class_baseline_b: RFClass;
  mai: number | null;
  alarm_level: AlarmLevel;
  alarm_id?: string;
  source_mode: 'SIMULATION' | 'SENSOR';
  synthetic: boolean;
}

export interface DeviceHealth {
  sensor: 'OK' | 'FAULT' | 'UNKNOWN';
  sensorOk: boolean;
  /** null = thiết bị/Backend chưa báo giá trị này. */
  i2cErrors: number | null;
  lastI2cError?: string;
  rssiDbm: number | null;
  uptimeS: number | null;
  uptimeMinutes: number | null;
  freeHeapKb: number | null;
  minFreeHeapKb: number | null;
  heapFragmentationPct: number | null;
  inferenceMs: number | null;
  mqttReconnects: number | null;
  bufferUsed: number | null;
  bufferCapacity: number | null;
  bufferStatus: 'EMPTY' | 'BUFFERING' | 'OVERFLOW' | 'UNKNOWN';
  queueLatencyMs: number | null;
  lastPacketUtc: string;
  packetGapS: number | null;
  healthScore: number | null;
  healthStatus: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
  lastCalibratedAt?: string | null;
  lastCalibrationState?: string | null;
}

export interface FeatureItem {
  index: number;
  name: string;
  group: string;
  window_s: number;
  unit: string;
  description: string;
  value: number | null;
  status: 'VALID' | 'WARNING' | 'INVALID' | 'MISSING' | 'NOT_APPLICABLE';
  reason?: string;
  source?: string;
  displayName?: string;
}

export interface FeatureSummary {
  total: number;
  validCount: number;
  warningCount: number;
  invalidCount: number;
  missingCount: number;
  contractId: string;
  version: string;
  sourceExport: string;
}

export interface ModelInfo {
  active: string;
  activeModelId: 'RF' | 'BASELINE_B' | null;
  baseline: string;
  baselineModelId: 'RF' | 'BASELINE_B';
  version: string;
  algorithm: string | null;
  featuresCount: number | null;
  features: string[];
  featureItems?: FeatureItem[];
  featureSummary?: FeatureSummary;
  inferenceMs: number | null;
  flashKb: number | null;
  ramKb: number | null;
  agreementPercent: number | null;
  psi: number | null;
  psiStatus: string;
  concordanceBreakdown: {
    normal: number | null;
    highRoll: number | null;
    persistentOffset: number | null;
    amplitudeGrowth: number | null;
  };
  /** Chỉ LIVE: ghi chú từ Backend (vd. thiếu dữ liệu đồng thuận). */
  note?: string;
}

export type DataMode = 'mock' | 'live';

export interface LinkStatus {
  state: 'API_ERROR' | 'NO_DATA' | 'STALE' | 'SENSOR_FAULT' | 'ONLINE';
  label: string;
  ageS: number | null;
  error?: string;
}

export interface ActionResult {
  ok: boolean;
  message: string;
}

export interface LoginTarget {
  mode: DataMode;
  url: string;
}

export interface CargoLiveContext {
  status: ApiCargoStatus | null;
  statusError: string;
  alerts: ApiCargoAlert[];
  getConfig: (cargoId: string) => Promise<ApiCargoConfig>;
  saveConfig: (cargoId: string, body: ApiCargoConfigIn) => Promise<ApiCargoConfig>;
  onSaved: () => void;
}

export interface AppData {
  mode: DataMode;
  cargoLive?: CargoLiveContext | null;
  /** Chỉ LIVE: tình trạng kết nối Backend/thiết bị. */
  link: LinkStatus | null;
  vesselName: string;
  deviceId: string | null;
  firmware: string | null;
  bootId: string | null;
  /** Chuỗi roll/pitch gần nhất để vẽ biểu đồ (MOCK: sinh từ kịch bản, LIVE: telemetry thật). */
  getSeries: (count: number, endSeq?: number) => { roll: number[]; pitch: number[] };
  route: Route;
  session: Session | null;
  scenario: Scenario;
  telemetry: Telemetry;
  config: DeviceConfig;
  previousConfig: DeviceConfig | null;
  alarms: Alarm[];
  commands: Command[];
  voyage: Voyage;
  voyages: Voyage[];
  selectedVoyageId: string;
  health: DeviceHealth;
  model: ModelInfo;
  replaySeconds: number;
  replayIndex: number;
  replayPlaying: boolean;
  replaySpeed: number;
  replayPoints: ReplayPoint[];
  buzzerMuted: boolean;
  latestSnapshot?: MotionSnapshot | null;
}

export interface AppActions {
  go: (route: Route) => void;
  back: () => void;
  login: (username: string, password: string, target: LoginTarget) => Promise<ActionResult>;
  logout: () => void;
  setScenario: (scenario: Scenario) => void;
  selectAlarm: (id: string) => void;
  selectedAlarmId: string;
  ackAlarm: (id: string) => Promise<ActionResult>;
  muteAlarm: (id: string) => Promise<ActionResult>;
  toggleBuzzer: () => void;
  updateAlarmNote: (id: string, note: string) => ActionResult;
  reviewAlarm: (id: string, label: 'TRUE' | 'FALSE' | 'UNCERTAIN') => Promise<ActionResult>;
  sendCommand: (name: string, adminOnly?: boolean, argument?: string) => void;
  setReplaySeconds: (seconds: number) => void;
  setReplayPlaying: (playing: boolean) => void;
  selectVoyage: (id: string) => void;
  setReplayIndex: (index: number) => void;
  setReplaySpeed: (speed: number) => void;
}

export interface ScreenProps {
  data: AppData;
  actions: AppActions;
}

export const MAIN_TABS: MainTab[] = ['Overview', 'LiveMotion', 'Alarms', 'VoyageReports', 'More'];

export const TAB_LABELS: Record<MainTab, string> = {
  Overview: 'Home',
  LiveMotion: 'Motion',
  Alarms: 'Alarms',
  VoyageReports: 'Reports',
  More: 'More',
};
