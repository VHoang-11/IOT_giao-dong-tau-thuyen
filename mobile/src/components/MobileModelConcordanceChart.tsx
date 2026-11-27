import React, { useMemo, useState } from 'react';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Svg, { Circle, G, Line, Rect, Text as SvgText } from 'react-native-svg';
import { FONT, SHADOWS, useTheme } from '../theme';
import { RFClass, Scenario } from '../types/domain';
import { getRFClassNameVi } from '../i18n/vi';

interface MobileModelConcordanceChartProps {
  scenario?: Scenario;
  height?: number;
}

export function MobileModelConcordanceChart({
  scenario = 'S0',
  height = 140,
}: MobileModelConcordanceChartProps) {
  const { colors } = useTheme();
  const { width: windowWidth } = useWindowDimensions();
  const width = Math.max(260, Math.min(windowWidth - 64, 460));
  const xPad = 38;
  const yPad = 14;

  const [touchIdx, setTouchIdx] = useState<number | null>(null);

  const points = useMemo(() => {
    return Array.from({ length: 25 }, (_, i) => {
      const t = i * 5;
      let rf: RFClass = 'NORMAL';
      let baseline: RFClass = 'NORMAL';

      if (scenario === 'S0b') {
        if (i >= 8 && i <= 14) {
          baseline = 'HIGH_ROLL';
          rf = 'NORMAL';
        }
      } else if (scenario === 'S1') {
        rf = 'HIGH_ROLL';
        baseline = 'HIGH_ROLL';
      } else if (scenario === 'S2') {
        rf = 'PERSISTENT_OFFSET';
        baseline = 'PERSISTENT_OFFSET';
      } else if (scenario === 'S3') {
        rf = i > 10 ? 'AMPLITUDE_GROWTH' : 'NORMAL';
        baseline = i > 10 ? 'HIGH_ROLL' : 'NORMAL';
      } else if (scenario === 'H1') {
        rf = 'AMPLITUDE_GROWTH';
        baseline = 'HIGH_ROLL';
      }

      const agree = rf === baseline;
      return { seq: i, t_sim_s: t, rf, baseline, agree };
    });
  }, [scenario]);

  const scaleX = (i: number) => xPad + (i / Math.max(1, points.length - 1)) * (width - xPad - 10);

  const classColor = (c: RFClass) => {
    switch (c) {
      case 'NORMAL':
        return colors.green;
      case 'HIGH_ROLL':
        return colors.amber;
      case 'PERSISTENT_OFFSET':
        return colors.tech;
      case 'AMPLITUDE_GROWTH':
        return colors.red;
      default:
        return colors.muted;
    }
  };

  const handleTouch = (locationX: number) => {
    const chartW = width - xPad - 10;
    const relX = Math.max(0, Math.min(chartW, locationX - xPad));
    const ratio = relX / Math.max(1, chartW);
    const idx = Math.min(points.length - 1, Math.max(0, Math.round(ratio * (points.length - 1))));
    setTouchIdx(idx);
  };

  const activeIdx = touchIdx !== null ? touchIdx : points.length - 1;
  const active = points[activeIdx] || points[0];
  const agreeCount = points.filter((p) => p.agree).length;
  const agreePct = ((agreeCount / points.length) * 100).toFixed(0);

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
          Diễn biến đồng thuận theo thời gian
        </Text>
        <View
          style={[
            styles.badgeWrap,
            {
              backgroundColor: +agreePct >= 90 ? colors.greenContainerBg : colors.warningContainerBg,
            },
          ]}
        >
          <Text
            style={[
              styles.cardBadge,
              { color: +agreePct >= 90 ? colors.green : colors.amber },
            ]}
          >
            {agreePct}% đồng thuận
          </Text>
        </View>
      </View>

      <View
        style={styles.touchArea}
        onStartShouldSetResponder={() => true}
        onMoveShouldSetResponder={() => true}
        onResponderGrant={(e) => handleTouch(e.nativeEvent.locationX)}
        onResponderMove={(e) => handleTouch(e.nativeEvent.locationX)}
        onResponderRelease={() => setTouchIdx(null)}
        onResponderTerminate={() => setTouchIdx(null)}
      >
        <Svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
          <Rect
            x={0}
            y={0}
            width={width}
            height={height}
            fill={colors.panel}
            stroke={colors.borderSubtle}
            strokeWidth={1}
            rx={10}
          />

          <Line x1={xPad} y1={yPad + 14} x2={width - 10} y2={yPad + 14} stroke={colors.border} strokeWidth={1} />
          <Line x1={xPad} y1={yPad + 44} x2={width - 10} y2={yPad + 44} stroke={colors.border} strokeWidth={1} />
          <Line x1={xPad} y1={yPad + 74} x2={width - 10} y2={yPad + 74} stroke={colors.border} strokeWidth={1} />

          <SvgText x={xPad - 5} y={yPad + 17} textAnchor="end" fill={colors.tech} fontSize={9} fontWeight="700">
            RF
          </SvgText>
          <SvgText x={xPad - 5} y={yPad + 47} textAnchor="end" fill={colors.amber} fontSize={9} fontWeight="700">
            B-B
          </SvgText>
          <SvgText x={xPad - 5} y={yPad + 77} textAnchor="end" fill={colors.title} fontSize={9} fontWeight="600">
            Khớp
          </SvgText>

          {points.map((p, i) => {
            const x = scaleX(i);
            const isHover = activeIdx === i;
            return (
              <G key={i}>
                {isHover && (
                  <Rect
                    x={x - 5}
                    y={yPad}
                    width={10}
                    height={86}
                    fill={colors.cyanContainerBg}
                    opacity={0.75}
                    rx={2}
                  />
                )}
                <Circle
                  cx={x}
                  cy={yPad + 14}
                  r={isHover ? 4.5 : 3.2}
                  fill={classColor(p.rf)}
                  stroke={colors.panel}
                  strokeWidth={1}
                />
                <Circle
                  cx={x}
                  cy={yPad + 44}
                  r={isHover ? 4.5 : 3.2}
                  fill={classColor(p.baseline)}
                  stroke={colors.panel}
                  strokeWidth={1}
                />
                <Circle
                  cx={x}
                  cy={yPad + 74}
                  r={isHover ? 4 : 2.8}
                  fill={p.agree ? colors.green : colors.amber}
                />
                {!p.agree && (
                  <Line
                    x1={x}
                    y1={yPad + 14}
                    x2={x}
                    y2={yPad + 74}
                    stroke={colors.amber}
                    strokeWidth={1}
                    strokeDasharray="2 2"
                  />
                )}
              </G>
            );
          })}
        </Svg>
      </View>

      {/* Readout */}
      <View
        style={[
          styles.readoutRow,
          { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
        ]}
      >
        <Text style={[styles.readoutLabel, { color: colors.textSecondary }]}>
          Mẫu #{active.seq + 1} (T+{active.t_sim_s}s)
        </Text>
        <Text style={[styles.readoutTag, { color: colors.tech }]}>
          RF: {getRFClassNameVi(active.rf)}
        </Text>
        <Text style={[styles.readoutTag, { color: colors.amber }]}>
          Baseline B: {getRFClassNameVi(active.baseline)}
        </Text>
        <Text style={[styles.readoutStatus, { color: active.agree ? colors.green : colors.amber }]}>
          {active.agree ? '✓ Đồng thuận' : '⚠ Bất đồng'}
        </Text>
      </View>

      {scenario === 'S0b' && (
        <View
          style={[
            styles.callout,
            { backgroundColor: colors.warningContainerBg, borderColor: colors.amber },
          ]}
        >
          <Text style={[styles.calloutText, { color: colors.title }]}>
            Kịch bản S0b: Gió giật làm Baseline B phát nhãn Lắc ngang mạnh, trong khi Random Forest nhận diện tàu đang tự hồi phục nên giữ nhãn Bình thường.
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 16,
    gap: 10,
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
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  touchArea: {
    width: '100%',
    alignItems: 'center',
  },
  readoutRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
    paddingHorizontal: 10,
    paddingVertical: 7,
    borderRadius: 8,
    borderWidth: 1,
  },
  readoutLabel: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  readoutTag: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  readoutStatus: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  callout: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 10,
  },
  calloutText: {
    fontSize: 13,
    fontFamily: FONT.regular,
    lineHeight: 18,
  },
});
