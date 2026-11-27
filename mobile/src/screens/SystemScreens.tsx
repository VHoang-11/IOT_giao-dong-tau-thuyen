import React, { useState } from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import {
  Action,
  LinkRow,
  MetricCard,
  Page,
  Panel,
  TwoCol,
} from '../components/UI';
import { MobileModelConcordanceChart } from '../components/MobileModelConcordanceChart';
import { C } from '../theme';
import { f, n } from '../data/format';
import { formatDateTimeUtc } from '../data/liveMapper';
import { Route, ScreenProps } from '../types/domain';

export function MoreScreen({ data, actions }: ScreenProps) {
  const [selectedTheme, setSelectedTheme] = useState<'light' | 'dark'>('light');
  const isOp = data.session?.role === 'Operator';
  const items: { title: string; subtitle: string; route: Route; badge?: string }[] = [
    { title: 'Control Center', subtitle: 'Quản trị cấu hình & lệnh thiết bị (Bảng 3.1)', route: 'ControlCenter' },
    { title: 'Replay & Review', subtitle: 'Phát lại chuỗi thời gian & thẩm định cảnh báo', route: 'ReplayReview' },
    { title: 'Device Health', subtitle: 'Chẩn đoán ESP32, MPU6050, I2C & bộ đệm', route: 'DeviceHealth' },
    {
      title: 'Model Monitor',
      subtitle: isOp ? 'Chỉ dành cho Supervisor / Admin (Bảng 3.1)' : 'Theo dõi Random Forest & Baseline B shadow',
      route: 'ModelMonitor',
      badge: isOp ? 'CHỈ SUPERVISOR' : undefined,
    },
  ];

  return (
    <Page
      vesselName={data.vesselName}
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="MORE"
      subtitle="DANH MỤC HỆ THỐNG & TÀI KHOẢN TRỰC"
    >
      <Panel title="THÔNG TIN TÀI KHOẢN" tag={data.session?.role?.toUpperCase() || 'ANONYMOUS'}>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>TÊN ĐĂNG NHẬP:</Text>
          <Text style={styles.metaVal}>{data.session?.username || '—'}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>VAI TRÒ (BẢNG 3.1):</Text>
          <Text style={[styles.metaVal, { color: C.cyan, fontWeight: 'bold' }]}>
            {data.session?.role}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>CHẾ ĐỘ HỆ THỐNG:</Text>
          <Text style={[styles.metaVal, { color: C.green }]}>DEMO / SIMULATION</Text>
        </View>
      </Panel>

      {/* Theme Appearance Selector */}
      <Panel title="GIAO DIỆN HIỂN THỊ (THEME SELECTION)" tag="APPEARANCE">
        <View style={{ gap: 8 }}>
          <Pressable
            onPress={() => setSelectedTheme('light')}
            style={{
              padding: 10,
              borderRadius: 5,
              borderWidth: 1.5,
              borderColor: selectedTheme === 'light' ? C.borderFocus : C.borderSubtle,
              backgroundColor: selectedTheme === 'light' ? '#EAF2FA' : C.bg,
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
            accessibilityRole="button"
          >
            <View style={{ flex: 1 }}>
              <Text style={{ color: C.text, fontSize: 12, fontWeight: '800' }}>
                ☀ Light Maritime (Nền trắng viền Navy - Mặc định)
              </Text>
              <Text style={{ color: C.muted, fontSize: 10, marginTop: 2 }}>
                Nền #F5F8FC, thẻ #FFFFFF, viền #183E65, chữ #102B49
              </Text>
            </View>
            {selectedTheme === 'light' && (
              <Text style={{ color: C.cyan, fontSize: 10, fontWeight: '900' }}>● ĐANG DÙNG</Text>
            )}
          </Pressable>

          <Pressable
            onPress={() => setSelectedTheme('dark')}
            style={{
              padding: 10,
              borderRadius: 5,
              borderWidth: 1.5,
              borderColor: selectedTheme === 'dark' ? C.borderFocus : C.borderSubtle,
              backgroundColor: selectedTheme === 'dark' ? '#EAF2FA' : C.bg,
              flexDirection: 'row',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
            accessibilityRole="button"
          >
            <View style={{ flex: 1 }}>
              <Text style={{ color: C.text, fontSize: 12, fontWeight: '800' }}>
                ☾ Dark Maritime (Cầu tàu đêm)
              </Text>
              <Text style={{ color: C.muted, fontSize: 10, marginTop: 2 }}>
                Chế độ tối giảm chói buồng lái ban đêm
              </Text>
            </View>
            {selectedTheme === 'dark' && (
              <Text style={{ color: C.cyan, fontSize: 10, fontWeight: '900' }}>● ĐANG DÙNG</Text>
            )}
          </Pressable>
        </View>
      </Panel>

      <Panel title="CÔNG CỤ GIÁM SÁT & ĐIỀU HÀNH" tag="OPERATIONS">
        {items.map((x) => (
          <LinkRow
            key={x.route}
            title={x.title}
            subtitle={x.subtitle}
            onPress={() => actions.go(x.route)}
          />
        ))}
      </Panel>

      <View style={{ marginTop: 12 }}>
        <Action tone="danger" label="ĐĂNG XUẤT PHIÊN LÀM VIỆC" onPress={actions.logout} />
      </View>
    </Page>
  );
}

export function DeviceHealthScreen({ data, actions }: ScreenProps) {
  const h = data.health;
  const isOffline = data.scenario === 'OFFLINE';
  const isSensorFault = data.scenario === 'SENSOR_FAULT';
  const cal = data.config.zero_calibration;

  return (
    <Page
      vesselName={data.vesselName}
      utcTime={data.telemetry.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="DEVICE HEALTH"
      subtitle="SỨC KHỎE ESP32, MPU6050 & CHẨN ĐOÁN IOT"
      onBack={actions.back}
    >
      {/* 1. Status Callout Banner */}
      {data.mode === 'live' ? (
        <View
          style={[
            styles.calloutBanner,
            data.link?.state === 'ONLINE'
              ? { borderColor: C.green, backgroundColor: C.greenContainerBg }
              : data.link?.state === 'SENSOR_FAULT'
              ? { borderColor: C.amber, backgroundColor: C.warningContainerBg }
              : { borderColor: C.red, backgroundColor: C.errorContainerBg },
          ]}
        >
          <View style={styles.calloutHeader}>
            <View
              style={[
                styles.statusDot,
                {
                  backgroundColor:
                    data.link?.state === 'ONLINE' ? C.green : data.link?.state === 'SENSOR_FAULT' ? C.amber : C.red,
                },
              ]}
            />
            <Text
              style={[
                styles.calloutTitle,
                {
                  color:
                    data.link?.state === 'ONLINE' ? C.green : data.link?.state === 'SENSOR_FAULT' ? C.amber : C.red,
                },
              ]}
            >
              {data.link?.label ?? '—'}
            </Text>
          </View>
          <Text style={styles.calloutText}>
            {data.link?.state === 'ONLINE'
              ? `Backend đang nhận telemetry từ thiết bị (mẫu cuối ${data.link.ageS ?? '?'}s trước).`
              : data.link?.state === 'SENSOR_FAULT'
              ? 'Backend báo sensor_ok=false: tín hiệu góc nghiêng không hợp lệ, không hiển thị trạng thái NORMAL.'
              : data.link?.state === 'API_ERROR'
              ? data.link.error ?? 'Không kết nối được Backend.'
              : data.link?.state === 'NO_DATA'
              ? 'Backend chưa nhận bản tin telemetry nào từ thiết bị này.'
              : 'Thiết bị im lặng quá ngưỡng cho phép. Dữ liệu cảm biến không khả dụng và không được hiển thị như thời gian thực.'}
          </Text>
        </View>
      ) : isOffline ? (
        <View style={[styles.calloutBanner, { borderColor: C.red, backgroundColor: C.errorContainerBg }]}>
          <View style={styles.calloutHeader}>
            <View style={[styles.statusDot, { backgroundColor: C.red }]} />
            <Text style={[styles.calloutTitle, { color: C.red }]}>MẤT KẾT NỐI (OFFLINE)</Text>
          </View>
          <Text style={styles.calloutText}>
            Thiết bị giám sát mất kết nối MQTT (&gt;30s). Dữ liệu cảm biến không khả dụng.
            Hệ thống tuân thủ nguyên tắc không tự tạo dữ liệu mới để hiển thị như dữ liệu thật.
            Dữ liệu đang được lưu vào bộ đệm Flash ngoại tuyến trên ESP32.
          </Text>
        </View>
      ) : isSensorFault ? (
        <View style={[styles.calloutBanner, { borderColor: C.amber, backgroundColor: C.warningContainerBg }]}>
          <View style={styles.calloutHeader}>
            <View style={[styles.statusDot, { backgroundColor: C.amber }]} />
            <Text style={[styles.calloutTitle, { color: C.amber }]}>LỖI CẢM BIẾN (SENSOR FAULT)</Text>
          </View>
          <Text style={styles.calloutText}>
            Phát hiện 3 lỗi giao tiếp trên bus I2C với cảm biến MPU6050 (NACK timeout).
            Tín hiệu góc nghiêng không hợp lệ; hệ thống không hiển thị trạng thái NORMAL.
          </Text>
        </View>
      ) : (
        <View style={[styles.calloutBanner, { borderColor: C.green, backgroundColor: C.greenContainerBg }]}>
          <View style={styles.calloutHeader}>
            <View style={[styles.statusDot, { backgroundColor: C.green }]} />
            <Text style={[styles.calloutTitle, { color: C.green }]}>THIẾT BỊ HOẠT ĐỘNG TỐT (100% HEALTH)</Text>
          </View>
          <Text style={styles.calloutText}>
            ESP32 kết nối ổn định qua MQTT QoS 0/1. Cảm biến MPU6050 truyền nhận dữ liệu chu kỳ 5.0s đạt chuẩn.
          </Text>
        </View>
      )}

      {/* 2. Key Diagnostic Metrics Bento Grid */}
      <TwoCol>
        <MetricCard
          label="ĐIỂM SỨC KHỎE (FR17)"
          value={h.healthScore === null ? h.healthStatus : `${h.healthScore}/100`}
          color={
            h.healthScore === null
              ? h.healthStatus === 'HEALTHY' ? C.green : h.healthStatus === 'DEGRADED' ? C.amber : C.red
              : h.healthScore >= 80 ? C.green : h.healthScore >= 40 ? C.amber : C.red
          }
        />
        <MetricCard
          label="TRẠNG THÁI CẢM BIẾN"
          value={h.sensor}
          color={h.sensor === 'OK' ? C.green : h.sensor === 'FAULT' ? C.amber : C.red}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="LỖI BUS I2C"
          value={n(h.i2cErrors)}
          color={h.i2cErrors === null ? C.muted : h.i2cErrors > 0 ? C.red : C.green}
        />
        <MetricCard
          label="FREE HEAP"
          value={f(h.freeHeapKb, 1, ' KB')}
          color={h.freeHeapKb !== null && h.freeHeapKb < 80 ? C.amber : C.cyan}
        />
      </TwoCol>

      <TwoCol>
        <MetricCard
          label="WIFI RSSI"
          value={h.rssiDbm !== null ? `${h.rssiDbm} dBm` : '—'}
          color={h.rssiDbm !== null ? C.cyan : C.muted}
        />
        <MetricCard
          label="UPTIME THIẾT BỊ"
          value={n(h.uptimeMinutes, ' min')}
          color={C.cyan}
        />
      </TwoCol>

      {/* 3. Hardware & Bus Diagnostics Details */}
      <Panel title="CHẨN ĐOÁN PHẦN CỨNG & BUS TRUYỀN THÔNG" tag="ESP32 • MPU6050">
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>MÃ THIẾT BỊ (DEVICE ID):</Text>
          <Text style={styles.metaVal}>{data.deviceId ?? '—'}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>BOOT ID / FIRMWARE:</Text>
          <Text style={styles.metaVal}>{data.bootId ?? '—'}{data.firmware ? ` (${data.firmware})` : ''}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>TẦN SỐ BUS I2C:</Text>
          <Text style={styles.metaVal}>{data.mode === 'live' ? '—' : '400 kHz (Fast Mode)'}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>TÌNH TRẠNG BUS I2C:</Text>
          <Text style={[styles.metaVal, { color: (h.i2cErrors ?? 0) > 0 ? C.red : h.i2cErrors === null ? C.muted : C.green }]}>
            {h.lastI2cError || (h.i2cErrors === null ? '—' : h.i2cErrors > 0 ? `${h.i2cErrors} lỗi I2C` : 'Hoạt động bình thường (0 NACK)')}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>BỘ NHỚ HEAP TỐI THIỂU:</Text>
          <Text style={styles.metaVal}>{f(h.minFreeHeapKb, 1, ' KB')}{h.heapFragmentationPct !== null ? ` (Phân mảnh ${h.heapFragmentationPct}%)` : ''}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>THỜI GIAN SUY LUẬN AI:</Text>
          <Text style={[styles.metaVal, { color: C.cyan }]}>{n(h.inferenceMs, ' ms / mẫu')}</Text>
        </View>
      </Panel>

      {/* 4. Buffer & Queue Condition (FR19) */}
      <Panel title="BỘ ĐỆM NGOẠI TUYẾN & HÀNG ĐỢI (FR19)" tag="FLASH RING BUFFER">
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>DUNG LƯỢNG BỘ ĐỆM TỐI ĐA:</Text>
          <Text style={styles.metaVal}>{n(h.bufferCapacity, ' mẫu')}{data.mode === 'mock' ? ' (~83 phút khi mất mạng)' : ''}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>SỐ MẪU ĐANG LƯU ĐỆM:</Text>
          <Text style={[styles.metaVal, { color: (h.bufferUsed ?? 0) > 0 ? C.amber : C.green }]}>
            {h.bufferUsed === null || !h.bufferCapacity ? '—' : `${h.bufferUsed} / ${h.bufferCapacity} mẫu (${((h.bufferUsed / h.bufferCapacity) * 100).toFixed(1)}%)`}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>TRẠNG THÁI HÀNG ĐỢI:</Text>
          <Text style={[styles.metaVal, { color: h.bufferStatus === 'BUFFERING' ? C.amber : C.green }]}>
            {h.bufferStatus === 'BUFFERING' ? 'ĐANG LƯU BÙ (BUFFERING)' : h.bufferStatus === 'EMPTY' ? 'ĐỒNG BỘ TRỰC TIẾP (EMPTY)' : h.bufferStatus === 'OVERFLOW' ? 'TRÀN BỘ ĐỆM (OVERFLOW)' : '—'}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>ĐỘ TRỄ HÀNG ĐỢI (QUEUE RTT):</Text>
          <Text style={styles.metaVal}>{n(h.queueLatencyMs, ' ms')}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>BẢN TIN TELEMETRY GẦN NHẤT:</Text>
          <Text style={[styles.metaVal, { color: isOffline ? C.red : C.green }]}>
            {h.lastPacketUtc}{h.packetGapS !== null ? ` (${h.packetGapS}s gap)` : ''}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>SỐ LẦN RECONNECT MQTT:</Text>
          <Text style={styles.metaVal}>{n(h.mqttReconnects, ' lần')}</Text>
        </View>
      </Panel>

      {/* 5. Zero Calibration Status (FR18) */}
      <Panel title="HIỆU CHUẨN ĐIỂM 0 (HEEL ZERO CALIBRATION)" tag="FR18 STATUS">
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>TRẠNG THÁI HIỆU CHUẨN:</Text>
          <Text style={[styles.metaVal, { color: cal || (data.mode === 'live' && h.lastCalibratedAt) ? C.green : C.muted }]}>
            {data.mode === 'live'
              ? h.lastCalibratedAt
                ? `LẦN CUỐI ${formatDateTimeUtc(h.lastCalibratedAt)} (${h.lastCalibrationState ?? '—'})`
                : 'CHƯA GHI NHẬN HIỆU CHUẨN'
              : cal ? 'ĐÃ HIỆU CHUẨN (30S TĨNH)' : 'MẶC ĐỊNH NHÀ MÁY (0.0°)'}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>ĐỘ LỆCH ROLL HIỆN TẠI (OFFSET):</Text>
          <Text style={[styles.metaVal, { color: C.cyan, fontWeight: 'bold' }]}>
            {cal ? `${cal.roll_offset_deg > 0 ? '+' : ''}${cal.roll_offset_deg.toFixed(2)}°` : data.mode === 'live' ? '—' : '0.00°'}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>ĐỘ LỆCH PITCH HIỆN TẠI (OFFSET):</Text>
          <Text style={[styles.metaVal, { color: C.amber }]}>
            {cal ? `${cal.pitch_offset_deg > 0 ? '+' : ''}${cal.pitch_offset_deg.toFixed(2)}°` : data.mode === 'live' ? '—' : '0.00°'}
          </Text>
        </View>
        {cal && (
          <View style={styles.metaRow}>
            <Text style={styles.metaLabel}>ĐỘ LỆCH CHUẨN KHI ĐO (30S):</Text>
            <Text style={[styles.metaVal, { color: C.green }]}>
              σ = {cal.std_dev_roll.toFixed(2)}° (Đạt chuẩn tĩnh ≤ 1.0°)
            </Text>
          </View>
        )}
        <View style={{ marginTop: 12 }}>
          <Action
            tone="neutral"
            label="ĐẾN CONTROL CENTER ĐỂ HIỆU CHUẨN →"
            onPress={() => actions.go('ControlCenter')}
          />
        </View>
      </Panel>
    </Page>
  );
}

export function ModelMonitorScreen({ data, actions }: ScreenProps) {
  const isOp = data.session?.role === 'Operator';
  const m = data.model;
  const t = data.telemetry;
  const classified = (c: string) => c !== 'UNKNOWN' && c !== 'FAULT';
  // UNKNOWN/FAULT không được tính là đồng thuận (cùng quy tắc với Backend).
  const agree =
    t.sensor_ok && classified(t.class_rf) && classified(t.class_baseline_b)
      ? t.class_rf === t.class_baseline_b
      : null;

  // RBAC Guard - Table 3.1
  if (isOp) {
    return (
      <Page
        vesselName={data.vesselName}
        title="MODEL MONITOR"
        subtitle="HỆ THỐNG GIÁM SÁT MÔ HÌNH HỌC MÁY"
        onBack={actions.back}
      >
        <View style={[styles.calloutBanner, { borderColor: C.amber, backgroundColor: '#2f2412' }]}>
          <View style={styles.calloutHeader}>
            <View style={[styles.statusDot, { backgroundColor: C.amber }]} />
            <Text style={[styles.calloutTitle, { color: C.amber }]}>
              TRUY CẬP BỊ TỪ CHỐI (BẢNG 3.1)
            </Text>
          </View>
          <Text style={styles.calloutText}>
            Theo Bảng 3.1 đề cương dự án Smart Vessel Motion Guard v2.0, vai trò Operator không có
            quyền truy cập màn hình Model Monitor. Tính năng này chỉ mở cho Supervisor và Admin.
          </Text>
          <View style={{ marginTop: 12 }}>
            <Action tone="neutral" label="QUAY LẠI TỔNG QUAN" onPress={() => actions.go('Overview')} />
          </View>
        </View>
      </Page>
    );
  }

  return (
    <Page
      vesselName={data.vesselName}
      utcTime={t.utc_time}
      isHornMuted={data.buzzerMuted}
      onToggleHorn={actions.toggleBuzzer}
      title="MODEL MONITOR"
      subtitle="GIÁM SÁT RANDOM FOREST & BASELINE B (SHADOW)"
      onBack={actions.back}
    >
      {/* 1. Active vs Shadow Model Overview */}
      <Panel title="CẤU HÌNH BỘ SUY LUẬN (INFERENCE ENGINE)" tag={`CHÍNH: ${m.activeModelId ?? '—'}`}>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>MÔ HÌNH QUYẾT ĐỊNH CHÍNH:</Text>
          <Text style={[styles.metaVal, { color: C.cyan, fontWeight: 'bold' }]}>
            {m.active}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>MÔ HÌNH BÓNG (SHADOW MODE):</Text>
          <Text style={[styles.metaVal, { color: C.amber }]}>{m.baseline}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>PHIÊN BẢN REGISTRY:</Text>
          <Text style={styles.metaVal}>{m.version}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>THỜI GIAN SUY LUẬN TRÊN ESP32:</Text>
          <Text style={[styles.metaVal, { color: C.green }]}>{n(m.inferenceMs, ' ms / mẫu')}</Text>
        </View>
      </Panel>

      {/* 2. Current Telemetry Predictions Comparison */}
      <Panel title="SO SÁNH KẾT QUẢ MẪU HIỆN HÀNH" tag="CURRENT DEMO SAMPLE">
        <TwoCol>
          <MetricCard
            label="DỰ ĐOÁN RANDOM FOREST"
            value={t.sensor_ok ? t.class_rf : 'N/A'}
            color={t.sensor_ok ? C.cyan : C.muted}
          />
          <MetricCard
            label="DỰ ĐOÁN BASELINE B"
            value={t.sensor_ok ? t.class_baseline_b : 'N/A'}
            color={t.sensor_ok ? C.amber : C.muted}
          />
        </TwoCol>

        <View style={{ marginTop: 10 }}>
          <View style={styles.metaRow}>
            <Text style={styles.metaLabel}>TRẠNG THÁI ĐỒNG THUẬN:</Text>
            <Text
              style={[
                styles.metaVal,
                {
                  color: agree === null ? C.muted : agree ? C.green : C.amber,
                  fontWeight: 'bold',
                },
              ]}
            >
              {agree === null
                ? 'N/A (CẢM BIẾN LỖI/OFFLINE)'
                : agree
                ? '✓ ĐỒNG THUẬN (AGREE)'
                : '⚠ BẤT ĐỒNG (DISAGREE)'}
            </Text>
          </View>
          {data.scenario === 'S0b' && !agree && (
            <View style={[styles.calloutBanner, { marginTop: 8, borderColor: C.amber, backgroundColor: '#2f2412' }]}>
              <Text style={styles.calloutText}>
                Giải thích bất đồng kịch bản S0b: Baseline B dựa trên ngưỡng biên độ tức thời
                nên phát nhãn High Roll khi có gió giật; trong khi Random Forest học đặc trưng chuỗi thời gian
                nhận diện tàu đang tự hồi phục và giữ nhãn Normal.
              </Text>
            </View>
          )}
        </View>
      </Panel>

      {/* Interactive Dual-Stream Concordance Timeline */}
      {data.mode === 'mock' && <MobileModelConcordanceChart scenario={data.scenario} height={145} />}

      {/* 3. Model Registry & Edge Specs */}
      <Panel title="THÔNG TIN ĐẶC TẢ MÔ HÌNH (MODEL REGISTRY)" tag="TINYML SPEC">
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>THUẬT TOÁN HỌC MÁY:</Text>
          <Text style={styles.metaVal}>{m.algorithm ?? '—'}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>CHIẾM DỤNG BỘ NHỚ FLASH:</Text>
          <Text style={styles.metaVal}>{n(m.flashKb, ' KB')}{data.mode === 'mock' ? ' (trong phân vùng 4MB)' : ''}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>CHIẾM DỤNG BỘ NHỚ RAM:</Text>
          <Text style={styles.metaVal}>{n(m.ramKb, ' KB')}{data.mode === 'mock' ? ' (trong 320KB SRAM)' : ''}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>VECTƠ ĐẶC TRƯNG ({m.featuresCount ?? '—'} FEATURES):</Text>
          <Text style={[styles.metaVal, { fontSize: 9 }]}>{m.features.length ? m.features.join(', ') : '—'}</Text>
        </View>
      </Panel>

      {/* 4. Concordance Breakdown */}
      <Panel title="THỐNG KÊ ĐỒNG THUẬN GIỮA RF VÀ BASELINE B" tag={m.agreementPercent === null ? 'CHƯA ĐỦ DỮ LIỆU' : `${m.agreementPercent}% ĐỒNG THUẬN`}>
        {m.note ? <Text style={[styles.calloutText, { marginBottom: 8, color: C.muted }]}>{m.note}</Text> : null}
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>TỔNG TỶ LỆ ĐỒNG THUẬN {data.mode === 'live' ? '(THIẾT BỊ)' : '(V-2026-001)'}:</Text>
          <Text style={[styles.metaVal, { color: C.green, fontWeight: 'bold' }]}>
            {n(m.agreementPercent, '%')}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>Lớp NORMAL:</Text>
          <Text style={styles.metaVal}>{n(m.concordanceBreakdown.normal, '%')}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>Lớp HIGH_ROLL:</Text>
          <Text style={styles.metaVal}>{n(m.concordanceBreakdown.highRoll, '%')}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>Lớp PERSISTENT_OFFSET:</Text>
          <Text style={styles.metaVal}>{n(m.concordanceBreakdown.persistentOffset, '%')}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>Lớp AMPLITUDE_GROWTH:</Text>
          <Text style={styles.metaVal}>{n(m.concordanceBreakdown.amplitudeGrowth, '%')}</Text>
        </View>
      </Panel>

      {/* 5. Data Drift & PSI (FR21) */}
      <Panel title="ĐỘ ỔN ĐỊNH PHÂN PHỐI & DRIFT (FR21)" tag="POPULATION STABILITY INDEX">
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>CHỈ SỐ PSI HIỆN TẠI:</Text>
          <Text style={[styles.metaVal, { color: C.green, fontWeight: 'bold' }]}>
            {m.psi !== null ? m.psi : '—'}
          </Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>ĐÁNH GIÁ ĐỘ LỆCH:</Text>
          <Text style={[styles.metaVal, { color: C.green }]}>{m.psiStatus}</Text>
        </View>
        <View style={styles.metaRow}>
          <Text style={styles.metaLabel}>ISOLATION FOREST (BACKEND):</Text>
          <Text style={[styles.metaVal, { color: C.amber }]}>{data.mode === 'live' ? 'Backend chưa cung cấp' : 'Chờ kết nối Backend TV3'}</Text>
        </View>
        <Text style={[styles.calloutText, { marginTop: 10, color: C.muted }]}>
          Lưu ý kỹ thuật: Backend TV3 chịu trách nhiệm định kỳ tính toán chỉ số PSI và Isolation Forest
          từ cơ sở dữ liệu lịch sử. Frontend không tự chạy suy luận hay huấn luyện mô hình.
        </Text>
      </Panel>
    </Page>
  );
}

const styles = StyleSheet.create({
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: C.borderSubtle,
  },
  metaLabel: {
    color: C.muted,
    fontSize: 10,
    fontFamily: 'monospace',
    fontWeight: 'bold',
  },
  metaVal: {
    color: C.text,
    fontSize: 11,
    fontFamily: 'monospace',
    textAlign: 'right',
  },
  calloutBanner: {
    borderWidth: 1,
    borderRadius: 6,
    padding: 12,
    marginBottom: 12,
  },
  calloutHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  calloutTitle: {
    fontSize: 12,
    fontFamily: 'monospace',
    fontWeight: 'bold',
  },
  calloutText: {
    color: C.textSecondary,
    fontSize: 11,
    lineHeight: 16,
  },
});
