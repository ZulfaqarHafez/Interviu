"use client";

import * as React from "react";
import Link from "next/link";
import { CheckCircle2, AlertTriangle, FlaskConical } from "lucide-react";
import { useCandidates, useRuns } from "@/lib/queries";
import { AgentArt } from "@/components/ui/EmptyArt";
import type { RunRecord } from "@/types/assay";

/**
 * Agents — the candidate definitions under test, deduplicated by name and rolled
 * up: how many experiments each has been through, its latest verdict, and a jump
 * to the most recent run. One agent definition = one row.
 */
export default function AgentsPage() {
  const candidatesQuery = useCandidates();
  const runsQuery = useRuns();
  const candidates = React.useMemo(() => candidatesQuery.data ?? [], [candidatesQuery.data]);
  const runs = React.useMemo(() => runsQuery.data ?? [], [runsQuery.data]);

  const rows = React.useMemo(() => groupAgents(candidates, runs), [candidates, runs]);

  return (
    <main className="ws-page">
      <header className="ws-head">
        <div>
          <h1>Agents</h1>
          <p>Every agent definition under test, with its reliability rolled up across runs.</p>
        </div>
        <span className="ws-count">{rows.length} agent{rows.length === 1 ? "" : "s"}</span>
      </header>

      {candidatesQuery.isLoading ? (
        <div className="ws-table-wrap" aria-hidden="true">
          {Array.from({ length: 6 }).map((_, i) => (
            <div className="ws-skeleton-row" key={i} />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <div className="ws-empty-rich">
          <AgentArt size={104} className="ws-empty-art" />
          <h2>No agents yet</h2>
          <p>Every agent definition you test gets registered here, with its reliability rolled up across runs.</p>
          <Link href="/" className="ws-empty-cta"><FlaskConical size={15} /> Test an agent</Link>
        </div>
      ) : (
        <div className="ws-table-wrap">
          <table className="ws-table">
            <thead>
              <tr>
                <th>Agent</th>
                <th>Adapter</th>
                <th className="num">Runs</th>
                <th>Latest verdict</th>
                <th className="num">Latest score</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.name}>
                  <td>
                    {r.latestRunId ? (
                      <Link href={`/runs/${r.latestRunId}`} className="ws-cell-strong">{r.name}</Link>
                    ) : (
                      <span className="ws-cell-strong">{r.name}</span>
                    )}
                    <div className="ws-cell-sub">{r.adapter}</div>
                  </td>
                  <td><span className="ws-chip accent">{r.adapter}</span></td>
                  <td className="num">{r.runCount}</td>
                  <td>
                    {r.verdict === "ship" ? (
                      <span className="ws-verdict ship"><CheckCircle2 size={13} /> Ship</span>
                    ) : r.verdict === "hold" ? (
                      <span className="ws-verdict hold"><AlertTriangle size={13} /> Needs review</span>
                    ) : (
                      <span className="ws-verdict idle">—</span>
                    )}
                  </td>
                  <td className="num">{r.score ?? "—"}</td>
                  <td className="num">
                    {r.latestRunId ? <Link href={`/runs/${r.latestRunId}`} className="ws-row-link">Open →</Link> : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

type AgentRow = {
  name: string;
  adapter: string;
  runCount: number;
  latestRunId: string | null;
  verdict: "ship" | "hold" | null;
  score: string | null;
};

function groupAgents(
  candidates: { id: string; name: string; adapter_type: string }[],
  runs: RunRecord[]
): AgentRow[] {
  const idToName: Record<string, string> = {};
  const idToAdapter: Record<string, string> = {};
  for (const c of candidates) {
    idToName[c.id] = c.name;
    idToAdapter[c.id] = c.adapter_type;
  }
  const map = new Map<string, AgentRow>();
  // Seed from candidates so agents with zero runs still appear.
  for (const c of candidates) {
    if (!map.has(c.name)) {
      map.set(c.name, { name: c.name, adapter: c.adapter_type, runCount: 0, latestRunId: null, verdict: null, score: null });
    }
  }
  // Runs come newest-first; the first run we see per name is the latest.
  for (const run of runs) {
    const name = idToName[run.candidate_id];
    if (!name) continue;
    const row = map.get(name) ?? { name, adapter: idToAdapter[run.candidate_id] ?? "—", runCount: 0, latestRunId: null, verdict: null, score: null };
    row.runCount += 1;
    if (!row.latestRunId) {
      row.latestRunId = run.id;
      if (run.status === "completed" && typeof run.certified === "boolean") {
        row.verdict = run.certified ? "ship" : "hold";
        if (typeof run.pass_count === "number" && typeof run.total_count === "number") {
          row.score = `${run.pass_count}/${run.total_count}`;
        }
      }
    }
    map.set(name, row);
  }
  return Array.from(map.values()).sort((a, b) => b.runCount - a.runCount);
}
