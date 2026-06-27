"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationOptions,
  type UseQueryOptions
} from "@tanstack/react-query";
import { interviuApi } from "@/lib/api";
import type {
  AgentSpec,
  CandidateConfig,
  CandidateProgress,
  Connector,
  ConnectorProbe,
  DatabaseHealth,
  DiagnosticLesson,
  ExamPack,
  JobScope,
  ProductReview,
  ProofBundle,
  RunComparison,
  RunEvent,
  RunRecord,
  Scorecard,
  TracePayload
} from "@/types/interviu";

type HealthPayload = { ok: boolean; tracerazor_importable: boolean; database_backend: string };

/**
 * Centralized query-key factory. Downstream components and mutations reuse these
 * so invalidation stays consistent across the app.
 */
export const queryKeys = {
  health: () => ["health"] as const,
  databaseHealth: () => ["health", "database"] as const,
  examPacks: () => ["exam-packs"] as const,
  connectors: () => ["connectors"] as const,
  connectorProbes: () => ["connectors", "probe"] as const,
  candidates: () => ["candidates"] as const,
  runs: () => ["runs"] as const,
  run: (runId: string) => ["runs", runId] as const,
  scorecard: (runId: string) => ["runs", runId, "scorecard"] as const,
  trace: (runId: string) => ["runs", runId, "trace"] as const,
  events: (runId: string) => ["runs", runId, "events"] as const,
  proofBundle: (runId: string) => ["runs", runId, "proof-bundle"] as const,
  agentSpec: (runId: string) => ["runs", runId, "agent-spec"] as const,
  reviewers: (runId: string) => ["runs", runId, "reviewers"] as const,
  runComparison: (runId: string, baseline?: string) =>
    ["runs", runId, "comparison", baseline ?? null] as const,
  runLessonsApplied: (runId: string) => ["runs", runId, "lessons-applied"] as const,
  candidateProgress: (candidateId: string) => ["candidates", candidateId, "progress"] as const,
  candidateLessons: (candidateId: string, examPackId?: string) =>
    ["candidates", candidateId, "lessons", examPackId ?? null] as const
} as const;

/** Options forwarded to a query hook, minus the fields the hook owns. */
type QueryOpts<T> = Omit<UseQueryOptions<T, Error, T>, "queryKey" | "queryFn">;

// --- Read queries -----------------------------------------------------------

export function useHealth(options?: QueryOpts<HealthPayload>) {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: () => interviuApi.health(),
    ...options
  });
}

export function useDatabaseHealth(options?: QueryOpts<DatabaseHealth>) {
  return useQuery({
    queryKey: queryKeys.databaseHealth(),
    queryFn: () => interviuApi.databaseHealth(),
    ...options
  });
}

export function useExamPacks(options?: QueryOpts<ExamPack[]>) {
  return useQuery({
    queryKey: queryKeys.examPacks(),
    queryFn: () => interviuApi.examPacks(),
    ...options
  });
}

export function useConnectors(options?: QueryOpts<Connector[]>) {
  return useQuery({
    queryKey: queryKeys.connectors(),
    queryFn: () => interviuApi.connectors(),
    ...options
  });
}

export function useConnectorProbes(options?: QueryOpts<ConnectorProbe[]>) {
  return useQuery({
    queryKey: queryKeys.connectorProbes(),
    queryFn: () => interviuApi.connectorProbes(),
    ...options
  });
}

export function useCandidates(options?: QueryOpts<CandidateConfig[]>) {
  return useQuery({
    queryKey: queryKeys.candidates(),
    queryFn: () => interviuApi.candidates(),
    ...options
  });
}

export function useRuns(options?: QueryOpts<RunRecord[]>) {
  return useQuery({
    queryKey: queryKeys.runs(),
    queryFn: () => interviuApi.runs(),
    ...options
  });
}

export function useRun(runId: string | null | undefined, options?: QueryOpts<RunRecord>) {
  return useQuery({
    queryKey: queryKeys.run(runId ?? ""),
    queryFn: () => interviuApi.proofBundle(runId as string).then((bundle) => bundle.run),
    enabled: Boolean(runId),
    ...options
  });
}

