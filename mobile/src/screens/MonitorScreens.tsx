import React, { useEffect, useState } from 'react';
import {
  Alert,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Inclinometer } from '../components/Inclinometer';
import { MotionChart } from '../components/MotionChart';
import { MobileMaiChart } from '../components/MobileMaiChart';
import {
  ActionBtn,
  MetricCard,
  Page,
  Panel,
  Pill,
  RiskBar,
  Severity,
  StatusBanner,
  StatusPill,
  TwoCol,
} from '../components/UI';
import { fakeWavePoints } from '../data/mock';
import { FONT, getSeverityColors, SHADOWS, useTheme } from '../theme';
import { ScreenProps } from '../types/domain';
import {
  getAlarmLevelNameVi,
  getRFClassNameVi,
  getRoleNameVi,
  getScenarioNameVi,
} from '../i18n/vi';

const fmtAngle = (n: number | null, suffix = '°') =>
  n === null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(1)}${suffix}`;

/**
 * MÀN HÌNH 1: TỔNG QUAN VẬN HÀNH (Overview)
 * Tập trung trạng thái an toàn, MAI, kết nối, thông tin tàu và cảnh báo cần xử lý.
 */
export function OverviewScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const t = data.telemetry;
  const raisedAlarms = data.alarms.filter((a) => a.status === 'RAISED');
  const ackedAlarms = data.alarms.filter((a) => a.status === 'ACKED');
  const isConnected = !!t.sensor_ok;
  const maiVal = t.mai ?? 0;

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={t.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      unackCount={raisedAlarms.length}
      title="Tổng quan vận hành"
      subtitle="Theo dõi trạng thái tàu, kết nối cảm biến, chỉ số MAI và cảnh báo ca trực"
    >
      {/* Status Banner */}
      <StatusBanner
        level={t.alarm_level}
        title={
          t.connection === 'OFFLINE'
            ? 'Mất kết nối thiết bị'
            : t.connection === 'SENSOR_FAULT'
            ? 'Lỗi cảm biến I2C'
            : t.alarm_level === 'CRITICAL'
            ? 'Cảnh báo mức nguy cấp'
            : t.alarm_level === 'WARNING'
            ? 'Cảnh báo dao động lớn'
            : t.alarm_level === 'CAUTION'
            ? 'Mức cảnh giác'
            : 'Trạng thái bình thường'
        }
        desc={
          t.connection === 'OFFLINE'
            ? 'Mất tín hiệu viễn trắc từ thiết bị. Không suy diễn trạng thái bình thường.'
            : t.connection === 'SENSOR_FAULT'
            ? 'Lỗi đọc cảm biến MPU6050 qua bus I2C. Dữ liệu góc nghiêng tạm thời không khả dụng.'
            : t.alarm_level === 'CRITICAL'
            ? 'Biên độ lắc ngang tăng nhanh hoặc vượt ngưỡng an toàn. Kiểm tra ổn định tàu ngay.'
            : t.alarm_level === 'WARNING'
            ? 'Nghiêng lệch kéo dài hoặc lắc lớn. Lưu ý nguy cơ xô lệch hàng hóa.'
            : 'Chuyển động tàu nằm trong giới hạn an toàn.'
        }
        elapsed={`T+${t.t_sim_s}s`}
      />

      {/* 2x2 Summary KPIs (Strict Web Color & Hierarchy Rules) */}
      <TwoCol>
        <MetricCard
          label="Mức cảnh báo tàu"
          value={getAlarmLevelNameVi(t.alarm_level)}
          subtext={
            t.alarm_level === 'CRITICAL'
              ? 'Vượt ngưỡng giới hạn'
              : t.alarm_level === 'WARNING'
              ? 'Biên độ lắc lớn'
              : 'Trong giới hạn an toàn'
          }
          color={
            t.alarm_level === 'CRITICAL'
              ? colors.red
              : t.alarm_level === 'WARNING' || t.alarm_level === 'CAUTION'
              ? colors.amber
              : colors.green
          }
        />
        <MetricCard
          label="Trạng thái thiết bị"
          value={
            isConnected
              ? 'Đang kết nối'
              : data.scenario === 'OFFLINE'
              ? 'Mất kết nối'
              : 'Lỗi cảm biến'
          }
          subtext={isConnected ? 'MPU6050 hoạt động tốt' : 'Mất tín hiệu viễn trắc'}
          color={
            isConnected
              ? colors.green
              : data.scenario === 'OFFLINE'
              ? colors.red
              : colors.amber
          }
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="Chỉ số bất thường MAI"
          value={isConnected && t.mai !== null ? `${t.mai} / 100` : '—'}
          subtext={
            !isConnected
              ? 'Chưa có dữ liệu'
              : maiVal >= 70
              ? 'Nguy cấp (≥ 70)'
              : maiVal >= 35
              ? 'Cảnh giác (35–70)'
              : 'Bình thường (< 35)'
          }
          color={
            !isConnected
              ? colors.muted
              : maiVal >= 70
              ? colors.red
              : maiVal >= 35
              ? colors.amber
              : colors.green
          }
        />
        <MetricCard
          label="Cảnh báo ca trực"
          value={`${raisedAlarms.length} đang mở`}
          subtext={
            raisedAlarms.length === 0
              ? 'Hệ thống an toàn'
              : `${ackedAlarms.length} đã xác nhận`
          }
          color={raisedAlarms.length > 0 ? colors.red : colors.green}
        />
      </TwoCol>

      {/* Motion & MAI Summary Panel */}
      <Panel title="Tóm tắt động học thân tàu" tag="Chu kỳ 5s">
        <RiskBar score={t.mai ?? 0} />

        <View style={[styles.kvList, { borderTopColor: colors.borderSubtle }]}>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Góc lắc ngang</Text>
            <Text style={[styles.kvVal, { color: isConnected ? colors.tech : colors.muted }]}>
              {fmtAngle(t.roll_deg)}{' '}
              {isConnected && t.roll_deg !== null
                ? `(${t.roll_deg > 0.1 ? 'Mạn phải' : t.roll_deg < -0.1 ? 'Mạn trái' : 'Cân bằng'})`
                : ''}
            </Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Góc chúi dọc</Text>
            <Text style={[styles.kvVal, { color: isConnected ? colors.amber : colors.muted }]}>
              {fmtAngle(t.pitch_deg)}{' '}
              {isConnected && t.pitch_deg !== null
                ? `(${t.pitch_deg > 0.1 ? 'Ngóc mũi' : t.pitch_deg < -0.1 ? 'Chúi mũi' : 'Mức chuẩn'})`
                : ''}
            </Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Phân loại TinyML</Text>
            <Text
              style={[
                styles.kvVal,
                {
                  color: !isConnected
                    ? colors.muted
                    : t.class_rf === 'NORMAL'
                    ? colors.green
                    : t.class_rf === 'AMPLITUDE_GROWTH' || t.class_rf === 'HIGH_ROLL'
                    ? colors.red
                    : colors.amber,
                },
              ]}
            >
              {getRFClassNameVi(t.class_rf)}
            </Text>
          </View>
        </View>
      </Panel>

      {/* Vessel & Shift Info Panel */}
      <Panel title="Thông số tàu & Ca trực" tag="vessel-demo-01">
        <View style={styles.kvListNoBorder}>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Tên tàu</Text>
            <Text style={[styles.kvVal, { color: colors.title }]}>MV SVMG-01 (IMO-9876543)</Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Kịch bản</Text>
            <Text style={[styles.kvVal, { color: colors.tech }]}>
              {data.scenario} · {getScenarioNameVi(data.scenario)}
            </Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Cấu hình</Text>
            <Text style={[styles.kvVal, { color: colors.title }]}>
              {data.config.profile} (v{data.config.config_version})
            </Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Sĩ quan trực</Text>
            <Text style={[styles.kvVal, { color: colors.title }]}>
              {data.session?.username} ({getRoleNameVi(data.session?.role)})
            </Text>
          </View>
        </View>
      </Panel>

      {/* Actionable Alarms Preview */}
      <Panel
        title="Cảnh báo cần xử lý"
        tag={raisedAlarms.length > 0 ? `${raisedAlarms.length} sự kiện` : 'An toàn'}
      >
        {raisedAlarms.length === 0 ? (
          <View
            style={[
              styles.safeBox,
              { backgroundColor: colors.greenContainerBg, borderColor: colors.green },
            ]}
          >
            <Text style={[styles.safeBoxText, { color: colors.green }]}>
              ✓ Không có cảnh báo nào đang chờ tiếp nhận.
            </Text>
          </View>
        ) : (
          <View style={{ gap: 10 }}>
            {raisedAlarms.slice(0, 2).map((a) => (
              <View
                key={a.id}
                style={[
                  styles.miniAlarmRow,
                  { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
                ]}
              >
                <View style={{ flex: 1, gap: 4 }}>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <Severity level={a.level} />
                    <Text style={[styles.miniAlarmId, { color: colors.textSecondary }]}>
                      {a.id}
                    </Text>
                  </View>
                  <Text style={[styles.miniAlarmTitle, { color: colors.title }]}>{a.title}</Text>
                </View>
                <Pressable
                  onPress={() => {
                    actions.selectAlarm(a.id);
                    actions.go('AlarmDetail');
                  }}
                  style={[styles.miniDetailBtn, { borderColor: colors.borderSubtle }]}
                  accessibilityRole="button"
                >
                  <Text style={[styles.miniDetailText, { color: colors.tech }]}>Xem ›</Text>
                </Pressable>
              </View>
            ))}
          </View>
        )}
      </Panel>

      {/* Quick Navigation */}
      <ActionBtn
        label="Mở Giám sát chuyển động →"
        onPress={() => actions.go('LiveMotion')}
        tone="primary"
      />
    </Page>
  );
}

/**
 * MÀN HÌNH 2: GIÁM SÁT CHUYỂN ĐỘNG (Live Motion)
 */
export function LiveMotionScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const [bufferSec, setBufferSec] = useState<'10s' | '30s' | '1m' | '5m'>('30s');
  const [touchedMotion, setTouchedMotion] = useState<{
    roll: number;
    pitch: number;
    idx: number;
  } | null>(null);
  const [isFrozen, setIsFrozen] = useState(false);
  const [frozenSeq, setFrozenSeq] = useState(data.telemetry.seq);
  const t = data.telemetry;

  const sampleCount =
    bufferSec === '10s' ? 24 : bufferSec === '30s' ? 48 : bufferSec === '1m' ? 80 : 120;
  const activeSeq = isFrozen ? frozenSeq : t.seq;
  const samples = fakeWavePoints(data.scenario, activeSeq, sampleCount);

  const toggleFreeze = () => {
    if (!isFrozen) {
      setFrozenSeq(t.seq);
      setIsFrozen(true);
    } else {
      setIsFrozen(false);
    }
  };

  const maiVal = t.mai ?? 0;

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={t.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="Giám sát chuyển động"
      subtitle="Đồ thị dao động Roll/Pitch, mô hình tàu và đối chiếu TinyML thời gian thực"
    >
      {/* 1. 4 KPIs in 2x2 Grid (Matched with Web) */}
      <TwoCol>
        <MetricCard
          label="Góc lắc ngang tức thời"
          value={fmtAngle(t.roll_deg)}
          subtext={
            t.sensor_ok && t.roll_deg !== null
              ? t.roll_deg > 0.1
                ? 'Mạn phải'
                : t.roll_deg < -0.1
                ? 'Mạn trái'
                : 'Cân bằng'
              : 'Mất dữ liệu'
          }
          color={
            !t.sensor_ok
              ? colors.muted
              : Math.abs(t.roll_deg || 0) >= data.config.roll_warning_deg
              ? colors.red
              : colors.tech
          }
        />
        <MetricCard
          label="Góc chúi dọc tức thời"
          value={fmtAngle(t.pitch_deg)}
          subtext={
            t.sensor_ok && t.pitch_deg !== null
              ? t.pitch_deg > 0.1
                ? 'Ngóc mũi'
                : t.pitch_deg < -0.1
                ? 'Chúi mũi'
                : 'Mức chuẩn'
              : 'Mất dữ liệu'
          }
          color={!t.sensor_ok ? colors.muted : colors.amber}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="Chỉ số bất thường MAI"
          value={t.sensor_ok && t.mai !== null ? `${t.mai} / 100` : '—'}
          subtext={
            !t.sensor_ok
              ? 'Không khả dụng'
              : maiVal >= 70
              ? 'Nguy cấp'
              : maiVal >= 35
              ? 'Cảnh giác'
              : 'Bình thường'
          }
          color={
            !t.sensor_ok
              ? colors.muted
              : maiVal >= 70
              ? colors.red
              : maiVal >= 35
              ? colors.amber
              : colors.green
          }
        />
        <MetricCard
          label="Nhận dạng TinyML"
          value={t.sensor_ok ? getRFClassNameVi(t.class_rf) : 'Mất tín hiệu'}
          subtext="23 đặc trưng đầu vào"
          color={
            !t.sensor_ok
              ? colors.red
              : t.class_rf === 'NORMAL'
              ? colors.green
              : t.class_rf === 'AMPLITUDE_GROWTH' || t.class_rf === 'HIGH_ROLL'
              ? colors.red
              : colors.amber
          }
        />
      </TwoCol>

      {/* 2. Vessel Motion Visualizer */}
      <Inclinometer
        rollDeg={t.roll_deg}
        pitchDeg={t.pitch_deg}
        mai={t.mai}
        alarmLevel={t.alarm_level}
        scenario={data.scenario}
        classRf={t.class_rf}
        sensorOk={t.sensor_ok}
        warningDeg={data.config.roll_warning_deg}
        tripDeg={data.config.roll_trip_deg}
        touchedSample={touchedMotion}
      />

      {/* 3. Oscilloscope Chart with Buffer & Freeze */}
      <Panel title="Biểu đồ dao động" tag={isFrozen ? 'Đang đóng băng' : `Cửa sổ ${bufferSec}`}>
        <View style={styles.chartControlsRow}>
          <View style={styles.bufferPillRow}>
            {(['10s', '30s', '1m', '5m'] as const).map((b) => {
              const active = bufferSec === b;
              return (
                <Pressable
                  key={b}
                  onPress={() => setBufferSec(b)}
                  style={[
                    styles.bufferBtn,
                    {
                      backgroundColor: active ? colors.primaryContainer : colors.panel2,
                      borderColor: active ? colors.primaryContainer : colors.borderSubtle,
                    },
                  ]}
                  accessibilityRole="button"
                >
                  <Text
                    style={[
                      styles.bufferBtnText,
                      { color: active ? '#FFFFFF' : colors.textSecondary },
                    ]}
                  >
                    {b}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          <Pressable
            onPress={toggleFreeze}
            style={[
              styles.freezeBtn,
              {
                backgroundColor: isFrozen ? colors.amber : colors.panel2,
                borderColor: isFrozen ? colors.amber : colors.borderSubtle,
              },
            ]}
            accessibilityRole="button"
          >
            <Text
              style={[
                styles.freezeBtnText,
                { color: isFrozen ? '#FFFFFF' : colors.title },
              ]}
            >
              {isFrozen ? '▶ Tiếp tục' : '❚❚ Đóng băng'}
            </Text>
          </Pressable>
        </View>

        <MotionChart
          roll={samples.roll}
          pitch={samples.pitch}
          height={185}
          offline={!t.sensor_ok}
          warningDeg={data.config.roll_warning_deg}
          tripDeg={data.config.roll_trip_deg}
          onTouchSample={setTouchedMotion}
        />
      </Panel>

      {/* 4. MAI Timeline */}
      <Panel title="Xu hướng chỉ số bất thường MAI" tag="Theo dõi TinyML">
        <MobileMaiChart
          currentMai={t.sensor_ok ? (t.mai ?? 14) : 0}
          alarms={data.alarms}
          thresholdCaution={35}
          thresholdCritical={Math.round(data.config.mai_alert_threshold * 100)}
          height={150}
          onSelectAlarm={(id) => {
            actions.selectAlarm(id);
            actions.go('AlarmDetail');
          }}
          offline={!t.sensor_ok}
        />
      </Panel>

      {/* 5. Shadow Comparison */}
      <Panel title="Đối chiếu mô hình TinyML" tag="Random Forest vs Baseline B">
        <View style={styles.kvListNoBorder}>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>
              Random Forest (Chính)
            </Text>
            <Text style={[styles.kvVal, { color: colors.tech }]}>
              {getRFClassNameVi(t.class_rf)}
            </Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>
              Baseline B (Đối chiếu)
            </Text>
            <Text style={[styles.kvVal, { color: colors.amber }]}>
              {getRFClassNameVi(t.class_baseline_b)}
            </Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Độ đồng thuận</Text>
            <Text
              style={[
                styles.kvVal,
                {
                  color: !t.sensor_ok
                    ? colors.muted
                    : t.class_rf === t.class_baseline_b
                    ? colors.green
                    : colors.amber,
                },
              ]}
            >
              {!t.sensor_ok
                ? 'Không khả dụng'
                : t.class_rf === t.class_baseline_b
                ? '✓ Đồng thuận'
                : '⚠ Bất đồng'}
            </Text>
          </View>
        </View>
      </Panel>
    </Page>
  );
}

/**
 * MÀN HÌNH 3: QUẢN LÝ CẢNH BÁO (Alarms)
 */
export function AlarmsScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const sevColors = getSeverityColors(colors);
  const [filter, setFilter] = useState<'ACTIVE' | 'ALL' | 'CRITICAL' | 'WARNING'>('ACTIVE');

  // Sort RAISED alarms to the top so urgent events are always visible first
  const priorityOrder: Record<string, number> = {
    CRITICAL: 0,
    WARNING: 1,
    CAUTION: 2,
    NORMAL: 3,
  };
  const sortedAlarms = [...data.alarms].sort((a, b) => {
    if (a.status === 'RAISED' && b.status !== 'RAISED') return -1;
    if (a.status !== 'RAISED' && b.status === 'RAISED') return 1;
    return (priorityOrder[a.level] ?? 9) - (priorityOrder[b.level] ?? 9);
  });

  const filteredAlarms = sortedAlarms.filter((a) => {
    if (filter === 'ACTIVE') return a.status === 'RAISED';
    if (filter === 'CRITICAL') return a.level === 'CRITICAL';
    if (filter === 'WARNING') return a.level === 'WARNING';
    return true;
  });

  const raisedCount = data.alarms.filter((a) => a.status === 'RAISED').length;
  const ackedCount = data.alarms.filter((a) => a.status === 'ACKED').length;
  const clearedCount = data.alarms.filter((a) => a.status === 'CLEARED').length;
  const critCount = data.alarms.filter((a) => a.level === 'CRITICAL' && a.status === 'RAISED').length;

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      unackCount={raisedCount}
      title="Quản lý cảnh báo"
      subtitle="Theo dõi, tiếp nhận và kiểm tra sự cố dao động vượt ngưỡng"
    >
      {/* 2x2 Summary Cards */}
      <TwoCol>
        <MetricCard
          label="Đang phát"
          value={`${raisedCount} sự kiện`}
          subtext={critCount > 0 ? `${critCount} mức nguy cấp` : 'Chờ tiếp nhận'}
          color={raisedCount > 0 ? colors.red : colors.green}
        />
        <MetricCard
          label="Đã xác nhận"
          value={`${ackedCount} sự kiện`}
          subtext="Sĩ quan đã tiếp nhận"
          color={ackedCount > 0 ? colors.amber : colors.muted}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="Đã kết thúc"
          value={`${clearedCount} sự kiện`}
          subtext="Đã ổn định"
          color={colors.green}
        />
        <MetricCard
          label="Tổng trong phiên"
          value={`${data.alarms.length} sự kiện`}
          subtext="Nhật ký ca trực"
          color={colors.tech}
        />
      </TwoCol>

      {/* Interactive MAI Timeline */}
      <Panel title="Xu hướng chỉ số bất thường MAI" tag="Cảnh báo theo mốc">
        <MobileMaiChart
          currentMai={data.telemetry.sensor_ok ? (data.telemetry.mai ?? 14) : 0}
          alarms={data.alarms}
          thresholdCaution={35}
          thresholdCritical={Math.round(data.config.mai_alert_threshold * 100)}
          height={150}
          onSelectAlarm={(id) => {
            actions.selectAlarm(id);
            actions.go('AlarmDetail');
          }}
          offline={!data.telemetry.sensor_ok}
        />
      </Panel>

      {/* Filter Pills */}
      <View style={styles.filterPillsRow}>
        {(
          [
            { key: 'ACTIVE', label: `Đang phát (${raisedCount})` },
            { key: 'ALL', label: `Tất cả (${data.alarms.length})` },
            {
              key: 'CRITICAL',
              label: `Nguy cấp (${data.alarms.filter((a) => a.level === 'CRITICAL').length})`,
            },
            {
              key: 'WARNING',
              label: `Cảnh báo (${data.alarms.filter((a) => a.level === 'WARNING').length})`,
            },
          ] as const
        ).map((f) => {
          const active = filter === f.key;
          return (
            <Pressable
              key={f.key}
              onPress={() => setFilter(f.key)}
              style={[
                styles.filterBtn,
                {
                  backgroundColor: active ? colors.primaryContainer : colors.panel,
                  borderColor: active ? colors.primaryContainer : colors.borderSubtle,
                },
              ]}
              accessibilityRole="button"
            >
              <Text
                style={[
                  styles.filterBtnText,
                  { color: active ? '#FFFFFF' : colors.title },
                ]}
              >
                {f.label}
              </Text>
            </Pressable>
          );
        })}
      </View>

      {/* Alarm Cards */}
      <View style={{ gap: 12 }}>
        {filteredAlarms.length === 0 ? (
          <View
            style={[
              styles.emptyAlarmWell,
              { backgroundColor: colors.panel, borderColor: colors.border },
            ]}
          >
            <Text style={[styles.emptyAlarmText, { color: colors.textSecondary }]}>
              Không có cảnh báo nào trong bộ lọc này.
            </Text>
          </View>
        ) : (
          filteredAlarms.map((alarm) => {
            const color = sevColors[alarm.level] ?? colors.muted;
            const isRaised = alarm.status === 'RAISED';

            return (
              <View
                key={alarm.id}
                style={[
                  styles.alarmCard,
                  {
                    backgroundColor: colors.panel,
                    borderColor: colors.border,
                    borderLeftColor: color,
                  },
                  SHADOWS.card,
                ]}
              >
                <View style={styles.cardTopRow}>
                  <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
                    <Severity level={alarm.level} />
                    <StatusPill status={alarm.status} />
                  </View>
                  <Text style={[styles.alarmIdText, { color: colors.textSecondary }]}>
                    {alarm.id}
                  </Text>
                </View>

                <Text style={[styles.alarmTitle, { color: colors.title }]}>{alarm.title}</Text>
                <Text style={[styles.alarmDesc, { color: colors.textSecondary }]}>
                  {alarm.detail}
                </Text>

                <View
                  style={[
                    styles.peakWell,
                    { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
                  ]}
                >
                  <View style={styles.peakItem}>
                    <Text style={[styles.peakLabel, { color: colors.textSecondary }]}>
                      Thời điểm
                    </Text>
                    <Text style={[styles.peakVal, { color: colors.title }]}>
                      {alarm.utcTime ?? alarm.at}
                    </Text>
                  </View>
                  {alarm.peakVector && (
                    <View style={styles.peakItem}>
                      <Text style={[styles.peakLabel, { color: colors.textSecondary }]}>
                        Biên độ đỉnh
                      </Text>
                      <Text style={[styles.peakVal, { color: colors.tech }]}>
                        {alarm.peakVector}
                      </Text>
                    </View>
                  )}
                  {alarm.anomalyIndex !== undefined && (
                    <View style={styles.peakItem}>
                      <Text style={[styles.peakLabel, { color: colors.textSecondary }]}>MAI</Text>
                      <Text style={[styles.peakVal, { color }]}>
                        {Math.round(alarm.anomalyIndex * 100)} / 100
                      </Text>
                    </View>
                  )}
                </View>

                <View style={styles.cardBtnRow}>
                  <Pressable
                    style={[
                      styles.detailBtn,
                      { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
                    ]}
                    onPress={() => {
                      actions.selectAlarm(alarm.id);
                      actions.go('AlarmDetail');
                    }}
                    accessibilityRole="button"
                  >
                    <Text style={[styles.detailBtnText, { color: colors.title }]}>
                      Chi tiết & Lịch sử ›
                    </Text>
                  </Pressable>

                  {isRaised && (
                    <Pressable
                      style={[styles.ackBtn, { backgroundColor: colors.primaryContainer }]}
                      onPress={() => actions.ackAlarm(alarm.id)}
                      accessibilityRole="button"
                    >
                      <Text style={styles.ackBtnText}>Tiếp nhận (ACK)</Text>
                    </Pressable>
                  )}
                </View>
              </View>
            );
          })
        )}
      </View>
    </Page>
  );
}

/**
 * MÀN HÌNH CHI TIẾT CẢNH BÁO (Alarm Detail)
 */
export function AlarmDetailScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const sevColors = getSeverityColors(colors);
  const alarm =
    data.alarms.find((x) => x.id === actions.selectedAlarmId) ?? data.alarms[0];

  const [note, setNote] = useState(alarm?.notes ?? '');

  useEffect(() => {
    setNote(alarm?.notes ?? '');
  }, [alarm?.id]);

  if (!alarm) {
    return (
      <Page onBack={actions.back} title="Chi tiết cảnh báo">
        <Text style={{ color: colors.title, padding: 16 }}>Không tìm thấy cảnh báo.</Text>
      </Page>
    );
  }

  const color = sevColors[alarm.level] ?? colors.muted;
  const isRaised = alarm.status === 'RAISED';
  const isCleared = alarm.status === 'CLEARED';
  const frozenSamples = fakeWavePoints('S3', 38, 48);

  const handleMute = () => {
    if (alarm.level === 'CRITICAL') {
      Alert.alert(
        'Từ chối tắt còi',
        'Theo quy chuẩn an toàn hàng hải, cảnh báo mức Nguy cấp (CRITICAL) không cho phép tạm tắt còi.'
      );
      return;
    }
    actions.muteAlarm(alarm.id);
    Alert.alert('Đã tạm tắt âm', `Đã tạm ngắt còi cho cảnh báo ${alarm.id} trong tối đa 300 giây.`);
  };

  const handleAck = () => {
    actions.ackAlarm(alarm.id);
    Alert.alert('Đã tiếp nhận', `Sĩ quan đã tiếp nhận sự kiện ${alarm.id}.`);
  };

  const handleSaveNote = () => {
    actions.updateAlarmNote(alarm.id, note);
    Alert.alert('Đã lưu ghi chú', 'Nhật ký sĩ quan đã được cập nhật.');
  };

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      onBack={actions.back}
      title={`Chi tiết cảnh báo ${alarm.id}`}
      subtitle="Báo cáo sự cố và thao tác tiếp nhận an toàn"
    >
      <Panel>
        <View style={styles.detailHeader}>
          <Severity level={alarm.level} />
          <StatusPill status={alarm.status} />
        </View>

        <Text style={[styles.detailTitle, { color: colors.title }]}>{alarm.title}</Text>
        <Text style={[styles.detailDesc, { color: colors.textSecondary }]}>{alarm.detail}</Text>

        <TwoCol>
          <View
            style={[
              styles.metaCell,
              { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
            ]}
          >
            <Text style={[styles.metaCellLabel, { color: colors.textSecondary }]}>Thiết bị</Text>
            <Text style={[styles.metaCellVal, { color: colors.title }]}>MV SVMG-01</Text>
            <Text style={[styles.metaCellSub, { color: colors.textSecondary }]}>MPU6050 Mast #1</Text>
          </View>
          <View
            style={[
              styles.metaCell,
              { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
            ]}
          >
            <Text style={[styles.metaCellLabel, { color: colors.textSecondary }]}>Thời điểm</Text>
            <Text style={[styles.metaCellVal, { color: colors.title }]}>
              {alarm.utcTime ?? alarm.at}
            </Text>
            <Text style={[styles.metaCellSub, { color: colors.green }]}>● Đồng bộ biên</Text>
          </View>
        </TwoCol>
      </Panel>

      <Panel title="Dữ liệu sóng tại thời điểm kích hoạt" tag="30s quanh sự kiện">
        <MotionChart roll={frozenSamples.roll} pitch={frozenSamples.pitch} height={160} />
      </Panel>

      <Panel title="Thao tác của sĩ quan trực ca">
        <Text style={[styles.remarksLabel, { color: colors.title }]}>Ghi chú nhật ký ca trực</Text>
        <View style={styles.noteInputRow}>
          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder="Ví dụ: Đã đổi hướng 15° sang mạn trái..."
            placeholderTextColor={colors.muted}
            style={[
              styles.noteInput,
              {
                backgroundColor: colors.panel2,
                borderColor: colors.borderSubtle,
                color: colors.title,
              },
            ]}
          />
          <Pressable
            onPress={handleSaveNote}
            style={[
              styles.saveNoteBtn,
              { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
            ]}
            accessibilityRole="button"
          >
            <Text style={[styles.saveNoteBtnText, { color: colors.tech }]}>Lưu</Text>
          </Pressable>
        </View>

        <View style={{ gap: 10, marginTop: 4 }}>
          <ActionBtn
            label={isRaised ? 'Tiếp nhận cảnh báo (ACK)' : 'Đã tiếp nhận'}
            onPress={handleAck}
            disabled={!isRaised}
            tone={isRaised ? 'primary' : 'neutral'}
          />

          <ActionBtn
            label={
              alarm.level === 'CRITICAL'
                ? 'Tạm tắt âm (Bị khóa với mức Nguy cấp)'
                : alarm.muted
                ? 'Đã tạm tắt âm (≤ 300s)'
                : 'Tạm tắt âm cảnh báo (≤ 300s)'
            }
            onPress={handleMute}
            disabled={alarm.level === 'CRITICAL' || isCleared}
            tone="ghost"
          />
        </View>

        <Text style={[styles.actionWarningNote, { color: colors.textSecondary }]}>
          Tiếp nhận (ACK) xác nhận sĩ quan đã xử lý thông tin; trạng thái chỉ kết thúc khi tàu hết dao động vượt ngưỡng.
        </Text>
      </Panel>
    </Page>
  );
}

const styles = StyleSheet.create({
  kvList: {
    borderTopWidth: 1,
    paddingTop: 10,
    marginTop: 6,
    gap: 8,
  },
  kvListNoBorder: {
    gap: 8,
  },
  kvRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
    flexWrap: 'wrap',
  },
  kvKey: {
    fontSize: 13,
    fontFamily: FONT.regular,
  },
  kvVal: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  safeBox: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
  },
  safeBoxText: {
    fontSize: 14,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  miniAlarmRow: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  miniAlarmId: {
    fontSize: 12,
    fontFamily: FONT.medium,
  },
  miniAlarmTitle: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  miniDetailBtn: {
    minHeight: 40,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderRadius: 8,
    justifyContent: 'center',
  },
  miniDetailText: {
    fontSize: 13,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  chartControlsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
  },
  bufferPillRow: {
    flexDirection: 'row',
    gap: 6,
  },
  bufferBtn: {
    minHeight: 36,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  bufferBtnText: {
    fontSize: 13,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  freezeBtn: {
    minHeight: 36,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  freezeBtnText: {
    fontSize: 13,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  filterPillsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  filterBtn: {
    minHeight: 44,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  filterBtnText: {
    fontSize: 13,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  emptyAlarmWell: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
  },
  emptyAlarmText: {
    fontSize: 14,
    fontFamily: FONT.regular,
  },
  alarmCard: {
    borderWidth: 1,
    borderLeftWidth: 4,
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  cardTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  alarmIdText: {
    fontSize: 12,
    fontFamily: FONT.medium,
  },
  alarmTitle: {
    fontSize: 17,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  alarmDesc: {
    fontSize: 14,
    fontFamily: FONT.regular,
    lineHeight: 20,
  },
  peakWell: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: 10,
    borderWidth: 1,
    borderRadius: 10,
    padding: 10,
  },
  peakItem: {
    gap: 2,
  },
  peakLabel: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  peakVal: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  cardBtnRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 4,
  },
  detailBtn: {
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 10,
  },
  detailBtnText: {
    fontSize: 14,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  ackBtn: {
    minHeight: 44,
    paddingHorizontal: 16,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ackBtnText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  detailHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  detailTitle: {
    fontSize: 18,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  detailDesc: {
    fontSize: 14,
    fontFamily: FONT.regular,
    lineHeight: 20,
  },
  metaCell: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    gap: 3,
  },
  metaCellLabel: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  metaCellVal: {
    fontSize: 15,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  metaCellSub: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  remarksLabel: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  noteInputRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },
  noteInput: {
    flex: 1,
    minHeight: 46,
    borderWidth: 1,
    borderRadius: 10,
    paddingHorizontal: 12,
    fontSize: 14,
    fontFamily: FONT.regular,
  },
  saveNoteBtn: {
    minHeight: 46,
    paddingHorizontal: 16,
    borderWidth: 1,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveNoteBtnText: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  actionWarningNote: {
    fontSize: 12,
    fontFamily: FONT.regular,
    lineHeight: 17,
  },
});
