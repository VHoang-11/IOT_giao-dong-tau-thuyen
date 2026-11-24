/**
 * SMART VESSEL MOTION GUARD (SVMG) - FEATURE REGISTRY
 * Contract-driven registry for 23 Kinematic Features (Official svmg-angle-23-v1)
 * 
 * Sources official contract: frontend/src/contracts/features23.json
 * Validates integrity, handles vector mapping, missing states, and CSV export.
 * Note: Frontend NEVER computes ML feature extraction algorithms locally.
 */

import features23Contract from './contracts/features23.json';
import featureSampleFixture from './fixtures/featureSampleFixture.json';
import type { FeatureItem } from './domain';
import { FEATURE_NAMES_VI } from './i18n/vi';

export interface FeatureDefinition {
  readonly index: number;
  readonly name: string;
  readonly displayName: string;
  readonly group: 'roll_60s' | 'roll_180s' | 'pitch_60s' | string;
  readonly window_s: number;
  readonly unit: string;
  readonly description: string;
  readonly defaultSampleValue: number;
  readonly defaultStatus: 'VALID' | 'WARNING' | 'INVALID';
  readonly defaultReason: string;
}

export interface FeatureGroupDefinition {
  readonly id: string;
  readonly title: string;
  readonly featureCount: number;
}

export interface FeatureSummary {
  readonly total: number;
  readonly validCount: number;
  readonly warningCount: number;
  readonly invalidCount: number;
  readonly missingCount: number;
  readonly contractId: string;
  readonly version: string;
  readonly sourceExport: string;
}

// 1. Contract Validation & Registration
function validateContractIntegrity(contract: typeof features23Contract): {
  groups: FeatureGroupDefinition[];
  features: FeatureDefinition[];
} {
  const schemaVersion = (contract as any).feature_schema_version || 'svmg-angle-23-v1';
  if (schemaVersion !== 'svmg-angle-23-v1') {
    throw new Error(`[FeatureRegistry] Invalid feature_schema_version: ${schemaVersion}`);
  }
  const count = (contract as any).feature_count ?? contract.features?.length;
  if (count !== 23) {
    throw new Error(`[FeatureRegistry] feature_count mismatch: expected 23, got ${count}`);
  }
  if (!Array.isArray(contract.features) || contract.features.length !== 23) {
    throw new Error(`[FeatureRegistry] features array length mismatch: expected 23, got ${contract.features?.length}`);
  }

  const sampleMap: Record<string, number> = (featureSampleFixture as any).samples || {};
  const seenNames = new Set<string>();
  const validatedFeatures: FeatureDefinition[] = [];

  for (let i = 0; i < contract.features.length; i++) {
    const f = contract.features[i];
    if (f.index !== i) {
      throw new Error(`[FeatureRegistry] Feature index sequence gap or mismatch at [${i}], received index ${f.index}`);
    }
    if (!f.name || seenNames.has(f.name)) {
      throw new Error(`[FeatureRegistry] Duplicate or empty feature name '${f.name}' at index ${i}`);
    }
    seenNames.add(f.name);

    // Group & window_s determined by official contract specification (FR05 / M1-08 / M2)
    let group: 'roll_60s' | 'roll_180s' | 'pitch_60s' = 'roll_60s';
    let window_s = 60;
    if (f.index >= 0 && f.index <= 7) {
      group = 'roll_60s';
      window_s = 60;
    } else if (f.index >= 8 && f.index <= 19) {
      group = 'roll_180s';
      window_s = (f.name === 'roll_rms_early_60' || f.name === 'roll_rms_late_60') ? 60 : 180;
    } else {
      group = 'pitch_60s';
      window_s = 60;
    }

    const viInfo = FEATURE_NAMES_VI[f.name];
    const displayName = viInfo?.titleVi || f.name;
    const description = viInfo?.descVi || f.name;
    const defaultVal = sampleMap[f.name] ?? 0;

    validatedFeatures.push({
      index: f.index,
      name: f.name,
      displayName,
      group,
      window_s,
      unit: f.unit,
      description,
      defaultSampleValue: defaultVal,
      defaultStatus: 'VALID',
      defaultReason: ''
    });
  }

  const validatedGroups: FeatureGroupDefinition[] = [
    { id: 'roll_60s', title: 'Roll Động học ngắn hạn (60s)', featureCount: 8 },
    { id: 'roll_180s', title: 'Roll Xu hướng dài hạn & Nghiêng lệch (180s)', featureCount: 12 },
    { id: 'pitch_60s', title: 'Pitch Động học nhồi/chúi ngắn hạn (60s)', featureCount: 3 }
  ];

  return { groups: validatedGroups, features: validatedFeatures };
}

