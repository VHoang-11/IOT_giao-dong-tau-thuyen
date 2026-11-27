import React, { useState } from 'react';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import Svg, {
  Circle,
  G,
  Line,
  Polygon,
  Polyline,
  Rect,
  Text as SvgText,
} from 'react-native-svg';
import { FONT, useTheme } from '../theme';

interface MotionChartProps {
  roll: number[];
  pitch: number[];
  height?: number;
  offline?: boolean;
  warningDeg?: number;
  tripDeg?: number;
  onTouchSample?: (sample: { roll: number; pitch: number; idx: number } | null) => void;
}

export function MotionChart({
  roll,
  pitch,
  height = 185,
  offline = false,
  warningDeg = 15.0,
  tripDeg = 22.0,
  onTouchSample,
}: MotionChartProps) {
  const { colors } = useTheme();
  const { width: windowWidth } = useWindowDimensions();
  const width = Math.max(260, Math.min(windowWidth - 64, 460));
  const xPad = 36;
  const yPad = 14;

  const [touchIdx, setTouchIdx] = useState<number | null>(null);

  if (offline || roll.length === 0) {
    return (
      <View
        style={[
          styles.emptyContainer,
          { height, backgroundColor: colors.errorContainerBg, borderColor: colors.red },
        ]}
      >
        <Text style={[styles.emptyTitle, { color: colors.red }]}>Không có dữ liệu dao động</Text>
        <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
          Mất tín hiệu viễn trắc — Không hiển thị số đo giả định
        </Text>
      </View>
    );
  }

  const combined = [...roll, ...pitch];
  const maxAbs = Math.max(24, ...combined.map(Math.abs)) * 1.1;

  const scaleY = (v: number) => yPad + (height - yPad * 2) * (0.5 - v / (2 * maxAbs));
  const scaleX = (i: number) => xPad + (i / Math.max(1, roll.length - 1)) * (width - xPad - 10);

  const rollPointsStr = roll.map((v, i) => `${scaleX(i).toFixed(1)},${scaleY(v).toFixed(1)}`).join(' ');
  const pitchPointsStr = pitch.map((v, i) => `${scaleX(i).toFixed(1)},${scaleY(v).toFixed(1)}`).join(' ');
  const zeroY = scaleY(0);
  const areaPolygonPoints = `${scaleX(0)},${zeroY} ${rollPointsStr} ${scaleX(roll.length - 1)},${zeroY}`;

  let peakIdx = 0;
  let peakRoll = roll[0] || 0;
  for (let i = 1; i < roll.length; i++) {
    if (Math.abs(roll[i]) > Math.abs(peakRoll)) {
      peakRoll = roll[i];
      peakIdx = i;
    }
  }

  const handleTouch = (locationX: number) => {
    const chartW = width - xPad - 10;
    const relX = Math.max(0, Math.min(chartW, locationX - xPad));
    const ratio = relX / Math.max(1, chartW);
    const idx = Math.min(roll.length - 1, Math.max(0, Math.round(ratio * (roll.length - 1))));
    setTouchIdx(idx);
    onTouchSample?.({ roll: roll[idx], pitch: pitch[idx] || 0, idx });
  };

  const handleTouchEnd = () => {
    setTouchIdx(null);
    onTouchSample?.(null);
  };

  const activeIdx = touchIdx !== null ? touchIdx : roll.length - 1;
  const activeRoll = roll[activeIdx] ?? 0;
  const activePitch = pitch[activeIdx] ?? 0;

  return (
    <View style={styles.wrapper}>
      {/* Interactive Touch Scrub Readout Tooltip */}
      <View
        style={[
          styles.readoutBar,
          { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
        ]}
      >
        <Text style={[styles.readoutMeta, { color: colors.textSecondary }]}>
          {touchIdx !== null ? `Mẫu #${activeIdx + 1}` : 'Tức thời'}
        </Text>
        <Text style={[styles.readoutVal, { color: colors.tech }]}>
          Roll: {activeRoll > 0 ? '+' : ''}
          {activeRoll.toFixed(1)}° ({activeRoll > 0.1 ? 'Mạn phải' : activeRoll < -0.1 ? 'Mạn trái' : 'Cân bằng'})
        </Text>
        <Text style={[styles.readoutVal, { color: colors.amber }]}>
          Pitch: {activePitch > 0 ? '+' : ''}
          {activePitch.toFixed(1)}°
        </Text>
      </View>

      {/* SVG Oscilloscope */}
      <View
        style={styles.chartTouchArea}
        onStartShouldSetResponder={() => true}
        onMoveShouldSetResponder={() => true}
        onResponderGrant={(e) => handleTouch(e.nativeEvent.locationX)}
        onResponderMove={(e) => handleTouch(e.nativeEvent.locationX)}
        onResponderRelease={handleTouchEnd}
        onResponderTerminate={handleTouchEnd}
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

          {/* Horizontal Grid Lines */}
          {[-20, -10, 0, 10, 20].map((deg) => {
            const y = scaleY(deg);
            const isZero = deg === 0;
            return (
              <G key={deg}>
                <Line
                  x1={xPad}
                  y1={y}
                  x2={width - 10}
                  y2={y}
                  stroke={isZero ? colors.borderSubtle : colors.border}
                  strokeDasharray={isZero ? undefined : '3 5'}
                  strokeWidth={isZero ? 1.2 : 0.8}
                />
                <SvgText
                  x={xPad - 5}
                  y={y + 3}
                  textAnchor="end"
                  fill={isZero ? colors.title : colors.textSecondary}
                  fontSize={9}
                  fontWeight={isZero ? '700' : '400'}
                >
                  {deg > 0 ? `+${deg}°` : `${deg}°`}
                </SvgText>
              </G>
            );
          })}

          {/* Warning Thresholds */}
          {warningDeg <= maxAbs && (
            <>
              <Line
                x1={xPad}
                y1={scaleY(warningDeg)}
                x2={width - 10}
                y2={scaleY(warningDeg)}
                stroke={colors.amber}
                strokeDasharray="4 3"
                strokeWidth={1.1}
                opacity={0.8}
              />
              <Line
                x1={xPad}
                y1={scaleY(-warningDeg)}
                x2={width - 10}
                y2={scaleY(-warningDeg)}
                stroke={colors.amber}
                strokeDasharray="4 3"
                strokeWidth={1.1}
                opacity={0.8}
              />
            </>
          )}

          {/* Trip Thresholds */}
          {tripDeg <= maxAbs && (
            <>
              <Line
                x1={xPad}
                y1={scaleY(tripDeg)}
                x2={width - 10}
                y2={scaleY(tripDeg)}
                stroke={colors.red}
                strokeDasharray="4 3"
                strokeWidth={1.2}
                opacity={0.85}
              />
              <Line
                x1={xPad}
                y1={scaleY(-tripDeg)}
                x2={width - 10}
                y2={scaleY(-tripDeg)}
                stroke={colors.red}
                strokeDasharray="4 3"
                strokeWidth={1.2}
                opacity={0.85}
              />
            </>
          )}

          {/* Roll Area Fill */}
          <Polygon points={areaPolygonPoints} fill={colors.cyanContainerBg} opacity={0.75} />

          {/* Pitch Curve (Cam / Amber) */}
          <Polyline
            points={pitchPointsStr}
            fill="none"
            stroke={colors.amber}
            strokeWidth={1.9}
            opacity={0.9}
          />

          {/* Roll Curve (Xanh dương kỹ thuật) */}
          <Polyline points={rollPointsStr} fill="none" stroke={colors.tech} strokeWidth={2.4} />

          {/* Peak Roll Marker */}
          {Math.abs(peakRoll) >= warningDeg && (
            <G>
              <Circle
                cx={scaleX(peakIdx)}
                cy={scaleY(peakRoll)}
                r={4}
                fill={Math.abs(peakRoll) >= tripDeg ? colors.red : colors.amber}
                stroke={colors.panel}
                strokeWidth={1.5}
              />
            </G>
          )}

          {/* Touch Scrub Needle */}
          <G>
            <Line
              x1={scaleX(activeIdx)}
              y1={yPad}
              x2={scaleX(activeIdx)}
              y2={height - yPad}
              stroke={colors.tech}
              strokeWidth={1.2}
              strokeDasharray="2 2"
            />
            <Circle
              cx={scaleX(activeIdx)}
              cy={scaleY(activeRoll)}
              r={4}
              fill={colors.tech}
              stroke={colors.panel}
              strokeWidth={1.5}
            />
            <Circle
              cx={scaleX(activeIdx)}
              cy={scaleY(activePitch)}
              r={3.5}
              fill={colors.amber}
              stroke={colors.panel}
              strokeWidth={1.2}
            />
          </G>
        </Svg>
      </View>

      {/* Clean Vietnamese Legend */}
      <View style={styles.legendRow}>
        <View style={styles.legendGroup}>
          <View style={[styles.dot, { backgroundColor: colors.tech }]} />
          <Text style={[styles.legendText, { color: colors.title }]}>Roll (°)</Text>
          <View style={[styles.dot, { backgroundColor: colors.amber, marginLeft: 10 }]} />
          <Text style={[styles.legendText, { color: colors.title }]}>Pitch (°)</Text>
          <View style={[styles.dash, { borderColor: colors.amber, marginLeft: 10 }]} />
          <Text style={[styles.legendText, { color: colors.amber }]}>±{warningDeg}°</Text>
          <View style={[styles.dash, { borderColor: colors.red, marginLeft: 8 }]} />
          <Text style={[styles.legendText, { color: colors.red }]}>±{tripDeg}°</Text>
        </View>
        <Text style={[styles.hintText, { color: colors.textSecondary }]}>
          Chạm hoặc kéo trên biểu đồ để soi từng mẫu
        </Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    width: '100%',
    gap: 8,
  },
  readoutBar: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 8,
    borderWidth: 1,
  },
  readoutMeta: {
    fontSize: 12,
    fontFamily: FONT.medium,
  },
  readoutVal: {
    fontSize: 13,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  chartTouchArea: {
    width: '100%',
    alignItems: 'center',
  },
  emptyContainer: {
    borderWidth: 1,
    borderStyle: 'dashed',
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    gap: 4,
  },
  emptyTitle: {
    fontSize: 15,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  emptySubtitle: {
    fontSize: 13,
    fontFamily: FONT.regular,
    textAlign: 'center',
  },
  legendRow: {
    gap: 4,
  },
  legendGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 4,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  dash: {
    width: 12,
    height: 0,
    borderTopWidth: 1.5,
    borderStyle: 'dashed',
  },
  legendText: {
    fontSize: 12,
    fontFamily: FONT.medium,
  },
  hintText: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
});
