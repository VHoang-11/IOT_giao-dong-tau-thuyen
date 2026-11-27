import React, { useState } from 'react';
import { View, Text, StyleSheet, Pressable, useWindowDimensions } from 'react-native';
import Svg, { Path, Line, Circle, Rect, Text as SvgText, G } from 'react-native-svg';
import { C, SHADOWS } from '../theme';
import { AlarmLevel, Scenario } from '../types/domain';

export interface InclinometerProps {
  rollDeg: number | null;
  pitchDeg?: number | null;
  mai?: number | null;
  alarmLevel?: AlarmLevel;
  scenario?: Scenario;
  /** LIVE: nhãn nguồn dữ liệu thật (SENSOR/SIMULATION) thay cho nhãn DEMO và tên kịch bản. */
  sourceLabel?: string;
  classRf?: string;
  sourceMode?: 'SIMULATION' | 'SENSOR';
  sensorOk?: boolean;
  compact?: boolean;
}

export function Inclinometer({
  rollDeg,
  pitchDeg = 0,
  mai = 0,
  alarmLevel = 'NORMAL',
  scenario = 'S0',
  sourceLabel,
  classRf = 'NORMAL',
  sourceMode = 'SIMULATION',
  sensorOk = true,
  compact = false,
}: InclinometerProps) {
  const [activeTab, setActiveTab] = useState<'front' | 'side'>('front');
  const { width: windowWidth } = useWindowDimensions();
  const width = Math.min(windowWidth - 40, 380);
  const height = compact ? 140 : 190;

  const isOffline = scenario === 'OFFLINE';
  const isSensorFault = scenario === 'SENSOR_FAULT' || sensorOk === false;
  const isAvailable = !isOffline && !isSensorFault && rollDeg !== null;

  const validRoll = isAvailable ? rollDeg : 0;
  const validPitch = isAvailable && pitchDeg !== null ? pitchDeg : 0;
  const validMai = isAvailable ? (mai ?? 0) : 0;

  const clampedRoll = Math.max(-30, Math.min(30, validRoll));
  const clampedPitch = Math.max(-15, Math.min(15, validPitch));

  // Severity colors matching Maritime White & Navy
  const severityColor =
    !isAvailable
      ? C.muted
      : alarmLevel === 'CRITICAL'
      ? C.red
      : alarmLevel === 'WARNING'
      ? C.amber
      : alarmLevel === 'CAUTION'
      ? C.cyan
      : C.green;

  const portStbd =
    validRoll < -0.1 ? 'PORT (TRÁI)' : validRoll > 0.1 ? 'STBD (PHẢI)' : 'EVEN KEEL';
  const bowStern =
    validPitch > 0.1 ? 'BOW UP (NGÓC)' : validPitch < -0.1 ? 'BOW DOWN (CHÚI)' : 'LEVEL';

  const maiPct = Math.min(100, Math.max(0, validMai));
  const maiColor = maiPct >= 70 ? C.red : maiPct >= 35 ? C.amber : C.green;

  // Pivot points
  const cx = 170;
  const cy = 135;

  return (
    <View style={[styles.container, compact && styles.containerCompact]}>
      {/* Top Header Bar */}
      <View style={styles.header}>
        <View style={styles.titleRow}>
          <Text style={styles.headerTitle}>2D VESSEL DYNAMICS</Text>
          <View style={styles.demoBadge}>
            <Text style={styles.demoBadgeText}>{sourceLabel ?? 'DEMO / SIM'}</Text>
          </View>
        </View>

        {/* View Switcher Tabs */}
        <View style={styles.tabGroup}>
          <Pressable
            onPress={() => setActiveTab('front')}
            style={[styles.tabBtn, activeTab === 'front' && styles.tabBtnActive]}
            accessibilityRole="button"
          >
            <Text
              style={[styles.tabBtnText, activeTab === 'front' && styles.tabBtnTextActive]}
            >
              FRONT (ROLL)
            </Text>
          </Pressable>
          <Pressable
            onPress={() => setActiveTab('side')}
            style={[styles.tabBtn, activeTab === 'side' && styles.tabBtnActive]}
            accessibilityRole="button"
          >
            <Text
              style={[styles.tabBtnText, activeTab === 'side' && styles.tabBtnTextActive]}
            >
              SIDE (PITCH)
            </Text>
          </Pressable>
        </View>
      </View>

      {/* Floating Telemetry HUD */}
      <View style={styles.hudRow}>
        <View style={styles.hudItem}>
          <Text style={styles.hudLabel}>ROLL:</Text>
          <Text
            style={[
              styles.hudVal,
              { color: Math.abs(validRoll) >= 15 ? C.red : Math.abs(validRoll) >= 10 ? C.amber : C.cyan },
            ]}
          >
            {isAvailable ? `${validRoll > 0 ? '+' : ''}${validRoll.toFixed(1)}°` : '—'}
          </Text>
          <Text style={styles.hudSub}>{isAvailable ? portStbd : 'DISCONNECTED'}</Text>
        </View>

        <View style={styles.hudItem}>
          <Text style={styles.hudLabel}>PITCH:</Text>
          <Text
            style={[
              styles.hudVal,
              { color: Math.abs(validPitch) >= 5 ? C.amber : C.text },
            ]}
          >
            {isAvailable ? `${validPitch > 0 ? '+' : ''}${validPitch.toFixed(1)}°` : '—'}
          </Text>
          <Text style={styles.hudSub}>{isAvailable ? bowStern : 'DISCONNECTED'}</Text>
        </View>

        <View
          style={[
            styles.severityPill,
            { borderColor: severityColor },
            isAvailable && alarmLevel === 'CRITICAL'
              ? SHADOWS.criticalGlow
              : isAvailable && alarmLevel === 'WARNING'
              ? SHADOWS.warningGlow
              : isAvailable && alarmLevel === 'CAUTION'
              ? SHADOWS.cautionGlow
              : undefined,
          ]}
        >
          <Text style={[styles.severityText, { color: severityColor }]}>
            {isAvailable ? alarmLevel : 'OFFLINE'}
          </Text>
        </View>
      </View>

      {/* SVG Canvas Area */}
      <View style={styles.svgWrapper}>
        <Svg width={width} height={height} viewBox="0 0 340 180">
          {/* Background Stage */}
          <Rect x={0} y={0} width={340} height={180} fill="#FFFFFF" rx={4} />

          {/* Guide Arc Grid (Roll Front View) */}
          {activeTab === 'front' && (
            <>
              {/* Base Arc */}
              <Path
                d="M 57.38 85 A 130 130 0 0 1 282.62 85"
                fill="none"
                stroke={C.borderSubtle}
                strokeDasharray="3 4"
                strokeWidth={2}
              />
              {/* Green Safe Zone ±10° */}
              <Path
                d="M 147.42 22 A 130 130 0 0 1 192.58 22"
                fill="none"
                stroke={C.green}
                strokeWidth={4}
              />
              {/* Port Amber Zone */}
              <Path
                d="M 129.83 26.65 A 130 130 0 0 1 147.42 22"
                fill="none"
                stroke={C.amber}
                strokeWidth={4}
              />
              {/* Stbd Amber Zone */}
              <Path
                d="M 192.58 22 A 130 130 0 0 1 210.17 26.65"
                fill="none"
                stroke={C.amber}
                strokeWidth={4}
              />
              {/* Port Red Zone */}
              <Path
                d="M 115.04 33.74 A 130 130 0 0 1 129.83 26.65"
                fill="none"
                stroke={C.red}
                strokeWidth={4}
              />
              {/* Stbd Red Zone */}
              <Path
                d="M 210.17 26.65 A 130 130 0 0 1 224.96 33.74"
                fill="none"
                stroke={C.red}
                strokeWidth={4}
              />

              {/* Ticks */}
              <Line x1={170} y1={14} x2={170} y2={28} stroke={C.border} strokeWidth={2} />
              <SvgText x={170} y={10} fill={C.border} fontSize="8" fontWeight="800" textAnchor="middle">
                0°
              </SvgText>
              <Line x1={147.4} y1={22} x2={149.5} y2={32} stroke={C.green} strokeWidth={1.5} />
              <SvgText x={143} y={16} fill={C.green} fontSize="7" fontWeight="bold" textAnchor="middle">
                -10°
              </SvgText>
              <Line x1={192.6} y1={22} x2={190.5} y2={32} stroke={C.green} strokeWidth={1.5} />
              <SvgText x={197} y={16} fill={C.green} fontSize="7" fontWeight="bold" textAnchor="middle">
                +10°
              </SvgText>
              <Line x1={125.5} y1={28.5} x2={129.5} y2={38} stroke={C.amber} strokeWidth={1.5} />
              <SvgText x={117} y={24} fill={C.amber} fontSize="7" fontWeight="bold" textAnchor="middle">
                -20°
              </SvgText>
              <Line x1={214.5} y1={28.5} x2={210.5} y2={38} stroke={C.amber} strokeWidth={1.5} />
              <SvgText x={223} y={24} fill={C.amber} fontSize="7" fontWeight="bold" textAnchor="middle">
                +20°
              </SvgText>
            </>
          )}

          {/* Waterline Datum Line */}
          <Line
            x1={15}
            y1={135}
            x2={325}
            y2={135}
            stroke="#0284C7"
            strokeDasharray="4 4"
            strokeWidth={1.5}
          />
          <SvgText x={315} y={131} fill="#0284C7" fontSize="8" fontWeight="bold">
            WL
          </SvgText>

          {/* FRONT VIEW: Cargo Vessel Cross-section rotating by clampedRoll */}
          {activeTab === 'front' && (
            <G transform={isAvailable ? `rotate(${clampedRoll} ${cx} ${cy})` : undefined}>
              {/* Vessel Main Hull */}
              <Path
                d="M 100 100 L 240 100 L 226 150 C 220 166 186 172 170 172 C 154 172 120 166 114 150 Z"
                fill="#102B49"
                stroke="#183E65"
                strokeWidth={2}
              />
              {/* Center Keel Line */}
              <Line
                x1={170}
                y1={75}
                x2={170}
                y2={172}
                stroke="#183E65"
                strokeDasharray="2 3"
                strokeWidth={1}
              />

              {/* Deck House & Bridge Accommodation */}
              <Rect x={138} y={75} width={64} height={25} fill="#FFFFFF" stroke="#183E65" strokeWidth={1.5} rx={1} />
              {/* Bridge Windows */}
              <Rect x={144} y={78} width={12} height={6} fill="#0284C7" />
              <Rect x={160} y={78} width={20} height={6} fill="#0284C7" />
              <Rect x={184} y={78} width={12} height={6} fill="#0284C7" />
              {/* Radar Mast */}
              <Line x1={170} y1={75} x2={170} y2={64} stroke="#183E65" strokeWidth={1.8} />
              <Line x1={164} y1={66} x2={176} y2={66} stroke="#183E65" strokeWidth={1.5} />

              {/* Stacked Cargo Containers */}
              {/* Bottom Tier: 3 containers */}
              <Rect x={108} y={88} width={26} height={12} fill="#DC2626" stroke="#183E65" strokeWidth={0.8} />
              <Rect x={206} y={88} width={26} height={12} fill="#0284C7" stroke="#183E65" strokeWidth={0.8} />
              {/* Top Tier: 2 containers */}
              <Rect x={110} y={76} width={24} height={12} fill="#D97706" stroke="#183E65" strokeWidth={0.8} />
              <Rect x={208} y={76} width={24} height={12} fill="#10B981" stroke="#183E65" strokeWidth={0.8} />

              {/* Metacenter Point (M) */}
              <Circle cx={170} cy={95} r={3} fill="#0284C7" stroke="#FFFFFF" strokeWidth={1} />
              <SvgText x={176} y={98} fill="#0284C7" fontSize="8" fontWeight="bold">
                M
              </SvgText>
              {/* Center of Gravity (G) */}
              <Circle cx={170} cy={122} r={3} fill="#D97706" stroke="#FFFFFF" strokeWidth={1} />
              <SvgText x={176} y={125} fill="#D97706" fontSize="8" fontWeight="bold">
                G
              </SvgText>
            </G>
          )}

          {/* SIDE VIEW: Cargo Vessel Profile rotating by clampedPitch */}
          {activeTab === 'side' && (
            <G transform={isAvailable ? `rotate(${clampedPitch} ${cx} ${cy})` : undefined}>
              {/* Waterline Wave Ripple */}
              <Path
                d="M 20 137 Q 35 133 50 137 T 80 137 T 110 137 T 140 137 T 170 137 T 200 137 T 230 137 T 260 137 T 290 137 T 320 137"
                fill="none"
                stroke="#0284C7"
                strokeWidth={1}
                opacity={0.5}
              />

              {/* Side Hull Profile: Stern (left) to Bulbous Bow (right) */}
              <Path
                d="M 45 106 L 275 106 C 285 106 295 116 298 126 C 302 138 290 148 275 152 L 70 152 C 55 152 45 142 42 128 Z"
                fill="#102B49"
                stroke="#183E65"
                strokeWidth={2}
              />
              {/* Bulbous Bow Silhouette Feature */}
              <Path
                d="M 292 135 C 304 135 304 145 292 147 Z"
                fill="#DC2626"
                stroke="#183E65"
                strokeWidth={1}
              />

              {/* Superstructure Bridge at Stern */}
              <Rect x={55} y={74} width={40} height={32} fill="#FFFFFF" stroke="#183E65" strokeWidth={1.5} rx={1} />
              <Rect x={60} y={78} width={30} height={6} fill="#0284C7" />
              {/* Funnel Exhaust Mast */}
              <Rect x={48} y={64} width={12} height={22} fill="#D97706" stroke="#183E65" strokeWidth={1} />
              <Rect x={48} y={64} width={12} height={6} fill="#183E65" />
              {/* Radar Antenna */}
              <Line x1={75} y1={74} x2={75} y2={62} stroke="#183E65" strokeWidth={1.5} />
              <Line x1={69} y1={65} x2={81} y2={65} stroke="#183E65" strokeWidth={1.5} />

              {/* Cargo Bay 1 Containers (Aft) */}
              <Rect x={105} y={92} width={45} height={14} fill="#0284C7" stroke="#183E65" strokeWidth={0.8} />
              <Rect x={108} y={78} width={40} height={14} fill="#DC2626" stroke="#183E65" strokeWidth={0.8} />

              {/* Cargo Bay 2 Containers (Midships) */}
              <Rect x={158} y={92} width={48} height={14} fill="#10B981" stroke="#183E65" strokeWidth={0.8} />
              <Rect x={160} y={78} width={44} height={14} fill="#D97706" stroke="#183E65" strokeWidth={0.8} />

              {/* Cargo Bay 3 Containers (Forward) */}
              <Rect x={214} y={92} width={45} height={14} fill="#153D64" stroke="#183E65" strokeWidth={0.8} />
              <Rect x={216} y={78} width={40} height={14} fill="#0284C7" stroke="#183E65" strokeWidth={0.8} />

              {/* Bow / Stern Directional Badges */}
              <SvgText x={50} y={166} fill={C.muted} fontSize="8" fontWeight="bold">
                STERN (ĐUÔI)
              </SvgText>
              <SvgText x={250} y={166} fill={C.muted} fontSize="8" fontWeight="bold">
                BOW (MŨI)
              </SvgText>
            </G>
          )}

          {/* Offline / Sensor Fault Overlay */}
          {!isAvailable && (
            <G>
              <Rect x={40} y={65} width={260} height={46} fill="rgba(254, 242, 242, 0.94)" stroke={C.red} strokeWidth={1.5} rx={5} />
              <SvgText x={170} y={84} fill={C.red} fontSize="11" fontWeight="800" textAnchor="middle">
                {isOffline ? 'OFFLINE — MẤT KẾT NỐI TELEMETRY' : 'SENSOR FAULT — LỖI CẢM BIẾN I2C'}
              </SvgText>
              <SvgText x={170} y={99} fill={C.textSecondary} fontSize="8" fontWeight="bold" textAnchor="middle">
                Dữ liệu góc nghiêng không khả dụng • Không suy diễn NORMAL
              </SvgText>
            </G>
          )}
        </Svg>
      </View>

      {/* Bottom Telemetry & Risk Meter */}
      <View style={styles.footerRow}>
        <View style={styles.maiTrackCol}>
          <View style={styles.maiHeader}>
            <Text style={styles.maiLabel}>MAI DYNAMICS:</Text>
            <Text style={[styles.maiScoreText, { color: maiColor }]}>
              {isAvailable ? `${maiPct.toFixed(0)}% (${(validMai / 100).toFixed(2)})` : '—'}
            </Text>
          </View>
          <View style={styles.maiTrack}>
            <View style={[styles.maiFill, { width: `${maiPct}%`, backgroundColor: maiColor }]} />
          </View>
        </View>

        <View style={styles.badgeCol}>
          <View style={styles.subPill}>
            <Text style={styles.subPillText}>{classRf}</Text>
          </View>
          {sourceLabel ? null : <Text style={styles.scenarioTag}>SCN: {scenario}</Text>}
        </View>
      </View>
    </View>
  );
}

