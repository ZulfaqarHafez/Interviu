export type CandidateConfig = {
  id: string;
  tenant_id?: string;
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

export type Health = {
  ok: boolean;
  tracerazor_importable: boolean;
  database_backend: string;
  /** True when an OpenAI key is configured, so an uploaded agent.md runs for real. */
  openai_configured?: boolean;
};

export type AgentIntakeDetected = {
  role: string;
  title: string;
  tools: string[];
  tool_count: number;
  token_estimate: number;
};

export type AgentIntakeResponse = {
  candidate: CandidateConfig;
  /** "live" when executed against a real LLM, "demo" when run deterministically. */
  mode: "live" | "demo";
  detected: AgentIntakeDetected;
};

export type ExamPack = {
  schema?: "assay.exam_pack.v1";
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
  schema: "assay.exam_pack.v1";
  pack: ExamPack;
  huggingface: {
    repo_type: "dataset";
    files: {
      "data/assay_exam_rows.jsonl": Array<Record<string, unknown>>;
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
  tenant_id?: string;
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
  job_scope?: JobScope | null;
  // Optional scorecard summary attached by GET /runs for the Experiments table.
  certified?: boolean;
  pass_count?: number;
  total_count?: number;
  degraded?: boolean;
  qualification_status?: "tailored" | "deterministic" | "partial";
  role_brief_summary?: string | null;
};

export type RunEvent = {
  span_id: string;
  tenant_id?: string;
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
  raw: Record<string, unknown>;
  message?: string | null;
};

export type Scorecard = {
  tenant_id?: string;
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
  lessons_applied: string[];
  prior_run_id: string | null;
  degraded?: boolean;
  degraded_reason?: string | null;
  qualification_status?: "tailored" | "deterministic" | "partial";
  role_brief_summary?: string | null;
  semantic_judge_used?: boolean;
  semantic_judge_summary?: Record<string, unknown>;
};

export type BriefCompetency = {
  key: string;
  label: string;
  why?: string;
  difficulty: "intro" | "standard" | "adversarial";
  seed_keywords?: string[];
  forbidden?: string[];
};

export type RoleBrief = {
  schema: "assay.role_brief.v1";
  run_id: string;
  candidate_id: string;
  candidate_name: string;
  mode: "fast" | "deep" | "deterministic";
  status: "ok" | "unavailable" | "error" | "deterministic";
  model?: string | null;
  role_summary: string;
  should_do: string[];
  must_not_do: string[];
  risks: string[];
  competencies: BriefCompetency[];
  sources: Array<{ title: string; url: string }>;
  message?: string | null;
  generated_at: string;
};

export type ProductReviewer = {
  key: string;
  name: string;
  status: "pass" | "warn" | "wait";
  label: string;
  summary: string;
  evidence: string[];
  next_step?: string | null;
  sprite: string;
};

export type ProductReview = {
  schema: "assay.product_review.v1";
  run_id: string;
  generated_at: string;
  reviewers: ProductReviewer[];
};

export type TracePayload = {
  run_id: string;
  events: RunEvent[];
  scorecard: Scorecard | null;
};

export type SubAgentSpec = {
  id: string;
  name: string;
  role: string;
  focus: string;
  trigger: string;
  sprite: string;
  priority: "recommended" | "optional";
  tools: string[];
  delegation_rule: string;
  definition_markdown: string;
};

export type AgentSpec = {
  schema: "assay.agent_spec.v1";
  run_id: string;
  candidate_id: string;
  candidate_name: string;
  exam_pack_id: string;
  generated_at: string;
  readiness: "ready" | "refine" | "needs_subagents";
  headline: string;
  agent_markdown: string;
  strengths: string[];
  gaps: string[];
  tracerazor_actions: string[];
  sub_agents: SubAgentSpec[];
  metrics: Record<string, unknown>;
};

export type AgentSpecFileExport = {
  run_id: string;
  directory: string;
  files: Record<string, string>;
  sub_agent_count: number;
};

export type SubAgentIdea = {
  name: string;
  purpose: string;
};

export type AgentResearchSource = {
  title: string;
  url: string;
};

export type AgentResearch = {
  run_id: string;
  candidate_id: string;
  candidate_name: string;
  mode: "fast" | "deep";
  status: "ok" | "unavailable" | "error";
  model?: string | null;
  summary: string;
  brief_markdown: string;
  recommended_tools: string[];
  recommended_subagents: SubAgentIdea[];
  risks: string[];
  sources: AgentResearchSource[];
  message?: string | null;
  generated_at: string;
};

export type Seniority = "intern" | "junior" | "mid" | "senior" | "lead" | "executive" | "unspecified";

export type JobScope = {
  raw_text: string;
  title: string;
  seniority: Seniority;
  responsibilities: string[];
  required_skills: string[];
  nice_to_have: string[];
  qualifications: string[];
  domain: string;
  risks: string[];
  compliance_flags: string[];
  extraction: "none" | "keyword" | "openai-fast" | "openai-deep";
};

export type RequirementSource = {
  phrase: string;
  field: string;
  rule_id: string;
  weight: number;
};

export type CompetencyRequirement = {
  competency: string;
  label: string;
  rationale: string;
  sources: RequirementSource[];
  expected_check_ids: string[];
  recommended_subagent_id: string | null;
  priority: "recommended" | "optional";
  covered_by_pack: string | null;
};

export type RoleAnalysis = {
  schema: "assay.role_analysis.v1";
  job_scope: JobScope;
  recommended_exam_pack_id: string;
  supplemental_pack_ids: string[];
  requirements: CompetencyRequirement[];
  recommended_subagents: SubAgentSpec[];
  uncovered_competencies: string[];
  compliance_notes: string[];
  extraction_status: "keyword" | "openai-fast" | "openai-deep" | "unavailable" | "error";
  sources: AgentResearchSource[];
  generated_at: string;
};

export type DatabaseHealth = {
  backend: string;
  ok: boolean;
  path?: string;
  tables?: Record<string, unknown>;
};

export type ProofBundle = {
  schema: "assay.proof_bundle.v1";
  product: "Assay";
  tenant_id?: string;
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
    qualification_status?: "tailored" | "deterministic" | "partial" | null;
    event_count: number;
  };
  role_brief?: RoleBrief | null;
  tailored_exam_pack?: ExamPack | null;
  database: DatabaseHealth | Record<string, unknown>;
  connectors: Connector[];
  connector_probes: ConnectorProbe[];
  agent_spec: AgentSpec | null;
  role_analysis?: RoleAnalysis | null;
  product_review?: ProductReview | null;
};

// --- Phase 0: closed learning loop (diagnostic library + progress) ---

export type LessonOutcome = "pending" | "improved" | "regressed" | "unchanged" | "still_failing";

export type DiagnosticLesson = {
  id: string;
  candidate_id: string;
  exam_pack_id: string;
  competency: string;
  text: string;
  origin_run_id: string;
  origin_score: number;
  origin_variant: string;
  created_at: string;
  updated_at: string;
  applied_run_ids: string[];
  last_applied_at?: string | null;
  latest_outcome: LessonOutcome;
  latest_outcome_score?: number | null;
  active: boolean;
};

export type CompetencyTrendPoint = {
  run_id: string;
  created_at: string;
  held_out_score: number;
  passed: boolean;
  transfer_gap: number;
  lessons_applied: number;
};

export type CompetencyProgress = {
  competency: string;
  label: string;
  points: CompetencyTrendPoint[];
  first_score: number;
  latest_score: number;
  delta: number;
  trend: "up" | "down" | "flat";
  active_lessons: number;
};

export type CandidateProgress = {
  schema: "assay.candidate_progress.v1";
  candidate_id: string;
  candidate_name: string;
  run_count: number;
  pass_rate: number;
  competencies: CompetencyProgress[];
  runs: RunRecord[];
  active_lessons: number;
};

export type ComparisonOutcome = "improved" | "regressed" | "unchanged" | "new" | "dropped";

export type CompetencyComparison = {
  competency: string;
  label: string;
  baseline_score: number;
  current_score: number;
  delta: number;
  outcome: ComparisonOutcome;
  baseline_passed: boolean;
  current_passed: boolean;
};

export type RunComparison = {
  schema: "assay.run_comparison.v1";
  run_id: string;
  baseline_run_id: string | null;
  candidate_id: string;
  competencies: CompetencyComparison[];
  improved: number;
  regressed: number;
  unchanged: number;
  certified_changed: boolean;
};
