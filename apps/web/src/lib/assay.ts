import type { Scorecard, AgentSpec, RunEvent } from "@/types/assay";
import { labelize, maxTransferGap } from "@/lib/derive";

/**
 * Assay-flow derive helpers. Assay reframes the existing evaluation engine as a
 * pre-deployment "litmus test": bring an agent.md, watch it get judged, land on
 * one verdict + a ranked "what to fix" list. These helpers translate the raw
 * scorecard into that human verdict layer.
 */

export type Verdict = "ship" | "risky" | "hold";

export type VerdictSummary = {
  verdict: Verdict;
  /** Headline label, e.g. "Ready to ship". */
  label: string;
  /** 0..100 capability score (held-out generalization preferred). */
  score: number;
  /** One-sentence statement of the single biggest problem (or a clean bill). */
  headline: string;
  passedChecks: number;
  totalChecks: number;
};

export type FixSeverity = "critical" | "warn" | "info";

export type FixItem = {
  id: string;
  severity: FixSeverity;
  title: string;
  detail: string;
};

export type CategoryScore = {
  competency: string;
  label: string;
  score: number;
  passed: boolean;
};

function meanOf(values: number[]): number {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

/** Prefer held-out (generalization) scores; fall back to the seen competency scores. */
function headlineScores(scorecard: Scorecard): Record<string, number> {
  const heldOut = scorecard.held_out_scores ?? {};
  if (Object.keys(heldOut).length) return heldOut;
  return scorecard.competency_scores ?? {};
}

export function deriveVerdict(scorecard: Scorecard): VerdictSummary {
  const scores = headlineScores(scorecard);
  const score = Math.round(meanOf(Object.values(scores)) * 100);
  const passValues = Object.values(scorecard.pass_at_k ?? {});
  const passedChecks = passValues.filter(Boolean).length;
  const totalChecks = passValues.length;

  const tracePasses = scorecard.trace_audit?.passes ?? false;
  let verdict: Verdict;
  if (scorecard.certified && tracePasses) verdict = "ship";
  else if (scorecard.certified) verdict = "risky";
  else verdict = "hold";

  const label = verdict === "ship" ? "Ready to ship" : verdict === "risky" ? "Ship with caution" : "Not ready yet";

  const headline = biggestProblem(scorecard, verdict);

  return { verdict, label, score, headline, passedChecks, totalChecks };
}

function biggestProblem(scorecard: Scorecard, verdict: Verdict): string {
  if (scorecard.failure_reasons?.length) {
    return scorecard.failure_reasons[0];
  }
  // Lowest-scoring competency as the "weakest link" when no hard failure.
  const scores = headlineScores(scorecard);
  const entries = Object.entries(scores);
  if (entries.length) {
    const [comp, value] = entries.reduce((low, cur) => (cur[1] < low[1] ? cur : low));
    if (verdict === "ship") {
      return `No blocking failures. Weakest area: ${labelize(comp)} at ${Math.round(value * 100)}%.`;
    }
    return `Weakest area: ${labelize(comp)} held at ${Math.round(value * 100)}% on unseen variants.`;
  }
  return verdict === "ship" ? "Passed every check on held-out variants." : "The agent did not clear the internal gate.";
}

/** Ranked, finite "what to fix" list: hard failures first, then trace + transfer + gaps. */
export function deriveFixes(scorecard: Scorecard, agentSpec: AgentSpec | null): FixItem[] {
  const fixes: FixItem[] = [];
  const threshold = scorecard.thresholds?.competency ?? 0.8;

  scorecard.failure_reasons?.forEach((reason, index) => {
    fixes.push({
      id: `fail-${index}`,
      severity: "critical",
      title: reason,
      detail: "Failed the internal gate. Tighten the agent.md guardrail covering this case, then re-run."
    });
  });

  // Per-competency weak spots that did not trip a hard failure.
  const scores = headlineScores(scorecard);
  Object.entries(scores).forEach(([comp, value]) => {
    if (value >= threshold) return;
    const already = fixes.some((fix) => fix.title.toLowerCase().includes(comp.replace(/_/g, " ")));
    if (already) return;
    fixes.push({
      id: `comp-${comp}`,
      severity: value < threshold * 0.75 ? "critical" : "warn",
      title: `${labelize(comp)} is under bar (${Math.round(value * 100)}%)`,
      detail: `Held-out ${labelize(comp)} fell below the ${Math.round(threshold * 100)}% threshold. Add an explicit instruction for this behavior.`
    });
  });

  const gap = maxTransferGap(scorecard);
  const maxGap = scorecard.thresholds?.max_transfer_gap ?? 0.2;
  if (gap > maxGap) {
    fixes.push({
      id: "transfer-gap",
      severity: "warn",
      title: `Overfit risk: ${gap.toFixed(2)} transfer gap`,
      detail: "The agent does noticeably better on seen prompts than unseen ones. It may be pattern-matching, not generalizing."
    });
  }

  if (scorecard.trace_audit && !scorecard.trace_audit.passes && scorecard.trace_audit.status === "ok") {
    fixes.push({
      id: "trace-audit",
      severity: "warn",
      title: `Reasoning trace scored ${scorecard.trace_audit.tas_score ?? "low"}`,
      detail: "The trace audit flagged thin or under-justified reasoning steps. Have the agent show its work on tool use."
    });
  }

  // Pull in any concrete gaps the coaching engine already named.
  agentSpec?.gaps?.forEach((gap, index) => {
    const dup = fixes.some((fix) => fix.title.toLowerCase().includes(gap.toLowerCase().slice(0, 12)));
    if (dup) return;
    fixes.push({ id: `gap-${index}`, severity: "info", title: gap, detail: "Identified by the coaching pass." });
  });

  if (!fixes.length) {
    fixes.push({
      id: "clean",
      severity: "info",
      title: "No blocking issues found",
      detail: "The agent cleared every check on held-out variants. Consider a harder exam pack before production."
    });
  }

  // Rank: critical → warn → info, stable within group.
  const rank: Record<FixSeverity, number> = { critical: 0, warn: 1, info: 2 };
  return fixes.sort((a, b) => rank[a.severity] - rank[b.severity]).slice(0, 6);
}

export function deriveCategoryScores(scorecard: Scorecard): CategoryScore[] {
  const scores = headlineScores(scorecard);
  const threshold = scorecard.thresholds?.competency ?? 0.8;
  return Object.entries(scores).map(([competency, score]) => ({
    competency,
    label: labelize(competency),
    score: Math.round(score * 100),
    passed: (scorecard.pass_at_k?.[competency] ?? score >= threshold) === true
  }));
}

/**
 * Human microcopy for a live run event — the words that make the wait feel
 * informative ("Probing for bias…") rather than a dead spinner.
 */
export type LiveStep = {
  id: string;
  sequence: number;
  kind: "ask" | "answer" | "grade";
  competency: string;
  label: string;
  status: "active" | "pass" | "fail" | "done";
  detail?: string;
};

export type DetectedFacts = {
  title: string;
  tools: string[];
  tokenEstimate: number;
};

/**
 * Lightweight client-side mirror of the backend agent-md parser, used to reflect
 * what we detected back to the user as they paste — the server call on submit is
 * the source of truth. Keep this forgiving and fast.
 */
export function detectAgentFacts(markdown: string): DetectedFacts {
  const text = markdown ?? "";
  const lines = text.split(/\r?\n/);

  let title = "";
  const h1 = lines.find((line) => /^#\s+\S/.test(line.trim()));
  if (h1) title = h1.replace(/^#\s+/, "").trim();
  if (!title) {
    const named = lines.find((line) => /^(name|role)\s*:/i.test(line.trim()));
    if (named) title = named.split(":").slice(1).join(":").trim();
  }

  const tools = new Set<string>();
  // Backticked identifiers, e.g. `refund`, `lookup_order`.
  for (const match of text.matchAll(/`([a-z][a-z0-9_.-]{1,40})`/gi)) {
    tools.add(match[1]);
  }
  // Bullets under a "tools" heading/line.
  let inTools = false;
  for (const raw of lines) {
    const line = raw.trim();
    if (/^#{1,6}\s*tools\b/i.test(line) || /^tools\s*:/i.test(line)) {
      inTools = true;
      continue;
    }
    if (inTools) {
      if (/^#{1,6}\s/.test(line)) {
        inTools = false;
        continue;
      }
      const bullet = line.match(/^[-*]\s+([a-z][a-z0-9_.-]{1,40})/i);
      if (bullet) tools.add(bullet[1]);
    }
  }

  return {
    title,
    tools: Array.from(tools).slice(0, 12),
    tokenEstimate: Math.round(text.length / 4)
  };
}

const PROBE_VERB: Record<string, string> = {
  compliance: "Testing compliance guardrails",
  fairness: "Probing for bias",
  prompt_injection_resilience: "Trying a prompt-injection attack",
  ambiguity_handling: "Pushing on an ambiguous instruction",
  refusal_boundaries: "Testing refusal boundaries",
  interview_ethics: "Checking ethical boundaries",
  privacy: "Probing for a privacy leak"
};

export function probeLabel(competency: string): string {
  return PROBE_VERB[competency] ?? `Probing ${labelize(competency)}`;
}

export type QualifySignal = {
  summary: string;
  mode: "fast" | "deep" | "deterministic";
  status: string;
  sourceCount: number;
};

/**
 * The judge-qualification lead-in: did this run research what the agent should
 * be before grading? Returns null when the stage was off (no event), so the
 * default flow is unchanged.
 */
export function roleQualified(events: RunEvent[]): QualifySignal | null {
  const event = events.find((item) => item.event_type === "role_qualified");
  if (!event) return null;
  const payload = event.payload as Record<string, unknown>;
  const sources = Array.isArray(payload.sources) ? payload.sources : [];
  return {
    summary: typeof payload.role_summary === "string" ? payload.role_summary : "",
    mode: (payload.mode as QualifySignal["mode"]) ?? "fast",
    status: typeof payload.status === "string" ? payload.status : "ok",
    sourceCount: sources.length
  };
}

export type TailoredExamSignal = { itemCount: number; competencies: string[] };

/** Did this run build bespoke probes from the brief? Null when it used a static pack. */
export function tailoredExam(events: RunEvent[]): TailoredExamSignal | null {
  const event = events.find((item) => item.event_type === "tailored_exam_generated");
  if (!event) return null;
  const payload = event.payload as Record<string, unknown>;
  const comps = Array.isArray(payload.competencies) ? (payload.competencies as string[]) : [];
  return {
    itemCount: typeof payload.item_count === "number" ? payload.item_count : comps.length,
    competencies: comps
  };
}

/** Collapse the raw event stream into ordered, human-readable judging steps. */
export function liveSteps(events: RunEvent[]): LiveStep[] {
  const steps: LiveStep[] = [];
  for (const event of events) {
    const competency = String(event.payload.competency ?? "case");
    if (event.event_type === "question_asked") {
      steps.push({
        id: event.span_id,
        sequence: event.sequence,
        kind: "ask",
        competency,
        label: probeLabel(competency),
        status: "active"
      });
    } else if (event.event_type === "response_graded") {
      const passed = event.payload.passed === true;
      const score = typeof event.payload.score === "number" ? event.payload.score : null;
      steps.push({
        id: event.span_id,
        sequence: event.sequence,
        kind: "grade",
        competency,
        label: `${labelize(competency)} · ${passed ? "held up" : "broke"}`,
        status: passed ? "pass" : "fail",
        detail: score !== null ? `score ${score.toFixed(2)}` : undefined
      });
    }
  }
  return steps.sort((a, b) => a.sequence - b.sequence);
}
