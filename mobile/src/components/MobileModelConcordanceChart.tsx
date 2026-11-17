import React, { useState } from 'react';
import { useWindowDimensions, View, Text, StyleSheet } from 'react-native';
import Svg, { Line, Circle, Rect, G, Text as SvgText } from 'react-native-svg';
import { C } from '../theme';
import { RFClass, Scenario } from '../types/domain';

interface MobileModelConcordanceChartProps {
  scenario?: Scenario;
  height?: number;
}

export function MobileModelConcordanceChart({
  scenario = 'S0',
  height = 145,
}: MobileModelConcordanceChartProps) {
  const { width: windowWidth } = useWindowDimensions();
  const width = Math.max(260, Math.min(windowWidth - 48, 420));
  const xPad = 32;
  const yPad = 14;

  const [touchIdx, setTouchIdx] = useState<number | null>(null);

  const points = React.useMemo(() => {
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

  const scaleX = (i: number) => {
    return xPad + (i / Math.max(1, points.length - 1)) * (width - xPad - 8);
  };

  const classColor = (c: RFClass) => {
    switch (c) {
      case 'NORMAL': return C.green;
      case 'HIGH_ROLL': return C.amber;
      case 'PERSISTENT_OFFSET': return '#38BDF8';
      case 'AMPLITUDE_GROWTH': return C.red;
      default: return C.muted;
    }
  };

  const handleTouch = (locationX: number) => {
    const chartW = width - xPad - 8;
    const relX = Math.max(0, Math.min(chartW, locationX - xPad));
    const ratio = relX / chartW;
    const idx = Math.min(points.length - 1, Math.max(0, Math.round(ratio * (points.length - 1))));
    setTouchIdx(idx);
  };

  const activeIdx = touchIdx !== null ? touchIdx : points.length - 1;
  const active = points[activeIdx] || points[0];

  const agreeCount = points.filter((p) => p.agree).length;
  const agreePct = ((agreeCount / points.length) * 100).toFixed(0);

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <Text style={styles.cardTitle}>ĐỐI CHIẾU DỰ ĐOÁN THEO THỜI GIAN</Text>
        <Text
          style={[
            styles.cardBadge,
            { color: +agreePct >= 90 ? C.green : C.amber },
          ]}
        >
          {agreePct}% ĐỒNG THUẬN ({agreeCount}/{points.length})
        </Text>
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
          <Rect x={0} y={0} width={width} height={height} fill="#FFFFFF" stroke={C.borderSubtle} strokeWidth={1} rx={6} />

          {/* Row Guide lines */}
          <Line x1={xPad} y1={yPad + 12} x2={width - 8} y2={yPad + 12} stroke={C.borderSubtle} strokeWidth={1} />
          <Line x1={xPad} y1={yPad + 42} x2={width - 8} y2={yPad + 42} stroke={C.borderSubtle} strokeWidth={1} />
          <Line x1={xPad} y1={yPad + 72} x2={width - 8} y2={yPad + 72} stroke={C.borderSubtle} strokeWidth={1} />

          {/* Row Labels */}
          <SvgText x={xPad - 4} y={yPad + 15} textAnchor="end" fill={C.cyan} fontSize={8} fontWeight="bold">
            RF
          </SvgText>
          <SvgText x={xPad - 4} y={yPad + 45} textAnchor="end" fill={C.amber} fontSize={8} fontWeight="bold">
            B-B
          </SvgText>
          <SvgText x={xPad - 4} y={yPad + 75} textAnchor="end" fill={C.text} fontSize={8} fontWeight="bold">
            Match
          </SvgText>

          {/* Stream Points */}
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
                    height={85}
                    fill="#E0F2FE"
                    opacity={0.6}
                    rx={2}
                  />
                )}
                {/* RF Point */}
                <Circle cx={x} cy={yPad + 12} r={isHover ? 4.5 : 3} fill={classColor(p.rf)} stroke="#FFFFFF" strokeWidth={1} />
                {/* Baseline B Point */}
                <Circle cx={x} cy={yPad + 42} r={isHover ? 4.5 : 3} fill={classColor(p.baseline)} stroke="#FFFFFF" strokeWidth={1} />
                {/* Concordance marker */}
                <Circle cx={x} cy={yPad + 72} r={isHover ? 4 : 2.6} fill={p.agree ? C.green : C.amber} />
                {!p.agree && (
                  <Line
                    x1={x}
                    y1={yPad + 12}
                    x2={x}
                    y2={yPad + 72}
                    stroke={C.amber}
                    strokeWidth={1}
                    strokeDasharray="2 2"
                  />
                )}
              </G>
            );
          })}
        </Svg>

        {/* Readout tag */}
        <View style={styles.readoutRow}>
          <Text style={styles.readoutLabel}>Mẫu #{active.seq} (T+{active.t_sim_s}s):</Text>
          <Text style={[styles.readoutTag, { color: classColor(active.rf) }]}>RF: {active.rf}</Text>
          <Text style={[styles.readoutTag, { color: classColor(active.baseline) }]}>B: {active.baseline}</Text>
          <Text style={[styles.readoutStatus, { color: active.agree ? C.green : C.amber }]}>
            {active.agree ? '✓ AGREE' : '⚠ DISAGREE'}
          </Text>
        </View>
      </View>

      {scenario === 'S0b' && (
        <View style={styles.callout}>
          <Text style={styles.calloutText}>
            Kịch bản S0b: Gió giật làm Baseline B kích hoạt nhãn HIGH_ROLL, trong khi RF nhận diện chuyển động tự hồi phục góc nghiêng nên giữ nhãn NORMAL.
          </Text>
        </View>
      )}
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
    marginBottom: 8,
    paddingBottom: 6,
    borderBottomWidth: 1,
    borderBottomColor: C.borderSubtle,
  },
  cardTitle: {
    color: C.text,
    fontSize: 10.5,
    fontWeight: '800',
    fontFamily: 'monospace',
  },
  cardBadge: {
    fontSize: 9,
    fontFamily: 'monospace',
    fontWeight: '700',
    backgroundColor: '#F0FDF4',
    borderWidth: 0.5,
    borderColor: '#BBF7D0',
    borderRadius: 3,
    paddingHorizontal: 4,
    paddingVertical: 1,
  },
  touchArea: {
    position: 'relative',
    width: '100%',
    alignItems: 'center',
  },
  readoutRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginTop: 6,
    width: '100%',
    justifyContent: 'space-between',
  },
  readoutLabel: {
    color: C.muted,
    fontSize: 9,
    fontFamily: 'monospace',
  },
  readoutTag: {
    fontSize: 9,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  readoutStatus: {
    fontSize: 9,
    fontWeight: '800',
    fontFamily: 'monospace',
  },
  callout: {
    backgroundColor: '#FFFBEB',
    borderWidth: 1,
    borderColor: C.amber,
    borderRadius: 4,
    padding: 6,
    marginTop: 8,
  },
  calloutText: {
    color: '#92400E',
    fontSize: 9,
    lineHeight: 13,
  },
});

