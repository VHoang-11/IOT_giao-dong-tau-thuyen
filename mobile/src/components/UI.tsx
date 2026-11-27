import React from 'react';
import {
  Animated,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import {
  FONT,
  getSeverityBg,
  getSeverityColors,
  SHADOWS,
  TYPOGRAPHY,
  useTheme,
} from '../theme';
import { AlarmLevel } from '../types/domain';
import { getAlarmLevelNameVi, getAlarmStatusNameVi } from '../i18n/vi';

export function Page({
  title,
  subtitle,
  children,
  onBack,
  vesselName = 'Tàu MV SVMG-01',
  utcTime,
  isHornMuted,
  onToggleHorn,
  unackCount = 0,
}: {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  onBack?: () => void;
  vesselName?: string;
  utcTime?: string;
  isHornMuted?: boolean;
  onToggleHorn?: () => void;
  unackCount?: number;
}) {
  const { colors, mode, toggleTheme } = useTheme();

  return (
    <ScrollView
      style={[styles.page, { backgroundColor: colors.canvas }]}
      contentContainerStyle={styles.pageContent}
      keyboardShouldPersistTaps="handled"
    >
      {/* Top Bridge Header */}
      <View
        style={[
          styles.topAppBar,
          { backgroundColor: colors.panel, borderColor: colors.border },
          SHADOWS.sm,
        ]}
      >
        <View style={styles.topAppBarLeft}>
          {onBack ? (
            <Pressable
              onPress={onBack}
              style={({ pressed }) => [
                styles.backBtn,
                { borderColor: colors.borderSubtle, backgroundColor: colors.panel2 },
                pressed && { opacity: 0.7 },
              ]}
              accessibilityRole="button"
              accessibilityLabel="Quay lại"
            >
              <Text style={[styles.backChevron, { color: colors.tech }]}>‹</Text>
              <Text style={[styles.backBtnText, { color: colors.tech }]}>Quay lại</Text>
            </Pressable>
          ) : (
            <View style={styles.vesselBrand}>
              <View style={[styles.brandIconPill, { backgroundColor: colors.cyanContainerBg }]}>
                <Text style={[styles.boatIcon, { color: colors.tech }]}>≋</Text>
              </View>
              <View style={{ flexShrink: 1 }}>
                <Text style={[styles.vesselName, { color: colors.title }]} numberOfLines={1}>
                  {vesselName}
                </Text>
                <Text style={[styles.vesselSub, { color: colors.textSecondary }]} numberOfLines={1}>
                  {unackCount > 0 ? `${unackCount} cảnh báo chờ xử lý` : 'Hệ thống ổn định'}
                </Text>
              </View>
            </View>
          )}
        </View>

        <View style={styles.topAppBarRight}>
          {/* Theme toggle shortcut */}
          <Pressable
            onPress={toggleTheme}
            style={({ pressed }) => [
              styles.themeToggleBtn,
              { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
              pressed && { opacity: 0.75 },
            ]}
            accessibilityRole="button"
            accessibilityLabel={mode === 'light' ? 'Chuyển sang giao diện tối' : 'Chuyển sang giao diện sáng'}
          >
            <Text style={[styles.themeToggleText, { color: colors.title }]}>
              {mode === 'light' ? '☀ Sáng' : '🌙 Tối'}
            </Text>
          </Pressable>

          {/* Buzzer status toggle */}
          {onToggleHorn && (
            <Pressable
              onPress={onToggleHorn}
              style={({ pressed }) => [
                styles.hornPill,
                isHornMuted
                  ? { backgroundColor: colors.panel2, borderColor: colors.borderSubtle }
                  : { backgroundColor: colors.errorContainerBg, borderColor: colors.red },
                pressed && { opacity: 0.75 },
              ]}
              accessibilityRole="button"
              accessibilityLabel={isHornMuted ? 'Còi báo động đang tắt' : 'Còi báo động đang bật'}
            >
              <Text style={[styles.hornStatus, { color: isHornMuted ? colors.muted : colors.red }]}>
                {isHornMuted ? '🔇 Tắt còi' : '🔔 Còi bật'}
              </Text>
            </Pressable>
          )}
        </View>
      </View>

      {/* Simulation Source Ribbon */}
      <View
        style={[
          styles.telemetryRibbon,
          { backgroundColor: colors.panel, borderColor: colors.border },
        ]}
      >
        <View style={styles.ribbonRow}>
          <View style={[styles.simBadge, { backgroundColor: colors.warningContainerBg }]}>
            <View style={[styles.simDot, { backgroundColor: colors.amber }]} />
            <Text style={[styles.simText, { color: colors.amber }]}>Dữ liệu mô phỏng</Text>
          </View>
          <Text style={[styles.utcTime, { color: colors.textSecondary }]}>
            {utcTime ?? '—'}
          </Text>
        </View>
      </View>

      {/* Screen Title & Subtitle */}
      {title && (
        <View style={styles.titleArea}>
          <Text style={[styles.screenTitle, { color: colors.title }]}>{title}</Text>
          {subtitle && (
            <Text style={[styles.screenSubtitle, { color: colors.textSecondary }]}>
              {subtitle}
            </Text>
          )}
        </View>
      )}

      {children}
    </ScrollView>
  );
}

export function StatusBanner({
  level,
  title,
  desc,
  elapsed = 'T+0s',
}: {
  level: AlarmLevel;
  title: string;
  desc: string;
  elapsed?: string;
}) {
  const { colors } = useTheme();
  const sevColors = getSeverityColors(colors);
  const sevBg = getSeverityBg(colors);
  const color = sevColors[level] ?? colors.muted;
  const bg = sevBg[level] ?? colors.neutralContainerBg;

  return (
    <View
      style={[
        styles.banner,
        { borderColor: colors.border, borderLeftColor: color, backgroundColor: bg },
      ]}
    >
      <View style={styles.bannerHeader}>
        <View style={styles.bannerBadgeRow}>
          <View style={[styles.pulseDot, { backgroundColor: color }]} />
          <View style={[styles.bannerPill, { borderColor: color, backgroundColor: colors.panel }]}>
            <Text style={[styles.bannerPillText, { color }]}>{getAlarmLevelNameVi(level)}</Text>
          </View>
          <Text style={[styles.bannerTitle, { color: colors.title }]} numberOfLines={2}>
            {title}
          </Text>
        </View>
        <Text style={[styles.bannerElapsed, { color: colors.textSecondary, backgroundColor: colors.panel }]}>
          {elapsed}
        </Text>
      </View>
      <Text style={[styles.bannerDesc, { color: colors.title }]}>{desc}</Text>
    </View>
  );
}

export function RiskBar({ score }: { score: number }) {
  const { colors } = useTheme();
  const normScore = score > 1 ? score / 100 : score;
  const displayPct = Math.round(normScore * 100);
  const statusColor =
    normScore >= 0.7 ? colors.red : normScore >= 0.35 ? colors.amber : colors.green;

  return (
    <View style={styles.riskBarContainer}>
      <View style={styles.riskLabels}>
        <Text style={[styles.riskLabelEdge, { color: colors.textSecondary }]}>An toàn (&lt;35)</Text>
        <Text style={[styles.riskLabelMid, { color: statusColor }]}>
          Hiện tại: {displayPct} / 100
        </Text>
        <Text style={[styles.riskLabelEdge, { color: colors.red }]}>Nguy cấp (≥70)</Text>
      </View>
      <View style={[styles.barTrack, { backgroundColor: colors.panel2, borderColor: colors.borderSubtle }]}>
        <View style={[styles.barSegment, { width: '35%', backgroundColor: colors.green }]} />
        <View style={[styles.barSegment, { width: '35%', backgroundColor: colors.amber }]} />
        <View style={[styles.barSegment, { width: '30%', backgroundColor: colors.red }]} />
      </View>
      <Text style={[styles.riskFooter, { color: colors.textSecondary }]}>
        Ngưỡng đánh giá mô phỏng • Phân loại TinyML
      </Text>
    </View>
  );
}

export function Panel({
  title,
  tag,
  children,
  extra,
}: {
  title?: string;
  tag?: string;
  children: React.ReactNode;
  extra?: string;
}) {
  const { colors } = useTheme();

  return (
    <View
      style={[
        styles.panel,
        { backgroundColor: colors.panel, borderColor: colors.border },
        SHADOWS.card,
      ]}
    >
      {(title || tag || extra) && (
        <View style={[styles.panelHeader, { borderBottomColor: colors.borderSubtle }]}>
          {title && <Text style={[styles.panelTitle, { color: colors.title }]}>{title}</Text>}
          {tag && (
            <View style={[styles.panelTagWrap, { backgroundColor: colors.panel2 }]}>
              <Text style={[styles.panelTag, { color: colors.tech }]}>{tag}</Text>
            </View>
          )}
          {extra && <Text style={[styles.panelExtra, { color: colors.tech }]}>{extra}</Text>}
        </View>
      )}
      {children}
    </View>
  );
}

export function MetricCard({
  label,
  value,
  unit,
  subtext,
  color,
  flex = 1,
}: {
  label: string;
  value: string;
  unit?: string;
  subtext?: string;
  color?: string;
  flex?: number;
}) {
  const { colors } = useTheme();
  const valueColor = color ?? colors.title;

  return (
    <View
      style={[
        styles.metricCard,
        { backgroundColor: colors.panel, borderColor: colors.border, flex },
        SHADOWS.sm,
      ]}
    >
      <Text style={[styles.metricLabel, { color: colors.title }]}>{label}</Text>
      <View style={styles.metricValRow}>
        <Text style={[styles.metricVal, { color: valueColor }]}>{value}</Text>
        {unit ? <Text style={[styles.metricUnit, { color: colors.textSecondary }]}>{unit}</Text> : null}
      </View>
      {subtext ? <Text style={[styles.metricSub, { color: colors.textSecondary }]}>{subtext}</Text> : null}
    </View>
  );
}

export function ActionBtn({
  label,
  onPress,
  disabled = false,
  tone = 'primary',
  icon,
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  tone?: 'primary' | 'secondary' | 'danger' | 'neutral' | 'ghost';
  icon?: string;
}) {
  const { colors, reducedMotion } = useTheme();
  const scaleAnim = React.useRef(new Animated.Value(1)).current;

  const animateTo = (toValue: number) => {
    if (reducedMotion) return;
    Animated.spring(scaleAnim, {
      toValue,
      useNativeDriver: true,
      speed: 45,
      bounciness: 0,
    }).start();
  };

  const bgStyle =
    tone === 'primary'
      ? { backgroundColor: colors.primaryContainer, borderColor: colors.primaryContainer }
      : tone === 'danger'
      ? { backgroundColor: colors.red, borderColor: colors.red }
      : tone === 'secondary'
      ? { backgroundColor: colors.panelHigh, borderColor: colors.borderSubtle }
      : tone === 'ghost'
      ? { backgroundColor: 'transparent', borderColor: colors.borderSubtle }
      : { backgroundColor: colors.panel2, borderColor: colors.borderSubtle };

  const txtColor =
    tone === 'primary' || tone === 'danger'
      ? '#FFFFFF'
      : disabled
      ? colors.muted
      : colors.title;

  return (
    <Animated.View style={{ transform: [{ scale: scaleAnim }] }}>
      <Pressable
        onPress={onPress}
        onPressIn={() => !disabled && animateTo(0.98)}
        onPressOut={() => animateTo(1)}
        disabled={disabled}
        accessibilityRole="button"
        style={({ pressed }) => [
          styles.actionBtn,
          bgStyle,
          disabled && styles.btnDisabled,
          pressed && !disabled && { opacity: 0.88 },
        ]}
      >
        {icon && <Text style={[styles.btnIcon, { color: txtColor }]}>{icon}</Text>}
        <Text style={[styles.actionBtnText, { color: txtColor }]}>{label}</Text>
      </Pressable>
    </Animated.View>
  );
}

export function Pill({
  label,
  level,
  status,
}: {
  label: string;
  level?: AlarmLevel;
  status?: string;
}) {
  const { colors } = useTheme();
  const sevColors = getSeverityColors(colors);
  const sevBg = getSeverityBg(colors);

  const color = level
    ? sevColors[level] ?? colors.muted
    : status === 'APPLIED' || status === 'ACKED' || status === 'CLEARED' || status === 'VALID'
    ? colors.green
    : status === 'REJECTED' || status === 'TIMEOUT' || status === 'INVALID'
    ? colors.red
    : status === 'SENT' || status === 'DELIVERED' || status === 'WARNING'
    ? colors.amber
    : colors.tech;

  const bg = level
    ? sevBg[level] ?? colors.neutralContainerBg
    : status === 'APPLIED' || status === 'ACKED' || status === 'CLEARED' || status === 'VALID'
    ? colors.greenContainerBg
    : status === 'REJECTED' || status === 'TIMEOUT' || status === 'INVALID'
    ? colors.errorContainerBg
    : status === 'SENT' || status === 'DELIVERED' || status === 'WARNING'
    ? colors.warningContainerBg
    : colors.cyanContainerBg;

  return (
    <View style={[styles.pill, { borderColor: color, backgroundColor: bg }]}>
      <Text style={[styles.pillText, { color }]}>{label}</Text>
    </View>
  );
}

export function TwoCol({ children }: { children: React.ReactNode }) {
  const { width } = useWindowDimensions();
  const isVeryNarrow = width < 340;
  return (
    <View style={[styles.twoCol, isVeryNarrow && { flexDirection: 'column' }]}>
      {children}
    </View>
  );
}

export function Label({ children }: { children: React.ReactNode }) {
  const { colors } = useTheme();
  return <Text style={[styles.metricLabel, { color: colors.title }]}>{children}</Text>;
}

export function Value({ children, color }: { children: React.ReactNode; color?: string }) {
  const { colors } = useTheme();
  return <Text style={[styles.metricVal, { color: color ?? colors.title }]}>{children}</Text>;
}

export function Body({ children }: { children: React.ReactNode }) {
  const { colors } = useTheme();
  return <Text style={[styles.bannerDesc, { color: colors.title }]}>{children}</Text>;
}

export function Small({ children }: { children: React.ReactNode }) {
  const { colors } = useTheme();
  return <Text style={[styles.riskFooter, { color: colors.textSecondary, textAlign: 'left' }]}>{children}</Text>;
}

export function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return <MetricCard label={label} value={value} color={color} />;
}

export function Action({
  label,
  onPress,
  disabled = false,
  tone = 'primary',
}: {
  label: string;
  onPress: () => void;
  disabled?: boolean;
  tone?: 'primary' | 'danger' | 'neutral';
}) {
  return <ActionBtn label={label} onPress={onPress} disabled={disabled} tone={tone} />;
}

export function LinkRow({
  title,
  subtitle,
  badge,
  onPress,
  disabled = false,
}: {
  title: string;
  subtitle?: string;
  badge?: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.linkRow,
        { backgroundColor: colors.panel, borderColor: colors.border },
        SHADOWS.sm,
        disabled && { opacity: 0.5 },
        pressed && !disabled && { backgroundColor: colors.panel2 },
      ]}
    >
      <View style={{ flex: 1, gap: 3 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <Text style={[styles.linkTitle, { color: colors.title }]}>{title}</Text>
          {badge && (
            <View style={[styles.linkBadge, { backgroundColor: colors.warningContainerBg }]}>
              <Text style={[styles.linkBadgeText, { color: colors.amber }]}>{badge}</Text>
            </View>
          )}
        </View>
        {subtitle && (
          <Text style={[styles.linkSubtitle, { color: colors.textSecondary }]}>{subtitle}</Text>
        )}
      </View>
      <Text style={[styles.linkChevron, { color: colors.tech }]}>›</Text>
    </Pressable>
  );
}

export function Severity({ level }: { level: AlarmLevel }) {
  return <Pill label={getAlarmLevelNameVi(level)} level={level} />;
}

export function StatusPill({ status }: { status: string }) {
  return <Pill label={getAlarmStatusNameVi(status)} status={status} />;
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
  },
  pageContent: {
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 28,
    gap: 14,
  },
  topAppBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: 1,
    gap: 8,
  },
  topAppBarLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    minWidth: 0,
  },
  topAppBarRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  vesselBrand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    flex: 1,
    minWidth: 0,
  },
  brandIconPill: {
    width: 36,
    height: 36,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  boatIcon: {
    fontSize: 20,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  vesselName: {
    fontSize: 15,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  vesselSub: {
    fontSize: 12,
    fontFamily: FONT.regular,
    marginTop: 1,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    minHeight: 44,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderRadius: 10,
    gap: 4,
  },
  backChevron: {
    fontSize: 18,
    fontFamily: FONT.bold,
    fontWeight: '700',
    marginTop: -2,
  },
  backBtnText: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  themeToggleBtn: {
    minHeight: 36,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  themeToggleText: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  hornPill: {
    minHeight: 36,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  hornStatus: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  telemetryRibbon: {
    borderRadius: 10,
    borderWidth: 1,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  ribbonRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  simBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 999,
  },
  simDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  simText: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  utcTime: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontVariant: ['tabular-nums'],
  },
  titleArea: {
    marginTop: 2,
    marginBottom: 2,
    gap: 4,
  },
  screenTitle: {
    ...TYPOGRAPHY.pageTitle,
  },
  screenSubtitle: {
    ...TYPOGRAPHY.secondary,
  },
  banner: {
    borderWidth: 1,
    borderLeftWidth: 4,
    borderRadius: 12,
    padding: 14,
    gap: 6,
  },
  bannerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: 8,
  },
  bannerBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
    flex: 1,
  },
  pulseDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  bannerPill: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  bannerPillText: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  bannerTitle: {
    fontSize: 15,
    fontFamily: FONT.bold,
    fontWeight: '700',
    flexShrink: 1,
  },
  bannerElapsed: {
    fontSize: 12,
    fontFamily: FONT.medium,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
    fontVariant: ['tabular-nums'],
  },
  bannerDesc: {
    ...TYPOGRAPHY.body,
  },
  panel: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    gap: 12,
  },
  panelHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
    borderBottomWidth: 1,
    paddingBottom: 10,
  },
  panelTitle: {
    ...TYPOGRAPHY.cardTitle,
    flexShrink: 1,
  },
  panelTagWrap: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 6,
  },
  panelTag: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  panelExtra: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  metricCard: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    minWidth: 140,
    alignItems: 'flex-start',
  },
  metricLabel: {
    ...TYPOGRAPHY.cardTitle,
    marginBottom: 8,
  },
  metricValRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 5,
    marginBottom: 6,
    flexWrap: 'wrap',
  },
  metricVal: {
    ...TYPOGRAPHY.metricValue,
    fontVariant: ['tabular-nums'],
  },
  metricUnit: {
    fontSize: 13,
    fontFamily: FONT.regular,
  },
  metricSub: {
    ...TYPOGRAPHY.secondary,
  },
  riskBarContainer: {
    gap: 6,
    marginTop: 4,
  },
  riskLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 4,
  },
  riskLabelEdge: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  riskLabelMid: {
    fontSize: 13,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  barTrack: {
    height: 8,
    borderRadius: 4,
    flexDirection: 'row',
    overflow: 'hidden',
    borderWidth: 1,
  },
  barSegment: {
    height: '100%',
  },
  riskFooter: {
    fontSize: 12,
    fontFamily: FONT.regular,
    textAlign: 'center',
  },
  actionBtn: {
    minHeight: 44,
    borderRadius: 10,
    borderWidth: 1,
    paddingVertical: 10,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
  },
  btnDisabled: {
    opacity: 0.45,
  },
  btnIcon: {
    fontSize: 15,
  },
  actionBtnText: {
    ...TYPOGRAPHY.button,
    textAlign: 'center',
  },
  pill: {
    paddingHorizontal: 10,
    paddingVertical: 3,
    borderRadius: 999,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  pillText: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  twoCol: {
    flexDirection: 'row',
    gap: 12,
  },
  linkRow: {
    minHeight: 54,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderWidth: 1,
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  linkTitle: {
    fontSize: 15,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  linkSubtitle: {
    fontSize: 13,
    fontFamily: FONT.regular,
    lineHeight: 18,
  },
  linkBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
  },
  linkBadgeText: {
    fontSize: 11,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  linkChevron: {
    fontSize: 22,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
});
