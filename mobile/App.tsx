/**
 * Smart Vessel Motion Guard Mobile — React Native / Expo Application
 * Complete implementation conforming to Google Stitch nautical bridge telemetry specifications.
 */
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Alert,
  Pressable,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { C } from './src/theme';
import { DataModeContext } from './src/components/UI';
import { MockDataService } from './src/data/service';
import { ApiError, createApi, loginBackend, normalizeBaseUrl } from './src/data/liveApi';
import {
  buildSeries,
  mapAlarm,
  mapCommand,
  mapConfigs,
  mapHealth,
  mapModel,
  mapReplay,
  mapRole,
  mapTelemetry,
  mapVoyage,
  noVoyage,
} from './src/data/liveMapper';
import { useLiveBackend } from './src/data/useLiveBackend';
import {
  MAIN_TABS,
  TAB_LABELS,
  Alarm,
  ActionResult,
  AppActions,
  AppData,
  DataMode,
  Command,
  DeviceConfig,
  MainTab,
  MotionSnapshot,
  ZeroCalibration,
  Role,
  Route,
  Scenario,
  Session,
} from './src/types/domain';
import {
  computeHealth,
  fakeWavePoints,
  computeModelInfo,
  DEMO_HEALTH,
  DEMO_MODEL,
  DEMO_VOYAGE,
  INITIAL_ALARMS,
  MOCK_VOYAGES,
  REPLAY_POINTS,
} from './src/data/mock';
import { LoginScreen, RegisterScreen, ForgotPasswordScreen } from './src/screens/AuthScreens';
import {
  OverviewScreen,
  LiveMotionScreen,
  AlarmsScreen,
  AlarmDetailScreen,
} from './src/screens/MonitorScreens';
import {
  ControlCenterScreen,
  VoyageReportsScreen,
  ReportDetailsScreen,
  ReplayReviewScreen,
} from './src/screens/OperationScreens';
import {
  MoreScreen,
  DeviceHealthScreen,
  ModelMonitorScreen,
} from './src/screens/SystemScreens';

const INITIAL_CONFIG: DeviceConfig = {
  profile: 'STANDARD',
  config_version: 7,
  roll_warning_deg: 15.0,
  roll_trip_deg: 22.0,
  mai_alert_threshold: 0.70,
  source_mode: 'SIMULATION',
  timewarp: 1,
  active_model: 'RF',
  scenario: 'S0',
};

function isAuthorized(route: Route, role: Role): boolean {
  if (route === 'ModelMonitor') {
    return role === 'Supervisor' || role === 'Admin';
  }
  return true; // Control Center is visible for Operator but privileged actions are disabled.
}

function tabForRoute(route: Route): MainTab {
  if (route === 'AlarmDetail') return 'Alarms';
  if (route === 'ReportDetails' || route === 'ReplayReview') return 'VoyageReports';
  if (
    route === 'ControlCenter' ||
    route === 'DeviceHealth' ||
    route === 'ModelMonitor' ||
    route === 'More'
  ) {
    return 'More';
  }
  if (MAIN_TABS.includes(route as MainTab)) {
    return route as MainTab;
  }
  return 'Overview';
}

const TAB_ICONS: Record<MainTab, string> = {
  Overview: '⊞',
  LiveMotion: '≋',
  Alarms: '🔔',
  VoyageReports: '📄',
  More: '⋯',
};

