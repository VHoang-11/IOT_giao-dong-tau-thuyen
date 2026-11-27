import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { FONT, SHADOWS, useTheme } from '../theme';
import { Voyage } from '../types/domain';

interface MobileVoyageChartsProps {
  voyage: Voyage;
}

export function MobileVoyageDistributionChart({ voyage }: MobileVoyageChartsProps) {
  const { colors } = useTheme();

  const bars = [
    {
      label: 'Góc lắc ngang cực đại',
      val: voyage.maxAbsRollDeg,
      max: 25,
      unit: '°',
      color: voyage.maxAbsRollDeg >= 15 ? colors.red : colors.tech,
      threshold: 15.0,
    },
    {
      label: 'Góc lắc ngang hiệu dụng (RMS)',
      val: voyage.rmsRollDeg,
      max: 25,
      unit: '°',
      color: colors.tech,
    },
    {
      label: 'Phân vị 95 góc lắc (P95)',
      val: voyage.p95AbsRollDeg,
      max: 25,
      unit: '°',
      color: colors.tech,
    },
    {
      label: 'Góc chúi dọc cực đại',
      val: voyage.maxAbsPitchDeg,
      max: 10,
      unit: '°',
      color: colors.amber,
    },
    {
      label: 'Góc chúi dọc hiệu dụng (RMS)',
      val: voyage.rmsPitchDeg,
      max: 10,
      unit: '°',
      color: colors.amber,
    },
  ];

  return (
    <View
      style={[
        styles.card,
        { backgroundColor: colors.panel, borderColor: colors.border },
        SHADOWS.card,
      ]}
    >
      <View style={[styles.cardHeader, { borderBottomColor: colors.borderSubtle }]}>
        <Text style={[styles.cardTitle, { color: colors.title }]}>
          Phân phối thống kê động học
        </Text>
        <View style={[styles.badgeWrap, { backgroundColor: colors.cyanContainerBg }]}>
          <Text style={[styles.cardBadge, { color: colors.tech }]}>
            {voyage.sampleCount} mẫu
          </Text>
        </View>
      </View>

      <View style={styles.barsContainer}>
        {bars.map((b) => {
          const pct = Math.min(100, (b.val / b.max) * 100);
          return (
            <View key={b.label} style={styles.barRow}>
              <View style={styles.barLabelRow}>
                <Text style={[styles.barLabel, { color: colors.title }]}>{b.label}</Text>
                <Text style={[styles.barVal, { color: b.color }]}>
                  {b.val.toFixed(2)}
                  {b.unit}
                </Text>
              </View>
              <View
                style={[
                  styles.barTrack,
                  { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
                ]}
              >
                <View style={[styles.barFill, { width: `${pct}%`, backgroundColor: b.color }]} />
                {b.threshold && (
                  <View
                    style={[
                      styles.thresholdLine,
                      { left: `${(b.threshold / b.max) * 100}%`, backgroundColor: colors.red },
                    ]}
                  />
                )}
              </View>
            </View>
          );
        })}
      </View>

      <Text style={[styles.footerNote, { color: colors.textSecondary }]}>
        Vạch đỏ: Ngưỡng cảnh báo lắc ngang 15.0° (Cấu hình mô phỏng)
      </Text>
    </View>
  );
}

export function MobileRfBreakdownChart({ voyage }: MobileVoyageChartsProps) {
  const { colors } = useTheme();
  const dist = voyage.rfDistribution;
  const segments = [
    { label: 'Bình thường', pct: dist.normalPct, color: colors.green },
    { label: 'Lắc ngang mạnh', pct: dist.highRollPct, color: colors.amber },
    { label: 'Nghiêng lệch kéo dài', pct: dist.persistentOffsetPct, color: colors.tech },
    { label: 'Biên độ tăng', pct: dist.amplitudeGrowthPct, color: colors.red },
  ];

  return (
    <View
      style={[
        styles.card,
        { backgroundColor: colors.panel, borderColor: colors.border },
        SHADOWS.card,
      ]}
    >
      <View style={[styles.cardHeader, { borderBottomColor: colors.borderSubtle }]}>
        <Text style={[styles.cardTitle, { color: colors.title }]}>
          Phân bố trạng thái Random Forest
        </Text>
        <View style={[styles.badgeWrap, { backgroundColor: colors.greenContainerBg }]}>
          <Text style={[styles.cardBadge, { color: colors.green }]}>
            ✓ {voyage.agreementPercent}% đồng thuận
          </Text>
        </View>
      </View>

      <View
        style={[
          styles.segmentBar,
          { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
        ]}
      >
        {segments.map((s) => (
          <View
            key={s.label}
            style={[styles.segmentSlice, { width: `${s.pct}%`, backgroundColor: s.color }]}
          />
        ))}
      </View>

      <View style={styles.legendGrid}>
        {segments.map((s) => (
          <View
            key={s.label}
            style={[
              styles.legendPill,
              { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
            ]}
          >
            <View style={[styles.dot, { backgroundColor: s.color }]} />
            <Text style={[styles.legendLabel, { color: colors.title }]}>{s.label}:</Text>
            <Text style={[styles.legendVal, { color: s.color }]}>{s.pct.toFixed(1)}%</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    gap: 12,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 8,
    paddingBottom: 8,
    borderBottomWidth: 1,
  },
  cardTitle: {
    fontSize: 17,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  badgeWrap: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  cardBadge: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  barsContainer: {
    gap: 10,
  },
  barRow: {
    gap: 4,
  },
  barLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
  },
  barLabel: {
    fontSize: 13,
    fontFamily: FONT.medium,
    flexShrink: 1,
  },
  barVal: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  barTrack: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
    position: 'relative',
    borderWidth: 1,
  },
  barFill: {
    height: '100%',
    borderRadius: 4,
  },
  thresholdLine: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: 2,
  },
  footerNote: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  segmentBar: {
    height: 14,
    flexDirection: 'row',
    borderRadius: 6,
    overflow: 'hidden',
    borderWidth: 1,
  },
  segmentSlice: {
    height: '100%',
  },
  legendGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  legendPill: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 8,
    paddingVertical: 4,
    gap: 5,
  },
  dot: {
    width: 7,
    height: 7,
    borderRadius: 3.5,
  },
  legendLabel: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  legendVal: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
});
