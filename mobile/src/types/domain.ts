export type Route =
  | 'Login' | 'Register' | 'ForgotPassword' | 'Overview' | 'LiveMotion' | 'Alarms' | 'AlarmDetail'
  | 'VoyageReports' | 'ReportDetails' | 'More' | 'ControlCenter'
  | 'ReplayReview' | 'DeviceHealth' | 'ModelMonitor';

export type MainTab = 'Overview' | 'LiveMotion' | 'Alarms' | 'More';
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
  demo: true;
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
  config_version: number;
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
}

export interface Command {
  id: string;
  name: string;
  status: CommandStatus;
  at: string;
  detail: string;
  config_version: number;
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
  roll_warning_deg: number;
  roll_trip_deg: number;
  mai_alert_threshold: number;
  source_mode: 'SIMULATION' | 'SENSOR';
  timewarp: number;
  active_model: 'RF' | 'BASELINE_B';
  scenario: Scenario;
  zero_calibration?: ZeroCalibration | null;
}

export interface Voyage {
  id: string;
  name: string;
  route: string;
  durationMinutes: number;
  durationHours: number;
  startTime: string;
  endTime: string;
  sourceMode: 'SIMULATION' | 'SENSOR';
  deviceId: string;
  modelVersion: string;
  configVersion: number;
  sampleCount: number;
  maxAbsRollDeg: number;
  rmsRollDeg: number;
  p95AbsRollDeg: number;
  maxAbsPitchDeg: number;
  rmsPitchDeg: number;
  maiMax: number;
  maiAvg: number;
  maiCautionMinutes: number;
  alarms: number;
  mttaSeconds: number;
  rfDistribution: {
    normalPct: number;
    highRollPct: number;
    persistentOffsetPct: number;
    amplitudeGrowthPct: number;
  };
  agreementPercent: number;
}

export interface ReplayPoint {
  seq: number;
  t_sim_s: number;
  roll: number;
  pitch: number;
  class_rf: RFClass;
  class_baseline_b: RFClass;
  mai: number;
  alarm_level: AlarmLevel;
  alarm_id?: string;
  source_mode: 'SIMULATION';
  synthetic: true;
}

export interface DeviceHealth {
  sensor: 'OK' | 'FAULT' | 'UNKNOWN';
  sensorOk: boolean;
  i2cErrors: number;
  lastI2cError?: string;
  rssiDbm: number | null;
  uptimeS: number;
  uptimeMinutes: number;
  freeHeapKb: number;
  minFreeHeapKb: number;
  heapFragmentationPct: number;
  inferenceMs: number;
  mqttReconnects: number;
  bufferUsed: number;
  bufferCapacity: number;
  bufferStatus: 'EMPTY' | 'BUFFERING' | 'OVERFLOW';
  queueLatencyMs: number;
  lastPacketUtc: string;
  packetGapS: number;
  healthScore: number;
  healthStatus: 'HEALTHY' | 'DEGRADED' | 'CRITICAL';
}

export interface FeatureItem {
  index: number;
  name: string;
  displayName?: string;
  group: string;
  window_s: number;
  unit: string;
  description: string;
  value: number | null;
  status: 'VALID' | 'WARNING' | 'INVALID' | 'MISSING' | 'NOT_APPLICABLE';
  reason?: string;
  source?: string;
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
  activeModelId: 'RF' | 'BASELINE_B';
  baseline: string;
  baselineModelId: 'RF' | 'BASELINE_B';
  version: string;
  algorithm: string;
  featuresCount: number;
  features: string[];
  featureItems?: FeatureItem[];
  featureSummary?: FeatureSummary;
  inferenceMs: number;
  flashKb: number;
  ramKb: number;
  agreementPercent: number;
  psi: number | null;
  psiStatus: string;
  concordanceBreakdown: {
    normal: number;
    highRoll: number;
    persistentOffset: number;
    amplitudeGrowth: number;
  };
}

export interface AppData {
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
  login: (username: string, password: string) => boolean;
  logout: () => void;
  setScenario: (scenario: Scenario) => void;
  selectAlarm: (id: string) => void;
  selectedAlarmId: string;
  ackAlarm: (id: string) => void;
  muteAlarm: (id: string) => void;
  toggleBuzzer: () => void;
  updateAlarmNote: (id: string, note: string) => void;
  reviewAlarm: (id: string, label: 'TRUE' | 'FALSE' | 'UNCERTAIN') => void;
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

export const MAIN_TABS: MainTab[] = ['Overview', 'LiveMotion', 'Alarms', 'More'];

export const TAB_LABELS: Record<MainTab, string> = {
  Overview: 'Tổng quan',
  LiveMotion: 'Chuyển động',
  Alarms: 'Cảnh báo',
  More: 'Thêm',
};
