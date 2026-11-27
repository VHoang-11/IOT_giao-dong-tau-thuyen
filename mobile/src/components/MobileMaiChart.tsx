import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';
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
  height = 150,
  onSelectAlarm,
  offline = false,
}: MobileMaiChartProps) {
  const { colors } = useTheme();
  const { width: windowWidth } = useWindowDimensions();
  const width = Math.max(260, Math.min(windowWidth - 64, 460));
  const xPad = 30;
  const yPad = 12;

  const [touchIdx, setTouchIdx] = useState<number | null>(null);

  const points = useMemo(() => {
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
      <View
        style={[
          styles.emptyContainer,
          { height, backgroundColor: colors.errorContainerBg, borderColor: colors.red },
        ]}
      >
        <Text style={[styles.emptyTitle, { color: colors.red }]}>
          Không có tín hiệu viễn trắc MAI
        </Text>
        <Text style={[styles.emptySubtitle, { color: colors.textSecondary }]}>
          Thiết bị ngoại tuyến hoặc lỗi cảm biến I2C
        </Text>
      </View>
    );
  }

  const scaleY = (v: number) => yPad + (height - yPad * 2) * (1 - v / 100);
  const scaleX = (i: number) => xPad + (i / Math.max(1, points.length - 1)) * (width - xPad - 10);

  const polyPoints = points.map((p, i) => `${scaleX(i).toFixed(1)},${scaleY(p.mai).toFixed(1)}`).join(' ');
  const areaPoints = `${scaleX(0)},${scaleY(0)} ${polyPoints} ${scaleX(points.length - 1)},${scaleY(0)}`;

  const handleTouch = (locationX: number) => {
    const chartW = width - xPad - 10;
    const relX = Math.max(0, Math.min(chartW, locationX - xPad));
    const ratio = relX / Math.max(1, chartW);
    const idx = Math.min(points.length - 1, Math.max(0, Math.round(ratio * (points.length - 1))));
    setTouchIdx(idx);
  };

  const activeIdx = touchIdx !== null ? touchIdx : points.length - 1;
  const activePoint = points[activeIdx] || points[0];
  const activeColor =
    activePoint.mai >= thresholdCritical
      ? colors.red
      : activePoint.mai >= thresholdCaution
      ? colors.amber
      : colors.green;

  return (
    <View style={styles.wrapper}>
      <View
        style={[
          styles.readoutBar,
          { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
        ]}
      >
        <Text style={[styles.readoutMeta, { color: colors.textSecondary }]}>
          Mốc T+{activePoint.t_sim_s}s
        </Text>
        <Text style={[styles.readoutVal, { color: activeColor }]}>
          Chỉ số MAI: {activePoint.mai} / 100
        </Text>
        {activePoint.alarm_id && (
          <Pressable
            onPress={() => onSelectAlarm?.(activePoint.alarm_id!)}
            style={[
              styles.alarmChip,
              {
                borderColor: activePoint.alarm_level === 'CRITICAL' ? colors.red : colors.amber,
                backgroundColor: colors.panel,
              },
            ]}
          >
            <Text
              style={[
                styles.alarmChipText,
                { color: activePoint.alarm_level === 'CRITICAL' ? colors.red : colors.amber },
              ]}
            >
              {activePoint.alarm_id} ›
            </Text>
          </Pressable>
        )}
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

          {/* Threshold Zone Tints */}
          <Rect
            x={xPad}
            y={scaleY(100)}
            width={width - xPad - 10}
            height={scaleY(thresholdCritical) - scaleY(100)}
            fill={colors.errorContainerBg}
            opacity={0.7}
          />
          <Rect
            x={xPad}
            y={scaleY(thresholdCritical)}
            width={width - xPad - 10}
            height={scaleY(thresholdCaution) - scaleY(thresholdCritical)}
            fill={colors.warningContainerBg}
            opacity={0.7}
          />
          <Rect
            x={xPad}
            y={scaleY(thresholdCaution)}
            width={width - xPad - 10}
            height={scaleY(0) - scaleY(thresholdCaution)}
            fill={colors.greenContainerBg}
            opacity={0.7}
          />

          {/* Threshold Lines */}
          <Line
            x1={xPad}
            y1={scaleY(thresholdCritical)}
            x2={width - 10}
            y2={scaleY(thresholdCritical)}
            stroke={colors.red}
            strokeDasharray="3 3"
            strokeWidth={1.1}
          />
          <Line
            x1={xPad}
            y1={scaleY(thresholdCaution)}
            x2={width - 10}
            y2={scaleY(thresholdCaution)}
            stroke={colors.amber}
            strokeDasharray="3 3"
            strokeWidth={1.1}
          />

          {/* Y Axis Grid */}
          {[0, 35, 70, 100].map((v) => (
            <G key={v}>
              <Line
                x1={xPad}
                y1={scaleY(v)}
                x2={width - 10}
                y2={scaleY(v)}
                stroke={colors.border}
                strokeWidth={0.8}
              />
              <SvgText x={xPad - 5} y={scaleY(v) + 3} textAnchor="end" fill={colors.textSecondary} fontSize={8.5}>
                {v}
              </SvgText>
            </G>
          ))}

          {/* Area & MAI Polyline */}
          <Polygon points={areaPoints} fill={colors.cyanContainerBg} opacity={0.55} />
          <Polyline points={polyPoints} fill="none" stroke={colors.title} strokeWidth={2.2} />

          {/* Alarm Markers */}
          {points.map((p, i) => {
            if (!p.alarm_id) return null;
            const x = scaleX(i);
            const y = scaleY(p.mai);
            const col = p.alarm_level === 'CRITICAL' ? colors.red : colors.amber;
            return (
              <G key={p.alarm_id + i}>
                <Line x1={x} y1={yPad} x2={x} y2={height - yPad} stroke={col} strokeWidth={1} strokeDasharray="2 2" />
                <Circle cx={x} cy={y} r={4} fill={col} stroke={colors.panel} strokeWidth={1.5} />
              </G>
            );
          })}

          {/* Scrub Marker */}
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
              cy={scaleY(activePoint.mai)}
              r={4.2}
              fill={activeColor}
              stroke={colors.panel}
              strokeWidth={1.5}
            />
          </G>
        </Svg>
      </View>

      {/* Vietnamese Legend */}
      <View style={styles.legendRow}>
        <View style={styles.legendGroup}>
          <View style={[styles.legendDot, { backgroundColor: colors.green }]} />
          <Text style={[styles.legendText, { color: colors.textSecondary }]}>&lt; 35 Bình thường</Text>
          <View style={[styles.legendDot, { backgroundColor: colors.amber, marginLeft: 10 }]} />
          <Text style={[styles.legendText, { color: colors.textSecondary }]}>35–70 Cảnh giác</Text>
          <View style={[styles.legendDot, { backgroundColor: colors.red, marginLeft: 10 }]} />
          <Text style={[styles.legendText, { color: colors.textSecondary }]}>≥ 70 Nguy cấp</Text>
        </View>
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
  alarmChip: {
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  alarmChipText: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  touchArea: {
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
    marginTop: 2,
  },
  legendGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 4,
  },
  legendDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  legendText: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
});
