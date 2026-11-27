import React, { createContext, useContext, useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

/**
 * Smart Vessel Motion Guard — Unified Mobile Theme System
 * Đồng bộ hoàn toàn Color Tokens & Typography Tokens với Web (styles.css).
 * - Navy chính (Tiêu đề): #142D45
 * - Xanh dương kỹ thuật (Roll / Tech): #2563A6
 * - Xanh lá tích cực (Normal / Connected): #00966A
 * - Cam cảnh giác (Caution / Pitch): #D97706
 * - Đỏ nguy cấp (Critical): #DC2626
 * - Xám xanh chú thích (Secondary): #64748B
 * - Nền sáng (Canvas): #F0F4F8
 * - Nền card (Surface): #FFFFFF
 */

export type ThemeMode = 'light' | 'dark';

export interface ThemeColors {
  canvas: string;
  bg: string;
  panel: string;
  panel2: string;
  panelHigh: string;
  border: string;
  borderNavy: string;
  borderSubtle: string;
  borderFocus: string;
  title: string;
  text: string;
  textSecondary: string;
  muted: string;
  cyan: string;
  cyanBright: string;
  tech: string;
  primaryContainer: string;
  white: string;
  green: string;
  tertiary: string;
  amber: string;
  orange: string;
  red: string;
  disabled: string;
  errorContainer: string;
  errorContainerBg: string;
  warningContainerBg: string;
  cyanContainerBg: string;
  greenContainerBg: string;
  neutralContainerBg: string;
  oceanSkyTop: string;
  oceanSkyBottom: string;
  oceanHorizonLine: string;
  oceanSeaTop: string;
  oceanSeaMid: string;
  oceanSeaDeep: string;
  oceanWaveLight: string;
  oceanWaveSubtle: string;
  oceanReflectionOpacity: number;
}

export const LIGHT_THEME: ThemeColors = {
  canvas: '#F0F4F8',
  bg: '#FFFFFF',
  panel: '#FFFFFF',
  panel2: '#F8FAFC',
  panelHigh: '#F1F5F9',
  border: 'rgba(100, 116, 139, 0.16)',
  borderNavy: '#142D45',
  borderSubtle: '#E2E8F0',
  borderFocus: '#2563A6',
  title: '#142D45',
  text: '#142D45',
  textSecondary: '#64748B',
  muted: '#64748B',
  cyan: '#2563A6',
  cyanBright: '#1D4ED8',
  tech: '#2563A6',
  primaryContainer: '#2563A6',
  white: '#FFFFFF',
  green: '#00966A',
  tertiary: '#059669',
  amber: '#D97706',
  orange: '#D97706',
  red: '#DC2626',
  disabled: '#94A3B8',
  errorContainer: '#FEE2E2',
  errorContainerBg: '#FEF2F2',
  warningContainerBg: '#FFFBEB',
  cyanContainerBg: '#F0F7FF',
  greenContainerBg: '#ECFDF5',
  neutralContainerBg: '#F1F5F9',
  oceanSkyTop: '#F8FAFC',
  oceanSkyBottom: '#E0F2FE',
  oceanHorizonLine: '#0284C7',
  oceanSeaTop: '#38BDF8',
  oceanSeaMid: '#0284C7',
  oceanSeaDeep: '#0369A1',
  oceanWaveLight: 'rgba(255, 255, 255, 0.78)',
  oceanWaveSubtle: 'rgba(224, 242, 254, 0.55)',
  oceanReflectionOpacity: 0.16,
};

export const DARK_THEME: ThemeColors = {
  canvas: '#0A101D',
  bg: '#131E30',
  panel: '#131E30',
  panel2: '#16243A',
  panelHigh: '#1E2E48',
  border: 'rgba(226, 232, 240, 0.12)',
  borderNavy: '#38BDF8',
  borderSubtle: '#1E2E48',
  borderFocus: '#38BDF8',
  title: '#F1F5F9',
  text: '#F1F5F9',
  textSecondary: '#94A3B8',
  muted: '#94A3B8',
  cyan: '#38BDF8',
  cyanBright: '#7DD3FC',
  tech: '#38BDF8',
  primaryContainer: '#2563A6',
  white: '#FFFFFF',
  green: '#34D399',
  tertiary: '#10B981',
  amber: '#FBBF24',
  orange: '#F59E0B',
  red: '#F87171',
  disabled: '#64748B',
  errorContainer: '#7F1D1D',
  errorContainerBg: '#2D1217',
  warningContainerBg: '#271A0C',
  cyanContainerBg: '#0C233C',
  greenContainerBg: '#0B291E',
  neutralContainerBg: '#16243A',
  oceanSkyTop: '#060F1E',
  oceanSkyBottom: '#0B1C33',
  oceanHorizonLine: '#38BDF8',
  oceanSeaTop: '#0A284A',
  oceanSeaMid: '#061B30',
  oceanSeaDeep: '#030F1C',
  oceanWaveLight: 'rgba(56, 189, 248, 0.45)',
  oceanWaveSubtle: 'rgba(14, 165, 233, 0.25)',
  oceanReflectionOpacity: 0.22,
};

export const C = LIGHT_THEME;

export const FONT = {
  regular: 'BeVietnamPro_400Regular',
  medium: 'BeVietnamPro_500Medium',
  semibold: 'BeVietnamPro_600SemiBold',
  bold: 'BeVietnamPro_700Bold',
} as const;

export const TYPOGRAPHY = {
  pageTitle: { fontSize: 24, lineHeight: 30, fontFamily: FONT.bold, fontWeight: '700' as const },
  sectionTitle: { fontSize: 19, lineHeight: 25, fontFamily: FONT.semibold, fontWeight: '600' as const },
  cardTitle: { fontSize: 17, lineHeight: 22, fontFamily: FONT.bold, fontWeight: '700' as const },
  metricValue: { fontSize: 16, lineHeight: 22, fontFamily: FONT.semibold, fontWeight: '600' as const },
  body: { fontSize: 14, lineHeight: 20, fontFamily: FONT.regular, fontWeight: '400' as const },
  button: { fontSize: 14, lineHeight: 19, fontFamily: FONT.semibold, fontWeight: '600' as const },
  secondary: { fontSize: 13, lineHeight: 18, fontFamily: FONT.regular, fontWeight: '400' as const },
  badge: { fontSize: 12, lineHeight: 16, fontFamily: FONT.medium, fontWeight: '500' as const },
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
};

export const SHADOWS = {
  card: {
    shadowColor: '#142D45',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  sm: {
    shadowColor: '#142D45',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  cautionGlow: {
    shadowColor: '#D97706',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 1,
  },
  warningGlow: {
    shadowColor: '#D97706',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.12,
    shadowRadius: 6,
    elevation: 2,
  },
  criticalGlow: {
    shadowColor: '#DC2626',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.14,
    shadowRadius: 8,
    elevation: 2,
  },
} as const;

export const SEVERITY_COLORS = {
  NORMAL: C.green,
  CAUTION: C.amber,
  WARNING: C.amber,
  CRITICAL: C.red,
  UNKNOWN: C.muted,
} as const;

export const SEVERITY_BG = {
  NORMAL: C.greenContainerBg,
  CAUTION: C.warningContainerBg,
  WARNING: C.warningContainerBg,
  CRITICAL: C.errorContainerBg,
  UNKNOWN: C.neutralContainerBg,
} as const;

export function getSeverityColors(colors: ThemeColors) {
  return {
    NORMAL: colors.green,
    CAUTION: colors.amber,
    WARNING: colors.amber,
    CRITICAL: colors.red,
    UNKNOWN: colors.muted,
  };
}

export function getSeverityBg(colors: ThemeColors) {
  return {
    NORMAL: colors.greenContainerBg,
    CAUTION: colors.warningContainerBg,
    WARNING: colors.warningContainerBg,
    CRITICAL: colors.errorContainerBg,
    UNKNOWN: colors.neutralContainerBg,
  };
}

interface ThemeContextValue {
  mode: ThemeMode;
  isDark: boolean;
  colors: ThemeColors;
  reducedMotion: boolean;
  setMode: (mode: ThemeMode) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  mode: 'light',
  isDark: false,
  colors: LIGHT_THEME,
  reducedMotion: false,
  setMode: () => {},
  toggleTheme: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = useState<ThemeMode>('light');
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    let active = true;
    AccessibilityInfo.isReduceMotionEnabled()
      .then((enabled) => {
        if (active) setReducedMotion(enabled);
      })
      .catch(() => {});

    const sub = AccessibilityInfo.addEventListener('reduceMotionChanged', (enabled) => {
      setReducedMotion(enabled);
    });
    return () => {
      active = false;
      sub?.remove?.();
    };
  }, []);

  const colors = mode === 'dark' ? DARK_THEME : LIGHT_THEME;
  const toggleTheme = () => setMode((prev) => (prev === 'light' ? 'dark' : 'light'));

  return React.createElement(
    ThemeContext.Provider,
    { value: { mode, isDark: mode === 'dark', colors, reducedMotion, setMode, toggleTheme } },
    children
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
