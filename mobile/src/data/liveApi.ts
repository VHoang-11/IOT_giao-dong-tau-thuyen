/**
 * Client REST cho Backend SVMG (FastAPI). Kiểu dữ liệu bám contracts/openapi.yaml và frontend/src/api.ts.
 * JWT chỉ giữ trong bộ nhớ (state của App), không ghi đĩa, không ghi log.
 * Không có dữ liệu giả: lỗi mạng/HTTP được ném lên cho UI hiển thị, không thay bằng MOCK.
 */

export type MotionClass = 'NORMAL' | 'HIGH_ROLL' | 'PERSISTENT_OFFSET' | 'AMPLITUDE_GROWTH' | 'UNKNOWN' | 'FAULT';
export type ApiAlarmLevel = 'NORMAL' | 'CAUTION' | 'WARNING' | 'CRITICAL';
export type ApiAlarmState = 'ACTIVE' | 'ACKED' | 'CLEARED';
export type ApiAlarmLabel = 'TRUE_ALARM' | 'FALSE_ALARM' | 'UNCLEAR';
export type ApiSourceMode = 'SENSOR' | 'SIMULATION';
export type ApiCommandState = 'SENT' | 'DELIVERED' | 'APPLIED' | 'REJECTED' | 'TIMEOUT';

export interface ApiTokenOut {
  access_token: string;
  token_type?: string;
  expires_in: number;
  username: string;
  role: string;
}

export interface ApiTelemetry {
  device_id: string;
  boot_id: string;
  seq: number;
  t_sim_s: number;
  source_mode: ApiSourceMode;
  roll_deg: number;
  pitch_deg: number;
  rms_roll_deg: number | null;
  class_rf: MotionClass;
  class_baseline_b: MotionClass | null;
  mai: number | null;
  alarm_level: ApiAlarmLevel;
  sensor_ok: boolean;
  server_rx_time: string;
}

export interface ApiDevice {
  /** CARGO = mạch hầm hàng riêng (không phải tàu chính). */
  node_type?: 'MOTION' | 'CARGO';
  parent_device_id?: string | null;
  device_id: string;
  name?: string | null;
  enabled?: boolean;
  source_mode: ApiSourceMode;
  state: 'online' | 'offline';
  last_seen?: string | null;
  fw?: string | null;
  boot_id?: string | null;
  model_version?: string | null;
  config_version?: number | null;
}

export interface ApiAlarm {
  id: number;
  alarm_id: string;
  device_id: string;
  boot_id: string;
  voyage_id?: string | null;
  state: ApiAlarmState;
  level: ApiAlarmLevel;
  max_level: ApiAlarmLevel;
  motion_class?: MotionClass | null;
  source_mode: ApiSourceMode;
  opened_at: string;
  acked_at?: string | null;
  acked_by?: string | null;
  cleared_at?: string | null;
  escalated: boolean;
  label?: ApiAlarmLabel | null;
  time_to_ack_s: number | null;
  boot_current?: boolean | null;
}

export interface ApiAckResult {
  alarm: ApiAlarm;
  already_acked: boolean;
  device_ack?: string;
  device_ack_detail?: string | null;
}

export interface ApiCommand {
  cmd_id: string;
  device_id: string;
  cmd: string;
  params?: Record<string, unknown> | null;
  ttl_s: number;
  issued_by: string;
  state: ApiCommandState;
  reason?: string | null;
  created_at: string;
  delivered_at?: string | null;
  finished_at?: string | null;
}

export interface ApiConfig {
  device_id: string;
  config_version: number;
  payload: Record<string, unknown>;
  created_by: string;
  created_at: string;
  applied: boolean;
  rejected_reason?: string | null;
}

export interface ApiDeviceHealth {
  device_id: string;
  free_heap_bytes: number;
  min_free_heap_bytes?: number | null;
  uptime_ms: number;
  sensor_ok: boolean;
  i2c_errors?: number | null;
  inference_ms?: number | null;
  mqtt_reconnects?: number | null;
  buffer_used?: number | null;
  buffer_capacity?: number | null;
  server_rx_time: string;
  buffer_used_pct: number | null;
}

