import React, { useEffect, useRef, useState } from 'react';
import {
  Animated,
  Easing,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import Svg, {
  Circle,
  Defs,
  Ellipse,
  G,
  Line,
  LinearGradient,
  Path,
  Polygon,
  Rect,
  Stop,
  Text as SvgText,
} from 'react-native-svg';
import { FONT, SHADOWS, useTheme } from '../theme';
import { AlarmLevel, Scenario } from '../types/domain';
import { getAlarmLevelNameVi, getRFClassNameVi } from '../i18n/vi';

const AnimatedG = Animated.createAnimatedComponent(G);

export interface InclinometerProps {
  rollDeg: number | null;
  pitchDeg?: number | null;
  mai?: number | null;
  alarmLevel?: AlarmLevel;
  scenario?: Scenario;
  classRf?: string;
  sourceMode?: 'SIMULATION' | 'SENSOR';
  sensorOk?: boolean;
  compact?: boolean;
  warningDeg?: number;
  tripDeg?: number;
  touchedSample?: { roll: number; pitch: number; idx: number } | null;
}

export function Inclinometer({
  rollDeg,
  pitchDeg = 0,
  mai = 0,
  alarmLevel = 'NORMAL',
  scenario = 'S0',
  classRf = 'NORMAL',
  sensorOk = true,
  compact = false,
  warningDeg = 15.0,
  tripDeg = 22.0,
  touchedSample = null,
}: InclinometerProps) {
  const { colors, reducedMotion } = useTheme();
  const [activeTab, setActiveTab] = useState<'iso' | 'front' | 'side'>('iso');
  const { width: windowWidth } = useWindowDimensions();

  const stageW = 460;
  const stageH = compact ? 210 : 250;
  const displayWidth = Math.max(260, Math.min(windowWidth - 64, 460));
  const displayHeight = Math.round((displayWidth / stageW) * stageH);

  // Subtle horizontal ocean wave drift (fixed relative to horizon, stops when reducedMotion or offline)
  const waveShift = useRef(new Animated.Value(0)).current;

  const isOffline = scenario === 'OFFLINE' || scenario === 'UNKNOWN';
  const isSensorFault = scenario === 'SENSOR_FAULT' || sensorOk === false;
  const isAvailable = !isOffline && !isSensorFault && rollDeg !== null;

  useEffect(() => {
    if (reducedMotion || !isAvailable) {
      waveShift.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(waveShift, {
          toValue: 14,
          duration: 3600,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: false,
        }),
        Animated.timing(waveShift, {
          toValue: -14,
          duration: 3600,
          easing: Easing.inOut(Easing.sin),
          useNativeDriver: false,
        }),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [reducedMotion, isAvailable, waveShift]);

  const validRoll = isAvailable ? (touchedSample ? touchedSample.roll : rollDeg ?? 0) : 0;
  const validPitch = isAvailable ? (touchedSample ? touchedSample.pitch : pitchDeg ?? 0) : 0;
  const validMai = isAvailable ? (mai ?? 0) : 0;

  const clampedRoll = Math.max(-30, Math.min(30, validRoll));
  const clampedPitch = Math.max(-15, Math.min(15, validPitch));
  const needleAngle = activeTab === 'side' ? clampedPitch : clampedRoll;

  const severityColor = !isAvailable
    ? colors.muted
    : alarmLevel === 'CRITICAL'
    ? colors.red
    : alarmLevel === 'WARNING' || alarmLevel === 'CAUTION'
    ? colors.amber
    : colors.green;

  const portStbd =
    validRoll < -0.1 ? 'Mạn trái' : validRoll > 0.1 ? 'Mạn phải' : 'Cân bằng';
  const bowStern =
    validPitch > 0.1 ? 'Ngóc mũi' : validPitch < -0.1 ? 'Chúi mũi' : 'Mức chuẩn';

  const maiPct = Math.min(100, Math.max(0, validMai));
  const maiColor = maiPct >= 70 ? colors.red : maiPct >= 35 ? colors.amber : colors.green;

  const cx = stageW / 2; // 230
  const horizonY = compact ? 105 : 122;

  return (
    <View
      style={[
        styles.container,
        { backgroundColor: colors.panel, borderColor: colors.border },
        SHADOWS.card,
        compact && styles.containerCompact,
      ]}
    >
      {/* Header & View Switcher */}
      <View style={[styles.header, { borderBottomColor: colors.borderSubtle }]}>
        <View style={styles.titleRow}>
          <Text style={[styles.headerTitle, { color: colors.title }]}>
            Mô hình chuyển động tàu
          </Text>
          <View style={[styles.simPill, { backgroundColor: colors.cyanContainerBg }]}>
            <Text style={[styles.simPillText, { color: colors.tech }]}>
              {isAvailable ? getRFClassNameVi(classRf) : getAlarmLevelNameVi(alarmLevel)}
            </Text>
          </View>
        </View>

        <View
          style={[
            styles.tabGroup,
            { backgroundColor: colors.panel2, borderColor: colors.borderSubtle },
          ]}
        >
          {(
            [
              { id: 'iso', label: 'Phối cảnh' },
              { id: 'front', label: 'Cắt ngang' },
              { id: 'side', label: 'Cắt dọc' },
            ] as const
          ).map((tab) => {
            const active = activeTab === tab.id;
            return (
              <Pressable
                key={tab.id}
                onPress={() => setActiveTab(tab.id)}
                style={[
                  styles.tabBtn,
                  active && { backgroundColor: colors.primaryContainer },
                ]}
                accessibilityRole="button"
              >
                <Text
                  style={[
                    styles.tabBtnText,
                    { color: active ? '#FFFFFF' : colors.textSecondary },
                  ]}
                >
                  {tab.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      {/* Main SVG Visualization Canvas */}
      <View
        style={[
          styles.svgWrapper,
          { borderColor: colors.borderSubtle, backgroundColor: colors.oceanSkyTop },
        ]}
      >
        <Svg
          width={displayWidth}
          height={displayHeight}
          viewBox={`0 0 ${stageW} ${stageH}`}
        >
          <Defs>
            <LinearGradient id="mobSkyGrad" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={colors.oceanSkyTop} />
              <Stop offset="1" stopColor={colors.oceanSkyBottom} />
            </LinearGradient>
            <LinearGradient id="mobSeaGrad" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor={colors.oceanSeaTop} stopOpacity="0.82" />
              <Stop offset="0.35" stopColor={colors.oceanSeaMid} stopOpacity="0.9" />
              <Stop offset="1" stopColor={colors.oceanSeaDeep} stopOpacity="0.98" />
            </LinearGradient>
            <LinearGradient id="mobHullGrad" x1="0" y1="0" x2="1" y2="0.8">
              <Stop offset="0" stopColor="#1E293B" />
              <Stop offset="0.55" stopColor="#0F172A" />
              <Stop offset="1" stopColor="#090D16" />
            </LinearGradient>
            <LinearGradient id="mobBootTopGrad" x1="0" y1="0" x2="1" y2="0.5">
              <Stop offset="0" stopColor="#DC2626" />
              <Stop offset="1" stopColor="#7F1D1D" />
            </LinearGradient>
            <LinearGradient id="mobDeckGrad" x1="0" y1="0" x2="1" y2="1">
              <Stop offset="0" stopColor="#475569" />
              <Stop offset="1" stopColor="#334155" />
            </LinearGradient>
          </Defs>

          {/* Sky & Sea Fixed Backdrop (Never rotates with ship) */}
          <Rect x={0} y={0} width={stageW} height={horizonY} fill="url(#mobSkyGrad)" />
          <Rect x={0} y={horizonY} width={stageW} height={stageH - horizonY} fill="url(#mobSeaGrad)" />

          {/* Fixed Horizon Reference Datum Line */}
          <Line
            x1={0}
            y1={horizonY}
            x2={stageW}
            y2={horizonY}
            stroke={colors.oceanHorizonLine}
            strokeWidth={1.2}
            strokeDasharray="6 3"
            opacity={0.78}
          />
          <SvgText
            x={10}
            y={horizonY - 5}
            fill={colors.oceanHorizonLine}
            fontSize={8.5}
            fontWeight="600"
          >
            Đường chân trời • Mực nước chuẩn 0°
          </SvgText>

          {/* Distant Ambient Ocean Waves (Moving gently on horizontal datum) */}
          <AnimatedG translateX={waveShift}>
            <Path
              d={`M -30 ${horizonY + 12} Q 35 ${horizonY + 9} 100 ${horizonY + 13} T 230 ${horizonY + 12} T 360 ${horizonY + 13} T ${stageW + 40} ${horizonY + 12}`}
              fill="none"
              stroke={colors.oceanWaveSubtle}
              strokeWidth={1.1}
              opacity={0.65}
            />
            <Path
              d={`M -30 ${horizonY + 28} Q 45 ${horizonY + 24} 120 ${horizonY + 29} T 260 ${horizonY + 28} T 400 ${horizonY + 29} T ${stageW + 40} ${horizonY + 28}`}
              fill="none"
              stroke={colors.oceanWaveLight}
              strokeWidth={1.2}
              opacity={0.55}
            />
          </AnimatedG>

          {/* Overhead Inclinometer Gauge Arc */}
          <G transform={`translate(${cx - 230}, 0)`}>
            <Path
              d="M 150 58 A 105 105 0 0 1 310 58"
              fill="none"
              stroke={colors.borderSubtle}
              strokeWidth={2.5}
            />
            {/* Safe Zone */}
            <Path
              d="M 185 40 A 105 105 0 0 1 275 40"
              fill="none"
              stroke={colors.green}
              strokeWidth={3}
              opacity={0.85}
            />
            {/* Caution Sectors */}
            <Path
              d="M 166 49 A 105 105 0 0 1 185 40"
              fill="none"
              stroke={colors.amber}
              strokeWidth={3}
            />
            <Path
              d="M 275 40 A 105 105 0 0 1 294 49"
              fill="none"
              stroke={colors.amber}
              strokeWidth={3}
            />
            {/* Critical Sectors */}
            <Path
              d="M 150 58 A 105 105 0 0 1 166 49"
              fill="none"
              stroke={colors.red}
              strokeWidth={3}
            />
            <Path
              d="M 294 49 A 105 105 0 0 1 310 58"
              fill="none"
              stroke={colors.red}
              strokeWidth={3}
            />

            <Line x1={230} y1={27} x2={230} y2={35} stroke={colors.title} strokeWidth={1.6} />
            <SvgText x={230} y={22} fill={colors.title} fontSize={9} fontWeight="700" textAnchor="middle">
              0°
            </SvgText>
            <SvgText x={178} y={33} fill={colors.textSecondary} fontSize={8} textAnchor="middle">
              -{activeTab === 'side' ? 8 : Math.round(warningDeg)}°
            </SvgText>
            <SvgText x={282} y={33} fill={colors.textSecondary} fontSize={8} textAnchor="middle">
              +{activeTab === 'side' ? 8 : Math.round(warningDeg)}°
            </SvgText>

            {/* Needle */}
            <G transform={`rotate(${needleAngle}, 230, 130)`}>
              <Line x1={230} y1={32} x2={230} y2={54} stroke={severityColor} strokeWidth={2.2} />
              <Polygon points="230,29 226.5,36 233.5,36" fill={severityColor} />
            </G>
          </G>

          {/* VIEW 1: ISOMETRIC CONTAINER VESSEL */}
          {activeTab === 'iso' && (
            <G transform={`translate(${cx - 270}, ${horizonY - 160})`}>
              {/* Underwater Reflection */}
              <G
                transform={`rotate(${-clampedRoll * 0.6}, 270, 180)`}
                opacity={colors.oceanReflectionOpacity}
              >
                <Path
                  d="M 125 162 L 380 190 C 415 194 432 188 438 182 C 425 208 385 224 345 218 L 135 186 Z"
                  fill="#0369A1"
                />
              </G>

              {/* Stern Wake Lines */}
              <AnimatedG translateX={waveShift} opacity={0.75}>
                <Ellipse cx={88} cy={173} rx={22} ry={5.5} fill={colors.oceanWaveSubtle} />
                <Path
                  d="M 105 169 C 75 166 45 167 16 168"
                  fill="none"
                  stroke={colors.oceanWaveLight}
                  strokeWidth={1.4}
                />
                <Path
                  d="M 112 177 C 82 183 52 191 22 198"
                  fill="none"
                  stroke={colors.oceanWaveLight}
                  strokeWidth={1.6}
                />
              </AnimatedG>

              {/* Dynamic Vessel Model (Rotates by Roll, shifts gently by Pitch) */}
              <G
                transform={`rotate(${clampedRoll}, 270, 160) translate(${(clampedPitch * 0.7).toFixed(1)}, ${(clampedPitch * 0.4).toFixed(1)})`}
                opacity={isAvailable ? 1 : 0.35}
              >
                <G transform="translate(270, 160) scale(1.12) translate(-270, -160)">
                  {/* Lower Hull Boot-Top */}
                  <Path
                    d="M 125 158 L 380 188 C 415 192 432 186 438 180 C 428 196 405 204 375 202 L 135 174 L 125 158 Z"
                    fill="url(#mobBootTopGrad)"
                    stroke="#7F1D1D"
                    strokeWidth={1}
                  />
                  <Ellipse cx={434} cy={184} rx={7} ry={4} fill="#B91C1C" stroke="#7F1D1D" strokeWidth={1} />

                  {/* Hull Topsides */}
                  <Path
                    d="M 120 142 L 375 172 C 408 176 430 178 440 174 L 438 180 C 415 192 380 188 125 158 L 115 146 Z"
                    fill="url(#mobHullGrad)"
                    stroke="#0F172A"
                    strokeWidth={1.2}
                  />

                  {/* Waterline Glow Stripe */}
                  <Path
                    d="M 125 158 L 380 188 C 412 192 430 186 438 180"
                    fill="none"
                    stroke="#38BDF8"
                    strokeWidth={1.5}
                    opacity={0.9}
                  />

                  {/* Main Deck Plane */}
                  <Path
                    d="M 120 142 L 155 128 L 410 158 C 428 163 438 170 440 174 C 430 178 408 176 375 172 Z"
                    fill="url(#mobDeckGrad)"
                    stroke="#1E293B"
                    strokeWidth={1}
                  />

                  {/* Container Stacks (3-faceted Isometric blocks) */}
                  {/* Bay 4 */}
                  <Polygon points="170,147 195,150 195,136 170,133" fill="#1E3A8A" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="195,150 215,143 215,129 195,136" fill="#2563A6" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="170,133 195,136 215,129 190,126" fill="#60A5FA" stroke="#0F172A" strokeWidth={0.7} />

                  <Polygon points="170,133 195,136 195,122 170,119" fill="#991B1B" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="195,136 215,129 215,115 195,122" fill="#DC2626" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="170,119 195,122 215,115 190,112" fill="#F87171" stroke="#0F172A" strokeWidth={0.7} />

                  {/* Bay 3 */}
                  <Polygon points="220,153 248,156 248,142 220,139" fill="#B45309" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="248,156 268,149 268,135 248,142" fill="#D97706" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="220,139 248,142 268,135 240,132" fill="#FBBF24" stroke="#0F172A" strokeWidth={0.7} />

                  <Polygon points="220,139 248,142 248,128 220,125" fill="#0369A1" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="248,142 268,135 268,121 248,128" fill="#2563A6" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="220,125 248,128 268,121 240,118" fill="#38BDF8" stroke="#0F172A" strokeWidth={0.7} />

                  <Polygon points="220,125 248,128 248,114 220,111" fill="#047857" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="248,128 268,121 268,107 248,114" fill="#00966A" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="220,111 248,114 268,107 240,104" fill="#34D399" stroke="#0F172A" strokeWidth={0.7} />

                  {/* Bay 2 */}
                  <Polygon points="274,159 304,162 304,148 274,145" fill="#047857" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="304,162 324,155 324,141 304,148" fill="#00966A" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="274,145 304,148 324,141 294,138" fill="#6EE7B7" stroke="#0F172A" strokeWidth={0.7} />

                  <Polygon points="274,145 304,148 304,134 274,131" fill="#991B1B" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="304,148 324,141 324,127 304,134" fill="#DC2626" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="274,131 304,134 324,127 294,124" fill="#FCA5A5" stroke="#0F172A" strokeWidth={0.7} />

                  {/* Bay 1 */}
                  <Polygon points="330,165 358,168 358,154 330,151" fill="#0369A1" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="358,168 376,162 376,148 358,154" fill="#2563A6" stroke="#0F172A" strokeWidth={0.7} />
                  <Polygon points="330,151 358,154 376,148 348,145" fill="#7DD3FC" stroke="#0F172A" strokeWidth={0.7} />

                  {/* Aft Superstructure Bridge */}
                  <Polygon points="126,143 154,146 154,116 126,113" fill="#E2E8F0" stroke="#0F172A" strokeWidth={0.9} />
                  <Polygon points="154,146 166,141 166,111 154,116" fill="#CBD5E1" stroke="#0F172A" strokeWidth={0.9} />
                  <Polygon points="126,113 154,116 166,111 138,108" fill="#F8FAFC" stroke="#0F172A" strokeWidth={0.9} />
                  <Polygon points="130,113 152,115 152,98 130,96" fill="#F1F5F9" stroke="#0F172A" strokeWidth={0.9} />
                  <Polygon points="152,115 163,111 163,94 152,98" fill="#E2E8F0" stroke="#0F172A" strokeWidth={0.9} />
                  <Polygon points="130,96 152,98 163,94 141,92" fill="#FFFFFF" stroke="#0F172A" strokeWidth={0.9} />
                  <Polygon points="132,106 150,108 150,101 132,99" fill="#38BDF8" />
                  <Polygon points="150,108 160,104 160,97 150,101" fill="#0284C7" />
                  <Line x1={145} y1={92} x2={145} y2={68} stroke="#1E293B" strokeWidth={1.8} />
                  <Line x1={138} y1={76} x2={152} y2={76} stroke="#1E293B" strokeWidth={1.4} />
                  <Circle cx={145} cy={67} r={2.5} fill={severityColor} />
                  <Polygon points="125,112 133,113 133,90 125,89" fill="#DC2626" stroke="#0F172A" strokeWidth={0.7} />

                  {/* M and G Markers */}
                  <Circle cx={270} cy={100} r={3} fill="#38BDF8" stroke="#FFFFFF" strokeWidth={1} />
                  <SvgText x={276} y={103} fill="#38BDF8" fontSize={8} fontWeight="700">M</SvgText>
                  <Circle cx={270} cy={130} r={3} fill="#D97706" stroke="#FFFFFF" strokeWidth={1} />
                  <SvgText x={276} y={133} fill="#FBBF24" fontSize={8} fontWeight="700">G</SvgText>
                </G>
              </G>

              {/* Waterline Contact Ripple */}
              <Path
                d="M 105 174 C 185 188 310 197 420 196 C 455 196 475 190 484 184"
                fill="none"
                stroke={colors.oceanWaveLight}
                strokeWidth={1.7}
                opacity={0.9}
              />
            </G>
          )}

          {/* VIEW 2: FRONT CROSS SECTION (ROLL) */}
          {activeTab === 'front' && (
            <G transform={`translate(${cx - 270}, ${horizonY - 160})`}>
              <G transform={`rotate(${clampedRoll}, 270, 160)`} opacity={isAvailable ? 1 : 0.35}>
                <Line x1={270} y1={55} x2={270} y2={206} stroke="#38BDF8" strokeDasharray="3 3" strokeWidth={1} opacity={0.6} />
                <Path
                  d="M 185 122 L 355 122 L 340 182 C 330 202 295 208 270 208 C 245 208 210 202 200 182 Z"
                  fill="url(#mobHullGrad)"
                  stroke="#0F172A"
                  strokeWidth={2}
                />
                <Path
                  d="M 206 182 L 334 182 C 325 202 295 208 270 208 C 245 208 215 202 206 182 Z"
                  fill="url(#mobBootTopGrad)"
                />
                <Line x1={185} y1={122} x2={355} y2={122} stroke="#38BDF8" strokeWidth={1.5} />
                <Rect x={235} y={84} width={70} height={38} fill="#F8FAFC" stroke="#0F172A" strokeWidth={1.4} rx={3} />
                <Rect x={242} y={91} width={56} height={9} fill="#38BDF8" rx={2} />
                <Line x1={270} y1={84} x2={270} y2={58} stroke="#1E293B" strokeWidth={2.2} />
                <Circle cx={270} cy={56} r={3.5} fill={severityColor} />
                <Rect x={198} y={104} width={32} height={18} fill="#DC2626" stroke="#0F172A" strokeWidth={0.9} rx={1} />
                <Rect x={310} y={104} width={32} height={18} fill="#2563A6" stroke="#0F172A" strokeWidth={0.9} rx={1} />
                <Rect x={200} y={86} width={28} height={18} fill="#00966A" stroke="#0F172A" strokeWidth={0.9} rx={1} />
                <Rect x={312} y={86} width={28} height={18} fill="#D97706" stroke="#0F172A" strokeWidth={0.9} rx={1} />
                <Circle cx={270} cy={112} r={3.2} fill="#38BDF8" stroke="#FFFFFF" strokeWidth={1.2} />
                <SvgText x={277} y={115} fill="#38BDF8" fontSize={8} fontWeight="700">M</SvgText>
                <Circle cx={270} cy={148} r={3.2} fill="#D97706" stroke="#FFFFFF" strokeWidth={1.2} />
                <SvgText x={277} y={151} fill="#FBBF24" fontSize={8} fontWeight="700">G</SvgText>
              </G>
            </G>
          )}

          {/* VIEW 3: SIDE PROFILE (PITCH) */}
          {activeTab === 'side' && (
            <G transform={`translate(${cx - 270}, ${horizonY - 160})`}>
              <G transform={`rotate(${clampedPitch}, 270, 160)`} opacity={isAvailable ? 1 : 0.35}>
                <Path
                  d="M 110 138 L 395 138 C 418 142 435 152 448 160 C 435 178 415 186 385 186 L 128 186 L 110 166 Z"
                  fill="url(#mobHullGrad)"
                  stroke="#0F172A"
                  strokeWidth={2}
                />
                <Circle cx={444} cy={162} r={5.5} fill="#B91C1C" stroke="#7F1D1D" strokeWidth={1} />
                <Rect x={225} y={108} width={44} height={30} fill="#DC2626" stroke="#0F172A" strokeWidth={0.9} />
                <Rect x={225} y={78} width={44} height={30} fill="#2563A6" stroke="#0F172A" strokeWidth={0.9} />
                <Rect x={274} y={108} width={44} height={30} fill="#00966A" stroke="#0F172A" strokeWidth={0.9} />
                <Rect x={274} y={78} width={44} height={30} fill="#D97706" stroke="#0F172A" strokeWidth={0.9} />
                <Rect x={324} y={114} width={44} height={24} fill="#38BDF8" stroke="#0F172A" strokeWidth={0.9} />
                <Rect x={132} y={78} width={56} height={60} fill="#F8FAFC" stroke="#0F172A" strokeWidth={1.4} rx={3} />
                <Rect x={140} y={86} width={40} height={8} fill="#38BDF8" rx={2} />
                <Path d="M 146 78 L 152 60 L 164 60 L 164 78 Z" fill="#DC2626" stroke="#0F172A" strokeWidth={0.9} />
                <Line x1={405} y1={138} x2={405} y2={110} stroke="#1E293B" strokeWidth={2.2} />
                <Circle cx={405} cy={107} r={3.2} fill="#38BDF8" />
                <SvgText x={115} y={198} fill="#E2E8F0" fontSize={8.5} fontWeight="700">Lái (Đuôi)</SvgText>
                <SvgText x={410} y={198} fill="#E2E8F0" fontSize={8.5} fontWeight="700">Mũi tàu</SvgText>
              </G>
            </G>
          )}

          {/* Offline / Sensor Fault Overlay */}
          {!isAvailable && (
            <G>
              <Rect
                x={55}
                y={horizonY - 38}
                width={stageW - 110}
                height={72}
                rx={10}
                fill={colors.panel}
                stroke={severityColor}
                strokeWidth={1.5}
              />
              <SvgText
                x={stageW / 2}
                y={horizonY - 8}
                fill={severityColor}
                fontSize={12.5}
                fontWeight="700"
                textAnchor="middle"
              >
                {isOffline ? 'Mất kết nối thiết bị' : 'Lỗi cảm biến I2C MPU6050'}
              </SvgText>
              <SvgText
                x={stageW / 2}
                y={horizonY + 14}
                fill={colors.textSecondary}
                fontSize={9.5}
                textAnchor="middle"
              >
                Không suy diễn góc nghiêng khi thiếu tín hiệu đo
              </SvgText>
            </G>
          )}
        </Svg>
      </View>

      {/* Bottom Clean Telemetry Strip (Matching Web Split Bar / Semantic Colors) */}
      <View style={[styles.footerRow, { borderTopColor: colors.borderSubtle }]}>
        <View style={styles.footerItem}>
          <Text style={[styles.footerLabel, { color: colors.textSecondary }]}>Góc lắc ngang</Text>
          <Text
            style={[
              styles.footerValue,
              {
                color: !isAvailable
                  ? colors.muted
                  : Math.abs(validRoll) >= tripDeg
                  ? colors.red
                  : Math.abs(validRoll) >= warningDeg
                  ? colors.amber
                  : colors.tech,
              },
            ]}
          >
            {isAvailable ? `${validRoll > 0 ? '+' : ''}${validRoll.toFixed(1)}° (${portStbd})` : '—'}
          </Text>
        </View>

        <View style={styles.footerItem}>
          <Text style={[styles.footerLabel, { color: colors.textSecondary }]}>Góc chúi dọc</Text>
          <Text
            style={[
              styles.footerValue,
              { color: !isAvailable ? colors.muted : colors.amber },
            ]}
          >
            {isAvailable ? `${validPitch > 0 ? '+' : ''}${validPitch.toFixed(1)}° (${bowStern})` : '—'}
          </Text>
        </View>

        <View style={styles.footerItem}>
          <Text style={[styles.footerLabel, { color: colors.textSecondary }]}>MAI</Text>
          <Text style={[styles.footerValue, { color: isAvailable ? maiColor : colors.muted }]}>
            {isAvailable ? `${maiPct} / 100` : '—'}
          </Text>
        </View>
      </View>

      <Text style={[styles.disclaimerCaption, { color: colors.textSecondary }]}>
        {touchedSample
          ? `Đang xem mẫu lịch sử #${touchedSample.idx + 1} • Hình minh họa động học 2D/Isometric`
          : `Kịch bản ${scenario} • Hình minh họa động học 2D/Isometric đồng bộ dữ liệu`}
      </Text>
    </View>
  );
}

export const ShipMotionVisualizer = Inclinometer;

const styles = StyleSheet.create({
  container: {
    borderWidth: 1,
    borderRadius: 12,
    padding: 14,
    width: '100%',
    gap: 10,
  },
  containerCompact: {
    padding: 12,
    gap: 8,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    paddingBottom: 8,
    flexWrap: 'wrap',
    gap: 8,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  headerTitle: {
    fontSize: 17,
    fontFamily: FONT.bold,
    fontWeight: '700',
  },
  simPill: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 999,
  },
  simPillText: {
    fontSize: 12,
    fontFamily: FONT.medium,
    fontWeight: '500',
  },
  tabGroup: {
    flexDirection: 'row',
    gap: 4,
    borderRadius: 10,
    padding: 3,
    borderWidth: 1,
  },
  tabBtn: {
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 7,
    minHeight: 34,
    justifyContent: 'center',
  },
  tabBtnText: {
    fontSize: 12,
    fontFamily: FONT.semibold,
    fontWeight: '600',
  },
  svgWrapper: {
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
    borderRadius: 10,
    overflow: 'hidden',
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    flexWrap: 'wrap',
    gap: 10,
    paddingTop: 8,
    borderTopWidth: 1,
  },
  footerItem: {
    minWidth: 90,
    gap: 2,
  },
  footerLabel: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
  footerValue: {
    fontSize: 14,
    fontFamily: FONT.semibold,
    fontWeight: '600',
    fontVariant: ['tabular-nums'],
  },
  disclaimerCaption: {
    fontSize: 12,
    fontFamily: FONT.regular,
  },
});
