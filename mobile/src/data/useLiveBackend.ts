/**
 * Lớp dữ liệu LIVE: polling các endpoint GET thật của FastAPI. Không bao giờ thay dữ liệu lỗi bằng MOCK.
 * Hết phiên (401) → gọi onUnauthorized (App đăng xuất), không lặp lại.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ApiAgreement,
  ApiAlarm,
  ApiCommand,
  ApiConfig,
  ApiDevice,
  ApiDrift,
  ApiError,
  ApiHealthSummary,
  ApiReplay,
  ApiReportSummary,
  ApiTelemetry,
  ApiVoyage,
  LiveApi,
} from './liveApi';
import { computeLink, LinkInfo, parseTime } from './liveMapper';

export interface Resource<T> {
  data: T | null;
  error: string;
  status: number | null;
  reload: () => void;
}

/** GET định kỳ. fetcher=null → không gọi. Dữ liệu cũ bị xóa khi đổi khóa (key) để không hiển thị lẫn thiết bị/chuyến. */
function useResource<T>(
  key: string,
  fetcher: (() => Promise<T>) | null,
  intervalMs: number,
  onUnauthorized: () => void
): Resource<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState('');
  const [status, setStatus] = useState<number | null>(null);
  const [nonce, setNonce] = useState(0);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;
  const unauthorized = useRef(onUnauthorized);
  unauthorized.current = onUnauthorized;
  const active = fetcher !== null;

  // Đổi khóa (thiết bị/chuyến/phiên khác) → bỏ dữ liệu cũ. reload() thì KHÔNG xóa để màn hình không nhấp nháy.
  useEffect(() => {
    setData(null);
    setError('');
    setStatus(null);
  }, [key, active]);

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    let pending = false;
    const load = async () => {
      const f = fetcherRef.current;
      if (pending || !f) return;
      pending = true;
      try {
        const d = await f();
        if (!cancelled) {
          setData(d);
          setError('');
          setStatus(200);
        }
      } catch (e) {
        if (cancelled) return;
        const code = e instanceof ApiError ? e.status : 0;
        if (code === 401) {
          cancelled = true;
          unauthorized.current();
          return;
        }
        setStatus(code);
        setError(e instanceof Error ? e.message : 'Lỗi không xác định');
      } finally {
        pending = false;
      }
    };
    void load();
    const id = intervalMs > 0 ? setInterval(() => void load(), intervalMs) : undefined;
    return () => {
      cancelled = true;
      if (id !== undefined) clearInterval(id);
    };
  }, [key, active, intervalMs, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, status, reload };
}

function useNow(intervalMs: number, enabled: boolean): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!enabled) return;
    const id = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(id);
  }, [intervalMs, enabled]);
  return now;
}

export interface LiveBackend {
  devices: Resource<ApiDevice[]>;
  telemetry: Resource<ApiTelemetry[]>;
  alarms: Resource<ApiAlarm[]>;
  health: Resource<ApiHealthSummary[]>;
  commands: Resource<ApiCommand[]>;
  configs: Resource<ApiConfig[]>;
  voyages: Resource<ApiVoyage[]>;
  summary: Resource<ApiReportSummary>;
  replay: Resource<ApiReplay>;
  agreement: Resource<ApiAgreement>;
  drift: Resource<ApiDrift>;
  device: ApiDevice | null;
  deviceId: string | null;
  link: LinkInfo;
  reloadAll: () => void;
}