export interface ApiHealthSummary {
  device_id: string;
  state: 'online' | 'offline';
  source_mode: ApiSourceMode;
  last_seen?: string | null;
  seconds_since_seen?: number | null;
  stale: boolean;
  latest?: ApiDeviceHealth | null;
  last_calibrated_at?: string | null;
  last_calibration_state?: ApiCommandState | null;
}

export interface ApiVoyage {
  voyage_id: string;
  device_id: string;
  source_mode: ApiSourceMode;
  status: 'ACTIVE' | 'ENDED';
  started_by: string;
  started_at: string;
  ended_at?: string | null;
  ended_by?: string | null;
}

export interface ApiDistribution {
  counts?: Record<string, number>;
  share?: Record<string, number>;
}

export interface ApiReportSummary {
  voyage: ApiVoyage;
  provisional: boolean;
  generated_at: string;
  source_label: string;
  first_sample_at?: string | null;
  last_sample_at?: string | null;
  duration_s?: number | null;
  data_quality: { samples: number; boots: number; sensor_fault_samples: number };
  motion: {
    samples_used: number;
    max_abs_roll_deg?: number | null;
    p95_abs_roll_deg?: number | null;
    mean_rms_roll_deg?: number | null;
    max_abs_pitch_deg?: number | null;
    max_abs_heel_offset_deg?: number | null;
  };
  class_rf: ApiDistribution;
  class_baseline_b: ApiDistribution;
  rf_baseline_agreement_rate?: number | null;
  alarm_levels: ApiDistribution;
  alarms: { total: number; mtta_s?: number | null };
  commands: { total: number };
  notes: string[];
  telemetry_rows: number;
}

export interface ApiReplayTelemetry {
  boot_id: string;
  seq: number;
  t_sim_s: number;
  server_rx_time: string;
  source_mode: ApiSourceMode;
  sensor_ok: boolean;
  roll_deg: number;
  pitch_deg: number;
  class_rf: MotionClass;
  class_baseline_b?: MotionClass | null;
  mai?: number | null;
  alarm_level: ApiAlarmLevel;
  model_version: string;
  config_version: number;
}

export interface ApiReplay {
  meta: { voyage_id: string; total_samples: number; window_samples: number };
  telemetry: ApiReplayTelemetry[];
  alarm_events: { seq: number; alarm_id: string; level: ApiAlarmLevel; boot_id: string }[];
  truncated: boolean;
  next_cursor?: string | null;
}

export interface ApiAgreement {
  status?: 'OK' | 'INSUFFICIENT_DATA' | 'MIXED_SOURCES';
  samples_considered: number;
  matched: number;
  agreement_rate?: number | null;
  by_rf_class: Record<string, { rf_total: number; matched: number; rate?: number | null }>;
  notes: string[];
}

export interface ApiDrift {
  available: boolean;
  reason?: string | null;
  expected_features: string[];
  feature_count?: number | null;
  features?: { feature_index: number; feature_name: string; psi: number; flagged: boolean }[];
}

/** Lỗi HTTP giữ mã trạng thái: 0 = không kết nối được, 401 = hết phiên, 403 = thiếu quyền. */
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const TIMEOUT_MS = 12000;

export function normalizeBaseUrl(raw: string): string {
  let url = raw.trim().replace(/\/+$/, '');
  if (url && !/^https?:\/\//i.test(url)) url = `http://${url}`;
  return url;
}

async function errorDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail) && body.detail.length) {
      const first = body.detail[0] as { msg?: string };
      if (first?.msg) return first.msg;
    }
  } catch {
    /* phản hồi không phải JSON */
  }
  return `HTTP ${response.status}`;
}

