"use client";

import * as React from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, AlertTriangle, Circle, FlaskConical } from "lucide-react";
import { useCandidates, useRuns, useAgentSpec } from "@/lib/queries";
import ProgressTrend from "@/components/progress/ProgressTrend";
import RunComparison from "@/components/scorecard/RunComparison";
import AgentRunControls from "@/components/assay/AgentRunControls";
import { AgentArt } from "@/components/ui/EmptyArt";
import type { RunRecord } from "@/types/assay";

/**
 * The agent's home: lead with the score trajectory (does it get better across
 * runs?), keep the iterate controls one click away, and list the run history.
 */
export default function AgentHome({ candidateId }: { candidateId: string }) {
  const candidatesQuery = useCandidates();
  const runsQuery = useRuns();

  const candidate = (candidatesQuery.data ?? []).find((item) => item.id === candidateId) ?? null;
  const runs = React.useMemo(
    () => (runsQuery.data ?? []).filter((run) => run.candidate_id === candidateId),
    [runsQuery.data, candidateId]
  );
  const latest = runs[0] ?? null; // GET /runs is newest-first
  const agentSpecQuery = useAgentSpec(latest?.id ?? null);

  const name = candidate?.name ?? "Agent";
  const packId = latest?.source_pack_id ?? latest?.exam_pack_id ?? "hr-v1";
  const refinedMarkdown = agentSpecQuery.data?.agent_markdown ?? null;

  const scored = runs.filter((run) => run.status === "completed" && typeof run.certified === "boolean");
  const latestScore = scoreOf(scored[0]);
  const prevScore = scoreOf(scored[1]);
  const delta = latestScore != null && prevScore != null ? latestScore - prevScore : null;

  return (
    <main className="ws-page">
      <header className="ws-head">
        <div>
          <Link href="/agents" className="rd-back-link"><ArrowLeft size={14} /> Agents</Link>
          <h1>{name}</h1>
          <p>
            {candidate?.adapter_type ?? "agent"} · {runs.length} run{runs.length === 1 ? "" : "s"}
            {latestScore != null && (
              <>
                {" · latest "}
                <strong>{latestScore}%</strong>
                {delta != null && delta !== 0 && (
                  <span className={delta > 0 ? "agent-delta up" : "agent-delta down"}>
                    {" "}({delta > 0 ? "+" : ""}{delta}% vs previous)
                  </span>
                )}
              </>
            )}
          </p>
        </div>
        <AgentRunControls
          candidateId={candidateId}
          agentName={name}
          examPackId={packId}
          baselineRunId={latest?.id ?? null}
          refinedMarkdown={refinedMarkdown}
        />
      </header>

      {runs.length === 0 ? (
        <div className="ws-empty-rich">
          <AgentArt size={104} className="ws-empty-art" />
          <h2>No runs yet for this agent</h2>
          <p>Run it through an adversarial exam and its score trajectory will build up here.</p>
          <Link href="/" className="ws-empty-cta"><FlaskConical size={15} /> Test this agent</Link>
        </div>
      ) : (
        <>
          <div className="learning-surfaces">
            <ProgressTrend candidateId={candidateId} />
            {latest ? <RunComparison runId={latest.id} /> : null}
          </div>

          <div className="ws-table-wrap">
            <table className="ws-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Verdict</th>
                  <th className="num">Score</th>
                  <th>Status</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => {
                  const verdict = run.status === "completed" && typeof run.certified === "boolean"
                    ? (run.certified ? "ship" : "hold")
                    : null;
                  const score = scoreLabel(run);
                  return (
                    <tr key={run.id}>
                      <td data-label="Run">
                        <Link href={`/runs/${run.id}`} className="ws-cell-strong mono">{run.id}</Link>
                        <div className="ws-cell-sub">{run.created_at?.slice(0, 16).replace("T", " ") ?? ""}</div>
                      </td>
                      <td data-label="Verdict">
                        {verdict === "ship" ? (
                          <span className="ws-verdict ship"><CheckCircle2 size={13} /> Ship</span>
                        ) : verdict === "hold" ? (
                          <span className="ws-verdict hold"><AlertTriangle size={13} /> Needs review</span>
                        ) : (
                          <span className="ws-verdict idle">—</span>
                        )}
                      </td>
                      <td className="num" data-label="Score">{score}</td>
                      <td data-label="Status"><span className="ws-status done"><Circle size={9} /> {run.status}</span></td>
                      <td className="num ws-row-action"><Link href={`/runs/${run.id}`} className="ws-row-link">Open →</Link></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </main>
  );
}

/** Latest pass-rate as a 0-100 number, or null when not scored. */
function scoreOf(run: RunRecord | undefined): number | null {
  if (!run || typeof run.pass_count !== "number" || typeof run.total_count !== "number" || !run.total_count) {
    return null;
  }
  return Math.round((run.pass_count / run.total_count) * 100);
}

function scoreLabel(run: RunRecord): string {
  if (typeof run.pass_count === "number" && typeof run.total_count === "number") {
    return `${run.pass_count}/${run.total_count}`;
  }
  return "—";
}