// Backward-compatible alias
export const ShipMotionVisualizer = Inclinometer;

const styles = StyleSheet.create({
  container: {
    backgroundColor: C.bg,
    borderColor: C.borderSubtle,
    borderWidth: 1,
    borderLeftWidth: 3.5,
    borderLeftColor: C.borderNavy,
    borderRadius: 14,
    padding: 12,
    width: '100%',
    gap: 10,
    ...SHADOWS.card,
  },
  containerCompact: {
    padding: 8,
    gap: 6,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: C.borderSubtle,
    paddingBottom: 6,
    flexWrap: 'wrap',
    gap: 6,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  headerTitle: {
    color: C.text,
    fontSize: 11,
    fontWeight: '800',
    letterSpacing: 0.6,
  },
  demoBadge: {
    backgroundColor: C.primaryContainer,
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 20,
  },
  demoBadgeText: {
    color: '#FFFFFF',
    fontSize: 8,
    fontWeight: '800',
    letterSpacing: 0.4,
  },
  tabGroup: {
    flexDirection: 'row',
    gap: 4,
    backgroundColor: C.panel2,
    borderRadius: 10,
    padding: 3,
    borderWidth: 1,
    borderColor: C.borderSubtle,
  },
  tabBtn: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 8,
  },
  tabBtnActive: {
    backgroundColor: C.primaryContainer,
  },
  tabBtnText: {
    color: C.muted,
    fontSize: 9,
    fontWeight: '700',
  },
  tabBtnTextActive: {
    color: '#FFFFFF',
  },
  hudRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    backgroundColor: C.panel2,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 10,
    paddingHorizontal: 12,
    paddingVertical: 6,
  },
  hudItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  hudLabel: {
    color: C.muted,
    fontSize: 9,
    fontWeight: '700',
  },
  hudVal: {
    fontSize: 12,
    fontWeight: '800',
    fontVariant: ['tabular-nums'],
  },
  hudSub: {
    color: C.textSecondary,
    fontSize: 8,
    fontWeight: '600',
  },
  severityPill: {
    borderWidth: 1,
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 2,
    backgroundColor: '#FFFFFF',
  },
  severityText: {
    fontSize: 9,
    fontWeight: '900',
    letterSpacing: 0.4,
  },
  svgWrapper: {
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 10,
    overflow: 'hidden',
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
    paddingTop: 4,
    borderTopWidth: 1,
    borderTopColor: C.borderSubtle,
  },
  maiTrackCol: {
    flex: 1,
    gap: 3,
  },
  maiHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  maiLabel: {
    color: C.muted,
    fontSize: 9,
    fontWeight: '700',
  },
  maiScoreText: {
    fontSize: 9,
    fontWeight: '800',
    fontVariant: ['tabular-nums'],
  },
  maiTrack: {
    height: 6,
    backgroundColor: C.panel2,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    overflow: 'hidden',
  },
  maiFill: {
    height: '100%',
    borderRadius: 3,
  },
  badgeCol: {
    alignItems: 'flex-end',
    gap: 2,
  },
  subPill: {
    backgroundColor: C.panelHigh,
    borderWidth: 1,
    borderColor: C.borderSubtle,
    borderRadius: 20,
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  subPillText: {
    color: C.text,
    fontSize: 9,
    fontWeight: '700',
  },
  scenarioTag: {
    color: C.muted,
    fontSize: 8,
    fontWeight: '600',
  },
});
