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

export interface SelectionMetricExplanationsResponse {
  schemaVersion: 1;
  metrics: SelectionMetricExplanation[];
}
