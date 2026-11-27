import React, { useContext } from 'react';
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { C, SEVERITY_COLORS, SEVERITY_BG, SHADOWS } from '../theme';
import { AlarmLevel, DataMode, LinkStatus } from '../types/domain';

/** Cho Page biết đang ở MOCK hay LIVE để không hiển thị chuỗi demo (độ trễ giả, "SIMULATION MODE"...) trên dữ liệu thật. */
export const DataModeContext = React.createContext<{
  mode: DataMode;
  link: LinkStatus | null;
  source: string | null;
}>({ mode: 'mock', link: null, source: null });

export function Page({
  title,
  subtitle,
  children,
  onBack,
  vesselName = 'VESSEL DEMO 01',
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
  const ctx = useContext(DataModeContext);
  const isLive = ctx.mode === 'live';
  const linkColor =
    ctx.link?.state === 'ONLINE' ? C.green : ctx.link?.state === 'SENSOR_FAULT' ? C.amber : C.red;
  return (
    <ScrollView
      style={styles.page}
      contentContainerStyle={styles.pageContent}
      keyboardShouldPersistTaps="handled"
    >
      {/* Top Bridge App Bar */}
      <View style={styles.topAppBar}>
        <View style={styles.topAppBarLeft}>
          {onBack ? (
            <Pressable
              onPress={onBack}
              style={styles.backBtn}
              accessibilityRole="button"
              accessibilityLabel="Go back"
            >
              <Text style={styles.backChevron}>‹</Text>
              <Text style={styles.backBtnText}>BACK</Text>
            </Pressable>
          ) : (
            <View style={styles.vesselBrand}>
              <Text style={styles.boatIcon}>≋</Text>
              <View>
                <Text style={styles.vesselName}>{vesselName}</Text>
                <Text style={styles.vesselSub}>
                  BRIDGE TELEMETRY {unackCount > 0 ? `• ${unackCount} UNACK` : isLive ? '• KHÔNG CÓ CẢNH BÁO MỞ' : '• NORMAL'}
                </Text>
              </View>
            </View>
          )}
        </View>

        {/* Right Horn/Buzzer toggle & Sensor status */}
        <View style={styles.topAppBarRight}>
          {onToggleHorn && (
            <Pressable
              onPress={onToggleHorn}
              style={[
                styles.hornPill,
                isHornMuted ? styles.hornMuted : styles.hornActive,
              ]}
              accessibilityRole="button"
              accessibilityLabel={isHornMuted ? 'Buzzer muted' : 'Buzzer active'}
            >
              <Text style={[styles.hornIcon, { color: isHornMuted ? C.muted : C.red }]}>
                {isHornMuted ? '🕨' : '🔔'}
              </Text>
              <View>
                <Text style={styles.hornTitle}>HORN</Text>
                <Text
                  style={[
                    styles.hornStatus,
                    { color: isHornMuted ? C.muted : C.red },
                  ]}
                >
                  {isHornMuted ? 'MUTED' : 'ACTIVE'}
                </Text>
              </View>
            </Pressable>
          )}
        </View>
      </View>

      {/* Sub-Header Telemetry Ribbon */}
      <View style={styles.telemetryRibbon}>
        <View style={styles.ribbonRow}>
          <View style={styles.simBadge}>
            <View style={[styles.simDot, isLive ? { backgroundColor: linkColor } : null]} />
            <Text style={[styles.simText, isLive ? { color: linkColor } : null]}>
              {isLive
                ? `${ctx.link?.label ?? 'LIVE'}${ctx.source ? ` • ${ctx.source}` : ''}`
                : 'SIMULATION MODE (DEMO)'}
            </Text>
          </View>
          <Text style={styles.utcTime}>{utcTime ?? (isLive ? '—' : '14:28:12 UTC')}</Text>
        </View>
        <View style={styles.ribbonSubRow}>
          <Text style={styles.streamText}>
            {isLive ? '● Backend REST (JWT) • làm mới 5–10s' : '● 40Hz BLE/LTE Telemetry Link'}
          </Text>
          <Text style={styles.latencyText}>
            {isLive
              ? ctx.link?.ageS !== null && ctx.link?.ageS !== undefined
                ? `Mẫu cuối: ${ctx.link.ageS}s trước`
                : 'Chưa có mẫu'
              : 'Latency: 24ms'}
          </Text>
        </View>
      </View>

      {/* Optional Screen Title & Subtitle */}
      {title && (
        <View style={styles.titleArea}>
          <Text style={styles.screenTitle}>{title}</Text>
          {subtitle && <Text style={styles.screenSubtitle}>{subtitle}</Text>}
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
  elapsed = 'T+04:12',
}: {
  level: AlarmLevel;
  title: string;
  desc: string;
  elapsed?: string;
}) {
  const color = SEVERITY_COLORS[level];
  const bg = SEVERITY_BG[level];
  const glow =
    level === 'CRITICAL'
      ? SHADOWS.criticalGlow
      : level === 'WARNING'
      ? SHADOWS.warningGlow
      : level === 'CAUTION'
      ? SHADOWS.cautionGlow
      : undefined;

  return (
    <View style={[styles.banner, { borderLeftColor: color, backgroundColor: bg }, glow]}>
      <View style={styles.bannerHeader}>
        <View style={styles.bannerBadgeRow}>
          <View style={[styles.pulseDot, { backgroundColor: color }]} />
          <View style={[styles.bannerPill, { borderColor: color }]}>
            <Text style={[styles.bannerPillText, { color }]}>{level}</Text>
          </View>
          <Text style={styles.bannerTitle}>{title}</Text>
        </View>
        <Text style={styles.bannerElapsed}>{elapsed}</Text>
      </View>
      <Text style={styles.bannerDesc}>{desc}</Text>
    </View>
  );
}

export function RiskBar({ score }: { score: number }) {
  // score is 0.0 - 1.0 (or 0 - 100)
  const normScore = score > 1 ? score / 100 : score;
  return (
    <View style={styles.riskBarContainer}>
      <View style={styles.riskLabels}>
        <Text style={styles.riskLabelLeft}>Normal &lt;0.35</Text>
        <Text
          style={[
            styles.riskLabelMid,
            { color: normScore >= 0.7 ? C.red : normScore >= 0.35 ? C.amber : C.green },
          ]}
        >
          ▲ Current: {normScore.toFixed(2)}
        </Text>
        <Text style={styles.riskLabelRight}>Alert ≥0.70</Text>
      </View>
      <View style={styles.barTrack}>
        <View style={[styles.barSegment, { width: '35%', backgroundColor: C.green }]} />
        <View style={[styles.barSegment, { width: '35%', backgroundColor: C.amber }]} />
        <View style={[styles.barSegment, { width: '30%', backgroundColor: C.red }]} />
      </View>
      <Text style={styles.riskFooter}>
        Calibrated demo thresholds • Random Forest Classifier
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
  return (
    <View style={styles.panel}>
      {(title || tag || extra) && (
        <View style={styles.panelHeader}>
          {title && <Text style={styles.panelTitle}>{title}</Text>}
          {tag && <Text style={styles.panelTag}>{tag}</Text>}
          {extra && <Text style={styles.panelExtra}>{extra}</Text>}
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
  color = C.text,
  flex = 1,
}: {
  label: string;
  value: string;
  unit?: string;
  subtext?: string;
  color?: string;
  flex?: number;
}) {
  return (
    <View style={[styles.metricCard, { flex }]}>
      <Text style={styles.metricLabel}>{label}</Text>
      <View style={styles.metricValRow}>
        <Text style={[styles.metricVal, { color }]}>{value}</Text>
        {unit && <Text style={styles.metricUnit}>{unit}</Text>}
      </View>
      {subtext && <Text style={styles.metricSub}>{subtext}</Text>}
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
  return (
    <Pressable
      onPress={onPress}
      disabled={disabled}
      accessibilityRole="button"
      style={({ pressed }) => [
        styles.actionBtn,
        tone === 'primary'
          ? styles.btnPrimary
          : tone === 'secondary'
          ? styles.btnSecondary
          : tone === 'danger'
          ? styles.btnDanger
          : tone === 'ghost'
          ? styles.btnGhost
          : styles.btnNeutral,
        disabled && styles.btnDisabled,
        pressed && !disabled && styles.btnPressed,
      ]}
    >
      {icon && <Text style={styles.btnIcon}>{icon}</Text>}
      <Text
        style={[
          styles.actionBtnText,
          tone === 'primary' ? styles.textPrimary : styles.textNeutral,
          disabled && styles.textDisabled,
        ]}
      >
        {label}
      </Text>
    </Pressable>
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
  const color = level
    ? SEVERITY_COLORS[level]
    : status === 'APPLIED' || status === 'ACKED' || status === 'RESOLVED'
    ? C.green
    : status === 'REJECTED'
    ? C.red
    : C.cyan;

  const bg = level
    ? SEVERITY_BG[level]
    : 'rgba(2, 132, 199, 0.08)';

  const glow =
    level === 'CRITICAL'
      ? SHADOWS.criticalGlow
      : level === 'WARNING'
      ? SHADOWS.warningGlow
      : undefined;

  return (
    <View style={[styles.pill, { borderColor: color, backgroundColor: bg }, glow]}>
      <Text style={[styles.pillText, { color }]}>{label}</Text>
    </View>
  );
}

export function TwoCol({ children }: { children: React.ReactNode }) {
  return <View style={styles.twoCol}>{children}</View>;
}

export function Label({ children }: { children: React.ReactNode }) {
  return <Text style={styles.metricLabel}>{children}</Text>;
}

export function Value({ children, color }: { children: React.ReactNode; color?: string }) {
  return <Text style={[styles.metricVal, color ? { color } : null]}>{children}</Text>;
}

export function Body({ children }: { children: React.ReactNode }) {
  return <Text style={styles.bannerDesc}>{children}</Text>;
}

export function Small({ children }: { children: React.ReactNode }) {
  return <Text style={styles.riskFooter}>{children}</Text>;
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
  onPress,
  disabled = false,
}: {
  title: string;
  subtitle?: string;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={[styles.linkRow, disabled && { opacity: 0.4 }]}
    >
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={styles.linkTitle}>{title}</Text>
        {subtitle && <Text style={styles.linkSubtitle}>{subtitle}</Text>}
      </View>
      <Text style={styles.linkChevron}>›</Text>
    </Pressable>
  );
}

export function Severity({ level }: { level: AlarmLevel }) {
  return <Pill label={level} level={level} />;
}

const styles = StyleSheet.create({
  page: {
    flex: 1,
    backgroundColor: C.canvas,
  },
  pageContent: {
    paddingHorizontal: 14,
    paddingTop: 8,
    paddingBottom: 28,
    gap: 12,
  },
  topAppBar: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: C.borderSubtle,
    backgroundColor: C.bg,
  },
  topAppBarLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  topAppBarRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  vesselBrand: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  boatIcon: {
    color: C.cyan,
    fontSize: 22,
    fontWeight: '800',
  },
  vesselName: {
    color: C.text,
    fontSize: 14,
    fontWeight: '800',
    letterSpacing: 0.8,
  },
  vesselSub: {
    color: C.muted,
    fontSize: 9,
    fontWeight: '600',
    letterSpacing: 0.4,
    marginTop: 1,
  },
  backBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 10,
    backgroundColor: C.bg,
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 8,
    gap: 4,
  },
  backChevron: {
    color: C.cyanBright,
    fontSize: 16,
    fontWeight: '800',
    marginTop: -2,
  },
  backBtnText: {
    color: C.cyanBright,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  hornPill: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 20,
    borderWidth: 1,
    gap: 6,
  },
  hornActive: {
    backgroundColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: C.red,
  },
  hornMuted: {
    backgroundColor: C.panel2,
    borderColor: C.border,
  },
  hornIcon: {
    fontSize: 13,
  },
  hornTitle: {
    color: C.text,
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 0.5,
    lineHeight: 9,
  },
  hornStatus: {
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 0.4,
    lineHeight: 9,
    marginTop: 1,
  },
  telemetryRibbon: {
    backgroundColor: C.panel2,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    paddingVertical: 7,
    paddingHorizontal: 12,
    gap: 5,
  },
  ribbonRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  simBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(245, 158, 11, 0.12)',
    paddingHorizontal: 8,
    paddingVertical: 2.5,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(245, 158, 11, 0.35)',
  },
  simDot: {
    width: 5,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: C.amber,
  },
  simText: {
    color: C.amber,
    fontSize: 9,
    fontWeight: '800',
    letterSpacing: 0.4,
  },
  utcTime: {
    color: C.textSecondary,
    fontSize: 11,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  ribbonSubRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderTopWidth: 1,
    borderTopColor: C.borderSubtle,
    paddingTop: 4,
  },
  streamText: {
    color: C.cyan,
    fontSize: 10,
    fontWeight: '700',
  },
  latencyText: {
    color: C.muted,
    fontSize: 10,
  },
  titleArea: {
    marginTop: 2,
    marginBottom: 2,
  },
  screenTitle: {
    color: C.text,
    fontSize: 18,
    fontWeight: '800',
    letterSpacing: 0.4,
  },
  screenSubtitle: {
    color: C.muted,
    fontSize: 11,
    marginTop: 2,
  },
  banner: {
    borderLeftWidth: 3.5,
    borderRadius: 12,
    borderTopWidth: 1,
    borderRightWidth: 1,
    borderBottomWidth: 1,
    borderColor: C.borderSubtle,
    padding: 12,
    gap: 6,
  },
  bannerHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  bannerBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  pulseDot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  bannerPill: {
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 7,
    paddingVertical: 1.5,
  },
  bannerPillText: {
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  bannerTitle: {
    color: C.text,
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  bannerElapsed: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '600',
    backgroundColor: C.panel2,
    paddingHorizontal: 7,
    paddingVertical: 2,
    borderRadius: 20,
  },
  bannerDesc: {
    color: C.text,
    fontSize: 12,
    lineHeight: 17,
  },
  panel: {
    backgroundColor: C.panel,
    borderWidth: 1,
    borderLeftWidth: 3.5,
    borderColor: C.borderSubtle,
    borderLeftColor: C.borderNavy,
    borderRadius: 14,
    padding: 14,
    gap: 10,
    ...SHADOWS.card,
  },
  panelHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: C.borderSubtle,
    paddingBottom: 6,
  },
  panelTitle: {
    color: C.cyan,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  panelTag: {
    color: C.muted,
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
  panelExtra: {
    color: C.borderFocus,
    fontSize: 10,
    fontWeight: '700',
  },
  metricCard: {
    backgroundColor: C.bg,
    borderWidth: 1,
    borderLeftWidth: 3.5,
    borderColor: C.borderSubtle,
    borderLeftColor: C.borderNavy,
    borderRadius: 12,
    padding: 12,
    gap: 4,
    minWidth: 120,
    ...SHADOWS.sm,
  },
  metricLabel: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  metricValRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    gap: 3,
  },
  metricVal: {
    fontSize: 22,
    fontWeight: '800',
    fontVariant: ['tabular-nums'],
    letterSpacing: -0.5,
  },
  metricUnit: {
    color: C.muted,
    fontSize: 11,
    fontWeight: '600',
  },
  metricSub: {
    color: C.textSecondary,
    fontSize: 10,
  },
  riskBarContainer: {
    gap: 4,
    marginTop: 4,
  },
  riskLabels: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  riskLabelLeft: {
    color: C.muted,
    fontSize: 9,
  },
  riskLabelMid: {
    fontSize: 10,
    fontWeight: '800',
  },
  riskLabelRight: {
    color: C.red,
    fontSize: 9,
    fontWeight: '700',
  },
  barTrack: {
    height: 6,
    borderRadius: 3,
    backgroundColor: C.canvas,
    flexDirection: 'row',
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: C.borderSubtle,
  },
  barSegment: {
    height: '100%',
  },
  riskFooter: {
    color: C.muted,
    fontSize: 9,
    textAlign: 'center',
    marginTop: 2,
  },
  actionBtn: {
    minHeight: 44,
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  btnPrimary: {
    backgroundColor: C.primaryContainer,
    borderWidth: 1,
    borderColor: C.borderNavy,
  },
  btnSecondary: {
    backgroundColor: C.panelHigh,
    borderWidth: 1,
    borderColor: C.borderSubtle,
  },
  btnDanger: {
    backgroundColor: C.red,
  },
  btnNeutral: {
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
  },
  btnGhost: {
    backgroundColor: 'transparent',
    borderWidth: 1,
    borderColor: C.borderSubtle,
  },
  btnDisabled: {
    opacity: 0.35,
  },
  btnPressed: {
    opacity: 0.8,
  },
  btnIcon: {
    fontSize: 14,
    color: '#FFFFFF',
  },
  actionBtnText: {
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.5,
    textAlign: 'center',
  },
  textPrimary: {
    color: '#FFFFFF',
  },
  textNeutral: {
    color: C.text,
  },
  textDisabled: {
    color: C.muted,
  },
  pill: {
    paddingHorizontal: 8,
    paddingVertical: 2.5,
    borderRadius: 20,
    borderWidth: 1,
  },
  pillText: {
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 0.4,
  },
  twoCol: {
    flexDirection: 'row',
    gap: 8,
  },
  linkRow: {
    minHeight: 52,
    paddingVertical: 12,
    paddingHorizontal: 14,
    backgroundColor: C.bg,
    borderColor: C.borderSubtle,
    borderWidth: 1,
    borderLeftWidth: 3.5,
    borderLeftColor: C.borderNavy,
    borderRadius: 12,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    ...SHADOWS.sm,
  },
  linkTitle: {
    color: C.text,
    fontSize: 13,
    fontWeight: '700',
  },
  linkSubtitle: {
    color: C.muted,
    fontSize: 11,
  },
  linkChevron: {
    fontSize: 22,
    color: C.cyan,
    fontWeight: '800',
  },
});
