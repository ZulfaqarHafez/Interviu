import type { CandidateConfig, Connector, ConnectorProbe, DatabaseHealth, ExamPack, ExamPackExport, ExamPackFileExport, ProofBundle, RunEvent, RunRecord, Scorecard, TracePayload } from "@/types/interviu";

function apiBaseUrl() {
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL;
  }
  if (typeof window !== "undefined") {
    const port = Number(window.location.port);
    const isLocal = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";
    if (isLocal && Number.isFinite(port) && port >= 3000 && port < 4000) {
      return `${window.location.protocol}//${window.location.hostname}:${port + 5000}`;
    }
  }
  return "http://127.0.0.1:8000";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export const interviuApi = {
  health: () => request<{ ok: boolean; tracerazor_importable: boolean; database_backend: string }>("/health"),
  databaseHealth: () => request<DatabaseHealth>("/health/database"),
  examPacks: () => request<ExamPack[]>("/exam-packs"),
  examPackExport: (packId: string) => request<ExamPackExport>(`/exam-packs/${packId}/export`),
  examPackFileExport: (packId: string) =>
    request<ExamPackFileExport>(`/exam-packs/${packId}/export-files`, {
      method: "POST"
    }),
  connectors: () => request<Connector[]>("/connectors"),
  connectorProbes: () => request<ConnectorProbe[]>("/connectors/probe"),
  candidates: () => request<CandidateConfig[]>("/candidates"),
  runs: () => request<RunRecord[]>("/runs"),
  createCandidate: (candidate: Partial<CandidateConfig>) =>
    request<CandidateConfig>("/candidates", {
      method: "POST",
      body: JSON.stringify(candidate)
    }),
  createRun: (candidateId: string, examPackId = "hr-v1") =>
    request<RunRecord>("/runs", {
      method: "POST",
      body: JSON.stringify({ candidate_id: candidateId, exam_pack_id: examPackId })
    }),
  startRun: (runId: string) =>
    request<Scorecard>(`/runs/${runId}/start`, {
      method: "POST"
    }),
  events: (runId: string) => request<RunEvent[]>(`/runs/${runId}/events`),
  scorecard: (runId: string) => request<Scorecard>(`/runs/${runId}/scorecard`),
  trace: (runId: string) => request<TracePayload>(`/runs/${runId}/trace`),
  proofBundle: (runId: string) => request<ProofBundle>(`/runs/${runId}/proof-bundle`)
};
