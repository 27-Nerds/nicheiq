export type SelectionMetricKind =
  | 'derived_score'
  | 'assessed_score'
  | 'estimate'
  | 'evidence'
  | 'context';

export interface SelectionMetricExplanation {
  key: string;
  label: string;
  kind: SelectionMetricKind;
  range: '0-100' | 'text';
  summary: string;
  method: string;
  sourceFields: string[];
  caveat?: string;
}

/**
 * Env-overridable market-fit cap thresholds served by the backend, mirroring
 * src/nicheiq/config/settings.py (payability_* / parity_* fields). Injected into
 * scoreRationale's cap-hint copy so a prod env override can't falsify it.
 */
export interface SelectionCapThresholds {
  payabilityLowThreshold: number;
  payabilityMarketFitCap: number;
  parityShippedMarketFitCap: number;
  parityPartialMarketFitCap: number;
  paritySubstituteMarketFitCap: number;
  paritySubstituteWeakWalletCap: number;
  parityBundledFreeCap: number;
}

export interface SelectionMetricExplanationsResponse {
  schemaVersion: 1;
  metrics: SelectionMetricExplanation[];
  /** Absent on older backend payloads; consumers fall back to the Python defaults. */
  capThresholds?: SelectionCapThresholds;
}
