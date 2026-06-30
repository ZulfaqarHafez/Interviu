"use client";

import * as React from "react";
import { assayApi } from "@/lib/api";
import { useExamPacks } from "@/lib/queries";
import { useRunStream } from "@/lib/useRunStream";
import { errorMessage } from "@/lib/derive";

/**
 * Reusable run orchestration so the iterate loop (rerun / test improved) works
 * from ANY page, not just the home-page phase machine. Wraps useRunStream +
 * createRun + candidateFromMarkdown. Callers render their own progress from the
 * returned `runStream` and navigate on `onComplete(newRunId)`.
 */
export type UseAgentRunOptions = {
  /** Fired once when a started run resolves, with the new run id. */
  onComplete?: (runId: string) => void;
};

export function useAgentRun(options: UseAgentRunOptions = {}) {
  const runStream = useRunStream();
  const examPacksQuery = useExamPacks();
  const packsData = examPacksQuery.data;
  const packs = React.useMemo(() => packsData ?? [], [packsData]);
  const [error, setError] = React.useState<string | null>(null);
  const [starting, setStarting] = React.useState(false);

  // Keep the completion callback in a ref so the effect doesn't re-fire when a
  // caller passes a fresh inline options object each render.
  const onCompleteRef = React.useRef(options.onComplete);
  onCompleteRef.current = options.onComplete;
  const firedFor = React.useRef<string | null>(null);

  React.useEffect(() => {
    if (runStream.status === "completed" && runStream.scorecard) {
      const runId = runStream.scorecard.run_id;
      if (firedFor.current !== runId) {
        firedFor.current = runId;
        onCompleteRef.current?.(runId);
      }
    }
  }, [runStream.status, runStream.scorecard]);

  // itemCount only drives the progress bar; runStream tolerates undefined.
  const itemCountFor = React.useCallback(
    (examPackId: string) => packs.find((item) => item.id === examPackId)?.items.length,
    [packs]
  );

  /** Re-test an already-registered candidate (the learning loop applies). */
  const rerun = React.useCallback(
    async (candidateId: string, examPackId: string) => {
      setError(null);
      setStarting(true);
      runStream.reset();
      firedFor.current = null;
      try {
        const createdRun = await assayApi.createRun(candidateId, examPackId, null);
        runStream.start(createdRun.id, { k: createdRun.k, itemCount: itemCountFor(createdRun.exam_pack_id) });
        return createdRun.id;
      } catch (exc) {
        setError(errorMessage(exc));
        return null;
      } finally {
        setStarting(false);
      }
    },
    [itemCountFor, runStream]
  );

  /** Register the refined agent.md as a new candidate and test it. */
  const testImproved = React.useCallback(
    async (refinedMarkdown: string, name: string, examPackId: string, baselineRunId?: string | null) => {
      const refined = refinedMarkdown.trim();
      if (!refined) return null;
      setError(null);
      setStarting(true);
      runStream.reset();
      firedFor.current = null;
      try {
        const intake = await assayApi.candidateFromMarkdown(refined, name);
        const createdRun = await assayApi.createRun(intake.candidate.id, examPackId, null, baselineRunId ?? null);
        runStream.start(createdRun.id, { k: createdRun.k, itemCount: itemCountFor(createdRun.exam_pack_id) });
        return { runId: createdRun.id, candidateId: intake.candidate.id };
      } catch (exc) {
        setError(errorMessage(exc));
        return null;
      } finally {
        setStarting(false);
      }
    },
    [itemCountFor, runStream]
  );

  const isRunning =
    starting || runStream.status === "queued" || runStream.status === "running";

  return {
    runStream,
    isRunning,
    error: error ?? (runStream.status === "failed" ? runStream.error : null),
    rerun,
    testImproved,
    reset: runStream.reset
  };
}
