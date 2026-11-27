/**
 * SMART VESSEL MOTION GUARD (SVMG) - MOBILE FEATURE REGISTRY
 * Contract-driven registry for 23 Kinematic Features (Official svmg-angle-23-v1)
 * Đồng bộ trực tiếp với frontend/src/featureRegistry.ts.
 */

import features23Contract from './contracts/features23.json';
import featureSampleFixture from './fixtures/featureSampleFixture.json';
import type { FeatureItem, FeatureSummary } from './types/domain';
import { FEATURE_NAMES_VI } from './i18n/vi';

export interface FeatureDefinition {
  readonly index: number;
  readonly name: string;
  readonly displayName: string;
  readonly group: 'roll_60s' | 'roll_180s' | 'pitch_60s';
  readonly window_s: number;
  readonly unit: string;
  readonly description: string;
  readonly defaultSampleValue: number;
  readonly defaultStatus: 'VALID' | 'WARNING' | 'INVALID';
  readonly defaultReason: string;
}

export interface FeatureGroupDefinition {
  readonly id: 'roll_60s' | 'roll_180s' | 'pitch_60s';
  readonly title: string;
  readonly featureCount: number;
}

function validateContractIntegrity(contract: typeof features23Contract): {
  groups: FeatureGroupDefinition[];
  features: FeatureDefinition[];
} {
  const schemaVersion = contract.feature_schema_version || 'svmg-angle-23-v1';
  if (schemaVersion !== 'svmg-angle-23-v1') {
    throw new Error(`[FeatureRegistry] Invalid feature_schema_version: ${schemaVersion}`);
  }
  const count = contract.feature_count ?? contract.features?.length;
  if (count !== 23 || !Array.isArray(contract.features) || contract.features.length !== 23) {
    throw new Error(`[FeatureRegistry] feature_count mismatch: expected 23, got ${count}`);
  }

  const sampleMap: Record<string, number> = (featureSampleFixture as any).samples || {};
  const seenNames = new Set<string>();
  const validatedFeatures: FeatureDefinition[] = [];

  for (let i = 0; i < contract.features.length; i++) {
    const f = contract.features[i];
    if (f.index !== i) {
      throw new Error(`[FeatureRegistry] Feature index mismatch at [${i}], got ${f.index}`);
    }
    if (!f.name || seenNames.has(f.name)) {
      throw new Error(`[FeatureRegistry] Duplicate or empty feature name '${f.name}' at index ${i}`);
    }
    seenNames.add(f.name);

    let group: 'roll_60s' | 'roll_180s' | 'pitch_60s' = 'roll_60s';
    let window_s = 60;
    if (f.index >= 0 && f.index <= 7) {
      group = 'roll_60s';
      window_s = 60;
    } else if (f.index >= 8 && f.index <= 19) {
      group = 'roll_180s';
      window_s = f.name === 'roll_rms_early_60' || f.name === 'roll_rms_late_60' ? 60 : 180;
    } else {
      group = 'pitch_60s';
      window_s = 60;
    }

    const viInfo = FEATURE_NAMES_VI[f.name];
    const displayName = viInfo?.titleVi || f.name;
    const description = viInfo?.descVi || f.name;
    const defaultVal = sampleMap[f.name];

    validatedFeatures.push({
      index: f.index,
      name: f.name,
      displayName,
      group,
      window_s,
      unit: f.unit,
      description,
      defaultSampleValue: typeof defaultVal === 'number' ? defaultVal : 0,
      defaultStatus: typeof defaultVal === 'number' ? 'VALID' : 'INVALID',
      defaultReason: typeof defaultVal === 'number' ? '' : 'Chưa có giá trị trong dữ liệu mẫu',
    });
  }

  const validatedGroups: FeatureGroupDefinition[] = [
    { id: 'roll_60s', title: 'Roll ngắn hạn (60s)', featureCount: 8 },
    { id: 'roll_180s', title: 'Roll dài hạn & xu hướng (180s)', featureCount: 12 },
    { id: 'pitch_60s', title: 'Pitch ngắn hạn (60s)', featureCount: 3 },
  ];

  return { groups: validatedGroups, features: validatedFeatures };
}

