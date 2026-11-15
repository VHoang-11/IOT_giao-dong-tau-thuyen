import React, { useState } from 'react';
import { useWindowDimensions, View, Text, StyleSheet } from 'react-native';
import Svg, { Line, Polyline, Polygon, Rect, Circle, Text as SvgText, G } from 'react-native-svg';
import { C } from '../theme';
import { Alarm } from '../types/domain';

interface MobileMaiChartProps {
  currentMai?: number;
  alarms?: Alarm[];
  thresholdCaution?: number;
  thresholdCritical?: number;
  height?: number;
  onSelectAlarm?: (alarmId: string) => void;
  offline?: boolean;
}

export function MobileMaiChart({
  currentMai = 14,
  alarms = [],
  thresholdCaution = 35,
  thresholdCritical = 70,
  height = 140,
  onSelectAlarm,
  offline = false,
}: MobileMaiChartProps) {
  const { width: windowWidth } = useWindowDimensions();
  const width = Math.max(260, Math.min(windowWidth - 48, 420));
  const xPad = 28;
  const yPad = 12;

  const [touchIdx, setTouchIdx] = useState<number | null>(null);

  // Generate 30 sequential MAI points
  const points = React.useMemo(() => {
    return Array.from({ length: 30 }, (_, i) => {
      const t = i * 5;
      const progress = i / 29;
      const baseVar = Math.sin(i * 0.2) * 8 + Math.cos(i * 0.4) * 4;
      const val = Math.max(0, Math.min(100, Math.round(currentMai * progress + (1 - progress) * 20 + baseVar)));
      const hasAlarm = (i === 8 || i === 18 || i === 25) && alarms.length > 0;
      const alm = hasAlarm ? alarms[i % alarms.length] : undefined;
      return { t_sim_s: t, mai: val, alarm_id: alm?.id, alarm_level: alm?.level };
    });
  }, [currentMai, alarms]);

  if (offline) {
    return (
      <View style={[styles.emptyContainer, { height }]}>
        <Text style={styles.emptyTitle}>NO MAI TELEMETRY</Text>
        <Text style={styles.emptySubtitle}>Thiết bị ngoại tuyến hoặc lỗi cảm biến I2C</Text>
      </View>
    );
  }

  const scaleY = (v: number) => {
    return yPad + (height - yPad * 2) * (1 - v / 100);
  };

  const scaleX = (i: number) => {
    return xPad + (i / Math.max(1, points.length - 1)) * (width - xPad - 8);
  };

  const polyPoints = points.map((p, i) => `${scaleX(i).toFixed(1)},${scaleY(p.mai).toFixed(1)}`).join(' ');
  const areaPoints = `${scaleX(0)},${scaleY(0)} ${polyPoints} ${scaleX(points.length - 1)},${scaleY(0)}`;

  const handleTouch = (locationX: number) => {
    const chartW = width - xPad - 8;
    const relX = Math.max(0, Math.min(chartW, locationX - xPad));
    const ratio = relX / chartW;
    const idx = Math.min(points.length - 1, Math.max(0, Math.round(ratio * (points.length - 1))));
    setTouchIdx(idx);
  };

  const activeIdx = touchIdx !== null ? touchIdx : points.length - 1;
  const activePoint = points[activeIdx] || points[0];

  return (
    <View style={styles.wrapper}>
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

          {/* Zones */}
          {/* Critical zone: 70..100 */}
          <Rect
            x={xPad}
            y={scaleY(100)}
            width={width - xPad - 8}
            height={scaleY(thresholdCritical) - scaleY(100)}
            fill="#FEF2F2"
            opacity={0.6}
          />
          {/* Caution zone: 35..70 */}
          <Rect
            x={xPad}
            y={scaleY(thresholdCritical)}
            width={width - xPad - 8}
            height={scaleY(thresholdCaution) - scaleY(thresholdCritical)}
            fill="#FFFBEB"
            opacity={0.6}
          />
          {/* Normal zone: 0..35 */}
          <Rect
            x={xPad}
            y={scaleY(thresholdCaution)}
            width={width - xPad - 8}
            height={scaleY(0) - scaleY(thresholdCaution)}
            fill="#F0FDF4"
            opacity={0.6}
          />

          {/* Threshold Lines */}
          <Line
            x1={xPad}
            y1={scaleY(thresholdCritical)}
            x2={width - 8}
            y2={scaleY(thresholdCritical)}
            stroke={C.red}
            strokeDasharray="3 3"
            strokeWidth={1}
          />
          <Line
            x1={xPad}
            y1={scaleY(thresholdCaution)}
            x2={width - 8}
            y2={scaleY(thresholdCaution)}
            stroke={C.amber}
            strokeDasharray="3 3"
            strokeWidth={1}
          />

          {/* Y Axis Grid & Labels */}
          {[0, 35, 70, 100].map((v) => (
            <G key={v}>
              <Line x1={xPad} y1={scaleY(v)} x2={width - 8} y2={scaleY(v)} stroke={C.borderSubtle} strokeWidth={0.8} />
              <SvgText x={xPad - 4} y={scaleY(v) + 3} textAnchor="end" fill={C.muted} fontSize={8}>
                {v}
              </SvgText>
            </G>
          ))}

          {/* Area fill */}
          <Polygon points={areaPoints} fill="rgba(16, 185, 129, 0.12)" />

          {/* MAI Polyline */}
          <Polyline points={polyPoints} fill="none" stroke={C.text} strokeWidth={2.2} />

          {/* Alarm Event Markers */}
          {points.map((p, i) => {
            if (!p.alarm_id) return null;
            const x = scaleX(i);
            const y = scaleY(p.mai);
            const col = p.alarm_level === 'CRITICAL' ? C.red : C.amber;
            return (
              <G key={p.alarm_id + i}>
                <Circle cx={x} cy={y} r={4.5} fill={col} stroke="#FFFFFF" strokeWidth={1.5} />
                <Line x1={x} y1={yPad} x2={x} y2={height - yPad} stroke={col} strokeWidth={1} strokeDasharray="2 2" />
              </G>
            );
          })}

          {/* Scrub Needle */}
          <G>
            <Line
              x1={scaleX(activeIdx)}
              y1={yPad}
              x2={scaleX(activeIdx)}
              y2={height - yPad}
              stroke={C.cyan}
              strokeWidth={1.2}
              strokeDasharray="2 2"
            />
            <Circle
              cx={scaleX(activeIdx)}
              cy={scaleY(activePoint.mai)}
              r={4}
              fill={activePoint.mai >= thresholdCritical ? C.red : activePoint.mai >= thresholdCaution ? C.amber : C.green}
              stroke="#FFFFFF"
              strokeWidth={1.5}
            />
          </G>
        </Svg>

        {/* Floating Readout */}
        <View style={styles.floatingHud}>
          <Text style={styles.hudLabel}>MAI:</Text>
          <Text
            style={[
              styles.hudVal,
              {
                color: activePoint.mai >= thresholdCritical ? C.red : activePoint.mai >= thresholdCaution ? C.amber : C.green,
              },
            ]}
          >
            {activePoint.mai} / 100
          </Text>
          {activePoint.alarm_id && (
            <View style={[styles.hudAlarmPill, { borderColor: activePoint.alarm_level === 'CRITICAL' ? C.red : C.amber }]}>
              <Text
                style={[
                  styles.hudAlarmText,
                  { color: activePoint.alarm_level === 'CRITICAL' ? C.red : C.amber },
                ]}
                onPress={() => onSelectAlarm && onSelectAlarm(activePoint.alarm_id!)}
              >
                {activePoint.alarm_id}
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* Legend */}
      <View style={styles.legend}>
        <View style={styles.legendRow}>
          <View style={[styles.legendDot, { backgroundColor: C.green }]} />
          <Text style={styles.legendText}>&lt; 35 Safe</Text>
          <View style={[styles.legendDot, { backgroundColor: C.amber, marginLeft: 8 }]} />
          <Text style={styles.legendText}>35-70 Caution</Text>
          <View style={[styles.legendDot, { backgroundColor: C.red, marginLeft: 8 }]} />
          <Text style={styles.legendText}>&ge; 70 Critical</Text>
        </View>
        <Text style={styles.legendHint}>Chạm để xem mốc cảnh báo</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    width: '100%',
    alignItems: 'center',
    marginBottom: 8,
  },
  touchArea: {
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
    fontSize: 12,
    fontWeight: '800',
  },
  emptySubtitle: {
    color: C.muted,
    fontSize: 10,
    marginTop: 3,
  },
  floatingHud: {
    position: 'absolute',
    top: 6,
    right: 10,
    backgroundColor: 'rgba(255, 255, 255, 0.94)',
    borderWidth: 1,
    borderColor: C.border,
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  hudLabel: {
    fontSize: 9,
    fontWeight: '800',
    color: C.muted,
  },
  hudVal: {
    fontSize: 10,
    fontWeight: '800',
    fontFamily: 'monospace',
  },
  hudAlarmPill: {
    borderWidth: 0.5,
    borderRadius: 3,
    paddingHorizontal: 4,
    paddingVertical: 1,
    backgroundColor: '#FFF1F2',
  },
  hudAlarmText: {
    fontSize: 8.5,
    fontWeight: '800',
    fontFamily: 'monospace',
  },
  legend: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    width: '100%',
    paddingHorizontal: 4,
    marginTop: 4,
  },
  legendRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  legendDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  legendText: {
    color: C.muted,
    fontSize: 9,
    marginLeft: 3,
  },
  legendHint: {
    color: C.muted,
    fontSize: 9,
    fontStyle: 'italic',
  },
});

