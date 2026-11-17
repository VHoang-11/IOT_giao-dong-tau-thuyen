// Smart Vessel Motion Guard — Maritime Theme System
// Specification:
// - Main background: #F5F7FA
// - Card background: #FFFFFF
// - Sidebar / Nav background: #FFFFFF
// - Header background: #FFFFFF
// - Navy borders & accents: #183E65 / subtle #E2E8F0
// - Primary text: #102B49
// - Secondary text: #55728D
// - Primary buttons: #153D64 (text #FFFFFF)
// - Telemetry accent: #0284C7
// - Normal: #10B981 | Warning: #D97706 | Critical: #DC2626 | Disabled: #94A3B8

export type ThemeMode = 'light' | 'dark';

export const LIGHT_THEME = {
  canvas: '#F5F7FA',          // Main background
  bg: '#FFFFFF',              // Card background
  panel: '#FFFFFF',           // Card panel
  panel2: '#F8FAFC',          // Wells & bento inside
  panelHigh: '#EDF2F7',       // Hover/active wells
  border: '#E2E8F0',          // Clean subtle border
  borderNavy: '#183E65',      // Navy accents
  borderSubtle: '#EDF2F7',    // Subtle dividers
  borderFocus: '#0284C7',     // Telemetry accent highlight
  cyan: '#0284C7',            // Telemetry accent: #0284C7
  cyanBright: '#0369A1',      // Deep sea cyan
  primaryContainer: '#153D64',// Primary button: #153D64
  white: '#FFFFFF',           // Pure white
  text: '#102B49',            // Primary text: #102B49
  textSecondary: '#55728D',   // Secondary text: #55728D
  muted: '#64748B',           // Technical labels, timestamps
  green: '#10B981',           // Normal: green
  tertiary: '#059669',        // Safe resolved
  amber: '#D97706',           // Warning: amber
  orange: '#F97316',          // Caution
  red: '#DC2626',             // Critical: red
  disabled: '#94A3B8',        // Disabled: grey
  errorContainer: '#FEE2E2',  // Critical background
  errorContainerBg: 'rgba(220, 38, 38, 0.08)',
  warningContainerBg: 'rgba(217, 119, 6, 0.08)',
  cyanContainerBg: 'rgba(2, 132, 199, 0.08)',
  greenContainerBg: 'rgba(16, 185, 129, 0.08)',
} as const;

export const DARK_THEME = {
  canvas: '#070D18',
  bg: '#0F172A',
  panel: '#0F172A',
  panel2: '#162032',
  panelHigh: '#1E293B',
  border: '#1E293B',
  borderNavy: '#334155',
  borderSubtle: '#1E293B',
  borderFocus: '#38BDF8',
  cyan: '#38BDF8',
  cyanBright: '#0284C7',
  primaryContainer: '#0284C7',
  white: '#F8FAFC',
  text: '#F1F5F9',
  textSecondary: '#94A3B8',
  muted: '#64748B',
  green: '#10B981',
  tertiary: '#34D399',
  amber: '#F59E0B',
  orange: '#FB923C',
  red: '#EF4444',
  disabled: '#64748B',
  errorContainer: '#7F1D1D',
  errorContainerBg: 'rgba(239, 68, 68, 0.12)',
  warningContainerBg: 'rgba(245, 158, 11, 0.12)',
  cyanContainerBg: 'rgba(56, 189, 248, 0.10)',
  greenContainerBg: 'rgba(16, 185, 129, 0.12)',
} as const;

// Default exported palette is Light Maritime (#F5F7FA, #FFFFFF, #E2E8F0, #102B49)
export const C = LIGHT_THEME;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
};

export const SHADOWS = {
  card: {
    shadowColor: '#102B49',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  sm: {
    shadowColor: '#102B49',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  cautionGlow: {
    shadowColor: '#D97706',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.14,
    shadowRadius: 6,
    elevation: 2,
  },
  warningGlow: {
    shadowColor: '#D97706',
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.18,
    shadowRadius: 8,
    elevation: 2,
  },
  criticalGlow: {
    shadowColor: '#DC2626',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.22,
    shadowRadius: 10,
    elevation: 3,
  },
} as const;

export const SEVERITY_COLORS = {
  NORMAL: C.green,
  CAUTION: C.cyan,
  WARNING: C.amber,
  CRITICAL: C.red,
  UNKNOWN: C.muted,
} as const;

export const SEVERITY_BG = {
  NORMAL: C.greenContainerBg,
  CAUTION: C.cyanContainerBg,
  WARNING: C.warningContainerBg,
  CRITICAL: C.errorContainerBg,
  UNKNOWN: 'rgba(100, 116, 139, 0.08)',
} as const;
