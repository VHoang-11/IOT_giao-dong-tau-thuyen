import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { C } from '../theme';
import { Voyage } from '../types/domain';

interface MobileVoyageChartsProps {
  voyage: Voyage;
}

export function MobileVoyageDistributionChart({ voyage }: MobileVoyageChartsProps) {
  const bars = [
    { label: 'Max Roll', val: voyage.maxAbsRollDeg, max: 25, unit: '°', color: voyage.maxAbsRollDeg > 15 ? C.red : C.cyan, threshold: 15.0 },
    { label: 'RMS Roll (T11)', val: voyage.rmsRollDeg, max: 25, unit: '°', color: C.cyan },
    { label: 'P95 Roll', val: voyage.p95AbsRollDeg, max: 25, unit: '°', color: '#0369A1' },
    { label: 'Max Pitch', val: voyage.maxAbsPitchDeg, max: 10, unit: '°', color: C.amber },
    { label: 'RMS Pitch', val: voyage.rmsPitchDeg, max: 10, unit: '°', color: '#B45309' },
  ];

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>PHÂN PHỐI THỐNG KÊ ĐỘNG HỌC (T11)</Text>
        <Text style={styles.cardBadge}>{voyage.sampleCount} MẪU</Text>
      </View>

      <View style={styles.barsContainer}>
        {bars.map((b) => {
          const pct = Math.min(100, (b.val / b.max) * 100);
          return (
            <View key={b.label} style={styles.barRow}>
              <View style={styles.barLabelRow}>
                <Text style={styles.barLabel}>{b.label}</Text>
                <Text style={[styles.barVal, { color: b.color }]}>
                  {b.val.toFixed(2)}{b.unit}
                </Text>
              </View>
              <View style={styles.barTrack}>
                <View style={[styles.barFill, { width: `${pct}%`, backgroundColor: b.color }]} />
                {b.threshold && (
                  <View
                    style={[
                      styles.thresholdLine,
                      { left: `${(b.threshold / b.max) * 100}%` },
                    ]}
                  />
                )}
              </View>
            </View>
          );
        })}
      </View>

      <Text style={styles.footerNote}>Vạch đỏ: Ngưỡng cảnh báo lắc ngang 15.0° (Mô phỏng)</Text>
    </View>
  );
}

export function MobileRfBreakdownChart({ voyage }: MobileVoyageChartsProps) {
  const dist = voyage.rfDistribution;
  const segments = [
    { label: 'Normal', pct: dist.normalPct, color: C.green },
    { label: 'High Roll', pct: dist.highRollPct, color: C.amber },
    { label: 'Offset', pct: dist.persistentOffsetPct, color: '#38BDF8' },
    { label: 'Growth', pct: dist.amplitudeGrowthPct, color: C.red },
  ];

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>PHÂN BỐ TRẠNG THÁI RANDOM FOREST</Text>
        <Text style={[styles.cardBadge, { color: C.green, backgroundColor: '#D1FAE5', borderColor: '#A7F3D0' }]}>
          ✓ {voyage.agreementPercent}% Đồng thuận
        </Text>
      </View>

      {/* Multi-segment bar */}
      <View style={styles.segmentBar}>
        {segments.map((s) => (
          <View
            key={s.label}
            style={[
              styles.segmentSlice,
              { width: `${s.pct}%`, backgroundColor: s.color },
            ]}
          />
        ))}
      </View>

      {/* Breakdown Pills */}
      <View style={styles.legendGrid}>
        {segments.map((s) => (
          <View key={s.label} style={styles.legendPill}>
            <View style={[styles.dot, { backgroundColor: s.color }]} />
            <Text style={styles.legendLabel}>{s.label}:</Text>
            <Text style={[styles.legendVal, { color: s.color }]}>{s.pct.toFixed(1)}%</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 8,
    padding: 12,
    marginBottom: 10,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: C.borderSubtle,
  },
  cardTitle: {
    color: C.text,
    fontSize: 11,
    fontWeight: '800',
    fontFamily: 'monospace',
    letterSpacing: 0.3,
  },
  cardBadge: {
    fontSize: 9,
    fontFamily: 'monospace',
    fontWeight: '700',
    color: C.cyan,
    backgroundColor: '#E0F2FE',
    borderWidth: 0.5,
    borderColor: '#BAE6FD',
    borderRadius: 3,
    paddingHorizontal: 5,
    paddingVertical: 1,
  },
  barsContainer: {
    gap: 8,
  },
  barRow: {
    gap: 3,
  },
  barLabelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  barLabel: {
    color: C.text,
    fontSize: 10,
    fontWeight: '600',
  },
  barVal: {
    fontSize: 11,
    fontFamily: 'monospace',
    fontWeight: '700',
  },
  barTrack: {
    height: 8,
    backgroundColor: '#F1F5F9',
    borderRadius: 4,
    overflow: 'hidden',
    position: 'relative',
    borderWidth: 0.5,
    borderColor: C.borderSubtle,
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
    backgroundColor: C.red,
  },
  footerNote: {
    color: C.muted,
    fontSize: 9,
    marginTop: 8,
    fontStyle: 'italic',
  },
  segmentBar: {
    height: 14,
    flexDirection: 'row',
    borderRadius: 4,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: C.border,
    marginBottom: 10,
  },
  segmentSlice: {
    height: '100%',
  },
  legendGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
  },
  legendPill: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#F8FAFC',
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 3,
    gap: 4,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  legendLabel: {
    color: C.text,
    fontSize: 9,
    fontWeight: '600',
  },
  legendVal: {
    fontSize: 9.5,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
});

