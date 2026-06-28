"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, AlertTriangle, Circle, Loader2, FlaskConical } from "lucide-react";
import { useRuns, useCandidates } from "@/lib/queries";
import { VialArt } from "@/components/ui/EmptyArt";
import type { RunRecord } from "@/types/assay";

/**
 * Experiments — the run history of the workspace. Every run an agent has been
 * put through, scored and certified, newest first. Reuses useRuns/useScorecard.
 */
export default function ExperimentsPage() {
  const runsQuery = useRuns();
  const candidatesQuery = useCandidates();
  const runs = React.useMemo(() => runsQuery.data ?? [], [runsQuery.data]);
  const candidates = React.useMemo(() => candidatesQuery.data ?? [], [candidatesQuery.data]);
  const nameById = React.useMemo(() => {
    const m: Record<string, string> = {};
    for (const c of candidates) m[c.id] = c.name;
    return m;
  }, [candidates]);

  return (
    <main className="ws-page">
      <header className="ws-head">
        <div>
          <h1>Experiments</h1>
          <p>Every run, scored and certified at pass^k. Open one to compare against its previous run and inspect the trace.</p>
        </div>
        <span className="ws-count">{runs.length} run{runs.length === 1 ? "" : "s"}</span>
      </header>

      {runsQuery.isLoading ? (
        <div className="ws-table-wrap" aria-hidden="true">
          {Array.from({ length: 8 }).map((_, i) => (
            <div className="ws-skeleton-row" key={i} />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <div className="ws-empty-rich">
          <VialArt size={104} className="ws-empty-art" />
          <h2>No experiments yet</h2>
          <p>Run an agent through an adversarial suite and every scored, certified run will land here — ready to compare and inspect.</p>
          <Link href="/" className="ws-empty-cta"><FlaskConical size={15} /> Run your first test</Link>
        </div>
      ) : (
        <div className="ws-table-wrap">
          <table className="ws-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Suite</th>
                <th>Verdict</th>
                <th className="num">Score</th>
                <th className="num">k</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <RunRow key={run.id} run={run} agentName={nameById[run.candidate_id] ?? run.candidate_id} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

function RunRow({ run, agentName }: { run: RunRecord; agentName: string }) {
  // Scorecard summary is attached to the run by GET /runs (no per-row fetch).
  const scored = run.status === "completed" && typeof run.certified === "boolean";
  const verdict = scored ? (run.certified ? "ship" : "hold") : null;
  const passCount = run.pass_count ?? 0;
  const total = run.total_count ?? 0;

  return (
    <tr>
      <td>
        <Link href={`/runs/${run.id}`} className="ws-cell-strong">{agentName}</Link>
        <div className="ws-cell-sub mono">{run.id}</div>
      </td>
      <td>
        {run.qualification_status === "tailored" ? (
          <span className="ws-tag" title={run.role_brief_summary ?? "Probes tailored to this agent"}>Tailored</span>
        ) : (
          run.exam_pack_id
        )}
      </td>
      <td>
        {verdict === "ship" ? (
          <span className="ws-verdict ship"><CheckCircle2 size={13} /> Ship</span>
        ) : verdict === "hold" ? (
          <span className="ws-verdict hold"><AlertTriangle size={13} /> Needs review</span>
        ) : (
          <span className="ws-verdict idle">—</span>
        )}
      </td>
      <td className="num">{scored ? `${passCount}/${total}` : "—"}</td>
      <td className="num">{run.k}×</td>
      <td><RunStatus status={run.status} /></td>
      <td className="num"><Link href={`/runs/${run.id}`} className="ws-row-link">Open →</Link></td>
    </tr>
  );
}

function RunStatus({ status }: { status: RunRecord["status"] }) {
  if (status === "running" || status === "created")
    return <span className="ws-status running"><Loader2 size={12} className="assay-spin" /> {status}</span>;
  if (status === "failed") return <span className="ws-status failed"><AlertTriangle size={12} /> failed</span>;
  return <span className="ws-status done"><Circle size={9} /> {status}</span>;
}
