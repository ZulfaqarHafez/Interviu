export type CandidateConfig = {
  id: string;
  name: string;
  adapter_type: "mock" | "http" | "openai-compatible" | "local-command" | "mcp-server";
  endpoint_url?: string | null;
  model?: string | null;
  system_prompt?: string | null;
  command?: string[] | null;
  mcp_server_url?: string | null;
  metadata?: Record<string, unknown>;
  created_at?: string;
};

export type ExamPack = {
  id: string;
  name: string;
  simulator_model: string;
  items: Array<{
    id: string;
    competency: string;
    prompt: string;
    held_out_prompt: string;
    rubric?: string;
    expected_checks?: Array<{
      id: string;
      label: string;
      keywords: string[];
      forbidden: string[];
      weight: number;
    }>;
    difficulty: string;
    counterfactual_group?: string | null;
  }>;
};

export type ExamPackExport = {
  schema: "interviu.exam_pack.v1";
  pack: ExamPack;
  huggingface: {
    repo_type: "dataset";
    files: {
      "data/interviu_exam_rows.jsonl": Array<Record<string, unknown>>;
      "README.md": string;
    };
    suggested_commands: string[];
  };
};

export type ExamPackFileExport = {
  pack_id: string;
  directory: string;
  files: Record<string, string>;
  row_count: number;
  suggested_commands: string[];
};

export type Connector = {
  id: string;
  name: string;
  status: "ready" | "planned" | "connected" | "unavailable";
  description: string;
};

export type ConnectorProbe = {
  id: string;
  name: string;
  status: "pass" | "warn" | "fail";
  evidence: string;
  details: Record<string, unknown>;
  next_step?: string | null;
};

export type RunRecord = {
  id: string;
  candidate_id: string;
  exam_pack_id: string;
  status: "created" | "running" | "completed" | "failed";
  k: number;
  competency_threshold: number;
  max_transfer_gap: number;
  tas_threshold: number;
  error?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type RunEvent = {
  span_id: string;
  run_id: string;
  sequence: number;
  actor: "candidate" | "examiner" | "grader_panel" | "lesson_library" | "trace_auditor" | "system";
  event_type: string;
  payload: Record<string, unknown>;
  started_at: string;
  ended_at?: string | null;
  tracerazor_step_id?: number | null;
};

export type TraceAuditSummary = {
  status: "ok" | "insufficient_steps" | "unavailable" | "error";
  trace_id?: string | null;
  tas_score?: number | null;
  grade?: string | null;
  passes: boolean;
  total_steps: number;
  total_tokens: number;
  metrics: Record<string, unknown>;
  savings: Record<string, unknown>;
  fixes: Array<Record<string, unknown>>;
  message?: string | null;
};

export type Scorecard = {
  run_id: string;
  status: string;
  certified: boolean;
  certificate_label: string;
  k: number;
  thresholds: Record<string, number>;
  simulator_model: string;
  pass_at_k: Record<string, boolean>;
  competency_scores: Record<string, number>;
  seen_scores: Record<string, number>;
  held_out_scores: Record<string, number>;
  transfer_gap: Record<string, number>;
  grader_disagreement: number;
  trace_audit: TraceAuditSummary;
  failure_reasons: string[];
  created_at: string;
};

export type TracePayload = {
  run_id: string;
  events: RunEvent[];
  scorecard: Scorecard | null;
};

export type DatabaseHealth = {
  backend: string;
  ok: boolean;
  path?: string;
  tables?: Record<string, unknown>;
};

export type ProofBundle = {
  schema: "interviu.proof_bundle.v1";
  product: "Interviu";
  generated_at: string;
  run: RunRecord;
  candidate: CandidateConfig | null;
  scorecard: Scorecard | null;
  events: RunEvent[];
  summary: {
    status: string;
    certified: boolean;
    certificate_label: string;
    tas_score?: number | null;
    trace_status: string;
    event_count: number;
  };
  database: DatabaseHealth | Record<string, unknown>;
  connectors: Connector[];
  connector_probes: ConnectorProbe[];
};