const parsed = validateContractIntegrity(features23Contract);

// Exported contract constants matching official schema
export const CONTRACT_SCHEMA_VERSION = (features23Contract as any).feature_schema_version || 'svmg-angle-23-v1';
export const PREPROCESSING_VERSION = (features23Contract as any).preprocessing_version || 'imu-cf-bw4-20to10-v1';
export const CONTRACT_ID = CONTRACT_SCHEMA_VERSION;
export const CONTRACT_VERSION = CONTRACT_SCHEMA_VERSION;
export const CONTRACT_TITLE = 'SVMG 23-Feature Kinematic Vector Contract';
export const CONTRACT_DESCRIPTION = 'Bản hợp đồng đặc tả 23 đặc trưng động học (Kinematic Feature Vector) phục vụ mô hình TinyML Random Forest và hệ thống giám sát Smart Vessel Motion Guard.';
export const TOTAL_FEATURES = (features23Contract as any).feature_count || 23;
export const CONTRACT_SOURCE_EXPORT = (featureSampleFixture as any).source_export || '2026-11-23T07-38_export.csv';
export const CONTRACT_EXPORTED_AT = (featureSampleFixture as any).exported_at || '2026-11-23T07:38:00Z';

export const FEATURE_GROUPS: readonly FeatureGroupDefinition[] = Object.freeze(parsed.groups);
export const FEATURE_REGISTRY: readonly FeatureDefinition[] = Object.freeze(parsed.features);

export const FEATURE_BY_ID = new Map<string, FeatureDefinition>(
  FEATURE_REGISTRY.map(f => [f.name, f])
);

export const FEATURE_BY_INDEX = new Map<number, FeatureDefinition>(
  FEATURE_REGISTRY.map(f => [f.index, f])
);

export const FEATURE_NAME_LIST: string[] = FEATURE_REGISTRY.map(f => f.name);

/**
 * Maps incoming vector or fallback sample to contract-compliant FeatureItem list.
 * Handles missing values, offline/fault states, and dimension validation.
 */
