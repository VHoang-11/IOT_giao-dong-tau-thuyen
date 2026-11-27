import React, { useState } from 'react';
import {
  Alert,
  LayoutChangeEvent,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { MotionChart } from '../components/MotionChart';
import { Inclinometer } from '../components/Inclinometer';
import {
  MobileRfBreakdownChart,
  MobileVoyageDistributionChart,
} from '../components/MobileVoyageCharts';
import {
  ActionBtn,
  LinkRow,
  MetricCard,
  Page,
  Panel,
  Pill,
  Severity,
  StatusPill,
  TwoCol,
} from '../components/UI';
import { SCENARIOS, fakeWavePoints } from '../data/mock';
import { FONT, SHADOWS, useTheme } from '../theme';
import { CommandStatus, ScreenProps } from '../types/domain';
import {
  getAlarmLevelNameVi,
  getCommandStatusNameVi,
  getRFClassNameVi,
} from '../i18n/vi';

/**
 * MÀN HÌNH 4: TRUNG TÂM ĐIỀU KHIỂN (Control Center)
 */
export function ControlCenterScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const [showTestUtility, setShowTestUtility] = useState(false);

  const role = data.session?.role ?? 'Operator';
  const isSupervisorOrAdmin = role === 'Supervisor' || role === 'Admin';
  const isAdmin = role === 'Admin';

  const cfg = data.config;
  const prev = data.previousConfig;

  const statusColor = (st: CommandStatus) =>
    st === 'APPLIED'
      ? colors.green
      : st === 'REJECTED' || st === 'TIMEOUT'
      ? colors.red
      : st === 'DELIVERED'
      ? colors.tech
      : colors.amber;

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      onBack={actions.back}
      title="Trung tâm điều khiển"
      subtitle="Quản trị cấu hình thiết bị giám sát và kiểm soát lệnh có phiên bản"
    >
      {/* Safety Scope Disclaimer */}
      <View
        style={[
          styles.disclaimerBanner,
          { backgroundColor: colors.warningContainerBg, borderColor: colors.amber },
        ]}
      >
        <Text style={[styles.disclaimerText, { color: colors.title }]}>
          Chỉ điều khiển thiết bị giám sát. Hệ thống không can thiệp bánh lái, động cơ hay vận hành hàng hải tàu.
        </Text>
      </View>

      {/* 2x2 Configuration Summary */}
      <TwoCol>
        <MetricCard
          label="Profile hiện hành"
          value={cfg.profile}
          subtext={`Phiên bản v${cfg.config_version}`}
          color={colors.tech}
        />
        <MetricCard
          label="Mô hình chính"
          value={cfg.active_model === 'RF' ? 'Random Forest' : 'Baseline B'}
          subtext={`Tốc độ mô phỏng ×${cfg.timewarp}`}
          color={colors.tech}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="Ngưỡng lắc an toàn"
          value={`${cfg.roll_warning_deg.toFixed(1)}° / ${cfg.roll_trip_deg.toFixed(1)}°`}
          subtext="Cảnh báo / Nguy cấp"
          color={colors.amber}
        />
        <MetricCard
          label="Ngưỡng MAI"
          value={cfg.mai_alert_threshold.toFixed(2)}
          subtext={cfg.zero_calibration ? 'Đã hiệu chuẩn điểm 0' : 'Điểm 0 mặc định'}
          color={colors.red}
        />
      </TwoCol>

      {/* Group 1: Profile & Rollback */}
      <Panel
        title="Cấu hình ngưỡng & Hoàn tác"
        tag={isSupervisorOrAdmin ? 'Giám sát / Quản trị' : 'Chỉ xem'}
      >
        <Text style={[styles.secNote, { color: colors.textSecondary }]}>
          Chọn bộ ngưỡng giám sát theo trạng thái biển hiện tại:
        </Text>

        <View style={styles.profileButtonGroup}>
          {(['STANDARD', 'SENSITIVE', 'CONSERVATIVE'] as const).map((p) => {
            const active = cfg.profile === p;
            return (
              <Pressable
                key={p}
                disabled={!isSupervisorOrAdmin}
                onPress={() => actions.sendCommand('set_profile', false, p)}
                style={[
                  styles.profileSelectBtn,
                  {
                    backgroundColor: active ? colors.primaryContainer : colors.panel2,
                    borderColor: active ? colors.primaryContainer : colors.borderSubtle,
                  },
                  !isSupervisorOrAdmin && styles.btnDisabledOpacity,
                ]}
                accessibilityRole="button"
              >
                <Text
                  style={[
                    styles.profileSelectBtnText,
                    { color: active ? '#FFFFFF' : colors.title },
                  ]}
                  numberOfLines={1}
                >
                  {active ? `✓ ${p}` : p}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <ActionBtn
          label={
            prev
              ? `Khôi phục về ${prev.profile} (v${prev.config_version})`
              : 'Chưa có bản lưu để khôi phục'
          }
          onPress={() => actions.sendCommand('rollback', false)}
          disabled={!isSupervisorOrAdmin || !prev}
          tone="ghost"
        />
      </Panel>

      {/* Group 2: Device Calibration & Snapshot */}
      <Panel title="Lệnh thiết bị tại biên" tag={isSupervisorOrAdmin ? 'Giám sát / Quản trị' : 'Chỉ xem'}>
        <View
          style={[
            styles.commandRowCard,
            { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
          ]}
        >
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={[styles.commandRowTitle, { color: colors.title }]}>
              Hiệu chuẩn điểm 0
            </Text>
            <Text style={[styles.commandRowSub, { color: colors.textSecondary }]}>
              Yêu cầu tàu tĩnh trong 30 giây (Kịch bản S0).
            </Text>
            <Text
              style={[
                styles.conditionVal,
                { color: data.scenario === 'S0' ? colors.green : colors.amber },
              ]}
            >
              {data.scenario === 'S0'
                ? '● Tàu tĩnh (S0) — Hợp lệ'
                : `● ${data.scenario} — Sẽ từ chối nếu không tĩnh`}
            </Text>
          </View>
          <ActionBtn
            label="Hiệu chuẩn"
            onPress={() => actions.sendCommand('calibrate_zero', false)}
            disabled={!isSupervisorOrAdmin}
            tone="secondary"
          />
        </View>

        <View
          style={[
            styles.commandRowCard,
            { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
          ]}
        >
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={[styles.commandRowTitle, { color: colors.title }]}>
              Chụp trạng thái 180s
            </Text>
            <Text style={[styles.commandRowSub, { color: colors.textSecondary }]}>
              Trích xuất chuỗi 36 mẫu roll/pitch lưu vào bộ nhớ phiên.
            </Text>
          </View>
          <ActionBtn
            label="Chụp mẫu"
            onPress={() => actions.sendCommand('request_snapshot', false)}
            disabled={!isSupervisorOrAdmin}
            tone="secondary"
          />
        </View>
      </Panel>

      {data.latestSnapshot && (
        <Panel title="Bản chụp trạng thái gần nhất" tag={data.latestSnapshot.snapshot_id}>
          <View style={{ gap: 6 }}>
            <View style={styles.kvRow}>
              <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Giới hạn Roll</Text>
              <Text style={[styles.kvVal, { color: colors.tech }]}>
                {data.latestSnapshot.roll_min.toFixed(1)}° .. {data.latestSnapshot.roll_max.toFixed(1)}°
              </Text>
            </View>
            <View style={styles.kvRow}>
              <Text style={[styles.kvKey, { color: colors.textSecondary }]}>RMS Roll / MAI</Text>
              <Text style={[styles.kvVal, { color: colors.amber }]}>
                {data.latestSnapshot.rms_roll_deg.toFixed(1)}° / MAI {data.latestSnapshot.mai}
              </Text>
            </View>
          </View>
        </Panel>
      )}

      {/* Group 3: Admin Simulation Controls */}
      <Panel
        title="Thiết lập mô phỏng & Lõi mô hình"
        tag={isAdmin ? 'Quản trị viên' : 'Chỉ Quản trị viên'}
      >
        <View style={styles.adminSection}>
          <Text style={[styles.adminSectionTitle, { color: colors.title }]}>
            Tốc độ thời gian mô phỏng
          </Text>
          <View style={styles.buttonTrio}>
            {(['1', '5', '10'] as const).map((tw) => {
              const active = cfg.timewarp === parseInt(tw, 10);
              return (
                <Pressable
                  key={tw}
                  disabled={!isAdmin}
                  onPress={() => actions.sendCommand('set_timewarp', true, tw)}
                  style={[
                    styles.trioBtn,
                    {
                      backgroundColor: active ? colors.primaryContainer : colors.panel2,
                      borderColor: active ? colors.primaryContainer : colors.borderSubtle,
                    },
                    !isAdmin && styles.btnDisabledOpacity,
                  ]}
                  accessibilityRole="button"
                >
                  <Text style={[styles.trioBtnText, { color: active ? '#FFFFFF' : colors.title }]}>
                    ×{tw}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <View style={styles.adminSection}>
          <Text style={[styles.adminSectionTitle, { color: colors.title }]}>
            Mô hình quyết định chính
          </Text>
          <View style={styles.buttonTrio}>
            {(
              [
                { id: 'RF', label: 'Random Forest' },
                { id: 'BASELINE_B', label: 'Baseline B' },
              ] as const
            ).map((m) => {
              const active = cfg.active_model === m.id;
              return (
                <Pressable
                  key={m.id}
                  disabled={!isAdmin}
                  onPress={() => actions.sendCommand('set_model', true, m.id)}
                  style={[
                    styles.trioBtn,
                    {
                      backgroundColor: active ? colors.primaryContainer : colors.panel2,
                      borderColor: active ? colors.primaryContainer : colors.borderSubtle,
                    },
                    !isAdmin && styles.btnDisabledOpacity,
                  ]}
                  accessibilityRole="button"
                >
                  <Text style={[styles.trioBtnText, { color: active ? '#FFFFFF' : colors.title }]}>
                    {m.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <View style={styles.adminSection}>
          <Text style={[styles.adminSectionTitle, { color: colors.title }]}>
            Kịch bản thử nghiệm (8 trạng thái)
          </Text>
          <View style={styles.scenarioGrid}>
            {SCENARIOS.map((s) => {
              const active = data.scenario === s.id;
              return (
                <Pressable
                  key={s.id}
                  disabled={!isAdmin}
                  onPress={() => actions.setScenario(s.id)}
                  style={[
                    styles.scenarioBtn,
                    {
                      backgroundColor: active ? colors.cyanContainerBg : colors.panel2,
                      borderColor: active ? colors.tech : colors.borderSubtle,
                    },
                    !isAdmin && styles.btnDisabledOpacity,
                  ]}
                  accessibilityRole="button"
                >
                  <Text
                    style={[
                      styles.scenarioBtnText,
                      { color: active ? colors.tech : colors.title },
                    ]}
                  >
                    {active ? `✓ ${s.id}` : s.id}
                  </Text>
                  <Text style={[styles.scenarioBtnDesc, { color: colors.textSecondary }]} numberOfLines={1}>
                    {s.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        {/* Collapsible Test Utility */}
        <Pressable
          onPress={() => setShowTestUtility((v) => !v)}
          style={[styles.collapseTrigger, { borderColor: colors.borderSubtle }]}
          accessibilityRole="button"
        >
          <Text style={[styles.collapseText, { color: colors.textSecondary }]}>
            {showTestUtility ? '▾ Ẩn tiện ích kiểm thử TTL' : '▸ Tiện ích kiểm thử quá hạn lệnh (QA)'}
          </Text>
        </Pressable>

        {showTestUtility && (
          <View
            style={[
              styles.commandRowCard,
              { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
            ]}
          >
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={[styles.commandRowTitle, { color: colors.title }]}>
                Thử nghiệm quá hạn (Timeout 30s)
              </Text>
              <Text style={[styles.commandRowSub, { color: colors.textSecondary }]}>
                Giả lập mất phản hồi ACK từ thiết bị để kiểm tra trạng thái TIMEOUT.
              </Text>
            </View>
            <ActionBtn
              label="Thử Timeout"
              onPress={() => actions.sendCommand('test_timeout', false)}
              disabled={!isSupervisorOrAdmin}
              tone="ghost"
            />
          </View>
        )}
      </Panel>

      {/* Group 4: Command Audit History */}
      <Panel title="Lịch sử thực thi lệnh" tag={`${data.commands.length} lệnh`}>
        {data.commands.length === 0 ? (
          <Text style={[styles.emptyHistoryText, { color: colors.textSecondary }]}>
            Chưa có lệnh nào được gửi trong phiên làm việc hiện tại.
          </Text>
        ) : (
          <View style={{ gap: 10 }}>
            {data.commands.map((cmd) => {
              const color = statusColor(cmd.status);
              return (
                <View
                  key={cmd.id}
                  style={[
                    styles.historyCard,
                    { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
                  ]}
                >
                  <View style={styles.historyHeader}>
                    <View style={{ flex: 1, gap: 2 }}>
                      <Text style={[styles.cmdNameText, { color: colors.title }]}>{cmd.name}</Text>
                      <Text style={[styles.cmdIdText, { color: colors.textSecondary }]}>
                        {cmd.id} • {cmd.at} • v{cmd.config_version}
                      </Text>
                    </View>
                    <View
                      style={[
                        styles.cmdStatusPill,
                        { borderColor: color, backgroundColor: colors.panel },
                      ]}
                    >
                      <Text style={[styles.cmdStatusText, { color }]}>
                        {getCommandStatusNameVi(cmd.status)}
                      </Text>
                    </View>
                  </View>
                  <Text style={[styles.historyDetailText, { color: colors.textSecondary }]}>
                    {cmd.detail}
                  </Text>
                </View>
              );
            })}
          </View>
        )}
      </Panel>
    </Page>
  );
}

/**
 * MÀN HÌNH 5: BÁO CÁO HÀNH TRÌNH (Voyage Reports)
 */
export function VoyageReportsScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const v = data.voyage;

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      onBack={actions.back}
      title="Báo cáo hành trình"
      subtitle="Tổng hợp thống kê dao động và chỉ số bất thường theo chuyến đi"
    >
      {/* Voyage Selector */}
      <Panel title="Chọn hải trình" tag={`${data.voyages.length} chuyến`}>
        <View style={styles.voyageSelectorRow}>
          {data.voyages.map((voy) => {
            const active = data.selectedVoyageId === voy.id;
            return (
              <Pressable
                key={voy.id}
                onPress={() => actions.selectVoyage(voy.id)}
                style={[
                  styles.voyageBtn,
                  {
                    backgroundColor: active ? colors.primaryContainer : colors.panel2,
                    borderColor: active ? colors.primaryContainer : colors.borderSubtle,
                  },
                ]}
                accessibilityRole="button"
              >
                <Text style={[styles.voyageBtnId, { color: active ? '#FFFFFF' : colors.title }]}>
                  {voy.id}
                </Text>
                <Text
                  style={[
                    styles.voyageBtnSub,
                    { color: active ? 'rgba(255,255,255,0.85)' : colors.textSecondary },
                  ]}
                >
                  {voy.durationMinutes} phút
                </Text>
              </Pressable>
            );
          })}
        </View>

        <View style={[styles.voyageMetaBox, { borderTopColor: colors.borderSubtle }]}>
          <Text style={[styles.voyageName, { color: colors.title }]}>{v.name}</Text>
          <Text style={[styles.voyageRoute, { color: colors.textSecondary }]}>{v.route}</Text>
        </View>
      </Panel>

      {/* 2x2 KPIs */}
      <TwoCol>
        <MetricCard
          label="Góc lắc cực đại"
          value={`${v.maxAbsRollDeg.toFixed(1)}°`}
          subtext={`RMS: ${v.rmsRollDeg.toFixed(2)}°`}
          color={v.maxAbsRollDeg >= 15 ? colors.red : colors.tech}
        />
        <MetricCard
          label="Góc chúi cực đại"
          value={`${v.maxAbsPitchDeg.toFixed(1)}°`}
          subtext={`RMS: ${v.rmsPitchDeg.toFixed(2)}°`}
          color={colors.amber}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="MAI cực đại"
          value={`${v.maiMax} / 100`}
          subtext="Chỉ số lớn nhất"
          color={v.maiMax >= 70 ? colors.red : v.maiMax >= 35 ? colors.amber : colors.green}
        />
        <MetricCard
          label="MAI trung bình"
          value={`${v.maiAvg} / 100`}
          subtext={`Vượt ngưỡng: ${v.maiCautionMinutes} phút`}
          color={v.maiAvg >= 70 ? colors.red : v.maiAvg >= 35 ? colors.amber : colors.green}
        />
      </TwoCol>

      <MobileVoyageDistributionChart voyage={v} />
      <MobileRfBreakdownChart voyage={v} />

      <ActionBtn
        label="Xem báo cáo kiểm toán chi tiết →"
        onPress={() => actions.go('ReportDetails')}
        tone="primary"
      />
      <ActionBtn
        tone="neutral"
        label="Mở Phát lại và đánh giá →"
        onPress={() => actions.go('ReplayReview')}
      />
    </Page>
  );
}

/**
 * MÀN HÌNH CHI TIẾT BÁO CÁO (Report Details)
 */
export function ReportDetailsScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const v = data.voyage;

  const tpCount = data.alarms.filter((a) => a.review === 'TRUE').length;
  const fpCount = data.alarms.filter((a) => a.review === 'FALSE').length;
  const uncertCount = data.alarms.filter((a) => !a.review || a.review === 'UNCERTAIN').length;

  const exportCsvDemo = () => {
    Alert.alert(
      'Xuất dữ liệu CSV',
      `Đã chuẩn bị tệp SVMG_${v.id}_telemetry.csv (${v.sampleCount} mẫu, chuẩn T11/T15).`
    );
  };

  const exportPdfNotice = () => {
    Alert.alert(
      'Báo cáo PDF chính thức',
      'Dịch vụ xuất bản PDF có chữ ký số đang chờ Backend TV3 tích hợp. Toàn bộ số liệu kiểm toán đã hiển thị đầy đủ trên màn hình.'
    );
  };

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="Chi tiết báo cáo hành trình"
      subtitle={`Mã hải trình ${v.id} • Kiểm toán số liệu T11`}
      onBack={actions.back}
    >
      <Panel title="Thông số kiểm toán động học" tag={`${v.sampleCount} mẫu`}>
        <View style={{ gap: 8 }}>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Góc lắc cực đại</Text>
            <Text style={[styles.kvVal, { color: v.maxAbsRollDeg >= 15 ? colors.red : colors.tech }]}>
              {v.maxAbsRollDeg.toFixed(2)}°
            </Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>RMS Roll (T11)</Text>
            <Text style={[styles.kvVal, { color: colors.tech }]}>{v.rmsRollDeg.toFixed(2)}°</Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Phân vị 95 Roll</Text>
            <Text style={[styles.kvVal, { color: colors.tech }]}>{v.p95AbsRollDeg.toFixed(2)}°</Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Pitch cực đại / RMS</Text>
            <Text style={[styles.kvVal, { color: colors.amber }]}>
              {v.maxAbsPitchDeg.toFixed(2)}° / {v.rmsPitchDeg.toFixed(2)}°
            </Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Độ đồng thuận mô hình</Text>
            <Text style={[styles.kvVal, { color: colors.green }]}>{v.agreementPercent}%</Text>
          </View>
        </View>
      </Panel>

      <Panel title="Thống kê thẩm định cảnh báo" tag={`${data.alarms.length} sự kiện`}>
        <View style={{ gap: 8 }}>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Xác nhận đúng</Text>
            <Text style={[styles.kvVal, { color: colors.green }]}>{tpCount} sự kiện</Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Báo giả</Text>
            <Text style={[styles.kvVal, { color: colors.red }]}>{fpCount} sự kiện</Text>
          </View>
          <View style={styles.kvRow}>
            <Text style={[styles.kvKey, { color: colors.textSecondary }]}>Chưa đánh giá / Chưa rõ</Text>
            <Text style={[styles.kvVal, { color: colors.amber }]}>{uncertCount} sự kiện</Text>
          </View>
        </View>
      </Panel>

      <Panel title="Nhật ký cảnh báo trong chuyến">
        <View style={{ gap: 8 }}>
          {data.alarms.map((x) => (
            <LinkRow
              key={x.id}
              title={`${x.id} · ${x.title}`}
              subtitle={`${getAlarmLevelNameVi(x.level)} · ${x.at}`}
              onPress={() => {
                actions.selectAlarm(x.id);
                actions.go('AlarmDetail');
              }}
            />
          ))}
        </View>
      </Panel>

      <Panel title="Xuất hồ sơ dữ liệu">
        <View style={{ gap: 10 }}>
          <ActionBtn label="Xuất file CSV (121 mẫu)" onPress={exportCsvDemo} tone="primary" />
          <ActionBtn label="Xuất PDF (Chờ tích hợp máy chủ)" onPress={exportPdfNotice} tone="ghost" />
        </View>
      </Panel>
    </Page>
  );
}

/**
 * MÀN HÌNH 6: PHÁT LẠI VÀ ĐÁNH GIÁ (Replay & Review)
 */
export function ReplayReviewScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const [trackWidth, setTrackWidth] = useState(280);

  const points = data.replayPoints || [];
  const curIdx = Math.min(points.length - 1, Math.max(0, data.replayIndex || 0));
  const cur = points[curIdx] || points[0] || {
    seq: 0,
    t_sim_s: 0,
    roll: 0,
    pitch: 0,
    class_rf: 'NORMAL' as const,
    class_baseline_b: 'NORMAL' as const,
    mai: 14,
    alarm_level: 'NORMAL' as const,
  };

  const windowCount = 40;
  const startIdx = Math.max(0, curIdx - windowCount + 1);
  const slice = points.slice(startIdx, curIdx + 1);
  const rollWave = slice.map((p) => p.roll);
  const pitchWave = slice.map((p) => p.pitch);

  const activeAlarm = data.alarms.find(
    (a) =>
      (a.id === 'ALM-8441' && Math.abs(cur.t_sim_s - 60) <= 15) ||
      (a.id === 'ALM-8450' && Math.abs(cur.t_sim_s - 150) <= 15) ||
      (a.id === 'ALM-8488' && Math.abs(cur.t_sim_s - 320) <= 15) ||
      (a.id === 'ALM-8492' && Math.abs(cur.t_sim_s - 480) <= 15)
  );

  const scrubToX = (locationX: number) => {
    const ratio = Math.max(0, Math.min(1, locationX / Math.max(1, trackWidth)));
    const nextIdx = Math.round(ratio * Math.max(1, points.length - 1));
    actions.setReplayIndex(nextIdx);
  };

  const handleTrackLayout = (e: LayoutChangeEvent) => {
    if (e.nativeEvent.layout.width > 0) {
      setTrackWidth(e.nativeEvent.layout.width);
    }
  };

  const progressPct = (curIdx / Math.max(1, points.length - 1)) * 100;

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="Phát lại và đánh giá"
      subtitle={`Hải trình ${data.selectedVoyageId} • 121 mẫu dữ liệu động học`}
      onBack={actions.back}
    >
      {/* 2x2 Synchronized Telemetry KPIs */}
      <TwoCol>
        <MetricCard
          label="Mốc thời gian"
          value={`T+${cur.t_sim_s}s`}
          subtext={`Mẫu ${curIdx + 1} / ${points.length}`}
          color={colors.tech}
        />
        <MetricCard
          label="Góc lắc ngang"
          value={`${cur.roll > 0 ? '+' : ''}${cur.roll.toFixed(1)}°`}
          subtext={cur.roll > 0.1 ? 'Mạn phải' : cur.roll < -0.1 ? 'Mạn trái' : 'Cân bằng'}
          color={Math.abs(cur.roll) >= 12 ? colors.red : colors.tech}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="Góc chúi dọc"
          value={`${cur.pitch > 0 ? '+' : ''}${cur.pitch.toFixed(1)}°`}
          subtext={cur.pitch > 0.1 ? 'Ngóc mũi' : cur.pitch < -0.1 ? 'Chúi mũi' : 'Mức chuẩn'}
          color={colors.amber}
        />
        <MetricCard
          label="Chỉ số MAI"
          value={`${cur.mai} / 100`}
          subtext={getRFClassNameVi(cur.class_rf)}
          color={cur.mai >= 70 ? colors.red : cur.mai >= 35 ? colors.amber : colors.green}
        />
      </TwoCol>

      {/* Vessel Visualizer Synchronized with Playhead */}
      <Inclinometer
        rollDeg={cur.roll}
        pitchDeg={cur.pitch}
        mai={cur.mai}
        alarmLevel={cur.alarm_level}
        scenario="S0"
        classRf={cur.class_rf}
        sensorOk={true}
      />

      {/* Touch-Draggable Transport Deck directly beneath Vessel Visualizer */}
      <Panel title="Bàn điều khiển phát lại" tag={`T+${cur.t_sim_s}s / 600s`}>
        {/* Touch Scrub Bar */}
        <View style={{ gap: 6 }}>
          <View style={styles.scrubHeaderRow}>
            <Text style={[styles.scrubTimeLabel, { color: colors.textSecondary }]}>0s</Text>
            <Text style={[styles.scrubCurrentLabel, { color: colors.tech }]}>
              Kéo thanh bên dưới để tua
            </Text>
            <Text style={[styles.scrubTimeLabel, { color: colors.textSecondary }]}>600s</Text>
          </View>

          <View
            style={styles.scrubTouchTarget}
            onLayout={handleTrackLayout}
            onStartShouldSetResponder={() => true}
            onMoveShouldSetResponder={() => true}
            onResponderGrant={(e) => scrubToX(e.nativeEvent.locationX)}
            onResponderMove={(e) => scrubToX(e.nativeEvent.locationX)}
          >
            <View style={[styles.scrubTrack, { backgroundColor: colors.panel2, borderColor: colors.borderSubtle }]}>
              <View
                style={[
                  styles.scrubFill,
                  { width: `${progressPct}%`, backgroundColor: colors.tech },
                ]}
              />
            </View>
            <View
              style={[
                styles.scrubThumb,
                {
                  left: `${progressPct}%`,
                  backgroundColor: colors.primaryContainer,
                  borderColor: colors.panel,
                },
              ]}
            />
          </View>
        </View>

        <TwoCol>
          <ActionBtn
            tone={data.replayPlaying ? 'primary' : 'secondary'}
            label={data.replayPlaying ? '❚❚ Tạm dừng' : '▶ Phát tiếp'}
            onPress={() => actions.setReplayPlaying(!data.replayPlaying)}
          />
          <ActionBtn
            tone="neutral"
            label="Về đầu (0s)"
            onPress={() => {
              actions.setReplayIndex(0);
              actions.setReplayPlaying(false);
            }}
          />
        </TwoCol>

        <TwoCol>
          <ActionBtn
            tone="neutral"
            label="−10s"
            onPress={() => actions.setReplayIndex(Math.max(0, curIdx - 2))}
          />
          <ActionBtn
            tone="neutral"
            label="+10s"
            onPress={() => actions.setReplayIndex(Math.min(points.length - 1, curIdx + 2))}
          />
        </TwoCol>

        <View style={[styles.speedBarWrap, { borderTopColor: colors.borderSubtle }]}>
          <Text style={[styles.speedLabel, { color: colors.textSecondary }]}>Tốc độ phát:</Text>
          <View style={styles.speedRow}>
            {[1, 5, 10, 20, 60].map((spd) => {
              const active = data.replaySpeed === spd;
              return (
                <Pressable
                  key={spd}
                  onPress={() => actions.setReplaySpeed(spd)}
                  style={[
                    styles.speedBtn,
                    {
                      backgroundColor: active ? colors.primaryContainer : colors.panel2,
                      borderColor: active ? colors.primaryContainer : colors.borderSubtle,
                    },
                  ]}
                  accessibilityRole="button"
                >
                  <Text style={[styles.speedBtnText, { color: active ? '#FFFFFF' : colors.title }]}>
                    ×{spd}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      </Panel>

      {/* Active Event Callout if Playhead hits Alarm Window */}
      {activeAlarm && (
        <View
          style={[
            styles.replayEventBanner,
            {
              backgroundColor:
                activeAlarm.level === 'CRITICAL' ? colors.errorContainerBg : colors.warningContainerBg,
              borderColor: activeAlarm.level === 'CRITICAL' ? colors.red : colors.amber,
            },
          ]}
        >
          <Text
            style={[
              styles.replayEventTitle,
              { color: activeAlarm.level === 'CRITICAL' ? colors.red : colors.amber },
            ]}
          >
            Sự kiện cảnh báo tại T+{cur.t_sim_s}s: {activeAlarm.id}
          </Text>
          <Text style={[styles.replayEventSub, { color: colors.title }]}>
            {activeAlarm.title} ({getAlarmLevelNameVi(activeAlarm.level)})
          </Text>
        </View>
      )}

      {/* Waveform Slice */}
      <Panel title="Biểu đồ sóng phát lại" tag={`Cửa sổ ${rollWave.length * 5}s`}>
        <MotionChart roll={rollWave} pitch={pitchWave} height={155} />
      </Panel>

      {/* Watchstander Alarm Review */}
      <Panel title="Đánh giá cảnh báo sau chuyến" tag="Thẩm định">
        <Text style={[styles.secNote, { color: colors.textSecondary }]}>
          Gắn nhãn xác nhận đúng hoặc báo giả để cập nhật thống kê báo cáo:
        </Text>
        <View style={{ gap: 12 }}>
          {data.alarms.map((alarm) => (
            <View
              key={alarm.id}
              style={[styles.reviewCard, { borderBottomColor: colors.borderSubtle }]}
            >
              <View style={styles.reviewHeader}>
                <Text style={[styles.reviewTitle, { color: colors.title }]}>
                  {alarm.id} · {alarm.title}
                </Text>
                <Severity level={alarm.level} />
              </View>
              <View style={styles.reviewBtnRow}>
                {(
                  [
                    { key: 'TRUE', label: '✓ Đúng', activeColor: colors.green },
                    { key: 'FALSE', label: '✗ Báo giả', activeColor: colors.red },
                    { key: 'UNCERTAIN', label: '? Chưa rõ', activeColor: colors.amber },
                  ] as const
                ).map((opt) => {
                  const selected = alarm.review === opt.key;
                  return (
                    <Pressable
                      key={opt.key}
                      onPress={() => actions.reviewAlarm(alarm.id, opt.key)}
                      style={[
                        styles.reviewBtn,
                        {
                          backgroundColor: selected ? colors.panel : colors.panel2,
                          borderColor: selected ? opt.activeColor : colors.borderSubtle,
                          borderWidth: selected ? 1.5 : 1,
                        },
                      ]}
                      accessibilityRole="button"
                    >
                      <Text
                        style={[
                          styles.reviewBtnText,
                          { color: selected ? opt.activeColor : colors.textSecondary },
                        ]}
                      >
                        {opt.label}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
            </View>
          ))}
        </View>
      </Panel>
    </Page>
  );
}

const styles = StyleSheet.create({
  disclaimerBanner: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
  },
  disclaimerText: {
    fontSize: 13,
    fontFamily: FONT.medium,
    lineHeight: 19,
  },
  secNote: {
    fontSize: 13,
    fontFamily: FONT.regular,
    lineHeight: 19,
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
  profileButtonGroup: {
    flexDirection: 'row',
    gap: 8,
  },
  profileSelectBtn: {
    flex: 1,
    borderWidth: 1,
    borderRadius: 10,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  profileSelectBtnText: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  commandRowCard: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  commandRowTitle: {
    fontSize: 15,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  commandRowSub: {
    fontSize: 13,
    fontFamily: FONT.regular,
    lineHeight: 18,
  },
  conditionVal: {
    fontSize: 12,
    fontFamily: FONT.medium,
    marginTop: 2,
  },
  adminSection: {
    gap: 8,
  },
  adminSectionTitle: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  buttonTrio: {
    flexDirection: 'row',
    gap: 8,
  },
  trioBtn: {
    flex: 1,
    minHeight: 44,
    borderWidth: 1,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 8,
  },
  trioBtnText: {
    fontSize: 13,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  scenarioGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  scenarioBtn: {
    width: '48%',
    borderWidth: 1,
    borderRadius: 10,
    padding: 10,
    minHeight: 54,
    justifyContent: 'center',
    gap: 2,
  },
  scenarioBtnText: {
    fontSize: 14,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  scenarioBtnDesc: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  btnDisabledOpacity: {
    opacity: 0.45,
  },
  collapseTrigger: {
    borderTopWidth: 1,
    paddingTop: 10,
    minHeight: 40,
    justifyContent: 'center',
  },
  collapseText: {
    fontSize: 13,
    fontFamily: FONT.medium,
  },
  emptyHistoryText: {
    fontSize: 13,
    fontFamily: FONT.regular,
    textAlign: 'center',
    paddingVertical: 10,
  },
  historyCard: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    gap: 6,
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  cmdNameText: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  cmdIdText: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  cmdStatusPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
    borderWidth: 1,
  },
  cmdStatusText: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  historyDetailText: {
    fontSize: 13,
    fontFamily: FONT.regular,
    lineHeight: 18,
  },
  voyageSelectorRow: {
    flexDirection: 'row',
    gap: 8,
  },
  voyageBtn: {
    flex: 1,
    minHeight: 52,
    borderWidth: 1,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 8,
  },
  voyageBtnId: {
    fontSize: 13,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  voyageBtnSub: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  voyageMetaBox: {
    borderTopWidth: 1,
    paddingTop: 10,
    gap: 3,
  },
  voyageName: {
    fontSize: 15,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  voyageRoute: {
    fontSize: 13,
    fontFamily: FONT.regular,
  },
  scrubHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  scrubTimeLabel: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontVariant: ['tabular-nums'],
  },
  scrubCurrentLabel: {
    fontSize: 12,
    fontFamily: FONT.medium,
  },
  scrubTouchTarget: {
    height: 44,
    justifyContent: 'center',
    position: 'relative',
  },
  scrubTrack: {
    height: 10,
    borderRadius: 5,
    borderWidth: 1,
    overflow: 'hidden',
  },
  scrubFill: {
    height: '100%',
  },
  scrubThumb: {
    position: 'absolute',
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    marginLeft: -10,
  },
  speedBarWrap: {
    borderTopWidth: 1,
    paddingTop: 10,
    gap: 8,
  },
  speedLabel: {
    fontSize: 13,
    fontFamily: FONT.medium,
  },
  speedRow: {
    flexDirection: 'row',
    gap: 6,
  },
  speedBtn: {
    flex: 1,
    minHeight: 40,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  speedBtnText: {
    fontSize: 13,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  replayEventBanner: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    gap: 3,
  },
  replayEventTitle: {
    fontSize: 14,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  replayEventSub: {
    fontSize: 13,
    fontFamily: FONT.regular,
  },
  reviewCard: {
    borderBottomWidth: 1,
    paddingBottom: 12,
    gap: 8,
  },
  reviewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  reviewTitle: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    flex: 1,
  },
  reviewBtnRow: {
    flexDirection: 'row',
    gap: 8,
  },
  reviewBtn: {
    flex: 1,
    minHeight: 44,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  reviewBtnText: {
    fontSize: 13,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
});