const parsed = validateContractIntegrity(features23Contract);

export const CONTRACT_SCHEMA_VERSION = features23Contract.feature_schema_version || 'svmg-angle-23-v1';
export const PREPROCESSING_VERSION = features23Contract.preprocessing_version || 'imu-cf-bw4-20to10-v1';
export const CONTRACT_ID = CONTRACT_SCHEMA_VERSION;
export const CONTRACT_VERSION = CONTRACT_SCHEMA_VERSION;
export const TOTAL_FEATURES = features23Contract.feature_count || 23;
export const CONTRACT_SOURCE_EXPORT =
  (featureSampleFixture as any).source_export || '2026-11-23T07-38_export.csv';

export const FEATURE_GROUPS: readonly FeatureGroupDefinition[] = Object.freeze(parsed.groups);
export const FEATURE_REGISTRY: readonly FeatureDefinition[] = Object.freeze(parsed.features);
export const FEATURE_NAME_LIST: string[] = FEATURE_REGISTRY.map((f) => f.name);

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

  if (isOffline) {
    const items: FeatureItem[] = FEATURE_REGISTRY.map((f) => ({
      index: f.index,
      name: f.name,
      displayName: f.displayName,
      group: f.group,
      window_s: f.window_s,
      unit: f.unit,
      description: f.description,
      value: null,
      status: 'NOT_APPLICABLE',
      reason: 'Mất kết nối thiết bị — Dữ liệu không khả dụng',
      source: 'UNAVAILABLE',
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
        sourceExport: CONTRACT_SOURCE_EXPORT,
      },
    };
  }

  if (!isSensorOk) {
    const items: FeatureItem[] = FEATURE_REGISTRY.map((f) => ({
      index: f.index,
      name: f.name,
      displayName: f.displayName,
      group: f.group,
      window_s: f.window_s,
      unit: f.unit,
      description: f.description,
      value: null,
      status: 'NOT_APPLICABLE',
      reason: 'Lỗi cảm biến phần cứng — Không suy diễn số đo',
      source: 'UNAVAILABLE',
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
        sourceExport: CONTRACT_SOURCE_EXPORT,
      },
    };
  }

  if (!vector) {
    const items: FeatureItem[] = FEATURE_REGISTRY.map((f) => ({
      index: f.index,
      name: f.name,
      displayName: f.displayName,
      group: f.group,
      window_s: f.window_s,
      unit: f.unit,
      description: f.description,
      value: f.defaultStatus === 'VALID' ? f.defaultSampleValue : null,
      status: f.defaultStatus,
      reason: f.defaultReason,
      source: 'MOCK_CONTRACT_SAMPLE',
    }));
    const validCount = items.filter((i) => i.status === 'VALID').length;
    return {
      items,
      summary: {
        total: TOTAL_FEATURES,
        validCount,
        warningCount: 0,
        invalidCount: TOTAL_FEATURES - validCount,
        missingCount: 0,
        contractId: CONTRACT_ID,
        version: CONTRACT_VERSION,
        sourceExport: CONTRACT_SOURCE_EXPORT,
      },
    };
  }

  let validCount = 0;
  let warningCount = 0;
  let invalidCount = 0;
  let missingCount = 0;

  const items: FeatureItem[] = FEATURE_REGISTRY.map((f, idx) => {
    const rawVal = idx < vector.length ? vector[idx] : undefined;
    if (rawVal === undefined) {
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
        reason: 'Chưa nhận được phần tử từ dữ liệu đầu vào',
        source,
      };
    }
    if (rawVal === null || !Number.isFinite(rawVal)) {
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
        reason: 'Giá trị không hợp lệ (NaN / Null)',
        source,
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
      value: rawVal,
      status: 'VALID',
      reason: '',
      source,
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
      sourceExport: CONTRACT_SOURCE_EXPORT,
    },
  };
}
