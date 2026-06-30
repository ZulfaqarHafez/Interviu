"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { assayApi } from "@/lib/api";
import type {
  AgentSpec,
  DiagnosticLesson,
  JobScope,
  ProductReview,
  ProofBundle,
  RunComparison,
  RunEvent,
  RunRecord,
  Scorecard,
  TracePayload
} from "@/types/assay";
import { queryKeys, type MutationOpts, type QueryOpts } from "./keys";

// --- Read queries -----------------------------------------------------------

export function useRuns(options?: QueryOpts<RunRecord[]>) {
  return useQuery({
    queryKey: queryKeys.runs(),
    queryFn: () => assayApi.runs(),
    ...options
  });
}

export function useRun(runId: string | null | undefined, options?: QueryOpts<RunRecord>) {
  return useQuery({
    queryKey: queryKeys.run(runId ?? ""),
    queryFn: () => assayApi.proofBundle(runId as string).then((bundle) => bundle.run),
    enabled: Boolean(runId),
    ...options
  });
}

export function useScorecard(runId: string | null | undefined, options?: QueryOpts<Scorecard>) {
  return useQuery({
    queryKey: queryKeys.scorecard(runId ?? ""),
    queryFn: () => assayApi.scorecard(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

export function useTrace(runId: string | null | undefined, options?: QueryOpts<TracePayload>) {
  return useQuery({
    queryKey: queryKeys.trace(runId ?? ""),
    queryFn: () => assayApi.trace(runId as string),
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
    queryFn: () => assayApi.events(runId as string),
    enabled: Boolean(runId),
    refetchInterval: live ? 1000 : false,
    ...options
  });
}

export function useProofBundle(runId: string | null | undefined, options?: QueryOpts<ProofBundle>) {
  return useQuery({
    queryKey: queryKeys.proofBundle(runId ?? ""),
    queryFn: () => assayApi.proofBundle(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

export function useAgentSpec(runId: string | null | undefined, options?: QueryOpts<AgentSpec>) {
  return useQuery({
    queryKey: queryKeys.agentSpec(runId ?? ""),
    queryFn: () => assayApi.agentSpec(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

export function useReviewers(runId: string | null | undefined, options?: QueryOpts<ProductReview>) {
  return useQuery({
    queryKey: queryKeys.reviewers(runId ?? ""),
    queryFn: () => assayApi.reviewers(runId as string),
    enabled: Boolean(runId),
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
    queryFn: () => assayApi.runComparison(runId as string, baseline),
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
    queryFn: () => assayApi.runLessonsApplied(runId as string),
    enabled: Boolean(runId),
    ...options
  });
}

// --- Mutations --------------------------------------------------------------

export type CreateRunVars = {
  candidateId: string;
  examPackId?: string;
  jobScope?: JobScope | null;
  baselineRunId?: string | null;
};

export function useCreateRun(options?: MutationOpts<RunRecord, CreateRunVars>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ candidateId, examPackId = "hr-v1", jobScope = null, baselineRunId = null }: CreateRunVars) =>
      assayApi.createRun(candidateId, examPackId, jobScope, baselineRunId),
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
    mutationFn: (runId: string) => assayApi.startRun(runId),
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
