"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { RotateCcw, Sparkles, Loader2 } from "lucide-react";
import { useAgentRun } from "@/lib/useAgentRun";

/**
 * Portable "keep iterating" controls — Rerun the same agent (learning loop) or
 * Test the refined agent.md. Works from any page (RunDetail, agent home), not
 * just the home-page verdict. On completion it routes to the new run.
 */
export type AgentRunControlsProps = {
  candidateId: string | null;
  agentName: string;
  examPackId: string;
  /** Run to compare an improved-version test against. */
  baselineRunId?: string | null;
  /** The refined agent.md from the run's agent-spec, if any. */
  refinedMarkdown?: string | null;
  className?: string;
};

export function AgentRunControls({
  candidateId,
  agentName,
  examPackId,
  baselineRunId,
  refinedMarkdown,
  className
}: AgentRunControlsProps) {
  const router = useRouter();
  const { runStream, isRunning, error, rerun, testImproved } = useAgentRun({
    onComplete: (newRunId) => router.push(`/runs/${newRunId}`)
  });

  const canImprove = Boolean(refinedMarkdown?.trim());
  const total = runStream.totalExpected;
  const done = runStream.gradedCount;

  if (isRunning) {
    return (
      <div className={`agent-run-controls running ${className ?? ""}`} role="status">
        <Loader2 size={16} className="assay-spin" />
        <span>
          Re-testing {agentName}
          {total > 0 ? ` — ${done}/${total} probes` : "…"}
        </span>
      </div>
    );
  }

  return (
    <div className={`agent-run-controls ${className ?? ""}`}>
      <button
        type="button"
        className="command-button"
        disabled={!candidateId}
        onClick={() => candidateId && void rerun(candidateId, examPackId)}
      >
        <RotateCcw size={16} /> Rerun same agent
      </button>
      {canImprove && (
        <button
          type="button"
          className="command-button accent"
          onClick={() => void testImproved(refinedMarkdown as string, `${agentName} v2`, examPackId, baselineRunId)}
        >
          <Sparkles size={16} /> Test improved version
        </button>
      )}
      {error && <span className="agent-run-error" role="alert">{error}</span>}
    </div>
  );
}

export default AgentRunControls;