export function useScorecard(runId: string | null | undefined, options?: QueryOpts<Scorecard>) {
  return useQuery({
    queryKey: queryKeys.scorecard(runId ?? ""),
    queryFn: () => interviuApi.scorecard(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

export function useTrace(runId: string | null | undefined, options?: QueryOpts<TracePayload>) {
  return useQuery({
    queryKey: queryKeys.trace(runId ?? ""),
    queryFn: () => interviuApi.trace(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

/**
 * Stream of run events. Pass `{ live: true }` to poll roughly once a second
 * while the run is in flight.
 */
export function useEvents(
  runId: string | null | undefined,
  opts?: { live?: boolean } & QueryOpts<RunEvent[]>
) {
  const { live, ...options } = opts ?? {};
  return useQuery({
    queryKey: queryKeys.events(runId ?? ""),
    queryFn: () => interviuApi.events(runId as string),
    enabled: Boolean(runId),
    refetchInterval: live ? 1000 : false,
    ...options
  });
}

export function useProofBundle(runId: string | null | undefined, options?: QueryOpts<ProofBundle>) {
  return useQuery({
    queryKey: queryKeys.proofBundle(runId ?? ""),
    queryFn: () => interviuApi.proofBundle(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

export function useAgentSpec(runId: string | null | undefined, options?: QueryOpts<AgentSpec>) {
  return useQuery({
    queryKey: queryKeys.agentSpec(runId ?? ""),
    queryFn: () => interviuApi.agentSpec(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

export function useReviewers(runId: string | null | undefined, options?: QueryOpts<ProductReview>) {
  return useQuery({
    queryKey: queryKeys.reviewers(runId ?? ""),
    queryFn: () => interviuApi.reviewers(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

export function useCandidateProgress(
  candidateId: string | null | undefined,
  options?: QueryOpts<CandidateProgress>
) {
  return useQuery({
    queryKey: queryKeys.candidateProgress(candidateId ?? ""),
    queryFn: () => interviuApi.candidateProgress(candidateId as string),
    enabled: Boolean(candidateId),
    ...options
  });
}

export function useCandidateLessons(
  candidateId: string | null | undefined,
  examPackId?: string,
  options?: QueryOpts<DiagnosticLesson[]>
) {
  return useQuery({
    queryKey: queryKeys.candidateLessons(candidateId ?? "", examPackId),
    queryFn: () => interviuApi.candidateLessons(candidateId as string, examPackId),
    enabled: Boolean(candidateId),
    ...options
  });
}

export function useRunComparison(
  runId: string | null | undefined,
  baseline?: string,
  options?: QueryOpts<RunComparison>
) {
  return useQuery({
    queryKey: queryKeys.runComparison(runId ?? "", baseline),
    queryFn: () => interviuApi.runComparison(runId as string, baseline),
    enabled: Boolean(runId),
    ...options
  });
}

export function useRunLessonsApplied(
  runId: string | null | undefined,
  options?: QueryOpts<DiagnosticLesson[]>
) {
  return useQuery({
    queryKey: queryKeys.runLessonsApplied(runId ?? ""),
    queryFn: () => interviuApi.runLessonsApplied(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

// --- Mutations --------------------------------------------------------------

type MutationOpts<TData, TVars> = Omit<
  UseMutationOptions<TData, Error, TVars>,
  "mutationFn"
>;

export function useCreateCandidate(
  options?: MutationOpts<CandidateConfig, Partial<CandidateConfig>>
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (candidate: Partial<CandidateConfig>) => interviuApi.createCandidate(candidate),
    ...options,
    onSettled: (...args) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.candidates() });
      options?.onSettled?.(...args);
    }
  });
}

export type CreateRunVars = {
  candidateId: string;
  examPackId?: string;
  jobScope?: JobScope | null;
};

export function useCreateRun(options?: MutationOpts<RunRecord, CreateRunVars>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ candidateId, examPackId = "hr-v1", jobScope = null }: CreateRunVars) =>
      interviuApi.createRun(candidateId, examPackId, jobScope),
    ...options,
    onSettled: (...args) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs() });
      options?.onSettled?.(...args);
    }
  });
}

export function useStartRun(options?: MutationOpts<Scorecard, string>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => interviuApi.startRun(runId),
    ...options,
    onSettled: (data, error, runId, ...rest) => {
      void queryClient.invalidateQueries({ queryKey: queryKeys.runs() });
      void queryClient.invalidateQueries({ queryKey: queryKeys.run(runId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.scorecard(runId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.events(runId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.trace(runId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.proofBundle(runId) });
      void queryClient.invalidateQueries({ queryKey: queryKeys.reviewers(runId) });
      options?.onSettled?.(data, error, runId, ...rest);
    }
  });
}