async function request<T>(
  baseUrl: string,
  path: string,
  init: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, ...rest } = init;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...rest,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(rest.headers as Record<string, string> | undefined),
      },
    });
  } catch {
    throw new ApiError(0, 'Không kết nối được Backend (sai địa chỉ, mạng hoặc máy chủ không phản hồi).');
  } finally {
    clearTimeout(timer);
  }
  if (!response.ok) {
    const message =
      response.status === 401
        ? token
          ? 'Phiên đăng nhập đã hết hạn hoặc không hợp lệ.'
          : 'Tên đăng nhập hoặc mật khẩu Backend không đúng.'
        : response.status === 403
        ? 'Tài khoản không đủ quyền cho thao tác này.'
        : await errorDetail(response);
    throw new ApiError(response.status, message);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

const q = encodeURIComponent;

export function createApi(baseUrl: string, token: string) {
  const get = <T>(path: string) => request<T>(baseUrl, path, { token });
  const send = <T>(method: string, path: string, body?: unknown) =>
    request<T>(baseUrl, path, {
      token,
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });

  return {
    devices: () => get<ApiDevice[]>('/api/v1/devices'),
    telemetry: (deviceId: string, limit = 120) =>
      get<ApiTelemetry[]>(`/api/v1/devices/${q(deviceId)}/telemetry?limit=${limit}`),
    alarms: (deviceId: string, limit = 100) =>
      get<ApiAlarm[]>(`/api/v1/alarms?device_id=${q(deviceId)}&limit=${limit}`),
    health: () => get<ApiHealthSummary[]>('/api/v1/health/devices'),
    commands: (limit = 50) => get<ApiCommand[]>(`/api/v1/commands?limit=${limit}`),
    configs: (deviceId: string) => get<ApiConfig[]>(`/api/v1/devices/${q(deviceId)}/config`),
    voyages: (deviceId: string) => get<ApiVoyage[]>(`/api/v1/voyages?device_id=${q(deviceId)}&limit=50`),
    voyageSummary: (voyageId: string) => get<ApiReportSummary>(`/api/v1/voyages/${q(voyageId)}/summary`),
    replay: (voyageId: string, limit = 2000) =>
      get<ApiReplay>(`/api/v1/voyages/${q(voyageId)}/replay?limit=${limit}`),
    agreement: (deviceId: string) => get<ApiAgreement>(`/api/v1/monitor/agreement?device_id=${q(deviceId)}`),
    drift: (deviceId: string) => get<ApiDrift>(`/api/v1/monitor/drift?device_id=${q(deviceId)}`),

    ackAlarm: (pk: number) => send<ApiAckResult>('POST', `/api/v1/alarms/${pk}/ack`),
    labelAlarm: (pk: number, label: ApiAlarmLabel) =>
      send<ApiAlarm>('PUT', `/api/v1/alarms/${pk}/label`, { label }),
    sendCommand: (deviceId: string, cmd: string, params: Record<string, unknown> = {}) =>
      send<ApiCommand>('POST', `/api/v1/devices/${q(deviceId)}/commands`, { cmd, params }),
    getCommand: (cmdId: string) => get<ApiCommand>(`/api/v1/commands/${q(cmdId)}`),
    rollbackConfig: (deviceId: string) =>
      send<ApiConfig>('POST', `/api/v1/devices/${q(deviceId)}/config/rollback`, {}),
    putConfig: (deviceId: string, body: Record<string, unknown>) =>
      send<ApiConfig>('PUT', `/api/v1/devices/${q(deviceId)}/config`, body),
  };
}

export type LiveApi = ReturnType<typeof createApi>;

export async function loginBackend(baseUrl: string, username: string, password: string): Promise<ApiTokenOut> {
  const data = await request<ApiTokenOut>(baseUrl, '/api/v1/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: `username=${q(username)}&password=${q(password)}`,
  });
  if (!data.access_token) throw new ApiError(500, 'Backend không trả về JWT.');
  return data;
}
