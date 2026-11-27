/**
 * Smart Vessel Motion Guard Mobile — React Native / Expo Application
 * Đồng bộ UI/UX, Typography (Be Vietnam Pro), Bảng màu và Hệ thống 23 đặc trưng với Web.
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
import {
  BeVietnamPro_400Regular,
  BeVietnamPro_500Medium,
  BeVietnamPro_600SemiBold,
  BeVietnamPro_700Bold,
  useFonts,
} from '@expo-google-fonts/be-vietnam-pro';
import { FONT, ThemeProvider, useTheme } from './src/theme';
import { MockDataService } from './src/data/service';
import {
  Alarm,
  AppActions,
  AppData,
  Command,
  DeviceConfig,
  MAIN_TABS,
  MainTab,
  MotionSnapshot,
  Role,
  Route,
  Scenario,
  Session,
  TAB_LABELS,
  ZeroCalibration,
} from './src/types/domain';
import {
  computeHealth,
  computeModelInfo,
  INITIAL_ALARMS,
  MOCK_VOYAGES,
  REPLAY_POINTS,
} from './src/data/mock';
import { ForgotPasswordScreen, LoginScreen, RegisterScreen } from './src/screens/AuthScreens';
import {
  AlarmDetailScreen,
  AlarmsScreen,
  LiveMotionScreen,
  OverviewScreen,
} from './src/screens/MonitorScreens';
import {
  ControlCenterScreen,
  ReplayReviewScreen,
  ReportDetailsScreen,
  VoyageReportsScreen,
} from './src/screens/OperationScreens';
import {
  DeviceHealthScreen,
  ModelMonitorScreen,
  MoreScreen,
} from './src/screens/SystemScreens';

const INITIAL_CONFIG: DeviceConfig = {
  profile: 'STANDARD',
  config_version: 7,
  roll_warning_deg: 15.0,
  roll_trip_deg: 22.0,
  mai_alert_threshold: 0.7,
  source_mode: 'SIMULATION',
  timewarp: 1,
  active_model: 'RF',
  scenario: 'S0',
};

function isAuthorized(route: Route, role: Role): boolean {
  if (route === 'ModelMonitor') {
    return role === 'Supervisor' || role === 'Admin';
  }
  return true;
}

function tabForRoute(route: Route): MainTab {
  if (route === 'AlarmDetail') return 'Alarms';
  if (
    route === 'ControlCenter' ||
    route === 'VoyageReports' ||
    route === 'ReportDetails' ||
    route === 'ReplayReview' ||
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
  More: '☰',
};

function AppShell() {
  const { colors, isDark } = useTheme();
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

  useEffect(() => {
    const ms = Math.max(120, Math.round(1200 / (config.timewarp || 1)));
    const id = setInterval(() => setTick((x) => x + 1), ms);
    return () => clearInterval(id);
  }, [config.timewarp]);

  const selectedVoyage = useMemo(
    () => MOCK_VOYAGES.find((v) => v.id === selectedVoyageId) || MOCK_VOYAGES[0],
    [selectedVoyageId]
  );

  const currentReplayPoint = REPLAY_POINTS[replayIndex] || REPLAY_POINTS[0];
  const replaySeconds = currentReplayPoint.t_sim_s;

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
    model: computeModelInfo(config.active_model, scenario, telemetry.sensor_ok),
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
      list.map((a) => (a.id === id && a.status === 'RAISED' ? { ...a, status: 'ACKED' as const } : a))
    );
  };

  const muteAlarm = (id: string) => {
    const a = alarms.find((item) => item.id === id);
    if (!a || a.level === 'CRITICAL') {
      Alert.alert(
        'Từ chối tắt âm',
        'Theo quy chuẩn an toàn hàng hải, cảnh báo mức Nguy cấp tuyệt đối không được tắt còi.'
      );
      return;
    }
    if (a.status === 'CLEARED') return;
    setAlarms((list) =>
      list.map((item) => (item.id === id ? { ...item, muted: !item.muted } : item))
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

  const reviewAlarm = (id: string, label: 'TRUE' | 'FALSE' | 'UNCERTAIN') => {
    setAlarms((items) =>
      items.map((a) => (a.id === id ? { ...a, review: label } : a))
    );
  };

  const sendCommand = (name: string, adminOnly = false, argument?: string) => {
    if (!session || session.role === 'Operator') {
      Alert.alert(
        'Từ chối quyền hạn (Bảng 3.1)',
        'Vai trò Sĩ quan trực ca không được phép gửi lệnh cấu hình thiết bị.'
      );
      return;
    }

    if (adminOnly && session.role !== 'Admin') {
      Alert.alert(
        'Yêu cầu quyền Quản trị viên',
        `Lệnh "${name}" yêu cầu quyền Quản trị viên (Admin).`
      );
      return;
    }

    const cmdId = `CMD-${Math.random().toString(16).slice(2, 6).toUpperCase()}-${Date.now().toString().slice(-4)}`;
    const fullCmdName = argument ? `${name} (${argument})` : name;
    const now = new Date();
    const utcTime = `${String(now.getUTCHours()).padStart(2, '0')}:${String(
      now.getUTCMinutes()
    ).padStart(2, '0')}:${String(now.getUTCSeconds()).padStart(2, '0')} UTC`;

    const isTimeout = name === 'test_timeout';
    const isCalZero = name === 'calibrate_zero';
    const isSnapshot = name === 'request_snapshot';
    const isRollback = name === 'rollback';
    const isStatic = scenario === 'S0';

    setCommands((items) => [
      {
        id: cmdId,
        name: isTimeout ? 'test_timeout (Thử nghiệm TTL 30s)' : fullCmdName,
        at: utcTime,
        status: 'SENT' as const,
        detail: isTimeout
          ? 'Đang gửi lệnh thử nghiệm quá hạn TTL 30s...'
          : isCalZero
          ? 'Đang kiểm tra độ ổn định tín hiệu tĩnh trong 30 giây...'
          : 'Đang xuất bản lệnh qua MQTT QoS 1 tới thiết bị...',
        config_version: config.config_version,
        issued_by: session.username,
        is_test_utility: isTimeout,
      },
      ...items,
    ]);

    setTimeout(() => {
      setCommands((items) =>
        items.map((c) =>
          c.id === cmdId
            ? {
                ...c,
                status: 'DELIVERED' as const,
                detail: isTimeout
                  ? 'Thiết bị đã nhận lệnh thử nghiệm; đang chờ phản hồi ACK...'
                  : 'Thiết bị đã nhận lệnh (PUBACK); đang kiểm tra điều kiện an toàn...',
              }
            : c
        )
      );
    }, 280);

    setTimeout(() => {
      if (isTimeout) {
        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'TIMEOUT' as const,
                  detail: 'Quá hạn TTL 30s không nhận được phản hồi ACK từ thiết bị.',
                  reason: 'TTL_EXPIRED',
                }
              : c
          )
        );
        Alert.alert('Quá thời gian chờ', `Lệnh ${cmdId} không nhận được phản hồi ACK.`);
        return;
      }

      if (isCalZero) {
        if (!isStatic) {
          setCommands((items) =>
            items.map((c) =>
              c.id === cmdId
                ? {
                    ...c,
                    status: 'REJECTED' as const,
                    detail: `NOT_STATIC: Tàu đang dao động (${scenario}). Độ lệch chuẩn roll > 1.0° trong 30s.`,
                    reason: 'NOT_STATIC',
                  }
                : c
            )
          );
          Alert.alert(
            'Lệnh bị từ chối (NOT_STATIC)',
            `Không thể hiệu chuẩn điểm 0 khi tàu đang dao động (${scenario}). Cần chuyển sang kịch bản S0 (Biển êm).`
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
                  detail: `Đã lưu điểm 0: Roll +0.12°, Pitch -0.05° vào cấu hình v${newVersion}.`,
                  config_version: newVersion,
                }
              : c
          )
        );
        Alert.alert('Hiệu chuẩn thành công', `Đã lưu điểm 0 vào cấu hình v${newVersion}.`);
        return;
      }

      if (name === 'set_profile' && argument) {
        const prof = argument as DeviceConfig['profile'];
        setPreviousConfig({ ...config });
        const newVersion = config.config_version + 1;
        const newWarning = prof === 'SENSITIVE' ? 12.0 : prof === 'CONSERVATIVE' ? 18.0 : 15.0;
        const newTrip = prof === 'SENSITIVE' ? 18.0 : prof === 'CONSERVATIVE' ? 25.0 : 22.0;
        const newMai = prof === 'SENSITIVE' ? 0.65 : prof === 'CONSERVATIVE' ? 0.75 : 0.7;

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
                  detail: `Đã áp dụng Profile ${prof} (v${newVersion}).`,
                  config_version: newVersion,
                }
              : c
          )
        );
        Alert.alert(
          'Cập nhật cấu hình',
          `Đã áp dụng Profile ${prof} (v${newVersion}): Cảnh báo ${newWarning}°, Nguy cấp ${newTrip}°, MAI ${newMai}.`
        );
        return;
      }

      if (isRollback) {
        if (!previousConfig) {
          setCommands((items) =>
            items.map((c) =>
              c.id === cmdId
                ? {
                    ...c,
                    status: 'REJECTED' as const,
                    detail: 'Chưa có bản cấu hình trước đó để khôi phục.',
                    reason: 'NO_PREVIOUS_VERSION',
                  }
                : c
            )
          );
          return;
        }

        const restored = { ...previousConfig };
        const newVersion = config.config_version + 1;
        setPreviousConfig({ ...config });
        setConfig({ ...restored, config_version: newVersion });

        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Đã khôi phục về Profile ${restored.profile} (v${newVersion}).`,
                  config_version: newVersion,
                }
              : c
          )
        );
        Alert.alert('Khôi phục thành công', `Đã khôi phục Profile ${restored.profile} (v${newVersion}).`);
        return;
      }

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
                  detail: `Đã kích hoạt kịch bản mô phỏng ${sc}.`,
                }
              : c
          )
        );
        return;
      }

      if (name === 'set_timewarp' && argument) {
        const tw = parseInt(argument.replace('×', ''), 10) || 1;
        setConfig((prev) => ({ ...prev, timewarp: tw }));
        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Tốc độ thời gian mô phỏng chuyển mức ×${tw}.`,
                }
              : c
          )
        );
        return;
      }

      if (name === 'set_model' && argument) {
        const mod = argument as DeviceConfig['active_model'];
        setConfig((prev) => ({ ...prev, active_model: mod }));
        setCommands((items) =>
          items.map((c) =>
            c.id === cmdId
              ? {
                  ...c,
                  status: 'APPLIED' as const,
                  detail: `Mô hình chính: ${mod === 'RF' ? 'Random Forest' : 'Baseline B'}.`,
                }
              : c
          )
        );
        return;
      }

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
                  detail: `Đã tạo bản chụp 180s (36 mẫu): ${snap.snapshot_id}.`,
                }
              : c
          )
        );
        Alert.alert('Đã lưu bản chụp', `Bản chụp ${snap.snapshot_id} (36 mẫu) đã lưu vào phiên.`);
      }
    }, 650);
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
    <SafeAreaView
      edges={['top', 'left', 'right', 'bottom']}
      style={[styles.root, { backgroundColor: colors.canvas }]}
    >
      <StatusBar barStyle={isDark ? 'light-content' : 'dark-content'} />
      <View style={{ flex: 1 }}>{renderScreen()}</View>

      {showTab && (
        <View
          style={[
            styles.tabs,
            { backgroundColor: colors.panel, borderTopColor: colors.borderSubtle },
          ]}
        >
          {MAIN_TABS.map((tab) => {
            const active = tabForRoute(route) === tab;
            const isAlarmsTab = tab === 'Alarms';

            return (
              <Pressable
                key={tab}
                accessibilityRole="tab"
                accessibilityState={{ selected: active }}
                onPress={() => go(tab)}
                style={({ pressed }) => [
                  styles.tab,
                  active && { backgroundColor: colors.cyanContainerBg },
                  pressed && { opacity: 0.75 },
                ]}
              >
                {active && (
                  <View
                    style={[styles.activeIndicator, { backgroundColor: colors.tech }]}
                  />
                )}
                <View style={styles.iconContainer}>
                  <Text
                    style={[
                      styles.tabIcon,
                      { color: active ? colors.tech : colors.textSecondary },
                    ]}
                  >
                    {TAB_ICONS[tab]}
                  </Text>
                  {isAlarmsTab && unackCount > 0 && (
                    <View style={[styles.badge, { backgroundColor: colors.red }]}>
                      <Text style={styles.badgeText}>{unackCount}</Text>
                    </View>
                  )}
                </View>
                <Text
                  style={[
                    styles.tabLabel,
                    {
                      color: active ? colors.tech : colors.textSecondary,
                      fontFamily: active ? FONT.semibold : FONT.medium,
                      fontWeight: active ? '600' : '500',
                    },
                  ]}
                  numberOfLines={1}
                >
                  {TAB_LABELS[tab]}
                </Text>
              </Pressable>
            );
          })}
        </View>
      )}
    </SafeAreaView>
  );
}

export default function App() {
  useFonts({
    BeVietnamPro_400Regular,
    BeVietnamPro_500Medium,
    BeVietnamPro_600SemiBold,
    BeVietnamPro_700Bold,
  });

  return (
    <ThemeProvider>
      <SafeAreaProvider>
        <AppShell />
      </SafeAreaProvider>
    </ThemeProvider>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  tabs: {
    height: 62,
    borderTopWidth: 1,
    flexDirection: 'row',
  },
  tab: {
    flex: 1,
    minWidth: 0,
    minHeight: 48,
    justifyContent: 'center',
    alignItems: 'center',
    paddingVertical: 6,
    position: 'relative',
  },
  activeIndicator: {
    position: 'absolute',
    top: 0,
    left: '20%',
    right: '20%',
    height: 2.5,
    borderBottomLeftRadius: 2,
    borderBottomRightRadius: 2,
  },
  iconContainer: {
    position: 'relative',
    alignItems: 'center',
    justifyContent: 'center',
  },
  tabIcon: {
    fontSize: 17,
    lineHeight: 20,
  },
  badge: {
    position: 'absolute',
    top: -4,
    right: -11,
    borderRadius: 999,
    paddingHorizontal: 5,
    paddingVertical: 1,
    minWidth: 16,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  tabLabel: {
    fontSize: 12,
    marginTop: 2,
  },
});
