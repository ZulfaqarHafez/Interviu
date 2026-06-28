import type {
  ExamPack,
  Scorecard
} from "@/types/assay";

/**
 * Pure derive helpers ported verbatim from page.tsx so every console component
 * shares one source of truth. page.tsx keeps its own copies until the
 * integration agent switches it to import from here.
 */

export type LoadState = "idle" | "loading" | "running" | "complete" | "error";

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
  return exc instanceof Error ? exc.message : "Unknown Assay error";
}
