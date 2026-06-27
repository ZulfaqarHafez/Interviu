import type {
  AgentSpec,
  CandidateConfig,
  DatabaseHealth,
  ExamPack,
  ProductReviewer,
  ProofBundle,
  RoleAnalysis,
  Scorecard
} from "@/types/interviu";

/**
 * Pure derive helpers ported verbatim from page.tsx so every console component
 * shares one source of truth. page.tsx keeps its own copies until the
 * integration agent switches it to import from here.
 */

export type LoadState = "idle" | "loading" | "running" | "complete" | "error";

type HealthLike = { ok: boolean; tracerazor_importable: boolean; database_backend?: string } | null;

export function emptyCompetencies(pack?: ExamPack): Record<string, number> {
  const names = pack?.items.map((item) => item.competency) ?? [
    "compliance",
    "fairness",
    "ambiguity_handling",
    "refusal_boundaries",
    "interview_ethics"
  ];
  return Object.fromEntries(Array.from(new Set(names)).map((name) => [name, 0]));
}

export function idleSpriteForPack(packId: string) {
  return packId.includes("injection") ? "candidate-proof" : "candidate-ready";
}

export function labelize(value: string) {
  return value
    .replace(/_/g, " ")
    .replace(/\b[a-z]/g, (letter) => letter.toUpperCase());
}

export function traceStatus(scorecard: Scorecard | null) {
  if (!scorecard) {
    return "pending";
  }
  const audit = scorecard.trace_audit;
  return audit.tas_score === null || audit.tas_score === undefined
    ? audit.status
    : `${audit.tas_score.toFixed(0)} ${audit.grade ?? ""}`.trim();
}

export function traceScoreLabel(scorecard: Scorecard | null) {
  const audit = scorecard?.trace_audit;
  if (!audit) return "Pending";
  if (audit.tas_score !== null && audit.tas_score !== undefined) return audit.tas_score.toFixed(1);
  if (audit.status === "error" || audit.status === "unavailable") return "Not scored";
  if (audit.status === "insufficient_steps") return "Insufficient";
  return "Pending";
}

export function traceAuditStatus(scorecard: Scorecard | null, traceRazorImportable?: boolean) {
  const status = scorecard?.trace_audit.status;
  if (status) return labelize(status);
  return traceRazorImportable ? "Ready" : "Unavailable";
}

export function maxTransferGap(scorecard: Scorecard) {
  return Math.max(0, ...Object.values(scorecard.transfer_gap));
}

export function connectorIcon(id: string) {
  if (id.includes("supabase")) return "sprite-supabase";
  if (id.includes("hugging")) return "sprite-hugging-face";
  if (id.includes("vercel")) return "sprite-vercel";
  if (id.includes("trace")) return "sprite-tracerazor";
  if (id.includes("http")) return "sprite-http-antenna";
  if (id.includes("mcp")) return "sprite-mcp-plug";
  if (id.includes("openai")) return "sprite-model-chip";
  if (id.includes("local")) return "sprite-local-command";
  return "sprite-candidate";
}

export function candidateDockSprite(candidate: CandidateConfig | null) {
  if (candidate?.adapter_type === "http") return "sprite-http-antenna";
  if (candidate?.adapter_type === "mcp-server") return "sprite-mcp-plug";
  if (candidate?.adapter_type === "local-command") return "sprite-local-command";
  if (candidate?.adapter_type === "openai-compatible") return "sprite-model-chip";
  return "sprite-candidate";
}

export type WorkflowStage = {
  key: string;
  label: string;
  meta: string;
  sprite: string;
  sheet: string;
  state: "idle" | "active" | "done" | "attention";
};

export function buildWorkflow(
  state: LoadState,
  scorecard: Scorecard | null,
  agentSpec: AgentSpec | null,
  roleAnalysis: RoleAnalysis | null,
  passedCount: number,
  totalCount: number
): WorkflowStage[] {
  const hasRun = scorecard !== null;
  const hasCoaching = agentSpec !== null || roleAnalysis !== null;
  return [
    {
      key: "prepare",
      label: "Prepare",
      meta: roleAnalysis ? `${roleAnalysis.requirements.length} role checks` : "candidate and role",
      sprite: roleAnalysis ? "lesson-pinned" : "run-queued",
      sheet: roleAnalysis ? "sheet-lessons" : "sheet-runs",
      state: state === "idle" && !hasRun ? "active" : "done"
    },
    {
      key: "evaluate",
      label: "Evaluate",
      meta: state === "running" ? "exam in progress" : hasRun ? `${passedCount}/${totalCount} checks` : "not started",
      sprite: state === "running" ? "run-running" : hasRun ? "run-complete" : "timeline-node",
      sheet: "sheet-runs",
      state: state === "running" ? "active" : hasRun ? "done" : "idle"
    },
    {
      key: "judge",
      label: "Judge",
      meta: scorecard ? (scorecard.certified ? "passed" : "needs review") : "waiting",
      sprite: scorecard?.certified ? "grader-approve" : scorecard ? "grader-reject" : "grader-deliberating",
      sheet: "sheet-judging",
      state: scorecard ? (scorecard.certified ? "done" : "attention") : state === "running" ? "active" : "idle"
    },
    {
      key: "teach",
      label: "Teach",
      meta: agentSpec ? readinessLabel(agentSpec.readiness) : "coaching next",
      sprite: agentSpec ? "lesson-applied" : "lesson-book",
      sheet: "sheet-lessons",
      state: hasCoaching ? "done" : scorecard ? "active" : "idle"
    }
  ];
}

