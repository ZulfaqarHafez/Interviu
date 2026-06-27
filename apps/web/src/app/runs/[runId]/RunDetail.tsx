"use client";

import Link from "next/link";
import { useQueryState, parseAsStringEnum } from "nuqs";
import { ArrowLeft, PanelRightOpen, Save } from "lucide-react";
import {
  useProofBundle,
  useReviewers,
  useScorecard,
  useTrace
} from "@/lib/queries";
import { downloadJson, errorMessage, maxTransferGap, traceScoreLabel } from "@/lib/derive";
import TraceDrawer from "@/components/trace/TraceDrawer";
import CompetencyRadar from "@/components/scorecard/CompetencyRadar";
import RunComparison from "@/components/scorecard/RunComparison";
import ProgressTrend from "@/components/progress/ProgressTrend";
import DiagnosticLibrary from "@/components/library/DiagnosticLibrary";

/**
 * Shareable run-detail view. Reuses the same composition pieces as the console
 * (radar, comparison, trend, library, trace drawer). The trace drawer's open
 * state is mirrored into `?drawer=trace` so the URL fully describes the view.
 */
export default function RunDetail({ runId }: { runId: string }) {
  const proofBundleQuery = useProofBundle(runId);
  const traceQuery = useTrace(runId);
  const scorecardQuery = useScorecard(runId);
  const reviewersQuery = useReviewers(runId);

  // Drawer open/closed driven by the URL so the view is deep-linkable.
  const [drawer, setDrawer] = useQueryState(
    "drawer",
    parseAsStringEnum(["trace", "spec", "research"]).withOptions({ history: "push" })
  );
  const drawerOpen = drawer !== null;

  const proofBundle = proofBundleQuery.data ?? null;
  const trace = traceQuery.data ?? null;
  const scorecard = scorecardQuery.data ?? proofBundle?.scorecard ?? null;
  const reviewers = reviewersQuery.data ?? proofBundle?.product_review ?? null;
  const events = trace?.events ?? proofBundle?.events ?? [];
  const agentSpec = proofBundle?.agent_spec ?? null;
  const candidateId = proofBundle?.candidate?.id ?? scorecard?.run_id ?? null;
  const candidateName = proofBundle?.candidate?.name ?? "Candidate";

  const isLoading = proofBundleQuery.isLoading && !proofBundle;
  const loadError = proofBundleQuery.error;

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: "24px 20px", display: "grid", gap: 18 }}>
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, flexWrap: "wrap" }}>
        <div style={{ display: "grid", gap: 4 }}>
          <Link
            href="/"
            style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--color-fg-muted)" }}
          >
            <ArrowLeft size={14} /> Back to console
          </Link>
          <h1 style={{ margin: 0, fontSize: 22, color: "var(--color-fg)" }}>{candidateName}</h1>
          <p style={{ margin: 0, fontSize: 13, color: "var(--color-fg-muted)" }}>
            Run <code>{runId}</code>
            {scorecard ? ` · ${scorecard.certified ? "Passed" : "Needs review"}` : ""}
            {scorecard ? ` · TraceRazor ${traceScoreLabel(scorecard)}` : ""}
            {scorecard ? ` · transfer gap ${maxTransferGap(scorecard).toFixed(2)}` : ""}
          </p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button
            type="button"
            className="command-button"
            onClick={() => void setDrawer("trace")}
          >
            <PanelRightOpen size={16} /> View trace
          </button>
          <button
            type="button"
            className="command-button"
            disabled={!proofBundle}
            onClick={() => proofBundle && downloadJson(`interviu-${runId}-proof-bundle.json`, proofBundle)}
          >
            <Save size={16} /> Export proof
          </button>
        </div>
      </header>

      {isLoading ? (
        <p style={{ color: "var(--color-fg-muted)", fontSize: 13 }}>Loading run…</p>
      ) : loadError ? (
        <p role="alert" style={{ color: "var(--color-fail)", fontSize: 13 }}>
          Could not load run {runId}: {errorMessage(loadError)}
        </p>
      ) : (
        <div className="learning-surfaces">
          <CompetencyRadar scorecard={scorecard} />
          <RunComparison runId={runId} baseline={scorecard?.prior_run_id ?? undefined} />
          <ProgressTrend candidateId={candidateId} />
          <DiagnosticLibrary candidateId={candidateId} />
        </div>
      )}

      {reviewers ? (
        <section className="panel-section" aria-label="reviewers">
          <h2 className="section-title">Reviewers</h2>
          <div className="reviewer-list">
            {reviewers.reviewers.map((reviewer) => (
              <div className={`reviewer-row ${reviewer.status}`} key={reviewer.key}>
                <span className={`sprite-sheet mini-sprite sprite-${reviewer.sprite}`} aria-hidden="true" />
                <span>
                  <strong>{reviewer.name}</strong>
                  <small>{reviewer.summary}</small>
                </span>
                <span className={`pill ${reviewer.status === "pass" ? "ready" : reviewer.status === "warn" ? "warn" : "planned"}`}>
                  {reviewer.label}
                </span>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <TraceDrawer
        events={events}
        trace={trace}
        scorecard={scorecard}
        proofBundle={proofBundle}
        agentSpec={agentSpec}
        agentResearch={null}
        open={drawerOpen}
        onOpenChange={(open) => void setDrawer(open ? "trace" : null)}
      />
    </main>
  );
}
