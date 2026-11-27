// SVMG LIVE API client.
// All requests use the same-origin Nginx reverse proxy (/api -> FastAPI).
// Kiểu dữ liệu bám đúng OpenAPI của backend (/openapi.json, 39 paths). JWT chỉ nằm trong React state, không ghi log.

export type MotionClass = 'NORMAL' | 'HIGH_ROLL' | 'PERSISTENT_OFFSET' | 'AMPLITUDE_GROWTH' | 'UNKNOWN' | 'FAULT';
export type AlarmLevel = 'NORMAL' | 'CAUTION' | 'WARNING' | 'CRITICAL';
export type AlarmState = 'ACTIVE' | 'ACKED' | 'CLEARED';
export type AlarmLabel = 'TRUE_ALARM' | 'FALSE_ALARM' | 'UNCLEAR';
export type SourceMode = 'SENSOR' | 'SIMULATION';
export type CommandState = 'SENT' | 'DELIVERED' | 'APPLIED' | 'REJECTED' | 'TIMEOUT';
export type CommandName = 'set_profile' | 'set_threshold' | 'calibrate_zero' | 'mute_alarm' | 'start_voyage' | 'stop_voyage' | 'restart_device' | 'ack_alarm';

export interface LiveAuthResponse {
  access_token: string;
  token_type?: string;
  expires_in: number;
  username: string;
  role: string;
}

export interface LiveTelemetry {
  device_id: string;
  boot_id: string;
  seq: number;
  t_sim_s: number;
  source_mode: SourceMode;
  roll_deg: number;
  pitch_deg: number;
  rms_roll_deg: number | null;
  /** NGỪNG DÙNG: Motion Node không còn gửi các trường này; dữ liệu hầm hàng nay đến từ Cargo Node (CargoOut). */
  cargo_water_pct?: number | null;
  cargo_temp_c?: number | null;
  cargo_humidity_pct?: number | null;
  class_rf: MotionClass;
  class_baseline_b: MotionClass | null;
  mai: number | null;
  alarm_level: AlarmLevel;
  sensor_ok: boolean;
  server_rx_time: string;
}

