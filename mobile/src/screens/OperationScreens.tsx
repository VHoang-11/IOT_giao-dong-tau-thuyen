import React from 'react';
import { Alert, Pressable, StyleSheet, Text, View } from 'react-native';
import { MotionChart } from '../components/MotionChart';
import { Inclinometer } from '../components/Inclinometer';
import { MobileVoyageDistributionChart, MobileRfBreakdownChart } from '../components/MobileVoyageCharts';
import {
  ActionBtn,
  Body,
  Label,
  LinkRow,
  MetricCard,
  Page,
  Panel,
  Pill,
  Small,
  TwoCol,
  Value,
} from '../components/UI';
import { SCENARIOS, fakeWavePoints } from '../data/mock';
import { C } from '../theme';
import { f, n } from '../data/format';
import { CommandStatus, ScreenProps } from '../types/domain';

export function ControlCenterScreen({ data, actions }: ScreenProps) {
  const role = data.session?.role ?? 'Operator';
  const isSupervisorOrAdmin = role === 'Supervisor' || role === 'Admin';
  const isAdmin = role === 'Admin';

  const cfg = data.config;
  const prev = data.previousConfig;

  const statusColor = (st: CommandStatus) =>
    st === 'APPLIED'
      ? C.green
      : st === 'REJECTED' || st === 'TIMEOUT'
      ? C.red
      : st === 'DELIVERED'
      ? C.cyan
      : C.amber;

  return (
    <Page
      vesselName={data.vesselName}
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      onBack={actions.back}
      title="CONTROL CENTER"
      subtitle="Cấu hình thiết bị giám sát • Kênh lệnh có phiên bản & Phân quyền"
    >
      {/* Scope Disclaimer Banner */}
      <View style={styles.disclaimerBanner}>
        <Text style={styles.disclaimerIcon}>🛡️</Text>
        <Text style={styles.disclaimerText}>
          CHỈ ĐIỀU KHIỂN THIẾT BỊ GIÁM SÁT • TUYỆT ĐỐI KHÔNG ĐIỀU KHIỂN BÁNH LÁI, ĐỘNG CƠ HAY HÀNG HẢI TÀU.
        </Text>
      </View>

      {/* 1. Active Configuration Well */}
      <Panel title="CẤU HÌNH THIẾT BỊ HIỆN HÀNH" tag={`VERSION v${cfg.config_version}`}>
        <View style={styles.cfgRow}>
          <View style={styles.cfgItem}>
            <Text style={styles.cfgLabel}>PROFILE:</Text>
            <View style={styles.activeProfileBadge}>
              <Text style={styles.activeProfileText}>{cfg.profile}</Text>
            </View>
          </View>
          <View style={styles.cfgItem}>
            <Text style={styles.cfgLabel}>NGUỒN DỮ LIỆU:</Text>
            <Text style={styles.cfgVal}>{cfg.source_mode}</Text>
          </View>
        </View>

        <View style={styles.cfgRow}>
          <View style={styles.cfgItem}>
            <Text style={styles.cfgLabel}>MÔ HÌNH CHÍNH:</Text>
            <Text style={[styles.cfgVal, { color: C.cyan }]}>
              {cfg.active_model === null ? '—' : cfg.active_model === 'RF' ? 'Random Forest (Edge)' : 'Baseline B'}
            </Text>
          </View>
          <View style={styles.cfgItem}>
            <Text style={styles.cfgLabel}>TỐC ĐỘ VIRTUAL:</Text>
            <Text style={[styles.cfgVal, { color: C.amber }]}>{cfg.timewarp === null ? '—' : `×${cfg.timewarp}`}</Text>
          </View>
        </View>

        {/* Threshold Metrics Bento */}
        <View style={styles.thresholdBento}>
          <View style={styles.thresholdTile}>
            <Text style={styles.thresholdTileLabel}>ROLL WARNING</Text>
            <Text style={[styles.thresholdTileVal, { color: C.amber }]}>
              {f(cfg.roll_warning_deg, 1, '°')}
            </Text>
            <Text style={styles.thresholdTileSub}>Amber Limit</Text>
          </View>
          <View style={styles.thresholdTile}>
            <Text style={styles.thresholdTileLabel}>CRITICAL TRIP</Text>
            <Text style={[styles.thresholdTileVal, { color: C.red }]}>
              {f(cfg.roll_trip_deg, 1, '°')}
            </Text>
            <Text style={styles.thresholdTileSub}>Red Limit</Text>
          </View>
          <View style={styles.thresholdTile}>
            <Text style={styles.thresholdTileLabel}>MAI ALERT</Text>
            <Text style={[styles.thresholdTileVal, { color: C.cyan }]}>
              {f(cfg.mai_alert_threshold, 2)}
            </Text>
            <Text style={styles.thresholdTileSub}>Damped α</Text>
          </View>
        </View>

        {cfg.zero_calibration && (
          <View style={[styles.cfgRow, { marginTop: 10, paddingTop: 8, borderTopWidth: 1, borderTopColor: C.border }]}>
            <View style={styles.cfgItem}>
              <Text style={styles.cfgLabel}>ĐIỂM 0 HIỆU CHUẨN:</Text>
              <Text style={[styles.cfgVal, { color: C.green }]}>
                Roll {cfg.zero_calibration.roll_offset_deg > 0 ? '+' : ''}{cfg.zero_calibration.roll_offset_deg}°, Pitch {cfg.zero_calibration.pitch_offset_deg}° (30s tĩnh)
              </Text>
            </View>
          </View>
        )}

        <Text style={[styles.secNote, { marginTop: 8 }]}>
          * Lưu ý: Các ngưỡng Roll và MAI là cấu hình mô phỏng nội bộ nhóm (Demo Profile, tham chiếu dải an toàn 15°–25° theo đề cương), không phải tiêu chuẩn IMO chính thức.
        </Text>
      </Panel>

      {/* 2. Monitoring Command Profiles Segmented Selector */}
      <Panel
        title="THAY ĐỔI PROFILE CẤU HÌNH"
        tag={isSupervisorOrAdmin ? 'SUPERVISOR / ADMIN' : 'CHỈ XEM (OPERATOR)'}
      >
        <Text style={styles.secNote}>
          Đổi cấu hình chống nhấp nháy N và ngưỡng an toàn. Giới hạn φ_hard luôn trong 15–25°:
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
                  active && styles.profileSelectBtnActive,
                  !isSupervisorOrAdmin && styles.btnDisabledOpacity,
                ]}
                accessibilityRole="button"
              >
                <Text
                  style={[
                    styles.profileSelectBtnText,
                    active && styles.profileSelectBtnTextActive,
                  ]}
                >
                  {active ? `✓ ${p}` : p}
                </Text>
              </Pressable>
            );
          })}
        </View>

        {/* Rollback Configuration Button */}
        <View style={styles.rollbackWell}>
          <ActionBtn
            label={
              prev
                ? `QUAY LUI VỀ PROFILE ${prev.profile} (ROLLBACK)`
                : 'CHƯA CÓ BẢN LƯU ĐỂ QUAY LUI (ROLLBACK)'
            }
            onPress={() => actions.sendCommand('rollback', false)}
            disabled={!isSupervisorOrAdmin || !prev}
            tone="ghost"
          />
          <Text style={styles.rollbackNote}>
            {prev
              ? `* Bản snapshot trước: Profile ${prev.profile} (v${prev.config_version}). Hoàn tác nguyên tử an toàn.`
              : '* Chưa có thay đổi cấu hình nào trước đó trong phiên này.'}
          </Text>
        </View>
      </Panel>

      {/* 3. Monitoring Commands (Supervisor / Admin) */}
      <Panel
        title="LỆNH ĐIỀU KHIỂN THIẾT BỊ GIÁM SÁT"
        tag="SUPERVISOR / ADMIN"
      >
        {/* Calibrate Zero */}
        <View style={styles.commandRowCard}>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.commandRowTitle}>Hiệu chuẩn độ lệch 0 (calibrate_zero)</Text>
            <Text style={styles.commandRowSub}>
              Đo độ lệch tĩnh và kiểm tra độ ổn định tín hiệu trong 30s. Điều kiện: Tàu tĩnh (σ ≤ 1.0°).
            </Text>
            <View style={styles.conditionRow}>
              <Text style={styles.conditionLabel}>Trạng thái hiện tại:</Text>
              <Text
                style={[
                  styles.conditionVal,
                  { color: data.mode === 'live' ? C.muted : data.scenario === 'S0' ? C.green : C.amber },
                ]}
              >
                {data.mode === 'live'
                  ? '● Thiết bị tự kiểm tra độ tĩnh ~30s (REJECTED nếu tàu còn dao động)'
                  : data.scenario === 'S0' ? '● Tàu tĩnh (S0, σ=0.15°) — HỢP LỆ' : `● ${data.scenario} (σ > 1.0°) — TỪ CHỐI (NOT_STATIC)`}
              </Text>
            </View>
          </View>
          <ActionBtn
            label="CALIBRATE"
            onPress={() => actions.sendCommand('calibrate_zero', false)}
            disabled={!isSupervisorOrAdmin}
            tone="secondary"
          />
        </View>

        {/* Request Snapshot (MOCK: firmware/Backend chưa có lệnh này) */}
        {data.mode === 'mock' && (
        <View style={styles.commandRowCard}>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.commandRowTitle}>Yêu cầu trích xuất sóng (request_snapshot)</Text>
            <Text style={styles.commandRowSub}>
              Thiết bị gửi chuỗi 180s roll/pitch giảm mẫu (36 mẫu) và lưu trực tiếp vào Mock State.
            </Text>
          </View>
          <ActionBtn
            label="SNAPSHOT"
            onPress={() => actions.sendCommand('request_snapshot', false)}
            disabled={!isSupervisorOrAdmin}
            tone="secondary"
          />
        </View>
        )}
      </Panel>

      {/* Snapshot Result Artifact in Mock State */}
      {data.latestSnapshot && (
        <Panel title="BẢN CHỤP DỮ LIỆU ĐỘNG HỌC (LATEST SNAPSHOT 180s)" tag="MOCK STATE ARTIFACT">
          <View style={styles.cfgRow}>
            <View style={styles.cfgItem}>
              <Text style={styles.cfgLabel}>MÃ SNAPSHOT:</Text>
              <Text style={[styles.cfgVal, { color: C.cyan }]}>{data.latestSnapshot.snapshot_id}</Text>
            </View>
            <View style={styles.cfgItem}>
              <Text style={styles.cfgLabel}>SỐ LƯỢNG MẪU:</Text>
              <Text style={styles.cfgVal}>{data.latestSnapshot.sample_count} mẫu (180s)</Text>
            </View>
          </View>
          <View style={styles.cfgRow}>
            <View style={styles.cfgItem}>
              <Text style={styles.cfgLabel}>GIỚI HẠN ROLL:</Text>
              <Text style={styles.cfgVal}>
                {data.latestSnapshot.roll_min.toFixed(1)}° .. {data.latestSnapshot.roll_max.toFixed(1)}°
              </Text>
            </View>
            <View style={styles.cfgItem}>
              <Text style={styles.cfgLabel}>RMS ROLL / MAI:</Text>
              <Text style={[styles.cfgVal, { color: C.amber }]}>
                {data.latestSnapshot.rms_roll_deg.toFixed(1)}° / MAI {data.latestSnapshot.mai}
              </Text>
            </View>
          </View>
          <Text style={styles.rollbackNote}>
            * Dữ liệu snapshot 180s đã được trích xuất và lưu trong Mock State bởi {data.latestSnapshot.triggered_by}.
          </Text>
        </Panel>
      )}

      {/* Test Harness / Mock Utility Panel */}
      {data.mode === 'mock' && (
      <Panel
        title="TIỆN ÍCH KIỂM THỬ (TEST HARNESS / MOCK ONLY)"
        tag="UTILITY FOR QA / DEV"
      >
        <Text style={styles.secNote}>
          Tiện ích giả lập sự cố kết nối phục vụ kiểm thử giao diện & vòng đời lệnh TIMEOUT (không phải lệnh cấu hình thiết bị trong Bảng 8.2 đề cương):
        </Text>
        <View style={styles.commandRowCard}>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={styles.commandRowTitle}>[TEST UTILITY] Thử nghiệm TIMEOUT (TTL 30s)</Text>
            <Text style={styles.commandRowSub}>
              Mô phỏng trường hợp mất gói tin QoS 1 hoặc thiết bị không phản hồi ACK (SENT → DELIVERED → TIMEOUT).
            </Text>
          </View>
          <ActionBtn
            label="TEST TIMEOUT"
            onPress={() => actions.sendCommand('test_timeout', false)}
            disabled={!isSupervisorOrAdmin}
            tone="ghost"
          />
        </View>
      </Panel>
      )}
      {/* 4. Advanced Admin Only Panel */}
      <Panel
        title="THIẾT LẬP MÔ PHỎNG VÀ LÕI MÔ HÌNH"
        tag={isAdmin ? 'ADMIN ACCESS GRANTED' : 'KHÓA: YÊU CẦU QUYỀN ADMIN'}
      >
        {/* Set Timewarp */}
        {data.mode === 'mock' && (
        <View style={styles.adminSection}>
          <Text style={styles.adminSectionTitle}>TỐC ĐỘ THỜI GIAN MÔ PHỎNG (TIMEWARP):</Text>
          <View style={styles.buttonTrio}>
            {(['1', '5', '10'] as const).map((tw) => (
              <Pressable
                key={tw}
                disabled={!isAdmin}
                onPress={() => actions.sendCommand('set_timewarp', true, tw)}
                style={[
                  styles.trioBtn,
                  cfg.timewarp === parseInt(tw, 10) && styles.trioBtnActive,
                  !isAdmin && styles.btnDisabledOpacity,
                ]}
                accessibilityRole="button"
              >
                <Text
                  style={[
                    styles.trioBtnText,
                    cfg.timewarp === parseInt(tw, 10) && styles.trioBtnTextActive,
                  ]}
                >
                  ×{tw}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        )}

        {/* Set Model */}
        <View style={styles.adminSection}>
          <Text style={styles.adminSectionTitle}>CHỌN MÔ HÌNH QUYẾT ĐỊNH CHÍNH (SET_MODEL):</Text>
          <View style={styles.buttonTrio}>
            {(
              [
                { id: 'RF', label: 'Random Forest (Edge)' },
                { id: 'BASELINE_B', label: 'Baseline B (Heuristic)' },
              ] as const
            ).map((m) => (
              <Pressable
                key={m.id}
                disabled={!isAdmin}
                onPress={() => actions.sendCommand('set_model', true, m.id)}
                style={[
                  styles.trioBtn,
                  { flex: 1 },
                  cfg.active_model === m.id && styles.trioBtnActive,
                  !isAdmin && styles.btnDisabledOpacity,
                ]}
                accessibilityRole="button"
              >
                <Text
                  style={[
                    styles.trioBtnText,
                    cfg.active_model === m.id && styles.trioBtnTextActive,
                  ]}
                >
                  {m.label}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>

        {/* Set Mode */}
        {data.mode === 'mock' && (
        <View style={styles.adminSection}>
          <Text style={styles.adminSectionTitle}>CHẾ ĐỘ NGUỒN TÍN HIỆU (SET_MODE):</Text>
          <View style={styles.buttonTrio}>
            <Pressable
              disabled={!isAdmin}
              onPress={() => actions.sendCommand('set_mode', true, 'SIMULATION')}
              style={[
                styles.trioBtn,
                { flex: 1 },
                cfg.source_mode === 'SIMULATION' && styles.trioBtnActive,
                !isAdmin && styles.btnDisabledOpacity,
              ]}
              accessibilityRole="button"
            >
              <Text
                style={[
                  styles.trioBtnText,
                  cfg.source_mode === 'SIMULATION' && styles.trioBtnTextActive,
                ]}
              >
                SIMULATION (Mô phỏng)
              </Text>
            </Pressable>

            <Pressable
              disabled={!isAdmin}
              onPress={() => actions.sendCommand('set_mode', true, 'SENSOR')}
              style={[styles.trioBtn, { flex: 1 }, !isAdmin && styles.btnDisabledOpacity]}
              accessibilityRole="button"
            >
              <Text style={styles.trioBtnText}>SENSOR (Thử nghiệm REJECTED)</Text>
            </Pressable>
          </View>
        </View>

        )}

        {/* Set Scenario Grid */}
        {data.mode === 'mock' && (
        <View style={styles.adminSection}>
          <Text style={styles.adminSectionTitle}>
            CHỌN KỊCH BẢN GIẢ LẬP (SET_SCENARIO — 8 TRƯỜNG HỢP):
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
                    active && styles.scenarioBtnActive,
                    !isAdmin && styles.btnDisabledOpacity,
                  ]}
                  accessibilityRole="button"
                >
                  <Text
                    style={[
                      styles.scenarioBtnText,
                      active && styles.scenarioBtnTextActive,
                    ]}
                  >
                    {active ? `✓ ${s.id}` : s.id}
                  </Text>
                  <Text style={styles.scenarioBtnDesc} numberOfLines={1}>
                    {s.label.split(' - ')[1] ?? s.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
        )}

        {/* Restart device (LIVE, Admin) */}
        {data.mode === 'live' && (
          <View style={styles.adminSection}>
            <Text style={styles.adminSectionTitle}>KHỞI ĐỘNG LẠI THIẾT BỊ (RESTART_DEVICE):</Text>
            <ActionBtn
              label="RESTART THIẾT BỊ"
              onPress={() => actions.sendCommand('restart_device', true)}
              disabled={!isAdmin}
              tone="ghost"
            />
          </View>
        )}
      </Panel>

      {/* 5. Command Execution History & Lifecycle Audit */}
      <Panel
        title="NHẬT KÝ VÒNG ĐỜI LỆNH (COMMAND AUDIT LOG)"
        tag="SENT → DELIVERED → APPLIED/REJECTED"
      >
        {data.commands.length === 0 ? (
          <Text style={styles.emptyHistoryText}>
            Chưa có lệnh nào được phát lệnh trong phiên làm việc hiện tại.
          </Text>
        ) : (
          <View style={styles.historyList}>
            {data.commands.map((cmd) => {
              const color = statusColor(cmd.status);
              return (
                <View key={cmd.id} style={styles.historyCard}>
                  <View style={styles.historyHeader}>
                    <View style={styles.cmdTitleCol}>
                      <Text style={styles.cmdIdText}>{cmd.id}</Text>
                      <Text style={styles.cmdNameText}>{cmd.name}</Text>
                    </View>
                    <View
                      style={[
                        styles.cmdStatusPill,
                        { borderColor: color, backgroundColor: `${color}1A` },
                      ]}
                    >
                      <Text style={[styles.cmdStatusText, { color }]}>
                        {cmd.status}
                      </Text>
                    </View>
                  </View>

                  <View style={styles.historyMetaRow}>
                    <Text style={styles.historyMetaTime}>🕒 {cmd.at}</Text>
                    {cmd.issued_by && (
                      <Text style={styles.historyMetaUser}>
                        Người phát: <Text style={{ color: C.text }}>{cmd.issued_by}</Text>
                      </Text>
                    )}
                    <Text style={styles.historyMetaVer}>{cmd.config_version === null ? '' : `v${cmd.config_version}`}</Text>
                  </View>

                  <Text style={styles.historyDetailText}>{cmd.detail}</Text>
                </View>
              );
            })}
          </View>
        )}
      </Panel>
    </Page>
  );
}

export function VoyageReportsScreen({ data, actions }: ScreenProps) {
  const v = data.voyage;
  const isSelected = (id: string) => data.selectedVoyageId === id;

  return (
    <Page
      vesselName={data.vesselName}
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="VOYAGE REPORTS"
      subtitle={data.mode === 'live' ? 'HÀNH TRÌNH GIÁM SÁT • DỮ LIỆU BACKEND' : 'HÀNH TRÌNH GIÁM SÁT • DỮ LIỆU MÔ PHỎNG'}
    >
      {/* 1. Voyage Selector Tabs */}
      <Panel title="DANH SÁCH CHUYẾN ĐI MÔ PHỎNG" tag="CHỌN CHUYẾN">
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
          {data.voyages.map((voy) => {
            const active = isSelected(voy.id);
            return (
              <Pressable
                key={voy.id}
                onPress={() => actions.selectVoyage(voy.id)}
                style={{
                  flex: 1,
                  minWidth: 95,
                  paddingVertical: 8,
                  paddingHorizontal: 8,
                  borderRadius: 5,
                  borderWidth: 1,
                  borderColor: active ? C.cyan : C.border,
                  backgroundColor: active ? '#EAF2FA' : C.panel,
                  alignItems: 'center',
                }}
              >
                <Text style={{ color: active ? C.cyan : C.text, fontSize: 11, fontFamily: 'monospace', fontWeight: 'bold' }}>
                  {active ? `● ${voy.id}` : voy.id}
                </Text>
                <Text style={{ color: C.muted, fontSize: 9, marginTop: 2 }} numberOfLines={1}>
                  {n(voy.durationMinutes, ' min')}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <View style={{ marginTop: 10, paddingTop: 8, borderTopWidth: 1, borderTopColor: C.border }}>
          <Value>{v.name}</Value>
          <Body>{v.route}</Body>
          <Small>Bắt đầu: {v.startTime} • Kết thúc: {v.endTime}</Small>
          {data.mode === 'live' && v.provisional && v.metricsLoaded ? (
            <Small>⚠ Chuyến đang chạy: số liệu chỉ là TẠM THỜI.</Small>
          ) : null}
          {data.mode === 'live' && v.id !== '—' && !v.metricsLoaded ? (
            <Small>Đang tải số liệu chuyến từ Backend…</Small>
          ) : null}
        </View>
      </Panel>

      {/* 2. Key Voyage Kinematic Metrics */}
      <TwoCol>
        <MetricCard
          label="THỜI LƯỢNG"
          value={v.durationMinutes === null ? '—' : `${v.durationMinutes} phút`}
          color={C.cyan}
        />
        <MetricCard
          label="SỰ KIỆN CẢNH BÁO"
          value={n(v.alarms)}
          color={v.alarms === null ? C.muted : v.alarms > 0 ? C.amber : C.green}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="ROLL CỰC ĐẠI |°|"
          value={f(v.maxAbsRollDeg, 1, '°')}
          color={v.maxAbsRollDeg === null ? C.muted : v.maxAbsRollDeg > 15 ? C.red : C.amber}
        />
        <MetricCard
          label="RMS ROLL (T11)"
          value={f(v.rmsRollDeg, 2, '°')}
          color={C.cyan}
        />
      </TwoCol>

      {/* Kinematic Statistical Distribution & RF Breakdown Charts */}
      <MobileVoyageDistributionChart voyage={v} />
      <MobileRfBreakdownChart voyage={v} />

      {/* 3. Extreme Kinematics & MAI Bento */}
      <Panel title="TỔNG QUAN CHỈ SỐ ĐỘNG HỌC & BẤT THƯỜNG" tag="KINEMATIC AUDIT">
        <View style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: C.border }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>P95 ROLL (T11):</Text>
            <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{f(v.p95AbsRollDeg, 2, '°')}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: C.border }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>MAX PITCH / RMS PITCH:</Text>
            <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{f(v.maxAbsPitchDeg, 2, '°')} / {f(v.rmsPitchDeg, 2, '°')}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: C.border }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>MAI CỰC ĐẠI / TRUNG BÌNH:</Text>
            <Text style={{ color: C.amber, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{n(v.maiMax)} / {n(v.maiAvg)}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: C.border }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>THỜI LƯỢNG MAI &gt; 70:</Text>
            <Text style={{ color: C.red, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{n(v.maiCautionMinutes, ' min')}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 4 }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>ĐỒNG THUẬN BASELINE B:</Text>
            <Text style={{ color: C.green, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{n(v.agreementPercent, '%')}</Text>
          </View>
        </View>
      </Panel>

      {/* 4. Classification Breakdown */}
      <Panel title="PHÂN BỐ TRẠNG THÁI RANDOM FOREST" tag="AI MODEL">
        <View style={{ height: 12, backgroundColor: '#D0DDEB', borderRadius: 4, overflow: 'hidden', flexDirection: 'row', marginVertical: 8 }}>
          <View style={{ width: `${v.rfDistribution.normalPct ?? 0}%`, backgroundColor: C.green }} />
          <View style={{ width: `${v.rfDistribution.highRollPct ?? 0}%`, backgroundColor: C.amber }} />
          <View style={{ width: `${v.rfDistribution.persistentOffsetPct ?? 0}%`, backgroundColor: '#38BDF8' }} />
          <View style={{ width: `${v.rfDistribution.amplitudeGrowthPct ?? 0}%`, backgroundColor: C.red }} />
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10, marginTop: 4 }}>
          <Text style={{ color: C.green, fontSize: 10, fontFamily: 'monospace' }}>● NORMAL: {n(v.rfDistribution.normalPct, '%')}</Text>
          <Text style={{ color: C.amber, fontSize: 10, fontFamily: 'monospace' }}>● HIGH_ROLL: {n(v.rfDistribution.highRollPct, '%')}</Text>
          <Text style={{ color: '#38BDF8', fontSize: 10, fontFamily: 'monospace' }}>● OFFSET: {n(v.rfDistribution.persistentOffsetPct, '%')}</Text>
          <Text style={{ color: C.red, fontSize: 10, fontFamily: 'monospace' }}>● GROWTH: {n(v.rfDistribution.amplitudeGrowthPct, '%')}</Text>
        </View>
      </Panel>

      {/* 5. Navigation CTAs */}
      <ActionBtn
        label="XEM BÁO CÁO KIỂM TOÁN CHI TIẾT →"
        onPress={() => actions.go('ReportDetails')}
      />
      <ActionBtn
        tone="neutral"
        label="PHÁT LẠI HÀNH TRÌNH (REPLAY & REVIEW) →"
        onPress={() => actions.go('ReplayReview')}
      />
    </Page>
  );
}

export function ReportDetailsScreen({ data, actions }: ScreenProps) {
  const v = data.voyage;

  // Compute cargo risk evidence from reviews in alarms
  const tpCount = data.alarms.filter((a) => a.review === 'TRUE').length;
  const fpCount = data.alarms.filter((a) => a.review === 'FALSE').length;
  const uncertCount = data.alarms.filter((a) => !a.review || a.review === 'UNCERTAIN').length;

  const exportCsvDemo = () => {
    Alert.alert(
      'XUẤT DỮ LIỆU CSV (121 MẪU)',
      data.mode === 'live'
        ? `Backend cung cấp CSV tại GET /api/v1/voyages/${v.id}/telemetry.csv (cần JWT). Ứng dụng mobile chưa hỗ trợ tải tệp có xác thực; hãy tải bằng dashboard web.\n\nSố bản ghi: ${n(v.sampleCount)}`
        : `Đã chuẩn bị tệp SVMG_${v.id}_telemetry.csv gồm 121 mẫu dữ liệu chuyển động (đúng chuẩn fixture T11/T15).\n\nCấu trúc: seq, t_sim_s, roll_deg, pitch_deg, source_mode, synthetic\nSố lượng: ${v.sampleCount} bản ghi\nThời lượng: 600s.`
    );
  };

  const exportPdfNotice = () => {
    Alert.alert(
      'BÁO CÁO PDF CHÍNH THỨC',
      data.mode === 'live'
        ? `Backend sinh PDF tại GET /api/v1/voyages/${v.id}/report.pdf (cần JWT). Ứng dụng mobile chưa hỗ trợ tải tệp có xác thực; hãy tải bằng dashboard web.`
        : 'Dịch vụ xuất bản PDF chính thức có chứng thư số đang chờ Backend TV3 Report Service tích hợp.\n\nTrong chế độ Mock, toàn bộ thông số kiểm toán đã được hiển thị trực tiếp và đầy đủ trên màn hình này.'
    );
  };

  return (
    <Page
      vesselName={data.vesselName}
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="VOYAGE REPORT DETAILS"
      subtitle="BÁO CÁO KIỂM TOÁN HÀNH TRÌNH — BẢNG 8.3"
      onBack={actions.back}
    >
      {/* Section 1: Voyage Metadata */}
      <Panel title="THÔNG TIN HÀNH TRÌNH & THIẾT BỊ" tag="BẢNG 8.3 §1">
        <View style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Mã chuyến đi:</Text>
            <Text style={{ color: C.cyan, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{v.id}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Thiết bị giám sát:</Text>
            <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace' }}>{v.deviceId}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Thời lượng giám sát:</Text>
            <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace' }}>{data.mode === 'live' ? n(v.durationMinutes, ' phút') : `${v.durationMinutes} phút (121 mẫu / 600s)`}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Nguồn dữ liệu:</Text>
            <Text style={{ color: C.amber, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{v.sourceMode}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Phiên bản mô hình AI:</Text>
            <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace' }}>{v.modelVersion}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Phiên bản cấu hình:</Text>
            <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace' }}>{v.configVersion === null ? '—' : `v${v.configVersion}`}</Text>
          </View>
        </View>
      </Panel>

      {/* Kinematic Statistical Distribution & RF Breakdown Charts */}
      <MobileVoyageDistributionChart voyage={v} />
      <MobileRfBreakdownChart voyage={v} />

      {/* Section 2: Kinematic Statistics Audit (T11 Recomputed) */}
      <Panel title="THỐNG KÊ ĐỘNG HỌC (T11 RECOMPUTED)" tag="KIỂM TOÁN T11">
        <View style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Tổng số mẫu (Sample Count):</Text>
            <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{n(v.sampleCount)}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Roll cực đại (Max |Roll|):</Text>
            <Text style={{ color: C.red, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{f(v.maxAbsRollDeg, 2, '°')}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>RMS Roll (Khớp chuẩn T11):</Text>
            <Text style={{ color: C.cyan, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{f(v.rmsRollDeg, 2, '°')}{data.mode === 'mock' ? ' (7.083967°)' : ''}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>P95 Roll (Khớp chuẩn T11):</Text>
            <Text style={{ color: C.amber, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{f(v.p95AbsRollDeg, 2, '°')}{data.mode === 'mock' ? ' (13.36°)' : ''}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Pitch cực đại / RMS Pitch:</Text>
            <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace' }}>{f(v.maxAbsPitchDeg, 2, '°')} / {f(v.rmsPitchDeg, 2, '°')}</Text>
          </View>
        </View>
        <Text style={[styles.rollbackNote, { marginTop: 8 }]}>
          * Các chỉ số trên được tính toán độc lập và trùng khớp hoàn toàn với kịch bản kiểm thử T11 fixture.
        </Text>
      </Panel>

      {/* Section 3: Anomaly Index & AI Distribution */}
      <Panel title="CHỈ SỐ BẤT THƯỜNG MAI & SO SÁNH AI" tag="BẢNG 8.3 §3 & §6">
        <View style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>MAI Cực đại / Trung bình:</Text>
            <Text style={{ color: C.amber, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{n(v.maiMax)} / {n(v.maiAvg)}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Thời lượng MAI &gt; 70:</Text>
            <Text style={{ color: C.red, fontSize: 12, fontFamily: 'monospace' }}>{n(v.maiCautionMinutes, ' phút')}</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Tỉ lệ đồng thuận RF & Baseline B:</Text>
            <Text style={{ color: C.green, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{n(v.agreementPercent, '%')}</Text>
          </View>
        </View>
      </Panel>

      {/* Section 4: Alarm Log */}
      <Panel title="NHẬT KÝ SỰ KIỆN CẢNH BÁO" tag={`${data.alarms.length} SỰ KIỆN`}>
        {data.alarms.map((x) => (
          <LinkRow
            key={x.id}
            title={`${x.id} • ${x.level}`}
            subtitle={`${x.title} | Trạng thái: ${x.status}`}
            onPress={() => {
              actions.selectAlarm(x.id);
              actions.go('AlarmDetail');
            }}
          />
        ))}
      </Panel>

      {/* Section 5: Cargo Risk Event Evidence */}
      <Panel title="BẰNG CHỨNG RỦI RO HÀNG HÓA & PHẢN HỒI" tag="CARGO EVIDENCE">
        <View style={{ gap: 6 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Xác nhận đúng (True Positive):</Text>
            <Text style={{ color: C.green, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{tpCount} sự kiện</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Báo giả (False Positive):</Text>
            <Text style={{ color: C.red, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>{fpCount} sự kiện</Text>
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <Text style={{ color: C.muted, fontSize: 11, fontFamily: 'monospace' }}>Chưa rõ / Chưa đánh giá:</Text>
            <Text style={{ color: C.amber, fontSize: 12, fontFamily: 'monospace' }}>{uncertCount} sự kiện</Text>
          </View>
        </View>
        <Text style={[styles.rollbackNote, { marginTop: 6 }]}>
          * Thống kê này được cập nhật tự động khi người trực gắn nhãn tại màn hình Replay & Review.
        </Text>
      </Panel>

      {/* Section 6: Official Dossiers & Exports */}
      <Panel title="HỒ SƠ HÀNH TRÌNH & XUẤT DỮ LIỆU" tag="EXPORTS">
        <View style={{ gap: 10 }}>
          <View style={{ padding: 10, borderRadius: 6, backgroundColor: C.panel2, borderWidth: 1, borderColor: C.borderSubtle }}>
            <Text style={{ color: C.text, fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' }}>
              DỮ LIỆU TELEMETRY CSV (121 MẪU)
            </Text>
            <Text style={{ color: C.muted, fontSize: 10, marginTop: 2 }}>
              Tệp CSV chuẩn chứa chuỗi thời gian roll, pitch và nhãn mô phỏng.
            </Text>
            <View style={{ marginTop: 8 }}>
              <ActionBtn label="XUẤT CSV DEMO" onPress={exportCsvDemo} />
            </View>
          </View>

          <View style={{ padding: 10, borderRadius: 6, backgroundColor: C.panel2, borderWidth: 1, borderColor: C.borderSubtle }}>
            <Text style={{ color: C.text, fontSize: 12, fontWeight: 'bold', fontFamily: 'monospace' }}>
              BÁO CÁO KIỂM TOÁN PDF CHÍNH THỨC
            </Text>
            <Text style={{ color: C.muted, fontSize: 10, marginTop: 2 }}>
              Dịch vụ sinh PDF có chữ ký số do TV3 Report Service xử lý từ CSDL.
            </Text>
            <View style={{ marginTop: 8 }}>
              <ActionBtn tone="neutral" label="PDF – CHỜ BACKEND TV3" onPress={exportPdfNotice} />
            </View>
          </View>
        </View>
      </Panel>

      <ActionBtn
        tone="neutral"
        label="PHÁT LẠI HÀNH TRÌNH (REPLAY & REVIEW) →"
        onPress={() => actions.go('ReplayReview')}
      />
    </Page>
  );
}

export function ReplayReviewScreen({ data, actions }: ScreenProps) {
  const points = data.replayPoints || [];
  const endT = points.length ? points[points.length - 1].t_sim_s : 0;
  const curIdx = Math.min(points.length - 1, Math.max(0, data.replayIndex || 0));
  const cur = points[curIdx] || points[0] || {
    seq: 0,
    t_sim_s: 0,
    roll: 0,
    pitch: 0,
    class_rf: 'NORMAL' as const,
    class_baseline_b: 'NORMAL' as const,
    mai: null as number | null,
    alarm_level: 'NORMAL' as const,
  };

  if (data.mode === 'live' && points.length === 0) {
    return (
      <Page
        vesselName={data.vesselName}
        utcTime={data.telemetry.utc_time}
        isHornMuted={data.buzzerMuted}
        onToggleHorn={actions.toggleBuzzer}
        title="REPLAY & REVIEW"
        subtitle="PHÁT LẠI CHUYẾN ĐI • DỮ LIỆU BACKEND"
        onBack={actions.back}
      >
        <Panel title="CHƯA CÓ DỮ LIỆU PHÁT LẠI" tag="BACKEND">
          <Text style={styles.secNote}>
            Chuyến đi đang chọn chưa có telemetry hợp lệ (hoặc đang tải). Hãy tạo chuyến đi cho thiết bị trên Backend
            rồi quay lại.
          </Text>
        </Panel>
      </Page>
    );
  }

  // Extract trailing 40 samples around current index for waveform display
  const windowCount = 40;
  const startIdx = Math.max(0, curIdx - windowCount + 1);
  const slice = points.slice(startIdx, curIdx + 1);
  const rollWave = slice.map((p) => p.roll);
  const pitchWave = slice.map((p) => p.pitch);

  // Check if current position matches an alarm event
  const activeAlarm = data.mode === 'live'
    ? cur.alarm_id
      ? data.alarms.find((a) => a.title.startsWith(`${cur.alarm_id} `))
      : undefined
    : data.alarms.find(
    (a) =>
      (a.id === 'ALM-8441' && Math.abs(cur.t_sim_s - 60) <= 15) ||
      (a.id === 'ALM-8450' && Math.abs(cur.t_sim_s - 150) <= 15) ||
      (a.id === 'ALM-8488' && Math.abs(cur.t_sim_s - 320) <= 15) ||
      (a.id === 'ALM-8492' && Math.abs(cur.t_sim_s - 480) <= 15)
  );

  return (
    <Page
      vesselName={data.vesselName}
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="REPLAY & REVIEW"
      subtitle={`PHÁT LẠI CHUYẾN ĐI • ${points.length} MẪU DỮ LIỆU ĐỘNG HỌC`}
      onBack={actions.back}
    >
      {/* 1. Playhead Telemetry Readout */}
      <Panel title="ĐỒNG HỒ PHÁT LẠI & THÔNG SỐ HIỆN TẠI" tag={`MẪU ${curIdx + 1}/${points.length}`}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
          <View>
            <Text style={{ color: C.muted, fontSize: 10, fontFamily: 'monospace' }}>MỐC THỜI GIAN VIRTUAL:</Text>
            <Text style={{ color: C.cyan, fontSize: 20, fontFamily: 'monospace', fontWeight: 'bold' }}>
              T+{cur.t_sim_s}s
            </Text>
          </View>
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={{ color: C.muted, fontSize: 10, fontFamily: 'monospace' }}>TRẠNG THÁI RF:</Text>
            <Text
              style={{
                color: cur.class_rf === 'NORMAL' ? C.green : cur.class_rf === 'AMPLITUDE_GROWTH' ? C.red : C.amber,
                fontSize: 13,
                fontFamily: 'monospace',
                fontWeight: 'bold',
              }}
            >
              {cur.class_rf}
            </Text>
          </View>
        </View>

        <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 10, paddingTop: 8, borderTopWidth: 1, borderTopColor: C.border }}>
          <View>
            <Text style={{ color: C.muted, fontSize: 10, fontFamily: 'monospace' }}>ROLL:</Text>
            <Text style={{ color: Math.abs(cur.roll) > 12 ? C.red : C.cyan, fontSize: 15, fontFamily: 'monospace', fontWeight: 'bold' }}>
              {cur.roll > 0 ? '+' : ''}{cur.roll.toFixed(1)}°
            </Text>
          </View>
          <View>
            <Text style={{ color: C.muted, fontSize: 10, fontFamily: 'monospace' }}>PITCH:</Text>
            <Text style={{ color: C.amber, fontSize: 15, fontFamily: 'monospace', fontWeight: 'bold' }}>
              {cur.pitch > 0 ? '+' : ''}{cur.pitch.toFixed(1)}°
            </Text>
          </View>
          <View>
            <Text style={{ color: C.muted, fontSize: 10, fontFamily: 'monospace' }}>MAI INDEX:</Text>
            <Text style={{ color: (cur.mai ?? 0) > 70 ? C.red : C.amber, fontSize: 15, fontFamily: 'monospace', fontWeight: 'bold' }}>
              {n(cur.mai)} / 100
            </Text>
          </View>
          <View>
            <Text style={{ color: C.muted, fontSize: 10, fontFamily: 'monospace' }}>BASELINE B:</Text>
            <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace' }}>
              {cur.class_baseline_b}
            </Text>
          </View>
        </View>
      </Panel>

      {/* 2D Vessel Visualizer Synchronized with Replay Playhead */}
      <Panel title="TRỰC QUAN HÓA THÂN TÀU (REPLAY DYNAMICS)" tag={`T+${cur.t_sim_s}s`}>
        <Inclinometer
          rollDeg={cur.roll}
          pitchDeg={cur.pitch}
          mai={cur.mai}
          alarmLevel={cur.alarm_level}
          scenario="S0"
          classRf={cur.class_rf}
          sensorOk={true}
          sourceLabel={data.mode === 'live' ? points[curIdx]?.source_mode : undefined}
          compact={false}
        />
      </Panel>

      {/* 2. Waveform Visualizer */}
      <Panel title="ĐỒ THỊ DAO ĐỘNG THEO THỜI GIAN PHÁT LẠI" tag="WAVEFORM SLICE">
        <MotionChart roll={rollWave} pitch={pitchWave} height={140} />
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 6 }}>
          <Text style={{ color: C.muted, fontSize: 9, fontFamily: 'monospace' }}>Lịch sử {slice.length ? Math.round(cur.t_sim_s - slice[0].t_sim_s) : 0}s trước</Text>
          <Text style={{ color: C.cyan, fontSize: 9, fontFamily: 'monospace' }}>Playhead Cursor: T+{cur.t_sim_s}s</Text>
        </View>
      </Panel>

      {/* 3. Event Marker Alert Banner */}
      {activeAlarm && (
        <View
          style={{
            backgroundColor: activeAlarm.level === 'CRITICAL' ? C.errorContainerBg : C.warningContainerBg,
            borderWidth: 1,
            borderColor: activeAlarm.level === 'CRITICAL' ? C.red : C.amber,
            borderRadius: 6,
            padding: 10,
            marginBottom: 12,
          }}
        >
          <Text style={{ color: activeAlarm.level === 'CRITICAL' ? C.red : C.amber, fontSize: 11, fontWeight: 'bold', fontFamily: 'monospace' }}>
            ⚠️ SỰ KIỆN CẢNH BÁO TẠI MỐC T+{cur.t_sim_s}s: {activeAlarm.id}
          </Text>
          <Text style={{ color: C.text, fontSize: 11, marginTop: 2 }}>
            {activeAlarm.title} — Mức độ: {activeAlarm.level}
          </Text>
        </View>
      )}

      {/* 4. Transport Deck & Scrubber */}
      <Panel title="BỘ ĐIỀU KHIỂN PHÁT LẠI (TRANSPORT DECK)" tag="ĐIỀU KHIỂN">
        {/* Scrubber slider bar representation */}
        <View style={{ marginBottom: 12 }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
            <Text style={{ color: C.muted, fontSize: 10, fontFamily: 'monospace' }}>0s (Bắt đầu)</Text>
            <Text style={{ color: C.cyan, fontSize: 11, fontFamily: 'monospace', fontWeight: 'bold' }}>T+{cur.t_sim_s}s / {endT}s</Text>
            <Text style={{ color: C.muted, fontSize: 10, fontFamily: 'monospace' }}>{endT}s (Kết thúc)</Text>
          </View>
          <View style={{ height: 10, backgroundColor: '#D0DDEB', borderRadius: 5, overflow: 'hidden', position: 'relative' }}>
            <View
              style={{
                width: `${(curIdx / Math.max(1, points.length - 1)) * 100}%`,
                height: '100%',
                backgroundColor: C.cyan,
              }}
            />
          </View>
        </View>

        {/* Primary Controls */}
        <View style={{ flexDirection: 'row', gap: 6, marginBottom: 10 }}>
          <View style={{ flex: 1 }}>
            <ActionBtn
              tone={data.replayPlaying ? 'primary' : 'secondary'}
              label={data.replayPlaying ? '❚❚ TẠM DỪNG' : '▶ PHÁT TIẾP'}
              onPress={() => actions.setReplayPlaying(!data.replayPlaying)}
            />
          </View>
          <View style={{ flex: 1 }}>
            <ActionBtn
              tone="neutral"
              label="VỀ ĐẦU (0s)"
              onPress={() => {
                actions.setReplayIndex(0);
                actions.setReplayPlaying(false);
              }}
            />
          </View>
        </View>

        <TwoCol>
          <ActionBtn
            tone="neutral"
            label={data.mode === 'live' ? '−2 MẪU (LÙI)' : '−10s (LÙI)'}
            onPress={() => actions.setReplayIndex(Math.max(0, curIdx - 2))}
          />
          <ActionBtn
            tone="neutral"
            label={data.mode === 'live' ? '+2 MẪU (TIẾN)' : '+10s (TIẾN)'}
            onPress={() => actions.setReplayIndex(Math.min(points.length - 1, curIdx + 2))}
          />
        </TwoCol>

        {/* Playback Speed Selector */}
        <View style={{ marginTop: 12, paddingTop: 8, borderTopWidth: 1, borderTopColor: C.border }}>
          <Text style={{ color: C.muted, fontSize: 10, fontFamily: 'monospace', marginBottom: 6 }}>
            TỐC ĐỘ PHÁT LẠI:
          </Text>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {[1, 5, 10, 20, 60].map((spd) => {
              const active = data.replaySpeed === spd;
              return (
                <Pressable
                  key={spd}
                  onPress={() => actions.setReplaySpeed(spd)}
                  style={{
                    flex: 1,
                    paddingVertical: 6,
                    borderRadius: 4,
                    alignItems: 'center',
                    borderWidth: 1,
                    borderColor: active ? C.cyan : C.border,
                    backgroundColor: active ? '#EAF2FA' : C.panel,
                  }}
                >
                  <Text style={{ color: active ? C.cyan : C.muted, fontSize: 11, fontFamily: 'monospace', fontWeight: 'bold' }}>
                    ×{spd}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>
      </Panel>

      {/* 5. Watchstander Alarm Review Deck */}
      <Panel title="ĐÁNH GIÁ CẢNH BÁO CỦA NGƯỜI TRỰC (REVIEW)" tag="CARGO RISK EVIDENCE">
        <Text style={[styles.secNote, { marginBottom: 10 }]}>
          Gắn nhãn nhận định người trực cho các sự kiện cảnh báo trong chuyến đi. {data.mode === 'live' ? 'Nhãn được lưu lên Backend (cần quyền Supervisor trở lên).' : 'Đánh giá được lưu trực tiếp vào Mock State và cập nhật tỷ lệ chính xác vận hành:'}
        </Text>
        {data.alarms.map((alarm) => (
          <View
            key={alarm.id}
            style={{
              paddingVertical: 8,
              borderBottomWidth: 1,
              borderBottomColor: C.border,
              gap: 6,
            }}
          >
            <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
              <Text style={{ color: C.text, fontSize: 12, fontFamily: 'monospace', fontWeight: 'bold' }}>
                {alarm.id} • {alarm.title}
              </Text>
              <Text
                style={{
                  color: alarm.review === 'TRUE' ? C.green : alarm.review === 'FALSE' ? C.red : C.amber,
                  fontSize: 10,
                  fontFamily: 'monospace',
                  fontWeight: 'bold',
                }}
              >
                {alarm.review ? `[${alarm.review}]` : '[CHƯA ĐÁNH GIÁ]'}
              </Text>
            </View>
            <Text style={{ color: C.muted, fontSize: 10 }}>
              Mức độ: {alarm.level} • Thời điểm: {alarm.at}
            </Text>
            <View style={{ flexDirection: 'row', gap: 6, marginTop: 4 }}>
              {(['TRUE', 'FALSE', 'UNCERTAIN'] as const).map((lbl) => (
                <Pressable
                  key={lbl}
                  onPress={async () => {
                    const r = await actions.reviewAlarm(alarm.id, lbl);
                    if (!r.ok) Alert.alert('KHÔNG LƯU ĐƯỢC NHÃN', r.message);
                  }}
                  style={{
                    flex: 1,
                    paddingVertical: 6,
                    borderRadius: 4,
                    alignItems: 'center',
                    borderWidth: 1,
                    borderColor: alarm.review === lbl ? (lbl === 'TRUE' ? C.green : lbl === 'FALSE' ? C.red : C.amber) : C.border,
                    backgroundColor: alarm.review === lbl ? '#EAF2FA' : C.panel,
                  }}
                >
                  <Text
                    style={{
                      color: alarm.review === lbl ? C.cyan : C.muted,
                      fontSize: 10,
                      fontFamily: 'monospace',
                      fontWeight: 'bold',
                    }}
                  >
                    {lbl === 'TRUE' ? '✓ ĐÚNG' : lbl === 'FALSE' ? '✗ SAI' : '? CHƯA RÕ'}
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
        ))}
      </Panel>
    </Page>
  );
}
const styles = StyleSheet.create({
  disclaimerBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: '#2A1D0B',
    borderWidth: 1,
    borderColor: '#7A5B2B',
    borderRadius: 5,
    padding: 10,
  },
  disclaimerIcon: {
    fontSize: 16,
  },
  disclaimerText: {
    color: '#F2CA73',
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.3,
    flex: 1,
    lineHeight: 13,
  },
  cfgRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: C.borderSubtle,
  },
  cfgItem: {
    flex: 1,
    gap: 2,
  },
  cfgLabel: {
    color: C.muted,
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  cfgVal: {
    color: C.text,
    fontSize: 12,
    fontWeight: '700',
  },
  activeProfileBadge: {
    backgroundColor: C.primaryContainer,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 3,
    alignSelf: 'flex-start',
  },
  activeProfileText: {
    color: C.canvas,
    fontSize: 10,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  thresholdBento: {
    flexDirection: 'row',
    gap: 6,
    marginTop: 6,
  },
  thresholdTile: {
    flex: 1,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 4,
    padding: 8,
    alignItems: 'center',
    gap: 2,
  },
  thresholdTileLabel: {
    color: C.muted,
    fontSize: 8,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  thresholdTileVal: {
    fontSize: 16,
    fontWeight: '800',
    fontVariant: ['tabular-nums'],
  },
  thresholdTileSub: {
    color: C.textSecondary,
    fontSize: 8,
  },
  secNote: {
    color: C.textSecondary,
    fontSize: 11,
    lineHeight: 15,
  },
  profileButtonGroup: {
    flexDirection: 'row',
    gap: 6,
  },
  profileSelectBtn: {
    flex: 1,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 5,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  profileSelectBtnActive: {
    backgroundColor: '#EAF2FA',
    borderColor: C.borderFocus,
  },
  profileSelectBtnText: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '800',
    textAlign: 'center',
  },
  profileSelectBtnTextActive: {
    color: C.cyanBright,
  },
  rollbackWell: {
    gap: 4,
    marginTop: 4,
  },
  rollbackNote: {
    color: C.muted,
    fontSize: 9,
    textAlign: 'center',
  },
  commandRowCard: {
    backgroundColor: C.bg,
    borderWidth: 1,
    borderLeftWidth: 3,
    borderColor: C.border,
    borderRadius: 5,
    padding: 10,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  commandRowTitle: {
    color: C.text,
    fontSize: 12,
    fontWeight: '700',
  },
  commandRowSub: {
    color: C.muted,
    fontSize: 10,
    lineHeight: 14,
  },
  conditionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 2,
  },
  conditionLabel: {
    color: C.muted,
    fontSize: 9,
  },
  conditionVal: {
    fontSize: 9,
    fontWeight: '800',
  },
  adminSection: {
    gap: 6,
    paddingVertical: 4,
    borderBottomWidth: 1,
    borderBottomColor: C.borderSubtle,
  },
  adminSectionTitle: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  buttonTrio: {
    flexDirection: 'row',
    gap: 6,
  },
  trioBtn: {
    flex: 1,
    minHeight: 38,
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 4,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  trioBtnActive: {
    backgroundColor: C.primaryContainer,
    borderColor: C.cyan,
  },
  trioBtnText: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '800',
    textAlign: 'center',
  },
  trioBtnTextActive: {
    color: C.canvas,
  },
  scenarioGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  scenarioBtn: {
    width: '48%',
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 4,
    padding: 8,
    gap: 2,
  },
  scenarioBtnActive: {
    backgroundColor: '#EAF2FA',
    borderColor: C.borderFocus,
  },
  scenarioBtnText: {
    color: C.muted,
    fontSize: 11,
    fontWeight: '800',
  },
  scenarioBtnTextActive: {
    color: C.cyanBright,
  },
  scenarioBtnDesc: {
    color: C.textSecondary,
    fontSize: 9,
  },
  btnDisabledOpacity: {
    opacity: 0.35,
  },
  emptyHistoryText: {
    color: C.muted,
    fontSize: 11,
    textAlign: 'center',
    paddingVertical: 12,
  },
  historyList: {
    gap: 8,
  },
  historyCard: {
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 5,
    padding: 10,
    gap: 4,
  },
  historyHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  cmdTitleCol: {
    gap: 1,
  },
  cmdIdText: {
    color: C.muted,
    fontSize: 9,
    fontFamily: 'monospace',
    fontWeight: '700',
  },
  cmdNameText: {
    color: C.text,
    fontSize: 12,
    fontWeight: '800',
  },
  cmdStatusPill: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 3,
    borderWidth: 1,
  },
  cmdStatusText: {
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  historyMetaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 2,
  },
  historyMetaTime: {
    color: C.muted,
    fontSize: 9,
  },
  historyMetaUser: {
    color: C.muted,
    fontSize: 9,
  },
  historyMetaVer: {
    color: C.cyan,
    fontSize: 9,
    fontWeight: '700',
  },
  historyDetailText: {
    color: C.textSecondary,
    fontSize: 10,
    lineHeight: 14,
    marginTop: 2,
  },
});