export function buildReviewers(
  state: LoadState,
  scorecard: Scorecard | null,
  health: HealthLike,
  databaseHealth: DatabaseHealth | null,
  proofBundle: ProofBundle | null
): ProductReviewer[] {
  const traceStatusValue = scorecard?.trace_audit.status;
  const runtimeWarn = state === "error" || databaseHealth?.ok === false || traceStatusValue === "error";
  const proofReady = scorecard?.certified && scorecard.trace_audit.status === "ok";
  return [
    {
      key: "experience",
      name: "UX reviewer",
      summary: scorecard ? "workflow, score, and coaching are visible" : "room is ready for a first run",
      sprite: "candidate-document",
      status: scorecard ? "pass" : "wait",
      label: scorecard ? "clear" : "ready",
      evidence: []
    },
    {
      key: "runtime",
      name: "Runtime reviewer",
      summary: runtimeWarn
        ? traceStatusValue === "error"
          ? "TraceRazor needs attention"
          : "local service needs attention"
        : `${health?.database_backend ?? "sqlite"} storage responding`,
      sprite: runtimeWarn ? "candidate-alert" : "candidate-shield",
      status: runtimeWarn ? "warn" : "pass",
      label: runtimeWarn ? "check" : "stable",
      evidence: []
    },
    {
      key: "evidence",
      name: "Evidence reviewer",
      summary: proofReady
        ? "proof bundle and audit passed"
        : scorecard
          ? "proof bundle records the review reasons"
          : proofBundle
            ? "proof bundle is available"
            : "waiting for scorecard",
      sprite: proofReady ? "candidate-approved" : scorecard ? "candidate-review" : "candidate-audit",
      status: proofReady ? "pass" : scorecard ? "warn" : "wait",
      label: proofReady ? "passed" : scorecard ? "review" : "waiting",
      evidence: []
    }
  ];
}

export type RosterAgent = {
  key: string;
  label: string;
  sprite: string;
  sheet: string;
  state: "idle" | "active" | "done";
  meta: string;
  title: string;
};

export function buildRoster(
  running: boolean,
  counts: Record<string, number>,
  scorecard: Scorecard | null,
  simulatorModel?: string
): RosterAgent[] {
  const roles: Array<{ key: string; label: string; sheet: string; actor: string; doneMeta: (count: number) => string }> = [
    { key: "examiner", label: "Examiner", sheet: "", actor: "examiner", doneMeta: (count) => `${count} asked` },
    { key: "grader", label: "Judge panel", sheet: "sheet-judging", actor: "grader_panel", doneMeta: (count) => `${count} graded` },
    { key: "lessons", label: "Lessons", sheet: "sheet-lessons", actor: "lesson_library", doneMeta: (count) => `${count} kept` },
    { key: "trace", label: "TraceRazor", sheet: "", actor: "trace_auditor", doneMeta: () => traceRosterMeta(scorecard) },
    { key: "sim", label: "Simulator", sheet: "", actor: "system", doneMeta: () => (simulatorModel ? "scored" : "ready") }
  ];
  return roles.map((role) => {
    const count = counts[role.actor] ?? 0;
    const state: RosterAgent["state"] = running ? "active" : count > 0 ? "done" : "idle";
    const meta = running ? "working" : count > 0 ? role.doneMeta(count) : "idle";
    return {
      key: role.key,
      label: role.label,
      sprite: rosterSprite(role.key, running, count, scorecard),
      sheet: role.sheet,
      state,
      meta,
      title: `${role.label}: ${meta}`
    };
  });
}

export function rosterSprite(key: string, running: boolean, count: number, scorecard: Scorecard | null): string {
  if (key === "grader") {
    if (running) return "grader-deliberating";
    if (scorecard?.certified) return "grader-approve";
    if (scorecard) return "grader-reject";
    return "grader-deliberating";
  }
  if (key === "lessons") {
    if (running) return "new-lesson-stamp";
    if (count > 4) return "library-many";
    if (count > 0) return "library-few";
    return "library-empty";
  }
  const map: Record<string, string> = { examiner: "domain", trace: "tracerazor", sim: "simulator" };
  return map[key] ?? "candidate";
}

export function runSprite(status: string): string {
  if (status === "running") return "run-running";
  if (status === "completed") return "run-complete";
  if (status === "failed") return "fail-bead";
  return "run-queued";
}

export function traceRosterMeta(scorecard: Scorecard | null) {
  const tas = scorecard?.trace_audit.tas_score;
  if (tas !== null && tas !== undefined) return `TAS ${tas.toFixed(0)}`;
  return scorecard?.trace_audit.status ?? "idle";
}

export function readinessLabel(readiness: AgentSpec["readiness"]) {
  if (readiness === "ready") return "Ready to ship";
  if (readiness === "needs_subagents") return "Add helpers";
  return "Refine";
}

export function readinessSprite(readiness: AgentSpec["readiness"]) {
  if (readiness === "ready") return "candidate-approved";
  if (readiness === "needs_subagents") return "candidate-question";
  return "candidate-review";
}

export function refineryHeroClass(readiness: AgentSpec["readiness"]) {
  return readiness === "ready" ? "passed" : "review";
}

export function downloadJson(filename: string, payload: unknown) {
  if (typeof window === "undefined") {
    return;
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function errorMessage(exc: unknown) {
  return exc instanceof Error ? exc.message : "Unknown Interviu error";
}