/** Một bản ghi hầm hàng từ Cargo Node (ESP32 thứ 2). Giá trị không đọc được = null (không phải 0). */
export interface CargoOut {
  device_id: string; boot_id: string; seq: number; uptime_ms: number; source_mode: SourceMode; sensor_ok: boolean;
  cargo_water_pct: number | null; cargo_temp_c: number | null; cargo_humidity_pct: number | null; server_rx_time: string;
}
export interface DeviceOut {
  /** MOTION = tàu chính (ESP32 đo dao động); CARGO = mạch hầm hàng riêng, gắn vào tàu chính qua parent_device_id. */
  node_type?: 'MOTION' | 'CARGO'; parent_device_id?: string | null;
  device_id: string; name?: string | null; enabled?: boolean; source_mode: SourceMode; state: 'online' | 'offline';
  last_seen?: string | null; fw?: string | null; boot_id?: string | null; model_version?: string | null; config_version?: number | null;
}
export interface AlarmOut {
  id: number; alarm_id: string; device_id: string; boot_id: string; voyage_id?: string | null; state: AlarmState; level: AlarmLevel;
  max_level: AlarmLevel; motion_class?: MotionClass | null; source_mode: SourceMode; opened_at: string; acked_at?: string | null;
  acked_by?: string | null; cleared_at?: string | null; escalated: boolean; label?: AlarmLabel | null; labeled_by?: string | null;
  labeled_at?: string | null; time_to_ack_s: number | null;
  /** false = cảnh báo của lần khởi động trước (lịch sử; thiết bị không còn giữ). */
  boot_current?: boolean | null;
  /** ACK trên THIẾT BỊ, khác ACK người trực (acked_by). Chỉ CONFIRMED mới là thiết bị đã xác nhận. */
  device_ack?: { state: 'NOT_REQUESTED' | 'PENDING' | 'CONFIRMED' | 'APPLIED_UNCONFIRMED' | 'REJECTED' | 'TIMEOUT';
    cmd_id?: string | null; reason?: string | null; confirmed_at?: string | null } | null;
}
export interface AlarmStats {
  total: number; active: number; acked: number; cleared: number; escalated: number; mtta_s?: number | null; escalation_rate?: number | null;
  by_max_level: Record<string, number>; labeled?: number; by_label?: Record<string, number>; label_coverage?: number | null; false_alarm_rate?: number | null;
  open_previous_boot?: number;
}
export interface AckResult { alarm: AlarmOut; already_acked: boolean; device_ack?: string; device_ack_detail?: string | null; device_ack_cmd_id?: string | null }
export interface CommandOut {
  cmd_id: string; device_id: string; cmd: string; params?: Record<string, unknown> | null; ttl_s: number; issued_by: string; state: CommandState;
  reason?: string | null; created_at: string; delivered_at?: string | null; finished_at?: string | null; rtt_s: number | null;
}
export interface CommandStats {
  total: number; by_state: Record<string, number>; rtt_mean_s?: number | null; rtt_p95_s?: number | null; rtt_max_s?: number | null; timeout_rate?: number | null;
}
export interface ConfigOut {
  device_id: string; config_version: number; payload: Record<string, unknown>; created_by: string; created_at: string; applied: boolean; rejected_reason?: string | null;
}
export interface DeviceHealthOut {
  device_id: string; free_heap_bytes: number; min_free_heap_bytes?: number | null; uptime_ms: number; sensor_ok: boolean; i2c_errors?: number | null;
  inference_ms?: number | null; mqtt_reconnects?: number | null; buffer_used?: number | null; buffer_capacity?: number | null; server_rx_time: string;
  buffer_used_pct: number | null;
}
export interface DeviceHealthSummary {
  device_id: string; state: 'online' | 'offline'; source_mode: SourceMode; last_seen?: string | null; seconds_since_seen?: number | null; stale: boolean;
  latest?: DeviceHealthOut | null; last_calibrated_at?: string | null; last_calibration_state?: CommandState | null;
}
export interface VoyageOut {
  voyage_id: string; device_id: string; source_mode: SourceMode; status: 'ACTIVE' | 'ENDED'; started_by: string; started_at: string;
  ended_at?: string | null; ended_by?: string | null;
}
export interface Distribution { counts?: Record<string, number>; share?: Record<string, number> }
export interface ReportSummary {
  voyage: VoyageOut; provisional: boolean; generated_at: string; source_label: string; source_modes: string[]; first_sample_at?: string | null;
  last_sample_at?: string | null; duration_s?: number | null;
  /** Chất lượng nhận theo bằng chứng: seq dùng chung telemetry/event/health nên khoảng trống seq KHÔNG đồng nghĩa mất gói. */
  data_quality: { samples: number; receive_status?: 'VERIFIED' | 'NO_LOSS_EVIDENCE' | 'INSUFFICIENT_EVIDENCE' | 'NO_DATA';
    expected_samples?: number | null; missing_samples?: number | null; received_rate?: number | null; received_rate_lower_bound?: number | null;
    seq_span?: number; seq_gaps?: number; seq_used_by_events?: number; seq_telemetry_outside_voyage?: number;
    seq_gaps_health_timing?: number; seq_gaps_unclassified?: number; boots: number; sensor_fault_samples: number };
  motion: { samples_used: number; max_abs_roll_deg?: number | null; p95_abs_roll_deg?: number | null; mean_rms_roll_deg?: number | null; max_abs_pitch_deg?: number | null; max_abs_heel_offset_deg?: number | null };
  class_rf: Distribution; class_baseline_b: Distribution; rf_baseline_agreement_rate?: number | null; alarm_levels: Distribution; alarms: AlarmStats;
  false_alarms_per_hour?: number | null; commands: { total: number; by_state?: Record<string, number> }; notes: string[]; telemetry_rows: number;
  telemetry_csv_sha256: string; disclaimer?: string;
}
export interface ReplayTelemetry {
  boot_id: string; seq: number; t_sim_s: number; timewarp: number; server_rx_time: string; source_mode: SourceMode; sensor_ok: boolean;
  scenario_id?: string | null; roll_deg: number; pitch_deg: number; rms_roll_deg?: number | null; heel_offset_deg?: number | null;
  cargo_water_pct?: number | null; cargo_temp_c?: number | null; cargo_humidity_pct?: number | null;
  trend_rms_deg_per_min?: number | null; class_rf: MotionClass; class_baseline_b?: MotionClass | null; mai?: number | null; alarm_level: AlarmLevel;
  model_version: string; config_version: number;
}
export interface ReplayResponse {
  meta: { voyage_id: string; device_id: string; status: 'ACTIVE' | 'ENDED'; source_modes: string[]; total_samples: number; window_samples: number;
    boots: number; first_sample_at?: string | null; last_sample_at?: string | null; duration_wall_s?: number | null; t_sim_monotonic?: boolean | null; timewarps: number[] };
  telemetry: ReplayTelemetry[];
  alarm_events: { boot_id: string; seq: number; alarm_id: string; level: AlarmLevel; prev_level?: AlarmLevel | null; motion_class?: MotionClass | null; t_sim_s: number; acked_by?: string | null; server_rx_time: string }[];
  alarms: AlarmOut[]; commands: { cmd_id: string; cmd: string; state: CommandState; issued_by: string; reason?: string | null; created_at: string; finished_at?: string | null }[];
  limit: number; truncated: boolean; next_cursor?: string | null;
}
export interface ClassAgreement { rf_total: number; matched: number; rate?: number | null }
/** Đồng thuận RF – Baseline B: chỉ cặp mà CẢ HAI có lớp phân loại hợp lệ; UNKNOWN/FAULT bị loại; không trộn SENSOR/SIMULATION. */
export interface AgreementStats {
  device_id: string; voyage_id?: string | null; source_label: string; source_modes: string[];
  status?: 'OK' | 'INSUFFICIENT_DATA' | 'MIXED_SOURCES'; samples_considered: number; excluded_sensor_fault: number;
  excluded_unclassified?: number; unclassified_labels?: Record<string, number>;
  matched: number; agreement_rate?: number | null; by_rf_class: Record<string, ClassAgreement>;
  by_source_mode?: Record<string, { samples_considered: number; matched: number; agreement_rate?: number | null; by_rf_class: Record<string, ClassAgreement> }>;
  limit: number; first_sample_at?: string | null; last_sample_at?: string | null; notes: string[];
}
export interface DriftStatus {
  device_id: string; window_hours: number; window_samples: number; source_modes: string[]; available: boolean; reason?: string | null;
  source?: 'unavailable' | 'ml'; expected_features: string[]; feature_contract_available?: boolean; feature_schema_version?: string | null;
  feature_count?: number | null; device_feature_schema_version?: string | null; device_feature_count?: number | null; schema_match?: boolean | null;
  features?: { feature_index: number; feature_name: string; psi: number; flagged: boolean }[]; flagged_count?: number | null;
}