export function mapToFeatureItems(
  vector?: (number | null | undefined)[] | null,
  options?: {
    isSensorOk?: boolean;
    isOffline?: boolean;
    source?: 'SAMPLE' | 'LIVE' | 'STATIC_CSV';
  }
): { items: FeatureItem[]; summary: FeatureSummary } {
  const isOffline = options?.isOffline ?? false;
  const isSensorOk = options?.isSensorOk ?? true;
  const source = options?.source ?? 'SAMPLE';

  // State: OFFLINE
  if (isOffline) {
    const items: FeatureItem[] = FEATURE_REGISTRY.map(f => ({
      index: f.index,
      name: f.name,
      displayName: f.displayName,
      group: f.group,
      window_s: f.window_s,
      unit: f.unit,
      description: f.description,
      value: null,
      status: 'NOT_APPLICABLE',
      reason: 'Mất kết nối thiết bị (OFFLINE) - Dữ liệu không khả dụng',
      source: 'UNAVAILABLE'
    }));
    return {
      items,
      summary: {
        total: TOTAL_FEATURES,
        validCount: 0,
        warningCount: 0,
        invalidCount: 0,
        missingCount: TOTAL_FEATURES,
        contractId: CONTRACT_ID,
        version: CONTRACT_VERSION,
        sourceExport: CONTRACT_SOURCE_EXPORT
      }
    };
  }

  // State: SENSOR_FAULT
  if (!isSensorOk) {
    const items: FeatureItem[] = FEATURE_REGISTRY.map(f => ({
      index: f.index,
      name: f.name,
      displayName: f.displayName,
      group: f.group,
      window_s: f.window_s,
      unit: f.unit,
      description: f.description,
      value: null,
      status: 'NOT_APPLICABLE',
      reason: 'Lỗi cảm biến phần cứng (SENSOR_FAULT) - Không suy diễn số đo',
      source: 'UNAVAILABLE'
    }));
    return {
      items,
      summary: {
        total: TOTAL_FEATURES,
        validCount: 0,
        warningCount: 0,
        invalidCount: 0,
        missingCount: TOTAL_FEATURES,
        contractId: CONTRACT_ID,
        version: CONTRACT_VERSION,
        sourceExport: CONTRACT_SOURCE_EXPORT
      }
    };
  }

  // If no vector provided, use fixture sample baseline (CSV 2026-11-23T07-38_export.csv)
  if (!vector) {
    const items: FeatureItem[] = FEATURE_REGISTRY.map(f => ({
      index: f.index,
      name: f.name,
      displayName: f.displayName,
      group: f.group,
      window_s: f.window_s,
      unit: f.unit,
      description: f.description,
      value: f.defaultSampleValue,
      status: f.defaultStatus,
      reason: f.defaultReason,
      source: 'MOCK_CONTRACT_SAMPLE'
    }));
    return {
      items,
      summary: {
        total: TOTAL_FEATURES,
        validCount: TOTAL_FEATURES,
        warningCount: 0,
        invalidCount: 0,
        missingCount: 0,
        contractId: CONTRACT_ID,
        version: CONTRACT_VERSION,
        sourceExport: CONTRACT_SOURCE_EXPORT
      }
    };
  }

  // Vector provided: validate dimensions
  const hasDimMismatch = vector.length !== TOTAL_FEATURES;
  let validCount = 0;
  let warningCount = 0;
  let invalidCount = 0;
  let missingCount = 0;

  const items: FeatureItem[] = FEATURE_REGISTRY.map((f, i) => {
    const val = vector[i];
    if (val === undefined || val === null || isNaN(val)) {
      missingCount++;
      return {
        index: f.index,
        name: f.name,
        displayName: f.displayName,
        group: f.group,
        window_s: f.window_s,
        unit: f.unit,
        description: f.description,
        value: null,
        status: 'MISSING',
        reason: hasDimMismatch
          ? `Lệch kích thước vectơ (nhận ${vector.length}, hợp đồng yêu cầu ${TOTAL_FEATURES})`
          : 'Chờ giá trị từ Backend TV3 / Feature Store',
        source: source === 'LIVE' ? 'BACKEND_LIVE' : 'MOCK_CONTRACT_SAMPLE'
      };
    }

    if (!isFinite(val)) {
      invalidCount++;
      return {
        index: f.index,
        name: f.name,
        displayName: f.displayName,
        group: f.group,
        window_s: f.window_s,
        unit: f.unit,
        description: f.description,
        value: null,
        status: 'INVALID',
        reason: 'Giá trị số không hợp lệ (Infinity/NaN)',
        source: source === 'LIVE' ? 'BACKEND_LIVE' : 'MOCK_CONTRACT_SAMPLE'
      };
    }

    validCount++;
    return {
      index: f.index,
      name: f.name,
      displayName: f.displayName,
      group: f.group,
      window_s: f.window_s,
      unit: f.unit,
      description: f.description,
      value: val,
      status: 'VALID',
      reason: f.defaultReason,
      source: source === 'LIVE' ? 'BACKEND_LIVE' : 'MOCK_CONTRACT_SAMPLE'
    };
  });

  return {
    items,
    summary: {
      total: TOTAL_FEATURES,
      validCount,
      warningCount,
      invalidCount,
      missingCount,
      contractId: CONTRACT_ID,
      version: CONTRACT_VERSION,
      sourceExport: CONTRACT_SOURCE_EXPORT
    }
  };
}

/**
 * Generates exact CSV formatted string for 23 features in contract order.
 * Properly marks data source to prevent misrepresentation of mock data as real.
 */
export function exportFeaturesToCSV(
  items: FeatureItem[],
  options?: { voyageId?: string; isMock?: boolean }
): string {
  const isMock = options?.isMock ?? true;
  const voyageId = options?.voyageId ?? 'V-2026-001';
  const timestamp = new Date().toISOString();

  const lines: string[] = [
    `# SMART VESSEL MOTION GUARD (SVMG) - KINEMATIC FEATURE VECTOR EXPORT`,
    `# Contract Schema: ${CONTRACT_SCHEMA_VERSION} | Preprocessing: ${PREPROCESSING_VERSION}`,
    `# Voyage ID: ${voyageId} | Exported At: ${timestamp}`,
    `# Data Nature: ${isMock ? 'MOCK / SAMPLE CONTRACT VERIFICATION ONLY (KHÔNG PHẢI DỮ LIỆU THỰC)' : 'PRODUCTION / TV3 FEATURE STORE'}`,
    `Index,Feature_ID,Group,Window_Seconds,Unit,Value,Status,Reason,Data_Source`
  ];

  for (const item of items) {
    const valStr = item.value !== null && item.value !== undefined ? item.value.toString() : 'N/A';
    const reasonEscaped = `"${(item.reason || '').replace(/"/g, '""')}"`;
    lines.push(
      `${item.index},${item.name},${item.group},${item.window_s},${item.unit},${valStr},${item.status},${reasonEscaped},${item.source || (isMock ? 'MOCK_SAMPLE' : 'LIVE')}`
    );
  }

  return lines.join('\n');
}