export function useLiveBackend(
  api: LiveApi | null,
  /** Khóa phiên (URL + token): đổi phiên → xóa dữ liệu cũ. */
  sessionKey: string,
  selectedVoyageId: string | null,
  /** Chỉ tải báo cáo/replay khi người dùng đang ở các màn hình đó. */
  reportsActive: boolean,
  modelActive: boolean,
  onUnauthorized: () => void
): LiveBackend {
  const on = api !== null;
  const devices = useResource<ApiDevice[]>(
    `${sessionKey}|devices`,
    on ? () => api.devices() : null,
    30000,
    onUnauthorized
  );

  const deviceId = useMemo(() => {
    const list = (devices.data ?? []).filter((d) => d.node_type !== 'CARGO'); // Cargo Node không phải tàu chính
    const sorted = [...list].sort((a, b) => (parseTime(b.last_seen) || 0) - (parseTime(a.last_seen) || 0));
    return sorted[0]?.device_id ?? null;
  }, [devices.data]);
  const device = useMemo(() => (devices.data ?? []).find((d) => d.device_id === deviceId && d.node_type !== 'CARGO') ?? null, [devices.data, deviceId]);
  const dk = `${sessionKey}|${deviceId}`;

  const telemetry = useResource<ApiTelemetry[]>(
    `${dk}|tel`,
    on && deviceId ? () => api.telemetry(deviceId, 120) : null,
    5000,
    onUnauthorized
  );
  const alarms = useResource<ApiAlarm[]>(
    `${dk}|alarms`,
    on && deviceId ? () => api.alarms(deviceId, 100) : null,
    5000,
    onUnauthorized
  );
  const health = useResource<ApiHealthSummary[]>(
    `${sessionKey}|health`,
    on ? () => api.health() : null,
    10000,
    onUnauthorized
  );
  const commands = useResource<ApiCommand[]>(
    `${sessionKey}|commands`,
    on ? () => api.commands(50) : null,
    10000,
    onUnauthorized
  );
  const configs = useResource<ApiConfig[]>(
    `${dk}|configs`,
    on && deviceId ? () => api.configs(deviceId) : null,
    30000,
    onUnauthorized
  );
  const voyages = useResource<ApiVoyage[]>(
    `${dk}|voyages`,
    on && deviceId ? () => api.voyages(deviceId) : null,
    30000,
    onUnauthorized
  );
  const summary = useResource<ApiReportSummary>(
    `${sessionKey}|summary|${selectedVoyageId}`,
    on && selectedVoyageId && reportsActive ? () => api.voyageSummary(selectedVoyageId) : null,
    30000,
    onUnauthorized
  );
  const replay = useResource<ApiReplay>(
    `${sessionKey}|replay|${selectedVoyageId}`,
    on && selectedVoyageId && reportsActive ? () => api.replay(selectedVoyageId, 2000) : null,
    0,
    onUnauthorized
  );
  const agreement = useResource<ApiAgreement>(
    `${dk}|agree`,
    on && deviceId && modelActive ? () => api.agreement(deviceId) : null,
    30000,
    onUnauthorized
  );
  const drift = useResource<ApiDrift>(
    `${dk}|drift`,
    on && deviceId && modelActive ? () => api.drift(deviceId) : null,
    60000,
    onUnauthorized
  );

  const now = useNow(1000, on);
  const healthStale = health.data?.find((h) => h.device_id === deviceId)?.stale ?? null;
  // Lỗi tải danh sách thiết bị cũng là mất kết nối Backend; lỗi tải telemetry thì ưu tiên báo lỗi đó.
  const apiError = telemetry.error || (deviceId ? '' : devices.error);
  const link = computeLink(telemetry.data, apiError, healthStale, now);

  const { reload: rTel } = telemetry;
  const { reload: rAl } = alarms;
  const { reload: rHe } = health;
  const { reload: rCo } = commands;
  const { reload: rCf } = configs;
  const { reload: rDe } = devices;
  const { reload: rVo } = voyages;
  const reloadAll = useCallback(() => {
    rTel();
    rAl();
    rHe();
    rCo();
    rCf();
    rDe();
    rVo();
  }, [rTel, rAl, rHe, rCo, rCf, rDe, rVo]);

  return {
    devices,
    telemetry,
    alarms,
    health,
    commands,
    configs,
    voyages,
    summary,
    replay,
    agreement,
    drift,
    device,
    deviceId,
    link,
    reloadAll,
  };
}
