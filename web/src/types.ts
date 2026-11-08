export type ScenarioTask = {
  id: string;
  table: string;
  kind: string;
  description: string;
};
export type Scenario = {
  id: string;
  dataset: string;
  title: string;
  recipient: string;
  purpose: string;
  utility_tasks: ScenarioTask[];
};
export type ScenariosResponse = {
  datasets: { id: string; available: boolean; scenario_ids: string[] }[];
  scenarios: Scenario[];
};
export type Policy = {
  table: string;
  column: string;
  action: string;
  params: Record<string, unknown>;
  reason: string;
  guarantee: string;
};
export type Plan = {
  dataset: string;
  scenario_id: string;
  released_tables: string[];
  policies: Policy[];
  k: number;
  key_id: string;
};
export type Span = {
  start: number;
  end: number;
  label: string;
  layer: string;
  score: number;
};
export type Turn = {
  record_id: string;
  conversation_id: string;
  original_text: string;
  protected_text: string;
  surrogate_text: string | null;
  spans: Span[];
};
export type Redact = {
  dataset: string;
  table: string | null;
  column: string | null;
  redacted: boolean;
  layers_run: string[];
  n_turns: number;
  turns: Turn[];
  per_label: { label: string; n: number; leaked: number; rate: number }[];
  span_labels_note?: string;
};
export type Utility = {
  id: string;
  description?: string;
  score: number | null;
  metric: string;
  required: boolean;
};
export type Scorecard = {
  tool: string;
  scenario: {
    id: string;
    title: string;
    recipient: string;
    purpose: string;
    utility_requirements: string[];
  };
  utility: Utility[];
  summary: {
    privacy: number;
    utility: number;
    composite: number;
    label: string;
    method: string;
  };
  risk_components: Record<string, number | null>;
  tables?: Record<string, { free_text?: Record<string, { identifying_leakage_rate?: number }> }>;
};
export type GateCheck = {
  id: string;
  name: string;
  kind: string;
  status: string;
  value: number | null;
  threshold: number;
  comparison: string;
  source: string;
  reason?: string;
};
export type Verify = {
  scenario_id: string;
  ours: Scorecard;
  baseline: Scorecard;
  baseline_name: string;
  gate: {
    passed: boolean;
    scenario_id: string;
    blocking: string[];
    checks: GateCheck[];
  };
  k: {
    table: string;
    qis: string[];
    pipeline_k: number;
    pycanon_k: number;
    method: string;
  }[];
  residual_risks: { id: string; text: string; source: string }[];
  ablation: {
    layer_off: string;
    leakage: number;
    utility: number;
    n_spans: number;
  }[];
};
export type Report = { plan_table_md: string; policy_card: unknown | null };
export type Run = {
  run_id: string;
  dataset: string;
  scenario_id: string;
  status: string;
  created_utc: string;
  git_hash: string;
  stages: { stage: string; status: string; duration_ms: number | null }[];
  gate: { passed: boolean; blocking: string[] } | null;
  headline: { privacy: number; utility: number; composite: number } | null;
  error: string | null;
};
export type Finding = {
  kind: string;
  dataset: string;
  table: string;
  column: string;
  source_column: string;
  algorithm?: string;
  variant?: string;
  match_rate?: number;
  agreement?: number;
};
