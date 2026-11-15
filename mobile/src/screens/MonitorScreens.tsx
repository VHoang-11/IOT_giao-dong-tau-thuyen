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
  StatusBanner,
  TwoCol,
} from '../components/UI';
import { fakeWavePoints } from '../data/mock';
import { C, SEVERITY_COLORS, SHADOWS } from '../theme';
import { Alarm, AlarmLevel, ScreenProps } from '../types/domain';

const fmtAngle = (n: number | null, suffix = '°') =>
  n === null ? '—' : `${n > 0 ? '+' : ''}${n.toFixed(1)}${suffix}`;

export function OverviewScreen({ data, actions }: ScreenProps) {
  const t = data.telemetry;
  const samples = fakeWavePoints(data.scenario, t.seq, 44);
  const unackAlarms = data.alarms.filter((a) => a.status === 'RAISED').length;

  const rollDir =
    t.roll_deg === null
      ? ''
      : t.roll_deg < -0.1
      ? 'Port'
      : t.roll_deg > 0.1
      ? 'Stbd'
      : 'Even Keel';

  const pitchDir =
    t.pitch_deg === null
      ? ''
      : t.pitch_deg > 0.1
      ? 'Bow Up'
      : t.pitch_deg < -0.1
      ? 'Bow Down'
      : 'Level';

  const maiNorm = t.mai !== null ? t.mai / 100 : 0;
  const maiRiskText =
    maiNorm >= 0.7
      ? 'CRITICAL RISK'
      : maiNorm >= 0.35
      ? 'ELEVATED RISK'
      : 'NORMAL RISK';

  return (
    <Page
      vesselName="VESSEL DEMO 01"
      utcTime={t.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      unackCount={unackAlarms}
    >
      {/* Escalation Status Banner */}
      <StatusBanner
        level={t.alarm_level}
        title={
          t.connection === 'OFFLINE'
            ? 'OFFLINE — MẤT KẾT NỐI'
            : t.connection === 'SENSOR_FAULT'
            ? 'SENSOR FAULT — LỖI CẢM BIẾN I2C'
            : t.alarm_level === 'CRITICAL'
            ? 'CẢNH BÁO MỨC ĐỘ NGUY CẤP (CRITICAL)'
            : t.alarm_level === 'WARNING'
            ? 'CẢNH BÁO MỨC ĐỘ 2 (WARNING)'
            : t.alarm_level === 'CAUTION'
            ? 'CẢNH BÁO MỨC ĐỘ 1 (CAUTION)'
            : 'HỆ THỐNG TRẠNG THÁI BÌNH THƯỜNG'
        }
        desc={
          t.connection === 'OFFLINE'
            ? 'Mất tín hiệu telemetry từ thiết bị. Không suy diễn trạng thái bình thường.'
            : t.connection === 'SENSOR_FAULT'
            ? 'Lỗi đọc cảm biến MPU6050 qua bus I2C. Dữ liệu góc nghiêng không khả dụng.'
            : t.alarm_level === 'CRITICAL'
            ? 'Biên độ lắc ngang tăng nhanh hoặc vượt ngưỡng an toàn. Kiểm tra ngay ổn định tàu!'
            : t.alarm_level === 'WARNING'
            ? 'Nghiêng lệch góc tĩnh kéo dài hoặc lắc lớn. Chú ý nguy cơ xô lệch tải trọng.'
            : 'Động học tàu nằm trong giới hạn an toàn Baseline B đã hiệu chuẩn.'
        }
        elapsed={`T+${t.t_sim_s}s`}
      />

      {/* AI Motion Classification Card */}
      <Panel title="EDGE AI MOTION CLASSIFIER" tag="INFERENCE WELL">
        <View style={styles.aiGrid}>
          {/* Left Score Box */}
          <View style={styles.aiScoreBox}>
            <Text style={styles.aiScoreLabel}>CLASSIFIER SCORE</Text>
            <View style={styles.aiScoreValRow}>
              <Text
                style={[
                  styles.aiScoreVal,
                  {
                    color:
                      maiNorm >= 0.7
                        ? C.red
                        : maiNorm >= 0.35
                        ? C.amber
                        : C.green,
                  },
                ]}
              >
                {t.mai !== null ? maiNorm.toFixed(2) : '—'}
              </Text>
              <Text style={styles.aiScoreUnit}>MAI</Text>
            </View>
            <View
              style={[
                styles.aiRiskPill,
                {
                  borderColor:
                    maiNorm >= 0.7
                      ? C.red
                      : maiNorm >= 0.35
                      ? C.amber
                      : C.green,
                },
              ]}
            >
              <Text
                style={[
                  styles.aiRiskText,
                  {
                    color:
                      maiNorm >= 0.7
                        ? C.red
                        : maiNorm >= 0.35
                        ? C.amber
                        : C.green,
                  },
                ]}
              >
                {t.sensor_ok ? maiRiskText : 'NO SENSOR'}
              </Text>
            </View>
          </View>

          {/* Right State Box */}
          <View style={styles.aiStateCol}>
            <Text style={styles.aiStateLabel}>STATE INFERENCE:</Text>
            <View
              style={[
                styles.aiStateBadge,
                {
                  borderColor:
                    t.class_rf === 'AMPLITUDE_GROWTH'
                      ? C.red
                      : t.class_rf === 'HIGH_ROLL' || t.class_rf === 'PERSISTENT_OFFSET'
                      ? C.amber
                      : C.cyan,
                },
              ]}
            >
              <Text
                style={[
                  styles.aiStateBadgeText,
                  {
                    color:
                      t.class_rf === 'AMPLITUDE_GROWTH'
                        ? C.red
                        : t.class_rf === 'HIGH_ROLL' || t.class_rf === 'PERSISTENT_OFFSET'
                        ? C.amber
                        : C.cyan,
                  },
                ]}
              >
                {t.class_rf}
              </Text>
            </View>
            <Text style={styles.aiModelText}>
              Model: {t.model_version} • Baseline B: {t.class_baseline_b}
            </Text>
          </View>
        </View>

        {/* Risk Spectrum Bar */}
        <RiskBar score={t.mai ?? 0} />
      </Panel>

      {/* 2D Vessel Motion Visualizer (Compact Overview) */}
      <Inclinometer
        rollDeg={t.roll_deg}
        pitchDeg={t.pitch_deg}
        mai={t.mai}
        alarmLevel={t.alarm_level}
        scenario={data.scenario}
        classRf={t.class_rf}
        sensorOk={t.sensor_ok}
        compact={true}
      />

      {/* Primary Inclinometer Gauges (2 Columns) */}
      <TwoCol>
        <MetricCard
          label="ROLL ANGLE (LẮC NGANG)"
          value={fmtAngle(t.roll_deg)}
          unit={rollDir}
          subtext="Cảm biến GYRO-1"
          color={C.cyan}
        />
        <MetricCard
          label="PITCH ANGLE (LẮC DỌC)"
          value={fmtAngle(t.pitch_deg)}
          unit={pitchDir}
          subtext="Trục dọc thân tàu"
          color={C.amber}
        />
      </TwoCol>

      {/* Live Motion Waveform Preview */}
      <Panel title="MOTION WAVEFORM PREVIEW" tag="ROLL / PITCH LIVE">
        <MotionChart
          roll={samples.roll}
          pitch={samples.pitch}
          height={140}
          offline={!t.sensor_ok}
        />
      </Panel>

      {/* Quick Navigation Action Buttons */}
      <ActionBtn
        label="XEM LIVE MOTION & MÔ HÌNH THÂN TÀU →"
        onPress={() => actions.go('LiveMotion')}
        tone="primary"
      />
      <ActionBtn
        label={`DANH SÁCH CẢNH BÁO (${unackAlarms} CHƯA XÁC NHẬN) →`}
        onPress={() => actions.go('Alarms')}
        tone="secondary"
      />
    </Page>
  );
}

export function LiveMotionScreen({ data, actions }: ScreenProps) {
  const [bufferSec, setBufferSec] = useState<'10s' | '30s' | '1m' | '5m'>('30s');
  const [touchedMotion, setTouchedMotion] = useState<{ roll: number; pitch: number; idx: number } | null>(null);
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

  return (
    <Page
      vesselName="VESSEL DEMO 01"
      utcTime={t.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      onBack={actions.back}
      title="LIVE MOTION TELEMETRY"
      subtitle="MPU6050 6-Axis IMU • Keel Frame Data Stream"
    >
      {/* Time Buffer & Freeze Toolbar */}
      <View style={styles.bufferSelectorBar}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
          <Text style={styles.bufferLabel}>BUFFER:</Text>
          <View style={styles.bufferPillRow}>
            {(['10s', '30s', '1m', '5m'] as const).map((b) => (
              <Pressable
                key={b}
                onPress={() => setBufferSec(b)}
                style={[
                  styles.bufferBtn,
                  bufferSec === b && styles.bufferBtnActive,
                ]}
                accessibilityRole="button"
              >
                <Text
                  style={[
                    styles.bufferBtnText,
                    bufferSec === b && styles.bufferBtnTextActive,
                  ]}
                >
                  {b}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        <Pressable
          onPress={toggleFreeze}
          style={{
            paddingHorizontal: 8,
            paddingVertical: 4,
            borderRadius: 4,
            backgroundColor: isFrozen ? C.amber : '#F0F4F8',
            borderWidth: 1,
            borderColor: isFrozen ? '#B45309' : C.border,
            flexDirection: 'row',
            alignItems: 'center',
            gap: 4,
          }}
          accessibilityRole="button"
        >
          <View
            style={{
              width: 5,
              height: 5,
              borderRadius: 3,
              backgroundColor: isFrozen ? '#FFFFFF' : C.cyan,
            }}
          />
          <Text
            style={{
              color: isFrozen ? '#FFFFFF' : C.text,
              fontSize: 9,
              fontWeight: '800',
              fontFamily: 'monospace',
            }}
          >
            {isFrozen ? 'PAUSED' : 'FREEZE'}
          </Text>
        </Pressable>
      </View>

      {/* Dynamic 2D Vessel Motion Visualizer Schematic */}
      <Panel title="2D VESSEL MOTION VISUALIZER" tag="HULL DYNAMICS">
        <Inclinometer
          rollDeg={touchedMotion ? touchedMotion.roll : t.roll_deg}
          pitchDeg={touchedMotion ? touchedMotion.pitch : t.pitch_deg}
          mai={t.mai}
          alarmLevel={t.alarm_level}
          scenario={data.scenario}
          classRf={t.class_rf}
          sensorOk={t.sensor_ok}
          compact={false}
        />
        <Text style={styles.inclinometerNote}>
          Mô hình động học 2D đồng bộ trực tiếp với vị trí chạm trên biểu đồ bên dưới.
        </Text>
      </Panel>

      {/* Waveform Trace Chart */}
      <Panel title="ROLL & PITCH OSCILLOSCOPE" tag={`${bufferSec.toUpperCase()} TRACE`}>
        <MotionChart
          roll={samples.roll}
          pitch={samples.pitch}
          height={180}
          offline={!t.sensor_ok}
          warningDeg={data.config.roll_warning_deg}
          tripDeg={data.config.roll_trip_deg}
          onTouchSample={setTouchedMotion}
        />
      </Panel>

      {/* Kinematic Numerical Metrics (2x2 Grid) */}
      <TwoCol>
        <MetricCard
          label="ROLL ANGLE (GÓC LẮC)"
          value={fmtAngle(t.roll_deg)}
          unit={t.roll_deg && t.roll_deg < 0 ? 'PORT' : 'STBD'}
          color={C.cyan}
        />
        <MetricCard
          label="PITCH ANGLE (GÓC CHÚI)"
          value={fmtAngle(t.pitch_deg)}
          unit={t.pitch_deg && t.pitch_deg > 0 ? 'BOW UP' : 'BOW DOWN'}
          color={C.amber}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="RMS ROLL (ĐỘ LỆCH CHUẨN)"
          value={fmtAngle(t.rms_roll_deg)}
          subtext="Cửa sổ 60 giây"
        />
        <MetricCard
          label="ANOMALY INDEX (MAI)"
          value={t.mai !== null ? String(t.mai) : '—'}
          unit="/ 100"
          color={t.mai && t.mai >= 70 ? C.red : C.amber}
        />
      </TwoCol>

      {/* Model Shadow Comparison */}
      <Panel title="PHÂN LOẠI MÔ HÌNH VÀ BÓNG RÂM (SHADOW)" tag="EDGE INFERENCE">
        <View style={styles.modelRow}>
          <Text style={styles.modelKey}>Random Forest (Active):</Text>
          <Pill label={t.class_rf} level={t.alarm_level} />
        </View>
        <View style={styles.modelRow}>
          <Text style={styles.modelKey}>Baseline B (Shadow):</Text>
          <Text style={styles.modelVal}>{t.class_baseline_b}</Text>
        </View>
        <View style={styles.modelRow}>
          <Text style={styles.modelKey}>Độ tương thích (Agreement):</Text>
          <Text style={[styles.modelVal, { color: C.green }]}>96.2% PATTERN MATCH</Text>
        </View>
        <Text style={styles.modelDisclaimer}>
          Dữ liệu và nhãn được tính từ bộ sinh tín hiệu giả lập, không phải suy luận AI trực tiếp trên máy khách.
        </Text>
      </Panel>

      <ActionBtn
        label="← QUAY VỀ OVERVIEW"
        onPress={() => actions.go('Overview')}
        tone="neutral"
      />
    </Page>
  );
}

export function AlarmsScreen({ data, actions }: ScreenProps) {
  const [filter, setFilter] = useState<'ACTIVE' | 'ALL' | 'CRITICAL' | 'WARNING'>('ACTIVE');

  const filteredAlarms = data.alarms.filter((a) => {
    if (filter === 'ACTIVE') return a.status === 'RAISED';
    if (filter === 'CRITICAL') return a.level === 'CRITICAL';
    if (filter === 'WARNING') return a.level === 'WARNING';
    return true;
  });

  const critCount = data.alarms.filter((a) => a.level === 'CRITICAL' && a.status === 'RAISED').length;
  const warnCount = data.alarms.filter((a) => a.level === 'WARNING').length;
  const cautionCount = data.alarms.filter((a) => a.level === 'CAUTION').length;
  const normalCount = data.alarms.filter((a) => a.level === 'NORMAL').length;

  return (
    <Page
      vesselName="VESSEL DEMO 01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      unackCount={critCount}
      title="BRIDGE ALARM LOG"
      subtitle="Bảng theo dõi và tiếp nhận cảnh báo buồng lái (IMO A.1021)"
    >
      {/* Annunciator Bento Matrix (4 tiles) */}
      <View style={styles.matrixContainer}>
        <View style={[styles.matrixTile, styles.tileCrit]}>
          <Text style={[styles.matrixTileTag, { color: C.red }]}>CRIT</Text>
          <Text style={[styles.matrixTileVal, { color: C.red }]}>
            {String(critCount).padStart(2, '0')}
          </Text>
          <Text style={[styles.matrixTileSub, { color: C.red }]}>UNACK</Text>
        </View>
        <View style={[styles.matrixTile, styles.tileWarn]}>
          <Text style={[styles.matrixTileTag, { color: C.amber }]}>WARN</Text>
          <Text style={[styles.matrixTileVal, { color: C.amber }]}>
            {String(warnCount).padStart(2, '0')}
          </Text>
          <Text style={[styles.matrixTileSub, { color: C.textSecondary }]}>TOTAL</Text>
        </View>
        <View style={[styles.matrixTile, styles.tileCaution]}>
          <Text style={[styles.matrixTileTag, { color: C.cyan }]}>CAUTION</Text>
          <Text style={[styles.matrixTileVal, { color: C.cyan }]}>
            {String(cautionCount).padStart(2, '0')}
          </Text>
          <Text style={[styles.matrixTileSub, { color: C.muted }]}>SILENT</Text>
        </View>
        <View style={[styles.matrixTile, styles.tileNormal]}>
          <Text style={[styles.matrixTileTag, { color: C.green }]}>NORMAL</Text>
          <Text style={[styles.matrixTileVal, { color: C.green }]}>
            {String(normalCount).padStart(2, '0')}
          </Text>
          <Text style={[styles.matrixTileSub, { color: C.muted }]}>RESOLV</Text>
        </View>
      </View>

      {/* Interactive MAI & Alarm Timeline */}
      <MobileMaiChart
        currentMai={data.telemetry.sensor_ok ? (data.telemetry.mai ?? 14) : 0}
        alarms={data.alarms}
        thresholdCaution={35}
        thresholdCritical={Math.round(data.config.mai_alert_threshold * 100)}
        height={135}
        onSelectAlarm={(id) => {
          actions.selectAlarm(id);
          actions.go('AlarmDetail');
        }}
        offline={!data.telemetry.sensor_ok}
      />

      {/* Filter Segmented Pills */}
      <View style={styles.filterPillsRow}>
        {(
          [
            { key: 'ACTIVE', label: `ACTIVE (${data.alarms.filter((a) => a.status === 'RAISED').length})` },
            { key: 'ALL', label: `ALL (${data.alarms.length})` },
            { key: 'CRITICAL', label: `CRITICAL (${data.alarms.filter((a) => a.level === 'CRITICAL').length})` },
            { key: 'WARNING', label: `WARNING (${data.alarms.filter((a) => a.level === 'WARNING').length})` },
          ] as const
        ).map((f) => (
          <Pressable
            key={f.key}
            onPress={() => setFilter(f.key)}
            style={[styles.filterBtn, filter === f.key && styles.filterBtnActive]}
            accessibilityRole="button"
          >
            <Text style={[styles.filterBtnText, filter === f.key && styles.filterBtnTextActive]}>
              {f.label}
            </Text>
          </Pressable>
        ))}
      </View>

      {/* Alarm Cards List */}
      <View style={styles.alarmList}>
        {filteredAlarms.length === 0 ? (
          <View style={styles.emptyAlarmWell}>
            <Text style={styles.emptyAlarmText}>Không có cảnh báo nào trong mục lọc này.</Text>
          </View>
        ) : (
          filteredAlarms.map((alarm) => {
            const color = SEVERITY_COLORS[alarm.level];
            const isRaised = alarm.status === 'RAISED';

            return (
              <View
                key={alarm.id}
                style={[
                  styles.alarmCard,
                  { borderLeftColor: color },
                  alarm.level === 'CRITICAL' && isRaised
                    ? SHADOWS.criticalGlow
                    : alarm.level === 'WARNING' && isRaised
                    ? SHADOWS.warningGlow
                    : alarm.level === 'CAUTION' && isRaised
                    ? SHADOWS.cautionGlow
                    : null,
                ]}
              >
                {/* Alarm Card Header */}
                <View style={styles.cardTopRow}>
                  <View style={[styles.levelBadge, { backgroundColor: color }]}>
                    <Text style={styles.levelBadgeText}>
                      {alarm.level} {isRaised ? '[UNACK]' : `[${alarm.status}]`}
                    </Text>
                  </View>
                  <Text style={styles.alarmIdText}>ID: {alarm.id}</Text>
                </View>

                {/* Alarm Time & Delta */}
                <View style={styles.cardTimeRow}>
                  <Text style={styles.cardTimeUtc}>🕒 {alarm.utcTime ?? alarm.at}</Text>
                  {alarm.relativeTime && (
                    <Text style={styles.cardTimeRel}>{alarm.relativeTime}</Text>
                  )}
                </View>

                {/* Alarm Title & Description */}
                <Text style={styles.alarmTitle}>{alarm.title}</Text>
                <Text style={styles.alarmDesc}>{alarm.detail}</Text>

                {/* Peak Vector & Anomaly Metric */}
                {(alarm.peakVector || alarm.anomalyIndex) && (
                  <View style={styles.peakWell}>
                    {alarm.peakVector && (
                      <View style={styles.peakItem}>
                        <Text style={styles.peakLabel}>PEAK MOTION VECTOR</Text>
                        <Text style={styles.peakVal}>{alarm.peakVector}</Text>
                      </View>
                    )}
                    {alarm.anomalyIndex !== undefined && (
                      <View style={[styles.peakItem, { alignItems: 'flex-end' }]}>
                        <Text style={styles.peakLabel}>ANOMALY INDEX</Text>
                        <Text style={[styles.peakVal, { color: color }]}>
                          {alarm.anomalyIndex.toFixed(2)} / 1.0
                        </Text>
                      </View>
                    )}
                  </View>
                )}

                {/* Action Buttons */}
                <View style={styles.cardBtnRow}>
                  <Pressable
                    style={styles.detailBtn}
                    onPress={() => {
                      actions.selectAlarm(alarm.id);
                      actions.go('AlarmDetail');
                    }}
                    accessibilityRole="button"
                  >
                    <Text style={styles.detailBtnText}>CHI TIẾT & LỊCH SỬ →</Text>
                  </Pressable>

                  {isRaised && (
                    <Pressable
                      style={[styles.ackBtn, { backgroundColor: color }]}
                      onPress={() => actions.ackAlarm(alarm.id)}
                      accessibilityRole="button"
                    >
                      <Text style={styles.ackBtnText}>TIẾP NHẬN (ACK)</Text>
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

export function AlarmDetailScreen({ data, actions }: ScreenProps) {
  const alarm =
    data.alarms.find((x) => x.id === actions.selectedAlarmId) ?? data.alarms[0];

  const [note, setNote] = useState(alarm?.notes ?? '');

  useEffect(() => {
    setNote(alarm?.notes ?? '');
  }, [alarm?.id]);

  if (!alarm) {
    return (
      <Page onBack={actions.back} title="ALARM DETAIL">
        <Text style={{ color: C.text, padding: 16 }}>Không tìm thấy cảnh báo.</Text>
      </Page>
    );
  }

  const color = SEVERITY_COLORS[alarm.level];
  const isRaised = alarm.status === 'RAISED';
  const isCleared = alarm.status === 'CLEARED';
  const frozenSamples = fakeWavePoints('S3', 38, 48);

  const handleMute = () => {
    if (alarm.level === 'CRITICAL') {
      Alert.alert(
        'REJECTED: KHÔNG THỂ MUTE',
        'Theo quy chuẩn an toàn hàng hải và đề cương dự án, cảnh báo mức CRITICAL tuyệt đối không được tắt còi (MUTE).'
      );
      return;
    }
    actions.muteAlarm(alarm.id);
    Alert.alert('BUZZER MUTED', `Đã tạm ngắt chuông cho sự kiện ${alarm.id} trong tối đa 300 giây.`);
  };

  const handleAck = () => {
    actions.ackAlarm(alarm.id);
    Alert.alert('ACKNOWLEDGED', `Sĩ quan đã tiếp nhận sự kiện ${alarm.id}. Trạng thái chuyển thành ACKED.`);
  };

  const handleSaveNote = () => {
    actions.updateAlarmNote(alarm.id, note);
    Alert.alert('ĐÃ LƯU GHI CHÚ', 'Đã cập nhật nhật ký sĩ quan trực ca vào sự kiện.');
  };

  return (
    <Page
      vesselName="VESSEL DEMO 01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      onBack={actions.back}
      title={`INCIDENT #${alarm.id}`}
      subtitle="Báo cáo chi tiết & thao tác tiếp nhận sự kiện an toàn"
    >
      {/* Alarm Status & Title Card */}
      <Panel>
        <View style={styles.detailHeader}>
          <View style={[styles.levelBadge, { backgroundColor: color }]}>
            <Text style={styles.levelBadgeText}>{alarm.level}</Text>
          </View>
          <View style={styles.statePill}>
            <Text style={styles.statePillText}>{alarm.status}</Text>
          </View>
        </View>

        <Text style={styles.detailTitle}>{alarm.title}</Text>
        <Text style={styles.detailDesc}>{alarm.detail}</Text>

        <View style={styles.detailMetaGrid}>
          <View style={styles.metaCell}>
            <Text style={styles.metaCellLabel}>TÀU & CẢM BIẾN</Text>
            <Text style={styles.metaCellVal}>Vessel Demo 01</Text>
            <Text style={styles.metaCellSub}>MPU6050 Mast #1</Text>
          </View>
          <View style={styles.metaCell}>
            <Text style={styles.metaCellLabel}>THỜI ĐIỂM KÍCH HOẠT</Text>
            <Text style={styles.metaCellVal}>{alarm.utcTime ?? alarm.at}</Text>
            <Text style={[styles.metaCellSub, { color: C.green }]}>● Edge Synced</Text>
          </View>
        </View>
      </Panel>

      {/* Frozen Waveform Capture */}
      <Panel title="FROZEN ROLL WAVEFORM (30s CAPTURE)" tag="INCIDENT WELL">
        <MotionChart
          roll={frozenSamples.roll}
          pitch={frozenSamples.pitch}
          height={160}
        />
        <View style={styles.frozenAnnotationRow}>
          <Text style={styles.frozenAnnotationText}>
            Đỉnh dao động ghi nhận: <Text style={{ color: C.red, fontWeight: '800' }}>24.2° PORT (TRIP)</Text>
          </Text>
          <Text style={styles.frozenSubText}>Chu kỳ lắc: 9.4s</Text>
        </View>
      </Panel>

      {/* Event Timeline Sequence */}
      <Panel title="NHẬT KÝ CHUỖI SỰ KIỆN (TIMELINE AUDIT)" tag="CHRONOLOGICAL">
        <View style={styles.timeline}>
          <View style={styles.timelineItem}>
            <View style={[styles.timelineDot, { backgroundColor: C.muted }]} />
            <Text style={styles.timelineTime}>14:28:01 UTC</Text>
            <Text style={styles.timelineText}>Phát hiện chu kỳ biên độ bất thường đầu tiên (+18.5°)</Text>
          </View>
          <View style={styles.timelineItem}>
            <View style={[styles.timelineDot, { backgroundColor: C.red }]} />
            <Text style={[styles.timelineTime, { color: C.red, fontWeight: '800' }]}>
              14:28:12 UTC [TRIGGER]
            </Text>
            <Text style={[styles.timelineText, { color: C.text, fontWeight: '700' }]}>
              Kích hoạt cảnh báo (Class: AMPLITUDE_GROWTH @ 24.2°)
            </Text>
          </View>
          <View style={styles.timelineItem}>
            <View style={[styles.timelineDot, { backgroundColor: C.amber }]} />
            <Text style={styles.timelineTime}>14:28:15 UTC</Text>
            <Text style={styles.timelineText}>Kích hoạt còi báo động buồng lái (Bridge Buzzer)</Text>
          </View>
          <View style={styles.timelineItem}>
            <View style={[styles.timelineDot, { backgroundColor: C.green }]} />
            <Text style={styles.timelineTime}>14:28:30 UTC</Text>
            <Text style={styles.timelineText}>Đẩy thông báo khẩn cấp tới ứng dụng di động sĩ quan</Text>
          </View>
        </View>
      </Panel>

      {/* Officer Remarks & Action Touchpad */}
      <Panel title="THAO TÁC CỦA SĨ QUAN TRỰC CA" tag="RESPONSE CONSOLE">
        <Text style={styles.remarksLabel}>GHI CHÚ NHẬT KÝ BUỒNG LÁI (OFFICER LOG NOTE)</Text>
        <View style={styles.noteInputRow}>
          <TextInput
            value={note}
            onChangeText={setNote}
            placeholder="Ví dụ: Đã đổi hướng 15° sang mạn trái, giảm tua máy"
            placeholderTextColor={C.muted}
            style={styles.noteInput}
          />
          <Pressable onPress={handleSaveNote} style={styles.saveNoteBtn}>
            <Text style={styles.saveNoteBtnText}>LƯU</Text>
          </Pressable>
        </View>

        <View style={styles.actionBtnStack}>
          <ActionBtn
            label={isRaised ? 'TIẾP NHẬN CẢNH BÁO (ACKNOWLEDGE)' : 'ĐÃ TIẾP NHẬN (ACKED)'}
            onPress={handleAck}
            disabled={!isRaised}
            tone={isRaised ? 'primary' : 'neutral'}
          />

          <ActionBtn
            label={
              alarm.level === 'CRITICAL'
                ? 'TẮT CÒI (MUTE) — BỊ CHẶN VÌ MỨC CRITICAL'
                : alarm.muted
                ? 'ĐÃ TẮT CÒI TẠM THỜI (MUTED ≤300s)'
                : 'TẮT CÒI BUỒNG LÁI (MUTE ≤300s)'
            }
            onPress={handleMute}
            disabled={alarm.level === 'CRITICAL' || isCleared}
            tone="ghost"
          />
        </View>

        <Text style={styles.actionWarningNote}>
          * Lưu ý: Thao tác ACK không đồng nghĩa với CLEARED. Khi mức độ nguy hiểm giảm, hệ thống mới chuyển CLEARED.
        </Text>
      </Panel>
    </Page>
  );
}

const styles = StyleSheet.create({
  aiGrid: {
    flexDirection: 'row',
    gap: 10,
    alignItems: 'stretch',
  },
  aiScoreBox: {
    flex: 1,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 10,
    padding: 10,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 3,
  },
  aiScoreLabel: {
    color: C.muted,
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  aiScoreValRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 4,
  },
  aiScoreVal: {
    fontSize: 24,
    fontWeight: '800',
    fontVariant: ['tabular-nums'],
  },
  aiScoreUnit: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '700',
  },
  aiRiskPill: {
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 1.5,
    marginTop: 2,
  },
  aiRiskText: {
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  aiStateCol: {
    flex: 1.4,
    justifyContent: 'center',
    gap: 6,
  },
  aiStateLabel: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  aiStateBadge: {
    borderWidth: 1,
    borderRadius: 8,
    backgroundColor: 'rgba(76, 214, 251, 0.1)',
    paddingHorizontal: 8,
    paddingVertical: 4,
    alignSelf: 'flex-start',
  },
  aiStateBadgeText: {
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  aiModelText: {
    color: C.textSecondary,
    fontSize: 10,
    lineHeight: 14,
  },
  bufferSelectorBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: C.panel,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 10,
    padding: 8,
  },
  bufferLabel: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '700',
  },
  bufferPillRow: {
    flexDirection: 'row',
    gap: 4,
  },
  bufferBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 8,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
  },
  bufferBtnActive: {
    backgroundColor: C.primaryContainer,
    borderColor: C.cyan,
  },
  bufferBtnText: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '700',
  },
  bufferBtnTextActive: {
    color: C.canvas,
  },
  inclinometerNote: {
    color: C.muted,
    fontSize: 10,
    textAlign: 'center',
    marginTop: 4,
  },
  modelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: C.borderSubtle,
  },
  modelKey: {
    color: C.muted,
    fontSize: 11,
    fontWeight: '600',
  },
  modelVal: {
    color: C.text,
    fontSize: 11,
    fontWeight: '700',
  },
  modelDisclaimer: {
    color: C.muted,
    fontSize: 10,
    lineHeight: 14,
    marginTop: 4,
  },
  matrixContainer: {
    flexDirection: 'row',
    gap: 6,
  },
  matrixTile: {
    flex: 1,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderRadius: 10,
    padding: 8,
    alignItems: 'center',
    gap: 2,
  },
  tileCrit: {
    borderColor: C.red,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
  },
  tileWarn: {
    borderColor: C.amber,
  },
  tileCaution: {
    borderColor: C.cyan,
  },
  tileNormal: {
    borderColor: C.borderSubtle,
  },
  matrixTileTag: {
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  matrixTileVal: {
    fontSize: 18,
    fontWeight: '800',
    fontVariant: ['tabular-nums'],
  },
  matrixTileSub: {
    fontSize: 8,
    fontWeight: '700',
  },
  filterPillsRow: {
    flexDirection: 'row',
    gap: 6,
    flexWrap: 'wrap',
  },
  filterBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
  },
  filterBtnActive: {
    backgroundColor: C.primaryContainer,
    borderColor: C.cyan,
  },
  filterBtnText: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '700',
  },
  filterBtnTextActive: {
    color: C.canvas,
  },
  alarmList: {
    gap: 10,
  },
  emptyAlarmWell: {
    backgroundColor: C.panel,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
  },
  emptyAlarmText: {
    color: C.muted,
    fontSize: 12,
  },
  alarmCard: {
    backgroundColor: C.panel,
    borderWidth: 1,
    borderLeftWidth: 3.5,
    borderColor: C.borderSubtle,
    borderRadius: 12,
    padding: 12,
    gap: 6,
    ...SHADOWS.sm,
  },
  alarmCardCriticalPulse: {
    backgroundColor: '#FEE2E2',
  },
  cardTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  levelBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2.5,
    borderRadius: 20,
  },
  levelBadgeText: {
    color: C.canvas,
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  alarmIdText: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '700',
    backgroundColor: C.panel2,
    paddingHorizontal: 5,
    paddingVertical: 2,
    borderRadius: 3,
  },
  cardTimeRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 2,
  },
  cardTimeUtc: {
    color: C.muted,
    fontSize: 10,
  },
  cardTimeRel: {
    color: C.amber,
    fontSize: 10,
    fontWeight: '700',
  },
  alarmTitle: {
    color: C.text,
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 0.2,
  },
  alarmDesc: {
    color: C.textSecondary,
    fontSize: 11,
    lineHeight: 16,
  },
  peakWell: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 4,
    padding: 8,
    marginTop: 4,
  },
  peakItem: {
    gap: 2,
  },
  peakLabel: {
    color: C.muted,
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  peakVal: {
    color: C.text,
    fontSize: 12,
    fontWeight: '800',
  },
  cardBtnRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 6,
  },
  detailBtn: {
    flex: 1,
    minHeight: 40,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  detailBtnText: {
    color: C.text,
    fontSize: 10,
    fontWeight: '800',
  },
  ackBtn: {
    minHeight: 40,
    paddingHorizontal: 12,
    borderRadius: 5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  ackBtnText: {
    color: C.canvas,
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 0.4,
  },
  detailHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  statePill: {
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
  },
  statePillText: {
    color: C.cyan,
    fontSize: 10,
    fontWeight: '800',
  },
  detailTitle: {
    color: C.text,
    fontSize: 16,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  detailDesc: {
    color: C.textSecondary,
    fontSize: 12,
    lineHeight: 18,
  },
  detailMetaGrid: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 6,
  },
  metaCell: {
    flex: 1,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 4,
    padding: 8,
    gap: 2,
  },
  metaCellLabel: {
    color: C.muted,
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  metaCellVal: {
    color: C.text,
    fontSize: 12,
    fontWeight: '700',
  },
  metaCellSub: {
    color: C.muted,
    fontSize: 10,
  },
  frozenAnnotationRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  frozenAnnotationText: {
    color: C.textSecondary,
    fontSize: 11,
  },
  frozenSubText: {
    color: C.muted,
    fontSize: 11,
  },
  timeline: {
    gap: 12,
    paddingLeft: 6,
    borderLeftWidth: 1,
    borderLeftColor: C.border,
  },
  timelineItem: {
    gap: 2,
    paddingLeft: 10,
  },
  timelineDot: {
    position: 'absolute',
    left: -4.5,
    top: 4,
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  timelineTime: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '600',
  },
  timelineText: {
    color: C.textSecondary,
    fontSize: 11,
    lineHeight: 16,
  },
  remarksLabel: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  noteInputRow: {
    flexDirection: 'row',
    gap: 8,
    alignItems: 'center',
  },
  noteInput: {
    flex: 1,
    minHeight: 44,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 5,
    paddingHorizontal: 10,
    color: C.text,
    fontSize: 12,
  },
  saveNoteBtn: {
    minHeight: 44,
    paddingHorizontal: 14,
    backgroundColor: C.panelHigh,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  saveNoteBtnText: {
    color: C.cyan,
    fontSize: 11,
    fontWeight: '800',
  },
  actionBtnStack: {
    gap: 8,
    marginTop: 6,
  },
  actionWarningNote: {
    color: C.muted,
    fontSize: 9,
    textAlign: 'center',
    marginTop: 4,
  },
});
