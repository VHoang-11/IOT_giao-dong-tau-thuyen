import React, { useState } from 'react';
import { useWindowDimensions, View, Text, StyleSheet } from 'react-native';
import Svg, { Line, Polyline, Polygon, Rect, Circle, Text as SvgText, G } from 'react-native-svg';
import { C } from '../theme';

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
  height = 175,
  offline = false,
  warningDeg = 15.0,
  tripDeg = 22.0,
  onTouchSample,
}: MotionChartProps) {
  const { width: windowWidth } = useWindowDimensions();
  // Safe bounded width for 360dp - 430dp mobile screens
  const width = Math.max(260, Math.min(windowWidth - 48, 420));
  const xPad = 32;
  const yPad = 14;

  const [touchIdx, setTouchIdx] = useState<number | null>(null);

  if (offline || roll.length === 0) {
    return (
      <View style={[styles.emptyContainer, { height }]}>
        <Text style={styles.emptyTitle}>NO LIVE TELEMETRY</Text>
        <Text style={styles.emptySubtitle}>
          OFFLINE / SENSOR FAULT — không suy diễn trạng thái NORMAL
        </Text>
      </View>
    );
  }

  const combined = [...roll, ...pitch];
  const maxAbs = Math.max(24, ...combined.map(Math.abs)) * 1.1;

  const scaleY = (v: number) => {
    return yPad + (height - yPad * 2) * (0.5 - v / (2 * maxAbs));
  };

  const scaleX = (i: number) => {
    return xPad + (i / Math.max(1, roll.length - 1)) * (width - xPad - 8);
  };

  const rollPointsStr = roll
    .map((v, i) => `${scaleX(i).toFixed(1)},${scaleY(v).toFixed(1)}`)
    .join(' ');

  const pitchPointsStr = pitch
    .map((v, i) => `${scaleX(i).toFixed(1)},${scaleY(v).toFixed(1)}`)
    .join(' ');

  const zeroY = scaleY(0);
  const areaPolygonPoints = `${scaleX(0)},${zeroY} ${rollPointsStr} ${scaleX(roll.length - 1)},${zeroY}`;

  // Find peak roll in current window
  let peakIdx = 0;
  let peakRoll = roll[0] || 0;
  for (let i = 1; i < roll.length; i++) {
    if (Math.abs(roll[i]) > Math.abs(peakRoll)) {
      peakRoll = roll[i];
      peakIdx = i;
    }
  }

  // Handle touch scrub
  const handleTouch = (locationX: number) => {
    const chartW = width - xPad - 8;
    const relX = Math.max(0, Math.min(chartW, locationX - xPad));
    const ratio = relX / chartW;
    const idx = Math.min(roll.length - 1, Math.max(0, Math.round(ratio * (roll.length - 1))));
    setTouchIdx(idx);
    if (onTouchSample) {
      onTouchSample({ roll: roll[idx], pitch: pitch[idx] || 0, idx });
    }
  };

  const handleTouchEnd = () => {
    setTouchIdx(null);
    if (onTouchSample) {
      onTouchSample(null);
    }
  };

  const activeIdx = touchIdx !== null ? touchIdx : roll.length - 1;
  const activeRoll = roll[activeIdx] ?? 0;
  const activePitch = pitch[activeIdx] ?? 0;

  return (
    <View style={styles.wrapper}>
      {/* Reticle Chart Viewport with Touch Scrubbing */}
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
          {/* Light Maritime Reticle Background */}
          <Rect
            x={0}
            y={0}
            width={width}
            height={height}
            fill="#FFFFFF"
            stroke={C.borderSubtle}
            strokeWidth={1}
            rx={6}
          />

          {/* Horizontal Reticle Grid Lines with Degree Labels */}
          {[-20, -10, 0, 10, 20].map((deg) => {
            const y = scaleY(deg);
            const isZero = deg === 0;
            return (
              <G key={deg}>
                <Line
                  x1={xPad}
                  y1={y}
                  x2={width - 8}
                  y2={y}
                  stroke={isZero ? C.border : C.borderSubtle}
                  strokeDasharray={isZero ? undefined : '2 4'}
                  strokeWidth={isZero ? 1.2 : 0.8}
                />
                <SvgText
                  x={xPad - 4}
                  y={y + 3}
                  textAnchor="end"
                  fill={isZero ? C.text : C.muted}
                  fontSize={8}
                  fontWeight={isZero ? 'bold' : 'normal'}
                >
                  {deg > 0 ? `+${deg}°` : `${deg}°`}
                </SvgText>
              </G>
            );
          })}

          {/* Warning Threshold Boundary (+15° & -15°) */}
          {warningDeg <= maxAbs && (
            <>
              <Line
                x1={xPad}
                y1={scaleY(warningDeg)}
                x2={width - 8}
                y2={scaleY(warningDeg)}
                stroke={C.amber}
                strokeDasharray="4 3"
                strokeWidth={1.1}
                opacity={0.8}
              />
              <Line
                x1={xPad}
                y1={scaleY(-warningDeg)}
                x2={width - 8}
                y2={scaleY(-warningDeg)}
                stroke={C.amber}
                strokeDasharray="4 3"
                strokeWidth={1.1}
                opacity={0.8}
              />
            </>
          )}

          {/* Trip Threshold Boundary (+22° & -22°) */}
          {tripDeg <= maxAbs && (
            <>
              <Line
                x1={xPad}
                y1={scaleY(tripDeg)}
                x2={width - 8}
                y2={scaleY(tripDeg)}
                stroke={C.red}
                strokeDasharray="4 3"
                strokeWidth={1.2}
                opacity={0.85}
              />
              <Line
                x1={xPad}
                y1={scaleY(-tripDeg)}
                x2={width - 8}
                y2={scaleY(-tripDeg)}
                stroke={C.red}
                strokeDasharray="4 3"
                strokeWidth={1.2}
                opacity={0.85}
              />
            </>
          )}

          {/* Roll Waveform Area Fill (Subtle cyan glow) */}
          <Polygon
            points={areaPolygonPoints}
            fill="rgba(2, 132, 199, 0.08)"
          />

          {/* Pitch Polyline (Amber - Lower amplitude) */}
          <Polyline
            points={pitchPointsStr}
            fill="none"
            stroke={C.amber}
            strokeWidth={1.8}
            opacity={0.85}
          />

          {/* Roll Polyline (Cyan - Prominent) */}
          <Polyline
            points={rollPointsStr}
            fill="none"
            stroke={C.cyan}
            strokeWidth={2.4}
          />

          {/* Peak Roll Marker Highlight */}
          {Math.abs(peakRoll) >= warningDeg && (
            <G>
              <Circle
                cx={scaleX(peakIdx)}
                cy={scaleY(peakRoll)}
                r={4}
                fill={Math.abs(peakRoll) >= tripDeg ? C.red : C.amber}
                stroke="#FFFFFF"
                strokeWidth={1.5}
              />
              <Line
                x1={scaleX(peakIdx)}
                y1={scaleY(peakRoll)}
                x2={scaleX(peakIdx)}
                y2={zeroY}
                stroke={Math.abs(peakRoll) >= tripDeg ? C.red : C.amber}
                strokeWidth={1}
                strokeDasharray="2 2"
              />
            </G>
          )}

          {/* Interactive Scrub Needle & Value Dots */}
          <G>
            <Line
              x1={scaleX(activeIdx)}
              y1={yPad}
              x2={scaleX(activeIdx)}
              y2={height - yPad}
              stroke={touchIdx !== null ? C.border : C.cyan}
              strokeDasharray={touchIdx !== null ? '3 3' : undefined}
              strokeWidth={touchIdx !== null ? 1.5 : 1.2}
            />
            <Circle
              cx={scaleX(activeIdx)}
              cy={scaleY(activeRoll)}
              r={4.5}
              fill={C.cyan}
              stroke="#FFFFFF"
              strokeWidth={1.5}
            />
            <Circle
              cx={scaleX(activeIdx)}
              cy={scaleY(activePitch)}
              r={3.8}
              fill={C.amber}
              stroke="#FFFFFF"
              strokeWidth={1.2}
            />
          </G>
        </Svg>

        {/* Floating HUD Scrub/Live Badge */}
        <View style={styles.floatingHud}>
          <Text style={styles.hudLabel}>
            {touchIdx !== null ? 'SCRUB:' : 'HEAD:'}
          </Text>
          <Text style={[styles.hudVal, { color: C.cyan }]}>
            Roll {activeRoll > 0 ? `+${activeRoll.toFixed(1)}` : activeRoll.toFixed(1)}°
          </Text>
          <Text style={[styles.hudVal, { color: C.amber }]}>
            Pitch {activePitch > 0 ? `+${activePitch.toFixed(1)}` : activePitch.toFixed(1)}°
          </Text>
          {Math.abs(peakRoll) >= warningDeg && (
            <View style={styles.hudPeakPill}>
              <Text style={styles.hudPeakText}>
                PEAK {Math.abs(peakRoll).toFixed(1)}°
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* Legend & Instructions Footer */}
      <View style={styles.legend}>
        <View style={styles.legendItem}>
          <View style={[styles.dot, { backgroundColor: C.cyan }]} />
          <Text style={styles.legendText}>
            Roll: <Text style={styles.legendVal}>{activeRoll > 0 ? `+${activeRoll.toFixed(1)}` : activeRoll.toFixed(1)}°</Text>
          </Text>
        </View>
        <View style={styles.legendItem}>
          <View style={[styles.dot, { backgroundColor: C.amber }]} />
          <Text style={styles.legendText}>
            Pitch: <Text style={styles.legendVal}>{activePitch > 0 ? `+${activePitch.toFixed(1)}` : activePitch.toFixed(1)}°</Text>
          </Text>
        </View>
        <Text style={styles.legendHint}>Chạm/kéo để soi mẫu</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    alignItems: 'center',
    width: '100%',
  },
  chartTouchArea: {
    position: 'relative',
    width: '100%',
    alignItems: 'center',
  },
  emptyContainer: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1.5,
    borderColor: C.red,
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 16,
    width: '100%',
  },
  emptyTitle: {
    color: C.red,
    fontSize: 13,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  emptySubtitle: {
    color: C.muted,
    fontSize: 11,
    marginTop: 4,
    textAlign: 'center',
    lineHeight: 16,
  },
  floatingHud: {
    position: 'absolute',
    top: 6,
    right: 10,
    backgroundColor: 'rgba(255, 255, 255, 0.94)',
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 5,
    paddingHorizontal: 7,
    paddingVertical: 3,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    elevation: 2,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 2,
  },
  hudLabel: {
    fontSize: 9,
    fontWeight: '800',
    color: C.muted,
  },
  hudVal: {
    fontSize: 9.5,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  hudPeakPill: {
    backgroundColor: '#FEE2E2',
    borderWidth: 0.5,
    borderColor: C.red,
    borderRadius: 3,
    paddingHorizontal: 4,
    paddingVertical: 1,
  },
  hudPeakText: {
    color: C.red,
    fontSize: 8.5,
    fontWeight: '800',
    fontFamily: 'monospace',
  },
  legend: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    width: '100%',
    paddingHorizontal: 6,
    marginTop: 6,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  legendText: {
    color: C.muted,
    fontSize: 10,
    fontWeight: '600',
  },
  legendVal: {
    color: C.text,
    fontWeight: '700',
    fontFamily: 'monospace',
  },
  legendHint: {
    color: C.muted,
    fontSize: 9,
    fontStyle: 'italic',
  },
});
