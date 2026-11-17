/**
 * Smart Vessel Motion Guard Mobile — React Native / Expo Application
 * Complete implementation conforming to Google Stitch nautical bridge telemetry specifications.
 */
import React, { useEffect, useMemo, useState } from 'react';
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
import { MockDataService } from './src/data/service';
import {
  MAIN_TABS,
  TAB_LABELS,
  Alarm,
  AppActions,
  AppData,
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

  // Live simulation tick timer (adjusted by config.timewarp)
  useEffect(() => {
    const ms = Math.max(120, Math.round(1200 / (config.timewarp || 1)));
    const id = setInterval(() => setTick((x) => x + 1), ms);
    return () => clearInterval(id);
  }, [config.timewarp]);

  // Selected voyage memo
  const selectedVoyage = useMemo(
    () => MOCK_VOYAGES.find((v) => v.id === selectedVoyageId) || MOCK_VOYAGES[0],
    [selectedVoyageId]
  );

  // Synchronized replay point
  const currentReplayPoint = REPLAY_POINTS[replayIndex] || REPLAY_POINTS[0];
  const replaySeconds = currentReplayPoint.t_sim_s;

  // Replay playback timer governed by replaySpeed
  useEffect(() => {
    if (!replayPlaying) return;
    const intervalMs = Math.max(80, Math.round(900 / Math.max(1, replaySpeed)));
    const id = setInterval(() => {
      setReplayIndex((prev) => {
        if (prev >= REPLAY_POINTS.length - 1) {
          setReplayPlaying(false);
          return REPLAY_POINTS.length - 1;
        }
        return prev + 1;
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [replayPlaying, replaySpeed]);

  const telemetry = useMemo(
    () => MockDataService.getDemoTelemetry(scenario, tick),
    [scenario, tick]
  );

  const data: AppData = {
    route,
    session,
    scenario,
    telemetry,
    config,
    previousConfig,
    alarms,
    commands,
    voyage: selectedVoyage,
    voyages: MOCK_VOYAGES,
    selectedVoyageId,
    replaySeconds,
    replayIndex,
    replaySpeed,
    replayPoints: REPLAY_POINTS,
    health: computeHealth(scenario, tick),
    model: computeModelInfo(config.active_model),
    replayPlaying,
    buzzerMuted,
    latestSnapshot,
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

  const login = (u: string, p: string) => {
    const s = MockDataService.authenticateDemo(u, p);
    if (!s) return false;
    setSession(s);
    setHistory([]);
    setRoute('Overview');
    return true;
  };

  const logout = () => {
    setSession(null);
    setHistory([]);
    setRoute('Login');
    setReplayPlaying(false);
  };

  const ackAlarm = (id: string) => {
    setAlarms((list) =>
      list.map((a) =>
        a.id === id && a.status === 'RAISED'
          ? { ...a, status: 'ACKED' as const }
          : a
      )
    );
  };

  const muteAlarm = (id: string) => {
    const a = alarms.find((item) => item.id === id);
    if (!a || a.level === 'CRITICAL') {
      Alert.alert(
        'REJECTED: KHÔNG THỂ MUTE',
        'Theo quy chuẩn an toàn hàng hải và đề cương dự án, cảnh báo mức CRITICAL tuyệt đối không được tắt còi (MUTE).'
      );
      return;
    }
    if (a.status === 'CLEARED') return;
    setAlarms((list) =>
      list.map((item) =>
        item.id === id ? { ...item, muted: !item.muted } : item
      )
    );
  };

  const toggleBuzzer = () => {
    setBuzzerMuted((prev) => !prev);
  };

  const updateAlarmNote = (id: string, note: string) => {
    setAlarms((list) =>
      list.map((item) => (item.id === id ? { ...item, notes: note } : item))
    );
  };

  const reviewAlarm = (
    id: string,
    label: 'TRUE' | 'FALSE' | 'UNCERTAIN'
  ) => {
    setAlarms((items) =>
      items.map((a) => (a.id === id ? { ...a, review: label } : a))
    );
  };

  // M4-04: Full Command Execution & Lifecycle (SENT -> DELIVERED -> APPLIED/REJECTED/TIMEOUT)
  const sendCommand = (name: string, adminOnly = false, argument?: string) => {
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
    setReplaySeconds: (s: number) => {
      const idx = Math.min(REPLAY_POINTS.length - 1, Math.max(0, Math.floor(s / 5)));
      setReplayIndex(idx);
    },
    setReplayPlaying,
    selectVoyage: setSelectedVoyageId,
    setReplayIndex: (idx: number) => setReplayIndex(Math.min(REPLAY_POINTS.length - 1, Math.max(0, idx))),
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
  const unackCount = alarms.filter((a) => a.status === 'RAISED').length;

  return (
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