export default function App() {
  const [route, setRoute] = useState<Route>('Login');
  const [history, setHistory] = useState<Route[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [scenario, setScenario] = useState<Scenario>('S0');
  const [tick, setTick] = useState(12);
  const [alarms, setAlarms] = useState<Alarm[]>(INITIAL_ALARMS);
  const [selectedAlarmId, setSelectedAlarmId] = useState('ALM-8492');
  const [config, setConfig] = useState<DeviceConfig>(INITIAL_CONFIG);
  const [previousConfig, setPreviousConfig] = useState<DeviceConfig | null>(null);
  const [commands, setCommands] = useState<Command[]>([]);
  const [selectedVoyageId, setSelectedVoyageId] = useState('V-2026-001');
  const [replayIndex, setReplayIndex] = useState(35);
  const [replaySpeed, setReplaySpeed] = useState(1);
  const [replayPlaying, setReplayPlaying] = useState(false);
  const [buzzerMuted, setBuzzerMuted] = useState(false);
  const [latestSnapshot, setLatestSnapshot] = useState<MotionSnapshot | null>(null);

  // --- LIVE: JWT chỉ nằm trong state (không ghi đĩa/log) ---
  const [mode, setMode] = useState<DataMode>('mock');
  const [baseUrl, setBaseUrl] = useState('');
  const [token, setToken] = useState<string | null>(null);
  const [liveVoyageId, setLiveVoyageId] = useState<string | null>(null);
  const live = mode === 'live';
  const api = useMemo(() => (live && token ? createApi(baseUrl, token) : null), [live, token, baseUrl]);
  const mounted = useRef(true);
  useEffect(() => () => { mounted.current = false; }, []);

  // Mock tick timer (adjusted by config.timewarp). Không chạy ở chế độ LIVE.
  useEffect(() => {
    if (live) return;
    const ms = Math.max(120, Math.round(1200 / (config.timewarp || 1)));
    const id = setInterval(() => setTick((x) => x + 1), ms);
    return () => clearInterval(id);
  }, [config.timewarp, live]);

  // ---------------------------------------------------------------------------------------------
  // Nguồn dữ liệu LIVE (Backend thật)
  const onUnauthorized = useCallback(() => {
    setToken(null);
    setSession(null);
    setMode('mock');
    setHistory([]);
    setRoute('Login');
    setReplayPlaying(false);
    Alert.alert('Hết phiên đăng nhập', 'Phiên làm việc với Backend đã hết hạn hoặc bị thu hồi. Vui lòng đăng nhập lại.');
  }, []);

  const reportsActive = route === 'VoyageReports' || route === 'ReportDetails' || route === 'ReplayReview';
  const lb = useLiveBackend(
    api,
    `${baseUrl}|${token ? token.slice(-12) : ''}`,
    liveVoyageId,
    reportsActive,
    route === 'ModelMonitor',
    onUnauthorized
  );

  // Chọn chuyến mặc định (mới nhất) khi Backend trả danh sách; bỏ chọn nếu chuyến không còn.
  useEffect(() => {
    if (!live) return;
    const list = lb.voyages.data;
    if (!list) return;
    if (!list.length) {
      if (liveVoyageId !== null) setLiveVoyageId(null);
      return;
    }
    if (!liveVoyageId || !list.some((v) => v.voyage_id === liveVoyageId)) {
      const newest = [...list].sort((a, b) => (a.started_at < b.started_at ? 1 : -1))[0];
      setLiveVoyageId(newest.voyage_id);
    }
  }, [live, lb.voyages.data, liveVoyageId]);

  const liveConfigs = useMemo(() => mapConfigs(lb.configs.data, lb.device), [lb.configs.data, lb.device]);
  const liveHealth = useMemo(
    () => mapHealth(lb.health.data?.find((h) => h.device_id === lb.deviceId) ?? null, lb.link),
    [lb.health.data, lb.deviceId, lb.link]
  );
  const liveReplay = useMemo(() => mapReplay(lb.replay.data), [lb.replay.data]);
  const liveAlarms = useMemo(() => (lb.alarms.data ?? []).map(mapAlarm), [lb.alarms.data]);
  const liveCommands = useMemo(
    () =>
      (lb.commands.data ?? [])
        .filter((c) => !lb.deviceId || c.device_id === lb.deviceId)
        .map((c) => mapCommand(c, liveConfigs.config.config_version || null)),
    [lb.commands.data, lb.deviceId, liveConfigs.config.config_version]
  );
  const liveVoyages = useMemo(
    () =>
      (lb.voyages.data ?? []).map((v) =>
        mapVoyage(v, lb.summary.data, lb.device, liveConfigs.config.config_version || null)
      ),
    [lb.voyages.data, lb.summary.data, lb.device, liveConfigs.config.config_version]
  );

  // Selected voyage memo
  const selectedVoyage = useMemo(
    () => MOCK_VOYAGES.find((v) => v.id === selectedVoyageId) || MOCK_VOYAGES[0],
    [selectedVoyageId]
  );
  const liveVoyage = liveVoyages.find((v) => v.id === liveVoyageId) ?? noVoyage(lb.deviceId);

  // Synchronized replay point
  const replayPoints = live ? liveReplay : REPLAY_POINTS;
  const currentReplayPoint = replayPoints[replayIndex] || replayPoints[0];
  const replaySeconds = currentReplayPoint ? currentReplayPoint.t_sim_s : 0;

  // Replay playback timer governed by replaySpeed
  useEffect(() => {
    if (!replayPlaying) return;
    const last = Math.max(0, replayPoints.length - 1);
    const intervalMs = Math.max(80, Math.round(900 / Math.max(1, replaySpeed)));
    const id = setInterval(() => {
      setReplayIndex((prev) => {
        if (prev >= last) {
          setReplayPlaying(false);
          return last;
        }
        return prev + 1;
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [replayPlaying, replaySpeed, replayPoints.length]);

  // Đổi chuyến đi (LIVE) → về đầu chuỗi phát lại
  useEffect(() => {
    setReplayIndex(0);
    setReplayPlaying(false);
  }, [liveVoyageId]);

  const mockTelemetry = useMemo(
    () => MockDataService.getDemoTelemetry(scenario, tick),
    [scenario, tick]
  );
  const liveTelemetry = useMemo(() => mapTelemetry(lb.link, lb.device), [lb.link, lb.device]);
  const getSeries = useMemo(
    () =>
      live
        ? buildSeries(lb.telemetry.data)
        : (count: number, endSeq?: number) => fakeWavePoints(scenario, endSeq ?? mockTelemetry.seq, count),
    [live, lb.telemetry.data, scenario, mockTelemetry.seq]
  );
  const telemetry = live ? liveTelemetry : mockTelemetry;
  const effectiveScenario: Scenario = live
    ? lb.link.state === 'SENSOR_FAULT'
      ? 'SENSOR_FAULT'
      : lb.link.state === 'ONLINE'
      ? 'UNKNOWN'
      : 'OFFLINE'
    : scenario;

  const data: AppData = {
    mode,
    link: live
      ? { state: lb.link.state, label: lb.link.label, ageS: lb.link.ageS, error: lb.link.error }
      : null,
    vesselName: live
      ? (lb.device?.name || lb.deviceId || 'CHƯA CÓ THIẾT BỊ').toUpperCase()
      : 'VESSEL DEMO 01',
    deviceId: live ? lb.deviceId : 'vessel-demo-01',
    firmware: live ? lb.device?.fw ?? null : 'v1.2.0-esp32',
    bootId: live ? lb.device?.boot_id ?? null : 'mock-boot-01',
    getSeries,
    route,
    session,
    scenario: effectiveScenario,
    telemetry,
    config: live ? liveConfigs.config : config,
    previousConfig: live ? liveConfigs.previous : previousConfig,
    alarms: live ? liveAlarms : alarms,
    commands: live ? liveCommands : commands,
    voyage: live ? liveVoyage : selectedVoyage,
    voyages: live ? liveVoyages : MOCK_VOYAGES,
    selectedVoyageId: live ? liveVoyageId ?? '' : selectedVoyageId,
    replaySeconds,
    replayIndex,
    replaySpeed,
    replayPoints,
    health: live ? liveHealth : computeHealth(scenario, tick),
    model: live
      ? mapModel(lb.device, liveConfigs.config, lb.agreement.data, lb.drift.data, liveHealth.inferenceMs)
      : computeModelInfo(config.active_model ?? 'RF'),
    replayPlaying,
    buzzerMuted,
    latestSnapshot: live ? null : latestSnapshot,
  };

  const go = (next: Route) => {
    const isAuthRoute = next === 'Login' || next === 'Register' || next === 'ForgotPassword';
    if (!isAuthRoute && !session) {
      setRoute('Login');
      setHistory([]);
      return;
    }
    if (session && !isAuthorized(next, session.role)) {
      Alert.alert(
        'Không đủ quyền hạn (Bảng 3.1)',
        `Vai trò ${session.role} không có quyền truy cập màn hình này.`
      );
      return;
    }
    if (next === route) return;
    setHistory((old) => [...old, route]);
    setRoute(next);
  };

  const back = () => {
    if (history.length) {
      const prev = history[history.length - 1];
      setRoute(prev);
      setHistory((old) => old.slice(0, -1));
    } else {
      setRoute(session ? 'Overview' : 'Login');
    }
  };

  const login = async (u: string, p: string, target: { mode: DataMode; url: string }): Promise<ActionResult> => {
    if (target.mode === 'mock') {
      const s = MockDataService.authenticateDemo(u, p);
      if (!s) return { ok: false, message: 'Tài khoản hoặc mã truy cập (passcode) chưa đúng. Vui lòng thử lại.' };
      setMode('mock');
      setToken(null);
      setSession(s);
      setHistory([]);
      setRoute('Overview');
      return { ok: true, message: '' };
    }
    const url = normalizeBaseUrl(target.url);
    if (!url) return { ok: false, message: 'Nhập địa chỉ Backend (vd. http://192.168.1.10:8000).' };
    try {
      const tok = await loginBackend(url, u.trim(), p);
      if (!mounted.current) return { ok: true, message: '' };
      setBaseUrl(url);
      setToken(tok.access_token);
      setLiveVoyageId(null);
      setReplayIndex(0);
      setMode('live');
      setSession({
        username: tok.username,
        displayName: tok.username,
        role: mapRole(tok.role),
        demo: false,
      });
      setHistory([]);
      setRoute('Overview');
      return { ok: true, message: '' };
    } catch (e) {
      return { ok: false, message: e instanceof Error ? e.message : 'Đăng nhập Backend thất bại.' };
    }
  };

  const logout = () => {
    setSession(null);
    setToken(null);
    setMode('mock');
    setHistory([]);
    setRoute('Login');
    setReplayPlaying(false);
  };

  const failure = (e: unknown, fallback: string): ActionResult => ({
    ok: false,
    message: e instanceof ApiError || e instanceof Error ? e.message : fallback,
  });

  const livePk = (id: string): number | null => {
    const a = liveAlarms.find((x) => x.id === id);
    return a?.pk ?? null;
  };

  const ackAlarm = async (id: string): Promise<ActionResult> => {
    if (live) {
      const pk = livePk(id);
      if (!api || pk === null) return { ok: false, message: 'Không tìm thấy cảnh báo trên Backend.' };
      try {
        const r = await api.ackAlarm(pk);
        lb.alarms.reload();
        const dev =
          r.device_ack === 'sent'
            ? 'Đã gửi lệnh báo ACK xuống thiết bị (chưa xác nhận từ thiết bị).'
            : r.device_ack === 'unsupported'
            ? 'Thiết bị chưa hỗ trợ lệnh ACK từ xa; ACK chỉ được ghi trên Backend.'
            : r.device_ack === 'failed'
            ? `ACK đã ghi trên Backend nhưng CHƯA báo được xuống thiết bị${r.device_ack_detail ? `: ${r.device_ack_detail}` : '.'}`
            : r.device_ack_detail ?? '';
        return {
          ok: true,
          message: `${r.already_acked ? 'Cảnh báo đã được ACK trước đó.' : 'Đã ghi nhận ACK trên Backend.'} ${dev}`.trim(),
        };
      } catch (e) {
        return failure(e, 'ACK thất bại.');
      }
    }
    setAlarms((list) =>
      list.map((a) =>
        a.id === id && a.status === 'RAISED'
          ? { ...a, status: 'ACKED' as const }
          : a
      )
    );
    return { ok: true, message: `Sĩ quan đã tiếp nhận sự kiện ${id}. Trạng thái chuyển thành ACKED.` };
  };

  const muteAlarm = async (id: string): Promise<ActionResult> => {
    const list = live ? liveAlarms : alarms;
    const a = list.find((item) => item.id === id);
    if (!a || a.level === 'CRITICAL') {
      return {
        ok: false,
        message:
          'Theo quy chuẩn an toàn hàng hải và đề cương dự án, cảnh báo mức CRITICAL tuyệt đối không được tắt còi (MUTE).',
      };
    }
    if (a.status === 'CLEARED') return { ok: false, message: 'Cảnh báo đã được giải tỏa.' };
    if (live) {
      if (!api || !lb.deviceId) return { ok: false, message: 'Chưa có thiết bị.' };
      try {
        const c = await api.sendCommand(lb.deviceId, 'mute_alarm', { duration_s: 60 });
        lb.commands.reload();
        void trackCommand(c.cmd_id, c.ttl_s);
        return { ok: true, message: `Đã gửi lệnh mute_alarm 60s (${c.cmd_id}). Kết quả hiển thị ở Control Center.` };
      } catch (e) {
        return failure(e, 'Gửi lệnh mute thất bại.');
      }
    }
    setAlarms((l) =>
      l.map((item) =>
        item.id === id ? { ...item, muted: !item.muted } : item
      )
    );
    return { ok: true, message: `Đã tạm ngắt chuông cho sự kiện ${id} trong tối đa 300 giây.` };
  };

  const toggleBuzzer = () => {
    setBuzzerMuted((prev) => !prev);
  };

  const updateAlarmNote = (id: string, note: string): ActionResult => {
    if (live) {
      return { ok: false, message: 'Backend chưa có API ghi chú cảnh báo nên ghi chú không được lưu.' };
    }
    setAlarms((list) =>
      list.map((item) => (item.id === id ? { ...item, notes: note } : item))
    );
    return { ok: true, message: 'Đã cập nhật nhật ký sĩ quan trực ca vào sự kiện.' };
  };

  const reviewAlarm = async (
    id: string,
    label: 'TRUE' | 'FALSE' | 'UNCERTAIN'
  ): Promise<ActionResult> => {
    if (live) {
      const pk = livePk(id);
      if (!api || pk === null) return { ok: false, message: 'Không tìm thấy cảnh báo trên Backend.' };
      try {
        await api.labelAlarm(
          pk,
          label === 'TRUE' ? 'TRUE_ALARM' : label === 'FALSE' ? 'FALSE_ALARM' : 'UNCLEAR'
        );
        lb.alarms.reload();
        return { ok: true, message: 'Đã lưu nhãn đánh giá lên Backend.' };
      } catch (e) {
        return failure(e, 'Gắn nhãn thất bại (cần quyền Supervisor trở lên).');
      }
    }
    setAlarms((items) =>
      items.map((a) => (a.id === id ? { ...a, review: label } : a))
    );
    return { ok: true, message: 'Đã lưu nhãn đánh giá.' };
  };

  /** Theo dõi vòng đời lệnh trên Backend đến trạng thái cuối (APPLIED/REJECTED/TIMEOUT) rồi báo kết quả. */
  const trackCommand = async (cmdId: string, ttlS: number) => {
    if (!api) return;
    const deadline = Date.now() + (ttlS + 15) * 1000;
    while (mounted.current && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, 2000));
      try {
        const c = await api.getCommand(cmdId);
        lb.commands.reload();
        if (c.state === 'APPLIED' || c.state === 'REJECTED' || c.state === 'TIMEOUT') {
          lb.reloadAll();
          if (mounted.current) {
            Alert.alert(
              c.state === 'APPLIED' ? 'LỆNH ĐÃ THỰC THI (APPLIED)' : `LỆNH ${c.state}`,
              `${c.cmd} (${cmdId})${c.reason ? `\nLý do: ${c.reason}` : ''}`
            );
          }
          return;
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return;
      }
    }
  };

  const sendLiveCommand = async (name: string, adminOnly: boolean, argument?: string) => {
    if (!session || session.role === 'Operator') {
      Alert.alert(
        'Từ chối quyền hạn (Bảng 3.1)',
        'Vai trò Operator (Sĩ quan trực ca) không được phép gửi lệnh cấu hình thiết bị giám sát.'
      );
      return;
    }
    if (adminOnly && session.role !== 'Admin') {
      Alert.alert('Yêu cầu quyền Admin (Bảng 3.1)', `Lệnh "${name}" yêu cầu quyền Quản trị viên (Admin). Vai trò hiện tại: ${session.role}.`);
      return;
    }
    if (!api || !lb.deviceId) {
      Alert.alert('Chưa có thiết bị', 'Backend chưa có thiết bị nào để gửi lệnh.');
      return;
    }
    const deviceId = lb.deviceId;
    try {
      if (name === 'set_profile' && argument) {
        const c = await api.sendCommand(deviceId, 'set_profile', { profile: argument });
        lb.commands.reload();
        void trackCommand(c.cmd_id, c.ttl_s);
        Alert.alert('ĐÃ GỬI LỆNH', `set_profile ${argument} (${c.cmd_id}) đang chờ thiết bị xác nhận.`);
      } else if (name === 'calibrate_zero') {
        const c = await api.sendCommand(deviceId, 'calibrate_zero');
        lb.commands.reload();
        void trackCommand(c.cmd_id, c.ttl_s);
        Alert.alert('ĐÃ GỬI LỆNH', `calibrate_zero (${c.cmd_id}). Thiết bị cần giữ tàu tĩnh ~30s rồi mới phản hồi.`);
      } else if (name === 'restart_device') {
        const c = await api.sendCommand(deviceId, 'restart_device');
        lb.commands.reload();
        void trackCommand(c.cmd_id, c.ttl_s);
        Alert.alert('ĐÃ GỬI LỆNH', `restart_device (${c.cmd_id}) đang chờ thiết bị xác nhận.`);
      } else if (name === 'rollback') {
        const cfg = await api.rollbackConfig(deviceId);
        lb.configs.reload();
        setTimeout(() => lb.reloadAll(), 3000);
        Alert.alert('ĐÃ GỬI ROLLBACK', `Đã phát cấu hình v${cfg.config_version} (quay lui). Chờ thiết bị áp dụng (applied=${cfg.applied}).`);
      } else if (name === 'set_model' && argument) {
        // Backend yêu cầu cấu hình đầy đủ có `profile`: chỉ dựa vào cấu hình đã có trên Backend, không tự đặt profile mặc định.
        if (!lb.configs.data || lb.configs.data.length === 0) {
          Alert.alert(
            'CHƯA CÓ CẤU HÌNH NỀN',
            'Backend chưa có phiên bản cấu hình nào cho thiết bị này. Hãy đặt Profile (set_profile) hoặc nạp cấu hình trước khi đổi mô hình chính.'
          );
          return;
        }
        const cfg = await api.putConfig(deviceId, {
          profile: liveConfigs.config.profile,
          primary_model: argument,
        });
        lb.configs.reload();
        setTimeout(() => lb.reloadAll(), 3000);
        Alert.alert('ĐÃ GỬI CẤU HÌNH', `primary_model=${argument} (cấu hình v${cfg.config_version}). Chờ thiết bị áp dụng.`);
      } else {
        Alert.alert(
          'CHƯA KHẢ DỤNG Ở CHẾ ĐỘ LIVE',
          `Lệnh "${name}" không có trong hợp đồng Backend/firmware hiện tại nên không được gửi.`
        );
      }
    } catch (e) {
      Alert.alert('GỬI LỆNH THẤT BẠI', e instanceof Error ? e.message : 'Lỗi không xác định.');
    }
  };

  // M4-04: Full Command Execution & Lifecycle (SENT -> DELIVERED -> APPLIED/REJECTED/TIMEOUT)
  const sendMockCommand = (name: string, adminOnly = false, argument?: string) => {
    // Check role permissions: Operator cannot send configuration commands
    if (!session || session.role === 'Operator') {
      Alert.alert(
        'Từ chối quyền hạn (Bảng 3.1)',
        'Vai trò Operator (Sĩ quan trực ca) không được phép gửi lệnh cấu hình thiết bị giám sát.'
      );
      return;
    }

    // Admin-only commands check
    if (adminOnly && session.role !== 'Admin') {
      Alert.alert(
        'Yêu cầu quyền Admin (Bảng 3.1)',
        `Lệnh "${name}" yêu cầu quyền Quản trị viên (Admin). Vai trò hiện tại: ${session.role}.`
      );
      return;
    }

    const cmdId = `CMD-${Math.random().toString(16).slice(2, 6).toUpperCase()}-${Date.now().toString().slice(-4)}`;
    const fullCmdName = argument ? `${name} (${argument})` : name;
    const now = new Date();
    const utcTime = `${String(now.getUTCHours()).padStart(2, '0')}:${String(
      now.getUTCMinutes()
    ).padStart(2, '0')}:${String(now.getUTCSeconds()).padStart(2, '0')} UTC`;

    // 1. Initial Lifecycle State: SENT
    const isTimeout = (name === 'test_timeout');
    const isCalZero = (name === 'calibrate_zero');
    const isSnapshot = (name === 'request_snapshot');
    const isRollback = (name === 'rollback');
    const isStatic = (scenario === 'S0');

    setCommands((items) => [
      {
        id: cmdId,
        name: isTimeout ? '[TEST UTILITY] test_timeout (Mô phỏng TTL 30s)' : fullCmdName,
        at: utcTime,
        status: 'SENT' as const,
        detail: isTimeout
          ? 'Khởi chạy tiện ích kiểm thử: Đang gửi lệnh thử nghiệm timeout TTL 30s...'
          : isCalZero
          ? 'Đang lấy mẫu và kiểm tra độ ổn định tín hiệu trong 30s (độ lệch chuẩn roll)...'
          : 'Đang xuất bản qua topic MQTT QoS 1 tới thiết bị giám sát...',
        config_version: config.config_version,
        issued_by: session.username,
        is_test_utility: isTimeout,
      },
      ...items,
    ]);

    // 2. Lifecycle State: DELIVERED (after 280ms)
    setTimeout(() => {
      setCommands((items) =>
        items.map((c) =>
          c.id === cmdId
            ? {
                ...c,
                status: 'DELIVERED' as const,
                detail: isTimeout
                  ? 'Thiết bị đã nhận lệnh thử nghiệm; đang đợi phản hồi ACK (mô phỏng mất gói)...'
                  : isCalZero
                  ? 'Thiết bị đang đo phương sai và độ lệch 0 trong cửa sổ 30s...'
                  : 'Thiết bị đã nhận lệnh (QoS 1 PUBACK); đang kiểm tra điều kiện an toàn...',
              }
            : c
        )
      );
    }, 280);

    // 3. Final Lifecycle State: APPLIED / REJECTED / TIMEOUT (after 750ms)
    setTimeout(() => {
      // TIMEOUT Simulation Test Case
      if (isTimeout) {
        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'TIMEOUT' as const,
                  detail: 'EXPIRED: Quá hạn TTL 30s không nhận được phản hồi ACK từ thiết bị (Tiện ích kiểm thử).',
                  reason: 'TTL_EXPIRED',
                }
              : c
          )
        );
        Alert.alert(
          'TIỆN ÍCH KIỂM THỬ: LỆNH QUÁ HẠN (TIMEOUT)',
          `Lệnh ${cmdId} không nhận được phản hồi từ thiết bị trong thời gian TTL cho phép (T10 test utility).`
        );
        return;
      }

      // calibrate_zero: Requires static condition in 30s (Scenario S0)
      if (isCalZero) {
        if (!isStatic) {
          setCommands((items) =>
            items.map((c) =>
              c.id === cmdId
                ? {
                    ...c,
                    status: 'REJECTED' as const,
                    detail: `NOT_STATIC: Tàu đang dao động (kịch bản ${scenario}). Độ lệch chuẩn roll σ > 1.0° trong 30s đo; không đạt điều kiện tĩnh.`,
                    reason: 'NOT_STATIC',
                  }
                : c
            )
          );
          Alert.alert(
            'LỆNH BỊ TỪ CHỐI (REJECTED)',
            `Mã từ chối: NOT_STATIC.\nThiết bị từ chối hiệu chuẩn zero vì độ lệch chuẩn roll vượt ngưỡng cho phép (kịch bản hiện tại: ${scenario}). Yêu cầu tàu tĩnh (kịch bản S0) để thực hiện.`
          );
          return;
        }

        const cal: ZeroCalibration = {
          roll_offset_deg: 0.12,
          pitch_offset_deg: -0.05,
          std_dev_roll: 0.15,
          duration_s: 30,
          calibrated_at: new Date().toISOString(),
          is_static: true,
        };
        const newVersion = config.config_version + 1;
        setConfig((prev) => ({
          ...prev,
          config_version: newVersion,
          zero_calibration: cal,
        }));

        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Tín hiệu tĩnh 30s đạt chuẩn (σ=0.15° ≤ 1.0°). Đã lưu điểm 0: roll +0.12°, pitch -0.05° vào cấu hình v${newVersion}.`,
                  config_version: newVersion,
                }
              : c
          )
        );
        Alert.alert(
          'LỆNH ĐÃ THỰC THI (APPLIED)',
          `Lệnh ${cmdId} (calibrate_zero): Đã lấy mẫu 30s tĩnh và lưu độ lệch 0 (roll +0.12°, pitch -0.05°) vào cấu hình v${newVersion}.`
        );
        return;
      }

      // set_profile: CONSERVATIVE / STANDARD / SENSITIVE
      if (name === 'set_profile' && argument) {
        const prof = argument as DeviceConfig['profile'];
        setPreviousConfig({ ...config });
        const newVersion = config.config_version + 1;
        const newWarning = prof === 'SENSITIVE' ? 12.0 : prof === 'CONSERVATIVE' ? 18.0 : 15.0;
        const newTrip = prof === 'SENSITIVE' ? 18.0 : prof === 'CONSERVATIVE' ? 25.0 : 22.0;
        const newMai = prof === 'SENSITIVE' ? 0.65 : prof === 'CONSERVATIVE' ? 0.75 : 0.70;

        setConfig((prev) => ({
          ...prev,
          profile: prof,
          config_version: newVersion,
          roll_warning_deg: newWarning,
          roll_trip_deg: newTrip,
          mai_alert_threshold: newMai,
        }));

        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Áp dụng Profile ${prof} thành công. Phiên bản cấu hình nâng lên v${newVersion}.`,
                  config_version: newVersion,
                }
              : c
          )
        );
        Alert.alert(
          'ÁP DỤNG CẤU HÌNH (APPLIED)',
          `Đã chuyển sang Profile ${prof}. Config version: v${newVersion}.\nRoll Warning (Mô phỏng): ${newWarning}°, Trip: ${newTrip}°, MAI: ${newMai}.`
        );
        return;
      }

      // rollback: Restores previous configuration version
      if (isRollback) {
        if (!previousConfig) {
          setCommands((items) =>
            items.map((c) =>
              c.id === cmdId
                ? {
                    ...c,
                    status: 'REJECTED' as const,
                    detail: 'NO_PREVIOUS_VERSION: Chưa có bản snapshot cấu hình trước đó để quay lui.',
                    reason: 'NO_PREVIOUS_VERSION',
                  }
                : c
            )
          );
          Alert.alert(
            'TỪ CHỐI ROLLBACK',
            'Chưa có bản ghi cấu hình trước đó trong phiên hiện tại để hoàn tác.'
          );
          return;
        }

        const restored = { ...previousConfig };
        const newVersion = config.config_version + 1;
        setPreviousConfig({ ...config });
        setConfig({
          ...restored,
          config_version: newVersion,
        });

        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Đã rollback về Profile ${restored.profile}. Phiên bản cấu hình mới: v${newVersion}.`,
                  config_version: newVersion,
                }
              : c
          )
        );
        Alert.alert(
          'ROLLBACK THÀNH CÔNG (APPLIED)',
          `Đã khôi phục Profile ${restored.profile} từ bản sao lưu trước đó. Config version mới: v${newVersion}.`
        );
        return;
      }

      // set_scenario: Admin only
      if (name === 'set_scenario' && argument) {
        const sc = argument as Scenario;
        setScenario(sc);
        setConfig((prev) => ({ ...prev, scenario: sc }));
        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Đã kích hoạt kịch bản mô phỏng ${sc}. Dữ liệu telemetry cập nhật ngay lập tức.`,
                }
              : c
          )
        );
        Alert.alert(
          'ĐỔI KỊCH BẢN (APPLIED)',
          `Đã kích hoạt kịch bản ${sc}. Đồ thị và số liệu trên Overview & Live Motion đã cập nhật theo kịch bản này.`
        );
        return;
      }

      // set_timewarp: Admin only
      if (name === 'set_timewarp' && argument) {
        const tw = parseInt(argument.replace('×', ''), 10) || 1;
        setConfig((prev) => ({ ...prev, timewarp: tw }));
        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Tốc độ thời gian ảo trong SIMULATION chuyển mức ×${tw}. Chu kỳ cập nhật dữ liệu tăng tốc.`,
                }
              : c
          )
        );
        Alert.alert('TIMEWARP APPLIED', `Tốc độ mô phỏng đặt ở mức ×${tw}. Chu kỳ cập nhật đồ thị đã tăng tốc tương ứng.`);
        return;
      }

      // set_model: Admin only
      if (name === 'set_model' && argument) {
        const mod = argument as DeviceConfig['active_model'];
        setConfig((prev) => ({ ...prev, active_model: mod }));
        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Mô hình quyết định chính: ${mod === 'RF' ? 'Random Forest (Dữ liệu demo)' : 'Baseline B (Dữ liệu demo)'}. Không suy luận TinyML trên Mobile.`,
                }
              : c
          )
        );
        Alert.alert('SET MODEL APPLIED', `Mô hình chính chuyển sang: ${mod} từ luồng dữ liệu demo.`);
        return;
      }

      // set_mode: Admin only
      if (name === 'set_mode' && argument) {
        if (argument === 'SENSOR') {
          setCommands((items) =>
            items.map((c) =>
              c.id === cmdId
                ? {
                    ...c,
                    status: 'REJECTED' as const,
                    detail: 'NO_SENSOR_IN_MOCK: Phần cứng MPU6050 thực tế chưa kết nối trong môi trường demo TV4.',
                    reason: 'NO_SENSOR_IN_MOCK',
                  }
                : c
            )
          );
          Alert.alert(
            'TỪ CHỐI CHUYỂN CHẾ ĐỘ SENSOR',
            'Chế độ SENSOR thật chưa có trong gói mock TV4 (chờ tích hợp phần cứng của TV1). Lệnh bị từ chối với lý do: NO_SENSOR_IN_MOCK.'
          );
          return;
        }

        setConfig((prev) => ({ ...prev, source_mode: 'SIMULATION' }));
        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: 'Chế độ hoạt động: SIMULATION.',
                }
              : c
          )
        );
        Alert.alert('MODE APPLIED', 'Đã đặt chế độ: SIMULATION.');
        return;
      }

      // request_snapshot
      if (isSnapshot) {
        const snap: MotionSnapshot = {
          snapshot_id: `SNAP-${String(Date.now()).slice(-6)}`,
          timestamp: new Date().toISOString(),
          window_s: 180,
          sample_count: 36,
          roll_min: -(telemetry.rms_roll_deg || 3.2),
          roll_max: +(telemetry.rms_roll_deg || 3.2),
          pitch_min: -1.6,
          pitch_max: 1.9,
          rms_roll_deg: telemetry.rms_roll_deg || 2.4,
          mai: telemetry.mai || 15,
          triggered_by: session.username,
          source_scenario: scenario,
        };
        setLatestSnapshot(snap);

        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Bản chụp 180s (36 mẫu) đã được tạo và lưu trong Mock State: ${snap.snapshot_id}.`,
                }
              : c
          )
        );
        Alert.alert(
          'SNAPSHOT TRACE ĐÃ LƯU',
          `Bản chụp 180s (${snap.snapshot_id}) gồm 36 mẫu động học đã được trích xuất và lưu trong Mock State.`
        );
        return;
      }
    }, 750);
  };
  const sendCommand = (name: string, adminOnly = false, argument?: string) => {
    if (live) {
      void sendLiveCommand(name, adminOnly, argument);
    } else {
      sendMockCommand(name, adminOnly, argument);
    }
  };

  const actions: AppActions = {
    go,
    back,
    login,
    logout,
    selectedAlarmId,
    selectAlarm: setSelectedAlarmId,
    ackAlarm,
    muteAlarm,
    toggleBuzzer,
    updateAlarmNote,
    reviewAlarm,
    sendCommand,
    setScenario: (s) => sendCommand('set_scenario', true, s),
    setReplaySeconds: (sec: number) => {
      const found = replayPoints.findIndex((pt) => pt.t_sim_s >= sec);
      setReplayIndex(Math.max(0, found === -1 ? replayPoints.length - 1 : found));
    },
    setReplayPlaying,
    selectVoyage: (id: string) => {
      if (live) setLiveVoyageId(id);
      else setSelectedVoyageId(id);
    },
    setReplayIndex: (idx: number) =>
      setReplayIndex(Math.min(Math.max(0, replayPoints.length - 1), Math.max(0, idx))),
    setReplaySpeed,
  };

  const p = { data, actions };

  const renderScreen = () => {
    switch (route) {
      case 'Login':
        return <LoginScreen {...p} />;
      case 'Register':
        return <RegisterScreen {...p} />;
      case 'ForgotPassword':
        return <ForgotPasswordScreen {...p} />;
      case 'Overview':
        return <OverviewScreen {...p} />;
      case 'LiveMotion':
        return <LiveMotionScreen {...p} />;
      case 'Alarms':
        return <AlarmsScreen {...p} />;
      case 'AlarmDetail':
        return <AlarmDetailScreen {...p} />;
      case 'ControlCenter':
        return <ControlCenterScreen {...p} />;
      case 'VoyageReports':
        return <VoyageReportsScreen {...p} />;
      case 'ReportDetails':
        return <ReportDetailsScreen {...p} />;
      case 'ReplayReview':
        return <ReplayReviewScreen {...p} />;
      case 'DeviceHealth':
        return <DeviceHealthScreen {...p} />;
      case 'ModelMonitor':
        return <ModelMonitorScreen {...p} />;
      case 'More':
        return <MoreScreen {...p} />;
    }
  };

  const showTab = Boolean(session && !['Login', 'Register', 'ForgotPassword'].includes(route));
  const unackCount = data.alarms.filter((a) => a.status === 'RAISED').length;

  const modeCtx = useMemo(
    () => ({ mode, link: data.link, source: live && lb.link.latest ? lb.link.latest.source_mode : null }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [mode, data.link?.state, data.link?.label, data.link?.ageS, live, lb.link.latest?.source_mode]
  );

  return (
    <DataModeContext.Provider value={modeCtx}>
    <SafeAreaProvider>
      <SafeAreaView edges={['top', 'left', 'right', 'bottom']} style={styles.root}>
        <StatusBar barStyle="dark-content" />
        <View style={{ flex: 1 }}>{renderScreen()}</View>

        {showTab && (
          <View style={styles.tabs}>
            {MAIN_TABS.map((tab) => {
              const active = tabForRoute(route) === tab;
              const isAlarmsTab = tab === 'Alarms';

              return (
                <Pressable
                  key={tab}
                  accessibilityRole="tab"
                  accessibilityState={{ selected: active }}
                  onPress={() => go(tab)}
                  style={[styles.tab, active ? styles.activeTab : null]}
                >
                  <View style={styles.iconContainer}>
                    <Text
                      style={[
                        styles.tabIcon,
                        active ? styles.tabIconActive : styles.tabIconInactive,
                      ]}
                    >
                      {TAB_ICONS[tab]}
                    </Text>
                    {isAlarmsTab && unackCount > 0 && (
                      <View style={styles.badge}>
                        <Text style={styles.badgeText}>{unackCount}</Text>
                      </View>
                    )}
                  </View>
                  <Text
                    style={[
                      styles.tabLabel,
                      active ? styles.selectedTab : styles.unselectedTab,
                    ]}
                  >
                    {TAB_LABELS[tab]}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        )}
      </SafeAreaView>
    </SafeAreaProvider>
    </DataModeContext.Provider>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: C.canvas,
  },
  tabs: {
    height: 60,
    backgroundColor: C.bg,
    borderTopColor: C.border,
    borderTopWidth: 1.5,
    flexDirection: 'row',
  },
  tab: {
    flex: 1,
    minWidth: 0,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 4,
  },
  activeTab: {
    borderTopColor: '#00B7E8',
    borderTopWidth: 2.5,
    backgroundColor: '#EAF4FF',
  },
  iconContainer: {
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabIcon: {
    fontSize: 16,
    lineHeight: 18,
  },
  tabIconActive: {
    color: '#0F2F4F',
  },
  tabIconInactive: {
    color: '#55728D',
  },
  badge: {
    position: 'absolute',
    top: -5,
    right: -10,
    backgroundColor: C.red,
    borderRadius: 7,
    paddingHorizontal: 4,
    paddingVertical: 1,
    minWidth: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    color: '#FFFFFF',
    fontSize: 8,
    fontWeight: '900',
  },
  tabLabel: {
    fontSize: 10,
    fontWeight: '700',
    marginTop: 2,
  },
  selectedTab: {
    color: '#0F2F4F',
    fontWeight: '800',
  },
  unselectedTab: {
    color: '#55728D',
    fontWeight: '600',
  },
});
