import React, { useMemo, useState } from 'react';
import { FlatList, Pressable, StyleSheet, Text, View } from 'react-native';
import {
  Action,
  LinkRow,
  MetricCard,
  Page,
  Panel,
  Pill,
  TwoCol,
} from '../components/UI';
import { MobileModelConcordanceChart } from '../components/MobileModelConcordanceChart';
import { FONT, SHADOWS, useTheme } from '../theme';
import { FeatureItem, Route, ScreenProps } from '../types/domain';
import {
  CONTRACT_ID,
  CONTRACT_SOURCE_EXPORT,
  CONTRACT_VERSION,
  TOTAL_FEATURES,
} from '../featureRegistry';
import { getRFClassNameVi, getRoleNameVi } from '../i18n/vi';

/**
 * MÀN HÌNH THÊM (More / Navigation Hub)
 */
export function MoreScreen({ data, actions }: ScreenProps) {
  const { colors, mode, setMode } = useTheme();
  const isOp = data.session?.role === 'Operator';

  const items: { title: string; subtitle: string; route: Route; badge?: string }[] = [
    {
      title: 'Trung tâm điều khiển',
      subtitle: 'Cấu hình ngưỡng an toàn, hiệu chuẩn điểm 0 và gửi lệnh thiết bị',
      route: 'ControlCenter',
    },
    {
      title: 'Báo cáo hành trình',
      subtitle: 'Tổng hợp thống kê chuyến đi, biểu đồ phân phối và xuất CSV',
      route: 'VoyageReports',
    },
    {
      title: 'Phát lại và đánh giá',
      subtitle: 'Phát lại chuỗi thời gian 121 mẫu và thẩm định cảnh báo',
      route: 'ReplayReview',
    },
    {
      title: 'Tình trạng thiết bị',
      subtitle: 'Chẩn đoán ESP32, cảm biến MPU6050, bus I2C và bộ đệm Flash',
      route: 'DeviceHealth',
    },
    {
      title: 'Giám sát mô hình',
      subtitle: isOp
        ? 'Chỉ dành cho Giám sát viên và Quản trị viên (Bảng 3.1)'
        : 'Random Forest, Baseline B, PSI và 23 đặc trưng động học',
      route: 'ModelMonitor',
      badge: isOp ? 'Giới hạn quyền' : undefined,
    },
  ];

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="Thêm & Hệ thống"
      subtitle="Danh mục chức năng vận hành, giao diện và tài khoản trực ca"
    >
      {/* Operations Hub */}
      <Panel title="Chức năng vận hành & Giám sát">
        <View style={{ gap: 10 }}>
          {items.map((x) => (
            <LinkRow
              key={x.route}
              title={x.title}
              subtitle={x.subtitle}
              badge={x.badge}
              onPress={() => actions.go(x.route)}
            />
          ))}
        </View>
      </Panel>

      {/* Theme Selector */}
      <Panel title="Giao diện hiển thị">
        <View style={{ gap: 10 }}>
          <Pressable
            onPress={() => setMode('light')}
            style={[
              styles.themeOptCard,
              {
                borderColor: mode === 'light' ? colors.tech : colors.borderSubtle,
                backgroundColor: mode === 'light' ? colors.cyanContainerBg : colors.panel2,
              },
            ]}
            accessibilityRole="button"
          >
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={[styles.themeOptTitle, { color: colors.title }]}>
                ☀ Giao diện Sáng (Mặc định)
              </Text>
              <Text style={[styles.themeOptSub, { color: colors.textSecondary }]}>
                Nền sáng #F0F4F8, thẻ trắng sạch, chữ navy #142D45
              </Text>
            </View>
            {mode === 'light' && (
              <Text style={[styles.themeActiveText, { color: colors.tech }]}>● Đang dùng</Text>
            )}
          </Pressable>

          <Pressable
            onPress={() => setMode('dark')}
            style={[
              styles.themeOptCard,
              {
                borderColor: mode === 'dark' ? colors.tech : colors.borderSubtle,
                backgroundColor: mode === 'dark' ? colors.cyanContainerBg : colors.panel2,
              },
            ]}
            accessibilityRole="button"
          >
            <View style={{ flex: 1, gap: 2 }}>
              <Text style={[styles.themeOptTitle, { color: colors.title }]}>
                🌙 Giao diện Tối (Buồng lái đêm)
              </Text>
              <Text style={[styles.themeOptSub, { color: colors.textSecondary }]}>
                Giảm chói mắt khi trực ca ban đêm, độ tương phản cao
              </Text>
            </View>
            {mode === 'dark' && (
              <Text style={[styles.themeActiveText, { color: colors.tech }]}>● Đang dùng</Text>
            )}
          </Pressable>
        </View>
      </Panel>

      {/* Account Info */}
      <Panel title="Thông tin tài khoản">
        <View style={{ gap: 8 }}>
          <View style={styles.metaRow}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Tên đăng nhập</Text>
            <Text style={[styles.metaVal, { color: colors.title }]}>
              {data.session?.username || '—'}
            </Text>
          </View>
          <View style={styles.metaRow}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Vai trò (Bảng 3.1)</Text>
            <Text style={[styles.metaVal, { color: colors.tech }]}>
              {getRoleNameVi(data.session?.role)}
            </Text>
          </View>
          <View style={[styles.metaRow, { borderBottomWidth: 0 }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Nguồn dữ liệu</Text>
            <Text style={[styles.metaVal, { color: colors.green }]}>Dữ liệu mô phỏng</Text>
          </View>
        </View>
      </Panel>

      <Action tone="danger" label="Đăng xuất khỏi hệ thống" onPress={actions.logout} />
    </Page>
  );
}

/**
 * MÀN HÌNH 7: TÌNH TRẠNG THIẾT BỊ (Device Health)
 */
export function DeviceHealthScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const [showTechDetails, setShowTechDetails] = useState(false);

  const h = data.health;
  const isOffline = data.scenario === 'OFFLINE';
  const isSensorFault = data.scenario === 'SENSOR_FAULT';
  const cal = data.config.zero_calibration;

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="Tình trạng thiết bị"
      subtitle="Chẩn đoán ESP32, cảm biến MPU6050, kết nối và bộ đệm ngoại tuyến"
      onBack={actions.back}
    >
      {/* 1. Priority Incident / Health Status Banner */}
      {isOffline ? (
        <View
          style={[
            styles.calloutBanner,
            { borderColor: colors.red, backgroundColor: colors.errorContainerBg },
          ]}
        >
          <Text style={[styles.calloutTitle, { color: colors.red }]}>
            Mất kết nối thiết bị
          </Text>
          <Text style={[styles.calloutText, { color: colors.title }]}>
            Thiết bị ngắt liên lạc MQTT (&gt; 30s). Hệ thống không tự tạo số đo thay thế và đang lưu đệm dữ liệu trên bộ nhớ Flash ESP32.
          </Text>
        </View>
      ) : isSensorFault ? (
        <View
          style={[
            styles.calloutBanner,
            { borderColor: colors.amber, backgroundColor: colors.warningContainerBg },
          ]}
        >
          <Text style={[styles.calloutTitle, { color: colors.amber }]}>
            Lỗi cảm biến MPU6050
          </Text>
          <Text style={[styles.calloutText, { color: colors.title }]}>
            Phát hiện {h.i2cErrors} lỗi trên bus I2C (NACK timeout). Dữ liệu góc nghiêng tạm thời không hợp lệ.
          </Text>
        </View>
      ) : (
        <View
          style={[
            styles.calloutBanner,
            { borderColor: colors.green, backgroundColor: colors.greenContainerBg },
          ]}
        >
          <Text style={[styles.calloutTitle, { color: colors.green }]}>
            Thiết bị hoạt động bình thường
          </Text>
          <Text style={[styles.calloutText, { color: colors.title }]}>
            ESP32 kết nối ổn định, cảm biến MPU6050 truyền nhận dữ liệu chu kỳ 5.0s đạt chuẩn.
          </Text>
        </View>
      )}

      {/* 2. Key Metrics 2x2 Grid */}
      <TwoCol>
        <MetricCard
          label="Điểm sức khỏe"
          value={`${h.healthScore} / 100`}
          subtext={
            h.healthStatus === 'HEALTHY'
              ? 'Ổn định'
              : h.healthStatus === 'DEGRADED'
              ? 'Suy giảm'
              : 'Nguy cấp'
          }
          color={h.healthScore >= 80 ? colors.green : h.healthScore >= 40 ? colors.amber : colors.red}
        />
        <MetricCard
          label="Trạng thái cảm biến"
          value={h.sensor === 'OK' ? 'Bình thường' : h.sensor === 'FAULT' ? 'Lỗi I2C' : 'Không rõ'}
          subtext={h.sensor === 'OK' ? 'MPU6050 kết nối tốt' : 'Kiểm tra phần cứng'}
          color={h.sensor === 'OK' ? colors.green : h.sensor === 'FAULT' ? colors.amber : colors.red}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="Lỗi bus I2C"
          value={String(h.i2cErrors)}
          subtext={h.i2cErrors > 0 ? 'Phát hiện NACK timeout' : '0 lỗi truyền thông'}
          color={h.i2cErrors > 0 ? colors.red : colors.green}
        />
        <MetricCard
          label="Tín hiệu WiFi RSSI"
          value={h.rssiDbm !== null ? `${h.rssiDbm} dBm` : '—'}
          subtext={h.rssiDbm !== null ? 'Thu phát ổn định' : 'Mất kết nối'}
          color={h.rssiDbm !== null ? colors.tech : colors.red}
        />
      </TwoCol>

      {/* 3. Connectivity & Offline Buffer */}
      <Panel title="Kết nối & Bộ đệm ngoại tuyến" tag={`${h.bufferUsed}/${h.bufferCapacity} mẫu`}>
        <View style={{ gap: 4 }}>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Trạng thái bộ đệm</Text>
            <Text
              style={[
                styles.metaVal,
                { color: h.bufferStatus === 'BUFFERING' ? colors.amber : colors.green },
              ]}
            >
              {h.bufferStatus === 'BUFFERING' ? 'Đang lưu bù Flash' : 'Đồng bộ trực tiếp'}
            </Text>
          </View>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Độ trễ hàng đợi</Text>
            <Text
              style={[
                styles.metaVal,
                { color: h.queueLatencyMs > 100 ? colors.amber : colors.green },
              ]}
            >
              {h.queueLatencyMs} ms
            </Text>
          </View>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Gói tin gần nhất</Text>
            <Text style={[styles.metaVal, { color: isOffline ? colors.red : colors.green }]}>
              {h.lastPacketUtc}
            </Text>
          </View>
          <View style={[styles.metaRow, { borderBottomWidth: 0 }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Thời gian hoạt động</Text>
            <Text style={[styles.metaVal, { color: colors.tech }]}>{h.uptimeMinutes} phút</Text>
          </View>
        </View>
      </Panel>

      {/* 4. Zero Calibration Status */}
      <Panel title="Hiệu chuẩn điểm 0">
        <View style={{ gap: 4 }}>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Trạng thái</Text>
            <Text style={[styles.metaVal, { color: cal ? colors.green : colors.textSecondary }]}>
              {cal ? 'Đã hiệu chuẩn (30s tĩnh)' : 'Mặc định nhà máy'}
            </Text>
          </View>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Độ lệch Roll</Text>
            <Text style={[styles.metaVal, { color: colors.tech }]}>
              {cal ? `${cal.roll_offset_deg > 0 ? '+' : ''}${cal.roll_offset_deg.toFixed(2)}°` : '0.00°'}
            </Text>
          </View>
          <View style={[styles.metaRow, { borderBottomWidth: 0 }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Độ lệch Pitch</Text>
            <Text style={[styles.metaVal, { color: colors.amber }]}>
              {cal ? `${cal.pitch_offset_deg > 0 ? '+' : ''}${cal.pitch_offset_deg.toFixed(2)}°` : '0.00°'}
            </Text>
          </View>
        </View>
        <View style={{ marginTop: 6 }}>
          <Action
            tone="neutral"
            label="Mở Trung tâm điều khiển để hiệu chuẩn →"
            onPress={() => actions.go('ControlCenter')}
          />
        </View>
      </Panel>

      {/* 5. Collapsible Technical Specs */}
      <Panel title="Thông số kỹ thuật chi tiết">
        <Pressable
          onPress={() => setShowTechDetails((v) => !v)}
          style={styles.collapseBtn}
          accessibilityRole="button"
        >
          <Text style={[styles.collapseBtnText, { color: colors.tech }]}>
            {showTechDetails ? '▾ Thu gọn thông số phần cứng' : '▸ Xem chi tiết phần cứng ESP32 & Bộ nhớ'}
          </Text>
        </Pressable>

        {showTechDetails && (
          <View style={{ gap: 4, marginTop: 4 }}>
            <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
              <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Mã thiết bị</Text>
              <Text style={[styles.metaVal, { color: colors.title }]}>vessel-demo-01</Text>
            </View>
            <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
              <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Tần số bus I2C</Text>
              <Text style={[styles.metaVal, { color: colors.title }]}>400 kHz</Text>
            </View>
            <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
              <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Bộ nhớ Heap trống</Text>
              <Text style={[styles.metaVal, { color: h.freeHeapKb < 80 ? colors.amber : colors.tech }]}>
                {h.freeHeapKb} KB (Tối thiểu {h.minFreeHeapKb} KB)
              </Text>
            </View>
            <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
              <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Thời gian suy luận AI</Text>
              <Text style={[styles.metaVal, { color: colors.tech }]}>{h.inferenceMs} ms / mẫu</Text>
            </View>
            <View style={[styles.metaRow, { borderBottomWidth: 0 }]}>
              <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Số lần kết nối lại MQTT</Text>
              <Text style={[styles.metaVal, { color: colors.title }]}>{h.mqttReconnects} lần</Text>
            </View>
          </View>
        )}
      </Panel>
    </Page>
  );
}

/**
 * MÀN HÌNH 8: GIÁM SÁT MÔ HÌNH & 23 ĐẶC TRƯNG (Model Monitor)
 */
export function ModelMonitorScreen({ data, actions }: ScreenProps) {
  const { colors } = useTheme();
  const isOp = data.session?.role === 'Operator';
  const m = data.model;
  const t = data.telemetry;

  const [featureGroupFilter, setFeatureGroupFilter] = useState<
    'ALL' | 'roll_60s' | 'roll_180s' | 'pitch_60s'
  >('ALL');
  const [expandedFeatureIndex, setExpandedFeatureIndex] = useState<number | null>(null);

  const filteredFeatures = useMemo(() => {
    const items = m.featureItems || [];
    if (featureGroupFilter === 'ALL') return items;
    return items.filter((f) => f.group === featureGroupFilter);
  }, [m.featureItems, featureGroupFilter]);

  if (isOp) {
    return (
      <Page
        vesselName="Tàu MV SVMG-01"
        title="Giám sát mô hình"
        subtitle="Theo dõi Random Forest và đối chiếu Baseline B"
        onBack={actions.back}
      >
        <View
          style={[
            styles.calloutBanner,
            { borderColor: colors.amber, backgroundColor: colors.warningContainerBg },
          ]}
        >
          <Text style={[styles.calloutTitle, { color: colors.amber }]}>
            Quyền truy cập bị giới hạn (Bảng 3.1)
          </Text>
          <Text style={[styles.calloutText, { color: colors.title }]}>
            Vai trò Sĩ quan trực ca (Operator) không có quyền truy cập màn hình Giám sát mô hình. Tính năng chỉ mở cho Giám sát viên và Quản trị viên.
          </Text>
          <View style={{ marginTop: 8 }}>
            <Action
              tone="primary"
              label="Quay lại Tổng quan"
              onPress={() => actions.go('Overview')}
            />
          </View>
        </View>
      </Page>
    );
  }

  const agree = t.sensor_ok ? t.class_rf === t.class_baseline_b : null;
  const isRf = m.activeModelId === 'RF';
  const currentPredPrimary = t.sensor_ok ? (isRf ? t.class_rf : t.class_baseline_b) : 'UNKNOWN';
  const effectiveValidCount =
    m.featureSummary?.validCount ?? (t.sensor_ok && data.scenario !== 'OFFLINE' ? TOTAL_FEATURES : 0);

  const renderFeatureItem = ({ item }: { item: FeatureItem }) => {
    const expanded = expandedFeatureIndex === item.index;
    const groupColor =
      item.group === 'roll_60s'
        ? colors.tech
        : item.group === 'roll_180s'
        ? colors.green
        : colors.amber;
    const statusColor =
      item.status === 'VALID'
        ? colors.green
        : item.status === 'WARNING'
        ? colors.amber
        : item.status === 'NOT_APPLICABLE'
        ? colors.muted
        : colors.red;
    const statusLabel =
      item.status === 'VALID'
        ? 'Hợp lệ'
        : item.status === 'WARNING'
        ? 'Cảnh giác'
        : item.status === 'NOT_APPLICABLE'
        ? 'Không khả dụng'
        : 'Lỗi';

    return (
      <Pressable
        onPress={() => setExpandedFeatureIndex(expanded ? null : item.index)}
        style={[
          styles.featureRowCard,
          { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
        ]}
        accessibilityRole="button"
      >
        <View style={styles.featureTopRow}>
          <View style={{ flex: 1, gap: 2 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
              <Text style={[styles.featureIdx, { color: groupColor }]}>#{item.index + 1}</Text>
              <Text style={[styles.featureTitle, { color: colors.title }]}>
                {item.displayName || item.name}
              </Text>
            </View>
            <Text style={[styles.featureCode, { color: colors.textSecondary }]}>
              {item.name} · {item.unit}
            </Text>
          </View>

          <View style={{ alignItems: 'flex-end', gap: 4 }}>
            <Text style={[styles.featureValue, { color: item.value !== null ? colors.title : colors.muted }]}>
              {item.value !== null ? item.value.toFixed(4) : '—'}
            </Text>
            <View style={[styles.featureStatusBadge, { borderColor: statusColor }]}>
              <Text style={[styles.featureStatusText, { color: statusColor }]}>{statusLabel}</Text>
            </View>
          </View>
        </View>

        {expanded && (
          <View style={[styles.featureDetailBox, { borderTopColor: colors.borderSubtle }]}>
            <Text style={[styles.featureDesc, { color: colors.textSecondary }]}>
              {item.description}
            </Text>
            {!!item.reason && (
              <Text style={[styles.featureReason, { color: colors.amber }]}>{item.reason}</Text>
            )}
          </View>
        )}
      </Pressable>
    );
  };

  return (
    <Page
      vesselName="Tàu MV SVMG-01"
      utcTime={t.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="Giám sát mô hình"
      subtitle="Random Forest, Baseline B, độ đồng thuận và 23 đặc trưng động học"
      onBack={actions.back}
    >
      {/* 1. 2x2 Summary KPIs */}
      <TwoCol>
        <MetricCard
          label="Mô hình chính"
          value={isRf ? 'Random Forest' : 'Baseline B'}
          subtext={m.version}
          color={colors.tech}
        />
        <MetricCard
          label="Dự đoán hiện tại"
          value={t.sensor_ok ? getRFClassNameVi(currentPredPrimary) : 'Không khả dụng'}
          subtext={t.sensor_ok ? 'Từ luồng mẫu hiện hành' : 'Cảm biến lỗi / Offline'}
          color={
            !t.sensor_ok
              ? colors.muted
              : currentPredPrimary === 'NORMAL'
              ? colors.green
              : currentPredPrimary === 'HIGH_ROLL' || currentPredPrimary === 'AMPLITUDE_GROWTH'
              ? colors.red
              : colors.amber
          }
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="Độ đồng thuận chung"
          value={`${m.agreementPercent}%`}
          subtext="Kiểm toán V-2026-001"
          color={m.agreementPercent >= 80 ? colors.green : colors.amber}
        />
        <MetricCard
          label="Chỉ số PSI"
          value={m.psi !== null ? String(m.psi) : '—'}
          subtext={m.psi !== null && m.psi < 0.1 ? 'Phân phối ổn định' : m.psiStatus}
          color={
            m.psi === null
              ? colors.muted
              : m.psi < 0.1
              ? colors.green
              : m.psi < 0.2
              ? colors.amber
              : colors.red
          }
        />
      </TwoCol>

      {/* 2. Concordance Timeline Chart */}
      <MobileModelConcordanceChart scenario={data.scenario} height={145} />

      {/* 3. Current Sample Comparison */}
      <Panel title="So sánh dự đoán mẫu hiện hành">
        <View style={{ gap: 4 }}>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>
              Random Forest (Chính)
            </Text>
            <Text style={[styles.metaVal, { color: colors.tech }]}>
              {t.sensor_ok ? getRFClassNameVi(t.class_rf) : 'Không khả dụng'}
            </Text>
          </View>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>
              Baseline B (Đối chiếu)
            </Text>
            <Text style={[styles.metaVal, { color: colors.amber }]}>
              {t.sensor_ok ? getRFClassNameVi(t.class_baseline_b) : 'Không khả dụng'}
            </Text>
          </View>
          <View style={[styles.metaRow, { borderBottomWidth: 0 }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Trạng thái so sánh</Text>
            <Text
              style={[
                styles.metaVal,
                { color: agree === null ? colors.muted : agree ? colors.green : colors.amber },
              ]}
            >
              {agree === null ? 'Không khả dụng' : agree ? '✓ Đồng thuận' : '⚠ Bất đồng'}
            </Text>
          </View>
        </View>
      </Panel>

      {/* 4. Model Specs & Concordance Breakdown */}
      <Panel title="Thông số TinyML & Độ ổn định" tag={m.version}>
        <View style={{ gap: 4 }}>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Kiến trúc</Text>
            <Text style={[styles.metaVal, { color: colors.title }]}>{m.algorithm}</Text>
          </View>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Tài nguyên biên</Text>
            <Text style={[styles.metaVal, { color: colors.tech }]}>
              Flash {m.flashKb} KB · RAM {m.ramKb} KB
            </Text>
          </View>
          <View style={[styles.metaRow, { borderBottomColor: colors.borderSubtle }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Thời gian suy luận</Text>
            <Text style={[styles.metaVal, { color: colors.green }]}>{m.inferenceMs} ms / mẫu</Text>
          </View>
          <View style={[styles.metaRow, { borderBottomWidth: 0 }]}>
            <Text style={[styles.metaLabel, { color: colors.textSecondary }]}>Isolation Forest</Text>
            <Text style={[styles.metaVal, { color: colors.amber }]}>Chờ kết nối máy chủ</Text>
          </View>
        </View>
      </Panel>

      {/* 5. Official 23 Kinematic Features Registry (FlatList + Filter + Expandable Details) */}
      <Panel
        title="Danh mục 23 đặc trưng động học"
        tag={`${effectiveValidCount}/${TOTAL_FEATURES} hợp lệ`}
      >
        <View
          style={[
            styles.contractSummaryBar,
            { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
          ]}
        >
          <Text style={[styles.contractText, { color: colors.textSecondary }]}>
            Hợp đồng: <Text style={{ color: colors.title, fontFamily: FONT.semibold }}>{CONTRACT_ID}</Text> (v{CONTRACT_VERSION})
          </Text>
          <Text style={[styles.contractText, { color: colors.textSecondary }]}>
            Nguồn mẫu: {CONTRACT_SOURCE_EXPORT}
          </Text>
        </View>

        {/* Group Filter Chips */}
        <View style={styles.filterRow}>
          {(
            [
              { id: 'ALL', label: 'Tất cả (23)' },
              { id: 'roll_60s', label: 'Roll 60s (8)' },
              { id: 'roll_180s', label: 'Roll 180s (12)' },
              { id: 'pitch_60s', label: 'Pitch 60s (3)' },
            ] as const
          ).map((grp) => {
            const active = featureGroupFilter === grp.id;
            return (
              <Pressable
                key={grp.id}
                onPress={() => {
                  setFeatureGroupFilter(grp.id);
                  setExpandedFeatureIndex(null);
                }}
                style={[
                  styles.filterChip,
                  {
                    backgroundColor: active ? colors.primaryContainer : colors.panel2,
                    borderColor: active ? colors.primaryContainer : colors.borderSubtle,
                  },
                ]}
                accessibilityRole="button"
              >
                <Text
                  style={[
                    styles.filterChipText,
                    { color: active ? '#FFFFFF' : colors.title },
                  ]}
                >
                  {grp.label}
                </Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={[styles.tapHint, { color: colors.textSecondary }]}>
          Chạm vào từng đặc trưng để xem mô tả chi tiết:
        </Text>

        <FlatList
          data={filteredFeatures}
          keyExtractor={(item) => item.name}
          renderItem={renderFeatureItem}
          scrollEnabled={false}
          ItemSeparatorComponent={() => <View style={{ height: 8 }} />}
        />
      </Panel>
    </Page>
  );
}

const styles = StyleSheet.create({
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    gap: 10,
    flexWrap: 'wrap',
  },
  metaLabel: {
    fontSize: 13,
    fontFamily: FONT.regular,
  },
  metaVal: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
    flexShrink: 1,
    textAlign: 'right',
  },
  themeOptCard: {
    padding: 12,
    borderRadius: 10,
    borderWidth: 1.5,
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 10,
    minHeight: 56,
  },
  themeOptTitle: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  themeOptSub: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  themeActiveText: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  calloutBanner: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    gap: 4,
  },
  calloutTitle: {
    fontSize: 16,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  calloutText: {
    fontSize: 14,
    fontFamily: FONT.regular,
    lineHeight: 20,
  },
  collapseBtn: {
    minHeight: 40,
    justifyContent: 'center',
  },
  collapseBtnText: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  contractSummaryBar: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 10,
    gap: 2,
  },
  contractText: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  filterRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  filterChip: {
    minHeight: 38,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  filterChipText: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  tapHint: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  featureRowCard: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    gap: 8,
  },
  featureTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 10,
  },
  featureIdx: {
    fontSize: 12,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  featureTitle: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    flexShrink: 1,
  },
  featureCode: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  featureValue: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  featureStatusBadge: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 7,
    paddingVertical: 1,
  },
  featureStatusText: {
    fontSize: 11,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  featureDetailBox: {
    borderTopWidth: 1,
    paddingTop: 8,
    gap: 4,
  },
  featureDesc: {
    fontSize: 13,
    fontFamily: FONT.regular,
    lineHeight: 18,
  },
  featureReason: {
    fontSize: 12,
    fontFamily: FONT.medium,
  },
});