/** Lỗi HTTP giữ mã trạng thái để giao diện phân biệt 401 (hết phiên), 403 (không đủ quyền), mất kết nối Backend. */
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function detail(response: Response): Promise<string> {
  try {
    const body = await response.json() as { detail?: unknown };
    if (typeof body.detail === 'string') return body.detail;
  } catch { /* phản hồi không phải JSON */ }
  return `HTTP ${response.status}`;
}

export async function apiRequest<T>(token: string, path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, { ...init, cache: 'no-store',
      headers: { ...(init.body ? { 'Content-Type': 'application/json' } : {}), ...init.headers, Authorization: `Bearer ${token}` } });
  } catch {
    throw new ApiError(0, 'Không kết nối được Backend (mạng hoặc máy chủ không phản hồi).');
  }
  if (!response.ok) {
    const msg = response.status === 401 ? 'Phiên đăng nhập LIVE đã hết hạn hoặc không hợp lệ.'
      : response.status === 403 ? 'Tài khoản không đủ quyền cho thao tác này.' : await detail(response);
    throw new ApiError(response.status, msg);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

/** Tải tệp (CSV/PDF) có JWT rồi lưu bằng Blob; không đưa token vào URL. */
export async function apiDownload(token: string, path: string, filename: string): Promise<void> {
  let response: Response;
  try { response = await fetch(path, { headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' }); }
  catch { throw new ApiError(0, 'Không kết nối được Backend.'); }
  if (!response.ok) throw new ApiError(response.status, await detail(response));
  const url = URL.createObjectURL(await response.blob());
  const a = document.createElement('a'); a.href = url; a.download = filename; a.click(); URL.revokeObjectURL(url);
}

export async function loginBackend(
  username: string,
  password: string
): Promise<LiveAuthResponse> {
  const response = await fetch('/api/v1/auth/login', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({ username, password }),
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(
      response.status === 401
        ? 'Tên đăng nhập hoặc mật khẩu Backend không đúng.'
        : `Đăng nhập Backend thất bại (HTTP ${response.status}).`
    );
  }

  const data = (await response.json()) as LiveAuthResponse;

  if (!data.access_token) {
    throw new Error('Backend không trả về JWT.');
  }

  return data;
}

export async function fetchLiveTelemetry(
  token: string,
  deviceId = 'vessel-demo-01',
  limit = 60
): Promise<LiveTelemetry[]> {
  const data = await apiRequest<unknown>(token, `/api/v1/devices/${encodeURIComponent(deviceId)}/telemetry?limit=${limit}`);
  if (!Array.isArray(data)) {
    throw new Error('Định dạng telemetry không hợp lệ.');
  }
  return data as LiveTelemetry[];
}
